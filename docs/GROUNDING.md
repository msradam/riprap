---
type: reference
---

# How a briefing is grounded

Riprap has two ways to write a briefing. Both start from the same evidence.

## Evidence

Every pebble that returns a value is rendered through its manifest's
`narration.template` into one or more plain sentences. If the template names a
field the value lacks, the pebble says nothing. Experimental pebbles begin with
"Experimental:". This rendering lives in `riprap/core/burr/evidence.py`.

Each piece of evidence has a `doc_id` (the manifest's `provenance.doc_id`).
Citations, source URLs and vintages come from the manifest's `provenance` block
and nowhere else.

## No-LLM mode (default)

With no LLM endpoint configured, the briefing is the evidence itself: one section
per Stone, one cited sentence per pebble. There is no model and nothing to
verify. This is the mode the static gallery and the MCP evidence tools use.

## LLM mode

Set `RIPRAP_LLM_BASE_URL` and `RIPRAP_LLM_MODEL` to any OpenAI-compatible
endpoint (for example local Ollama at `http://localhost:11434/v1`). The model
then rewrites the evidence as a list of claims. It never writes free prose.

1. The model receives the evidence sentences, grouped by section, each labelled
   with its `doc_id`. Retrieved policy passages are added as `rag_*` documents.
2. It must answer with JSON that matches a schema built for this request:
   `claims: [{section, text, doc_ids, numbers}]`. `doc_ids` is an enum of the
   ids actually passed in, and `section` is an enum of the sections that have
   evidence. The schema goes to the endpoint as `response_format`, so the
   decoder cannot produce other ids.
3. Code checks every claim (`riprap/core/burr/synthesis.py`, `verify`):
   - it cites at least one doc_id, and every cited id was passed in;
   - its section is one of the sections offered;
   - every number in the claim, both in its `numbers` field and anywhere in its
     text, matches a number in the documents it cites;
   - its text has no template placeholders such as `<value>` or `[doc_id]`.
4. If any claim fails, the model gets one retry with the failures and reasons
   listed.
5. Claims that still fail are dropped. They are returned in `dropped_claims`
   with their reason and shown in a collapsed "Dropped claims" section. They are
   never part of the rendered briefing.
6. The briefing is rendered from the surviving claims only. A section with
   evidence but no surviving claim prints "No grounded evidence for this
   section." A claim that cites an experimental source is prefixed
   "Experimental:" if the model left that out.

If no endpoint answers, the briefing falls back to the no-LLM evidence and says
why in `grounding.fallback_reason`.

### Questions

When the input is a question, not just a place, three more rules apply.

- The planner chooses which sources to consult from each manifest's
  `answers:` line; `select_pebbles` adds a short always-run floor (FEMA flood
  zone, Sandy extent and the DEP 2050 scenario for an address; NWS alerts for
  a "right now" question). Only those pebbles run, and every briefing lists the
  sources consulted and the ones not checked. A bare address runs every source.
- The claims schema gains a section `answer`. The model writes one to three
  claims there that answer the question directly; they are verified exactly
  like every other claim. The briefing opens with them. If none survives, it
  opens with the fixed line "The sources consulted do not answer this question
  directly. Here is what they show." A section whose only evidence is already
  stated in the answer is not repeated.
- Questions Riprap does not answer (buying, renting or insuring property,
  legal advice, a prediction for a specific day, or a hazard other than
  flooding) get a fixed refusal text, never model prose.

### Number tolerance

A claimed number matches an evidence number when one of these holds:

- they are equal, ignoring thousands separators and a leading sign;
- the evidence number rounds to the claimed number at the claim's precision
  (evidence 5870.5 supports "5870", "5871" and "5,870"; 16.89 supports "16.9"
  but not "16.95");
- the same holds after converting metres to feet or feet to metres, or metres to
  kilometres or kilometres to metres (16.89 m supports "55 ft"; 1417 m supports
  "1.4 km").

The numbers 311 and 911 are treated as service names, not measurements.
Numbers that appear in the user's own question or in the resolved address
(a house number, a street number, a year the user named) may be restated
without evidence support; they are the user's words, not claims about the
data. Numbers
must come from the documents the claim cites: a real number from a different
document does not count.

### What is not checked

Only citations and numbers are verified. Whether a non-numeric phrase ("sits
outside the 2012 Sandy extent") is supported by its cited document is not
checked by code. The evidence sentences are short and the model is told to
restate them, but a claim can still misstate a non-numeric fact and pass.

## Measuring it

`scripts/probe_grounding.py` runs the gallery addresses in LLM mode and writes
`tests/probe_grounding_results.json`: claims kept, claims dropped with reasons,
and claims that needed the retry. `tests/test_claim_verifier.py` holds
hand-written good and bad claims for the verifier.

## Disclosure checks

`riprap/core/compliance/predicates.py` runs substring checks on every briefing
for disclosure phrases (scope statement, automation disclosure, informational
disclaimer, citations on numeric sentences). They check that the disclosures are
present. They are not evidence of briefing quality.
