<script lang="ts">
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { STATIC_SITE, QUICKSTART_URL } from '$lib/staticSite';
</script>

<svelte:head>
  <title>Riprap: {page.status === 404 ? 'page not found' : 'error'}</title>
</svelte:head>

<div class="error-page">
  <h1>{page.status}: {page.error?.message ?? 'Something went wrong'}</h1>
  <p><a href="{resolve('/(app)/gallery')}/">Read the precomputed briefings in the gallery</a></p>
  {#if STATIC_SITE}
    <p><a href={QUICKSTART_URL}>Run locally to ask your own question</a></p>
  {:else}
    <p><a href={resolve('/')}>Ask a new question</a></p>
  {/if}
</div>

<style>
  .error-page {
    max-width: 600px;
    margin: 80px auto;
    padding: 0 16px;
    font-family: var(--font-sans);
    color: var(--ink);
  }
  .error-page h1 {
    font-size: 24px;
    line-height: 1.2;
    margin: 0 0 16px;
  }
  .error-page a {
    display: inline-block;
    min-height: 24px;
    color: var(--accent);
    text-underline-offset: 2px;
  }
</style>
