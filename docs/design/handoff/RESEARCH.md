# Research — calm technology and civic-cartographic precedent

Two threads. Read both before designing anything; this document reports
findings, it does not pre-decide what to do with them — that synthesis is
the design session's job, done fresh, not inherited from here.

## Thread 1 — Calm Technology (calmtech.com, Amber Case)

The site states eight principles. Reading them literally, as an attention
and motion budget for a document-reading surface (not a phone-first
ambient-notification product, which is the context most calm-tech
commentary assumes):

1. **Technology should require the smallest possible amount of
   attention.** For a report, this reads as: the reader's attention goes
   to the content, not to the chrome. Motion, color, and iconography
   should not compete with the prose and the numbers for the eye.
2. **Technology should inform and create calm.** A briefing that states
   uncertainty plainly (a modeled or synthetic figure says so, every
   time) is calmer than one that hides uncertainty behind confident-
   looking typography — false confidence is not calm, it is a debt paid
   later when the reader discovers the hedge was missing.
3. **Technology should make use of the periphery.** Metadata (citation
   marks, timestamps, source labels) belongs in the visual periphery —
   findable at a glance, not competing with body text for primary
   attention. This is a genuinely different design job on paper/screen
   than in a phone-notification context: "periphery" here likely means
   type weight, size, and color-tier, not physical screen position.
4. **Amplify the best of technology and the best of humanity.** A
   citation-grounded report is the specific claim Riprap already makes
   about this; the design should not undercut it by making the citation
   apparatus feel like decoration rather than the actual evidentiary
   backbone of the document.
5. **Technology can communicate but doesn't need to speak.** Read for a
   report: status/severity/evidence-class information should be legible
   from the mark itself (shape, weight, position) as much as possible,
   not solely from a color that requires a legend lookup every time.
6. **Technology should work even when it fails.** A missing data source,
   an offline probe, an unreachable API — the layout should degrade
   gracefully (an omitted section, not a broken one; see BRIEF.md's
   "silence over confabulation" note).
7. **The right amount of technology is the minimum needed to solve the
   problem.** One motion duration if any, not a library of easing
   curves. One line weight system, not four. This is a budget to set
   deliberately, not a call to add nothing.
8. **Technology should respect social norms.** A civic/engineering report
   has its own norms — dated methodology, numbered sections, a citation
   apparatus, a stamp/hash page for verification — closer to ASTM/USGS
   report conventions than to consumer-app conventions. Respecting those
   norms is itself a calm-tech move: it meets the reader where their
   trust calibration already is.

The site's own visual choices are consistent with principle 7: no
autoplaying media, minimal chrome, prose-forward. Exact typography/spacing
specifics were not reliably extractable and should not be copied
literally — the principles are the transferable part, not calmtech.com's
own CSS.

## Thread 2 — decades-trusted civic-cartographic and report conventions

Researched instead of guessed, because a civic-engineer reader's trust
calibration is built on forty years of specific, learnable conventions —
reusing them (accurately) is worth more than a novel palette that has to
earn trust from zero.

**FEMA Flood Insurance Rate Maps (FIRM).** Confirmed convention: the
1%-annual-chance floodplain (zones A/AO/AH/AE/VE) renders in blue shading;
the 0.2%-annual-chance/moderate-risk Zone X (shaded) renders in orange;
minimal-risk Zone X is unshaded. VE vs. AE (the 3-ft wave-height threshold)
is a letter-code distinction, not a color distinction. Exact hex values
were not extractable from FEMA's official graphics-guidance PDF in this
research pass (403/non-text-parseable) — treat as a follow-up if exact
FEMA-matching hex is wanted, not a blocker.

Important: this is a *probability-band* axis (how likely is a flood of
this size), which is a different question from Riprap's *evidence-class*
axis (empirical/modeled/proxy/synthetic — how directly do we know this) or
a potential *severity* axis (how bad would this be). Reusing FEMA's
blue/orange for a different axis would misread as "this is an official
FEMA zone." If any color from this palette gets reused, it should be for
something that actually is a probability-band concept, not repurposed.

**NWS watch/warning/advisory colors.** Confirmed finding, and a useful
negative one: NWS assigns colors **per hazard type**, not on a shared
severity gradient — e.g. a Tornado Watch is yellow and a Storm Warning is
dark violet, unrelated hues for unrelated hazards. There is no single
"redder = worse" scale to borrow wholesale. This suggests a severity axis
for Riprap (if one is designed) should be its own small, deliberately
designed ladder — not an attempt to reverse-engineer NWS's lookup table,
which isn't actually a perceptual scale.

**USWDS (US Web Design System).** Confirmed directly: color tokens use a
5-90 numeric grade scale (0=white, 100=black) plus "vivid" accent variants,
where grade delta predicts contrast ratio — a systematic way to guarantee
accessibility rather than checking case by case. Confirmed hex:
`blue-60v` = `#005ea2`, `blue-warm-70v` = `#1a4480`. Riprap's *existing*
`--tier-empirical`/`--tier-modeled` already match these exactly (see
BRIEF.md) — a real, citable asset, not a coincidence to restate as
"USWDS-inspired."

**USGS topographic maps.** The traditional five-plate color system (green
for vegetation/woodland, blue for hydrography, red for urban/important
roads, black for cultural features and labels, brown for contours/relief)
is a genuinely different grammar from FEMA's or NWS's — organized by *what
kind of thing is being shown* rather than *how urgent it is*. Index
contours (heavier-weight, labeled) versus intermediate contours
(lightweight, unlabeled) is a two-weight-line convention worth knowing
about for any map-adjacent legend or table-heading treatment, regardless
of whether the literal green/blue/red/black/brown palette gets used.

**IPCC AR6 WGI visual style.** Confirmed to exist as an authored 24-page
guide (Lato + Myriad Pro), built through explicit co-design with cognitive
scientists per secondary sourcing (exact type scale not independently
extracted this pass — the source PDF resisted text extraction). The
directionally solid, citable finding: IPCC actively designs *against*
clutter — a chart is built so the single most important message reads
first, via salience (color, size, spacing), with density treated as a cost
to be paid deliberately, not a default. "Authoritative" in this tradition
does not mean "dense."

**ASTM E1527-21 (Phase I Environmental Site Assessment).** Confirmed
structural, not typographic: the standard's Appendix X5 specifies required
*content* (site photos, a boundary map, flagged Recognized Environmental
Conditions, dated methodology disclosure) rather than any font or layout.
The implication for Riprap: a report reads as authoritative because of
what it discloses and how completely (dated methodology, every claim
sourced, an explicit scope/disclaimer statement) more than because of a
particular typeface — which is evidence *for* Riprap's existing citation-
grounding approach being the right lever, not a typography problem to
solve instead.

## Open follow-up (not done in this pass)

Exact FEMA/NWS/IPCC hex values and IPCC's exact type-scale numbers were
not reliably extractable via URL-based fetch in this research pass (PDF
encoding/compression issues, one 403). If exact government-hex matching
becomes important, the next step is downloading the source PDFs directly
and extracting text locally, not re-attempting the same URL fetch.
