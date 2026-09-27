<script lang="ts">
  import type { Citation } from '$lib/types/claim';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import TierKey from '$lib/components/glyphs/TierKey.svelte';
  import { citations as cstore } from '$lib/stores/citations.svelte';

  interface Props {
    citations: Record<string, Citation>;
    /** Precomputed gallery page: sources were read at generation time. */
    snapshot?: boolean;
  }
  let { citations, snapshot = false }: Props = $props();

  let entries = $derived(Object.values(citations).sort((a, b) => a.n - b.n));
</script>

<div class="citation-drawer">
  <div class="citation-drawer-head">
    <span class="section-label">Citations · {entries.length}</span>
    <span class="citation-drawer-meta">{snapshot ? 'snapshot' : 'live'} · primary sources</span>
  </div>
  {#if entries.length}
    <div class="citation-tier-key"><TierKey /></div>
  {/if}
  <ol class="citation-list">
    {#each entries as c (c.id)}
      <!-- tabindex: an inline citation moves focus here, so the next Tab
           reaches this entry's source link. -->
      <li
        id="cite-{c.id}"
        tabindex="-1"
        class="citation-item"
        class:is-active={cstore.active === c.id}
      >
        <span class="citation-num">[{c.n}]</span>
        <div class="citation-body">
          <div class="citation-line-1">
            <TierGlyph tier={c.tier} size={10} color="var(--tier-{c.tier})" />
            <span class="citation-source">{c.source}</span>
            {#if c.maturity === 'experimental'}<span class="exp-badge">Experimental</span>{/if}
            <span class="citation-vintage">v. {c.vintage}</span>
          </div>
          <div class="citation-title">
            {#if c.url && c.url.startsWith('http')}
              <a href={c.url} target="_blank" rel="noopener noreferrer">{c.title}</a>
            {:else}
              {c.title}
            {/if}
          </div>
          <div class="citation-meta">
            <span class="citation-docid">{c.docId}</span>
            <span class="citation-retrieved">retr. {c.retrieved}</span>
          </div>
        </div>
      </li>
    {/each}
  </ol>
  <div class="citation-drawer-foot">
    <span class="section-label">Trust signals</span>
    <p class="citation-foot-copy">
      All foundation models Apache-2.0. All data from public-record federal,
      state, and city sources. No commercial APIs contacted at runtime.
    </p>
  </div>
</div>

<style>
  .citation-drawer :global(a) {
    color: inherit;
    border-bottom: 1px solid var(--rule-soft);
    text-decoration: none;
  }
  .citation-drawer :global(a:hover) {
    border-bottom-color: var(--accent);
    color: var(--accent);
  }
  .citation-tier-key {
    margin: 0 0 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--rule-soft);
  }
  /* 17px text box + 2 x 3.5px = 24px target (WCAG 2.5.8); inline padding does not change line height. */
  .citation-title a {
    padding-block: 3.5px;
  }
</style>
