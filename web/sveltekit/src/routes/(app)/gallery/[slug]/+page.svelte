<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import ResultsView from '$lib/components/results/ResultsView.svelte';
  import { RunState } from '$lib/client/runState.svelte';
  import { galleryIndex, llmStamp } from '$lib/client/gallery';
  import { persistSnapshot } from '$lib/stores/briefingState.svelte';
  import { snapshotFromRun } from '$lib/client/briefingModel';
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
  let meta = $derived({ generatedAt: entry.generated_at, commit: entry.riprap_commit, stamp: llmStamp(entry) });

  /** Save this entry as a print snapshot and open the print route. The
   *  id is what a reader would type to run the same briefing live, so the
   *  print route's "run this briefing" fallback leads somewhere sensible. */
  function print() {
    const id = entry.question ?? entry.address;
    persistSnapshot(snapshotFromRun(run, id, queryText, entry.generated_at, 'gallery'));
    goto(resolve('/(app)/print/[queryId]', { queryId: encodeURIComponent(id) }));
  }
</script>

<svelte:head>
  <title>{entry.neighborhood}: Riprap gallery</title>
  <!-- A question entry is described by its question: a refusal is not a
       flood-exposure briefing for the address. -->
  <meta
    name="description"
    content={entry.question
      ? `Precomputed Riprap gallery entry: ${entry.question}`
      : `Precomputed Riprap flood-exposure briefing for ${entry.address}.`}
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
