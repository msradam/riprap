---
name: Riprap
description: Cited flood-exposure briefings for New York City places and questions.
colors:
  blue-60v: "#005EA2"
  blue-warm-70v: "#1A4480"
  blue-warm-80v: "#162E51"
  cyan-700: "#0E7490"
  amber-800: "#92400E"
  red-700: "#B91C1C"
  green-800: "#166534"
  slate-950: "#0F172A"
  slate-700: "#334155"
  slate-600: "#475569"
  slate-tertiary: "#4E5A6E"
  slate-300: "#CBD5E1"
  slate-250: "#DCE2EA"
  paper: "#F4F6F9"
  paper-sunken: "#E8ECF2"
  paper-inset: "#EEF1F5"
  mist: "#C9D2DD"
  sky-100: "#E3ECF2"
  white: "#FFFFFF"
typography:
  display:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "36px"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.25
  body:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Overpass Mono, ui-monospace, monospace"
    fontSize: "11px"
    fontWeight: 500
    letterSpacing: "0.08em"
  data:
    fontFamily: "Overpass Mono, ui-monospace, monospace"
    fontSize: "13px"
    fontWeight: 400
rounded:
  hairline: "1px"
  badge: "3px"
spacing:
  s-1: "4px"
  s-2: "8px"
  s-3: "12px"
  s-4: "16px"
  s-5: "24px"
  s-6: "32px"
  s-7: "48px"
  s-8: "64px"
  s-9: "96px"
components:
  inline-cite:
    textColor: "{colors.blue-60v}"
    typography: "{typography.data}"
  exp-badge:
    textColor: "{colors.slate-700}"
    typography: "{typography.label}"
    rounded: "{rounded.badge}"
    padding: "0 5px"
  citation-item:
    backgroundColor: "{colors.white}"
    textColor: "{colors.slate-700}"
    padding: "10px 12px"
  page:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.slate-950}"
---

# Design System: Riprap

<!-- Documented from the incumbent code (web/sveltekit/src/lib/tokens.css,
     styles.css) and the handoff tokens (docs/design/handoff/tokens/) during
     the Impeccable pass, 2026-09-27. Type, logo and palette are PINNED by
     the owner: change sizes, weights, spacing and use; never the families,
     the mark or the hue families. -->

## Overview

**Creative North Star: "The Survey Sheet"** (inferred; the owner has not
named one)

Riprap reads like a public-works survey sheet brought to a desk: cool paper,
navy ink, drafting labels in a highway-signage mono, and a federal blue that
marks what can be checked. It is an engineering artefact, not a dashboard or
a consumer app. Density is moderate and calm: the briefing text leads, the
map and citations sit at its side, and colour is spent on meaning (the link
to a source, an evidence tier, an alert), not on decoration.

The palette is USWDS-aligned on purpose: the empirical and modelled tier
blues are exactly USWDS `blue-60v` and `blue-warm-70v`, which a civic reader
has met before. Depth comes from tonal layering of paper surfaces and
hairline rules, not shadows.

**Key Characteristics:**
- Cool paper surfaces in three tones, navy text, one federal-blue accent.
- Sofia Sans for everything a person reads; Overpass Mono for data, labels
  and citation marks.
- Evidence tier carried by a square's fill (solid, hatched, hollow,
  stippled), hue as reinforcement only.
- Flat, hairline-ruled, square-cornered.

## Colors

A cool, low-chroma civic palette: slates and papers carry the page, the
blues carry evidence and links, amber and red are reserved for signal.

### Primary
- **Federal Blue** (blue-60v): links, inline citation marks, focus rings,
  the empirical evidence tier. The colour of "you can check this".
- **Warm Navy** (blue-warm-70v): modelled and synthetic evidence tiers, the
  Keystone stone.
- **Deep Navy** (blue-warm-80v): the Capstone stone.

### Secondary
- **Survey Cyan** (cyan-700): the Touchstone (live signals) stone hint.

### Tertiary (signal only)
- **Hazard Amber** (amber-800): warnings, severity 2 and 3, the Lodestone
  stone hint.
- **Alert Red** (red-700): active flood alerts and severity 4 only.
- **Done Green** (green-800): success and completed steps, always with a
  check or text.

### Neutral
- **Ink** (slate-950): primary text and strong rules.
- **Secondary Ink** (slate-700): secondary text.
- **Tertiary Ink** (slate-tertiary): metadata; replaces the old #64748B,
  which failed AA on the sunken surface.
- **Proxy Slate** (slate-600): proxy tier, severity 1, Cornerstone stone.
- **Soft Rule** (slate-300) and **Hairline** (slate-250): decorative
  dividers.
- **Paper** (paper), **Sunken Paper** (paper-sunken), **Inset Paper**
  (paper-inset), **Card White** (white): the four surfaces.
- **Mist** (mist): the app desk backdrop. **Sky** (sky-100): basemap water.

### Named Rules
**The Checkable Blue Rule.** Federal Blue means a source or a control you
can act on. Do not use it for decoration or headings.

**The Signal Budget Rule.** Amber and red appear only for hazard signal
(warnings, alerts, severity). A calm briefing has none.

**The Pinned Palette Rule.** No new hue family. Rebalance use and fix
contrast within these tokens.

## Typography

**Display and Body Font:** Sofia Sans (system-ui fallback)
**Label/Mono Font:** Overpass Mono (ui-monospace fallback)

**Character:** a Gotham-lineage civic grotesque for reading, paired with a
mono drawn from the US highway signage alphabet for data, coordinates and
citation marks. Both are OFL and self-hosted through @fontsource. PINNED.

### Hierarchy
- **Display** (600, 36px, 1.15): the briefing place or question heading.
- **Headline** (600, 22px, 1.25): region and section headings.
- **Body** (400, 16px, 1.55, 70ch measure): briefing prose and answers.
- **Data** (Overpass Mono 400, 13px): citation lines, figures, metadata.
- **Label** (Overpass Mono 500, 11px, 0.08em, uppercase): section labels,
  badges.

### Named Rules
**The Mono Means Data Rule.** Overpass Mono is for figures, identifiers,
labels and citation marks; reading text is Sofia Sans.

**The Twelve Pixel Floor Rule.** Text a reader must read is at least 12px.
The incumbent code breaks this (9, 10 and 10.5px labels); treat those as
defects, not precedent.

## Layout

A desk-and-sheet model: a mist backdrop, a paper briefing band with a
1600px maximum width and 28px side padding on desktop, and a three-region
shell (briefing, map, citations) that stacks on narrow screens. Spacing
follows a 4px base scale (4, 8, 12, 16, 24, 32, 48, 64, 96). Prose holds a
70ch measure.

## Elevation & Depth

Flat. Depth is tonal (paper, sunken, inset, card) and ruled (hairlines and
a strong ink rule), never shadowed.

### Named Rules
**The No-Elevation Rule.** No box shadows on report content; the handoff's
rules lint enforces it.

## Shapes

Square and drafted: corners are square or a 1px hairline radius; badges
take a 3px radius. Evidence tier is a small square mark; severity is a
filled-step triangle, a different shape so the two axes never merge.

## Components

### Inline citation
- **Style:** Overpass Mono 500, Federal Blue, superscript `[n]`, no
  underline; an accessible name naming the source.
- **Behaviour:** activates the matching entry in the citations list and
  scrolls it into view. Inline, so it keeps the WCAG 2.5.8 inline target
  exception.

### Citation list item
- **Style:** a 32px number column and body, 10px 12px padding, a 2px soft
  left rule that turns active on selection; source, experimental badge and
  vintage on the first line, title as a link, metadata in mono.

### Experimental badge
- **Style:** Overpass Mono 10px uppercase, secondary ink, a 1px soft rule
  border, 3px radius. Marks sources without an evaluation behind them.

### Evidence-tier mark
- **Style:** a small square whose fill encodes the tier (solid empirical,
  hatched modelled, hollow proxy, stippled synthetic); hue reinforces.

### Logo
- **The dam mark**, `fill=currentColor`, PINNED. Never recoloured into a
  seal-like or official-looking treatment.

## Do's and Don'ts

### Do:
- **Do** keep every numeric claim next to its citation mark.
- **Do** carry evidence tier and severity by shape as well as colour.
- **Do** measure contrast with the handoff gates (`node
  docs/design/handoff/gates/verify.mjs`).
- **Do** make an omitted section read as intentional, not broken.

### Don't:
- **Don't** add or swap a typeface, recolour the dam mark, or introduce a
  hue family.
- **Don't** rename the Five Stones; add plain-language subtitles instead.
- **Don't** use shadows or rounded card chrome on report content.
- **Don't** borrow seal-like or agency-branded treatments; Riprap is
  independent.
