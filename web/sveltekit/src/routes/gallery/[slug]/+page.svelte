<script lang="ts">
  import { resolve } from '$app/paths';
  import ResultsView from '$lib/components/results/ResultsView.svelte';
  import { RunState } from '$lib/client/runState.svelte';
  import { formatGeneratedAt, llmStamp } from '$lib/client/gallery';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let entry = $derived(data.entry);
  // Rebuilt from the saved `final` payload: no EventSource, no fetch.
  let run = $derived(RunState.fromFinal(entry.final, entry.address));
  let stamp = $derived(llmStamp(entry));
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
  {/snippet}
</ResultsView>

<style>
  .snapshot-note {
    margin: 0 0 12px;
  }
</style>
