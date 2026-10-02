<script lang="ts">
  /** Landing at `/`: a Persuade page inside the report system
   *  (docs/DESIGN.md, "Landing"): one real answer in the hero, real
   *  answers as proof with who it is for, the open models, the sources by
   *  Stone, developers and MCP, one "evidence, not advice" line, and last
   *  the collaboration call. Live briefings render at /q/<query>. */
  import '$lib/components/landing/landing.css';
  import LandHero from '$lib/components/landing/LandHero.svelte';
  import LandProof from '$lib/components/landing/LandProof.svelte';
  import LandStones from '$lib/components/landing/LandStones.svelte';
  import LandDevelopers from '$lib/components/landing/LandDevelopers.svelte';
  import LandFrontier from '$lib/components/landing/LandFrontier.svelte';
  import LandCollab from '$lib/components/landing/LandCollab.svelte';
  import UseBand from '$lib/components/landing/UseBand.svelte';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();
</script>

<svelte:head>
  <title>Riprap: the flood and heat record for any New York City block, cited</title>
  <meta name="description" content="Ask about flood or heat at a New York City address or community district and get a one-page briefing in seconds, with every sentence cited to a public record and its date. Open source, open data, runs on a laptop." />
</svelte:head>

<div class="land">
  <LandHero chips={data.chips} specimen={data.specimen} count={data.count} />
  <LandProof cards={data.proof} count={data.count} />
  <LandFrontier />
  <LandStones />
  <LandDevelopers />
  <UseBand />
  <LandCollab />
</div>

<style>
  .land {
    padding-bottom: 48px;
    background: var(--paper);
    color: var(--ink);
    font-family: var(--font-sans);
  }
</style>
