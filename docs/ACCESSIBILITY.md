# Accessibility statement

Riprap's web app is built to meet the Web Content Accessibility Guidelines
(WCAG) 2.2 at Level AA. The City of New York adopted that standard in December
2025 ([Mayor's Office for People with Disabilities](https://www.nyc.gov/site/mopd/initiatives/digital-accessibility.page)),
and a project the City links to is judged against it. Riprap has not been
audited by an outside party, and this statement does not claim conformance.

Last reviewed 5 October 2026. The same statement is a page in the app, at
`/accessibility/`, linked from the footer of every page
(`web/sveltekit/src/routes/(site)/accessibility/+page.svelte`). Change the two
together.

## How it was tested

| Check | What it is | Where | Result on record |
|---|---|---|---|
| axe-core | `@axe-core/playwright` with the rule tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa` and `wcag22aa`; a test fails on any violation | `web/sveltekit/tests/e2e/journeys.spec.ts` and `heat.spec.ts` (`pnpm test:e2e`) | Not rerun for this statement. The suite needs a browser and runs on a developer's machine; continuous integration does not run it yet |
| Contrast gate | Every text and graphic colour role against every surface it is drawn on: 4.5 to 1 for text (1.4.3), 3 to 1 for graphics (1.4.11) | `node docs/design/handoff/gates/contrast-gate.mjs` | `contrast-gate: PASS (25 role/surface/ground checks)`, 5 October 2026 |
| Code review | The Svelte components and CSS read against each WCAG 2.2 Level A and AA criterion | This document | 5 October 2026, findings below |

The axe tests cover these states: the landing page, a flood briefing, a heat
briefing for an address and for a district, a briefing while it loads, a
refusal, a failed source, an open citation, the
print view, the gallery index and a gallery entry, the map's list of points
with a point chosen by mouse and by keyboard, and (added with this statement)
the about page and the accessibility page. One journey is driven with the
keyboard alone, one at 390 CSS pixels wide, and one with reduced motion.

The contrast gate reads the design tokens in
`docs/design/handoff/tokens/tokens.css`. The app's own token file
(`web/sveltekit/src/lib/tokens.css`) was checked with the same contrast code on
the same day: the lowest text pair is link blue on sunken paper at 5.67 to 1.

**No person who uses a screen reader, a switch, voice control or screen
magnification has tested Riprap.** The repository holds no record of a manual
screen reader pass either. Automated checks find only some barriers, so the
list under "Known limitations" is what is known, not all there is.

## What the code review found

"Fixed" means changed in the code on 5 October 2026. "Holds" means the review
found the criterion met in the source; it was not measured in a browser unless
the axe tests cover it.

| Criterion | Finding |
|---|---|
| 1.1.1 Non-text content | Holds. The landing's example answer is text, not an image; decorative marks are hidden, and the map has the equivalents listed under "The map" below |
| 1.3.1, 2.4.1, 2.4.6 Structure, bypass, headings | Holds. One `h1` a page, `header`, `main` and `footer` landmarks, labelled sections, and a skip link to the main content. The map has its own "Skip the map" link |
| 1.4.1 Use of colour | Holds. Evidence classes carry a glyph and a word as well as a colour; the heat ramp has a numbered scale |
| 1.4.3, 1.4.11 Contrast | Holds for the colour roles (the gate above). Hairline rules around some boxes are fainter than 3 to 1; none is the only sign of a control |
| 1.4.10 Reflow, 1.4.12 Text spacing | Holds in the code: single-column layouts below 720 and 480 CSS pixels, heights set as minimums. Measured in a browser at 390 pixels only. The command block on the landing page scrolls sideways and can be scrolled with the keyboard |
| 2.1.1 Keyboard | Holds. One full journey is tested with the keyboard alone |
| 2.2.2 Pause, stop, hide | Fixed. The landing page's moving preview runs in a loop for longer than five seconds and stopped only on hover or focus. It now has a "Pause the preview" button, and it is a still picture when reduced motion is set |
| 2.3.3, reduced motion | Holds. Animations and map movement are switched off under `prefers-reduced-motion` |
| 2.4.2 Page titled, 3.1.1 Language | Holds. Every route sets a title; the document language is English |
| 2.4.4 Link purpose | Holds. Links are named for their target; citation marks are named "Citation 3, FloodNet" and the like |
| 2.4.7 Focus visible, 2.4.11 Focus not obscured | Fixed. A 3 pixel focus ring was already on every control, but the sticky header could cover a control focused by Shift+Tab near the top of the window. Focused controls now scroll clear of the header (`:focus-visible { scroll-margin-top }` in `chrome.css`) |
| 2.5.3 Label in name | Fixed. The header's query button showed the question and "edit" but was named only "Edit query". Its name now starts with the words shown |
| 2.5.7 Dragging movements | Fixed. The map could be panned only by dragging (or with the keyboard). It now has four pan buttons beside its zoom buttons |
| 2.5.8 Target size | Holds. Stand-alone links and buttons are at least 24 by 24 CSS pixels; a citation mark has a 24 pixel hit area. Links inside a sentence are exempt |
| 3.2.6 Consistent help | Fixed. The footer of every page now carries, in the same order, where to go for alerts and help, the about and accessibility links, and the feedback link. The print view has no footer (see below) |
| 3.3.1, 3.3.2 Errors and labels | Holds, with one fix. The question box has a visible label, and an empty submit is explained in text in a status region. The box is now also marked invalid while that message shows |
| 3.3.7, 3.3.8 Redundant entry, authentication | Not applicable. There are no accounts and no multi-step forms |
| 4.1.2 Name, role, value | Holds under the axe tests |
| 4.1.3 Status messages | Holds. One polite live region announces progress every ten seconds while a briefing loads and then "Briefing ready" with the answer's first sentence; an error is an alert |

## Known limitations

- **The map.** The map is drawn on a canvas, and a screen reader cannot read
  what is on it. The briefing text is its equivalent: every point and area on
  the map comes from a sentence in the briefing. The caption under the map
  says what is plotted and how many of each, "Map points as a list" gives
  every point as a button that selects it, and the layer switches are labelled
  checkboxes. The background tiles have no street labels. One finger scrolls
  the page past the map on a phone; two fingers move it.
- **Colour on the map.** A heat briefing's surface temperature layer is a
  colour ramp from blue to red. The caption and the numbered scale under it
  say the same in words, and the figures are in the briefing text. The ramp
  has not been tested with colour-blind readers.
- **Print view and PDF.** Riprap makes no PDF. The print view is a web page
  laid out for paper, and a PDF saved from it is tagged by the browser, which
  Riprap does not control and has not tested. The print view has no site
  header, footer or skip link, and it opens the browser's print dialog when it
  loads.
- **English only.** The app and its briefings are in English. Some sentences
  keep technical terms from their sources (a vertical datum, a rainfall
  rate); a briefing lists the ones it uses under "Terms on this page".
- **Truncated text.** On a narrow screen the header shortens a long question
  and the status of a running briefing. The full text is in the page heading
  and in the live region.
- **Other sites.** Riprap links to agency pages and maps it does not control.
- **The gallery on GitHub Pages** is the same build as the app, so the same
  limits apply.

## Report a barrier

Open an issue on the project's tracker,
<https://github.com/msradam/riprap/issues/new/choose>, and say what page you
were on, what you were trying to do and what assistive technology or browser
you use. A barrier is treated as a defect: it is fixed in the code and
recorded in the [changelog](../CHANGELOG.md). The tracker needs a free GitHub
account.
