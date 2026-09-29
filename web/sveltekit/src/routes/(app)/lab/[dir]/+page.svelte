<script lang="ts">
  import LandingA from '$lib/lab/a/LandingA.svelte';
  import LandingB from '$lib/lab/b/LandingB.svelte';
  import LandingC from '$lib/lab/c/LandingC.svelte';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();
</script>

<svelte:head>
  <title>Design lab {data.dir.toUpperCase()} · Riprap</title>
</svelte:head>

{#if data.dir === 'a'}
  <LandingA stories={data.stories} />
{:else if data.dir === 'b'}
  <LandingB stories={data.stories} />
{:else}
  <LandingC stories={data.stories} />
{/if}
