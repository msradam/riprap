# Claude Code prompt — implement the Riprap report-content design system

Paste this into a Claude Code session running **in the Riprap repository**.
It implements the resolved design system (see `HANDOFF.md` and
`RIPRAP-MAPPING.md` in this handoff folder) into the live SvelteKit app,
including migrating the map to deck.gl. Do not invent visual decisions —
they are all made; your job is to wire them in and make the gates pass.

---

## Role & guardrails

You are implementing a **finished** design system, not designing one. Every
color, font, mark, and threshold is decided and lives in the handoff files.

- **Do not** introduce a color, radius, shadow, or font that is not a token.
- **Do not** touch the structural site chrome (header, footer, skip-nav, generic buttons — `@nysds`). Scope is **report content** only.
- **Do not** reintroduce `#64748B` for tertiary text (it fails AA at 4.01:1 on the sunken surface) — use `--riprap-text-tertiary` `#4E5A6E`.
- Ground every value in `tokens/tokens.css`. If you need a color that isn't there, stop and add it to BOTH `tokens/tokens.css` and `tokens/reference.css` identically (the drift gate compares them), then continue.
- After every change that touches tokens or components, run `node gates/verify.mjs` and keep it green.

## Read first
`HANDOFF.md`, `RIPRAP-MAPPING.md`, `tokens/tokens.dtcg.json`, `reference/riprap-tokens-current.css` (what's shipping now), `reference/riprap-print-pdf-current.css`, and `app/score.py` (severity tiers). Diff the current token file against `tokens/tokens.css` so you know exactly what changes.

---

## Task 1 — Tokens

1. Replace the shipping token file with `tokens/tokens.css` (the `--riprap-*` custom properties). Keep the three-layer structure (primitive → semantic → purpose). Confirm `--riprap-text-tertiary` is `#4E5A6E`, not `#64748B`.
2. Wire `tokens.dtcg.json` into whatever token pipeline exists (or add one). `reference.css` is the drift source of truth — keep it byte-identical to `tokens.css`'s `:root` declarations.
3. Grep the codebase for hard-coded hexes in report-content components and replace with `var(--riprap-*)`. `rules-lint.mjs` will fail the build on raw hex in the component CSS.

## Task 2 — Fonts (self-hosted, no CDN)
```
npm i @fontsource/sofia-sans @fontsource/overpass-mono
```
Import the used weights (Sofia Sans 400/600/700/800; Overpass Mono 400/600) in the app entry. **Remove any Google Fonts `<link>`** — offline-safe is a hard requirement. Set the report-content font tokens:
`--riprap-font-display` / `--riprap-font-sans` → Sofia Sans; `--riprap-font-mono` → Overpass Mono. For the PDF path, register the same local font files with WeasyPrint so the document hash stays reproducible.

## Task 3 — Evidence-tier + severity marks (Svelte components)
Lift the SVG symbols verbatim from `Riprap briefing.dc.html` (the `<defs>` block): `sq-solid / sq-hatch / sq-hollow / sq-stipple` (patterns `rp-hatch`, `rp-dots`) and `sev-1..4` (clip `rp-tri`).

- `EvidenceMark.svelte` — prop `tier: 'empirical'|'modeled'|'proxy'|'synthetic'`; renders the matching square via `<use>`, colored by the tier token. **Fill/shape is the carrier; color is reinforcement.** Always accompanied by a text tier code (EMP/MOD/PRX/SYN) OR sits on content whose shape already differs.
- `SeverityMark.svelte` — prop `level: 1|2|3|4` wired to `app/score.py` output; renders the filled-step triangle. Different shape + hue family from evidence — never merge the two.
- **Accessibility:** every decorative mark SVG gets `aria-hidden="true"` (meaning is in the adjacent text). The marks must never be the sole carrier — verified by `Color audit.dc.html`'s 1.4.1 section.

## Task 4 — Citation marks
Inline superscript `[n]` in Overpass Mono, `<a>` to the source, with `aria-label="Citation {n}: {source description}"` (2.4.4). Inline → exempt from 2.5.8 target size; **do not enlarge them**. `:focus-visible` ring from `--riprap-focus`.

## Task 5 — Register table
Follow `.riprap-register` in `css/components.css` and the specimen's screen 2: mono uppercase `th` with `scope="col"`, a visually-hidden `<caption>`, 2px `--riprap-rule-strong` header underline, `--riprap-surface-sunken` zebra, tabular-nums on numeric columns, evidence + severity marks per row.

## Task 6 — Print grammar (WeasyPrint)
Update `app/print_pdf.py` + the print CSS to the resolved grammar: cover (title / scope / disclaimer / severity mark) → body with **grouped citations** → SHA-256 stamp page. Move footer/eyebrow color off `#64748b` onto `#4E5A6E`. Inline resolved hexes (don't rely on `var()` across WeasyPrint versions). Close the known static-map gap (see the `Future` note atop `app/print_pdf.py`) — render the deck.gl map to a static image for print (Task 7).

## Task 7 — deck.gl integration (over the existing MapLibre/CARTO basemap)

The current map is MapLibre GL with a CARTO Positron basemap. **Overlay deck.gl** rather than replacing the basemap, using the interleaved `MapboxOverlay` so deck layers sort correctly with basemap labels.

```
npm i deck.gl @deck.gl/mapbox
```

```js
import { MapboxOverlay } from '@deck.gl/mapbox';
import { GeoJsonLayer, ScatterplotLayer } from '@deck.gl/layers';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';

// after the MapLibre map is created:
const overlay = new MapboxOverlay({ interleaved: true, layers: buildLayers(data) });
map.addControl(overlay);
```

Layer → evidence-tier encoding (mirror the legend squares exactly; pull the hexes from the tokens, do not hard-code):

| Layer | deck.gl type | Tier | Fill / style |
|---|---|---|---|
| Sandy Inundation Zone (2012) | `GeoJsonLayer` | empirical | solid fill, `--riprap-tier-empirical` |
| FEMA / DEP 2050 scenarios | `GeoJsonLayer` (polygons) | modeled | dashed outline + low-opacity fill (hatch is a legend affordance; on the map use dashed stroke + ~16% fill), `--riprap-tier-modeled` |
| Ida HWM points (2021) | `ScatterplotLayer` | empirical | `--riprap-tier-empirical` |
| Microtopography (HAND/TWI) | `GeoJsonLayer` | proxy | hollow / off-by-default in the catalog, `--riprap-tier-proxy` |
| 311 flood requests | `HeatmapLayer` | empirical | sequential ramp anchored on `--riprap-tier-empirical` |

- **Legend:** reuse `EvidenceMark` so the on-map legend and the report body use the identical square marks.
- **Layer toggles:** real `<button>` controls with `aria-pressed`, accessible names, ≥24px targets, `:focus-visible` — not click-only divs (see the specimen's layer list). Layer state must read from text (ON/OFF) + icon, never color/opacity alone.
- **Accessibility:** the map is decorative-of-a-text-equivalent — give the map container `role="img"` + an `aria-label` summarizing what the layers show, since the briefing prose already states the exact figures. Respect `prefers-reduced-motion` (no fly-to animations when set).
- **Print:** render the deck.gl scene to a static PNG (deck.gl `Deck` with `preserveDrawingBuffer`, or a server-side headless render) and embed it in the WeasyPrint PDF — closes the static-map gap.

## Task 8 — Interactive controls & motion
Every report-content control is a native element (`<button>`/`<a>`/`<input>`), keyboard-reachable, with an accessible name and a `:focus-visible` ring from `--riprap-focus`. On-screen text floor 12px. One motion budget: no transition/animation > 150ms; honor `prefers-reduced-motion`. No elevation (no box-shadow/blur) — hierarchy comes from rules, weight, and type. `rules-lint.mjs` enforces the last three.

---

## Definition of done
1. `node gates/verify.mjs` exits 0 (contrast, grayscale, rules-lint, drift all green).
2. `RIPRAP_DESIGN_TARGET_URL=<served build> node gates/behavioral-gate.mjs` passes (keyboard, target size, axe).
3. No CDN font requests; app works offline; PDF hash reproducible across two machines.
4. No raw hex in report-content CSS; every rendered color is a token (cross-check against `Color audit.dc.html`'s scan logic).
5. Evidence + severity remain distinguishable in grayscale and under color-blindness (the marks carry meaning by shape).
6. The rendered result matches the specimens (`Riprap briefing.dc.html` — briefing, register, print) in structure, type, marks, and spacing.

## What NOT to do
- Don't redesign anything — this is implementation. Questions of taste are already resolved in the handoff.
- Don't add decorative gradients, shadows, rounded-card treatments, or icons that aren't the evidence/severity marks.
- Don't let the map's color be the only thing distinguishing a layer's tier — shape/text is the carrier.
- Don't reintroduce the tertiary contrast bug, a CDN font, or a color that isn't a token.
