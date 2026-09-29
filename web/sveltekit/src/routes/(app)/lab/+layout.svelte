<script lang="ts">
  import type { Snippet } from 'svelte';
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { DIRECTIONS } from '$lib/lab/labModel';

  let { children }: { children: Snippet } = $props();

  const NAMES = { a: 'A evidence file', b: 'B editorial', c: 'C analyst' } as const;

  let slug = $derived(page.params.slug);
  let dir = $derived(page.params.dir);
  let links = $derived([
    {
      key: 'current',
      label: 'Current',
      // Gallery pages use a trailing slash (gallery/+layout.ts).
      href: slug ? `${resolve('/(app)/gallery/[slug]', { slug })}/` : resolve('/')
    },
    ...DIRECTIONS.map((d) => ({
      key: d,
      label: NAMES[d],
      href: slug
        ? resolve('/(app)/lab/[dir]/gallery/[slug]', { dir: d, slug })
        : resolve('/(app)/lab/[dir]', { dir: d })
    }))
  ]);
</script>

<nav class="lab-bar" aria-label="Design lab directions">
  <span class="lab-bar-title">Design lab (pass 2, Part A)</span>
  <ul>
    {#each links as l (l.key)}
      <li>
        <a href={l.href} aria-current={l.key === dir ? 'page' : undefined}>{l.label}</a>
      </li>
    {/each}
  </ul>
</nav>

{@render children()}

<style>
  .lab-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 4px 16px;
    padding: 6px 16px;
    background: var(--paper-deep);
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.4;
    color: var(--ink-secondary);
  }
  .lab-bar-title {
    font-weight: 600;
  }
  ul {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  a {
    display: inline-block;
    min-height: 24px;
    color: var(--ink);
  }
  a[aria-current='page'] {
    font-weight: 600;
    text-decoration: none;
  }
</style>
