<script lang="ts">
  /** Landing at `/`: a Persuade page inside the report system
   *  (docs/DESIGN.md, "Landing"). It widens in scale: one real answer in
   *  the hero, real answers as proof, the sources by Stone, who it is for,
   *  developers and MCP, the experimental models, how to collaborate, and
   *  evidence, not advice. Live briefings render at /q/<query>. */
  import '$lib/components/landing/landing.css';
  import LandHero from '$lib/components/landing/LandHero.svelte';
  import LandProof from '$lib/components/landing/LandProof.svelte';
  import LandStones from '$lib/components/landing/LandStones.svelte';
  import LandFor from '$lib/components/landing/LandFor.svelte';
  import LandDevelopers from '$lib/components/landing/LandDevelopers.svelte';
  import LandFrontier from '$lib/components/landing/LandFrontier.svelte';
  import LandCollab from '$lib/components/landing/LandCollab.svelte';
  import UseBand from '$lib/components/landing/UseBand.svelte';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();
</script>

<svelte:head>
  <title>Riprap: the flood record for any New York City block, cited</title>
  <meta name="description" content="Ask about a New York City address, community district or flood question and get a one-page briefing in seconds, with every sentence cited to a public record and its date. Open source, open data, runs on a laptop." />
</svelte:head>

<div class="land">
  <LandHero chips={data.chips} specimen={data.specimen} count={data.count} />
  <LandProof cards={data.proof} count={data.count} />
  <LandStones />
  <LandFor />
  <LandDevelopers />
  <LandFrontier />
  <LandCollab />
  <UseBand />
</div>

<style>
  .land {
    padding-bottom: 48px;
    background: var(--paper);
    color: var(--ink);
    font-family: var(--font-sans);
  }
</style>
