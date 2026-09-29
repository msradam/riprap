<script lang="ts">
  import { resolve } from '$app/paths';
  import type { RunState } from '$lib/client/runState.svelte';
  import type { GalleryEntry } from '$lib/client/gallery';
  import type { LabModel } from '$lib/lab/labModel';
  import type { Card } from '$lib/types/card';
  import LabProse from '$lib/lab/LabProse.svelte';
  import LabNotes from '$lib/lab/LabNotes.svelte';
  import LabSources from '$lib/lab/LabSources.svelte';
  import LabMap from '$lib/lab/LabMap.svelte';
  import DroppedClaims from '$lib/components/briefing/DroppedClaims.svelte';
  import FigureBand from './FigureBand.svelte';
  import { figureBands, shortDate } from './figures';

  interface Props { run: RunState; model: LabModel; entry: GalleryEntry }
  let { run, model }: Props = $props();

  let isCount = $derived(!!model.leadWord && /^\d/.test(model.leadWord));
  /** A count stays in its sentence in the model; here the number is the
   *  headline, so the dek picks up the sentence after it. */
  let dek = $derived.by(() => {
    if (!isCount || !model.answer.length) return model.answer;
    const [first, ...rest] = model.answer[0];
    const text = first.text.replace(/^[\d,.]+%?\s+/, '');
    return [[{ ...first, text }, ...rest], ...model.answer.slice(1)];
  });

  let split = $derived(figureBands(model.cards, model.cited));
  /** Band i follows body section i; leftovers follow the last section. */
  const bandAfter = (i: number, last: boolean) =>
    last ? split.bands.slice(i) : split.bands[i] ? [split.bands[i]] : [];

  const stop = (t: string) => (/[.!?]$/.test(t) ? t : `${t}.`);
  const finding = (c: Card) => c.body || c.sub || c.headline || '';
  let absentLine = $derived(
    model.absent.map((c) => `${c.title} (${(c.absent ?? '').toLowerCase()})`).join('; ')
  );
  let caption = $derived(model.kind === 'district' ? model.place : (model.neighborhood || model.place));
</script>

<article class="b">
  <header class="b-head b-col">
    <h1>
      {#if model.kind === 'address'}
        <span class="b-kicker">Flood exposure</span><span class="visually-hidden">: </span>
        <span class="b-place">{model.place}</span>
      {:else}
        <span class="b-kicker">{model.question ?? model.place}</span>
        {#if model.leadWord}
          <span class={['b-lead', isCount && 'is-count']}>{model.leadWord}{isCount ? '' : '.'}</span>
        {/if}
      {/if}
    </h1>
    <div class="b-dek" class:is-count={isCount}>
      {#each dek as parts, i (i)}
        <LabProse {parts} citations={model.citationsById} cite="sup" />
      {/each}
    </div>
    <p class="b-byline">
      <span>Riprap briefing</span>
      {#if model.kind !== 'address'}<span>{model.place}</span>{/if}
      <span>Snapshot of {model.generated}</span>
    </p>
    {#if model.modeLine}<p class="b-mode">{model.modeLine}</p>{/if}
  </header>

  <figure class="b-map b-wide">
    <LabMap {run} height="440px" class="b-labmap" />
    <figcaption>Figure 1. {caption}, with the evidence the sources place on the map. Layers and a list of the map points follow.</figcaption>
  </figure>

  {#if model.body.length}
    {#each model.body as s, i (i)}
      <section class="b-col b-section">
        {#if s.label}<h2>{s.label}</h2>{/if}
        {#each s.paras as parts, j (j)}
          <LabProse {parts} citations={model.citationsById} cite="sup" />
        {/each}
      </section>
      {#each bandAfter(i, i === model.body.length - 1) as band (band.key)}
        <FigureBand {band} />
      {/each}
    {/each}
  {:else}
    {#each split.bands as band (band.key)}
      <FigureBand {band} />
    {/each}
  {/if}

  <section class="b-notes" aria-labelledby="b-notes-h">
    <div class="b-col">
      <h2 id="b-notes-h">How we know this</h2>
      {#if model.checks}<p>{stop(model.checks)}</p>{/if}
      {#if model.modeLine}<p>{stop(model.modeLine)}</p>{/if}
      {#each model.scope as parts, i (i)}
        <LabProse {parts} citations={model.citationsById} cite="sup" />
      {/each}
      {#each model.outOfScope as parts, i (i)}
        <LabProse {parts} citations={model.citationsById} cite="sup" />
      {/each}
      <DroppedClaims claims={model.dropped} />

      {#if split.rest.length || model.absent.length}
        <h3>More from the sources</h3>
        {#if split.rest.length}
          <ul class="b-more">
            {#each split.rest as c (c.id)}
              <li>
                <span class="b-more-source">{c.source}{#if c.experimental}, experimental{/if}</span>
                <span class="b-more-title">{c.title}</span>
                {#if finding(c)}<span class="b-more-finding">{finding(c)}</span>{/if}
                <span class="b-more-date">{shortDate(c.vintage)}</span>
              </li>
            {/each}
          </ul>
        {/if}
        {#if model.absent.length}
          <p class="b-absent">{model.absent.length} more sources had no result: {absentLine}.</p>
        {/if}
      {/if}

      {#if model.citations.length}
        <LabNotes citations={model.citations} heading="Notes" headingLevel={3} class="b-labnotes" />
      {/if}

      <h3>What was checked</h3>
      <LabSources lists={model.lists} class="b-labsources" />

      <h3>This snapshot</h3>
      <p class="b-snap">
        Generated {model.generated}, commit <span class="b-mono">{model.commit}</span>{#if model.stamp}. {model.stamp}{/if}.
      </p>
      {#if model.metaCard?.models?.length}
        <ul class="b-models">
          {#each model.metaCard.models as m, i (i)}
            <li>
              <strong>{m.name}</strong>:
              {#if m.href}<a href={m.href} target="_blank" rel="noopener noreferrer">{m.repo}</a>{:else}{m.repo}{/if},
              {m.where}, {m.how}{#if m.latency}, {m.latency}{/if}{#if m.detail}. {m.detail}{/if}.
            </li>
          {/each}
        </ul>
      {/if}
      <p class="b-back"><a href={resolve('/(app)/lab/[dir]', { dir: 'b' })}>All briefings in the gallery</a></p>
    </div>
  </section>
</article>

<style>
  .b {
    --b-text: 640px;
    --b-wide: 1040px;
    padding: 56px 16px 0;
    color: var(--ink);
    font-family: var(--font-sans);
  }
  .b-col {
    max-width: var(--b-text);
    margin-inline: auto;
  }
  .b-wide {
    max-width: var(--b-wide);
    margin-inline: auto;
  }

  /* Headline block */
  h1 {
    margin: 0;
    font-weight: 700;
  }
  .b-kicker {
    display: block;
    font-size: 18px;
    font-weight: 500;
    line-height: 1.4;
    color: var(--ink-secondary);
    text-wrap: pretty;
  }
  .b-lead {
    display: block;
    margin-top: 8px;
    font-size: 108px;
    line-height: 0.95;
    letter-spacing: -0.04em;
    font-variant-numeric: lining-nums;
  }
  .b-place {
    display: block;
    margin-top: 8px;
    font-size: 56px;
    line-height: 1.02;
    letter-spacing: -0.025em;
    text-wrap: balance;
  }
  .b-dek {
    margin-top: 24px;
  }
  .b-dek :global(p) {
    margin: 0 0 0.6em;
    font-size: 23px;
    line-height: 1.4;
    text-wrap: pretty;
  }
  /* The count's own sentence runs straight on from the number. */
  .b-dek.is-count {
    margin-top: 4px;
  }
  .b-byline {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 20px;
    margin: 28px 0 0;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .b-byline span:first-child {
    font-weight: 600;
    color: var(--ink);
  }
  .b-mode {
    margin: 4px 0 0;
    font-size: 13px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }

  /* Citation marks: small superscripts in ink, blue only as links. */
  .b :global(.lab-cite) {
    color: var(--riprap-blue-60v);
    text-decoration: none;
    padding: 0 1px;
  }
  .b :global(.lab-cite sup) {
    font-family: var(--font-mono);
    font-size: 0.6em;
    line-height: 0;
    vertical-align: super;
  }
  .b :global(.lab-cite:hover) {
    text-decoration: underline;
  }
  .b :global(a:focus-visible),
  .b :global(summary:focus-visible),
  .b :global(button:focus-visible),
  .b :global(input:focus-visible) {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }

  /* Figure 1 */
  /* The caption sits right under the map frame, before the layer switches
     and the points list that LabMap renders after it. */
  .b-map {
    display: flex;
    flex-direction: column;
    margin-top: 56px;
    margin-bottom: 0;
  }
  .b-map :global(.b-labmap) {
    display: contents;
  }
  .b-map figcaption {
    order: 1;
  }
  .b-map :global(.lab-map-layers),
  .b-map :global(.lab-map-points),
  .b-map :global(#lab-after-map) {
    order: 2;
  }
  .b-map figcaption {
    max-width: var(--b-text);
    margin: 10px 0 0;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .b-map :global(.lab-map-skip) {
    position: absolute;
    left: -9999px;
  }
  .b-map :global(.lab-map-skip:focus) {
    position: static;
    display: inline-block;
    margin-bottom: 8px;
    color: var(--riprap-blue-60v);
  }
  .b-map :global(.lab-map-layers) {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 20px;
    margin: 12px 0 0;
    padding: 0;
    border: 0;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .b-map :global(.lab-map-layers legend) {
    float: left;
    margin-right: 8px;
    padding: 0;
    font-weight: 600;
    color: var(--ink);
  }
  .b-map :global(.lab-map-layers label) {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 24px;
  }
  .b-map :global(.lab-map-layers input) {
    width: 18px;
    height: 18px;
    margin: 0;
    accent-color: var(--ink);
  }
  .b-map :global(.lab-map-points) {
    margin-top: 8px;
    font-size: 14px;
  }
  .b-map :global(.lab-map-points summary) {
    min-height: 24px;
    cursor: pointer;
    color: var(--ink-secondary);
  }
  .b-map :global(.lab-map-points ul) {
    margin: 8px 0 0;
    padding: 0;
    list-style: none;
    columns: 2 300px;
  }
  .b-map :global(.lab-map-point) {
    display: block;
    width: 100%;
    min-height: 24px;
    padding: 4px 0;
    border: 0;
    background: none;
    font: inherit;
    text-align: left;
    color: var(--ink);
    cursor: pointer;
    break-inside: avoid;
  }
  .b-map :global(.lab-map-point-meta) {
    display: block;
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .b-map :global(.lab-map-note) {
    display: none;
  }

  /* Body */
  .b-section {
    margin-top: 56px;
  }
  .b-section + .b-section {
    margin-top: 40px;
  }
  h2 {
    margin: 0 0 12px;
    font-size: 26px;
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: -0.01em;
  }
  .b-section :global(p) {
    margin: 0 0 1em;
    font-size: 19px;
    line-height: 1.55;
    text-wrap: pretty;
  }

  /* Notes box */
  .b-notes {
    margin: 72px -16px 0;
    padding: 48px 16px 64px;
    background: var(--paper-deep);
    font-size: 16px;
    line-height: 1.55;
  }
  .b-notes p {
    margin: 0 0 0.8em;
  }
  .b-notes :global(p) {
    margin: 0 0 0.8em;
  }
  h3 {
    margin: 36px 0 10px;
    font-size: 20px;
    font-weight: 700;
    line-height: 1.25;
  }
  .b-notes :global(.dropped-claims) {
    border: 0;
    background: var(--paper);
  }
  .b-notes :global(.dropped-claims summary) {
    font-family: var(--font-sans);
    font-size: 15px;
  }
  .b-more {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .b-more li {
    padding: 10px 0;
    font-size: 15px;
    line-height: 1.45;
  }
  .b-more-source,
  .b-more-date {
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .b-more-source {
    display: block;
  }
  .b-more-date {
    font-family: var(--font-mono);
    margin-left: 6px;
  }
  .b-more-title {
    font-weight: 600;
  }
  .b-more-title::after {
    content: '. ';
  }
  .b-absent {
    font-size: 15px;
    color: var(--ink-secondary);
  }

  .b-notes :global(.lab-notes-heading) {
    margin: 36px 0 10px;
    font-size: 20px;
    font-weight: 700;
    line-height: 1.25;
  }
  .b-notes :global(.lab-notes-list) {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .b-notes :global(.lab-note) {
    position: relative;
    padding: 8px 4px 8px 40px;
    font-size: 15px;
    line-height: 1.45;
  }
  .b-notes :global(.lab-note.is-active) {
    background: var(--paper);
  }
  .b-notes :global(.lab-note-n) {
    position: absolute;
    left: 4px;
    top: 9px;
    font-family: var(--font-mono);
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .b-notes :global(.lab-note-source) {
    font-weight: 600;
  }
  .b-notes :global(.lab-note-source::after) {
    content: '. ';
  }
  .b-notes :global(.lab-note-title a) {
    color: var(--riprap-blue-60v);
  }
  .b-notes :global(.lab-note-badge) {
    display: block;
    width: fit-content;
    font-size: 13px;
    font-weight: 600;
  }
  .b-notes :global(.lab-note-vintage),
  .b-notes :global(.lab-note-tier),
  .b-notes :global(.lab-note-docid) {
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .b-notes :global(.lab-note-vintage) {
    display: block;
    width: fit-content;
    float: left;
    margin-right: 0.4em;
    font-family: var(--font-mono);
  }
  .b-notes :global(.lab-note-vintage::after),
  .b-notes :global(.lab-note-tier::after) {
    content: ',';
  }
  .b-notes :global(.lab-note::after) {
    content: '';
    display: block;
    clear: both;
  }

  .b-notes :global(.lab-sources details) {
    margin: 0 0 8px;
    font-size: 15px;
  }
  .b-notes :global(.lab-sources summary) {
    min-height: 24px;
    font-weight: 600;
    cursor: pointer;
  }
  .b-notes :global(.lab-sources ul) {
    margin: 6px 0 12px;
    padding-left: 20px;
    color: var(--ink-secondary);
  }
  .b-snap {
    font-size: 15px;
  }
  .b-mono {
    font-family: var(--font-mono);
    font-size: 14px;
  }
  .b-models {
    margin: 0;
    padding-left: 20px;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .b-models li {
    margin-bottom: 6px;
  }
  .b-notes a {
    color: var(--riprap-blue-60v);
  }
  .b-back {
    margin-top: 32px;
    font-size: 16px;
  }
  .b-back a {
    display: inline-block;
    min-height: 24px;
  }

  @media (max-width: 640px) {
    .b {
      padding-top: 32px;
    }
    .b-lead {
      font-size: 84px;
    }
    .b-place {
      font-size: 40px;
    }
    .b-dek :global(p) {
      font-size: 21px;
    }
    /* Full-bleed map on a phone; the caption keeps the gutter. */
    .b-map {
      margin-inline: -16px;
    }
    .b-map figcaption,
    .b-map :global(.lab-map-layers),
    .b-map :global(.lab-map-points),
    .b-map :global(.lab-map-skip:focus) {
      margin-inline: 16px;
    }
    .b-section :global(p) {
      font-size: 18px;
    }
  }
</style>
