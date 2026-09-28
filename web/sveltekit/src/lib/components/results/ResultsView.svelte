<script lang="ts">
  import type { Snippet } from 'svelte';
  import Briefing from '$lib/components/briefing/Briefing.svelte';
  import CompareBriefing from '$lib/components/briefing/CompareBriefing.svelte';
  import CitationDrawer from '$lib/components/briefing/CitationDrawer.svelte';
  import DroppedClaims from '$lib/components/briefing/DroppedClaims.svelte';
  import LazyMap from '$lib/components/map/LazyMap.svelte';
  import MapLegend from '$lib/components/map/MapLegend.svelte';
  import SkeletonBriefing from '$lib/components/states/SkeletonBriefing.svelte';
  import ErrorCard from '$lib/components/states/ErrorCard.svelte';
  import FindingsRegion from '$lib/components/findings/FindingsRegion.svelte';
  import type { Density, ProvenanceMode } from '$lib/types/card';
  import type { RunState } from '$lib/client/runState.svelte';
  import { briefingState, sourceLists } from '$lib/stores/briefingState.svelte';
  import { looksLikeQuestion } from '$lib/client/runState.svelte';
  import { splitBriefing } from '$lib/client/parseBriefing';
  import { modeLine } from '$lib/client/cardAdapter';
  import { browser } from '$app/environment';
  import { page } from '$app/state';

  /** Briefing + map + citations + findings for one run. Shared by the
   *  live route (/q/[queryId]) and the static gallery (/gallery/[slug]).
   *  `notice` renders under the heading (the gallery's snapshot line). */
  interface Props {
    run: RunState;
    queryText: string;
    notice?: Snippet;
    /** True on precomputed gallery pages. */
    snapshot?: boolean;
  }
  let { run, queryText, notice, snapshot = false }: Props = $props();

  /** Hovering a findings card lights up its layer on the map. */
  let linkedKey = $state<string | null>(null);
  let density = $state<Density>('comfortable');
  let provenanceMode = $state<ProvenanceMode>('smart');
  let active = $state({ empirical: true, modeled: true, synthetic: true, proxy: true });
  // ?grammar=1 surfaces the dev-only card-grammar catalog. Client only:
  // prerendering forbids reading url.searchParams.
  let showGrammar = $derived(browser && page.url.searchParams.get('grammar') === '1');

  let grounding = $derived(run.finalResult?.grounding);
  let blocks = $derived(run.briefing.blocks);
  let citations = $derived(run.briefing.citations);
  let question = $derived(
    run.plan?.question || grounding?.question || (looksLikeQuestion(queryText) ? queryText : '')
  );
  // Consulted (failed steps flagged), ran but returned no data, and not
  // checked for this question. Older gallery JSON lacks the first and last.
  let lists = $derived(sourceLists(run));
  let failedCount = $derived(lists.consulted?.filter((r) => r.failed).length ?? 0);
  let showSources = $derived(
    !!run.finalResult && !run.stopped &&
    (!!lists.consulted || lists.noData.length > 0 || lists.notChecked !== undefined)
  );
  /** Lists at or under this length open by default. */
  const SHORT_LIST = 8;

  // Lead = the Answer section; the body starts at the first other section
  // head. The backend's scope preamble and its "Out of scope" section are
  // disclosure, so they render as quiet notes (words unchanged): the
  // preamble under the Answer, Out of scope after the body.
  let split = $derived(splitBriefing(blocks));
  let hasAnswer = $derived(blocks.some((b) => b.kind === 'head' && b.label === 'Answer'));
  let unanswered = $derived(
    !!question && !!run.finalResult && !run.stopped && !hasAnswer && grounding?.tier !== 'llm'
  );

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

  function handleFindingsCite() {
    document.getElementById('region-cites')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
</script>

{#snippet sources()}
  <section class="sources" aria-label="Sources consulted, sources with no data, and sources not checked">
    {#if lists.consulted}
      <details class="sources-col" open={lists.consulted.length <= SHORT_LIST}>
        <summary class="sources-head">
          <!-- Older snapshots carry no consulted list, only the failed steps. -->
          {lists.hasConsultedList ? 'Sources consulted' : 'Sources that failed to respond'} ({lists.consulted.length}){#if lists.hasConsultedList && failedCount}, {failedCount} failed to respond{/if}
        </summary>
        <ul class="sources-list">
          {#each lists.consulted as s (s.id)}
            <li class:is-failed={s.failed}>{s.title}{#if s.failed}<span class="sources-failed">: failed to respond</span>{/if}</li>
          {/each}
        </ul>
      </details>
    {/if}
    {#if lists.noData.length}
      <details class="sources-col" open={lists.noData.length <= SHORT_LIST}>
        <summary class="sources-head">Ran but returned no data ({lists.noData.length})</summary>
        <ul class="sources-list">
          {#each lists.noData as t, i (`${i}-${t}`)}
            <li>{t}</li>
          {/each}
        </ul>
      </details>
    {/if}
    {#if lists.notChecked?.length}
      <details class="sources-col" open={lists.notChecked.length <= SHORT_LIST}>
        <summary class="sources-head">Not checked for this question ({lists.notChecked.length})</summary>
        <ul class="sources-list">
          {#each lists.notChecked as t, i (`${i}-${t}`)}
            <li>{t}</li>
          {/each}
        </ul>
      </details>
    {:else if lists.notChecked}
      <p class="sources-col sources-none">
        <span class="sources-head">Not checked for this question:</span> none of the sources for this kind of place were skipped.
      </p>
    {/if}
  </section>
{/snippet}

{#snippet notAnswered()}
  <p class="briefing-status unanswered" role="status">
    This question was not answered directly. Riprap is running without a language model here,
    so this is the evidence briefing for the place above.
  </p>
{/snippet}

<section class="hero-band">
  <div class="hero-band-inner">
    <div class="app-shell-top is-desktop" class:is-stopped={run.stopped} class:is-generating={loading}>
      <section id="region-briefing" class="app-region app-region-brief" aria-labelledby="brief-h1">
        <header class="region-head">
          <span class="section-label">Briefing</span>
        </header>
        <h1 id="brief-h1" class="brief-h1">
          Flood-exposure briefing
          <span class="brief-h1-addr">{queryText}</span>
        </h1>
        {@render notice?.()}
        {#if question}
          <p class="brief-line">Question: {question}</p>
        {/if}
        {#if run.resolvedPlace}
          <p class="brief-line resolved-place">
            <span class="brief-line-label">Briefing for:</span> {run.resolvedPlace}
          </p>
        {/if}

        {#if run.errorState}
          <ErrorCard state={run.errorState} />
        {:else}
          {#if grounding}
            <p class="region-head-meta grounding-line">
              {#if grounding.tier === 'llm'}
                {modeLine(grounding)}
              {:else}
                Evidence briefing (no LLM){#if grounding.fallback_reason}. The LLM was unavailable ({grounding.fallback_reason}), so the evidence briefing is shown.{/if}
              {/if}
            </p>
          {/if}

          {#if loading}
            <div class="generating-status">
              <span class="pulse" aria-hidden="true"></span>
              <span aria-hidden="true">{loadingText}… <span class="generating-elapsed">{elapsed} s</span></span>
              <span class="visually-hidden" aria-live="polite">{srStatus}</span>
              <p class="generating-expect">
                Briefings take from a few seconds to a few minutes; questions answered by a
                language model can take up to five minutes.
              </p>
              {#if !run.plan && run.planTokens}
                <details class="plan-details">
                  <summary>Planner streaming ({run.planTokens.length} chars)</summary>
                  <pre class="plan-stream">{run.planTokens}</pre>
                </details>
              {/if}
            </div>
            {#if run.geocodeSucceeded}
              <!-- Geocode done; the briefing arrives whole in `final`. -->
              <SkeletonBriefing />
            {/if}
          {/if}

          {#if run.plan?.intent === 'compare' && run.finalResult?.targets?.length === 2}
            <CompareBriefing
              paragraph={run.finalResult.paragraph}
              {citations}
              targets={run.finalResult.targets}
              structuredA={run.compareStepsA}
              structuredB={run.compareStepsB}
            />
            {#if showSources}{@render sources()}{/if}
          {:else}
            {#if split.lead.length}
              <Briefing blocks={split.lead} {citations} streaming={false} />
            {/if}
            {#if unanswered}{@render notAnswered()}{/if}
            {#if split.scope.length}
              <div class="scope-note"><Briefing blocks={split.scope} {citations} streaming={false} /></div>
            {/if}
            {#if showSources}{@render sources()}{/if}
            {#if split.body.length}
              <Briefing blocks={split.body} {citations} streaming={false} />
            {/if}
            {#if split.outOfScope.length}
              <div class="scope-note scope-note-end">
                <p class="scope-note-label">Out of scope</p>
                <Briefing blocks={split.outOfScope} {citations} streaming={false} />
              </div>
            {/if}
          {/if}

          <DroppedClaims claims={grounding?.dropped_claims} />
        {/if}
      </section>

      {#if !run.stopped}
      <div class="app-region-side" style="grid-area: side;">
        <aside id="region-map" class="app-region app-region-map" aria-label="Map region">
          <header class="region-head">
            <span class="section-label">Map</span>
            <!-- The map canvas, its controls and the layer list are many tab
                 stops; this jumps straight to the citations. -->
            <a class="map-skip" href="#region-cites">Skip the map</a>
            {#if run.plan?.intent === 'compare'}
              {#if !(run.compareAddressA || run.compareAddressB)}
                <span class="region-head-meta">awaiting geocode…</span>
              {/if}
            {:else if !run.address}
              <span class="region-head-meta">awaiting geocode…</span>
            {/if}
          </header>
          {#if run.plan?.intent === 'compare'}
            <div class="compare-map-stack">
              {#if run.compareAddressA}
                <div class="compare-map-place">
                  <div class="compare-map-label">A · {run.compareAddressA.label}</div>
                  <div style="position: relative;">
                    <LazyMap
                ready={!loading}
                      address={run.compareAddressA}
                      activeLayers={active}
                      sandyEmpirical={run.sandyFcA}
                      depModeled={run.depFcA}
                      syntheticPrior={run.synFcA}
                      proxy311={run.proxyFcA}
                      idaHwm={run.idaHwmFcA}
                    />
                  </div>
                </div>
              {/if}
              {#if run.compareAddressB}
                <div class="compare-map-place">
                  <div class="compare-map-label">B · {run.compareAddressB.label}</div>
                  <div style="position: relative;">
                    <LazyMap
                ready={!loading}
                      address={run.compareAddressB}
                      activeLayers={active}
                      sandyEmpirical={run.sandyFcB}
                      depModeled={run.depFcB}
                      syntheticPrior={run.synFcB}
                      proxy311={run.proxyFcB}
                      idaHwm={run.idaHwmFcB}
                    />
                  </div>
                </div>
              {/if}
            </div>
          {:else}
            <!-- Rendered before the geocode lands too, so the frame and the
                 layer list hold their space and the citations never jump. -->
            <div style="position: relative; flex: 1; min-height: 0;">
              <LazyMap
                ready={!loading}
                address={run.address}
                activeLayers={active}
                sandyEmpirical={run.sandyFc}
                depModeled={run.depFc}
                syntheticPrior={run.synFc}
                proxy311={run.proxyFc}
                idaHwm={run.idaHwmFc}
                registerPoints={run.registerPointsFc}
                terramindLulc={run.terramindLulcFc}
                terramindBuildings={run.terramindBuildingsFc}
                {linkedKey}
              />
              <MapLegend
                {active}
                featureCounts={run.mapFeatureCounts}
                onToggle={(k) => (active = { ...active, [k]: !active[k] })}
              />
            </div>
          {/if}
          <p class="map-text-note">Everything shown on the map is also listed in the briefing and the citations.</p>
        </aside>

        <!-- tabindex: the "Skip the map" target takes focus, so the next Tab
             continues inside the citations. -->
        <aside id="region-cites" class="app-region app-region-cites" aria-label="Citations" tabindex="-1">
          <CitationDrawer {citations} {snapshot} />
        </aside>
      </div>
      {/if}
    </div>

    {#if !run.stopped}
    <div class="app-shell-bottom">
      <section class="app-region app-region-findings" aria-label="Findings">
        <FindingsRegion
          data={run.findingsData}
          {density}
          {provenanceMode}
          {showGrammar}
          {linkedKey}
          onLink={(key) => (linkedKey = key)}
          onCite={handleFindingsCite}
        />
      </section>
    </div>
    {/if}
  </div>
</section>

<style>
  .grounding-line {
    margin: 0 0 12px;
  }
  .brief-line {
    margin: 0 0 8px;
    font-size: 15px;
    line-height: 1.45;
    color: var(--ink-secondary);
    max-width: 70ch;
    overflow-wrap: anywhere;
  }
  .brief-line.resolved-place {
    color: var(--ink);
    margin-bottom: 16px;
  }
  .brief-line-label {
    font-weight: 600;
  }
  .unanswered {
    max-width: 70ch;
    font-size: 15px;
    color: var(--ink);
  }
  .sources {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
    gap: 12px 24px;
    margin: 8px 0 24px;
    padding: 12px 0;
    border-top: 1px solid var(--rule-soft);
    border-bottom: 1px solid var(--rule-soft);
    max-width: 70ch;
  }
  .sources-col {
    margin: 0;
    min-width: 0;
  }
  .sources-head {
    font-family: var(--font-sans);
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
    min-height: 24px;
    line-height: 24px;
  }
  summary.sources-head {
    cursor: pointer;
  }
  summary.sources-head:hover {
    text-decoration: underline;
  }
  .sources-list {
    margin: 4px 0 0;
    padding-left: 18px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .sources-list li + li {
    margin-top: 2px;
  }
  .sources-none {
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .map-skip {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--accent);
  }
  .map-skip + .region-head-meta {
    margin-left: 12px;
  }
  .map-text-note {
    margin: 8px 0 0;
    font-size: 13px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  #region-cites:focus-visible {
    outline: none;
  }
  .sources-failed {
    color: var(--ink);
    font-weight: 600;
  }
  .generating-elapsed {
    color: var(--ink-tertiary);
    font-variant-numeric: tabular-nums;
  }
  .generating-expect {
    flex-basis: 100%;
    margin: 0;
    font-family: var(--font-sans);
    font-size: 14px;
    color: var(--ink-secondary);
    max-width: 70ch;
  }
  .compare-map-stack {
    display: flex;
    flex-direction: column;
    gap: var(--s-3, 8px);
    padding-top: 4px;
  }
  .compare-map-place {
    display: flex;
    flex-direction: column;
  }
  .compare-map-label {
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-secondary);
    padding: 2px 0 4px;
    border-bottom: 1px solid var(--rule-soft);
    margin-bottom: 4px;
  }
  .plan-details {
    border: 1px solid var(--rule-soft);
    background: var(--paper-deep);
    margin-bottom: 16px;
  }
  .plan-details summary {
    padding: 10px 14px;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-secondary);
  }
  .plan-stream {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-tertiary);
    white-space: pre-wrap;
    padding: 0 14px 12px;
    margin: 0;
    max-height: 240px;
    overflow: auto;
  }
  .generating-status {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 0;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink-secondary);
    flex-wrap: wrap;
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
</style>
