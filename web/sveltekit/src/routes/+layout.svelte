<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import AppHeader from '$lib/components/shell/AppHeader.svelte';
  import AppFooter from '$lib/components/shell/AppFooter.svelte';
  import SkipLinks from '$lib/components/shell/SkipLinks.svelte';
  import { page } from '$app/state';
  import { resolve } from '$app/paths';

  interface Props { children: Snippet; }
  let { children }: Props = $props();

  // Route params arrive decoded; no second decodeURIComponent.
  let query = $derived(page.params.queryId || null);

  // The landing at / and the print artifact at /print/<id> both bring
  // their own chrome, so the layout's AppHeader / AppFooter sit out
  // for those. Briefings at /q/<id> still get the app chrome.
  let isPrint = $derived(page.route.id?.startsWith('/print/') ?? false);
  let isLanding = $derived(page.route.id === '/');
  let chromeFree = $derived(isPrint || isLanding);
  // Gallery pages are static snapshots: the header must not call /api/*.
  let isGallery = $derived(page.route.id?.startsWith('/gallery') ?? false);
</script>

{#if !chromeFree}
  <SkipLinks />
  <AppHeader {query} offline={isGallery} onResetCold={() => (window.location.href = resolve('/'))} />
{/if}
<main>{@render children()}</main>
{#if !chromeFree}
  <AppFooter />
{/if}

<style>
  main {
    min-height: calc(100vh - 200px);
  }
</style>
