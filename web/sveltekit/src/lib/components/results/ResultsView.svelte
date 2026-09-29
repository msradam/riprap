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
  import { briefingModel, type SnapshotMeta } from '$lib/client/briefingModel';
  import { briefingState } from '$lib/stores/briefingState.svelte';

  /** One briefing, laid out as a public report: the question and its
   *  answer lead, the map is a figure, the evidence is a table, and how
   *  the briefing was made is recorded once at the end. Shared by the live
   *  route (/q/[queryId]) and the static gallery (/gallery/[slug]).
   *  `notice` renders beside the jump links (the gallery's print button). */
  interface Props {
    run: RunState;
    queryText: string;
    notice?: Snippet;
    /** True on precomputed gallery pages. */
    snapshot?: boolean;
    /** Gallery pages: when and from which commit the snapshot was made. */
    meta?: SnapshotMeta;
  }
  let { run, queryText, notice, snapshot = false, meta }: Props = $props();

  let model = $derived(briefingModel(run, queryText, meta));
  /** A source list longer than this starts closed. */
  const LONG_LIST = 8;
  let howOpen = $state(false);

  let hasBriefing = $derived(!!run.finalResult);
  let isCompare = $derived(run.plan?.intent === 'compare' && run.finalResult?.targets?.length === 2);
  let isPlace = $derived(model.kind !== 'question');
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
  let title = $derived(model.question ?? model.place);
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
        labelledby="brief-evidence-h"
      />
    </section>
  {/if}
{/snippet}

{#snippet sections()}
  {#each model.body as s, i (i)}
    <section class="brief-block brief-section" aria-labelledby={s.label ? `brief-sec-${i}` : undefined}>
      {#if s.label}<h2 id="brief-sec-{i}" class="brief-h2">{s.label}</h2>{/if}
      {#each s.paras as parts, j (j)}
        <AnswerProse {parts} citations={model.citationsById} class="brief-body" />
      {/each}
    </section>
  {/each}
{/snippet}

{#snippet answerBlock()}
  <section id="brief-answer" class="brief-answer" aria-labelledby="brief-answer-h">
    <h2 id="brief-answer-h" class="visually-hidden">{model.leadLabel}</h2>
    {#if model.lead}<p class={['brief-lead', !snapshot && 'is-arriving']}>{model.lead}</p>{/if}
    {#each model.answer as parts, i (i)}
      <AnswerProse {parts} citations={model.citationsById} class="brief-answer-p" />
    {/each}
  </section>
{/snippet}

{#snippet railBlock()}
  {#if answerCites.length || showTerms}
    <aside class="brief-rail" aria-label="Sources for the {model.leadLabel === 'In brief' ? 'summary' : 'answer'}, and terms">
      {#if answerCites.length}
        <SourceNotes citations={answerCites} label="Sources for the {model.leadLabel === 'In brief' ? 'summary' : 'answer'}" />
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
    {#if model.checks}<p class="brief-quiet">{model.checks}</p>{/if}
    {#if model.modeLine}<p class="brief-quiet">{model.modeLine}</p>{/if}
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
      <h1 id="brief-h1" class="brief-title">{title}</h1>
      <p class="brief-meta">
        {#if run.resolvedPlace}
          <span class="resolved-place"><span class="brief-meta-label">Briefing for:</span> {run.resolvedPlace}</span>
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
          {@render notice?.()}
        </div>
      {/if}
    </header>

    {#if loading}
      <div class="generating-status">
        <span class="pulse" aria-hidden="true"></span>
        <span aria-hidden="true">{loadingText}, <span class="data">{elapsed} s</span></span>
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
        <div class="brief-place">
          {@render answerBlock()}
          <div class="brief-grid">
            {#if showMap}
              <div class="brief-side">
                <div class="brief-sticky">{@render map()}</div>
              </div>
            {/if}
            <div class="brief-main">
              {@render railBlock()}
              {@render afterBlock()}
              {@render evidence()}
              {@render sections()}
            </div>
          </div>
        </div>
      {:else}
        <div class="brief-top">
          {@render answerBlock()}
          {@render railBlock()}
          {@render afterBlock()}
        </div>
        {#if !run.stopped}
          {#if showMap}{@render map()}{/if}
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
                  <SourceList citations={model.citations} noted={isCompare ? [] : model.cited} />
                </details>
              {:else}
                <SourceList citations={model.citations} noted={isCompare ? [] : model.cited} />
              {/if}
            </div>
          {/if}
          <div>
            {#if showSources}
              <h3 class="brief-h3">What was checked</h3>
              <SourcesChecked lists={model.lists} />
            {/if}
            {#if model.outOfScope.length}
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
  </section>
</article>

<style>
  .brief {
    --text-w: 680px;
    --rail-w: 280px;
    --col-gap: 56px;
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
  .brief.is-place {
    max-width: 1344px;
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
  .brief-meta a,
  .brief-jumps a {
    display: inline-block;
    min-height: 24px;
  }
  .brief-tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 24px;
    margin-top: 2px;
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
    grid-template-rows: auto 1fr;
    column-gap: var(--col-gap);
    align-items: start;
    margin-top: 6px;
  }
  .brief-answer,
  .brief-after {
    grid-column: 1;
  }
  .brief-rail {
    grid-column: 2;
    grid-row: 1 / span 2;
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
  .brief :global(.inline-cite) {
    padding: 0 1px;
    text-decoration: none;
  }
  .brief :global(.inline-cite sup) {
    font-family: var(--font-mono);
    font-size: 13px;
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
    margin-top: 40px;
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

  /* Place briefings: evidence and sections left, the map sticky right */
  .brief-grid {
    display: grid;
    grid-template-columns: minmax(0, 58fr) minmax(0, 42fr);
    grid-template-areas: 'main side';
    column-gap: 40px;
    align-items: start;
  }
  .brief-main {
    grid-area: main;
    min-width: 0;
  }
  .brief-side {
    grid-area: side;
    align-self: stretch;
    min-width: 0;
    padding-top: 4px;
  }
  .brief-sticky {
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
    margin-top: 40px;
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
  .generating-status {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 12px;
    margin-top: 24px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .generating-expect {
    flex-basis: 100%;
    margin: 0;
    max-width: 54ch;
  }
  .pulse {
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
    flex-basis: 100%;
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

  /* Place briefings: the summary on top, then the notes, method lines,
     evidence and sections beside the sticky map. */
  .is-place .brief-answer {
    max-width: var(--text-w);
    margin-top: 10px;
  }
  .is-place .brief-rail {
    padding-top: 0;
  }
  .is-place .brief-rail :global(.source-notes) {
    columns: 2;
    column-gap: 32px;
  }
  .is-place .brief-rail :global(.source-note) {
    break-inside: avoid;
  }

  @media (max-width: 1099px) {
    .is-place .brief-rail :global(.source-notes) {
      columns: auto;
    }
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
    /* One column: the summary's notes and method lines, then the map,
       then the evidence and sections. */
    .brief-grid {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: none;
      max-width: var(--text-w);
    }
    .brief-main {
      display: contents;
    }
    .brief-grid :global(.brief-rail) {
      order: -3;
    }
    .brief-grid :global(.brief-after) {
      order: -2;
    }
    .brief-side {
      order: -1;
      grid-area: auto;
      padding-top: 32px;
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
    .is-question .brief-map {
      --map-h: 300px;
    }
    .brief-block {
      margin-top: 40px;
    }
  }
</style>
