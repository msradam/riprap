# HANDOFF — Riprap report-content design system (v1, resolved)

This is the human-readable handoff. It states every decision that was
made, why, and where it lives, so a coding session (or a reviewer) can
pick it up without re-deriving anything. The companion file
`CLAUDE-CODE-PROMPT.md` is the actionable build prompt for implementing
this into the live SvelteKit codebase, including the deck.gl migration.

---

## 1. What was decided (and the reasoning)

### Type — Sofia Sans + Overpass Mono
- **Sofia Sans** — display / UI / body. An open, geometric-humanist grotesque in the Gotham lineage: reads NYC-civic (tall x-height, urban authority) without being Gotham (proprietary) or Arial (NY State brand, not vendorable as an asset). Strong tabular figures for the register.
- **Overpass Mono** — data, coordinates, citation marks, drafting labels. Derived from the US Federal Highway Administration signage alphabet — a civic-infrastructure register with unambiguous digits.
- **IBM Plex was explicitly rejected** — it is the generic-AI "technical" default and carries that tell. The serif-headline register was also rejected: the "large serif headline + sans body" combo is itself a current AI trope.
- **Hard constraint:** both are OFL and MUST ship self-hosted via `@fontsource` (no CDN). Riprap is offline-safe and generates deterministic PDFs; a CDN font breaks both. The specimen files load them from Google Fonts *for preview convenience only* — production vendors them.

### Color — one token system, three layers
Primitive → semantic → purpose. The full set is in `tokens/tokens.dtcg.json` and mirrored to `tokens/tokens.css` (built) + `tokens/reference.css` (drift source of truth).

- **Confirmed bug fixed:** `--ink-tertiary` `#64748B` measured **4.01:1 on the sunken surface** — a real WCAG 1.4.3 failure. Replaced by `--riprap-text-tertiary` `#4E5A6E` (min **5.88:1**). Verified live in `proof/index.html`.
- **Status green** darkened from `#1F7A3D` (4.74:1, risky) to `#166534` (6.29:1 on inset).
- **Every color the specimen paints is a token** — verified by a live scan (`Color audit.dc.html`), which originally caught 6 off-palette convenience colors and drove them into the token set (`slate-250/350/450`, `green-800`, `paper-inset`, `mist`, `sky-100`).

### Evidence tier — the square, fill carries directness
Riprap's existing epistemic axis (empirical / modeled / proxy / synthetic) was **color-only**, failing WCAG 1.4.1 in grayscale and print. Resolved to a **square whose FILL encodes the tier** — solid / hatched / hollow / stippled — with hue as reinforcement only. Chosen from a 4-option exploration (`Evidence-tier marks.dc.html`, option 1a). Distinction survives grayscale because it is shape, not hue.

### Severity — the triangle, a separate axis
"How bad is this" (`app/score.py` tier 1–4) is a **different question** from "how directly is this known," so it gets a **different mark: a filled-step triangle S1–S4**, different shape and hue family, so the two axes never collapse into one another.

### Citations — periphery, not decoration
Inline superscript `[n]` in Overpass Mono, each carrying a descriptive accessible name (`aria-label="Citation 3: NYC OpenData, 311 flood service requests"`). Inline, so they qualify for the WCAG 2.5.8 target-size inline exception — do not inflate them.

### Print grammar
Cover (title / scope / disclaimer / severity) → body with grouped citations → SHA-256 stamp page. Fonts registered as **local files** so the PDF hash stays reproducible. Resolved hexes are inlined in the print CSS so the document renders identically regardless of the pinned WeasyPrint version.

### Map — deck.gl over the CARTO basemap
The map moves to **deck.gl**, overlaid on the existing MapLibre CARTO Positron basemap. Each layer is tagged by deck.gl type and by evidence tier; the legend marks mirror the tier squares exactly. See the prompt for the integration recipe.

---

## 2. What's in the package

```
tokens/
  tokens.dtcg.json     W3C DTCG tokens — primitive / semantic / purpose
  tokens.css           built CSS custom properties (--riprap-*) — gates read this
  reference.css        hand-typed drift source of truth (must match tokens.css)
css/
  components.css       on-screen component layer — var()-only, focus-visible, no elevation
gates/
  verify.mjs           runs all four in order; first non-zero exit blocks
  contrast-gate.mjs    WCAG 2.x contrast, every text/mark role × surface  (CONFIGURED)
  grayscale-gate.mjs   same, through Rec.601 desaturation (1.4.1)          (CONFIGURED)
  rules-lint.mjs       structural rules: no raw hex, focus-visible, no elevation, motion budget (CONFIGURED)
  drift-gate.mjs       tokens.css vs reference.css, name by name           (CONFIGURED)
  behavioral-gate.mjs  Playwright + axe — needs a served build (NOT run here)
  lib/                 zero-dependency color + token-parse helpers
proof/index.html       every contrast ratio computed live from shipped hexes
RIPRAP-MAPPING.md       typeface + @fontsource vendoring, evidence/severity axes, deck.gl encoding
HANDOFF.md              this file
CLAUDE-CODE-PROMPT.md   the implementation prompt for the codebase
```

Plus the rendered specimens (design project, `.dc.html`):
`Riprap demo.dc.html` (front door), `Riprap briefing.dc.html` (briefing / register / print),
`Accessibility check.dc.html`, `Color audit.dc.html`, `Evidence-tier marks.dc.html`,
`Civic type gallery.dc.html`.

---

## 3. How compliance is verified (three layers, no assertions)

1. **Deterministic gates (CI, zero-dependency):** `node gates/verify.mjs` → contrast, grayscale, rules-lint, drift. All green.
2. **Live re-runnable checkers (browser):** `Accessibility check.dc.html` (223 elements — contrast, grayscale, sizing, target size, keyboard, focus, ARIA) and `Color audit.dc.html` (token membership, 1.4.1 redundancy, color-blindness simulation). Both re-probe the real briefing DOM on reload.
3. **Behavioral gate (remaining):** `behavioral-gate.mjs` (Playwright + `@axe-core`) — the one layer that needs a served build, for real focus traversal and axe's full ruleset. Run it in the coding session against a live URL.

Measured headline (from the live scoreboard): text min **4.56:1**, marks all ≥3:1 incl. grayscale, **0 rogue colors**, 12px size floor, all decorative marks `aria-hidden`, all interactive controls keyboard-reachable + named + focus-visible.

---

## 4. Scope

In scope: **report content** — text/surface tokens, the evidence + severity marks, citation marks, the register table treatment, the print grammar, and the map layer encoding. Out of scope: Riprap's structural site chrome (header, footer, skip-nav, generic buttons) which already exists (`@nysds`). The two most important product decisions surfaced but left to the team: (a) severity is a genuine separate axis — the mark is designed, wiring it to `score.py` output is a product call; (b) the register's bulk-asset density vs. calm tension was resolved toward the engineering-artifact reading per direction given.
