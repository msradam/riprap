<script lang="ts">
  import type { Snippet } from 'svelte';
  import { tick } from 'svelte';
  import CompareBriefing from '$lib/components/briefing/CompareBriefing.svelte';
  import DroppedClaims from '$lib/components/briefing/DroppedClaims.svelte';
  import AnswerProse from '$lib/components/briefing/AnswerProse.svelte';
  import SourceNotes from '$lib/components/briefing/SourceNotes.svelte';
  import SourceList from '$lib/components/briefing/SourceList.svelte';
  import SourcesChecked from '$lib/components/briefing/SourcesChecked.svelte';
  import MapFigure from '$lib/components/briefing/MapFigure.svelte';
  import EvidenceTable from '$lib/components/briefing/EvidenceTable.svelte';
  import HowMade from '$lib/components/briefing/HowMade.svelte';
  import LazyMap from '$lib/components/map/LazyMap.svelte';
  import SkeletonBriefing from '$lib/components/states/SkeletonBriefing.svelte';
  import ErrorCard from '$lib/components/states/ErrorCard.svelte';
  import type { RunState } from '$lib/client/runState.svelte';
  import { boldFirstSentence, briefingModel, type SnapshotMeta } from '$lib/client/briefingModel';
  import { briefingState } from '$lib/stores/briefingState.svelte';

  /** One briefing, laid out as a public report: the question and its
   *  answer lead, the map is a figure, the evidence is a table, and how
   *  the briefing was made is recorded once at the end. Shared by the live
   *  route (/q/[queryId]) and the static gallery (/gallery/[slug]).
   *  `notice` renders at the right end of the jump links row (the
   *  gallery's print button); `footer` renders after Sources and method. */
  interface Props {
    run: RunState;
    queryText: string;
    notice?: Snippet;
    footer?: Snippet;
    /** True on precomputed gallery pages. */
    snapshot?: boolean;
    /** Gallery pages: when and from which commit the snapshot was made. */
    meta?: SnapshotMeta;
  }
  let { run, queryText, notice, footer, snapshot = false, meta }: Props = $props();

  let model = $derived(briefingModel(run, queryText, meta));
  /** A source list longer than this starts closed. */
  const LONG_LIST = 8;
  let howOpen = $state(false);

  let hasBriefing = $derived(!!run.finalResult);
  let isCompare = $derived(run.plan?.intent === 'compare' && run.finalResult?.targets?.length === 2);
  let isPlace = $derived(model.kind !== 'question');
  /** A place briefing's "In brief" paragraph, set in the Brief style. */
  let isBrief = $derived(model.leadLabel === 'In brief');
  // Compare briefings carry their own source notes; the full list then
  // needs no citation targets of its own.
  let sourceNoted = $derived(isCompare ? model.citations.map((c) => c.id) : model.cited);
  let answerCites = $derived(model.citations.filter((c) => model.cited.includes(c.id)));
  let showSources = $derived(
    hasBriefing && !run.stopped &&
    (!!model.lists.consulted || model.lists.noData.length > 0 || model.lists.notChecked !== undefined)
  );
  let showTerms = $derived(hasBriefing && !run.stopped && model.terms.length > 0);
  let showMap = $derived(hasBriefing && !run.stopped && !isCompare && !!run.address);
  let showEvidence = $derived(hasBriefing && !run.stopped && !isCompare && model.cards.length > 0);
  let kindLine = $derived(
    model.kind === 'question'
      ? run.finalResult?.area_boundary ? 'Flood-exposure briefing, district question' : 'Flood-exposure briefing, question'
      : `Flood-exposure briefing, ${model.kind}`
  );
  // A place briefing is titled with the place as the reader typed it; the
  // meta line names the place it resolved to.
  let title = $derived(model.question ?? (queryText.trim() || model.place));
  // Keep house numbers such as "90-01" on one line, as the landing does.
  let titleParts = $derived(title.split(/(\d+-\d+)/));
  const norm = (t: string) => t.replace(/\s+/g, ' ').trim().toLowerCase();
  let placeRepeats = $derived(!!run.resolvedPlace && norm(run.resolvedPlace) === norm(title));
  let jumps = $derived([
    { href: '#brief-answer', label: model.leadLabel === 'In brief' ? 'In brief' : 'Answer' },
    ...(showEvidence ? [{ href: '#brief-evidence', label: 'Evidence' }] : []),
    ...(showMap ? [{ href: '#brief-map', label: 'Map' }] : []),
    { href: '#brief-sources', label: 'Sources' }
  ]);

  // Live runs only: elapsed time while the briefing is being built. The
  // visible counter ticks every second; the screen-reader line changes
  // at most every 10 seconds.
  const startedAt = Date.now();
  let now = $state(startedAt);
  let srStatus = $state('Planning intent');
  let loading = $derived(!snapshot && !run.finalResult && !run.errorState && !run.streamDone);
  let elapsed = $derived(Math.max(0, Math.round((now - startedAt) / 1000)));
  let loadingText = $derived.by(() => {
    if (!run.plan) return 'Planning intent';
    switch (briefingState.phase) {
      case 'specialists':
        return briefingState.totalSpecialists
          ? `Gathering evidence (${briefingState.firedCount}/${briefingState.totalSpecialists})`
          : 'Gathering evidence';
      case 'reconciling': return 'Reconciling';
      case 'error': return `Error${briefingState.errorMessage ? `: ${briefingState.errorMessage}` : ''}`;
      default: return 'Resolving address';
    }
  });
  $effect(() => {
    if (!loading) return;
    let ticks = 0;
    const t = setInterval(() => {
      now = Date.now();
      ticks += 1;
      if (ticks % 10 === 0) srStatus = `${loadingText}, ${ticks} seconds elapsed`;
    }, 1000);
    return () => clearInterval(t);
  });

  /** The meta line's link opens the method block and brings it into view. */
  async function openHowMade(e: MouseEvent) {
    e.preventDefault();
    howOpen = true;
    await tick();
    const el = document.getElementById('how-made');
    el?.scrollIntoView({ block: 'start' });
    el?.querySelector('summary')?.focus({ preventScroll: true });
  }
</script>

{#snippet evidence()}
  {#if showEvidence}
    <section id="brief-evidence" class="brief-block" aria-labelledby="brief-evidence-h">
      <h2 id="brief-evidence-h" class="brief-h2">Evidence</h2>
      <EvidenceTable
        groups={model.evidenceGroups}
        findings={model.findings}
        citations={model.citationsById}
        notRun={model.notRun}
        notRunHref={showSources && model.lists.notChecked?.length ? '#not-checked' : undefined}
        snapshotDate={model.generated?.slice(0, 10)}
        labelledby="brief-evidence-h"
      />
    </section>
  {/if}
{/snippet}

{#snippet sectionList(level: 'h2' | 'h3')}
  {#each model.body as s, i (i)}
    <section class={['brief-section', level === 'h2' && 'brief-block']} aria-labelledby={s.label ? `brief-sec-${i}` : undefined}>
      {#if s.label}<svelte:element this={level} id="brief-sec-{i}" class="brief-{level}">{s.label}</svelte:element>{/if}
      {#each s.paras as parts, j (j)}
        <AnswerProse {parts} citations={model.citationsById} class="brief-body" />
      {/each}
    </section>
  {/each}
{/snippet}

{#snippet sections()}
  <!-- Place briefings: the sections restate the evidence table, so they
       wait in one closed disclosure after it. Questions keep them open. -->
  {#if isPlace && model.body.length}
    <details class="brief-block brief-written">
      <summary><h2 class="brief-h2">The written briefing, section by section</h2></summary>
      {@render sectionList('h3')}
    </details>
  {:else}
    {@render sectionList('h2')}
  {/if}
{/snippet}

{#snippet answerBlock()}
  <section id="brief-answer" class="brief-answer" aria-labelledby="brief-answer-h">
    <h2 id="brief-answer-h" class="visually-hidden">{model.leadLabel}</h2>
    {#if model.lead}<p class={['brief-lead', model.leadIsSentence && 'is-sentence', !snapshot && 'is-arriving']}>{model.lead}</p>{/if}
    {#each model.answer as parts, i (i)}
      <AnswerProse
        parts={isBrief && i === 0 ? boldFirstSentence(parts) : parts}
        citations={model.citationsById}
        class={isBrief ? 'brief-answer-p is-brief' : model.keyed && i > 0 ? 'brief-answer-p is-support' : 'brief-answer-p'}
      />
    {/each}
  </section>
{/snippet}

{#snippet railBlock()}
  {#if answerCites.length || showTerms || model.checks || model.modeLine}
    <aside class="brief-rail" aria-label="Sources for the {isBrief ? 'summary' : 'answer'}, how it was checked, and terms">
      {#if answerCites.length}
        <SourceNotes citations={answerCites} label="Sources for the {isBrief ? 'summary' : 'answer'}" />
      {/if}
      <!-- Machinery sits in the margin (endnotes on narrow screens), not
           under the answer. -->
      {#if model.checks || model.modeLine}
        <div class="brief-machinery">
          {#if model.checks}<p class="brief-quiet">{model.checks}</p>{/if}
          {#if model.modeLine}<p class="brief-quiet">{model.modeLine}</p>{/if}
        </div>
      {/if}
      {#if showTerms}
        <section class="brief-terms" aria-labelledby="brief-terms-h">
          <h3 id="brief-terms-h" class="brief-h3">Terms on this page</h3>
          <dl>
            {#each model.terms as t (t.term)}
              <div><dt>{t.term}:</dt> <dd>{t.reading}</dd></div>
            {/each}
          </dl>
        </section>
      {/if}
    </aside>
  {/if}
{/snippet}

{#snippet afterBlock()}
  <div class="brief-after">
    {#each model.scope as parts, i (i)}
      <AnswerProse {parts} citations={model.citationsById} class="brief-quiet brief-scope" />
    {/each}
    <DroppedClaims claims={model.dropped} />
    {#if model.unanswered}
      <p class="brief-status" role="status">
        This question was not answered directly. Riprap is running without a language model here,
        so this is the evidence briefing for the place above.
      </p>
    {/if}
    {#if model.nyc && !run.stopped}
      <p class="brief-quiet brief-scope">
        <!-- nyc-leak-ok: gated on model.nyc (the run was routed to the NYC deployment) -->
        Live here or own property here? <a href="https://www.floodhelpny.org/" target="_blank" rel="noopener noreferrer">FloodHelpNY</a>
        explains flood zones and insurance for New York City residents.
      </p>
    {/if}
  </div>
{/snippet}

{#snippet map()}
  <!-- ponytail: map shown only once the run has finished; a live map
       during generation would need the loading skeleton to hold its space. -->
  <div id="brief-map" class="brief-map">
    <MapFigure {run} />
  </div>
{/snippet}

<article class={['brief', isPlace ? 'is-place' : 'is-question']}>
  <section id="region-briefing" aria-labelledby="brief-h1">
    <header class="brief-head">
      <p class="brief-kind">{kindLine}</p>
      <h1 id="brief-h1" class="brief-title">{#each titleParts as p, i (i)}{#if i % 2}<span class="nowrap">{p}</span>{:else}{p}{/if}{/each}</h1>
      <p class="brief-meta">
        {#if run.resolvedPlace}
          <span class="resolved-place"><span class="brief-meta-label">Briefing for:</span> {placeRepeats ? 'the place named above' : run.resolvedPlace}</span>
        {/if}
        {#if model.generated}<span>Snapshot <span class="data">{model.generated.slice(0, 10)}</span></span>{/if}
        {#if hasBriefing && !run.stopped}<a href="#how-made" onclick={openHowMade}>How this briefing was made</a>{/if}
      </p>
      {#if (hasBriefing && !run.stopped) || notice}
        <div class="brief-tools">
          {#if hasBriefing && !run.stopped}
            <nav aria-label="On this page">
              <ul class="brief-jumps">
                {#each jumps as j (j.href)}
                  <li><a href={j.href}>{j.label}</a></li>
                {/each}
              </ul>
            </nav>
          {/if}
          {#if notice}<div class="brief-action">{@render notice()}</div>{/if}
        </div>
      {/if}
    </header>

    {#if loading}
      <div class="generating-status">
        <p class="generating-line" aria-hidden="true">
          <span class="pulse"></span>{loadingText}, <span class="data">{elapsed}</span> s
        </p>
        <span class="visually-hidden" aria-live="polite">{srStatus}</span>
        <p class="generating-expect">
          Briefings take from a few seconds to a few minutes; questions answered by a
          language model can take up to five minutes.
        </p>
        {#if !run.plan && run.planTokens}
          <details class="plan-details">
            <summary>Planner streaming ({run.planTokens.length} characters)</summary>
            <pre class="plan-stream">{run.planTokens}</pre>
          </details>
        {/if}
      </div>
      {#if run.geocodeSucceeded}
        <!-- Geocode done; the briefing arrives whole in `final`. -->
        <SkeletonBriefing />
      {/if}
    {/if}

    {#if run.errorState}
      <ErrorCard state={run.errorState} />
    {:else if isCompare && run.finalResult?.targets}
      <div class="brief-compare">
        <CompareBriefing
          paragraph={run.finalResult.paragraph}
          citations={model.citationsById}
          targets={run.finalResult.targets}
          structuredA={run.compareStepsA}
          structuredB={run.compareStepsB}
        />
        <div class="brief-compare-maps">
          {#each [{ key: 'A', place: run.compareAddressA, sandy: run.sandyFcA, dep: run.depFcA, syn: run.synFcA, proxy: run.proxyFcA, ida: run.idaHwmFcA }, { key: 'B', place: run.compareAddressB, sandy: run.sandyFcB, dep: run.depFcB, syn: run.synFcB, proxy: run.proxyFcB, ida: run.idaHwmFcB }] as m (m.key)}
            {#if m.place}
              <figure class="brief-compare-map">
                <LazyMap
                  address={m.place}
                  activeLayers={{ empirical: true, modeled: true, synthetic: true, proxy: true }}
                  sandyEmpirical={m.sandy}
                  depModeled={m.dep}
                  syntheticPrior={m.syn}
                  proxy311={m.proxy}
                  idaHwm={m.ida}
                />
                <figcaption>Place {m.key}: {m.place.label}</figcaption>
              </figure>
            {/if}
          {/each}
        </div>
      </div>
    {:else if hasBriefing}
      {#if isPlace && !run.stopped}
        <!-- Place briefings: In brief, then the evidence and sections, on
             the left; the right column holds the rail (notes, method
             lines, terms, scope note) and under it the sticky map, so
             neither column leaves an empty quadrant. Source order is
             reading order at every width: the summary, its notes and
             method lines, the map, then the evidence and sections. -->
        <div class="brief-grid">
          {@render answerBlock()}
          <div class="brief-side">
            {@render railBlock()}
            {@render afterBlock()}
            {#if showMap}<div class="brief-sticky">{@render map()}</div>{/if}
          </div>
          <div class="brief-main">
            {@render evidence()}
            {@render sections()}
          </div>
        </div>
      {:else}
        <!-- Figure 1 sits in the text column beside the rail, so a long
             rail does not push it down the page. -->
        <div class="brief-top">
          {@render answerBlock()}
          {@render railBlock()}
          {@render afterBlock()}
          {#if !run.stopped && showMap}{@render map()}{/if}
        </div>
        {#if !run.stopped}
          {@render evidence()}
          {@render sections()}
        {:else}
          {@render sections()}
        {/if}
      {/if}
    {/if}

    {#if hasBriefing && !run.stopped}
      <section id="brief-sources" class="brief-block brief-end" aria-labelledby="brief-sources-h">
        <h2 id="brief-sources-h" class="brief-h2">Sources and method</h2>
        <div class="brief-end-grid">
          {#if model.citations.length}
            <div>
              <h3 class="brief-h3">Sources cited</h3>
              {#if model.citations.length > LONG_LIST}
                <!-- A long list starts closed; following a citation mark opens it. -->
                <details class="brief-cited">
                  <summary>All {model.citations.length} sources, with titles and document ids</summary>
                  <SourceList citations={model.citations} noted={sourceNoted} />
                </details>
              {:else}
                <SourceList citations={model.citations} noted={sourceNoted} />
              {/if}
            </div>
          {/if}
          <div>
            {#if showSources}
              <h3 class="brief-h3">What was checked</h3>
              <SourcesChecked lists={model.lists} />
            {/if}
            <!-- Compare columns carry their own Out of scope note; the merged
                 text would print the second place's heading raw. -->
            {#if model.outOfScope.length && !isCompare}
              <h3 class="brief-h3">Out of scope</h3>
              {#each model.outOfScope as parts, i (i)}
                <AnswerProse {parts} citations={model.citationsById} class="brief-quiet" />
              {/each}
            {/if}
          </div>
        </div>
        <HowMade {model} stones={run.findingsData.stones} bind:open={howOpen} />
      </section>
    {/if}
    {#if footer}<div class="brief-footer">{@render footer()}</div>{/if}
  </section>
</article>

<style>
  .brief {
    --text-w: 680px;
    --rail-w: 280px;
    --col-gap: 48px;
    --sticky-top: 68px;
    --scroll-offset: 72px;
    max-width: calc(var(--text-w) + var(--rail-w) + var(--col-gap) + 64px);
    margin: 0 auto;
    padding: 12px 32px 64px;
    color: var(--ink);
    font-family: var(--font-sans);
    font-size: 17px;
    line-height: 1.55;
  }
  .brief :global(a) {
    color: var(--riprap-text-link);
  }
  .brief :global(:focus-visible) {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  .brief :global(section),
  .brief :global(#brief-map) {
    scroll-margin-top: var(--scroll-offset);
  }

  /* Top: kind line, title, meta line, jump links */
  .brief-kind,
  .brief-meta,
  .brief-tools {
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .brief-kind {
    margin: 0 0 2px;
  }
  .brief-title {
    margin: 0;
    font-size: 34px;
    font-weight: 600;
    line-height: 1.18;
    letter-spacing: -0.01em;
    text-wrap: balance;
    overflow-wrap: anywhere;
  }
  .brief-title .nowrap {
    white-space: nowrap;
  }
  .is-question .brief-title {
    max-width: 30ch;
  }
  .brief-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0 20px;
    margin: 6px 0 0;
    overflow-wrap: anywhere;
  }
  .brief-meta-label {
    font-weight: 600;
  }
  /* The meta link's text sits at the top of its 24px box, level with the
     plain text beside it. The jump links centre theirs, as the gallery's
     print button beside them does, so that row shares one baseline. */
  .brief-meta a {
    display: inline-block;
    min-height: 24px;
  }
  .brief-jumps a {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
  }
  .brief-tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 24px;
    margin-top: 2px;
  }
  /* An action, not a jump: at the row's right end. */
  .brief-action {
    margin-left: auto;
  }
  .brief-footer {
    margin-top: 24px;
    font-size: 14px;
    line-height: 1.45;
  }
  .brief-jumps {
    display: flex;
    flex-wrap: wrap;
    gap: 0 16px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  /* The answer and its source notes */
  .brief-top {
    display: grid;
    grid-template-columns: minmax(0, var(--text-w)) var(--rail-w);
    grid-template-rows: auto auto 1fr;
    column-gap: var(--col-gap);
    align-items: start;
    margin-top: 8px;
  }
  .brief-answer,
  .brief-after,
  .brief-top > .brief-map {
    grid-column: 1;
  }
  .brief-rail {
    grid-column: 2;
    grid-row: 1 / span 3;
    padding-top: 10px;
  }
  .brief-lead {
    margin: 0 0 8px;
    font-size: 64px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
  }
  /* A live answer's lead word arrives once, over 150 ms. */
  .brief-lead.is-arriving {
    animation: lead-in 150ms ease-out both;
  }
  /* A refusal leads with a sentence: the lead's weight, a smaller size. */
  .brief-lead.is-sentence {
    max-width: 22ch;
    font-size: 44px;
    line-height: 1.1;
    letter-spacing: -0.015em;
    text-wrap: balance;
  }
  @keyframes lead-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .brief-lead.is-arriving { animation: none; }
  }
  .brief :global(.brief-answer-p) {
    margin: 0 0 12px;
    max-width: 54ch;
    font-size: 20px;
    line-height: 1.5;
  }
  /* A keyed answer: the key sentence at the Answer size, the rest of the
     answer one step smaller (Body) as its support. */
  .brief :global(.brief-answer-p.is-support) {
    font-size: 17px;
    line-height: 1.55;
  }
  /* Brief: the "In brief" paragraph of a place briefing, its first
     sentence in 600. Used only here (DESIGN.md type scale). */
  .brief :global(.brief-answer-p.is-brief) {
    font-size: 24px;
    line-height: 1.4;
    font-weight: 400;
  }
  .brief :global(.brief-answer-p.is-brief strong) {
    font-weight: 600;
  }
  .brief :global(.inline-cite) {
    padding: 0 1px;
    text-decoration: none;
  }
  .brief :global(.inline-cite sup) {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 400;
    line-height: 0;
    padding-left: 0.15em;
  }
  .brief :global(.inline-cite:hover),
  .brief :global(.inline-cite:focus-visible) {
    text-decoration: underline;
  }
  .brief-after {
    margin-top: 4px;
  }
  .brief :global(.brief-quiet) {
    margin: 0 0 6px;
    max-width: 54ch;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .brief :global(.brief-scope) {
    margin-top: 12px;
  }
  .brief-status {
    max-width: 54ch;
    margin: 12px 0 0;
    font-size: 17px;
  }

  /* Headings: one h2 style on the page */
  .brief-h2 {
    margin: 0 0 8px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }
  .brief-h3 {
    margin: 24px 0 8px;
    font-size: 17px;
    font-weight: 600;
    line-height: 1.3;
  }
  .brief-block {
    margin-top: 48px;
  }

  /* Figure 1 on question briefings, at the text width */
  .is-question .brief-map {
    --map-h: 360px;
    max-width: var(--text-w);
    margin-top: 32px;
  }
  .is-question .brief-block {
    max-width: var(--text-w);
  }
  /* The exhibit table takes the text and rail width. */
  .is-question .brief-end,
  .is-question #brief-evidence {
    max-width: none;
  }

  /* Place briefings: In brief, evidence and sections left; the rail and
     the sticky map right. The right column spans both rows; the flexible
     second row absorbs its height, so the evidence starts right under
     In brief whatever the rail's length. */
  .brief-grid {
    display: grid;
    grid-template-columns: minmax(0, 58fr) minmax(0, 42fr);
    grid-template-rows: auto 1fr;
    grid-template-areas: 'answer side' 'main side';
    column-gap: var(--col-gap);
    align-items: start;
    margin-top: 8px;
  }
  .brief-grid > .brief-answer {
    grid-area: answer;
  }
  .brief-main {
    grid-area: main;
    min-width: 0;
  }
  .brief-side {
    grid-area: side;
    align-self: stretch;
    min-width: 0;
  }
  .brief-side .brief-after {
    margin-top: 16px;
  }
  .brief-sticky {
    margin-top: 32px;
    position: sticky;
    top: var(--sticky-top);
    max-height: calc(100vh - var(--sticky-top) - 16px);
    overflow-y: auto;
    --map-h: 460px;
  }

  .brief-section :global(.brief-body) {
    margin: 0 0 12px;
    max-width: 54ch;
    font-size: 17px;
    line-height: 1.55;
  }

  .brief-machinery {
    margin-top: 16px;
  }
  .brief-machinery :global(.brief-quiet:last-child) {
    margin-bottom: 0;
  }
  .brief-written > summary {
    min-height: 24px;
    cursor: pointer;
  }
  .brief-written > summary .brief-h2 {
    display: inline;
  }
  .brief-written .brief-section {
    margin-top: 24px;
  }
  .brief-written .brief-h3 {
    margin-top: 0;
  }
  .brief-terms {
    margin-top: 16px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .brief-terms .brief-h3 {
    margin-top: 0;
  }
  .brief-terms dl {
    margin: 0;
    max-width: 54ch;
  }
  .brief-terms div + div {
    margin-top: 4px;
  }
  .brief-terms dt {
    display: inline;
    font-weight: 600;
    color: var(--ink);
  }
  .brief-terms dd {
    display: inline;
    margin: 0;
  }

  .brief-end {
    margin-top: 48px;
  }
  .brief-cited summary {
    min-height: 24px;
    margin-bottom: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
  }
  .brief-end-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 48px;
    align-items: start;
  }
  .brief-end-grid > div > .brief-h3:first-child {
    margin-top: 0;
  }

  /* Live run: generating status */
  /* Where the answer will be: what is happening and how long it has taken,
     in the answer's size, then what to expect in Small. */
  .generating-status {
    margin-top: 16px;
    max-width: var(--text-w);
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .generating-line {
    margin: 0 0 4px;
    font-size: 20px;
    line-height: 1.5;
    color: var(--ink);
  }
  .generating-line .data {
    font-size: 18px;
  }
  .generating-line .pulse {
    display: inline-block;
    margin-right: 10px;
    vertical-align: 0.15em;
  }
  .generating-expect {
    margin: 0;
    max-width: 54ch;
  }
  .pulse {
    flex: none;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-graphical);
    animation: pulse 1.4s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(0.85); }
    50% { opacity: 1; transform: scale(1.1); }
  }
  @media (prefers-reduced-motion: reduce) {
    .pulse { animation: none; opacity: 0.7; }
  }
  .plan-details {
    margin-top: 8px;
  }
  .plan-details summary {
    min-height: 24px;
    cursor: pointer;
  }
  .plan-stream {
    margin: 4px 0 0;
    max-height: 240px;
    overflow: auto;
    white-space: pre-wrap;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink-secondary);
  }

  /* Compare intent */
  .brief-compare {
    margin-top: 24px;
  }
  .brief-compare-maps {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
    gap: 24px;
    margin-top: 24px;
  }
  .brief-compare-map {
    margin: 0;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .brief-compare-map figcaption {
    margin-top: 8px;
  }

  @media (max-width: 1099px) {
    .brief-top {
      grid-template-columns: minmax(0, 1fr);
      max-width: var(--text-w);
    }
    /* Source notes become endnotes directly under the answer. */
    .brief-rail {
      grid-column: 1;
      grid-row: auto;
      padding-top: 4px;
    }
    /* One column, in source order: the summary, its endnotes and method
       lines, the map, then the evidence and sections. */
    .brief-grid {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: none;
      grid-template-areas: 'answer' 'side' 'main';
      max-width: var(--text-w);
    }
    .brief-side .brief-after {
      margin-top: 4px;
    }
    .brief-end-grid {
      grid-template-columns: minmax(0, 1fr);
      row-gap: 24px;
    }
    .brief-sticky {
      position: static;
      max-height: none;
      overflow: visible;
      --map-h: 300px;
    }
  }

  @media (max-width: 640px) {
    .brief {
      --scroll-offset: 132px;
      padding: 16px 16px 48px;
    }
    .brief-title {
      font-size: 26px;
    }
    .brief-lead {
      font-size: 44px;
    }
    .brief-lead.is-sentence {
      font-size: 32px;
    }
    .brief :global(.brief-answer-p.is-brief) {
      font-size: 21px;
    }
    .is-question .brief-map {
      --map-h: 300px;
    }
    .brief-block {
      margin-top: 32px;
    }
  }
</style>
