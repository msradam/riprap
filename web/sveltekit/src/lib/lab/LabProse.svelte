<script lang="ts">
  import type { Citation, ClaimPart } from '$lib/types/claim';
  import { citations as cstore } from '$lib/stores/citations.svelte';
  import { tidy } from './a/tidy';

  /** One paragraph of claim parts as plain prose. A run of adjacent parts
   *  citing the same source shows its number once, after the last part. */
  interface Props {
    parts: ClaimPart[];
    citations: Record<string, Citation>;
    cite?: 'sup' | 'bracket';
    class?: string;
  }
  let { parts, citations, cite = 'sup', class: className }: Props = $props();

  const tidied = $derived(tidy(parts));

  /** Same behaviour as Cite.svelte: mark active, focus the note without a
   *  focus jump, then one instant scroll to bring it into view. */
  function activate(e: MouseEvent, id: string) {
    e.preventDefault();
    cstore.active = id;
    const el = document.getElementById(`cite-${id}`);
    if (!el) return;
    el.focus({ preventScroll: true });
    el.scrollIntoView({ block: 'nearest' });
  }
</script>

<p class={className}>
  {#each tidied as p, i (i)}{#if p.bold}<strong>{p.text}</strong>{:else}{p.text}{/if}{#if p.cite && citations[p.cite] && tidied[i + 1]?.cite !== p.cite}{@const c = citations[p.cite]}<a
        href="#cite-{c.id}"
        class="lab-cite"
        data-cite={c.id}
        onclick={(e) => activate(e, c.id)}
        aria-label="Citation {c.n}: {c.source}, {c.title}"
      >{#if cite === 'sup'}<sup>{c.n}</sup>{:else}[{c.n}]{/if}</a>{/if}{/each}
</p>
