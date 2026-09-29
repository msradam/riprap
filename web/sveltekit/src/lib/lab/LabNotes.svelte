<script lang="ts">
  import type { Citation } from '$lib/types/claim';
  import type { Tier } from '$lib/types/tier';
  import { citations as cstore } from '$lib/stores/citations.svelte';

  interface Props {
    citations: Citation[];
    class?: string;
    heading?: string;
    headingLevel?: 2 | 3;
  }
  let { citations, class: className, heading, headingLevel = 2 }: Props = $props();

  const TIER_WORDS: Record<Tier, string> = {
    empirical: 'Measured',
    modeled: 'Modeled',
    proxy: 'Proxy',
    synthetic: 'Synthetic'
  };
</script>

<div class={['lab-notes', className]}>
  {#if heading}
    <svelte:element this={`h${headingLevel}`} class="lab-notes-heading">{heading}</svelte:element>
  {/if}
  <ol class="lab-notes-list">
    {#each citations as c (c.id)}
      <!-- tabindex: an inline citation moves focus here, so the next Tab
           reaches this note's source link. -->
      <li id="cite-{c.id}" tabindex="-1" class={['lab-note', cstore.active === c.id && 'is-active']}>
        <span class="lab-note-n">{c.n}</span>
        <span class="lab-note-source">{c.source}</span>
        <span class="lab-note-title">
          {#if c.url?.startsWith('http')}
            <a href={c.url} target="_blank" rel="noopener noreferrer">{c.title}</a>
          {:else}
            {c.title}
          {/if}
        </span>
        {#if c.maturity === 'experimental'}<span class="lab-note-badge">Experimental</span>{/if}
        <span class="lab-note-vintage">data as of {c.vintage}</span>
        <span class="lab-note-tier">{TIER_WORDS[c.tier] ?? c.tier}</span>
        <span class="lab-note-docid">{c.docId}</span>
      </li>
    {/each}
  </ol>
</div>

<style>
  .lab-note.is-active {
    background: var(--paper-deep);
  }
  .lab-note:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  .lab-note-docid {
    font-family: var(--font-mono);
  }
</style>
