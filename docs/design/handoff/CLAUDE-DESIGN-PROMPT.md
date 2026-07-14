# Design Riprap's report-content visual system

You are doing original design work, not implementing a spec someone else
already wrote. This handoff gives you research and constraints, not a
finished palette or component set — that is deliberate. Do not reuse a
color palette, radius policy, or component aesthetic from any other
design system you have seen (including any prior draft of this handoff
you may find referenced in this repo's history) without re-deriving it
from the material below. If you find yourself picking a hex because it
"seems right," stop and connect it back to one of the research findings
or a measured constraint instead.

## Read first, in order

1. `BRIEF.md` — what Riprap is, who reads it, what already exists and
   works (do not treat this as a blank slate — some of it is a real
   asset, some of it has a real bug, both are stated plainly).
2. `RESEARCH.md` — Calm Technology's eight principles read as a reading-
   surface budget, plus FEMA/NWS/USWDS/USGS/IPCC/ASTM civic-cartographic
   and report-design precedent, each with a stated "so what."
3. `reference/` — the actual currently-shipping token file, print CSS,
   logo, and a screenshot of a real briefing. Ground truth, not mood
   board.

## The four framings, and how they should pull against each other

The task is not "average these four things into one look." Each names a
real tension worth resolving deliberately:

- **Civic tech**: built for a specific institutional user with a job to
  do (a planner, an engineer, a grant writer), not a general public
  audience being persuaded or entertained. Optimize for a returning user
  who scans quickly, not a first-time visitor who needs onboarding.
- **Civil engineering artifact**: the visual register of a stamped
  drawing, a survey, a geotechnical report — dated, sourced, versioned,
  reviewable by a second engineer. Numbered sections, explicit units,
  explicit uncertainty. This pulls toward density and precision.
- **Calm technology**: pulls the other way — minimum necessary attention,
  periphery for metadata, one motion budget, no decoration competing with
  content. The tension between "civil engineering artifact" (wants
  completeness) and "calm technology" (wants restraint) is the actual
  design problem; resolve it, don't split the difference by halfway
  measures on both.
- **Scientific report**: citation apparatus as load-bearing, not
  decorative (IPCC's finding: authoritative ≠ dense — salience over
  density). A claim without a citation should look visibly incomplete;
  the citation mark should be findable without shouting.

## What you're actually designing

A token system and a small component vocabulary for **report content** —
not Riprap's structural site chrome (header, footer, skip-nav, generic
buttons), which already exists and is out of scope here (see BRIEF.md).
Concretely, at minimum:

- **Text and surface tokens** for both on-screen and print rendering,
  meeting WCAG 2.2 AA (4.5:1 body text, 3:1 graphical/UI) — measured
  against `gates/contrast-gate.mjs`, not asserted.
- **The evidence-tier mark** (empirical/modeled/proxy/synthetic — Riprap's
  existing epistemic axis, currently color-only and therefore currently
  failing WCAG 1.4.1 in grayscale/print reproduction). Fix this: the
  distinction must survive desaturation, not just differ in hue.
- **A decision on severity/hazard as a second axis.** Riprap's tier
  rubric (`app/score.py`) computes exposure severity but nothing in the
  live UI renders it as its own mark today (BRIEF.md). Decide, and state
  your reasoning, whether report content needs a visually distinct
  severity mark alongside evidence-tier, or whether that's a real but
  separate product decision to flag rather than build speculatively. If
  you do design one, keep it visually and conceptually distinct from
  evidence-tier — "how do we know this" and "how bad is this" are
  different questions and should never collapse into one mark answering
  both.
- **Citation marks** (`[doc_id]` tags that already follow every numeric
  claim in a briefing) — periphery-not-decoration, per Calm Technology
  principle 3 and the IPCC finding above.
- **A print grammar**: page geometry, running header/footer, a cover page
  and a stamp/verification page, grounded in `app/print_pdf.py`'s actual
  current implementation (`reference/riprap-print-pdf-current.css`) — not
  reinvented from zero. Confirm WeasyPrint's actual `var()`/custom-
  property support for the pinned version before assuming browser-CSS
  parity.
- **A register/table treatment** for the bulk asset-list surfaces
  (`/register/*`), since these are the highest-density, most report-like
  screens in the product today.

Typography: IBM Plex Sans/Serif/Mono is already vendored, licensed, and
in use (BRIEF.md). Keep it unless you have a specific, stated reason not
to — a font swap is a bigger, separately-justified decision, not a
default move.

## How to verify what you build

`gates/` ships five scripts — `contrast-gate.mjs`, `grayscale-gate.mjs`,
`rules-lint.mjs`, `drift-gate.mjs`, `behavioral-gate.mjs` — plus a
`verify.mjs` orchestrator. Right now every one of them runs and exits 0
with a "this is a template" message; try `node gates/verify.mjs` before
you start, so you've seen the baseline. The WCAG math inside them (fixed
thresholds, fixed formulas) is verified correct — see `gates/README.md`.
Everything else in them is a labeled `CONFIGURE` block, empty until you
fill it in with your own token/role names.

As you design:

1. Write `tokens/tokens.dtcg.json` (W3C Design Tokens Community Group
   format — see the sibling Hanji design system in `~/calluna-meta` for
   an example of the three-layer primitive/semantic/purpose shape, if
   useful as a structural reference; its actual token *values* are not
   relevant to Riprap and should not be copied) and a built
   `tokens/tokens.css`.
2. Hand-type `tokens/reference.css` as your own verified source of truth
   — the drift gate's job is to catch the built CSS silently diverging
   from what you actually decided.
3. Fill in each gate's `CONFIGURE` block with your real token names.
4. Run `node gates/verify.mjs`. Green means your own stated decisions are
   internally consistent and meet the fixed accessibility floor — it does
   not mean the design is good, only that it isn't quietly broken.
5. Build `specimens/` (components at at least two viewport widths) and
   `proof/` (a page that computes and displays contrast ratios live from
   your shipped hexes, the same way the gate does) so the numbers in any
   documentation you write are the same numbers a machine actually
   computed, not hand-typed.
6. Write your own `PRINCIPLES.md`: one numbered rule per real design
   decision, each naming which gate (if any) enforces it, in the style
   `gates/README.md` and this file model. A decision with no gate and no
   stated reason it can't have one is worth a second look, not
   necessarily wrong.

## Definition of done

- Every text/graphical role passes `gates/contrast-gate.mjs` and
  `gates/grayscale-gate.mjs` in every ground you ship.
- The evidence-tier distinction is legible without color (shape, border
  style, pattern, or label — not hue alone).
- `docs/PRINT-GRAMMAR.md` (or your equivalent) is grounded in
  `app/print_pdf.py`'s actual current CSS, with each substitution stated
  explicitly, and the WeasyPrint custom-property caveat resolved one way
  or the other (confirmed working, or a documented fallback).
- A `RIPRAP-MAPPING.md` (or your equivalent) states, token by token and
  component by component, how this maps onto Riprap's actual current code
  (`reference/riprap-tokens-current.css` and the host repo) — and lists
  what's genuinely new/open rather than improvising past a gap.
- Every claim about a number (a contrast ratio, a hex value) traces back
  to something a gate or `proof/` page actually computed.
- You've stated, in your own words, how you resolved the civic-artifact-
  vs-calm-technology tension — not just that you were aware of it.
