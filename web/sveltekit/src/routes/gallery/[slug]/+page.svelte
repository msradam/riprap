<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import ResultsView from '$lib/components/results/ResultsView.svelte';
  import { RunState } from '$lib/client/runState.svelte';
  import { formatGeneratedAt, llmStamp } from '$lib/client/gallery';
  import { persistSnapshot, snapshotFromRun } from '$lib/stores/briefingState.svelte';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let entry = $derived(data.entry);
  // Rebuilt from the saved `final` payload: no EventSource, no fetch.
  let run = $derived(RunState.fromFinal(entry.final, entry.address));
  let stamp = $derived(llmStamp(entry));

  /** Save this entry as a print snapshot and open the print route. The
   *  id is what a reader would type to run the same briefing live, so the
   *  print route's "run this briefing" fallback leads somewhere sensible. */
  function print() {
    const id = entry.question ?? entry.address;
    persistSnapshot(snapshotFromRun(run, id, entry.address, entry.generated_at));
    goto(resolve('/print/[queryId]', { queryId: encodeURIComponent(id) }));
  }
</script>

<svelte:head>
  <title>{entry.neighborhood} · Riprap gallery</title>
  <meta name="description" content="Precomputed Riprap flood-exposure briefing for {entry.address}." />
</svelte:head>

<ResultsView {run} queryText={entry.address} snapshot>
  {#snippet notice()}
    <p class="region-head-meta snapshot-note">
      Precomputed snapshot, generated {formatGeneratedAt(entry.generated_at)} from Riprap
      commit {entry.riprap_commit}. Live readings (tides, alerts, sensors) are as of that time.
      {#if stamp}{stamp}.{/if}
      <a href="{resolve('/gallery')}/">All gallery entries</a>
    </p>
    <p class="snapshot-actions">
      <button type="button" class="region-action" onclick={print}>Print this briefing</button>
    </p>
  {/snippet}
</ResultsView>

<style>
  .snapshot-note {
    margin: 0 0 12px;
  }
  .snapshot-actions {
    margin: 0 0 16px;
  }
  .snapshot-actions .region-action {
    min-height: 28px;
    font-size: 12px;
  }
</style>
