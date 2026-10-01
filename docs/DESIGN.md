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
  lead:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "64px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1.18
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.25
  answer:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.55
  small:
    fontFamily: "Sofia Sans, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
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
    typography: "{typography.small}"
    rounded: "{rounded.badge}"
    padding: "0 5px"
  answer-lead:
    textColor: "{colors.slate-950}"
    typography: "{typography.lead}"
  source-note:
    textColor: "{colors.slate-700}"
    typography: "{typography.small}"
  evidence-row:
    textColor: "{colors.slate-950}"
    typography: "{typography.small}"
    padding: "10px 0"
  page:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.slate-950}"
---

# Design System: Riprap

<!-- Documented from the incumbent code during the first Impeccable pass
     (2026-09-27) and rewritten for pass 2 (2026-09-29) after the owner's
     init interview and the three-direction lab. Type families, the dam mark,
     the palette and the Five Stones names are PINNED: change sizes, weights,
     spacing and use; never the families, the mark or the hue families. The
     owner delegated the element choices to the design session; they are
     recorded here as that session's choices. -->

## Overview

**Creative North Star: "The Survey Sheet", set as a public report.**

A Riprap briefing reads like a carefully typeset public report on cool
survey paper. The question is the title. The answer comes next, in the
reader's language, with its sources beside it. The evidence follows as an
exhibit table, the map is a figure, and how the briefing was made is
recorded once, at the end. It is not a dashboard, a trace viewer or a
consumer app. Colour is spent on meaning (the link to a source, an evidence
tier, an alert), never on decoration.

The palette is USWDS-aligned on purpose: the empirical and modelled tier
blues are USWDS `blue-60v` and `blue-warm-70v`, which a civic reader has met
before. Depth comes from paper tones and a few hairlines, not shadows.

**Key characteristics:**
- The answer is the strongest type on the page.
- Sofia Sans for everything a person reads; Overpass Mono only for figures,
  identifiers and dates.
- Evidence tier is carried by a square's fill (solid, hatched, hollow,
  stippled) in tables, keys and the map, and by words in source notes;
  never by a mark on every sentence.
- Flat and square-cornered, with hairlines only where they separate rows.

## Colors

A cool, low-chroma civic palette: slates and papers carry the page, the
blues carry evidence and links, amber and red are reserved for signal.

### Primary
- **Federal Blue** (blue-60v): links, citation marks, focus rings, the
  empirical tier. The colour of "you can check this".
- **Warm Navy** (blue-warm-70v): modelled and synthetic tiers, the Keystone
  stone.
- **Deep Navy** (blue-warm-80v): the Capstone stone.

### Secondary
- **Survey Cyan** (cyan-700): the Touchstone (live signals) stone hint.

### Tertiary (signal only)
- **Hazard Amber** (amber-800): warnings and the Lodestone stone hint.
- **Alert Red** (red-700): active flood alerts only.
- **Done Green** (green-800): success and completed steps, always with text.

### Neutral
- **Ink** (slate-950): primary text, the answer, headings.
- **Secondary Ink** (slate-700): meta lines, source notes, captions.
- **Tertiary Ink** (slate-tertiary): the least important metadata.
- **Proxy Slate** (slate-600): proxy tier, Cornerstone stone.
- **Soft Rule** (slate-300) and **Hairline** (slate-250): row separators
  and the one input border.
- **Paper**, **Sunken Paper**, **Inset Paper**, **Card White**: the
  surfaces. **Mist**: the app desk backdrop. **Sky**: basemap water, and
  the landing's question chips.

### Named Rules
**The Checkable Blue Rule.** Federal Blue means a source or a control you
can act on. Never headings, never headlines, never decoration.

**The Signal Budget Rule.** Amber and red appear only for hazard signal. A
calm briefing has none.

**The Pinned Palette Rule.** No new hue family.

## Typography

**Reading font:** Sofia Sans. **Data font:** Overpass Mono. Both OFL and
self-hosted. PINNED. There is no italic in report content.

### Scale
| Role | Font | Size / weight / leading | Use |
|---|---|---|---|
| Lead | Sofia Sans | 64 / 700 / 1.0 (44 on phones) | "Yes.", "No.", a count, or the sentence saying the sources do not answer |
| Title | Sofia Sans | 34 / 600 / 1.18 (26 on phones), max 30ch | The H1: the question, or the place |
| Headline | Sofia Sans | 22 / 600 / 1.25 | h2: Evidence, Map, Sources and method, report sections |
| Brief | Sofia Sans | 24 / 400 / 1.4 (21 on phones), first sentence 600 | The "In brief" paragraph of an address or district briefing, and nothing else |
| Answer | Sofia Sans | 20 / 400 / 1.5, max 64ch | The answer to a question; with a lead fact, its key sentence only, the rest of the answer in Body |
| Body | Sofia Sans | 17 / 400 / 1.55, max 68ch | Report sections |
| Small | Sofia Sans | 14 to 15 / 400 / 1.45 | Meta line, source notes, table cells, captions, method block |
| Data | Overpass Mono | 13 to 14 / 400, tabular figures | Figures, dates, doc ids, citation numbers, the commit |

### Named Rules
**The Mono Means Data Rule.** Overpass Mono is for figures, identifiers,
dates and citation numbers. It is never a label voice: no uppercase tracked
mono eyebrows above blocks.

**The Twelve Pixel Floor Rule.** Nothing a reader must read is under 12px.
Third-party map controls are restyled to meet it.

**The Measure Rule.** Prose lines stay at 75 characters or fewer.

**The One Heading Style Rule.** Every h2 on a page uses one style: Headline,
or Title on the landing; sections are numbered in one sequence or not at all.

## Layout

Spacing follows the 4px scale (4, 8, 12, 16, 24, 32, 48, 64, 96).

### Question briefing
A single text column (about 680px) with a margin rail (about 280px) at
1100px and wider. From the top: the kind line, the title, the meta line,
the jump links, the lead and the answer with its source notes in the rail,
a pointer for residents, Figure 1 (the map), the evidence table, report
sections if any, then Sources and method. The lead word sits above y=260 at
1440 and the whole answer is on the first screen.

### Address and district briefings
The question page's frame (about 1008px) and title. At 1100px and wider the
page below the title is one two-column grid: the main column (about 58%)
holds the "In brief" paragraph in the Brief style, then the evidence table
directly under it, then the report sections in one closed disclosure, "The
written briefing, section by section", since they restate the table; the
right column (about 42%) holds the source notes, the checks-ran and mode
lines, the terms, the scope note and the resident pointer, then the map,
sticky, 460px tall, beside the table. Neither column leaves an empty
quadrant at the top. Below 1100px everything is one column: the summary,
the evidence table and the written sections, then the endnotes, the terms,
the scope note and the map at 300px, so the evidence comes before the
apparatus on a phone. The map attribution starts folded into its (i) control.

### Phone (390)
One column, 16px gutters, no horizontal scroll. Source notes become
endnotes directly after the answer. Table rows become stacked blocks.

## Elevation & Depth

Flat. Depth is tonal and ruled, never shadowed.

**The Border Budget Rule.** Borders exist only to separate table rows, to
frame the map and the query input, and to draw focus. No card borders, no
side stripes, no boxes around blocks of text.

## Components

### Kind line and meta line
- **Kind line:** Small, secondary ink, plain words ("Flood-exposure
  briefing, question").
- **Meta line:** Small, secondary ink, one line under the title: the place
  (on question briefings), "Snapshot" with the date in Data, and the link
  "How this briefing was made". Items are separated by space, not dots.

### Answer block
- **Lead:** the Lead style in Ink, on its own line.
- **Answer:** the Answer style in Ink. A count lead keeps its sentence
  intact below it. When the result names a lead fact (`grounding.lead_fact`),
  the key sentence comes first in Answer and the rest of the answer follows
  as its own paragraph in Body, as support. The key sentence is the
  backend's lead sentence when `in_lead` is true, else the first answer
  sentence citing `lead_fact.doc_id`. Without a lead fact no sentence is
  singled out. An experimental source is never the key sentence: its
  paragraph comes after the others and opens with the Experimental badge.
- **Citations:** a small superscript number in Federal Blue after the
  sentence's closing punctuation, never before it. No tier mark in prose.
  Numbers follow first appearance on the page (the answer or In brief, the
  evidence table, the report sections), the same number in the margin
  notes, the Cite column, the source list and the print packet. Several
  marks on one claim read in ascending order. Anchors keep the doc id.
- **Below it:** the scope disclosure and the resident pointer.
- **Refusal:** a refusal's lead is set at 44px (32px on phones), smaller
  than an answer's 64px, on purpose: a refusal is not an answer and must not
  look like one.
- **In the margin:** the checks-ran line and the mode line in Small
  secondary ink, under the source notes (after the endnotes below 1100px).
  Machinery never sits directly under the answer.

### Source note (margin rail, endnote on phones)
Number in Data, then the source name as the link (Small, 600, underline on
hover and focus only), then one line: the tier in words (Measured, Modeled,
Proxy, Synthetic), the Experimental badge where it applies, and "data as of"
with the date in Data. The long source description and doc id live only in
the full source list.

### Evidence table
- **Columns:** Source, Finding, Figure (Data, right aligned), Tier (the
  tier square and the word), Data as of (Data), Cite (the number).
- **Finding:** the finding sentence first in 600 ("This address is outside
  the 2012 Sandy extent"), the dataset name after it in secondary ink. A
  dataset name is never set as if it were the result.
- **Order:** a first group "Behind the answer" holds the rows the answer
  cites, experimental or not; then one group per Stone, headed with the
  Stone name and its role ("Cornerstone, the hazard reader"); then the
  experimental and forecast sources the answer does not cite, in one closed
  disclosure after the table titled with its count ("Experimental and
  forecast sources (4)"), each row keeping its Experimental badge. NPCC4 and
  the NWS alerts are not experimental. Sources that did not run are listed
  once, under Sources and method; one line after the table links there.
- **DEP scenarios:** the DEP stormwater scenarios share one Modeled row: one
  finding per scenario (current, 2050, 2080), each with its own citation,
  and its own date only when the dates differ.
- **Figure:** a label of about 16 characters or fewer sits under the
  figure; a longer one moves to the finding's secondary line. A live
  reading on a gallery page is dated "at snapshot, <date>".
- **Rows:** 10px vertical padding, a Hairline between rows, no zebra, no
  cell borders.

### Map figure
- **Question briefings:** Figure 1 at the text column width, 360px tall,
  with a caption line under the frame.
- **Place briefings:** sticky in the right column.
- **Layer switches:** checkboxes labelled in words with counts ("Measured
  (empirical), 12"). Never "EMP ON".
- **Always:** the keyboard list "Map points as a list" and a "Skip the map"
  link.

### How this briefing was made
One closed disclosure at the end: the checks, the mode line, the models
(name, where it ran, how, latency), the trace, the model id once, the
commit and snapshot time, and the disclaimer once.

### Jump links
One row under the meta line: Answer, Evidence, Map, Sources. Plain links
in Small. An action such as "Print this briefing" sits at the row's right
end, apart from the jumps; "All gallery entries" is a plain link at the
end of the page.

### Header and footer
One header and one footer on every page except print. The header carries
the wordmark (linked home), the context words, the active deployment when
one is known, and the links "methodology" and "gallery"; the query box and
the print link appears only on a live briefing. The footer
carries the disclaimer, the open beta sentence with its feedback link, the
standards line, the build line and the dam mark credit. A page that already
states the disclaimer (a briefing's scope note, the landing's "evidence, not
advice" section) drops it from the footer, so it appears once per page.

### Empty search
An empty or blank submit keeps the page, moves focus to the input and shows
"Type an address, a community district such as QN12, or a question." under
it in Small, in ink, in a status region. It is a prompt, not an error: no
red, no disabled button, no browser bubble. Typing clears it.

### Experimental badge
Small, secondary ink, a 1px Soft Rule border, 3px radius, sentence case.

### Evidence-tier mark
A small square whose fill encodes the tier; used in the evidence table, the
map legend and the tier key only.

### Landing
A Persuade page inside the report system. The hero pairs the h1 (52px, 34px
on phones), one subhead and the query box (or, on the static site, "Browse
briefings" and "Run it yourself") with a real gallery answer set as a
specimen: the question, the lead word at Lead size, the key sentence and
its source notes. Real questions follow as chips. Proof comes next, as
gallery answers on Card White cards with no border: one wide district card
with its figure, then question cards with a verbatim quote. Then the
sources by Stone (`#methodology`), who it is for, developers and MCP, the
experimental models, how to collaborate, and one "evidence, not advice"
line with the official sources. Section headings use the Title scale. Tonal
bands of Sunken Paper and one Ink code block give rhythm. There are no
shadows, borders, stat rows or numbered cards. Cards and Title-scale
section headings are for the landing only; briefing, gallery and print
pages keep the report style. Community districts are written QN12, with no
space, in copy, examples and placeholders.

### Gallery index
The typographic list stays: place over question, snapshot date in Data,
plus each entry's lead or first answer sentence in Small. Each entry may
carry a one-line reason (why it is in the gallery) under its title, and an
address entry may name a featured source whose sentence is its snippet, so
ten addresses never read as one template.

### Frozen readings
On a gallery snapshot, forecasts say "Forecast made at the snapshot, <date>
<time> UTC." and an active alert says "Active at the snapshot, ..."; live
times are written in UTC. The Figure column never shows a temperature.

### Print
A's report structure: page one carries the title, the meta line, the answer
and its source notes; the evidence table and source lists start on page
two. A print from a gallery snapshot dates live readings "at snapshot,
<date>"; only a live run prints "live". The folded experimental group
prints open.

### Logo
**The dam mark**, `fill=currentColor`, PINNED. Never recoloured into a
seal-like or official-looking treatment.

## Do's and Don'ts

### Do:
- **Do** keep every numeric claim next to its citation number.
- **Do** carry evidence tier by shape and words as well as colour.
- **Do** give a plain reading where a technical term appears (NAVD88 is an
  elevation above a survey datum, not a depth).
- **Do** measure contrast with the handoff gates (`node
  docs/design/handoff/gates/verify.mjs`).

### Don't:
- **Don't** add or swap a typeface, recolour the dam mark, or introduce a
  hue family.
- **Don't** rename the Five Stones; add plain-language subtitles instead.
- **Don't** use shadows, card chrome, side stripes or italic headlines.
- **Don't** put machinery (telemetry, traces, model ids) above the answer.
- **Don't** borrow seal-like or agency-branded treatments; Riprap is
  independent.
