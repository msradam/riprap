# Docs index

One-line map of everything under `docs/`. Read in this order if
you're new; jump directly if you know what you need.

| Doc | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system shape: the one Burr app, Five-Stone taxonomy, evidence and verified-claim synthesis, SvelteKit + FastAPI + MCP surface. Start here. |
| [GROUNDING.md](GROUNDING.md) | How a briefing is grounded: manifest-rendered evidence, no-LLM mode, LLM claims verified in code, what is not checked. |
| [METHODOLOGY.md](METHODOLOGY.md) | The deterministic exposure tier used by the offline register builders: sub-indices, weights, floor rule, references. |
| [DEPLOY.md](DEPLOY.md) | Running Riprap: local with no LLM, local with an LLM, Docker, and an optional GPU LLM endpoint on Modal. |
| [briefing-standards.md](briefing-standards.md) | The FEMA, IPCC, TCFD, ASTM, AP Stylebook and SPJ rules behind the 13 disclosure checks (caveat-phrase substring tests, not a quality score). |
| [EMISSIONS.md](EMISSIONS.md) | Per-call energy ledger in `app/emissions.py`: measured, estimated or unknown, and why hosted endpoints get no figure. |
| [BENCHMARKS.md](BENCHMARKS.md) | Historical: latency and energy on four addresses from the retired Modal/L4 stack (2026-05-09). |
| [RESEARCH.md](RESEARCH.md) | Research notes: what existing flood-risk tools do and how Riprap differs. |
| [multi-city.md](multi-city.md) | Six deployments (NYC plus experimental Chicago, Seattle, SF, Boston, Albany) on Socrata, CKAN and SeeClickFix, with their limits. |
| [PORT-YOUR-CITY.md](PORT-YOUR-CITY.md) | Step-by-step walkthrough for adding your jurisdiction, using the Boston port as the worked example. |
| [byod.md](byod.md) | Bring Your Own Data: `.riprap/` auto-discovery and the `RIPRAP_EXTRA_MANIFESTS` env var. Worked example with real FDNY data. |
| [multi-hazard.md](multi-hazard.md) | Heat and air-quality scaffolds (`deployments/heat/`, `deployments/air/`) on the same Stones taxonomy. |
| [demo.md](demo.md) | Demo script for the flood, heat and air deployments. |
| [VERIFICATION.md](VERIFICATION.md) | Historical snapshot (2026-05-16) of a deterministic verification pass: sweep results, pytest, lint, BYOD evidence. See the CI badge for current status. |

Top-level docs that complement these:

- [`README.md`](../README.md): project overview, quickstart, Five Stones, models, citations.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md): dev setup, probe scripts, PR flow.
- [`CHANGELOG.md`](../CHANGELOG.md): version history (`v0.5.0` is the hackathon submission).
- [`SECURITY.md`](../SECURITY.md): vulnerability disclosure.
- [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md): Contributor Covenant 2.1.
