<script lang="ts">
  import { resolve } from '$app/paths';
  import type { RunState } from '$lib/client/runState.svelte';
  import type { GalleryEntry } from '$lib/client/gallery';
  import type { LabModel } from '$lib/lab/labModel';
  import LabProse from '$lib/lab/LabProse.svelte';
  import LabNotes from '$lib/lab/LabNotes.svelte';
  import LabSources from '$lib/lab/LabSources.svelte';
  import LabMap from '$lib/lab/LabMap.svelte';
  import DroppedClaims from '$lib/components/briefing/DroppedClaims.svelte';
  import { tidy, dropLead, citedIn, figureOf, findingOf } from './tidy';

  /** Direction A, "evidence file": a well-set report. The question is the
   *  title, the answer leads with its sources in the margin, the map is
   *  Figure 1, the evidence is an exhibit table, the method is an appendix. */
  interface Props { run: RunState; model: LabModel; entry: GalleryEntry }
  let { run, model }: Props = $props();

  const KIND_LINE = {
    question: 'Flood-exposure briefing, question',
    district: 'Flood-exposure briefing, district',
    address: 'Flood-exposure briefing, address'
  } as const;

  let kindLine = $derived(
    model.kind === 'district' && model.question ? 'Flood-exposure briefing, district question' : KIND_LINE[model.kind]
  );
  /** "Yes." keeps its full stop; a count is set bare and leaves its sentence. */
  let lead = $derived(model.leadWord && /^[A-Z]/.test(model.leadWord) ? `${model.leadWord}.` : model.leadWord);
  let answer = $derived(
    model.answer.map((p, i) => tidy(i === 0 ? dropLead(p, model.leadWord) : p))
  );
  let answerIds = $derived(citedIn(model.answer));
  let answerCites = $derived(model.citations.filter((c) => answerIds.includes(c.id)));
  let otherCites = $derived(model.citations.filter((c) => !answerIds.includes(c.id)));
  let absentNames = $derived([...new Set(model.absent.map((c) => c.source))]);
</script>

<article class="a-brief">
  <header class="a-head">
    <p class="a-kind">{kindLine}</p>
    <h1 class={['a-title', model.question && 'is-question']}>{model.question ?? model.place}</h1>
    <p class="a-meta">
      {#if model.question}<span>{model.place}</span>{/if}
      <span>Snapshot <time class="a-mono">{model.generated}</time></span>
      <a href="#a-method">How this briefing was made</a>
    </p>
  </header>

  <div class="a-top">
    <section class="a-answer" aria-labelledby="a-answer-h">
      <h2 id="a-answer-h" class="visually-hidden">{model.leadLabel ?? 'Answer'}</h2>
      {#if lead}<p class="a-lead">{lead}</p>{/if}
      {#each answer as parts, i (i)}
        <LabProse {parts} citations={model.citationsById} class="a-answer-p" />
      {/each}
    </section>

    {#if answerCites.length}
      <aside class="a-rail" aria-label="Sources for the answer">
        <LabNotes citations={answerCites} heading="Sources for the answer" class="a-notes a-notes-rail" />
      </aside>
    {/if}

    <div class="a-after">
      {#if model.checks}<p class="a-quiet">{model.checks}</p>{/if}
      <p class="a-quiet">{model.modeLine}</p>
      {#each model.scope as parts, i (i)}
        <LabProse parts={tidy(parts)} citations={model.citationsById} class="a-scope" />
      {/each}
    </div>
  </div>

  <figure class="a-figure">
    <LabMap {run} height="360px" class="a-map" />
    <figcaption class="a-caption">Figure 1. The place and the mapped evidence around it.</figcaption>
  </figure>

  {#each model.body as s, i (i)}
    <section class="a-section" aria-labelledby="a-sec-{i}">
      {#if s.label}
        <h2 id="a-sec-{i}" class="a-h2"><span class="a-sec-n">{i + 1}</span>{s.label}</h2>
      {/if}
      {#each s.paras as parts, j (j)}
        <LabProse parts={tidy(parts)} citations={model.citationsById} class="a-prose" />
      {/each}
    </section>
  {/each}

  {#if model.cards.length}
    <section class="a-evidence" aria-labelledby="a-ev-h">
      <h2 id="a-ev-h" class="a-h2">Evidence</h2>
      <table class="a-table" aria-labelledby="a-ev-h">
        <thead>
          <tr>
            <th scope="col">Source</th>
            <th scope="col">Finding</th>
            <th scope="col">Figure</th>
            <th scope="col">Data as of</th>
          </tr>
        </thead>
        <tbody>
          {#each model.cards as c (c.id)}
            {@const fig = figureOf(c)}
            {@const find = findingOf(c)}
            <tr>
              <td class="a-td-source">
                <span class="a-td-label" aria-hidden="true">Source</span>
                <div>{c.source}{#if c.experimental} <span class="a-badge">Experimental</span>{/if}</div>
              </td>
              <td class="a-td-finding">
                <span class="a-td-label" aria-hidden="true">Finding</span>
                <div>
                  {#if find}<span class="a-find">{find.first}</span> {find.rest}{/if}
                  <span class="a-find-title">{c.title}</span>
                </div>
              </td>
              <td class="a-td-figure">
                <span class="a-td-label" aria-hidden="true">Figure</span>
                <div>
                  {#if fig}
                    <span class="a-mono a-fig">{fig.value}</span>
                    {#if fig.label}<span class="a-fig-label">{fig.label}</span>{/if}
                  {/if}
                </div>
              </td>
              <td class="a-td-date">
                <span class="a-td-label" aria-hidden="true">Data as of</span>
                <div class="a-mono">{c.vintage}</div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
      {#if absentNames.length}
        <p class="a-absent">No result from: {absentNames.join(', ')}.</p>
      {/if}
    </section>
  {/if}

  <section class="a-appendix" aria-labelledby="a-app-h">
    <h2 id="a-app-h" class="a-h2">Sources and method</h2>

    {#if otherCites.length}
      <LabNotes citations={otherCites} heading="Other sources cited" headingLevel={3} class="a-notes" />
    {/if}

    <h3 class="a-h3">What was checked</h3>
    <LabSources lists={model.lists} class="a-sources" />

    <DroppedClaims claims={model.dropped} />

    {#if model.outOfScope.length}
      <h3 class="a-h3">Out of scope</h3>
      {#each model.outOfScope as parts, i (i)}
        <LabProse parts={tidy(parts)} citations={model.citationsById} class="a-small" />
      {/each}
    {/if}

    <h3 id="a-method" class="a-h3" tabindex="-1">How this briefing was made</h3>
    <p class="a-small">{model.modeLine}</p>
    <p class="a-small">
      Snapshot <time class="a-mono">{model.generated}</time>, commit <code class="a-mono">{model.commit}</code>.{#if model.stamp}
        {model.stamp}.{/if}
    </p>
    {#if model.metaCard?.models?.length}
      <ul class="a-models">
        {#each model.metaCard.models as m, i (i)}
          <li><span class="a-model-name">{m.name}</span>, {m.where}</li>
        {/each}
      </ul>
    {/if}

    <p class="a-back">
      <a href="{resolve('/(app)/gallery')}/">All gallery briefings</a>
      <a href={resolve('/(app)/lab/[dir]', { dir: 'a' })}>Direction A cover</a>
    </p>
  </section>
</article>

<style>
  .a-brief {
    --a-text: 680px;
    --a-rail: 280px;
    --a-gap: 56px;
    max-width: calc(var(--a-text) + var(--a-rail) + var(--a-gap));
    margin: 0 auto;
    padding: 18px 32px 96px;
    color: var(--ink);
    font-family: var(--font-sans);
    font-size: 17px;
    line-height: 1.55;
  }
  .a-mono {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 0.9em;
  }
  a,
  .a-brief :global(a) {
    color: var(--riprap-text-link);
  }
  .a-brief :global(:focus-visible) {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }

  /* Header */
  .a-kind {
    margin: 0 0 4px;
    font-size: 15px;
    line-height: 1.35;
    color: var(--ink-secondary);
  }
  .a-title {
    margin: 0;
    font-size: 35px;
    font-weight: 600;
    line-height: 1.1;
    letter-spacing: -0.01em;
    text-wrap: balance;
  }
  .a-title.is-question {
    max-width: 30ch;
  }
  .a-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 20px;
    margin: 8px 0 0;
    font-size: 15px;
    line-height: 1.4;
    color: var(--ink-secondary);
  }
  .a-meta a {
    display: inline-block;
    min-height: 24px;
  }

  /* Answer and its margin notes */
  .a-top {
    display: grid;
    grid-template-columns: minmax(0, var(--a-text)) var(--a-rail);
    column-gap: var(--a-gap);
    grid-template-rows: auto 1fr;
    align-items: start;
    margin-top: 18px;
  }
  .a-answer,
  .a-after {
    grid-column: 1;
  }
  .a-rail {
    grid-column: 2;
    grid-row: 1 / span 2;
    padding-top: 12px;
  }
  .a-lead {
    margin: 0 0 6px;
    font-size: 52px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.015em;
    font-variant-numeric: tabular-nums;
  }
  .a-brief :global(.a-answer-p) {
    margin: 0 0 12px;
    font-size: 20px;
    line-height: 1.5;
  }
  .a-after {
    margin-top: 12px;
  }
  .a-quiet {
    margin: 0 0 4px;
    font-size: 15px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .a-brief :global(.a-scope) {
    margin: 12px 0 0;
    font-size: 15px;
    line-height: 1.45;
    color: var(--ink-secondary);
    max-width: 68ch;
  }

  /* Citation marks: small figures after the sentence, no tier glyph. */
  .a-brief :global(.lab-cite) {
    text-decoration: none;
    padding: 0 1px;
  }
  .a-brief :global(.lab-cite sup) {
    font-family: var(--font-mono);
    font-size: 0.62em;
    font-weight: 500;
    line-height: 0;
    /* Keeps a run of marks ("3 4 5") from reading as one number. */
    padding-left: 0.14em;
  }
  .a-brief :global(.lab-cite:hover) {
    text-decoration: underline;
  }

  /* Notes, in the rail and in the appendix */
  .a-brief :global(.a-notes .lab-notes-heading) {
    margin: 0 0 10px;
    font-size: 15px;
    font-weight: 600;
    line-height: 1.3;
  }
  .a-brief :global(.lab-notes-list) {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .a-brief :global(.lab-note) {
    position: relative;
    display: flex;
    flex-wrap: wrap;
    gap: 0 10px;
    padding: 6px 4px 8px 28px;
    margin-bottom: 4px;
    font-size: 15px;
    line-height: 1.4;
    color: var(--ink-secondary);
    overflow-wrap: anywhere;
  }
  .a-brief :global(.lab-note-n) {
    position: absolute;
    left: 4px;
    top: 6px;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink);
  }
  .a-brief :global(.lab-note-source) {
    flex-basis: 100%;
    font-weight: 600;
    color: var(--ink);
  }
  .a-brief :global(.lab-note-title) {
    flex-basis: 100%;
  }
  .a-brief :global(.lab-note-title a) {
    display: inline;
  }
  .a-brief :global(.lab-note-tier) {
    order: 1;
    color: var(--ink);
  }
  .a-brief :global(.lab-note-vintage),
  .a-brief :global(.lab-note-badge) {
    order: 2;
  }
  .a-brief :global(.lab-note-docid) {
    order: 3;
    font-size: 13px;
  }
  .a-brief :global(.lab-note-badge),
  .a-badge {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-secondary);
    border: 1px solid var(--rule-soft);
    border-radius: 3px;
    padding: 0 5px;
    white-space: nowrap;
  }
  .a-brief :global(.a-notes-rail .lab-note) {
    font-size: 14px;
  }

  /* Figure 1: the LabMap's children join the figure so the caption sits
     directly under the map frame, ahead of the layer and point lists. */
  .a-figure {
    display: flex;
    flex-direction: column;
    max-width: var(--a-text);
    margin: 48px 0 0;
  }
  .a-figure :global(.a-map) {
    display: contents;
  }
  .a-figure :global(.lab-map-frame) {
    order: 1;
    border: 1px solid var(--rule-soft);
  }
  .a-caption {
    order: 2;
    margin: 8px 0 12px;
    font-size: 15px;
    color: var(--ink-secondary);
  }
  .a-figure :global(.lab-map-layers),
  .a-figure :global(.lab-map-points),
  .a-figure :global(.lab-map-note),
  .a-figure :global(#lab-after-map) {
    order: 3;
  }
  .a-figure :global(.lab-map-skip) {
    position: absolute;
    left: -9999px;
  }
  .a-figure :global(.lab-map-skip:focus) {
    position: static;
    align-self: flex-start;
    margin-bottom: 8px;
  }
  .a-figure :global(.lab-map-layers) {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 20px;
    margin: 0 0 8px;
    padding: 0;
    border: 0;
    font-size: 15px;
  }
  .a-figure :global(.lab-map-layers legend) {
    float: left;
    margin-right: 12px;
    padding: 0;
    color: var(--ink-secondary);
  }
  .a-figure :global(.lab-map-layers label) {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 24px;
  }
  .a-figure :global(.lab-map-layers input) {
    width: 18px;
    height: 18px;
    margin: 0;
    accent-color: var(--ink);
  }
  .a-figure :global(.lab-map-points summary),
  .a-brief :global(.lab-sources summary) {
    min-height: 24px;
    cursor: pointer;
    font-size: 15px;
    color: var(--ink);
  }
  .a-figure :global(.lab-map-points ul) {
    list-style: none;
    margin: 6px 0 0;
    padding: 0;
  }
  .a-figure :global(.lab-map-point) {
    display: flex;
    flex-wrap: wrap;
    gap: 0 10px;
    width: 100%;
    min-height: 24px;
    padding: 4px 0;
    border: 0;
    border-bottom: 1px solid var(--riprap-rule-hairline);
    background: none;
    font: inherit;
    font-size: 15px;
    text-align: left;
    color: var(--ink);
    cursor: pointer;
  }
  .a-figure :global(.lab-map-point-meta) {
    color: var(--ink-secondary);
  }
  .a-figure :global(.lab-map-note) {
    margin: 8px 0 0;
    font-size: 15px;
    color: var(--ink-secondary);
  }

  /* Report sections */
  .a-h2 {
    margin: 56px 0 12px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }
  .a-sec-n {
    display: inline-block;
    min-width: 1.6em;
    font-variant-numeric: tabular-nums;
    color: var(--ink-secondary);
  }
  .a-section {
    max-width: var(--a-text);
  }
  .a-brief :global(.a-prose) {
    margin: 0 0 14px;
    max-width: 68ch;
    font-size: 17px;
    line-height: 1.55;
  }

  /* Evidence exhibit */
  .a-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 15px;
    line-height: 1.45;
  }
  .a-table th {
    padding: 0 16px 8px 0;
    text-align: left;
    font-weight: 600;
    color: var(--ink-secondary);
    border-bottom: 1px solid var(--ink);
  }
  .a-table td {
    padding: 12px 16px 12px 0;
    vertical-align: top;
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  .a-td-source {
    width: 22%;
    color: var(--ink-secondary);
    overflow-wrap: anywhere;
  }
  .a-td-figure {
    width: 14%;
  }
  .a-td-date {
    width: 13%;
    overflow-wrap: anywhere;
    color: var(--ink-secondary);
  }
  .a-find {
    font-weight: 600;
  }
  .a-find-title,
  .a-fig-label {
    display: block;
    margin-top: 4px;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .a-fig {
    display: block;
    font-size: 16px;
    font-weight: 500;
  }
  .a-td-label {
    display: none;
  }
  .a-absent {
    margin: 16px 0 0;
    max-width: 68ch;
    font-size: 15px;
    color: var(--ink-secondary);
  }

  /* Appendix */
  .a-appendix {
    max-width: calc(var(--a-text) + var(--a-rail) + var(--a-gap));
    margin-top: 72px;
    padding-top: 8px;
    border-top: 1px solid var(--ink);
    font-size: 15px;
    color: var(--ink-secondary);
  }
  .a-appendix .a-h2 {
    margin-top: 16px;
    color: var(--ink);
  }
  .a-h3,
  .a-appendix :global(.a-notes .lab-notes-heading) {
    margin: 32px 0 8px;
    font-size: 17px;
    font-weight: 600;
    color: var(--ink);
  }
  .a-appendix :global(.a-notes) {
    max-width: var(--a-text);
  }
  .a-brief :global(.a-sources) {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px 32px;
    align-items: start;
  }
  .a-brief :global(.a-sources ul) {
    margin: 6px 0 0;
    padding-left: 18px;
  }
  .a-brief :global(.a-sources li) {
    margin-bottom: 2px;
  }
  .a-brief :global(.lab-sources-none) {
    margin: 0;
  }
  .a-brief :global(.a-small) {
    margin: 0 0 8px;
    max-width: 68ch;
    font-size: 15px;
    line-height: 1.5;
  }
  #a-method {
    scroll-margin-top: 16px;
  }
  #a-method:focus-visible {
    outline: none;
  }
  .a-models {
    margin: 4px 0 0;
    padding-left: 18px;
    max-width: 68ch;
  }
  .a-model-name {
    color: var(--ink);
  }
  .a-back {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 24px;
    margin: 40px 0 0;
  }
  .a-back a {
    display: inline-block;
    min-height: 24px;
  }

  @media (max-width: 1099px) {
    .a-top {
      grid-template-columns: minmax(0, 1fr);
      max-width: var(--a-text);
    }
    .a-rail {
      grid-column: 1;
      grid-row: auto;
      padding-top: 20px;
      margin-top: 8px;
      border-top: 1px solid var(--riprap-rule-hairline);
    }
    .a-brief :global(.a-sources) {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  @media (max-width: 640px) {
    .a-brief {
      padding: 20px 16px 64px;
    }
    .a-title {
      font-size: 29px;
    }
    .a-lead {
      font-size: 44px;
    }
    .a-brief :global(.a-answer-p) {
      font-size: 19px;
    }
    /* The exhibit becomes a stacked list, one entry per source. */
    .a-table,
    .a-table tbody,
    .a-table tr,
    .a-table td {
      display: block;
      width: auto;
    }
    .a-table thead {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
    }
    .a-table tr {
      padding: 12px 0;
      border-bottom: 1px solid var(--riprap-rule-hairline);
    }
    .a-table td {
      display: grid;
      grid-template-columns: 6.5em minmax(0, 1fr);
      column-gap: 12px;
      padding: 3px 0;
      border: 0;
    }
    .a-td-label {
      display: block;
      font-size: 14px;
      color: var(--ink-secondary);
    }
    /* An empty figure cell says nothing: drop the row. */
    .a-td-figure:not(:has(.a-fig)) {
      display: none;
    }
  }
</style>
