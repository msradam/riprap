<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import AppHeader from '$lib/components/shell/AppHeader.svelte';
  import AppFooter from '$lib/components/shell/AppFooter.svelte';
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

  // Every page but the print artifact at /print/<id> gets the app chrome
  // (styled by lib/chrome.css in the base sheet), the landing included.
  let routeId = $derived(page.route.id ?? '');
  let chromeFree = $derived(routeId.startsWith('/(app)/print/'));
  let isLanding = $derived(routeId === '/');
  // The landing and the gallery need no backend: the header must not call
  // /api/*. Briefing pages carry the disclaimer in their scope note and
  // the landing in its "evidence, not advice" section; the footer does not
  // repeat it.
  let isBriefing = $derived(routeId.startsWith('/(app)/q/') || routeId === '/(app)/gallery/[slug]');
  let isGallery = $derived(routeId.startsWith('/(app)/gallery'));
  // The about and accessibility pages: static, and about New York City.
  let isSitePage = $derived(routeId.startsWith('/(site)/'));

  // The run status lives in a module store that outlives the /q/ page, so
  // a refused run's "stopped" pill followed the reader into the gallery.
  // Pages that show no live run start from idle.
  afterNavigate(({ to }) => {
    const id = to?.route.id ?? '';
    if (id === '/' || id.startsWith('/(app)/gallery') || id.startsWith('/(site)/')) briefingState.reset();
  });
</script>

<svelte:head>
  {#each [sofia400, sofia600, mono500] as href (href)}
    <link rel="preload" as="font" type="font/woff2" {href} crossorigin="anonymous" />
  {/each}
</svelte:head>

{#if !chromeFree}
  <!-- USWDS skip link: hidden until focused, never display:none. -->
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <AppHeader {query} offline={isGallery || isLanding || isSitePage} onResetCold={() => (window.location.href = query ? `${resolve('/')}?q=${encodeURIComponent(query)}` : resolve('/'))} />
{/if}
<main id={chromeFree ? undefined : 'main-content'} tabindex="-1">{@render children()}</main>
{#if !chromeFree}
  <AppFooter disclaimer={!isBriefing && !isLanding} nycPage={isLanding || isGallery || isSitePage} />
{/if}

<style>
  .skip-link {
    position: absolute;
    left: -9999px;
    top: 8px;
    padding: 8px 12px;
    background: var(--ink);
    color: var(--paper);
    font-family: var(--font-sans);
    font-size: 14px;
    z-index: 1000;
    text-decoration: none;
  }
  .skip-link:focus,
  .skip-link:focus-visible {
    left: 8px;
    outline: 3px solid var(--accent);
    outline-offset: 2px;
  }
  main {
    min-height: calc(100vh - 200px);
  }
  /* Skip-link target, not a control: no ring around the whole page. */
  main:focus-visible {
    outline: none;
  }
</style>
