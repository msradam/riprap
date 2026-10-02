<script lang="ts">
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { STATIC_SITE, QUICKSTART_URL } from '$lib/staticSite';

  let notFound = $derived(page.status === 404);
</script>

<svelte:head>
  <title>Riprap: {notFound ? 'page not found' : 'error'}</title>
  <meta name="description" content="Riprap: cited flood and heat briefings for New York City places, from public data. Open source, Apache-2.0." />
</svelte:head>

<div class="error-page">
  <p class="error-kind">Error <span class="data">{page.status}</span></p>
  <h1>{notFound ? 'There is no page at this address.' : (page.error?.message ?? 'Something went wrong.')}</h1>
  <ul>
    <li><a href="{resolve('/(app)/gallery')}/">Read the precomputed briefings in the gallery</a></li>
    {#if STATIC_SITE}
      <li><a href={QUICKSTART_URL}>Run locally to ask your own question</a></li>
    {:else}
      <li><a href={resolve('/')}>Ask a new question</a></li>
    {/if}
  </ul>
</div>

<style>
  .error-page {
    max-width: 680px;
    margin: 64px auto 96px;
    padding: 0 32px;
    font-family: var(--font-sans);
    color: var(--ink);
  }
  .error-kind {
    margin: 0 0 4px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .error-page h1 {
    margin: 0 0 16px;
    max-width: 30ch;
    font-size: 34px;
    font-weight: 600;
    line-height: 1.18;
    letter-spacing: -0.01em;
    text-wrap: balance;
  }
  .error-page ul {
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 17px;
    line-height: 1.55;
  }
  .error-page li + li {
    margin-top: 8px;
  }
  .error-page a {
    display: inline-block;
    min-height: 24px;
    color: var(--riprap-text-link);
    text-underline-offset: 3px;
  }
  .error-page a:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  @media (max-width: 640px) {
    .error-page {
      margin-top: 32px;
      padding: 0 16px;
    }
    .error-page h1 {
      font-size: 26px;
    }
  }
</style>
