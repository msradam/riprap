# Docs index

One-line map of everything under `docs/`. Read in this order if
you're new; jump directly if you know what you need.

| Doc | Purpose |
|---|---|
| [BACKGROUND.md](BACKGROUND.md) | Why Riprap exists, who it is for and not for, the Five Stones in full and how they generalise beyond NYC. |
| [DATA-SOURCES.md](DATA-SOURCES.md) | The public sources behind the NYC deployment and what each is used for. |
| [MODELS.md](MODELS.md) | Every model Riprap can run, what each evaluation supports, and how LLM energy is recorded. |
| [REPOSITORY.md](REPOSITORY.md) | Code map: the pipeline at a glance, source-of-truth paths and the repository tree. |
| [PRIVACY.md](PRIVACY.md) | What Riprap stores and sends, 311 redaction, and a do-no-harm note. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system shape: the one Burr app, Five-Stone taxonomy, evidence and LLM claims checked in code for citations and numbers, SvelteKit + FastAPI + MCP surface. Start here. |
| [GROUNDING.md](GROUNDING.md) | How a briefing is grounded: manifest-rendered evidence, no-LLM mode, LLM claims checked in code for citations and numbers, answer rules, what is not checked. |
| [METHODOLOGY.md](METHODOLOGY.md) | The deterministic exposure tier used by the offline register builders: sub-indices, weights, floor rule, references. |
| [DEPLOY.md](DEPLOY.md) | Running Riprap: local with no LLM, local with an LLM, Docker, and an optional GPU LLM endpoint on Modal. |
| [briefing-standards.md](briefing-standards.md) | The FEMA, IPCC, TCFD, ASTM, AP Stylebook and SPJ rules behind the 13 disclosure checks (caveat-phrase substring tests, not a quality score). |
| [EMISSIONS.md](EMISSIONS.md) | Per-call energy ledger in `app/emissions.py`: measured, estimated or unknown, and why hosted endpoints get no figure. |
| [multi-city.md](multi-city.md) | Six deployments (NYC plus experimental Chicago, Seattle, SF, Boston, Albany) on Socrata, CKAN and SeeClickFix, with their limits. |
| [PORT-YOUR-CITY.md](PORT-YOUR-CITY.md) | Step-by-step walkthrough for adding your jurisdiction, using the Boston port as the worked example. |
| [byod.md](byod.md) | Bring Your Own Data: `.riprap/` auto-discovery and the `RIPRAP_EXTRA_MANIFESTS` env var. Worked example with real FDNY data. |
| [multi-hazard.md](multi-hazard.md) | Heat and air-quality scaffolds (`deployments/heat/`, `deployments/air/`) on the same Stones taxonomy. |

## History

Records of earlier states of the project, kept for reference. None of them describes current behaviour.

| Doc | What it records |
|---|---|
| [history/BENCHMARKS.md](history/BENCHMARKS.md) | Latency and energy on four addresses from the retired Modal/L4 stack (2026-05-09). |
| [history/RESEARCH.md](history/RESEARCH.md) | A May 2026 research note on existing flood-risk tools and how Riprap differed then. |
| [history/VERIFICATION.md](history/VERIFICATION.md) | A deterministic verification pass on 2026-05-16: sweep results, pytest, lint, BYOD evidence. |
| [history/demo.md](history/demo.md) | The flood, heat and air demo script; only the flood part runs today. |

Design records: [PRODUCT.md](PRODUCT.md) (product context) and [DESIGN.md](DESIGN.md) (the design system), read by the Impeccable design tooling from `docs/`.

Top-level docs that complement these:

- [`README.md`](../README.md): what Riprap does, status, quickstart, privacy, how to cite.
- [`CONTRIBUTING.md`](../.github/CONTRIBUTING.md): dev setup, probe scripts, PR flow.
- [`CHANGELOG.md`](../CHANGELOG.md): version history (`v0.5.0` is the hackathon submission).
- [`SECURITY.md`](../.github/SECURITY.md): vulnerability disclosure.
- [`CODE_OF_CONDUCT.md`](../.github/CODE_OF_CONDUCT.md): Contributor Covenant 2.1.
