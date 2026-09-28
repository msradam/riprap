# Models and inference energy

Every model Riprap can run, what each evaluation supports, and how LLM energy is recorded. Moved from the README in refactor 7.

## Models

Every model is optional. Without the `ml` extra the model pebbles skip
themselves and the briefing is built from the data pebbles alone. The
table lists what the app runs today and what each evaluation supports.

| Model | Where it runs | Maturity | What the evidence supports |
|---|---|---|---|
| [`msradam/Granite-TTM-r2-Battery-Surge`](https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge) | `ttm_battery_surge` pebble, in process on CPU | Experimental | Test MAE 0.1091 m on held-out Battery gauge data, 41% better than persistence and 25% better than zero-shot TTM. It forecasts the surge residual only, has no wind or pressure input, and its briefing sentence points readers to NOAA ETSS or the Stevens Flood Advisory System for storm decisions. |
| Granite TimeSeries TTM r2 (base) | `ttm_311_forecast` and `floodnet_forecast` pebbles, in process on CPU | Experimental | Indicative forecasts of 311 complaint volume and FloodNet event recurrence. No held-out evaluation is published. |
| Granite Embedding 278M | `policy_corpus` pebble, query embedding only (the corpus index is built offline by `scripts/build_rag_index.py`) | Experimental | Retrieves passages from five NYC agency PDFs. Retrieval quality is not scored. |
| Flair NER (`flair/ner-english-ontonotes-fast`) | `policy_corpus` pebble, in process on CPU | Experimental | Coarse entity tags (agency, date, amount, place) on the retrieved passages. |
| Prithvi-EO 2.0 | Offline only: the baked Ida layer behind `prithvi_water`, and `scripts/run_eo_batch.py` | Experimental | Satellite-detected surface water after Ida. It mostly shows marsh, shoreline and park water, gives no inside or outside verdict for an address, and says nothing about street or basement flooding. |
| [`msradam/Prithvi-EO-2.0-NYC-Pluvial`](https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial) | Default checkpoint for `scripts/run_eo_batch.py`; not used by the app at runtime | Experimental | Test IoU 0.598, but the labels are the base model's own Ida polygons (self-distillation) and the random split shares parent scenes, so this measures agreement with pseudo-labels, not flood detection. |
| [`msradam/TerraMind-NYC-Adapters`](https://huggingface.co/msradam/TerraMind-NYC-Adapters) | Not used by the app | Research artifact | LoRA family on TerraMind 1.0. Reported mIoU: LULC 0.5866, TiM 0.6023, Buildings 0.5511. |
| Any OpenAI-compatible LLM | Optional, external endpoint | Production path, with claims checked in code | On ten gallery addresses, `granite4:micro` kept 122 claims and dropped 0; `llama3.1:8b` kept 191 and dropped 0 (`tests/probe_grounding_results*.json`). Every claim gets citation and number checks. Question answers also get lead rules (extractive mode, the default) or five answer checks and the entailment check (guarded mode) ([`docs/GROUNDING.md`](GROUNDING.md)). |
| `knowledgator/gliclass-large-v3.0` (GLiClass large v3.0) | Entailment check on guarded answers, in process on CPU (`ml` extra) | Experimental | An NLI-style classifier that scores whether the cited evidence supports each answer claim. It misses paraphrased inferences and drops some correct claims ([`docs/GROUNDING.md`](GROUNDING.md)). |
| GLiClass modern-base 311 filter | Non-NYC free-text 311 feeds (SF, Boston, Albany), in process on CPU; weights built locally and found through `RIPRAP_311_FILTER_PATH` | Experimental | Distilled from silver labels. Unreliable on live feeds: it kept street-cleaning and sidewalk reports as flooding (`tests/flood311_live_counts_2026-09-27.txt`). Without the weights, records pass unfiltered and the briefing says so. |

The three `msradam/*` fine-tunes were trained on AMD Instinct MI300X via
AMD Developer Cloud and are published under Apache 2.0. Reproduction
recipes live under `experiments/`.


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
`emissions` block of every result. In-process CPU models are not in it.
The numbers in [`docs/history/BENCHMARKS.md`](history/BENCHMARKS.md) come from the
retired GPU stack and are historical. Details in
[`docs/EMISSIONS.md`](EMISSIONS.md).

