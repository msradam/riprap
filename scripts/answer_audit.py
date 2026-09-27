"""Audit answer claims for the five error classes in
riprap/core/burr/answer_checks.py (refactor 3).

    answer_audit.py audit tests/question_eval/v1 tests/question_eval/v2_1 ...
    answer_audit.py entail tests/question_eval/v2_1 tests/question_eval/v3g
    answer_audit.py rebuild-docs tests/question_eval/audit_docs_30.json tests/question_eval/v2_1

`audit` reads the run records `scripts/question_eval.py run` writes and
prints hits per class per arm, for answer claims and for all claims; it
writes audit.json next to the arm directories with every hit.

Each record's documents come from, in order: the record's own `documents`
(runs made after refactor 3); for live sources, the record's own claims
citing only that source (they restate it as it was at run time); the
rebuilt documents file (`rebuild-docs`: one no-LLM run per question, so
baked sources are exact and live ones are from the rebuild time).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DOCS_30 = ROOT / "tests" / "question_eval" / "audit_docs_30.json"
LIVE = {"nws_alerts", "nws_obs", "noaa_tides", "usgs_gauges", "floodnet", "nyc311", "nyc311_nta",
        "floodnet_forecast", "ttm_311_forecast", "ttm_battery_surge"}


def _questions() -> dict[str, dict]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import question_eval

    return {q["id"]: q for q in question_eval._load_questions()}


def record_docs(rec: dict, rebuilt: dict[str, dict[str, str]]) -> dict[str, str]:
    if rec.get("documents"):
        return rec["documents"]
    docs = dict(rebuilt.get(rec["id"].replace("_rep", ""), {}))
    for c in rec.get("claims") or []:
        ids = c.get("doc_ids") or []
        if len(ids) == 1 and ids[0] in LIVE and c.get("section") != "answer":
            docs[ids[0]] = c["text"]
    return docs


def audit_record(rec: dict, question: str, docs: dict[str, str]) -> list[dict]:
    from riprap.core.burr import answer_checks as ac

    hits = []
    answer = [c for c in rec.get("claims") or [] if c.get("section") == "answer"]
    for c in rec.get("claims") or []:
        for cls, reason in ac.check_claim(c["text"], c.get("doc_ids") or [], docs):
            hits.append({"id": rec["id"], "section": c["section"], "class": cls, "reason": reason,
                         "text": c["text"]})
    if rec.get("answer_lead"):  # extractive: the facts are verbatim, so check the lead
        facts = [c["doc_ids"][0] for c in answer if c.get("doc_ids")]
        for cls, reason in ac.check_lead(rec["answer_lead"], facts, question, docs, rec.get("values")):
            hits.append({"id": rec["id"], "section": "answer", "class": cls, "reason": reason,
                         "text": f"{rec['answer_lead']}: {', '.join(facts)}"})
    for cls, reason in ac.check_answer([c["text"] for c in answer], question, docs, rec.get("values")):
        hits.append({"id": rec["id"], "section": "answer", "class": cls, "reason": reason,
                     "text": " ".join(c["text"] for c in answer)})
    return hits


def cmd_audit(dirs: list[Path]) -> None:
    from riprap.core.burr.answer_checks import CLASSES

    qs = _questions()
    rebuilt = json.loads(DOCS_30.read_text()) if DOCS_30.exists() else {}
    report = {}
    for d in dirs:
        hits, n_answers = [], 0
        for f in sorted(d.glob("*.json")):
            rec = json.loads(f.read_text())
            if "claims" not in rec or f.stem.endswith("_rep"):
                continue
            n_answers += any(c.get("section") == "answer" for c in rec["claims"])
            hits += audit_record(rec, qs[rec["id"]]["question"], record_docs(rec, rebuilt))
        ans = Counter(h["class"] for h in hits if h["section"] == "answer")
        every = Counter(h["class"] for h in hits)
        report[d.name] = {"questions_with_answer": n_answers,
                          "answer_hits": {c: ans.get(c, 0) for c in CLASSES}, "answer_total": sum(ans.values()),
                          "answer_questions_flagged": len({h["id"] for h in hits if h["section"] == "answer"}),
                          "all_claim_hits": {c: every.get(c, 0) for c in CLASSES}, "hits": hits}
        print(d.name, json.dumps({k: v for k, v in report[d.name].items() if k != "hits"}))
    (dirs[-1].parent / "audit.json").write_text(json.dumps(report, indent=1))


def cmd_entail(dirs: list[Path]) -> None:
    """Score every model-written answer claim with the entailment check and
    write entail.json next to the arm directories (claims, scores, drops,
    seconds per question). Extractive answers are the cited text, so they are
    listed but not scored."""
    import time

    from riprap.core.burr import entailment as en

    qs = _questions()
    rebuilt = json.loads(DOCS_30.read_text()) if DOCS_30.exists() else {}
    backend, threshold = en.backend(), en.THRESHOLDS[en.backend()]
    report = {"backend": backend, "threshold": threshold}
    for d in dirs:
        rows, per_q = [], []
        for f in sorted(d.glob("*.json")):
            rec = json.loads(f.read_text())
            if "claims" not in rec or f.stem.endswith("_rep") or rec.get("answer_lead"):
                continue
            docs = record_docs(rec, rebuilt)
            t0, n = time.perf_counter(), 0
            for c in rec["claims"]:
                if c.get("section") != "answer":
                    continue
                ev = "\n".join(docs.get(i, "") for i in c.get("doc_ids") or [])
                p = en.p_supported(c["text"], ev, backend)
                n += 1
                rows.append({"id": rec["id"], "question": qs[rec["id"]]["question"], "text": c["text"],
                             "doc_ids": c.get("doc_ids"), "p_supported": round(p, 4), "dropped": p < threshold})
            if n:
                per_q.append(time.perf_counter() - t0)
        report[d.name] = {"claims": len(rows), "dropped": sum(r["dropped"] for r in rows),
                          "median_seconds_per_question": round(sorted(per_q)[len(per_q) // 2], 3) if per_q else None,
                          "rows": rows}
        print(d.name, {k: v for k, v in report[d.name].items() if k != "rows"}, flush=True)
    (dirs[-1].parent / "entail.json").write_text(json.dumps(report, indent=1))


def cmd_rebuild_docs(out: Path, arm: Path) -> None:
    """One no-LLM run per place, using the target each question resolved
    to in `arm` (the regex planner cannot pull a place out of a question);
    saves doc texts per question id."""
    from riprap.core.burr.app import district_summary, run
    sys.path.insert(0, str(ROOT / "scripts"))
    import question_eval

    by_place: dict[str, dict[str, str]] = {}
    docs = {}
    for qid in _questions():
        targets = (json.loads((arm / f"{qid}.json").read_text()).get("plan") or {}).get("targets") or [{}]
        place = targets[0].get("text") or ""
        if place not in by_place:
            district = re.fullmatch(r"\s*(MN|BX|BK|QN|SI)\s*\d{2}\s*", place, re.I)
            out_ = district_summary(place, no_llm=True) if district else run(place, no_llm=True)
            by_place[place] = question_eval._doc_texts(out_)
        docs[qid] = by_place[place]
        print(qid, place, len(docs[qid]), flush=True)
    out.write_text(json.dumps(docs, indent=1))


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "audit":
        cmd_audit([Path(a) for a in args])
    elif cmd == "entail":
        cmd_entail([Path(a) for a in args])
    elif cmd == "rebuild-docs":
        cmd_rebuild_docs(Path(args[0]), Path(args[1]))
    else:
        raise SystemExit(__doc__)
