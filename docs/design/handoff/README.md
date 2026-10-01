# Riprap design handoff — research + gates, not a finished system

> **Historical, September 2026.** This is the brief a design pass started
> from. The tokens, gates and reference files here are still the source of
> the visual identity. The product it describes has since changed: the
> server-side PDF export, the exposure score (`app/score.py`), the heat and
> air scaffolds and the San Francisco and Boston deployments were removed
> in October 2026, so the tasks in the prompt files that name them no
> longer apply.

This package is a **brief**, not a delivered design. It hands a future
design session (Claude or otherwise) two research threads, Riprap's real
current state, a fixed accessibility floor, and working-but-empty
verification tooling — and leaves the actual palette, component
aesthetic, and information-design decisions to that session, done from
first principles. Nothing in `tokens/` or `css/` is pre-filled with a
color or a component treatment; that is deliberate, not incomplete.

Start with `CLAUDE-DESIGN-PROMPT.md`.

## Manifest

```
CLAUDE-DESIGN-PROMPT.md   The actual design brief. Start here.
BRIEF.md                  Riprap: what it is, who reads it, what already
                           exists (assets, bugs, constraints) — read before
                           CLAUDE-DESIGN-PROMPT.md's task list will make sense.
RESEARCH.md                Calm Technology's 8 principles + FEMA/NWS/USWDS/
                           USGS/IPCC/ASTM civic-cartographic precedent,
                           each with a stated "so what," not a conclusion.
reference/                 Riprap's ACTUAL current state — not a proposal.
  riprap-tokens-current.css    The live token file (web/sveltekit).
  riprap-print-pdf-current.css The live WeasyPrint print stylesheet.
  logo-dam-mark.svg             The actual identity mark.
  screenshots/hero-current.png  A real briefing, as currently shipped.
gates/                      Deterministic verification tooling. Runs today,
                           with nothing designed yet — try `node gates/
                           verify.mjs`. WCAG math is fixed (law); role
                           lists are empty CONFIGURE blocks (your job).
  README.md                 How to use these once you have a token file.
  lib/color.mjs                WCAG contrast + Rec.601 grayscale math.
  lib/tokens.mjs                CSS custom-property parser (prefix-agnostic).
  contrast-gate.mjs, grayscale-gate.mjs, rules-lint.mjs, drift-gate.mjs
    Zero-dependency. Run with plain `node`.
  behavioral-gate.mjs        Needs playwright + @axe-core/playwright.
  verify.mjs                 Runs the four zero-dependency gates in order.
```

## Where this format came from

The tokens → gates → proof/specimens → docs → implementation-prompt shape
is borrowed from an earlier design handoff the owner wrote for an
unrelated product: the best structure found for a handoff that has to
survive contact with a different team and a different codebase later.
Only the *shape* is reused. That system's palette, radius policy and
component decisions were made for a different reader and medium and are
not referenced or copied here.

An earlier, more opinionated draft of this handoff (internally called
"Datum") was produced and then deliberately not shipped here: it made
real palette and component decisions on its own, which is exactly the
work this package intends to leave to a proper first-principles design
session instead of pre-deciding. What survived from that draft into this
one: the verified WCAG math in `gates/lib/`, the CSS parsing utility in
`gates/lib/tokens.mjs`, and one confirmed real bug in Riprap's *existing*
shipped code — `--ink-tertiary` fails WCAG AA contrast on one of its two
current surfaces (see `BRIEF.md`) — worth fixing in
`web/sveltekit/src/lib/tokens.css` regardless of when or whether this
broader design work ships.

## Running the (currently empty) gates

```
cd gates
node verify.mjs
```

Every gate exits 0 right now with a "this is a template" message. That's
the correct starting state — see `gates/README.md`.
