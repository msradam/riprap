"""Mellea-validated reconciliation for Riprap.

`reconcile_strict_streaming` is the one reconciler on the "strict" path
(single_address, neighborhood, development_check all call it): a
hand-rolled rejection sampler — typed requirements + reroll-until-pass,
in the spirit of IBM Research's Mellea framework — that streams each
attempt's tokens to the user instead of validating silently behind a
"validating" skeleton. Replaces post-hoc sentence-dropping with "don't
accept output until requirements pass."

The five invariants checked each attempt (four ported from the parent
project's mellea_probe, one added here):

  1. non_empty                 — the attempt produced at least ~50 chars
  2. no_invented_numbers       — every number in output appears in source
  3. no_placeholder_tokens     — output never contains "[source]" or
                                 raw <document> markup
  4. every_claim_cited         — each numeric token has a [doc_id] within
                                 ~40 chars
  5. referenced_doc_ids_exist  — cited doc_ids ⊆ input doc_ids
"""
from __future__ import annotations

import logging
import os
import queue
import re
import threading
import time
from typing import Any

from app import llm

log = logging.getLogger("riprap.mellea")

# Default reconciler model — same env-var contract as app/reconcile.py.
DEFAULT_MODEL = os.environ.get(
    "RIPRAP_RECONCILER_MODEL",
    os.environ.get("RIPRAP_OLLAMA_MODEL", "granite4.1:8b"),
)

# Loop budget — try up to N samples before falling back to the last
# candidate even if it didn't pass all requirements. Low ceiling so a
# pathological case can't run away with latency.
#
# Override at process start with RIPRAP_MELLEA_MAX_ATTEMPTS. We default
# to 2 on the local Ollama path (where each attempt is 30-90 s on the
# Mac) and 3 on remote/vLLM (where attempts are seconds). This caps
# worst-case demo latency without giving up the principal grounding
# guarantee — the first-attempt pass rate on the curated probes is >85%.
def _default_loop_budget() -> int:
    try:
        n = int(os.environ.get("RIPRAP_MELLEA_MAX_ATTEMPTS", "0"))
        if n > 0:
            return n
    except ValueError:
        pass
    return 2 if os.environ.get("RIPRAP_LLM_PRIMARY", "ollama").lower() == "ollama" else 3


DEFAULT_LOOP_BUDGET = _default_loop_budget()

# Number tokens — \b enforces a word boundary so identifier codes like
# QN1206, B12 (community board), or M14 (bus route) are skipped entirely.
# Inside QN1206 there's no \b between any chars, so no submatch leaks.
_NUM_RE = re.compile(r"\b-?\d[\d,]*(?:\.\d+)?\b")
_CITE_RE = re.compile(r"\[(?P<id>[a-z][a-z0-9_]*)\]")
_PAREN_CITE_RE = re.compile(r"\((?P<id>[a-z][a-z0-9_]*)\)")

# A street number ("20 Coffey St") is an address identifier, not a fresh
# statistical claim — it's already carrying whatever citation it needs
# wherever the full address first appears (e.g. a "Flagged projects"
# bullet). A later summary sentence that just re-lists the same street
# numbers for readability ("concentrated on 20 Coffey St, 100 Sullivan
# St...") shouldn't have to re-cite each one — real production case from
# development_check output. Matches "<number> <Capitalized word(s)>
# <street suffix>" immediately after the digits.
_STREET_SUFFIXES = (
    "St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Pl|Place|Dr|Drive|"
    "Ln|Lane|Ct|Court|Way|Sq|Square|Ter|Terrace|Pkwy|Parkway|Cir|Circle|"
    "Hwy|Highway|Plaza|Broadway"
)
_STREET_ADDRESS_TAIL_RE = re.compile(
    # No leading ^ — this is matched via .match(text, pos) at a specific
    # offset, and ^ only anchors to true position 0 of the string, not
    # to `pos`. Without dropping it, this silently never matches at any
    # nonzero offset (i.e. almost always).
    r"\s+[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,2}\s+(?:" + _STREET_SUFFIXES + r")\b"
)


def _is_street_address_number(text: str, end_pos: int) -> bool:
    """True if the number ending at `end_pos` is immediately followed by
    a street-address tail ("... St", "... Avenue", ...)."""
    return bool(_STREET_ADDRESS_TAIL_RE.match(text, end_pos))


def _fix_parenthetical_citations(text: str, valid_ids: set[str]) -> str:
    """Granite occasionally cites with (doc_id) instead of [doc_id] —
    same intent, wrong bracket, and _CITE_RE only recognizes square
    brackets, so it reads as an uncited claim. Rewrite only when the
    parenthetical content is an exact match against a real doc_id for
    *this* query; an ordinary aside that happens to be a single
    lowercase word (e.g. "(approximately)") never matches a real id,
    so this can't misfire into treating prose as a citation."""
    def _sub(m: re.Match) -> str:
        tok = m.group("id")
        return f"[{tok}]" if tok in valid_ids else m.group(0)
    return _PAREN_CITE_RE.sub(_sub, text)
# Same trivial-numbers list as the post-hoc verifier — well-known service
# line numbers, single digits.
_TRIVIAL_NUMS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "100",
                 "311", "911", "211"}


def _strip_markdown_for_check(text: str) -> str:
    """Drop bold markers + citation tags so the numeric scan is clean."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\[[a-z0-9_]+\]", "", text, flags=re.I)
    return text


def _normalize_num(s: str) -> set[str]:
    forms = {s}
    no_comma = s.replace(",", "")
    forms.add(no_comma)
    if "." in no_comma:
        forms.add(no_comma.rstrip("0").rstrip("."))
    return {f for f in forms if f}


def _haystack(doc_msgs: list[dict]) -> str:
    return "\n".join(m.get("content", "") for m in doc_msgs)


def _doc_ids(doc_msgs: list[dict]) -> set[str]:
    """Each doc message has role like "document <id>"; extract ids."""
    out = set()
    for m in doc_msgs:
        role = m.get("role", "")
        if role.startswith("document "):
            out.add(role.split(" ", 1)[1].strip())
    return out


# --- the four invariants ---------------------------------------------------


def _check_no_invented_numbers(doc_msgs: list[dict]):
    haystack = _haystack(doc_msgs)
    def _fn(text: str):
        clean = _strip_markdown_for_check(text)
        invented = []
        for n in _NUM_RE.findall(clean):
            if n in _TRIVIAL_NUMS:
                continue
            forms = _normalize_num(n)
            if not any(f in haystack for f in forms):
                invented.append(n)
        return not invented  # pass = no invented numbers
    return _fn


def _check_no_placeholder_tokens():
    def _fn(text: str):
        bad = []
        if "[source]" in text.lower():
            bad.append("[source]")
        if "<document" in text:
            bad.append("<document>")
        if "</document" in text:
            bad.append("</document>")
        if "[doc_id]" in text:
            # Model echoed the EXTRA_SYSTEM_PROMPT skeleton literally
            bad.append("[doc_id]")
        return not bad
    return _fn


# Sentence end = `. ` or `.\n` or end-of-string. Question/exclamation
# marks rarely appear in these briefings; period is enough.
_SENT_END = re.compile(r"\.[\s)]|\.$")


def _citation_span(text: str, pos: int) -> tuple[int, int]:
    """The span of text a citation near `pos` could plausibly cover.

    Base case: the sentence containing `pos` (bounded by the previous
    and next `_SENT_END` match) — the citation can be anywhere in the
    sentence, not just adjacent to the number.

    Bulleted list items are the one place that's too narrow: a bullet
    like "- 20 Coffey St (BBL ...). new building, issued 11/26/2025.
    [dob_permits]" packs several period-delimited clauses under one
    citation at the end, same as how a human writes a footnoted list
    (one citation per item, not one per clause) — real production case
    from development_check output. When `pos` falls on a line starting
    with "- " or "* ", extend the span to the whole line so a citation
    anywhere on it counts for every clause in it.
    """
    start = 0
    for m in _SENT_END.finditer(text, 0, pos):
        start = m.end()
    m = _SENT_END.search(text, pos)
    end = m.start() + 1 if m else len(text)

    line_start = text.rfind("\n", 0, pos) + 1
    line_end_nl = text.find("\n", pos)
    line_end = line_end_nl if line_end_nl != -1 else len(text)
    if text[line_start:line_end].lstrip().startswith(("- ", "* ")):
        start, end = min(start, line_start), max(end, line_end)
    return start, end


def _check_every_claim_cited():
    """Each non-trivial numeric token must have a [doc_id] somewhere in
    its citation span (see _citation_span)."""
    def _fn(text: str):
        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        for m in _NUM_RE.finditer(clean):
            n = m.group(0)
            if n in _TRIVIAL_NUMS or _is_street_address_number(clean, m.end()):
                continue
            s, e = _citation_span(clean, m.start())
            if not _CITE_RE.search(clean[s:e]):
                return False
        return True
    return _fn


def _failing_sentences_for_citations(text: str) -> list[str]:
    """Return the citation spans (see _citation_span) that contain a
    non-trivial number but no [doc_id] citation. Used to give the model
    targeted reroll feedback so it can fix the exact spots that failed."""
    clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    bad: list[str] = []
    seen_spans: set[tuple[int, int]] = set()
    for m in _NUM_RE.finditer(clean):
        n = m.group(0)
        if n in _TRIVIAL_NUMS or _is_street_address_number(clean, m.end()):
            continue
        span = _citation_span(clean, m.start())
        if span in seen_spans:
            continue
        s, e = span
        if not _CITE_RE.search(clean[s:e]):
            seen_spans.add(span)
            bad.append(clean[s:e].strip())
    return bad


def _check_referenced_doc_ids_exist(doc_msgs: list[dict]):
    valid = _doc_ids(doc_msgs)
    def _fn(text: str):
        cited = {m.group("id") for m in _CITE_RE.finditer(text)}
        rogue = cited - valid
        return not rogue
    return _fn


# --- main entry point ------------------------------------------------------


def reconcile_strict_streaming(
    doc_msgs: list[dict],
    system_prompt: str,
    user_prompt: str = "Write the cited briefing now.",
    model: str | None = None,
    loop_budget: int = DEFAULT_LOOP_BUDGET,
    ollama_options: dict | None = None,
    on_token=None,
    on_attempt_end=None,
) -> dict[str, Any]:
    """Hand-rolled rejection sampler that *streams* each attempt's tokens
    to the user as they arrive from Granite, instead of validating
    silently behind a "validating" skeleton. Checks the five invariants
    in this module's docstring each attempt, accepts the first attempt
    that passes all of them, falls back to the last attempt if the
    budget is exhausted.

    Callbacks (both optional, both fire on the calling thread):
      on_token(delta: str, attempt_idx: int)
        — fires for every token chunk as it arrives from Granite.
      on_attempt_end(attempt_idx: int, passed: list[str], failed: list[str])
        — fires after each attempt with its per-requirement outcome.
        The frontend uses this to render reroll banners + reset the
        briefing buffer when a new attempt begins.
    """
    model = model or DEFAULT_MODEL
    t0 = time.time()

    checks = [
        ("non_empty",
         lambda p: bool(p and len(p.strip()) > 50)),
        ("numerics_grounded",
         _check_no_invented_numbers(doc_msgs)),
        ("no_placeholder_tokens",
         _check_no_placeholder_tokens()),
        ("citations_dense",
         _check_every_claim_cited()),
        ("citations_resolve",
         _check_referenced_doc_ids_exist(doc_msgs)),
    ]

    base_messages = doc_msgs + [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    # num_predict 600 — this function writes a 4-section briefing under
    # the requirements above. A denser deployment (NYC: 25 pebbles + RAG over the
    # policy corpus) can genuinely need most of that; 350 (this path's
    # old default, tuned for a much smaller vLLM max_model_len that no
    # longer reflects the primary Ollama/Mac-Mini deployment) truncated
    # NYC briefings mid-sentence before the fixed scope footer, verified
    # against a real query. Override with RIPRAP_MELLEA_NUM_PREDICT if
    # a specific remote deployment needs a tighter ceiling again.
    # num_ctx (Ollama only) is forwarded via extra_body; vLLM ignores it.
    base_opts = {"temperature": 0,
                 "num_ctx": int(os.environ.get("RIPRAP_MELLEA_NUM_CTX", "4096")),
                 "num_predict": int(os.environ.get("RIPRAP_MELLEA_NUM_PREDICT", "600")),
                 **(ollama_options or {})}

    paragraph = ""
    last_passed: list[str] = []
    last_failed: list[str] = [name for name, _ in checks]
    last_paragraph = ""
    best_paragraph = ""  # best non-empty paragraph seen across all attempts
    attempts = 0
    _streaming_hung = False  # set on first per-token timeout; skip retries

    # Two-phase timeout: the FIRST token from a cold remote deployment
    # (e.g. a Modal container waking from scale-to-zero) can take 3-4 min
    # (container boot + model load into GPU VRAM). Once streaming has
    # started, each subsequent token should arrive in < 5 s; we use a
    # tight 45 s inter-token timeout to catch mid-stream stalls quickly.
    _first_token_timeout = int(os.environ.get("RIPRAP_FIRST_TOKEN_TIMEOUT_S", "400"))
    _inter_token_timeout = int(os.environ.get("RIPRAP_TOKEN_TIMEOUT_S", "45"))

    # When PRIMARY=vllm, a scale-to-zero remote deployment (e.g. Modal)
    # can take ~250-360s to cold-start (container boot + model load). The
    # container starts when the warmup request hits the proxy, but the
    # proxy returns 503 immediately. LiteLLM would fall back to Ollama
    # and fail before the remote is ready. Poll /v1/models here (after
    # specialists, but before generation) and wait — keepalives keep the
    # SSE connection alive.
    _vllm_base = os.environ.get("RIPRAP_LLM_BASE_URL", "").rstrip("/")
    if os.environ.get("RIPRAP_LLM_PRIMARY", "ollama") == "vllm" and _vllm_base:
        try:
            import httpx as _httpx
            _probe_url = f"{_vllm_base}/models"
            _probe_key = os.environ.get("RIPRAP_LLM_API_KEY", "") or "EMPTY"
            _probe_headers = {"Authorization": f"Bearer {_probe_key}"}
            _probe_deadline = t0 + _first_token_timeout
            log.info("mellea: polling vLLM readiness at %s", _probe_url)
            while time.time() < _probe_deadline:
                try:
                    _r = _httpx.get(_probe_url, headers=_probe_headers, timeout=5.0)
                    # Any non-503/502/504 means the service is UP (200 = ready,
                    # 401 = auth-gated but alive, 404 = wrong path but alive).
                    if _r.status_code not in (502, 503, 504):
                        log.info("mellea: vLLM ready (status=%d, %.1fs elapsed)",
                                 _r.status_code, time.time() - t0)
                        break
                except Exception as _pe:
                    log.debug("mellea: vLLM probe: %r", _pe)
                time.sleep(10)
            else:
                log.warning("mellea: vLLM not ready after %.1fs, proceeding anyway",
                            time.time() - t0)
        except ImportError:
            log.warning("mellea: httpx not available, skipping vLLM probe")

    for attempt_idx in range(loop_budget):
        attempts = attempt_idx + 1
        # On reroll, append a tight feedback message naming what failed AND
        # the specific failing sentences (so the model knows exactly which
        # ones to fix). Granite responds well to surgical corrections.
        messages = list(base_messages)
        if attempt_idx > 0 and last_failed:
            feedback = [
                f"Your previous draft failed: {', '.join(last_failed)}.",
            ]
            if "citations_dense" in last_failed and last_paragraph:
                bad = _failing_sentences_for_citations(last_paragraph)
                if bad:
                    feedback.append(
                        "Specific sentences with uncited numbers:"
                    )
                    for s in bad[:3]:
                        feedback.append(f"  - {s.strip()}")
                    feedback.append(
                        "Add a [doc_id] citation at the end of each. "
                        "Re-emit the FULL briefing."
                    )
            else:
                feedback.append(
                    "Re-write so every sentence containing a number ends "
                    "with a [doc_id] citation."
                )
            messages.append({"role": "user", "content": "\n".join(feedback)})

        chunks: list[str] = []

        # Each attempt gets its own sentinel so that a stale daemon thread
        # from a previous timed-out attempt cannot corrupt this attempt's
        # queue (the closure captures variables by reference; re-binding
        # them per-attempt keeps each daemon's sentinel unique).
        _stream_q: queue.Queue = queue.Queue()
        _done_sentinel = object()

        def _stream_worker(q=_stream_q, done=_done_sentinel,
                           msgs=messages, opts=base_opts):
            try:
                for _chunk in llm.chat(model=model, messages=msgs,
                                       stream=True, options=opts):
                    q.put(_chunk)
            except Exception as _e:
                q.put(_e)
            finally:
                q.put(done)

        _st = threading.Thread(target=_stream_worker, daemon=True)
        _st.start()
        _timed_out = False
        _got_first_token = False
        while True:
            _timeout = _inter_token_timeout if _got_first_token else _first_token_timeout
            try:
                chunk = _stream_q.get(timeout=_timeout)
            except queue.Empty:
                log.warning("mellea: timeout (%ds, first=%s) — breaking stream",
                            _timeout, not _got_first_token)
                _timed_out = True
                _streaming_hung = True
                break
            if chunk is _done_sentinel:
                break
            if isinstance(chunk, Exception):
                log.warning("mellea: stream error: %r", chunk)
                if not _got_first_token:
                    # LiteLLM/httpx timeout before first token — treat as
                    # streaming hung so we don't start a concurrent retry.
                    _timed_out = True
                    _streaming_hung = True
                break
            delta = (chunk.get("message") or {}).get("content") or ""
            if delta:
                _got_first_token = True
                chunks.append(delta)
                if on_token is not None:
                    try:
                        on_token(delta, attempt_idx)
                    except Exception:
                        log.exception("on_token callback raised")
        paragraph = "".join(chunks).strip()
        from app.reconcile import _strip_code_fences  # noqa: PLC0415
        paragraph = _strip_code_fences(paragraph)
        paragraph = _fix_parenthetical_citations(paragraph, _doc_ids(doc_msgs))
        if paragraph:
            best_paragraph = paragraph

        passed: list[str] = []
        failed: list[str] = []
        for name, fn in checks:
            try:
                (passed if fn(paragraph) else failed).append(name)
            except Exception as e:
                log.warning("requirement %s raised: %r", name, e)
                failed.append(name)

        last_passed = passed
        last_failed = failed
        last_paragraph = paragraph
        if on_attempt_end is not None:
            try:
                on_attempt_end(attempt_idx, passed, failed)
            except Exception:
                log.exception("on_attempt_end callback raised")

        if not failed:
            break

        # If this attempt's stream hung, stop retrying with streaming.
        # A stale daemon thread is still consuming vLLM resources; starting
        # another streaming request would create a second concurrent request
        # and can crash vLLM (observed as HTTP/2 stream error on the SSE
        # connection). Signal the caller to use a non-streaming fallback.
        if _timed_out:
            log.warning("mellea: streaming hung — aborting retry loop "
                        "to avoid concurrent vLLM requests")
            break

    return {
        "paragraph": paragraph or best_paragraph,
        "rerolls": max(0, attempts - 1),
        "n_attempts": attempts,
        "requirements_total": len(checks),
        "requirements_passed": last_passed,
        "requirements_failed": last_failed,
        "elapsed_s": round(time.time() - t0, 2),
        "model": model,
        "loop_budget": loop_budget,
    }


def _extract_text(result) -> str:
    """SamplingResult / ModelOutputThunk text extraction."""
    for attr in ("sample", "result", "value", "content"):
        v = getattr(result, attr, None)
        if v is not None:
            if hasattr(v, "value"):
                return str(v.value)
            return str(v)
    return str(result)


def _extract_attempts(result) -> int:
    """How many samples were drawn before stopping."""
    for attr in ("n_attempts", "num_attempts", "attempts"):
        v = getattr(result, attr, None)
        if isinstance(v, int):
            return v
    samples = getattr(result, "sample_validations", None) or getattr(result, "samples", None)
    if isinstance(samples, list):
        return len(samples)
    return 1


def _extract_pass_fail(result) -> tuple[list[str], list[str]]:
    """Best-effort extraction of which requirements passed on the
    accepted sample. mellea v0.4 exposes sample_validations as a list
    where each entry is itself a list of (Requirement, ValidationResult)
    tuples — duck-type defensively.
    """
    validations = getattr(result, "sample_validations", None)
    if not validations:
        return [], []
    last = validations[-1] if isinstance(validations, list) else validations
    passed: list[str] = []
    failed: list[str] = []
    items = last if isinstance(last, list) else [last]
    for item in items:
        # Item might be (Requirement, ValidationResult) tuple, or a single
        # ValidationResult, or a Requirement, depending on mellea version.
        ok = None
        descr = ""
        if isinstance(item, tuple) and len(item) >= 2:
            descr = str(item[0])[:80]
            v = item[1]
            ok = bool(getattr(v, "passed", getattr(v, "is_valid",
                          getattr(v, "result", False))))
        else:
            descr = str(getattr(item, "requirement", item))[:80]
            ok = bool(getattr(item, "passed", getattr(item, "is_valid",
                          getattr(item, "result", False))))
        if ok:
            passed.append(descr)
        else:
            failed.append(descr)
    return passed, failed
