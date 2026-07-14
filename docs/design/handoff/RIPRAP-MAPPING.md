# RIPRAP-MAPPING — how this design system attaches to the codebase

How the resolved report-content design maps onto Riprap's existing stack,
and the two hard constraints a coding session must honor.

## Typeface — Sofia Sans + Overpass Mono

Resolved after an explicit search of the civic / mapping / compliance type
landscape (see the `*type*` specimen files in the design project).

| Role | Family | Why |
|---|---|---|
| Display / UI / body | **Sofia Sans** | Open, geometric-humanist grotesque in the Gotham lineage — reads NYC-civic (tall x-height, urban authority) without being Gotham (proprietary) or Arial (NY State brand, un-vendorable). Excellent tabular figures for the register. |
| Data / coordinates / citations / drafting labels | **Overpass Mono** | Derived from the US Federal Highway Administration signage alphabet — civic-infrastructure register, unambiguous digits. |

### Vendoring — the hard constraint
Both faces are **OFL** and MUST ship self-hosted via **`@fontsource`**, NOT a
CDN. Riprap is offline-safe / air-gappable and generates deterministic PDFs;
a CDN font would break both. Install:

```
npm i @fontsource/sofia-sans @fontsource/overpass-mono
```

Import the weights actually used (400/600/700/800 for Sofia Sans; 400/600 for
Overpass Mono). The print path (WeasyPrint) must register the same local font
files so the PDF hash stays reproducible across machines.

### Why not the obvious NYC options
- **Gotham** — NYC's brand face, but proprietary (license + self-host fail).
- **Arial** — NY State brand, but a system font (not distinctive, not vendorable as a brand asset).
- Using either would also risk implying **city/state affiliation**, which the project disclaimer explicitly forbids. Sofia Sans gives the register with zero licensing or affiliation exposure.

## Map — deck.gl over a CARTO basemap
The map layer is **deck.gl** (assumed as the map tech). Basemap: CARTO
Positron (light) so the evidence/severity ink reads on top. Sofia Sans is
compatible with the CARTO label register, so report chrome and basemap labels
form one continuous type system.

Layer → evidence-tier encoding:
- **Empirical** extents (Sandy zone, 311 points) → solid fill / solid square in the legend.
- **Modeled** extents (FEMA/DEP 2050) → hatched fill / hatched square, dashed outline.
- **Proxy** layers (HAND/TWI microtopography) → hollow square, off-by-default in the catalog.

## Evidence tier vs severity — two axes, two marks
- **Evidence tier** (how directly known): a **square**, fill carries directness — solid / hatched / hollow / stippled. Token group `purpose.tier.*`.
- **Severity** (how bad — `app/score.py` tier 1–4): a **filled-step triangle**, S1–S4. Token group `purpose.severity.*`. Deliberately a different shape and hue family so the two never collapse.

## Contrast fix
`--ink-tertiary` `#64748B` (measured 4.01:1 on the sunken surface — a real AA
failure) is replaced by `--riprap-text-tertiary` `#4E5A6E` (min 5.88:1). See
`proof/index.html` for every ratio computed live.

## Gates
`node gates/verify.mjs` runs contrast → grayscale → rules-lint → drift, all
zero-dependency and green against `tokens/tokens.css`. The behavioral gate
(`behavioral-gate.mjs`, Playwright + axe) is the remaining layer — run it
against a served specimen for keyboard, target-size, and axe checks.
