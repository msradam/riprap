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
  const CORRECTION = `${REPO}/issues/new?template=correction.yml`;
  const FLOODNET_LICENCE = 'https://docs.google.com/document/d/1jd5Q2UYj_0PwMRplFISmhT6LswpS08D9/edit';

  /** The NYC Open Data datasets a briefing reads, by the portal's own name
   *  and four-by-four ID, as docs/DATA-SOURCES.md lists them. FloodNet's
   *  table is listed there as not read directly: Riprap reads FloodNet's API. */
  const OPEN_DATA: { id: string; name: string; use: string }[] = [
    { id: 'erm2-nwe9', name: '311 Service Requests from 2020 to Present', use: 'flood and sewer complaints' },
    { id: '5xsi-dfpx', name: 'Sandy Inundation Zone', use: 'the 2012 Sandy extent' },
    { id: '9i7c-xyvv', name: 'NYC Stormwater Flood Maps', use: 'the four modelled stormwater scenarios' },
    { id: 'phvi-damg', name: 'NYCHA Public Housing Developments', use: 'public housing' },
    { id: 'a3nt-yts4', name: '2019 - 2020 School Point Locations', use: 'public schools' },
    { id: 'ipu4-2q9a', name: 'DOB Permit Issuance', use: 'only when a question asks about construction' },
    { id: '9nt8-h7nd', name: '2020 Neighborhood Tabulation Areas (NTAs)', use: 'area outlines' },
    { id: 'he6d-2qns', name: 'Land Cover Raster Data (2017), 6in Resolution', use: 'tree canopy and paved ground' },
    { id: 'ckaz-6gaa', name: 'NYC Parks Spray Showers', use: 'places to cool off' },
    { id: 'y5rm-wagw', name: 'NYC Parks Pools', use: 'places to cool off' }
  ];
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
  <li>The rules still answer first. The model is called only when no rule handles the query.</li>
  <li>In planning, the model may set the intent among six (code overrides it when the parser found an address or a district), the target text, the focus, and which sources run beyond a fixed floor. It also writes a rationale of at most 300 characters, which appears only in the JSON plan and the stream's plan event, never in the briefing.</li>
  <li>In answering, the model may propose a lead from a fixed list (yes, no, partly, a count, or cannot answer) and pick up to four existing sentences and their order.</li>
  <li>By default the model cannot write a sentence or a number in a briefing: the sentences it picks are shown as code wrote them.</li>
  <li>No yes or no stands on the model's word. Code overrides the lead for questions about a past event, about now and about a forecast, requires a yes-or-no question shape, and checks the lead against the cited figures. A failure is sent back to the model once; after that the lead and the picks are dropped.</li>
  <li>Each answer says which path produced it (<code>answer_path</code> in the JSON, <code>rules</code> or <code>llm</code>), for example: "Answered by rules over the question's words; no language model was used."</li>
</ul>
<p class="site-small">
  One developer setting, off by default (<code>RIPRAP_LLM_BARE=1</code>), is the one mode in
  which a model rewrites evidence as sentences, checked for citation ids and numbers. It is not
  used on the public site or in the gallery.
  <a href="{DOCS}/GROUNDING.md">How answers are checked</a>.
</p>

<h2 id="models">Experimental models</h2>
<p>
  One other open model can add sentences: an estimate of paved and green land from recent
  satellite images. It is a fine-tune made by Riprap's maintainer and is not an official product.
  Every sentence from it opens with "Experimental", states the model's limits and its tested
  accuracy, and follows the sentence from the city's own land cover map.
</p>
<p>
  Two more were tested and taken out. A forecast of surge at the Battery is out of default
  briefings since 5 October 2026: on 639 held-out four-day windows its mean error was 0.115 m,
  and damped persistence, a one-line rule, scored 0.108 m and beats it. It foresaw 1 of the 23
  windows that reached flood stage. A person running their own copy can switch it back on. The
  model card hosted on Hugging Face is out of date; the
  <a href="{DOCS}/model-cards/Granite-TTM-r2-Battery-Surge.md">corrected card</a> is in the
  repository. A satellite water layer was tested twice and retired. The heat briefing uses no
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
  <li>a sanity check on 5 October 2026, run by AI agents separate from those that wrote the code, which worked from the code, the public sources and the app's output before reading any project document. It re-derived 487 briefing sentences from the public sources with separate code: 475 were confirmed, 10 were wrong and 2 sat on the edge of a map cell. The 10 wrong sentences came from three defects (an address elevation read from a neighbouring map cell, hospitals counted twice, and a construction permits count). The first two have since been corrected in the code, and the permits sentence was taken out of plain briefings.</li>
</ul>
<p>
  The agents that ran that check worked read-only, under the maintainer's direction, and were
  not the agents that wrote the code.
  <a href="{DOCS}/history/SANITY-CHECK-2026-10-05.md">Its method, its figures, and what was done about each problem it found</a>.
  The repository records no audit by a person outside the project. Riprap's checks are patterns
  and rules: they do not read meaning, and they can miss a wrong inference.
</p>
<p>
  These checks confirm that a sentence matches its source. Nothing yet tests the joined evidence
  against flooding that was observed, so a briefing can agree with every record it reads and
  still miss what happened on a block.
</p>
<p>
  Riprap is built by one person. No community group, agency or resident has yet shaped or tested
  it. To send a correction, or an account of flooding or heat that the records miss, see
  <a href="#corrections">Corrections</a>.
</p>

<h2 id="limits">What the data cannot say</h2>
<ul>
  <li>311 counts are complaints filed, not floods measured. Published research finds that some neighbourhoods report less often for the same conditions, so a low count is not evidence of a dry block.</li>
  <li>The city's four stormwater flood maps are modelled scenarios, not forecasts or observations. The city says its map "does not provide the exact depth of flooding at any location".</li>
  <li>Outside a mapped area is not safe. NYC Emergency Management reports that during Hurricane Ida the most heavily impacted areas, "representing over half of all damaged buildings, were also outside of any flood risk scenario".</li>
  <li>A FloodNet depth is a measurement at one point under one sensor. It is not the depth across a street or at a building. Riprap counts only the events FloodNet has verified, and it quotes a sensor's status as FloodNet lists it today without interpreting it.</li>
  <li>A neighbourhood name can be answered for a larger official area, or for part of one. The line under the briefing's title says which area was used.</li>
  <li>Surface temperature is not air temperature, and the Heat Vulnerability Index is a rank among neighbourhoods. The Health Department says "a neighborhood with low vulnerability does not mean no risk". For air temperature across the city, see BetaNYC's <a href="https://urbanheat.nyc">NYC Urban Heat Portal</a>.</li>
  <li>No one has compared briefings with an independent record of where water stood in a storm.</li>
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
  2012). FloodNet's data, and the sentences and figures made from it, are licensed CC BY-NC-SA
  4.0 and are not under Riprap's Apache-2.0 licence. FloodNet's
  <a href={FLOODNET_LICENCE}>Data Access License Agreement</a> binds anyone who uses its data;
  FloodNet has not been asked about Riprap's use and has not approved it
  (<a href="{DOCS}/DATA-SOURCES.md#floodnets-licence-and-what-riprap-does-about-it">what Riprap does about each clause</a>).
  Other tools for the same records are credited in
  <a href="{DOCS}/BACKGROUND.md#related-work">Related work</a>.
</p>

<h2 id="open-data">NYC Open Data used</h2>
<p>
  Each dataset by the name NYC Open Data gives it, with its ID. What Riprap does to each before a
  sentence is written, the copy dates and the sources published elsewhere (federal, state, the
  Health Department, FloodNet) are in <a href="{DOCS}/DATA-SOURCES.md">docs/DATA-SOURCES.md</a>.
</p>
<ul>
  {#each OPEN_DATA as d (d.id)}
    <li>
      <a href="https://data.cityofnewyork.us/d/{d.id}">{d.name}</a> (<code>{d.id}</code>): {d.use}
    </li>
  {/each}
</ul>

<h2 id="corrections">Corrections</h2>
<p>
  If a sentence is wrong, or reads as saying more than its record does,
  <a href={CORRECTION}>fill in the correction form</a> with the place and the sentence. The form
  asks nothing technical; it is public and needs a free GitHub account. Corrections are made in the code and recorded in the
  <a href="{REPO}/blob/main/CHANGELOG.md">changelog</a>. If the error is in a source dataset, the
  issue will say so and point to the publisher. An account of flooding or heat that the records
  miss is welcome on the same form; Riprap has no way yet to put one into a briefing, so it is
  kept there.
</p>
