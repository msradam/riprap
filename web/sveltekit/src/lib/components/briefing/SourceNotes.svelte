<script lang="ts">
  import type { Citation } from '$lib/types/claim';
  import { citations as cstore } from '$lib/stores/citations.svelte';
  import { asOfPhrase } from '$lib/client/briefingText';
  import { TIER_WORDS } from '$lib/types/tier';

  /** The answer's sources, short: number, source name as the link, then
   *  the tier in words, the Experimental badge and the data date. The
   *  long title and doc id live only in the full source list. */
  interface Props {
    citations: Citation[];
    label: string;
    class?: string;
  }
  let { citations, label, class: className }: Props = $props();
</script>

{#snippet asOf(v: string)}
  {@const a = asOfPhrase(v)}{#if a.date}{a.label} <span class="data">{a.date}</span>{:else}{a.label}{/if}
{/snippet}

<ol class={['source-notes', className]} aria-label={label}>
  {#each citations as c (c.id)}
    <!-- tabindex: an inline citation moves focus here, so the next Tab
         reaches this note's source link. -->
    <li id="cite-{c.id}" tabindex="-1" class={['source-note', cstore.active === c.id && 'is-active']}>
      <span class="source-note-n">{c.n}</span>
      <span class="source-note-name">
        {#if c.url?.startsWith('http')}
          <a href={c.url} target="_blank" rel="noopener noreferrer">{c.source}</a>
        {:else}
          {c.source}
        {/if}
      </span>
      <span class="source-note-line">
        {#if c.maturity === 'experimental'}{TIER_WORDS[c.tier] ?? c.tier} <span class="exp-badge">Experimental</span>{:else}{TIER_WORDS[c.tier] ?? c.tier}{/if}, {@render asOf(c.vintage)}
      </span>
    </li>
  {/each}
</ol>

<style>
  .source-notes {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .source-note {
    position: relative;
    padding: 4px 4px 6px 28px;
    margin-bottom: 8px;
    overflow-wrap: anywhere;
    scroll-margin-top: var(--scroll-offset, 80px);
  }
  .source-note.is-active {
    background: var(--paper-deep);
  }
  .source-note:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  .source-note-n {
    position: absolute;
    left: 4px;
    top: 5px;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink);
  }
  .source-note-name {
    display: block;
    font-weight: 600;
    color: var(--ink);
  }
  .source-note-name a {
    color: var(--riprap-text-link);
    text-decoration: none;
  }
  .source-note-name a:hover,
  .source-note-name a:focus-visible {
    text-decoration: underline;
  }
  .source-note-line {
    display: block;
  }
</style>
