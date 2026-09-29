<script lang="ts">
  /** Landing at `/`: a front page at report restraint (docs/DESIGN.md,
   *  "Landing"). The query box and examples, the gallery as stories, what
   *  a briefing contains, then the cities, bring-your-own-data and
   *  responsible use as quiet sections. Live briefings render at /q/<query>. */
  import { onMount } from 'svelte';
  import SkipLink from '$lib/components/shell/SkipLink.svelte';
  import LandHeader from '$lib/components/landing/LandHeader.svelte';
  import LandHero from '$lib/components/landing/LandHero.svelte';
  import LandStories from '$lib/components/landing/LandStories.svelte';
  import LandStones from '$lib/components/landing/LandStones.svelte';
  import CityPicker from '$lib/components/landing/CityPicker.svelte';
  import UseBand from '$lib/components/landing/UseBand.svelte';
  import LandFooter from '$lib/components/landing/LandFooter.svelte';
  import { byodRegistry } from '$lib/stores/byodRegistry.svelte';
  import { STATIC_SITE } from '$lib/staticSite';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let byodOpen = $state(false);

  // Load the BYOD registry so the trigger can say how many files are
  // already stored in this browser.
  onMount(() => {
    if (!STATIC_SITE && !byodRegistry.loaded) void byodRegistry.load();
  });
</script>

<svelte:head>
  <title>Riprap: flood-exposure briefings for New York City</title>
  <meta name="description" content="Riprap composes federal, state, and city open data into a written flood-exposure briefing in which every claim cites a public record. Open source, Apache-2.0. New York City is in production; Chicago, Seattle, San Francisco, Boston and Albany are experimental." />
</svelte:head>

<SkipLink />

<div class="land">
  <LandHeader />
  <div class="land-page" id="main-content">
    <LandHero />
    <LandStories stories={data.stories} />
    <LandStones />
    <!-- City samples and BYOD both run a live briefing: not on the static site. -->
    {#if !STATIC_SITE}
      <CityPicker />
      <section class="land-byod" aria-labelledby="byod-h">
        <h2 id="byod-h">Your own data</h2>
        <p>Files stay in your browser. No upload.</p>
        <button type="button" onclick={() => (byodOpen = true)}>
          Bring your own data{#if byodRegistry.entries.length > 0}&nbsp;({byodRegistry.entries.length} saved){/if}
        </button>
      </section>
    {/if}
    <UseBand />
  </div>
  <LandFooter />

  <!-- Loaded on first open: it brings js-yaml and papaparse, which the
       landing's first view does not need. -->
  {#if byodOpen}
    {#await import('$lib/components/landing/ByodDialog.svelte') then { default: ByodDialog }}
      <ByodDialog open onClose={() => (byodOpen = false)} />
    {/await}
  {/if}
</div>

<style>
  .land {
    min-height: 100vh;
    background: var(--paper);
    color: var(--ink);
    font-family: var(--font-sans);
  }
  .land-page {
    max-width: 1040px;
    margin: 0 auto;
    padding: 0 32px;
  }
  .land-byod {
    margin-top: 64px;
    max-width: 60ch;
  }
  .land-byod h2 {
    margin: 0 0 8px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }
  .land-byod p {
    margin: 0 0 8px;
    font-size: 17px;
    line-height: 1.55;
  }
  .land-byod button {
    min-height: 24px;
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    font-size: 17px;
    color: var(--riprap-text-link);
    text-decoration: underline;
    text-underline-offset: 0.2em;
    cursor: pointer;
  }
  .land-byod button:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  @media (max-width: 640px) {
    .land-page {
      padding: 0 16px;
    }
    .land-byod {
      margin-top: 48px;
    }
  }
</style>
