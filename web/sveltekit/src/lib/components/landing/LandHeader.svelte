<script lang="ts">
  /** Landing header: the wordmark and two plain links, in the app header's
   *  lower-case register. */
  import RipMark from '$lib/components/shell/RipMark.svelte';
  import { resolve } from '$app/paths';
</script>

<header class="land-header">
  <span class="riprap-wordmark"><RipMark size={20} />riprap</span>
  <nav class="land-header-nav" aria-label="Site">
    <a href="#methodology">methodology</a>
    <a href="{resolve('/(app)/gallery')}/">gallery</a>
  </nav>
</header>

<style>
  .land-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px 16px;
    max-width: 1040px;
    margin: 0 auto;
    padding: 20px 32px;
  }
  .land-header-nav {
    display: flex;
    gap: 20px;
    font-size: 14px;
  }
  .land-header-nav a {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    color: var(--riprap-text-link);
    text-underline-offset: 0.2em;
  }
  .land-header-nav a:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  @media (max-width: 640px) {
    .land-header {
      padding: 14px 16px;
    }
  }
</style>
