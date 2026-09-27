# Product

<!-- impeccable:product-schema 1 -->

<!-- Written during the unattended Impeccable pass (2026-09-27). The owner
     asked not to be interviewed; facts come from impeccable_pass.md, the
     design handoff (docs/design/handoff/) and the refactor reports. Lines
     marked (inferred) are the author's reading and await the owner. -->

## Platform

web

## Users

Professional readers who need a defensible, sourced statement about flood
exposure at a New York City place:

- data journalists writing a sourced sentence on deadline;
- community board and city council staff preparing for a meeting;
- city resilience analysts and agency capital planners checking a site;
- civic engineers, urban planners and NGO staff (drainage review, grant
  evidence such as a FEMA BRIC sub-application);
- civic researchers and the BetaNYC / NYC Open Data community.

They already read government cartography and technical reports, and are
professionally sceptical. It is not a resident-facing tool and not a
real-estate or insurance tool.

## Product Purpose

Riprap turns an NYC street address, a community district code (such as
QN12) or a plain-language flood question into a briefing in which every
number is cited to a public record, an agency report or a labelled model
output. Success is a reader who can quote a sentence and show its source,
and who can see what was not checked.

## Positioning

The answer is assembled from the cited evidence itself: in the default
mode the answer text is the source sentence word for word behind a fixed
lead ("Yes.", "No.", "In part.", "From the sources consulted:"), and the
briefing says which sources were consulted, which were not checked, which
claims were dropped and which checks ran. When the evidence does not
answer, it says so instead of guessing.

## Operating Context

- A single briefing streams in over 20 seconds to several minutes (the LLM
  path can take up to 300 s; the no-LLM path is faster).
- Readers move between the on-screen briefing, its map and citations, and a
  printed or PDF packet brought to a meeting or attached to a filing.
- A static gallery of precomputed briefings runs with no backend (GitHub
  Pages style).
- Six city deployments exist (NYC production; Chicago, Seattle, San
  Francisco, Boston and Albany experimental).

## Capabilities and Constraints

- Inputs: street address, community district code, natural-language flood
  question. Out-of-scope questions (buying, renting or insuring property,
  legal advice, a forecast for a named day, a hazard other than flooding)
  get a fixed refusal text.
- Output: an Answer (question mode), sections grouped by the Five Stones
  (Cornerstone, Keystone, Touchstone, Lodestone, Capstone), inline numbered
  citations with a citations list, "Sources consulted / Not checked",
  dropped claims, experimental badges, a line naming the checks that ran, a
  MapLibre map, and a print route.
- A section with no evidence is omitted or marked, never fabricated
  ("silence over confabulation").
- Independent open-source software, not affiliated with FEMA, NOAA, USGS or
  any city government; the design must not imply otherwise.
- Backend behaviour and grounding logic are out of scope for design work.

## Brand Commitments

- Name: Riprap (the loose rock armour that protects a shoreline).
- Logo: the dam mark (`docs/design/handoff/reference/logo-dam-mark.svg`),
  pinned.
- Type: Sofia Sans and Overpass Mono, pinned (sizes, weights and hierarchy
  may change within them).
- Colour: the "hydro" palette in `docs/design/handoff/tokens/tokens.css`,
  pinned (use and contrast may be rebalanced; no new hue family).
- Taxonomy: the Five Stones names are pinned; plain-language subtitles may
  be added.

## Evidence on Hand

- 30 author-written questions and 20 held-out questions with recorded runs
  (`tests/question_eval/`).
- The static gallery (`web/sveltekit/src/lib/gallery/`): ten no-LLM address
  briefings and four LLM question briefings.
- Methodology and grounding documentation (`docs/GROUNDING.md`,
  `docs/METHODOLOGY.md`).
- No user research, testimonials, adoption figures or partner endorsements
  exist; do not fabricate them.

## Product Principles

1. Evidence, not advice: report what public records show and refuse what
   they cannot support.
2. Every claim is checkable: a reader can reach the source of any sentence.
3. Say what is missing: sources not checked, dropped claims and
   experimental labels are part of the answer, not fine print.
4. Honest silence beats a plausible guess.
5. A professional document: it has to hold up on paper and in a meeting.
   (inferred from the print packet and audience)

## Accessibility & Inclusion

WCAG 2.2 AA and Section 508 are stated commitments. Evidence tier is
carried by shape as well as colour (grayscale-safe), contrast is measured
by the handoff gates, and every interactive control must be keyboard
reachable with a visible focus.
