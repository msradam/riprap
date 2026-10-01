# Models and inference energy

## Models

Riprap runs no model in its own process and ships no weights. With nothing
configured, a briefing is built from the data, and a question is answered
by rules over its words (`riprap/core/burr/rule_answer.py`).

The one model Riprap can use is an optional LLM behind any
OpenAI-compatible endpoint (`RIPRAP_LLM_BASE_URL`, `RIPRAP_LLM_MODEL`); it
was tested with Granite 4.1 8B
(`hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M` over Ollama). The rules
answer first even then. The model is asked only when the rules do not
recognise a question or cannot read its place: it plans the query, chooses
a lead and up to four cited facts, and code checks that choice; the answer
text is the sources' own sentences ([`docs/GROUNDING.md`](GROUNDING.md)).
The gallery is built with no model. `app/models_info.py` lists the
endpoint that answered in each result's `models` field and at
`/api/models`.

An earlier probe had the model rewrite the evidence for ten gallery
addresses as claims (the mode now behind `RIPRAP_LLM_BARE=1`).
`granite4:micro` kept 122 claims and dropped 0, and `llama3.1:8b` kept 191
and dropped 0 (`tests/probe_grounding_results*.json`).

Earlier versions ran a satellite water model, three time-series forecasts,
an embedding model and an entity tagger. None of them is used now; the
code is in git history at `8b87165`.

## Inference energy

`app/emissions.py` records every LLM call in a briefing with its tokens,
duration and an energy status:

| Status | When |
|---|---|
| measured | Local endpoint on Apple Silicon with the `energy` extra (zeus-apple-silicon). Whole-chip energy during the call, so it includes other processes. |
| estimated | Local endpoint with `RIPRAP_ENERGY_WATTS` set: declared watts times duration. |
| unknown | Everything else. Hosted endpoints are always unknown and no per-query figure is reported for them. |

zeus-apple-silicon 1.1.0 reads 0 mJ of CPU energy on an Apple M5; those
readings are rejected and the call is marked unknown. The ledger is the
`emissions` block of every result.
The numbers in [`docs/history/BENCHMARKS.md`](history/BENCHMARKS.md) come from the
retired GPU stack and are historical. Details in
[`docs/EMISSIONS.md`](EMISSIONS.md).
