<script lang="ts">
  import type { Snippet } from 'svelte';
  import Briefing from '$lib/components/briefing/Briefing.svelte';
  import CompareBriefing from '$lib/components/briefing/CompareBriefing.svelte';
  import CitationDrawer from '$lib/components/briefing/CitationDrawer.svelte';
  import DroppedClaims from '$lib/components/briefing/DroppedClaims.svelte';
  import RipMap from '$lib/components/map/RipMap.svelte';
  import MapLegend from '$lib/components/map/MapLegend.svelte';
  import SkeletonBriefing from '$lib/components/states/SkeletonBriefing.svelte';
  import ErrorCard from '$lib/components/states/ErrorCard.svelte';
  import FindingsRegion from '$lib/components/findings/FindingsRegion.svelte';
  import type { Density, ProvenanceMode } from '$lib/types/card';
  import type { RunState } from '$lib/client/runState.svelte';
  import type { SourceRef } from '$lib/client/agentStream';
  import { briefingState } from '$lib/stores/briefingState.svelte';
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
  let question = $derived(run.plan?.question || grounding?.question || '');
  let consulted = $derived(run.finalResult?.consulted ?? []);
  let notChecked = $derived(run.finalResult?.not_checked ?? []);

  function handleFindingsCite() {
    document.getElementById('region-cites')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
</script>

{#snippet sourceList(label: string, items: SourceRef[])}
  {#if items.length}
    <details class="region-head-meta grounding-line">
      <summary>{label} ({items.length})</summary>
      <ul>
        {#each items as s (s.id)}
          <li>{s.title}</li>
        {/each}
      </ul>
    </details>
  {/if}
{/snippet}

<section class="hero-band">
  <div class="hero-band-inner">
    <div class="app-shell-top is-desktop">
      <main id="region-briefing" class="app-region app-region-brief" aria-labelledby="brief-h1">
        <header class="region-head">
          <span class="section-label">Briefing</span>
        </header>
        <h1 id="brief-h1" class="brief-h1">
          Flood-exposure briefing
          <span class="brief-h1-addr">{queryText}</span>
        </h1>
        {@render notice?.()}
        {#if question}
          <p class="grounding-line">Question: {question}</p>
        {/if}

        {#if run.errorState}
          <ErrorCard state={run.errorState} />
        {:else}
          {#if grounding}
            <p class="region-head-meta grounding-line">
              {#if grounding.tier === 'llm'}
                LLM claims checked against cited sources: {grounding.claims?.length ?? 0} kept, {grounding.dropped_claims?.length ?? 0} dropped{#if grounding.model}&nbsp;({grounding.model}){/if}
              {:else}
                Evidence briefing (no LLM){#if grounding.fallback_reason}. The LLM was unavailable ({grounding.fallback_reason}), so the evidence briefing is shown.{/if}
              {/if}
            </p>
          {/if}

          {#if run.plan?.intent === 'compare' && run.finalResult?.targets?.length === 2}
            <CompareBriefing
              paragraph={run.finalResult.paragraph}
              {citations}
              targets={run.finalResult.targets}
              structuredA={run.compareStepsA}
              structuredB={run.compareStepsB}
            />
          {:else if blocks.length}
            <Briefing {blocks} {citations} streaming={false} />
          {:else if run.geocodeSucceeded && !run.finalResult}
            <!-- Geocode done; the briefing arrives whole in `final`. -->
            <SkeletonBriefing />
          {:else if !run.plan}
            <div class="generating-status" aria-live="polite">
              <span class="pulse"></span> Planning intent…
              {#if run.planTokens}
                <details class="plan-details">
                  <summary>Planner streaming ({run.planTokens.length} chars)</summary>
                  <pre class="plan-stream">{run.planTokens}</pre>
                </details>
              {/if}
            </div>
          {:else if !run.finalResult}
            <!-- Mirrors StatusPill's phase logic. -->
            <div class="generating-status" aria-live="polite">
              <span class="pulse"></span>
              {#if briefingState.phase === 'specialists'}
                Gathering evidence{#if briefingState.totalSpecialists}
                  ({briefingState.firedCount}/{briefingState.totalSpecialists}){/if}…
              {:else if briefingState.phase === 'reconciling'}
                Reconciling…
              {:else if briefingState.phase === 'error'}
                Error{#if briefingState.errorMessage}: {briefingState.errorMessage}{/if}
              {:else}
                Resolving address…
              {/if}
            </div>
          {/if}

          {@render sourceList('Sources consulted', consulted)}
          {@render sourceList('Not checked', notChecked)}

          <DroppedClaims claims={grounding?.dropped_claims} />
        {/if}
      </main>

      <div class="app-region-side" style="grid-area: side;">
        <aside id="region-map" class="app-region app-region-map" aria-label="Map region">
          <header class="region-head">
            <span class="section-label">Map</span>
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
                    <RipMap
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
                    <RipMap
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
          {:else if run.address}
            <div style="position: relative; flex: 1; min-height: 0;">
              <RipMap
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
        </aside>

        <aside id="region-cites" class="app-region app-region-cites" aria-label="Citations">
          <CitationDrawer {citations} {snapshot} />
        </aside>
      </div>
    </div>

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
  </div>
</section>

<style>
  .grounding-line {
    margin: 0 0 12px;
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
    font-size: 11px;
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
    font-size: 11px;
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
