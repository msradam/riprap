"""Document-grounded reconciliation via Granite 4.1 (local Ollama).

Uses Granite 4.1's native grounded-generation interface: each specialist
that produced data becomes a separate message with role="document <doc_id>".
Ollama's chat template lifts those into the model's `<documents>` system
block and prepends IBM's official grounded-generation system prompt.

Specialists that didn't fire emit nothing — silence over confabulation.
The model is post-trained to refuse to ground on absent documents.

A server-side post-check verifies every numeric token in the output appears
verbatim in the source documents. Sentences with ungrounded numbers are
dropped from the rendered paragraph (still recorded in the trace as
unverified for audit). This is the cheapest reliable guardrail against
the worst hallucination class — fabricated stats — and it's deterministic.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from app import llm

log = logging.getLogger("riprap.reconcile")

# Reconciliation is the synthesis step — citation discipline + structured
# output adherence both improve materially with the 8b variant.
# RIPRAP_RECONCILER_MODEL is the canonical name; RIPRAP_OLLAMA_MODEL is
# kept as a back-compat fallback. Default is 8b for a self-hosted
# deployment with real inference (Modal, a Mac Mini, local Ollama); HF
# Spaces run data probes only post-hackathon, with inferencing disabled.
OLLAMA_MODEL = os.environ.get("RIPRAP_RECONCILER_MODEL",
                              os.environ.get("RIPRAP_OLLAMA_MODEL", "granite4.1:8b"))

def _manifests_by_doc_id() -> dict[str, object]:
    """doc_id -> pebble manifest, across every shipped deployment."""
    from riprap.core.pebbles import load_registry
    from riprap.core.pebbles.deployments import discover_deployments

    out: dict[str, object] = {}
    for dep in discover_deployments():
        try:
            reg = load_registry(dep.root)
        except Exception:  # noqa: BLE001 - one malformed deployment must not break the rest
            continue
        for p in reg.all():
            out.setdefault(p.manifest.provenance.doc_id or p.id, p.manifest)
    return out


def citations_from_docs(doc_msgs: list[dict]) -> list[dict]:
    """Citation records for the document messages, from manifest
    provenance only. rag_* passages resolve to the policy_corpus
    manifest; a doc_id no manifest owns gets a bare record."""
    from riprap.core.pebbles.vintage import citation

    index = _manifests_by_doc_id()
    seen: dict[str, dict] = {}
    for msg in doc_msgs:
        role = msg.get("role", "")
        if not role.startswith("document "):
            continue
        doc_id = role[len("document "):].strip()
        if doc_id in seen:
            continue
        manifest = index.get("policy_corpus" if doc_id.startswith("rag_") else doc_id)
        seen[doc_id] = citation(manifest, doc_id=doc_id) if manifest else {"doc_id": doc_id}
    return list(seen.values())


# The Ollama chat template auto-prepends Granite's own grounded-generation
# system suffix once the message list contains role="document" entries.
# This text is OUR additional system prompt, prepended to that suffix.
# Fixed strings, not model output. Earlier versions asked the model to
# reproduce these verbatim as the opening/closing lines of every briefing;
# a smaller reconciler model (verified: an 8B->3B swap for a low-memory
# deployment tier) sometimes just... didn't, silently failing
# informational_disclaimer_present / automation_disclosure_present even
# though the model's actual grounded content was fine. These are wrapped
# around the model's output by the caller (wrap_with_scope) instead —
# zero-risk regardless of model size, since they're never generated.
SCOPE_HEADER = (
    "This is an automated flood-exposure briefing produced by Riprap from "
    "live and baked data sources. It is informational only and not a "
    "substitute for a professional flood assessment, an elevation "
    "certificate, or an insurance determination."
)
NON_SCOPE_FOOTER = (
    "**Out of scope.** This briefing does not assess title, structural "
    "condition, indoor air quality, wind/hail risk, or compliance with "
    "specific zoning rules. Where a probe was offline at run time, the "
    "relevant section omits that signal."
)


def wrap_with_scope(content: str) -> str:
    """Assemble the final briefing: fixed scope header, the model's
    grounded content, fixed out-of-scope footer. See SCOPE_HEADER's
    comment for why this isn't left to the model."""
    content = content.strip()
    if not content:
        return content
    return f"{SCOPE_HEADER}\n\n{content}\n\n{NON_SCOPE_FOOTER}"


def wrap_mellea_paragraph(paragraph: str) -> str:
    """wrap_with_scope for a Mellea rejection-sampling result. A short/empty
    paragraph means the streaming attempt stalled or failed upstream — leave
    it alone rather than wrap near-nothing in a header/footer."""
    if paragraph and len(paragraph.strip()) >= 50:
        return wrap_with_scope(paragraph)
    return paragraph


EXTRA_SYSTEM_PROMPT = """Write the body of a flood-exposure briefing for an NYC address. Use ONLY the facts in the provided documents.

Output ONLY the four sections below, filling each <...> with content drawn only from the documents. Do NOT write any opening scope sentence or closing "out of scope" line; the caller adds those. **Every sentence that contains a number MUST include a citation tag using the actual document id it came from. Cite ONLY doc_ids that appear in THIS query's documents list.** Bold at most one phrase per section using `**...**`. Omit any section whose supporting facts are absent from the documents — do NOT fill an empty section with generic, uncited sentences like "reinforcing the need for flood mitigation measures", and do NOT speculate about what a scenario or model "would likely show" when no such document is present; state plainly that no modeled-scenario data is available for this section and stop there.

If a sentence states numbers drawn from two different documents, cite each number to its own doc_id separately, right after that number (e.g. a total-requests count from one document and a flood-specific subset count from a different document each get their own citation tag) — never attribute a number to a doc_id it did not come from, and never let one citation tag stand in for two different documents' numbers.

**Status.**
<one sentence: dominant exposure signal(s) for this address, citing the strongest document ids>.

**Empirical evidence.**
<1-3 sentences citing observed flood evidence (Sandy extent, 311 complaints, FloodNet sensors, Ida high-water marks), each citing its own document id>.

**Modeled scenarios.**
<1-2 sentences citing modeled flooding (DEP stormwater scenarios) and terrain (HAND, TWI, percentile)>.

**Policy context.**
<1 sentence per RAG document hit, citing the agency name and the rag_* doc_id exactly as given>.

Constraints:
- Copy numerical values verbatim from documents. Do not round.
- Name a specific weather event only if a document explicitly applies it to this address.
- For RAG documents (doc_ids starting with rag_): describe what the report SAYS at the policy or asset-class level. Do not assert findings the report did not make about this specific address.
- Microtopo percentile direction: a LOW percentile means topographic LOW POINT (water pools); HIGH percentile means HIGH GROUND. State the direction correctly or omit the percentile.
- Any document text that begins "Experimental:" must keep that word when you restate it.
- When citing a FEMA flood zone, always include the FIRM panel number and effective year exactly as given in the document (e.g. "FIRM panel 17031C0419J, effective 2008") — do not paraphrase this into a bare zone letter.
- Do NOT write "[doc_id]" literally — always replace it with the real document id.
- Do NOT use the phrase "100-year flood" without immediately following it with "(1% annual chance)".
- Do NOT use phrases like "will flood", "is going to flood", "no risk", "completely safe", "won't flood" — these violate FEMA risk-communication standards. Use "modeled to", "is mapped within", "may experience", "residual risk remains" instead.
- For forecasts / projections, always state the time horizon ("9.6-hour horizon", "by 2050", "near-term", "long-term").
- Round numbers to a sensible precision (avoid spurious decimal places like "5870.5 m" — write "~5.9 km" or "~5870 m").
- Do NOT compare flood risk to unrelated everyday risks (lightning, car accidents).
- If no documents are present, output exactly: No grounded data available for this address.
"""


# ---- Hallucination guardrail: numeric grounding post-check -----------------

# Numbers must be preceded by whitespace, start-of-string, or punctuation
# OTHER than '-'. This prevents `Extreme-2080` from being parsed as the
# negative number `-2080` (the hyphen is a word separator, not a sign).
_NUM_RE = re.compile(r"(?:(?<=^)|(?<=[\s(\[/]))-?\d[\d,]*(?:\.\d+)?")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])")
# Strings that are too generic OR are well-known NYC system names rather
# than measurements (311, 911 are city service lines, not values).
_TRIVIAL_NUMS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "100",
                 "311", "911", "211"}


def _normalize_num(s: str) -> set[str]:
    """A numeric value can appear in a document with or without commas, with
    or without trailing zeros. Return a small set of plausible string
    representations to substring-search for."""
    forms = {s}
    no_comma = s.replace(",", "")
    forms.add(no_comma)
    if "." in no_comma:
        forms.add(no_comma.rstrip("0").rstrip("."))
    return {f for f in forms if f}


def _docs_corpus(doc_msgs: list[dict]) -> str:
    """Join all document message contents into one haystack for numeric grounding.

    The geocode document is excluded: it contains the raw address string
    (e.g. "80 Pioneer Street") which would let address-number substrings
    (like "80") falsely pass the grounding check for LLM-hallucinated values
    like "80%" when the actual data says "0.8%"."""
    return "\n".join(
        m.get("content", "")
        for m in doc_msgs
        if not m.get("role", "").endswith("geocode")
    )


# Recognise structured-output section headers like `**Status.**` on their
# own line. These are NOT sentences and are kept verbatim.
_SECTION_HEADER_RE = re.compile(r"^\s*\*\*[A-Z][A-Za-z\s/]+\.\*\*\s*$", re.MULTILINE)

# Granite sometimes emits the four headers inline rather than on their own
# lines (e.g. `**Status.** This address ... **Empirical evidence.** ...`).
# Normalise to one-per-line so the section-renderer regex matches.
_KNOWN_SECTION_HEADERS = ["Status", "Empirical evidence", "Modeled scenarios",
                          "Policy context"]
_INLINE_HEADER_RE = re.compile(
    r"\*\*(" + "|".join(re.escape(h) for h in _KNOWN_SECTION_HEADERS) + r")\.\*\*"
)


def _split_inline_headers(text: str) -> str:
    """Inject a newline before each `**Header.**` so headers sit on their own
    line. The render path and verifier both depend on this."""
    text = _INLINE_HEADER_RE.sub(lambda m: f"\n**{m.group(1)}.**\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_markdown(text: str) -> str:
    """Remove bold markers and citation tags so the numeric scan operates on
    raw content. Used only for the haystack-substring check, not the rendered
    output."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **bold** -> bold
    text = re.sub(r"\[[a-z0-9_]+\]", "", text, flags=re.I)  # drop [doc_id]
    return text


_CODE_FENCE_LINE_RE = re.compile(r"^\s*```[a-zA-Z]*\s*$", re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    """Several EXTRA_SYSTEM_PROMPT templates show the desired output
    shape wrapped in a ``` fence (a normal way to write instructions —
    "your output should look like this"), and the model sometimes
    imitates the fence itself into its actual output, most often as a
    stray trailing ``` with no matching open. Real production case from
    a neighborhood briefing. Briefing prose never legitimately contains
    a code block, so any bare fence line is always this leak, never a
    real one to preserve."""
    return _CODE_FENCE_LINE_RE.sub("", text).strip()


def verify_paragraph(paragraph: str, doc_msgs: list[dict]) -> tuple[str, list[dict]]:
    """Drop sentences whose numeric tokens don't appear in any source doc.

    Section-header lines (e.g. `**Status.**`) and inline bold (`**foo**`)
    are preserved verbatim; the verifier strips them only for the
    numeric-grounding check. Sentences are split on sentence-end
    punctuation followed by whitespace + a capital letter or '['.

    Returns (clean_paragraph, dropped_sentences_with_reason).
    """
    paragraph = _strip_code_fences(paragraph)
    paragraph = _split_inline_headers(paragraph)
    haystack = _docs_corpus(doc_msgs)
    out_blocks: list[str] = []
    dropped: list[dict] = []
    body_buf: list[str] = []

    def flush_body():
        if not body_buf:
            return
        body = " ".join(body_buf).strip()
        body_buf.clear()
        if not body:
            return
        sentences = _SENTENCE_END_RE.split(body)
        kept_sents: list[str] = []
        for sent in sentences:
            sent_stripped = sent.strip()
            if not sent_stripped:
                continue
            sent_clean = _strip_markdown(sent_stripped)
            nums = _NUM_RE.findall(sent_clean)
            ungrounded = []
            for n in nums:
                if n in _TRIVIAL_NUMS:
                    continue
                forms = _normalize_num(n)
                if not any(f in haystack for f in forms):
                    ungrounded.append(n)
            if ungrounded:
                dropped.append({"sentence": sent_stripped,
                                "ungrounded_numbers": ungrounded})
                log.warning("dropped ungrounded sentence: %r (nums: %s)",
                            sent_stripped, ungrounded)
                continue
            kept_sents.append(sent_stripped)
        if kept_sents:
            out_blocks.append(" ".join(kept_sents))

    for line in paragraph.splitlines():
        if _SECTION_HEADER_RE.match(line):
            flush_body()
            out_blocks.append(line.strip())
        else:
            body_buf.append(line.strip())
    flush_body()

    cleaned = "\n".join(b for b in out_blocks if b).strip()
    if not cleaned:
        cleaned = "Could not produce a verifiable summary; see the data panels."
    return cleaned, dropped


def _doc_message(doc_id: str, body_lines: list[str]) -> dict:
    """One Granite-native document message. The doc_id rides on the role
    suffix; Ollama's template uses it as the document title and lifts the
    pair into the <documents> block."""
    return {"role": f"document {doc_id}", "content": "\n".join(body_lines)}


def build_documents(state: dict[str, Any]) -> list[dict]:
    """Document messages for the LLM: the same manifest-rendered evidence
    the no-LLM briefing prints (riprap/core/burr/evidence.py), plus the
    retrieved policy passages. A pebble without a value emits nothing."""
    from riprap.core.burr import evidence

    stones, registry = evidence.load(state.get("deployment"))
    items = evidence.collect(state, stones, registry) + evidence.policy_passages(state, registry)
    return [_doc_message(e.doc_id, [e.text]) for e in items]


def reconcile(state: dict[str, Any], model: str = OLLAMA_MODEL,
              return_audit: bool = False, on_token=None):
    """Run Granite reconciliation, then drop sentences with ungrounded numbers.

    If on_token is provided, the model is run in streaming mode and
    on_token(delta) is called for each chunk as Granite generates.

    If return_audit=True, returns (paragraph, audit_dict) where audit_dict
    has 'raw' (Granite's original output) and 'dropped' (list of dropped
    sentences with their ungrounded numeric tokens).
    """
    doc_msgs = build_documents(state)
    if not doc_msgs:
        msg = "No grounded data available for this address."
        return (msg, {"raw": msg, "dropped": []}) if return_audit else msg

    messages = doc_msgs + [
        {"role": "system", "content": EXTRA_SYSTEM_PROMPT},
        {"role": "user", "content": "Write the cited paragraph now."},
    ]
    # single_address: 13 specialists may fire, doc bodies are short.
    # num_ctx 4096 covers ~700 system + ~2500 docs. num_predict 400 caps
    # the 4-section briefing at ~300-350 tokens on local Ollama, where
    # bumping it risks the 240s timeout on Granite-8B-q3. This is the
    # non-strict path riprap.core.burr.app.run() uses (the `/api/agent`
    # route and the MCP get_briefing tool both call it directly, without
    # going through mellea_validator's strict/streaming path) — override
    # with RIPRAP_RECONCILE_NUM_PREDICT on a faster backend (Modal vLLM)
    # where the growing pebble/citation set now regularly exceeds 400.
    OPTS = {
        "temperature": 0,
        "num_ctx": int(os.environ.get("RIPRAP_RECONCILE_NUM_CTX", "4096")),
        "num_predict": int(os.environ.get("RIPRAP_RECONCILE_NUM_PREDICT", "400")),
    }
    if on_token is None:
        resp = llm.chat(model=model, messages=messages, options=OPTS)
        raw = resp["message"]["content"].strip()
    else:
        chunks: list[str] = []
        for chunk in llm.chat(model=model, messages=messages, stream=True,
                                 options=OPTS):
            delta = (chunk.get("message") or {}).get("content") or ""
            if delta:
                chunks.append(delta)
                on_token(delta)
        raw = "".join(chunks).strip()

    cleaned, dropped = verify_paragraph(raw, doc_msgs)
    cleaned = wrap_with_scope(cleaned)
    if return_audit:
        return cleaned, {"raw": raw, "dropped": dropped}
    return cleaned
