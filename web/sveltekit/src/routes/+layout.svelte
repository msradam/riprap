<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import AppHeader from '$lib/components/shell/AppHeader.svelte';
  import AppFooter from '$lib/components/shell/AppFooter.svelte';
  import SkipLink from '$lib/components/shell/SkipLink.svelte';
  import { briefingState } from '$lib/stores/briefingState.svelte';
  import { afterNavigate } from '$app/navigation';
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  // The first view of every page sets its text in these three faces; the
  // other weights load on demand through app.css (font-display: swap).
  import sofia400 from '@fontsource/sofia-sans/files/sofia-sans-latin-400-normal.woff2?url';
  import sofia600 from '@fontsource/sofia-sans/files/sofia-sans-latin-600-normal.woff2?url';
  import mono500 from '@fontsource/overpass-mono/files/overpass-mono-latin-500-normal.woff2?url';

  interface Props { children: Snippet; }
  let { children }: Props = $props();

  // Route params arrive decoded; no second decodeURIComponent.
  let query = $derived(page.params.queryId || null);

  // The landing at / and the print artifact at /print/<id> both bring
  // their own chrome, so the layout's AppHeader / AppFooter sit out
  // for those. Briefings at /q/<id> and error pages still get the app
  // chrome (styled by lib/chrome.css in the base sheet).
  let routeId = $derived(page.route.id ?? '');
  let isPrint = $derived(routeId.startsWith('/(app)/print/'));
  let chromeFree = $derived(isPrint || routeId === '/');
  // Gallery pages are static snapshots: the header must not call /api/*.
  let isGallery = $derived(routeId.startsWith('/(app)/gallery'));

  // The run status lives in a module store that outlives the /q/ page, so
  // a refused run's "stopped" pill followed the reader into the gallery.
  // Pages that show no live run start from idle.
  afterNavigate(({ to }) => {
    const id = to?.route.id ?? '';
    if (id === '/' || id.startsWith('/(app)/gallery')) briefingState.reset();
  });
</script>

<svelte:head>
  {#each [sofia400, sofia600, mono500] as href (href)}
    <link rel="preload" as="font" type="font/woff2" {href} crossorigin="anonymous" />
  {/each}
</svelte:head>

{#if !chromeFree}
  <SkipLink />
  <AppHeader {query} offline={isGallery} onResetCold={() => (window.location.href = query ? `${resolve('/')}?q=${encodeURIComponent(query)}` : resolve('/'))} />
{/if}
<!-- The landing sets its own skip target (.land-page), so main only carries the skip-link id on app routes. -->
<main id={chromeFree ? undefined : 'main-content'} tabindex="-1">{@render children()}</main>
{#if !chromeFree}
  <AppFooter />
{/if}

<style>
  main {
    min-height: calc(100vh - 200px);
  }
  /* Skip-link target, not a control: no ring around the whole page. */
  main:focus-visible {
    outline: none;
  }
</style>
