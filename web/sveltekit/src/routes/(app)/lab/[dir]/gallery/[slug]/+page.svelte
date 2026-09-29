<script lang="ts">
  import BriefingA from '$lib/lab/a/BriefingA.svelte';
  import BriefingB from '$lib/lab/b/BriefingB.svelte';
  import BriefingC from '$lib/lab/c/BriefingC.svelte';
  import { RunState } from '$lib/client/runState.svelte';
  import { labModel } from '$lib/lab/labModel';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let entry = $derived(data.entry);
  let dir = $derived(data.dir);
  let run = $derived(RunState.fromFinal(entry.final, entry.address));
  let model = $derived(labModel(run, entry));
</script>

<svelte:head>
  <title>{entry.neighborhood} · Design lab {dir.toUpperCase()} · Riprap</title>
</svelte:head>

{#if dir === 'a'}
  <BriefingA {run} {model} {entry} />
{:else if dir === 'b'}
  <BriefingB {run} {model} {entry} />
{:else}
  <BriefingC {run} {model} {entry} />
{/if}
