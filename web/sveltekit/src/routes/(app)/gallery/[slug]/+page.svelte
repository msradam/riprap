<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import ResultsView from '$lib/components/results/ResultsView.svelte';
  import { RunState } from '$lib/client/runState.svelte';
  import { galleryIndex, liveQuery, llmStamp, withGrounding } from '$lib/client/gallery';
  import { persistSnapshot } from '$lib/stores/briefingState.svelte';
  import { snapshotFromRun } from '$lib/client/briefingModel';
  import { hazardLabel, isHeat } from '$lib/client/agentStream';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let entry = $derived(data.entry);
  // Rebuilt from the saved `final` payload: no EventSource, no fetch.
  let run = $derived(RunState.fromFinal(entry.final, entry.address));
  // A question entry is titled with its question, which a refusal's
  // `final` does not carry (no plan question, no grounding question).
  let queryText = $derived(entry.question ?? entry.address);
  // A refusal points to the gallery's evidence briefing for the same address.
  let sibling = $derived(run.refused
    ? galleryIndex.find((e) => e.slug !== entry.slug && !e.question && e.address === entry.address) ?? null
    : null);
  // A bare-place entry links to the same place's briefing for the other
  // hazard, when the gallery holds one.
  let heat = $derived(isHeat(run.plan));
  let other = $derived(entry.question
    ? null
    : galleryIndex.find((e) => !e.question && e.address === entry.address && (e.hazard === 'heat') !== heat) ?? null);
  let meta = $derived({ generatedAt: entry.generated_at, commit: entry.riprap_commit, stamp: llmStamp(withGrounding(entry, entry.final.grounding)) });

  /** Save this entry as a print snapshot and open the print route. The
   *  id is what a reader would type to run the same briefing live ("heat
   *  QN12" for a bare heat entry), so the print route's "run this
   *  briefing" fallback starts the same briefing, and a place's heat and
   *  flood entries do not share a snapshot key. */
  function print() {
    const id = liveQuery(entry);
    persistSnapshot(snapshotFromRun(run, id, queryText, entry.generated_at, 'gallery'));
    goto(resolve('/(app)/print/[queryId]', { queryId: encodeURIComponent(id) }));
  }
</script>

<svelte:head>
  <title>{entry.neighborhood}: Riprap gallery</title>
  <!-- A question entry is described by its question: a refusal is not a
       briefing for the address. -->
  <meta
    name="description"
    content={entry.question
      ? `Precomputed Riprap gallery entry: ${entry.question}`
      : `Precomputed Riprap ${hazardLabel(run.plan).toLowerCase()} for ${entry.address}.`}
  />
</svelte:head>

<ResultsView {run} {queryText} snapshot {meta}>
  {#snippet notice()}
    {#if sibling}
      <p class="snapshot-sibling">
        Riprap's evidence briefing for this address:
        <a href="{resolve('/(app)/gallery/[slug]', { slug: sibling.slug })}/">{sibling.neighborhood}</a>
      </p>
    {/if}
    {#if other}
      <p class="snapshot-sibling">
        <a href="{resolve('/(app)/gallery/[slug]', { slug: other.slug })}/">{heat ? 'Flood' : 'Heat'} briefing for this place</a>
      </p>
    {/if}
    <button type="button" class="snapshot-print" onclick={print}>Print this briefing</button>
  {/snippet}
  {#snippet footer()}
    <a class="snapshot-all" href="{resolve('/(app)/gallery')}/">All gallery entries</a>
  {/snippet}
</ResultsView>

<style>
  .snapshot-sibling {
    margin: 0 0 8px;
  }
  .snapshot-all {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
  }
  .snapshot-print {
    min-height: 24px;
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    color: var(--riprap-text-link);
    text-decoration: underline;
    cursor: pointer;
  }
  .snapshot-print:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
</style>
