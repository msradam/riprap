# Docs index

One-line map of everything under `docs/`. Read in this order if
you're new; jump directly if you know what you need.

| Doc | Purpose |
|---|---|
| [BACKGROUND.md](BACKGROUND.md) | Why Riprap exists, who it is for and not for, related work and how Riprap differs from or defers to it, the Five Stones in full and how they generalise beyond NYC. |
| [DATA-SOURCES.md](DATA-SOURCES.md) | The public sources behind the NYC deployment and what each is used for; every NYC Open Data dataset by name and ID, with what Riprap does to it. |
| [ACCESSIBILITY.md](ACCESSIBILITY.md) | The accessibility statement: the standard (WCAG 2.2 AA), how it was tested, what the code review found, known limitations and how to report a barrier. |
| [MODELS.md](MODELS.md) | The optional LLM, the experimental land-cover model, the surge forecast that is out of default briefings (with its backtest against six baselines), the retired satellite water layer and its two tests, and how energy is recorded. The corrected surge model card is in [model-cards/](model-cards/Granite-TTM-r2-Battery-Surge.md). |
| [REPOSITORY.md](REPOSITORY.md) | Code map: the pipeline at a glance, source-of-truth paths and the repository tree. |
| [PRIVACY.md](PRIVACY.md) | What Riprap stores and sends, 311 redaction, and a do-no-harm note. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system shape: the one Burr app, Five-Stone taxonomy, evidence and LLM claims checked in code for citations and numbers, SvelteKit + FastAPI + MCP surface. Start here. |
| [GROUNDING.md](GROUNDING.md) | How a briefing is grounded: manifest-rendered evidence, no-LLM mode and its rule answers, LLM answers checked in code, what is not checked. |
| [METHODOLOGY.md](METHODOLOGY.md) | Why Riprap computes no score, the evidence classes, the asset-register rule, terrain indices and scope; what the data cannot say, the distances, time windows and filters behind each count, and how to report an error. |
| [DEPLOY.md](DEPLOY.md) | Running Riprap: local with no LLM, local with an LLM, Docker, and an optional GPU LLM endpoint on Modal. |
| [briefing-standards.md](briefing-standards.md) | The FEMA, IPCC, TCFD, ASTM, AP Stylebook and SPJ rules behind the 13 disclosure checks (caveat-phrase substring tests, not a quality score). |
| [EMISSIONS.md](EMISSIONS.md) | Per-call energy ledger in `app/emissions.py`: measured, estimated or unknown, and why hosted endpoints get no figure. |
| [multi-city.md](multi-city.md) | Four deployments (NYC plus experimental Chicago, Seattle and Albany) on Socrata and SeeClickFix, with their limits. |
| [PORT-YOUR-CITY.md](PORT-YOUR-CITY.md) | Step-by-step walkthrough for adding your jurisdiction, using Chicago as the worked example. |
| [byod.md](byod.md) | Bring Your Own Data: `.riprap/` auto-discovery and the `RIPRAP_EXTRA_MANIFESTS` env var. Worked example with real FDNY data. |

## History

Records of earlier states of the project, kept for reference. None of them describes current behaviour.

| Doc | What it records |
|---|---|
| [history/BENCHMARKS.md](history/BENCHMARKS.md) | Latency and energy on four addresses from the retired Modal/L4 stack (2026-05-09). |
| [history/RESEARCH.md](history/RESEARCH.md) | A May 2026 research note on existing flood-risk tools and how Riprap differed then. |
| [history/SANITY-CHECK-2026-10-05.md](history/SANITY-CHECK-2026-10-05.md) | The sanity check of 5 October 2026, run by separate AI agents under the maintainer's direction: its method, the 680, 487, 475, 10 and 2 figures, every problem it found and what was done about each. |
| [history/VERIFICATION.md](history/VERIFICATION.md) | A deterministic verification pass on 2026-05-16: sweep results, pytest, lint, BYOD evidence. |
| [history/demo.md](history/demo.md) | The May 2026 flood, heat and air demo script. The heat and air scaffolds it describes were removed in October 2026. |

Design records: [PRODUCT.md](PRODUCT.md) (product context) and [DESIGN.md](DESIGN.md) (the design system), read by the Impeccable design tooling from `docs/`.

Top-level docs that complement these:

- [`README.md`](../README.md): what Riprap does, what it cannot tell you, status, quickstart, where a model runs and how Riprap was built, privacy, how to cite.
- [`CONTRIBUTING.md`](../.github/CONTRIBUTING.md): dev setup, probe scripts, PR flow.
- [`CHANGELOG.md`](../CHANGELOG.md): version history (`v0.5.0` is the hackathon submission).
- [`SECURITY.md`](../.github/SECURITY.md): vulnerability disclosure.
- [`CODE_OF_CONDUCT.md`](../.github/CODE_OF_CONDUCT.md): Contributor Covenant 2.1.
