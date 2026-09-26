# Changelog

All notable changes to Riprap. The hackathon submission tag is
`v0.5.0` (build 2026-05-07); subsequent dates record polish work
that landed on the hackathon-period production deploys.

## [Unreleased] (MVP refactor)

- One orchestrator: the Burr app in `riprap/core/burr/app.py` now runs
  every intent (`single_address`, `neighborhood`, `development_check`,
  `live_now`, `compare`, `not_implemented`) with one parallel fan-out
  over the intent's pebbles. `app/fsm.py`, `app/intents/`, `app/stones/`
  and `app/reconcile.py` are removed.
- No-LLM mode is the default: every pebble value is rendered through its
  manifest `narration.template` (`riprap/core/burr/evidence.py`) and
  printed as the briefing.
- LLM mode talks to any OpenAI-compatible endpoint through the `openai`
  client (`RIPRAP_LLM_BASE_URL`, `RIPRAP_LLM_MODEL`, optional fallback).
  The model returns JSON claims; code checks citations and numbers,
  retries once and drops what fails (`docs/GROUNDING.md`). LiteLLM,
  Mellea and the reroll banners are removed.
- Neighbourhood intents accept a community district code such as `QN12`
  (the union of its NTAs). New `/api/district/{code}` and
  `/api/nyc311/flood_requests` routes; `/api/stream`, `/api/compare` and
  the debug endpoints are removed.
- MCP server rebuilt on the official `mcp` SDK with `list_sources`,
  `get_evidence`, `get_district_summary`, `get_citation`,
  `nyc311_flood_requests` and `get_briefing`. All but `get_briefing` work
  without an LLM.
- Static gallery: `scripts/build_gallery.py` precomputes ten NYC
  briefings that SvelteKit prerenders at `/gallery` with no backend, for
  GitHub Pages (`BASE_PATH`).
- Provenance comes only from manifests. Every provenance block has
  `date_modified` and `retrieved_at`, and every manifest has
  `maturity: production` or `maturity: experimental`.
- Experimental labels on `prithvi_water` (now "satellite-detected surface
  water after Ida", with no inside or outside verdict),
  `ttm_311_forecast`, `floodnet_forecast`, `ttm_battery_surge` and
  `policy_corpus`. The zero-shot `ttm_forecast` pebble is deleted and
  `prithvi_live` is removed from the app.
- The remote ML server (`app/inference.py`, `services/riprap-models`,
  `inference/`, `load/triton-local`) and all per-request Prithvi and
  TerraMind code are removed. TTM, Granite Embedding (query only) and
  Flair NER run in process on CPU; GLiNER is gone. Earth observation
  runs as a batch job (`scripts/run_eo_batch.py`).
- Light install: `uv sync` is the core with no torch. Extras: `ml`, `eo`,
  `pdf`, `energy`. The Makefile and `web/static` are removed.
- One HTTP client (`riprap/core/http.py`, httpx with hishel caching and
  stamina retries) for every adapter, including Nominatim with a 1
  request per second gate; geopy is removed. USGS gauges use the OGC API.
  FloodNet TLS verification is on. Dataset IDs fixed for HVI, NYCHA and
  NYS DOH hospitals.
- Energy ledger labels each LLM call measured (zeus-apple-silicon on a
  local endpoint), estimated (`RIPRAP_ENERGY_WATTS`) or unknown; hosted
  endpoints are always unknown. The NVML proxy headers and the sudo
  `powermetrics` path are removed, and `docs/BENCHMARKS.md` is marked
  historical.
- The `compliance` substring checks are described as disclosure checks,
  never a quality score.
- Docker: `Dockerfile.app` installs core plus `ml`; `docker-compose.yml`
  has the app and an optional `local-llm` Ollama profile. Modal is
  optional. Burr tracking is opt-in (`RIPRAP_BURR_TRACKING=1`).

## [Unreleased] — 2026-07-10 (Albany deployment)

### Fixed
- **NYC compliance 12/13 → 13/13 in the no-LLM tier.** Multi-sentence
  pebble narratives (`ida_hwm`, `microtopo`, `nyc311`) carried one
  trailing citation, but `every_numeric_claim_cited` (SPJ 7.1) audits
  per sentence, so their leading numeric sentences failed the audit.
  `_cite_numeric_sentences` in the templated reconciler now suffixes
  every uncited numeric-claim sentence with its `[doc_id]`, sharing the
  predicate's own regexes so repair and audit can't drift. Regression
  tests in `tests/test_templated_reconciler.py`.

### Added
- **Sixth city: Albany, NY** (`deployments/albany/`). First city with no
  open-data 311 export — its 311 intake runs on SeeClickFix, so
  `albany_311` calls the SeeClickFix public API via a new
  `app/context/seeclickfix.py` module (`python_call` pebble) that
  fetches nearest-first, haversine-filters to 300 m, and emits the same
  records shape as `socrata_records`. Water level resolves to NOAA
  8518995 (Albany, Hudson River — already in the station table). 13/13
  compliance at 24 Eagle St (City Hall); added to
  `scripts/probe_cities.py` and the deployment-routing tests. Any other
  SeeClickFix city reuses the module with just a manifest.
- **`albany_flood_311`** — flood-filtered variant of the Albany 311
  pebble: server-side `request_types` filter on Albany's flood-adjacent
  SeeClickFix categories (Water Issues/flooding 3418, Sinkholes 12499,
  Sewers/Drainage 12500) at 800 m radius.
- **Federal pebble: `fema_nfhl`** (`app/context/fema_nfhl.py`). Effective
  FEMA flood zone at any mapped US point from the NFHL ArcGIS layer 28,
  plus the FIRM panel effective year from layer 3 — satisfying the
  `firm_citation_has_vintage` predicate (FEMA 1.5). Fills the Hazard
  Reader section for every non-NYC city.
- **Federal pebble: `usgs_gauges`** (`app/context/usgs_gauges.py`). Live
  stage/discharge at the nearest active USGS stream gauge within a
  ~14 km box (NWIS instantaneous values, 15-minute cadence, one retry
  on NWIS's intermittent 503s). For Albany that's Patroon Creek at
  Albany (01359135), 1.5 km from City Hall; cities with no gauge in the
  box skip the pebble cleanly.
- **MCP server** (`riprap/mcp/server.py`, `python -m riprap.mcp.server`).
  Exposes Riprap as three agent-callable tools instead of a 1:1 wrap of
  the HTTP API: `get_briefing(address)`, `list_sources(deployment)`,
  `get_citation(deployment, doc_id)`. `list_sources` shares its
  stones+pebbles description with the HTTP `/api/pebbles` route via the
  new `riprap/core/pebbles/describe.py` helper. Defaults to stdio
  transport (Claude Desktop / local agent config); `--http` serves
  streamable-http for a remote agent.

### Changed
- **README scope-boundary section names the FEMA NFIP appeal process
  explicitly** as the contrast case: the 90-day appeal window and the
  scientific-or-technical-evidence-only standard (44 CFR Part 67) that
  a Riprap briefing is not part of.

## [Unreleased] — 2026-05-17 (Sunday, rebrand + BYOD + PDF route)

### Added — rebrand surface (Claude Design handoff)
- **New positioning copy across the marketing surface.** Hero H1 cycles
  through "A climate-exposure briefing for {New York City | Chicago |
  Seattle | San Francisco | Boston}." in federal-blue italic; deck
  names the four primary source families (FEMA / NOAA / USGS / city
  open data) so the trust-strip claim is foreshadowed inline. Browser
  title + meta description rewritten for any-US-place framing.
- **Dynamic header chip.** `/api/deployment` returns active deployment
  `{name, city, hazard}` from `stones.yaml`'s optional new
  `deployment:` block (with sensible deployment-dir-name fallback —
  `nyc → NYC`, `sf → SF`, `heat → NYC + "Heat-exposure briefing"`,
  etc.). `AppHeader` reads it through a Svelte 5 store; chip pill
  swaps as you change `RIPRAP_DEPLOYMENT`.
- **Six new trust components** (per civic-tech compliance registers
  USWDS · GOV.UK Design System · Section 508 · WCAG 2.2 AA · Plain
  Writing Act 2010):
  - `PhaseBanner.svelte` — open-beta banner, GOV.UK pattern
  - `UseBand.svelte` — responsible-use disclaimer + non-affiliation
  - `SourceStrip.svelte` — trust-signal counts (23 · 9 · 5 · 3)
  - `StandardsStrip.svelte` — compliance badges
  - `CityPicker.svelte` — five-city pill row, jumps to canonical
    anchor addresses that probe_cities.py exercises in CI
  - `SkipLink.svelte` — USWDS-canonical "Skip to main content"
- **BYOD client-side dialog** (`ByodDialog.svelte` + `client/byod.ts`
  + `stores/byodRegistry.svelte.ts`). Three-section workflow: file
  drop → adapter auto-detection → pebble mapping. Files stay on the
  user's machine; manifest persisted to IndexedDB via idb-keyval.
  Parsers: PapaParse for CSV, native JSON for `.json` / `.geojson`,
  js-yaml for `.yaml` / `.yml`.
- **Server-side PDF route** at `/api/print` via WeasyPrint
  (`app/print_pdf.py`). POST briefing JSON, get back a tagged PDF
  with cover · briefing · citations · verification stamp. SHA-256
  document hash on the stamp page lets two reviewers verify
  bit-for-bit equivalence. The header "export PDF" button now POSTs
  the cached `PrintSnapshot` from localStorage and opens the PDF in
  a new tab via a blob URL (replacing the legacy
  `/print/<queryId>` print-stylesheet path).

### Changed
- **Deleted `LandPreview.svelte`** — its "Briefing excerpt" pane
  carried synthetic numbers ("1% AE flood zone", "4.7 ft Sandy HWM",
  "14 nuisance floods since 2023") dressed in real-looking citation
  chrome on a page whose standards strip badges `✓ Plain Writing Act`.
  Removed. `LandStones` below is the structural explainer for "what
  you'll get back" and contains no fabricated data.
- **`LandStones` taglines** rewritten hazard- and city-agnostic
  (was NYC-specific: "what NYC's ground remembers", "MTA · NYCHA
  · DOE · DOH · PLUTO"; now: "what the ground remembers", "Transit
  entrances · public housing · schools · hospitals · whatever asset
  registers a jurisdiction publishes").
- **Provenance correctness fixes.** `floodnet.yaml` license
  `CC-BY-NC-4.0` → `CC-BY-NC-SA 4.0` (ShareAlike was missing; FloodNet
  data terms require it). `npcc4_slr.yaml` license
  `NYC Open Data Terms of Use` → `CC-BY-NC 4.0 (Annals of the New
  York Academy of Sciences)` with parent DOI `10.1111/nyas.15116` in
  the citation string.
- **AppFooter disclaimer reworded** from "does not predict damage"
  to "is a reference dossier, not a stamped engineering memo, risk
  score, or disclosure." Lists explicit out-of-scope uses (real-estate
  transactions, mortgage / insurance, personal property decisions).
- README adds a **"What this is. What this isn't."** block naming the
  user types Riprap is for (resilience consultants, ASTM E1527-21 BER
  addenda preparers, journalists, agency analysts) and explicitly NOT
  for (drainage / hydraulic design, residents — defer to FloodHelpNY,
  mortgage / insurance underwriting, real-estate transactions).

## [Unreleased] — 2026-05-16 (Saturday, post-hackathon OSS polish)

### Added
- **Five-city framework generalisation.** NYC is now the reference
  deployment; four new deployments ship alongside it on the same code:
  - `deployments/chicago/` — Socrata 311 (`v6vf-nfxy`), NOAA Calumet Harbor 9087044
  - `deployments/seattle/` — federal pebbles only (Seattle CSR lacks point geometry)
  - `deployments/sf/` — DataSF 311 (`vw6y-z8j6`, `point` field), NOAA SF Bay
  - `deployments/boston/` — Analyze Boston 311 via CKAN, NOAA Boston Harbor 8443970
- **`ckan_records` adapter** (`riprap/core/pebbles/adapters/ckan_records.py`)
  — bbox SQL push-down + haversine refine, since CKAN datasets usually
  ship lat/lon as numeric columns rather than a geometry-typed field.
  Unlocks Boston, Philadelphia, Toronto, EU portals.
- **BYOD load paths.** `load_registry` now merges manifests from
  `${CWD}/.riprap/` and from `RIPRAP_EXTRA_MANIFESTS` (colon-separated
  paths). Relative paths in BYOD manifests resolve against the
  manifest's own directory, so a user can ship a manifest + data file
  side-by-side anywhere on disk. Worked example in `examples/byod/`
  using real FDNY firehouses data (NYC Open Data `hc8x-tcnd`, 219
  records). Full walkthrough in `docs/byod.md`.
- **`scripts/probe_cities.py`** — 5-deployment sweep, runs in ~110 s
  against real upstream APIs, asserts 13/13 compliance per city.
  Reproducible regression check.
- **`docs/multi-city.md`, `docs/byod.md`, `docs/VERIFICATION.md`,
  `docs/PORT-YOUR-CITY.md`** — open-source onboarding surface.
- **`tests/test_byod_load.py`** — 7 tests covering both load paths,
  manifest-dir path resolution, cross-deployment portability, and
  override warnings.

### Changed
- `web/main.py:_run_compare` — fixed B023 loop-variable closure capture
  in the per-target trace wrapper (`_TaggedQ` now binds via `__init__`
  params, not closure). Latent footgun made deterministic.
- `tests/test_stone_envelope.py::test_step_to_stone_mapping_covers_known_steps`
  — was grep-based on `web/main.py` source; the pebble refactor moved
  `_STEP_TO_STONE` to a runtime dict comp. Test now asserts against the
  imported runtime dict.
- README banner re-pitched for OSS: framework, not just NYC.
- CONTRIBUTING re-framed from "hackathon submission" to "civic-tech
  framework that began as a hackathon project."
- `.github/ISSUE_TEMPLATE/port_to_new_city.yml` — refreshed to cite
  the 5 existing deployments + Socrata/CKAN adapters as starting points.

## [Unreleased] — 2026-05-09 (Saturday)

### Added
- **Per-query inference energy ledger** with real NVML readings off
  the L4 GPU. The status row on the Findings region now reports
  total Wh + total tokens for every briefing, with a leading icon
  (`✓` / `◐` / `~`) disclosing whether the number was measured or
  estimated. Full breakdown documented in
  [`docs/EMISSIONS.md`](docs/EMISSIONS.md).
- `inference-vllm/proxy.py`: 100 ms-cadence NVML sampler, response
  headers `X-GPU-Power-W` / `X-GPU-Energy-J` on every forwarded
  POST, and a `GET /v1/power` endpoint for bracket-sampling clients.
- `app/emissions.py` — new module with a thread-local `Tracker` that
  records every LLM and ML inference call (model, hardware, tokens,
  duration, joules) with a `measured: bool` flag per row.
- `scripts/probe_stones_fire.py` — programmatic CI that runs an
  address query against the lablab UI and asserts all five Stones
  fire, no `torchvision::nms` / `deps unavailable` dep regression,
  and the `emissions` block carries `nvidia_l4` hardware.
- `scripts/probe_benchmarks.py` — collects the canonical
  four-address verification set into `outputs/benchmarks.json`
  for the `docs/BENCHMARKS.md` page.
- `docs/EMISSIONS.md`, `docs/DEPLOY.md`, `docs/BENCHMARKS.md`,
  `CHANGELOG.md`, `CONTRIBUTING.md`.

### Changed
- The `RunHealthStrip` chip dropped the cloud-energy comparison
  (the sign convention was misleading and the comparison is now
  redundant given real measurements). New format:
  `<icon> X.X Wh / Y.YK tok inference`.
- `app/llm.py:_default_hardware_label` defaults to `"NVIDIA L4"`
  when remote vLLM is configured (was `"AMD MI300X"`, a stale
  string from the droplet days).
- `app/llm.py:chat()` now brackets every completion with two GETs
  to the inference Space's `/v1/power` endpoint; the average powers
  the LLM-call energy reading instead of the data-sheet estimate.
- `app/inference.py:_post()` reads NVML headers off the proxy
  response and forwards real joules into `emissions.record_ml`.

### Fixed
- `app/flood_layers/prithvi_live.py`: when the configured remote
  inference call fails (`RemoteUnreachable`), the specialist no
  longer falls through to the local terratorch path. The local
  path crashes with `RuntimeError: operator torchvision::nms does
  not exist` on the cpu-basic UI Space; surfacing a clean
  `remote prithvi-pluvial unreachable` skip is correct.
- `app/context/terramind_nyc.py:_try_remote()`: returns a
  `{"ok": False, "skipped": "remote terramind/<adapter>: ..."}`
  sentinel on remote failure, instead of `None` which was
  silently masked as `deps unavailable on this deployment`.
- `web/main.py`: explicit `/favicon.svg`, `/favicon.png`,
  `/favicon.ico`, `/robots.txt` routes — they were 404-ing under
  the SvelteKit SPA fallback because only `/_app` was mounted off
  the build directory.

### Documentation
- Full README rewrite reflecting the post-droplet L4 topology, the
  new emissions feature, and updated repo structure. Hackathon
  framing preserved.
- New `docs/DEPLOY.md` with the production topology, env-var
  reference, and per-Space deploy commands.
- New `docs/EMISSIONS.md` documenting what's measured vs. estimated,
  the NVML pipeline, and how to verify.

### Infrastructure note
- The DigitalOcean MI300X droplet was decommissioned 2026-05-06.
  All production inference now serves from `msradam/riprap-vllm`
  (NVIDIA L4). The MI300X runbook is preserved in
  [`docs/DROPLET-RUNBOOK.md`](docs/DROPLET-RUNBOOK.md) for anyone
  reproducing the AMD-judging setup; setting
  `RIPRAP_HARDWARE_LABEL=AMD MI300X` swaps the emissions profile
  back when redeploying to that hardware.

---

## [v0.5.0] — 2026-05-07

Hackathon submission tag.

### Added
- Five-Stone Burr FSM with Granite-native document-role messages
- Mellea four-check rejection sampling for the Capstone
- SvelteKit UI with SSE streaming, briefing prose, evidence-card
  grid, MapLibre overlay, citation drawer
- Three NYC-specialised foundation models published Apache-2.0:
  `msradam/TerraMind-NYC-Adapters` (LULC + Buildings + TiM LoRAs),
  `msradam/Prithvi-EO-2.0-NYC-Pluvial`,
  `msradam/Granite-TTM-r2-Battery-Surge`
- 30+ FSM specialists across hazard memory, asset registers, live
  observation, forecasting, and citation-grounded synthesis
