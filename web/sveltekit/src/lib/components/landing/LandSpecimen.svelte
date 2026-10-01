<script lang="ts">
  import { resolve } from '$app/paths';
  import AnswerProse from '$lib/components/briefing/AnswerProse.svelte';
  import SourceNotes from '$lib/components/briefing/SourceNotes.svelte';
  import type { Citation, ClaimPart } from '$lib/types/claim';

  /** A real gallery answer, set as on its briefing: the question, the
   *  lead word, the key sentence with its citation mark, the briefing's
   *  own flagged-sensor sentence, and the answer's source notes. Every
   *  text comes from the snapshot at build time. */
  export interface Specimen {
    slug: string;
    question: string;
    lead: string | null;
    key: ClaimPart[];
    /** The sentence where the briefing flags one of its own sensors. */
    flagged: ClaimPart[];
    citations: Citation[];
    date: string;
  }
  let { specimen }: { specimen: Specimen } = $props();

  // Keep house numbers such as "90-01" on one line.
  let qParts = $derived(specimen.question.split(/(\d+-\d+)/));
  let byId = $derived(Object.fromEntries(specimen.citations.map((c) => [c.id, c])));
</script>

<figure class="specimen">
  <figcaption class="specimen-caption">
    A real answer from the gallery, snapshot <time class="data" datetime={specimen.date}>{specimen.date}</time>
  </figcaption>
  <p class="specimen-q">
    {#each qParts as p, i (i)}{#if i % 2}<span class="nowrap">{p}</span>{:else}{p}{/if}{/each}
  </p>
  {#if specimen.lead}<p class="specimen-lead">{specimen.lead}</p>{/if}
  <AnswerProse parts={specimen.key} citations={byId} class="specimen-key" />
  <AnswerProse parts={specimen.flagged} citations={byId} class="specimen-flag" />
  <div class="specimen-notes">
    <SourceNotes citations={specimen.citations} label="Sources for the answer" />
  </div>
  <a class="land-link" href="{resolve('/(app)/gallery/[slug]', { slug: specimen.slug })}/">Read the full briefing</a>
</figure>

<style>
  .specimen {
    margin: 0;
    padding: 32px;
    background: var(--riprap-white);
  }
  .specimen-caption {
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .specimen-q {
    margin: 16px 0 0;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
    text-wrap: balance;
  }
  .nowrap {
    white-space: nowrap;
  }
  .specimen-lead {
    margin: 16px 0 0;
    font-size: 64px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
  }
  .specimen :global(.specimen-key) {
    margin: 12px 0 0;
    max-width: 64ch;
    font-size: 20px;
    line-height: 1.5;
  }
  .specimen :global(.specimen-flag) {
    margin: 12px 0 0;
    max-width: 64ch;
    font-size: 17px;
    line-height: 1.55;
  }
  .specimen-notes {
    margin: 24px 0 8px;
  }
  @media (max-width: 640px) {
    .specimen {
      padding: 24px 16px;
    }
    .specimen-lead {
      font-size: 44px;
    }
    /* Compact on a phone: the first source note only; the briefing has the rest. */
    .specimen-notes :global(.source-note:nth-child(n + 2)) {
      display: none;
    }
  }
</style>
