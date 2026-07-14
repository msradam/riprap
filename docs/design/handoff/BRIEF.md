# Brief — what Riprap is, who reads it, what already exists

## What Riprap is

An open-source tool that turns a US address into a short, citation-grounded
climate-exposure briefing: a written paragraph plus evidence cards plus a
map, where every numeric claim traces back to a specific public-record
dataset, agency report, or model output (`[doc_id]` citation tags). Flood
is the production-grade reference hazard (NYC, 25 data sources); heat and
air-quality are working scaffolds on the same architecture. Six city
deployments ship today: NYC, Chicago, Seattle, San Francisco, Boston,
Albany — same code, different manifests. It is explicitly not a stamped
engineering memo, a risk score, or a real-estate disclosure, and it is
independent open-source software, not affiliated with any government
agency, even though it reads FEMA/NOAA/USGS/city open data.

## Who reads it

Civic engineers, urban planners, NGOs, and government-office analysts —
someone doing a drainage review, a resilience office siting a capital
project, a grant writer citing evidence in a FEMA BRIC sub-application, a
journalist who needs a defensible number with a source. Not a consumer
shopping for flood insurance. The reader already trusts (or is skeptical
of, professionally) government cartography and technical reports; they are
not the audience a consumer app's visual language is built for.

## Two ways the design gets read

1. **On screen**, as a live web page (SvelteKit): the briefing paragraph,
   a MapLibre map with layered hazard extents, evidence cards grouped by
   the "Five Stones" taxonomy (Cornerstone/hazard-memory, Touchstone/live,
   Lodestone/forecast, Keystone/assets, Capstone/synthesis), a register
   browser for bulk asset lists.
2. **On paper**, as a generated PDF (WeasyPrint, server-side, already
   working — `app/print_pdf.py`): a two-page-minimum document — cover page
   with title/scope/disclaimer, briefing body, grouped citations, a stamp
   page with a SHA-256 document hash two reviewers can compare bit-for-bit.
   Print is not a stretch goal or an afterthought; it already exists and is
   part of what "real print reports" means here — the design work should
   make it better (a static map render is a known gap — see the `Future`
   note at the top of `app/print_pdf.py`), not invent it from zero.

`reference/riprap-print-pdf-current.css` is the actual currently-shipping
print stylesheet. `reference/screenshots/hero-current.png` is the actual
currently-shipping web view (a real briefing for DUMBO, Brooklyn).
`reference/riprap-tokens-current.css` is the actual currently-shipping
design-token file. Read these before designing anything — they are ground
truth, not a mood board.

## What already exists and works (do not treat as a blank slate)

- **IBM Plex Sans / Serif / Mono**, vendored via `@fontsource`,
  Apache-2.0/SIL-OFL licensed, used throughout. Sans for UI chrome, Serif
  for the briefing prose (a report reads as a report, not a dashboard),
  Mono for metadata/citations/technical labels. There is no stated reason
  to replace this; if the design session concludes IBM Plex is wrong for
  this surface, that conclusion needs its own argument, not a default
  swap.
- **The dam mark** (`reference/logo-dam-mark.svg`): a geometric riprap/dam
  icon, `fill=currentColor` so it inherits color from context, CC-BY 3.0
  original by Chintuza (Noun Project), attribution now carried in body
  copy rather than embedded in the SVG. This is Riprap's actual identity
  mark — a name pun (riprap = the loose rock armor that protects a
  shoreline from erosion) rendered as a stylized dam cross-section.
- **A four-tier evidence system**: empirical (directly measured/observed)
  / modeled (a scenario simulation) / proxy (an indirect indicator) /
  synthetic (a foundation-model-derived signal). This is Riprap's central
  epistemic claim — every fact in a briefing is labeled by how directly it
  is known, not just what it says. It is currently color-only
  (`--tier-empirical` etc. in `reference/riprap-tokens-current.css`), which
  is a real accessibility gap: WCAG 1.4.1 requires color not be the sole
  carrier of meaning, and grayscale-only reproduction (print, photocopy,
  some colorblind modes) currently loses this distinction entirely.
  Whatever visual system the design session builds must encode this
  epistemic tier through more than hue alone.
- **The tier 1-4 exposure-severity rubric** (`app/score.py`): a
  deterministic scoring model, published and cited (`docs/METHODOLOGY.md`
  in the host repo), currently used only by the offline bulk register
  builders (`/register/{schools,nycha,mta_entrances}`), not the live
  single-query briefing. This is a genuinely separate axis from the
  evidence tier above — "how directly do we know this" is not the same
  question as "how severe is this" — and today nothing in the live UI
  renders severity as its own mark. Whether and how to surface it is a
  real open design question, not a settled fact to design around.
- **WCAG 2.2 AA + Section 508** compliance is an existing, stated
  commitment (landing page badges, `docs/ARCHITECTURE.md`), not a nice-to-
  have. A known live bug: `--ink-tertiary` (#64748B) in the current token
  file computes to 4.4:1 against `--paper` and 4.01:1 against
  `--paper-deep` — both below the 4.5:1 AA body-text minimum, despite a
  code comment claiming 4.7:1. Verified independently with the WCAG 2.x
  relative-luminance formula (`gates/lib/color.mjs` reproduces the same
  number). Whatever the new tertiary-text color is, it needs to actually
  clear 4.5:1 against every surface it is used on, measured, not asserted.
- **`--tier-empirical` (#005EA2) and `--tier-modeled` (#1A4480) already
  exactly match USWDS's own `blue-60v` and `blue-warm-70v` tokens** (US Web
  Design System, the federal design-system baseline) — confirmed against
  designsystem.digital.gov, not a coincidence claim. This is a real,
  testable asset: Riprap is already precisely on-convention with the
  government design system a civic-engineer reader has likely encountered
  before, in at least this one respect.
- **A structural-chrome layer already uses `@nysds/components`** (New York
  State's official open-source design system) for the site's skip-nav and
  a row of city-picker buttons on the landing page — narrowly scoped
  because most of NYSDS's header/footer components assert NY State agency
  branding Riprap does not have. This is unrelated to the report-content
  design work here (evidence marks, citations, print layout) and does not
  need to change; see `reference/riprap-tokens-current.css`'s
  `--nys-color-theme*` block for how that integration already points at
  Riprap's own accent color rather than a separate palette.

## Constraints that are not optional

- WCAG 2.2 AA minimum, ideally AAA where cheap. Every contrast claim must
  be a measured number, not an assertion.
- Print output via WeasyPrint (a real, deployed rendering engine with its
  own CSS-support limits — confirm custom-property/`var()` support in the
  pinned WeasyPrint version before assuming it works the same as browser
  CSS).
- No third-party font or asset CDN calls — Riprap runs partly offline-
  capable / self-hosted deployments; everything must be vendorable.
- The report must never visually imply government affiliation Riprap does
  not have (see `docs/ARCHITECTURE.md`'s and the landing page's existing
  "Independent open-source project. Not affiliated with FEMA, NOAA, USGS,
  or any city government" disclosure — the visual design should not
  undercut that in the other direction, e.g. by borrowing an official
  seal-like treatment).
- A section is omitted, never fabricated, when no data fired for it
  (Riprap's "silence over confabulation" contract). The design should make
  an omitted section read as intentional and honest, not like a broken
  layout with a hole in it.
