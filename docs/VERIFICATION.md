# Verification, 2026-05-16

> **Historical snapshot.** This records a verification pass against the
> `pebble-refactor` branch on 2026-05-16. Several things it mentions are
> gone: `_run_compare` in `web/main.py` (compare now runs inside the Burr
> app), the "All routing targets exhausted" LiteLLM error, the remote ML
> models (TerraMind, live Prithvi) and `requirements.txt` (dependencies
> are in `pyproject.toml` and `uv.lock`). The "13/13" column counts the
> disclosure checks: substring tests for caveat phrases, not a quality
> score. See the CI badge for current status.

## Sweep (5 cities × real APIs, no-LLM tier)

```
DEPLOYMENT          ADDRESS                                           DISCLOSURE  CITY PEBBLE       WALL
─────────────────   ──────────────────────────────────────────────    ──────────  ────────────────  ──────
nyc                 189 Atlantic Ave, Brooklyn                        13/13 ✓     nyc311=29         101 s
chicago             233 S Wacker Dr, Chicago, IL                      13/13 ✓     chicago_311=200   1.2 s
seattle             2100 5th Ave, Seattle, WA                         13/13 ✓     (none, by design) 0.6 s
sf                  1 Dr Carlton B Goodlett Pl, San Francisco, CA     13/13 ✓     sf_311=200        2.6 s
boston              1 City Hall Square, Boston, MA                    13/13 ✓     boston_311=396    0.6 s
```

5/5 PASS. Reproduce with
`.venv/bin/python scripts/probe_cities_smoke.py http://127.0.0.1:7860`
(consolidated from the `probe_cities.py` this snapshot originally ran).

## Pytest

```
42 passed, 6 skipped, 1 warning in 34s
```

Skipped tests need a live backend (`test_integration.py`) — run
separately when the server is up.

New tests this round (in `tests/test_byod_load.py`):

- `test_base_registry_excludes_byod_pebble` — no env, no `.riprap/`, no override
- `test_extra_manifests_env_merges_pebble` — env var path merges
- `test_extra_manifests_single_file_entry` — env var accepts a single yaml
- `test_dotriprap_auto_discovery` — `${CWD}/.riprap/*.yaml` auto-merges
- `test_byod_manifest_resolves_paths_against_manifest_dir` — the key portability guarantee
- `test_byod_pebble_portable_across_deployments` — same manifest, NYC vs Boston base
- `test_byod_id_collision_overrides_base` — override + stderr warning

## Lint (ruff)

All touched files clean. Real bugs fixed during this pass:

- `web/main.py:_run_compare` — B023 loop-variable capture in the per-target
  trace wrapper. The captured `_q` and `_label` were defined in the loop
  body and used inside a class method, so a future change that lets the
  `_TaggedQ` instance outlive the iteration would silently bind to the
  last-iteration values. Fixed by binding via `__init__` parameters.
- `tests/test_stone_envelope.py::test_step_to_stone_mapping_covers_known_steps`
  — was grepping `web/main.py` source for literal `"floodnet"` etc., but
  the pebble refactor moved `_STEP_TO_STONE` to a runtime dict comp. The
  test now asserts against the imported `_STEP_TO_STONE` directly, which
  is what we actually want to verify.

## UI (Playwright smoke, inference-offline)

Drove `http://127.0.0.1:8765/` with `189 Atlantic Avenue, Brooklyn`:

- SvelteKit landing page renders cleanly (search form, methodology, sources)
- Form submit routes to `/q/<address>`
- SSE stream connects; trace envelope frames all 5 Stone regions
- With vLLM Space paused: surfaces "All routing targets exhausted" inline
  with a link to status, no broken UI states. **Graceful offline path verified.**
- Cornerstone shows all 5 specialist functions in the provenance list,
  each reporting why they didn't fire (`query outside NYC bounds`, `no marks
  within 800m`, etc.)

The full LLM happy-path needs `RIPRAP_LLM_BASE_URL` pointing at a live
Granite 4.1 endpoint. Tested separately against the `msradam/riprap-inference`
Modal apps.

## BYOD demonstration (NYC + Boston deployments)

`examples/byod/fdny_firehouses.{yaml,csv}` (real NYC Open Data, 219 records):

| Loading path | Deployment | Address | Result |
|---|---|---|---|
| `RIPRAP_EXTRA_MANIFESTS=examples/byod` | NYC | 189 Atlantic Ave | 4 in 1.5 km radius, nearest Engine 224 @ 274 Hicks (454 m), 13/13 disclosure checks |
| `cp into ./.riprap/ && cd ./.riprap/..` | NYC | 80 Pioneer St, Red Hook | 2 in 1.5 km, nearest Battalion 32/Engine 202/Ladder 101, 13/13 disclosure checks |
| `RIPRAP_EXTRA_MANIFESTS=examples/byod` | Boston | 1 City Hall Square | 0 in radius (correct: NYC-only CSV), nearest 282 km away in Manhattan, Boston-native pebbles still flow (`boston_311=396`), 13/13 disclosure checks |

## Adapters in the registry

```
ADAPTERS = {
  "baked_vector",       # GeoJSON / GeoTIFF / Parquet
  "ckan_records",       # NEW — Boston, Philly, EU portals
  "csv_points",         # Tabular point data
  "local_corpus_with_ner",  # RAG + NER consolidated
  "python_call",        # Escape hatch for custom Python
  "rest_json",          # Generic REST + JMESPath
  "socrata_records",    # NYC, Chicago, Seattle, SF, DC, ...
}
```

## Reproducibility — pinned versions

For full release reproducibility. Anyone cloning the repo should be
able to recreate the verified state from these versions + the
checked-in `requirements.txt`.

**Foundation models (all Apache 2.0):**
- `ibm-granite/granite-4.1-8b` — reconciler LLM
- `ibm-granite/granite-embedding-278m-multilingual` — RAG embedding
- `ibm-granite/granite-timeseries-ttm-r2` (+ Riprap fine-tunes) — TTM forecasts
- `msradam/Prithvi-EO-2.0-NYC-Pluvial`: satellite water segmentation (experimental)
- `msradam/TerraMind-NYC-Adapters` — LULC / buildings via LoRA on TerraMind v1
- `flair/ner-english-ontonotes-large` — typed entity extraction (replaced GLiNER)

**Verified-at:**
- `burr==0.32.x` (Application + MapActions)
- `transformers>=4.45`, `sentence-transformers>=5.0`
- `torch==2.5.1` (CPU on local; CUDA on remote)
- `granite-tsfm==0.3.3` (pinned — 0.3.4+ drops py3.10)

**Per-deployment data sources (citation manifests in
`deployments/<city>/manifests/*.yaml`):**
- NYC: 23 pebbles; Sandy 2012 extent, NYC DEP stormwater scenarios,
  Ida HWMs, Prithvi-EO satellite-detected surface water after Ida
  (experimental), USGS 3DEP DEM + HAND/TWI,
  FloodNet, NYC 311 (`erm2-nwe9`), NWS METAR + alerts, NOAA Battery
  (8518750), NPCC4 (`doi:10.1111/nyas.15116`), MTA / NYCHA / DOE / DOH
  registers, policy corpus (Comptroller, DEP, ConEd, MTA, NYCHA PDFs)
- Chicago: 4 pebbles via Socrata `v6vf-nfxy` + NOAA Calumet Harbor 9087044
- Seattle: 3 federal pebbles (CSR 311 has no Point geometry; skipped)
- SF: 4 pebbles via DataSF `vw6y-z8j6` + NOAA SF Bay
- Boston: 4 pebbles via Analyze Boston `1a0b420d-...` (CKAN) + NOAA Boston Harbor 8443970

## Known follow-ups

- **LLM happy-path UI smoke against a cloud GPU backend**: verified
  locally on M3 via Ollama. Cloud inference runs on the two Modal apps
  in the companion `msradam/riprap-inference` repo.
- **`app/context/*.py` → proper pebble adapters** — currently called via
  `python_call`. Moving each to a typed adapter would close the
  "manifests, not code" loop fully.
- **Capstone provenance reads `policy_corpus` state key** — Phase 5 of
  the UI ↔ backend alignment; deferred from the Option II refactor.
- **Unified citation namespace under `policy_corpus`** — Phase 6 of
  the same plan; replaces the `rag_*` per-PDF citation chips with a
  single parent chip whose children are the individual sources.
