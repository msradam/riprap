<script lang="ts">
  import type { Citation, ClaimPart } from '$lib/types/claim';
  import { tidy } from '$lib/client/briefingText';
  import { activateCitation } from '$lib/stores/citations.svelte';

  /** One paragraph of claim parts as plain prose: no tier marks, and a
   *  small citation number after the closing punctuation. A run of
   *  adjacent parts citing the same source shows its number once. A part
   *  marked `exp` sets the Experimental badge. */
  interface Props {
    parts: ClaimPart[];
    citations: Record<string, Citation>;
    class?: string;
  }
  let { parts, citations, class: className }: Props = $props();

  const tidied = $derived(tidy(parts));
</script>

<p class={className}>
  {#each tidied as p, i (i)}{#if p.exp}<span class="exp-badge">Experimental</span>{/if}{#if p.bold}<strong>{p.text}</strong>{:else}{p.text}{/if}{#if p.cite && citations[p.cite] && tidied[i + 1]?.cite !== p.cite}{@const c = citations[p.cite]}<a
        href="#cite-{c.id}"
        class="inline-cite"
        data-cite={c.id}
        onclick={(e) => activateCitation(e, c.id)}
        aria-label="Citation {c.n}: {c.source}, {c.title}"
      ><sup>{c.n}</sup></a>{/if}{/each}
</p>
