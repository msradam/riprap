<script lang="ts">
  import type {
    Card, Density, FindingsData, ProvenanceMode, StoneKey, StoneTrace
  } from '$lib/types/card';
  import { STONE_ORDER } from '$lib/types/card';
  import RunHealthStrip from './RunHealthStrip.svelte';
  import StoneRegion from './StoneRegion.svelte';
  import CardGrammarReference from './CardGrammarReference.svelte';

  /** Findings region: 5 Stones in canonical order, top-banner run-health
   *  strip, optional dev-only card-grammar catalog. linkedKey is owned by
   *  the parent route (`q/[queryId]/+page.svelte` or `q/sample/+page.svelte`)
   *  so the briefing's map can read it without a store. */
  interface Props {
    data: FindingsData;
    density?: Density;
    provenanceMode?: ProvenanceMode;
    showGrammar?: boolean;
    linkedKey?: string | null;
    onCite?: (citeId: string) => void;
    onLink?: (key: string | null) => void;
    /** Doc ids the briefing text cites. Cards for these restate the
     *  briefing, so they stay collapsed until the reader asks for them. */
    citedDocIds?: Set<string>;
  }

  let {
    data,
    density = 'comfortable',
    provenanceMode = 'smart',
    showGrammar = false,
    linkedKey = null,
    onCite,
    onLink,
    citedDocIds = new Set(),
  }: Props = $props();

  const isStated = (c: Card) =>
    citedDocIds.has(c.docId) || (!!c.citeId && citedDocIds.has(c.citeId));
  let hiddenCards = $derived(data.cards.filter(isStated));
  /** Collapsed again whenever a new run's data arrives; never persisted. */
  let showAll = $derived.by(() => (void data, false));

  /** A hover that links a collapsed card reveals every card first. */
  function link(key: string | null) {
    if (key && !showAll && hiddenCards.some((c) => c.mapLayer === key)) showAll = true;
    onLink?.(key);
  }

  // Index cards by Stone, keep order from `data.cards`.
  let cardsByStone = $derived.by<Record<StoneKey, Card[]>>(() => {
    const out: Record<StoneKey, Card[]> = {
      cornerstone: [], keystone: [], touchstone: [], lodestone: [], capstone: [],
    };
    for (const c of data.cards) out[c.stone].push(c);
    // Findings first; sources that produced nothing go to the end.
    for (const k of STONE_ORDER) out[k].sort((a, b) => Number(!!a.absent) - Number(!!b.absent));
    return out;
  });

  // Index traces by Stone with safe defaults so a missing Stone still
  // renders an empty region rather than crashing.
  let tracesByStone = $derived.by<Record<StoneKey, StoneTrace>>(() => {
    const out: Record<StoneKey, StoneTrace> = {
      cornerstone: { key: 'cornerstone', members: [] },
      keystone:    { key: 'keystone', members: [] },
      touchstone:  { key: 'touchstone', members: [] },
      lodestone:   { key: 'lodestone', members: [] },
      capstone:    { key: 'capstone', members: [] },
    };
    for (const t of data.stones) out[t.key] = t;
    return out;
  });
</script>

<section class="findings" aria-label="Findings, grouped by Stone">
  <header class="findings-head">
    <h2 class="findings-h2">Findings · grouped by Stone</h2>
    <span class="findings-tagline">cards = what each Stone found · provenance collapses below</span>
  </header>

  {#if hiddenCards.length}
    <button
      type="button"
      class="evidence-toggle"
      aria-expanded={showAll}
      aria-controls="findings-stones"
      onclick={() => (showAll = !showAll)}
    >
      {showAll ? 'Show fewer evidence cards' : `Show all evidence cards (${hiddenCards.length} more)`}
    </button>
  {/if}

  <RunHealthStrip
    cards={data.cards}
    stones={data.stones}
    wallSeconds={data.wallSeconds}
    cacheHit={data.cacheHit}
    emissions={data.emissions}
  />

  <div id="findings-stones">
    {#each STONE_ORDER as key (key)}
      {@const all = cardsByStone[key]}
      {@const cards = showAll ? all : all.filter((c) => !isStated(c))}
      <StoneRegion
        stone={key}
        {cards}
        hiddenCount={all.length - cards.length}
        trace={tracesByStone[key]}
        {density}
        {provenanceMode}
        {linkedKey}
        {onCite}
        onLink={link}
      />
    {/each}
  </div>

  {#if showGrammar}
    <CardGrammarReference {density} />
  {/if}
</section>

<style>
  .findings {
    background: var(--paper);
    color: var(--ink);
  }
  .findings-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--s-3);
    padding: var(--s-3) 0 var(--s-2);
  }
  .findings-h2 {
    margin: 0;
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 22px;
    font-weight: 500;
    color: var(--ink);
  }
  .evidence-toggle {
    background: transparent;
    border: 0;
    padding: 4px 0;
    min-height: 24px; /* WCAG 2.5.8 target size */
    margin-bottom: var(--s-2);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-secondary);
    letter-spacing: 0.05em;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .evidence-toggle:hover { color: var(--ink); }
  .findings-tagline {
    font-family: var(--font-mono);
    font-size: 12px;
    min-width: 0;
    overflow-wrap: anywhere;
    color: var(--ink-tertiary);
    letter-spacing: 0.05em;
  }
</style>
