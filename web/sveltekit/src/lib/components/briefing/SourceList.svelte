<script lang="ts">
  import type { Citation } from '$lib/types/claim';
  import { citations as cstore } from '$lib/stores/citations.svelte';
  import { asOfPhrase } from '$lib/client/briefingText';
  import { TIER_WORDS } from '$lib/types/tier';

  /** Every source the briefing cites: its name as the link, then its long
   *  title as plain text and its doc id. A citation mark focuses the
   *  element with id `cite-{id}`; for sources already shown as a source
   *  note beside the answer that element is the note, so these entries
   *  carry no id (ids stay unique). */
  interface Props {
    citations: Citation[];
    /** Ids already rendered as source notes. */
    noted: string[];
  }
  let { citations, noted }: Props = $props();
</script>

{#snippet asOf(c: Citation)}
  {@const a = asOfPhrase(c.vintage, c.retrieved)}{#if a.date}{a.label} <span class="data">{a.date}</span>{:else}{a.label}{/if}
{/snippet}

{#snippet entry(c: Citation)}
  <span class="source-entry-n data">{c.n}</span>
  <!-- Only the name is the link; the long description is plain text. -->
  <span class="source-entry-name">
    {#if c.url?.startsWith('http')}
      <a href={c.url} target="_blank" rel="noopener noreferrer">{c.source}</a>
    {:else}
      {c.source}
    {/if}
  </span>
  <span class="source-entry-title">{c.title}</span>
  <span class="source-entry-line">
    {#if c.maturity === 'experimental'}{TIER_WORDS[c.tier] ?? c.tier} <span class="exp-badge">Experimental</span>{:else}{TIER_WORDS[c.tier] ?? c.tier}{/if}, {@render asOf(c)},
    <span class="data">{c.docId}</span>{#if c.queryUrl?.startsWith('https://')},
      <a href={c.queryUrl} target="_blank" rel="noopener noreferrer">the exact query</a>{/if}
  </span>
{/snippet}

<ol class="source-list">
  {#each citations as c (c.id)}
    {#if noted.includes(c.id)}
      <li class="source-entry">{@render entry(c)}</li>
    {:else}
      <!-- tabindex: an inline citation moves focus here, so the next Tab
           reaches this entry's source link. -->
      <li id="cite-{c.id}" tabindex="-1" class={['source-entry', cstore.active === c.id && 'is-active']}>
        {@render entry(c)}
      </li>
    {/if}
  {/each}
</ol>

<style>
  .source-list {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .source-entry {
    max-width: 54ch;
    position: relative;
    padding: 4px 4px 6px 36px;
    margin-bottom: 8px;
    overflow-wrap: anywhere;
    scroll-margin-top: var(--scroll-offset, 80px);
  }
  .source-entry.is-active {
    background: var(--paper-deep);
  }
  .source-entry:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  .source-entry-n {
    position: absolute;
    left: 4px;
    top: 5px;
    color: var(--ink);
  }
  .source-entry-name {
    display: block;
    font-weight: 600;
    color: var(--ink);
  }
  .source-entry-title,
  .source-entry-line {
    display: block;
  }
  .source-entry-name a {
    color: var(--riprap-text-link);
    text-decoration: none;
  }
  .source-entry-line a {
    color: var(--riprap-text-link);
  }
  .source-entry-name a:hover,
  .source-entry-name a:focus-visible {
    text-decoration: underline;
  }
</style>
