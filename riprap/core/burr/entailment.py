"""Entailment check on answer claims: does the cited evidence support what
the claim says?

Word patterns (answer_checks.py) cannot see a claim that answers another
question, attributes a fact to the wrong thing, or paraphrases an
inference. This check asks a natural-language-inference model instead,
with the cited evidence as the premise and the claim as the hypothesis.

  RIPRAP_ENTAILMENT=gliclass   default; knowledgator/gliclass-large-v3.0 on CPU
  RIPRAP_ENTAILMENT=guardian   ibm-granite/granite-guardian-4.1-8b on the GPU
  RIPRAP_ENTAILMENT=off        skip

Both adapters are copied from the round-two code of an unpublished
experiment (System One), experiments/23_system_one/run.py:
GLiClass in its documented NLI form, Guardian reading P(no risk) one step
after a prefilled <score>. Models are pinned by SHA and loaded from
safetensors only. The models need the `ml` extra; without it, or without
the weights, the check is skipped and the briefing says so.
"""

from __future__ import annotations

import os
import re
import time
from functools import lru_cache

GLICLASS = ("knowledgator/gliclass-large-v3.0", "e065d1844f913a9aa611cf33623a9538b8aa8841")
GUARDIAN = ("ibm-granite/granite-guardian-4.1-8b", "ab01ccca5dcfb80246369a086a4a87a29198f5af")
ALLOW = ["*.safetensors", "*.json", "*.jinja", "*.txt", "*.model"]
DENY = ["*.bin", "*.pt", "*.pth", "*.pkl", "*.ckpt", "*.py"]
MAX_TOKENS = 512
# P(supported) below this drops the claim. Chosen on the System One Task B
# calibration split (scripts/calibrate_entailment.py): the highest threshold
# that keeps at least 95% of that split's true claims.
# GLiClass: 0.787085 on 146 calibration items (tests/entailment_calibration_gliclass.json);
# on the 582 test items it keeps 86% of true claims and catches 85% of the rest.
# Guardian has no calibrated threshold yet, so selecting it skips the check.
THRESHOLDS = {"gliclass": 0.787085, "guardian": None}
DROP_REASON = "not supported by the cited evidence (entailment check)"
LABELS = {"gliclass": "entailment check (GLiClass large, CPU)",
          "guardian": "entailment check (Granite Guardian 8B)"}


def backend() -> str:
    b = os.environ.get("RIPRAP_ENTAILMENT", "gliclass").strip().lower()
    return b if b in ("gliclass", "guardian", "off") else "gliclass"


def _snapshot(repo_sha: tuple[str, str]) -> str:
    from huggingface_hub import snapshot_download

    repo, sha = repo_sha
    return snapshot_download(repo, revision=sha, allow_patterns=ALLOW, ignore_patterns=DENY)


@lru_cache(maxsize=1)
def _gliclass():
    import gliclass.pipeline
    import torch
    from gliclass import GLiClassModel, ZeroShotClassificationPipeline
    from transformers import AutoTokenizer

    gliclass.pipeline.tqdm = lambda it, *a, **k: it  # no progress bar per claim
    path = _snapshot(GLICLASS)
    model = GLiClassModel.from_pretrained(path)
    tok = AutoTokenizer.from_pretrained(path)
    # The pipeline treats any device other than cuda as CPU, which is what we want here.
    pipe = ZeroShotClassificationPipeline(model, tok, classification_type="multi-label",
                                          device=torch.device("cpu"))
    return pipe, tok


@lru_cache(maxsize=1)
def _guardian():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    path = _snapshot(GUARDIAN)
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16).to(device).eval()
    yes = sorted({tok.encode(t, add_special_tokens=False)[0] for t in ("yes", " yes")})
    no = sorted({tok.encode(t, add_special_tokens=False)[0] for t in ("no", " no")})
    return model, tok, device, yes, no


_GUARDIAN_CRITERIA = (
    "A text is considered ungrounded or unfaithful if it includes information lacking support from, "
    "or directly contradicting, the provided document(s). This risk arises when the text fabricates "
    "details, misinterprets the content, or makes unsupported extrapolations beyond what is explicitly "
    "stated in the document(s).")
_GUARDIAN_NOTHINK = (
    "<guardian><no-think>As a judge agent, assess whether the provided text meets the given judging "
    "criteria using all available information, including conversations, documents, and tools. Provide "
    "your score immediately without explanation. Output empty <think>\n</think> tags followed by your "
    "score in <score></score> tags.")
_GUARDIAN_SCHEMA = "If the last assistant's text meets the criteria, return 'yes'; otherwise, return 'no'."


def available() -> tuple[bool, str]:
    """(usable, reason when not)."""
    b = backend()
    if b == "off":
        return False, "entailment check off (RIPRAP_ENTAILMENT=off)"
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        if b == "gliclass":
            import gliclass  # noqa: F401
    except ImportError:
        return False, "entailment check skipped: install the ml extra"
    if THRESHOLDS.get(b) is None:
        return False, f"entailment check skipped: no calibrated threshold for {b}"
    return True, ""


def trim(evidence: str, claim: str, tok, max_tokens: int = MAX_TOKENS) -> str:
    """The evidence cut to the passage most relevant to the claim: whole
    sentences, ranked by words shared with the claim, kept in their original
    order, up to `max_tokens` (the claim's own tokens count against it)."""
    budget = max_tokens - len(tok.encode(claim, add_special_tokens=False)) - 16
    if len(tok.encode(evidence, add_special_tokens=False)) <= budget:
        return evidence
    sents = re.split(r"(?<=[.!?])\s+|\n+", evidence)
    words = set(re.findall(r"\w+", claim.lower()))
    ranked = sorted(range(len(sents)), key=lambda i: -len(words & set(re.findall(r"\w+", sents[i].lower()))))
    keep, used = set(), 0
    for i in ranked:
        n = len(tok.encode(sents[i], add_special_tokens=False))
        if used + n > budget:
            continue
        keep.add(i)
        used += n
    return " ".join(sents[i] for i in sorted(keep))


def p_supported(claim: str, evidence: str, b: str | None = None) -> float:
    b = b or backend()
    if b == "guardian":
        import torch

        model, tok, device, yes, no = _guardian()
        msgs = [{"role": "assistant", "content": claim},
                {"role": "user", "content": f"{_GUARDIAN_NOTHINK}\n\n### Criteria: {_GUARDIAN_CRITERIA}\n\n"
                                            f"### Scoring Schema: {_GUARDIAN_SCHEMA}"}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                       documents=[{"doc_id": "0", "text": trim(evidence, claim, tok)}])
        enc = tok(text + "<think>\n</think>\n<score>", return_tensors="pt", add_special_tokens=False).to(device)
        with torch.no_grad():
            p = torch.softmax(model(**enc).logits[0, -1].float(), -1)
        p_yes, p_no = float(p[yes].sum()), float(p[no].sum())
        return p_no / (p_yes + p_no)  # "yes" means the groundedness risk is present
    pipe, tok = _gliclass()
    return float(pipe(trim(evidence, claim, tok), [claim], threshold=0.0)[0][0]["score"])


def check(claims: list[dict], texts: dict[str, str]) -> tuple[list[dict], list[dict], dict]:
    """Split answer claims into (kept, dropped) by the entailment check.
    Other claims pass through. `info` records whether the check ran, the
    backend, per-claim scores and the time taken."""
    ok, why = available()
    if not ok:
        return claims, [], {"ran": False, "reason": why}
    b = backend()
    threshold = THRESHOLDS[b]
    kept, dropped, scores, t0 = [], [], [], time.perf_counter()
    for c in claims:
        if c.get("section") != "answer":
            kept.append(c)
            continue
        evidence = "\n".join(texts.get(i, "") for i in c.get("doc_ids") or [])
        p = p_supported(c["text"], evidence, b)
        scores.append({"text": c["text"], "p_supported": round(p, 4)})
        if p < threshold:
            dropped.append({**c, "reason": DROP_REASON, "p_supported": round(p, 4)})
        else:
            kept.append(c)
    return kept, dropped, {"ran": True, "backend": b, "threshold": threshold, "scores": scores,
                           "seconds": round(time.perf_counter() - t0, 3), "label": LABELS[b]}
