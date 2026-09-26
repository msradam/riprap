"""Question-set evaluation for the v1 / v2 A/B (refactor 2).

    run    run every question through the pipeline in this checkout and save
           one JSON per question:  question_eval.py run tests/question_eval/v2
    score  compare arms against tests/question_eval/questions.yaml:
           question_eval.py score tests/question_eval/v1 tests/question_eval/v2

The same script runs both arms; it only reads `run()` output, so it works on
the v1 code (refactor/mvp) and the v2 code (refactor/mvp-2). LLM settings come
from RIPRAP_LLM_BASE_URL / RIPRAP_LLM_MODEL.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = Path(__file__).resolve().parent.parent / "tests" / "question_eval" / "questions.yaml"


def _load_questions(path: Path = QUESTIONS) -> list[dict]:
    import yaml

    return yaml.safe_load(path.read_text())


def _pebbles_run(out: dict) -> list[str]:
    """Data pebbles the run attempted (ok or not), not those it skipped."""
    from riprap.core.pebbles.bridge import get_registry

    ids = set(get_registry(out.get("deployment") or "nyc").ids())
    return sorted({r["step"] for r in out.get("trace") or []
                   if r.get("step") in ids and not (r.get("result") or {}).get("skipped")})


def _tokens(calls: list[dict]) -> dict:
    return {"prompt": sum(c.get("prompt_tokens") or 0 for c in calls),
            "completion": sum(c.get("completion_tokens") or 0 for c in calls),
            "seconds": round(sum(c.get("duration_s") or 0 for c in calls), 2), "n_calls": len(calls)}


def _n_documents(out: dict) -> int | None:
    try:
        from riprap.core.burr.synthesis import _documents

        return len(_documents(out)[0])
    except Exception:  # noqa: BLE001 - the count is informational
        return None


def cmd_run(outdir: Path, only: list[str] | None = None, suffix: str = "") -> None:
    from riprap.core import llm
    from riprap.core.burr.app import run

    outdir.mkdir(parents=True, exist_ok=True)
    meta = {"llm": llm.describe(), "started": datetime.now(UTC).isoformat(timespec="seconds"),
            "git": os.popen(f"git -C {ROOT} rev-parse --short HEAD").read().strip()}
    (outdir / "meta.json").write_text(json.dumps(meta, indent=1))
    for q in _load_questions():
        if only and q["id"] not in only:
            continue
        t0 = time.time()
        try:
            out, err = run(q["question"]), None
        except Exception as e:  # noqa: BLE001 - record and continue
            out, err = {}, f"{type(e).__name__}: {e}"
        wall = round(time.time() - t0, 1)
        g = out.get("grounding") or {}
        plan = out.get("plan") or {}
        rec = {
            "id": q["id"], "kind": q["kind"], "question": q["question"], "error": err,
            "wall_s": wall, "intent": out.get("intent"), "deployment": out.get("deployment"),
            "plan": {k: v for k, v in plan.items() if k != "llm_calls"},
            "pebbles_run": _pebbles_run(out) if out else [],
            "consulted": out.get("consulted"), "not_checked": out.get("not_checked"),
            "planner_tokens": _tokens(plan.get("llm_calls") or []),
            "synthesis_tokens": _tokens(g.get("llm_calls") or []),
            "n_documents": _n_documents(out) if out else None,
            "tier": g.get("tier"), "model": g.get("model"), "attempts": g.get("attempts"),
            "claims": g.get("claims") or [], "dropped_claims": g.get("dropped_claims") or [],
            "retried_claims": g.get("retried_claims") or [],
            "paragraph": out.get("paragraph"),
        }
        (outdir / f"{q['id']}{suffix}.json").write_text(json.dumps(rec, indent=1, default=str))
        print(f"{q['id']}{suffix} {q['kind']:13s} {str(rec['intent']):16s} pebbles={len(rec['pebbles_run']):2d} "
              f"kept={len(rec['claims'])} dropped={len(rec['dropped_claims'])} {wall}s", flush=True)


def _mention_hits(item: list[str], text: str) -> bool:
    t = text.lower()
    for alt in item:
        a = alt.lower()
        if re.fullmatch(r"[\d.]+", a):
            if re.search(rf"(?<![\d.]){re.escape(a)}(?![\d])", t):
                return True
        elif a in t:
            return True
    return False


def _answer_text(rec: dict) -> str:
    return " ".join(c["text"] for c in rec.get("claims") or [] if c.get("section") == "answer")


def score_arm(outdir: Path, questions: list[dict]) -> tuple[dict, list[dict]]:
    rows = []
    for q in questions:
        f = outdir / f"{q['id']}.json"
        if not f.exists():
            continue
        rec = json.loads(f.read_text())
        ran = set(rec["pebbles_run"])
        in_scope = q["kind"] not in ("out_of_scope", "not_covered")
        body = rec.get("paragraph") or ""
        answer = _answer_text(rec)
        mentions = [(_mention_hits(item, answer + " " + body), item) for item in q["answer_should_mention"]]
        refused = rec.get("intent") in ("out_of_scope", "not_implemented")
        rows.append({
            "id": q["id"], "kind": q["kind"],
            "must_run": len(q["must_run"]), "must_run_hit": len(set(q["must_run"]) & ran),
            "misses": sorted(set(q["must_run"]) - ran),
            "waste": len(set(q["irrelevant"]) & ran), "n_run": len(ran),
            "answer_present": bool(answer) if in_scope else None,
            "mention_hit": sum(h for h, _ in mentions), "mention_total": len(mentions),
            "mention_misses": [i for h, i in mentions if not h],
            "refusal_ok": refused if not in_scope else None,
            "kept": len(rec["claims"]), "dropped": len(rec["dropped_claims"]),
            "drop_reasons": [d["reason"].split(":")[0] for d in rec["dropped_claims"]],
            "wall_s": rec["wall_s"], "planner_tokens": rec["planner_tokens"]["prompt"] + rec["planner_tokens"]["completion"],
            "synthesis_tokens": rec["synthesis_tokens"]["prompt"] + rec["synthesis_tokens"]["completion"],
            "n_documents": rec.get("n_documents"),
            "pebble_set": sorted(ran), "intent": rec.get("intent"),
        })
    return _summarize(rows), rows


def _summarize(rows: list[dict]) -> dict:
    def agg(rs):
        mr = sum(r["must_run"] for r in rs)
        ans = [r["answer_present"] for r in rs if r["answer_present"] is not None]
        ref = [r["refusal_ok"] for r in rs if r["refusal_ok"] is not None]
        mt = sum(r["mention_total"] for r in rs)
        return {
            "n": len(rs),
            "must_run_recall": round(sum(r["must_run_hit"] for r in rs) / mr, 3) if mr else None,
            "waste": sum(r["waste"] for r in rs),
            "pebbles_per_q": round(statistics.mean(r["n_run"] for r in rs), 1) if rs else None,
            "answer_present": round(sum(ans) / len(ans), 3) if ans else None,
            "mention_rate": round(sum(r["mention_hit"] for r in rs) / mt, 3) if mt else None,
            "refusals_ok": f"{sum(ref)}/{len(ref)}" if ref else None,
            "kept": sum(r["kept"] for r in rs), "dropped": sum(r["dropped"] for r in rs),
            "median_wall_s": round(statistics.median(r["wall_s"] for r in rs), 1) if rs else None,
            "median_planner_tokens": statistics.median(r["planner_tokens"] for r in rs) if rs else None,
            "median_synthesis_tokens": statistics.median(r["synthesis_tokens"] for r in rs) if rs else None,
            "median_documents": statistics.median(r["n_documents"] for r in rs if r["n_documents"] is not None)
            if any(r["n_documents"] is not None for r in rs) else None,
        }
    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r["kind"]].append(r)
    return {"all": agg(rows), **{k: agg(v) for k, v in by_kind.items()},
            "drop_reasons": dict(Counter(x for r in rows for x in r["drop_reasons"]))}


def stability(outdir: Path) -> dict:
    """Pebble-set changes between a question's run and its `_rep` rerun."""
    changed, n, walls = [], 0, []
    for rep in sorted(outdir.glob("*_rep.json")):
        a = json.loads((outdir / rep.name.replace("_rep", "")).read_text())
        b = json.loads(rep.read_text())
        n += 1
        walls.append((a["wall_s"], b["wall_s"]))
        if set(a["pebbles_run"]) != set(b["pebbles_run"]) or a["intent"] != b["intent"]:
            changed.append({"id": a["id"], "first": a["pebbles_run"], "second": b["pebbles_run"],
                            "intents": [a["intent"], b["intent"]]})
    return {"n_pairs": n, "n_changed": len(changed), "changed": changed,
            "median_wall_s_pairs": [statistics.median(w) for w in walls]}


def cmd_score(dirs: list[Path]) -> None:
    questions = _load_questions()
    report = {}
    for d in dirs:
        summary, rows = score_arm(d, questions)
        report[d.name] = {"summary": summary, "stability": stability(d), "rows": rows}
    print(json.dumps({k: {"summary": v["summary"], "stability": {x: y for x, y in v["stability"].items() if x != "changed"}}
                      for k, v in report.items()}, indent=1))
    (dirs[-1].parent / "scores.json").write_text(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    cmd, *args = sys.argv[1:]
    if cmd == "run":
        only = os.environ.get("QE_ONLY", "").split(",") if os.environ.get("QE_ONLY") else None
        cmd_run(Path(args[0]), only, os.environ.get("QE_SUFFIX", ""))
    elif cmd == "score":
        cmd_score([Path(a) for a in args])
    else:
        raise SystemExit(__doc__)
