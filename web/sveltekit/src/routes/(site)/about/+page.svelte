<script lang="ts">
  /** About, method and AI disclosure: where a language model can run and
   *  what it cannot change, the experimental models, how Riprap was built
   *  and checked, what the data cannot say, and how to report an error.
   *  The long forms are docs/METHODOLOGY.md, docs/GROUNDING.md and
   *  docs/MODELS.md; the figures of the 5 October 2026 check are the ones
   *  in the README. */
  import { resolve } from '$app/paths';

  const REPO = 'https://github.com/msradam/riprap';
  const DOCS = `${REPO}/blob/main/docs`;
</script>

<svelte:head>
  <title>About Riprap: method, AI disclosure and limits</title>
  <meta
    name="description"
    content="Where a language model can run in Riprap and what it cannot change, how Riprap was built and checked, what its public records cannot say, and how to report an error."
  />
</svelte:head>

<p class="site-kind">About</p>
<h1>About Riprap: method, AI disclosure and limits</h1>
<p class="site-lead">
  Riprap answers flood and heat questions about New York City places from public records. Rules or
  an open Granite model read your question and choose the evidence. Every sentence you read comes
  word for word from a public record, with its source and date.
</p>

<h2 id="method">How an answer is made</h2>
<p>
  For each place, Riprap reads the public sources that cover it. Code turns each record into one
  sentence that carries the record's source and the date of its data. A question is answered by
  rules over its own words: they pick which of those sentences answer it, and whether the figures
  support a yes, a no or a count. The sentences are shown unchanged.
</p>
<p>
  The sentences are written by Riprap's code from the records. They are not quotations of a
  publisher's own prose, and some state a figure Riprap computed from a record, such as the share
  of a district inside a mapped extent. The citation beside each sentence names the record and its
  date so the figure can be checked.
  <a href="{DOCS}/METHODOLOGY.md">The method in full</a>.
</p>

<h2 id="ai">Where a language model can run</h2>
<p>
  <strong>By default, none runs.</strong> The public site and every saved briefing in the
  <a href="{resolve('/(app)/gallery')}/">gallery</a> are built with no language model.
</p>
<p>
  A person who runs their own copy can connect one. It was tested with IBM's Granite 4.1 8B, an
  open-weight model that runs on a laptop. With a model connected:
</p>
<ul>
  <li>The rules still answer first. The model is asked only when the rules do not match a question or cannot read the place in it.</li>
  <li>The model may choose which sources to read, pick up to four of the existing sentences, and propose a lead from a fixed list: yes, no, partly, a count, or cannot answer.</li>
  <li>The model never writes a sentence. It cannot change a number, a date or a citation, because the sentences it picks are shown as code wrote them.</li>
  <li>No yes or no stands on the model's word. For a question about past flooding, a rule sets it from the observed records. Any other yes or no the model proposes is kept only when code finds it supported by the cited figures; otherwise the answer has no yes or no.</li>
  <li>Each answer says which path produced it, for example: "Answered by rules over the question's words; no language model was used."</li>
</ul>
<p class="site-small">
  One developer setting, off by default (<code>RIPRAP_LLM_BARE=1</code>), restores an older mode
  in which the model rewrites the evidence as claims and code checks each claim's citations and
  numbers. It is not used on the public site or in the gallery.
  <a href="{DOCS}/GROUNDING.md">How answers are checked</a>.
</p>

<h2 id="models">Experimental models</h2>
<p>
  Two other open models can add sentences: a forecast of surge at the Battery, and an estimate of
  paved and green land from recent satellite images. They are fine-tunes made by Riprap's
  maintainer and are not official products. Every sentence from one opens with "Experimental",
  states the model's limits and its tested accuracy, and names the official source to rely on. A
  third model, a satellite water layer, was tested twice and retired. The heat briefing uses no
  model: its forecast is the National Weather Service's.
  <a href="{DOCS}/MODELS.md">What each model was tested against, and the results</a>.
</p>

<h2 id="built">How Riprap was built</h2>
<p>
  AI coding agents wrote most of Riprap's code, tests and documents, working from prompts written
  by the maintainer, and agent sessions also reviewed that work. The maintainer, Adam Munawar
  Rahman, directed it, decides what Riprap claims, and is accountable for all of it.
</p>
<p>The output was checked in three ways:</p>
<ul>
  <li>automated tests of the code and of the wording of answers;</li>
  <li>sets of test questions with answer keys, some written without sight of the code (<a href="{DOCS}/GROUNDING.md">docs/GROUNDING.md</a>);</li>
  <li>an independent sanity check on 5 October 2026, which worked from the code, the public sources and the app's output before reading any project document. It re-derived 487 briefing sentences from the public sources with separate code: 475 were confirmed, 10 were wrong and 2 sat on the edge of a map cell. The 10 wrong sentences came from three defects (an address elevation read from a neighbouring map cell, hospitals counted twice, and a construction permits count). The first two have since been corrected in the code, and the permits sentence was taken out of plain briefings.</li>
</ul>
<p>
  The repository records no audit by a person outside the project. Riprap's checks are patterns
  and rules: they do not read meaning, and they can miss a wrong inference.
</p>

<h2 id="limits">What the data cannot say</h2>
<ul>
  <li>311 counts are complaints filed, not floods measured. Published research finds that some neighbourhoods report less often for the same conditions, so a low count is not evidence of a dry block.</li>
  <li>The city's stormwater maps are modelled scenarios, not forecasts or observations. The city says its map "does not provide the exact depth of flooding at any location".</li>
  <li>Outside a mapped area is not safe. NYC Emergency Management reports that during Hurricane Ida the most heavily impacted areas, "representing over half of all damaged buildings, were also outside of any flood risk scenario".</li>
  <li>A FloodNet depth is a measurement at one point under one sensor. It is not the depth across a street or at a building.</li>
  <li>Surface temperature is not air temperature, and the Heat Vulnerability Index is a rank among neighbourhoods. The Health Department says "a neighborhood with low vulnerability does not mean no risk".</li>
  <li>A briefing describes public records about a place. It is not a judgement on a property or on the people who live there, and it is not advice.</li>
  <li>Riprap is in English only.</li>
</ul>
<p>
  The sources for each of these statements, and the distances and time windows Riprap uses, are
  in <a href="{DOCS}/METHODOLOGY.md#10-what-the-data-cannot-say">docs/METHODOLOGY.md</a>.
</p>

<h2 id="independent">Whose project this is</h2>
<p>
  Riprap is an independent, open-source project. It is not a product of the City of New York and
  is not endorsed by or affiliated with FloodNet, New York University, the City University of New
  York, FEMA, NOAA, USGS or the City. The City publishes its open data for information only and
  does not warrant its completeness, accuracy, content or fitness for any use (Local Law 11 of
  2012). Every NYC Open Data dataset Riprap reads is listed with its ID and what Riprap does to it
  in <a href="{DOCS}/DATA-SOURCES.md">docs/DATA-SOURCES.md</a>, and other tools for the same
  records are credited in <a href="{DOCS}/BACKGROUND.md#related-work">Related work</a>.
</p>

<h2 id="corrections">Corrections</h2>
<p>
  If a sentence is wrong, or reads as saying more than its record does,
  <a href="{REPO}/issues/new/choose">open an issue on the project's tracker</a> with the address or
  question and the sentence. Corrections are made in the code and recorded in the
  <a href="{REPO}/blob/main/CHANGELOG.md">changelog</a>. If the error is in a source dataset, the
  issue will say so and point to the publisher.
</p>
