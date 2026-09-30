<script lang="ts">
  /** Landing at `/`: a front page at report restraint (docs/DESIGN.md,
   *  "Landing"). The query box and examples, the gallery as stories, what
   *  a briefing contains, then the cities and responsible use as quiet
   *  sections. Live briefings render at /q/<query>. */
  import LandHero from '$lib/components/landing/LandHero.svelte';
  import LandStories from '$lib/components/landing/LandStories.svelte';
  import LandStones from '$lib/components/landing/LandStones.svelte';
  import CityPicker from '$lib/components/landing/CityPicker.svelte';
  import UseBand from '$lib/components/landing/UseBand.svelte';
  import { STATIC_SITE } from '$lib/staticSite';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();
</script>

<svelte:head>
  <title>Riprap: flood-exposure briefings for New York City</title>
  <meta name="description" content="Riprap composes federal, state, and city open data into a written flood-exposure briefing in which every claim cites a public record. Open source, Apache-2.0. New York City is in production; Chicago, Seattle, San Francisco, Boston and Albany are experimental." />
</svelte:head>

<div class="land">
  <div class="land-page">
    <LandHero />
    <LandStories stories={data.stories} />
    <LandStones />
    <!-- City samples run a live briefing: not on the static site. -->
    {#if !STATIC_SITE}
      <CityPicker />
    {/if}
    <UseBand />
  </div>
</div>

<style>
  .land {
    background: var(--paper);
    color: var(--ink);
    font-family: var(--font-sans);
  }
  .land-page {
    max-width: 1040px;
    margin: 0 auto;
    padding: 0 32px 96px;
  }
  @media (max-width: 640px) {
    .land-page {
      padding: 0 16px 48px;
    }
  }
</style>
