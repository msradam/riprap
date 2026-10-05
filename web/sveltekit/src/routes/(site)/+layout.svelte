<script lang="ts">
  // The site's own pages of prose (about, accessibility): one column at a
  // reading measure, in the landing's type sizes.
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();
</script>

<article class="site-doc">{@render children()}</article>

<style>
  .site-doc {
    max-width: 760px;
    margin: 48px auto 96px;
    padding: 0 32px;
    font-family: var(--font-sans);
    font-size: 17px;
    line-height: 1.55;
    color: var(--ink);
  }
  .site-doc :global(.site-kind) {
    margin: 0 0 4px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .site-doc :global(h1) {
    margin: 0 0 16px;
    font-size: 34px;
    font-weight: 600;
    line-height: 1.18;
    letter-spacing: -0.01em;
    text-wrap: balance;
  }
  .site-doc :global(h2) {
    margin: 40px 0 8px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
    /* The sticky header covers the top of a section reached by #id. */
    scroll-margin-top: 72px;
  }
  .site-doc :global(p),
  .site-doc :global(ul) {
    margin: 0 0 12px;
    max-width: 68ch;
  }
  .site-doc :global(ul) {
    padding-left: 20px;
  }
  .site-doc :global(li) {
    margin-bottom: 6px;
  }
  .site-doc :global(.site-lead) {
    font-size: 20px;
    line-height: 1.5;
    color: var(--ink-secondary);
  }
  .site-doc :global(.site-small) {
    font-size: 14px;
    line-height: 1.5;
    color: var(--ink-secondary);
  }
  .site-doc :global(blockquote) {
    margin: 0 0 12px;
    padding-left: 16px;
    border-left: 2px solid var(--ink-secondary);
    max-width: 66ch;
  }
  .site-doc :global(code) {
    font-family: var(--font-mono);
    font-size: 14px;
    overflow-wrap: anywhere;
  }
  @media (max-width: 640px) {
    .site-doc {
      margin-top: 32px;
      padding: 0 16px;
    }
    .site-doc :global(h1) {
      font-size: 26px;
    }
    .site-doc :global(.site-lead) {
      font-size: 18px;
    }
  }
</style>
