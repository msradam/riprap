<script lang="ts">
  import { resolve } from '$app/paths';
  import type { RunState } from '$lib/client/runState.svelte';
  import type { GalleryEntry } from '$lib/client/gallery';
  import type { LabModel } from '$lib/lab/labModel';
  import type { Card } from '$lib/types/card';
  import type { Tier } from '$lib/types/tier';
  import { STONE_META, STONE_ORDER } from '$lib/types/card';
  import { citations as cstore } from '$lib/stores/citations.svelte';
  import LabProse from '$lib/lab/LabProse.svelte';
  import LabNotes from '$lib/lab/LabNotes.svelte';
  import LabSources from '$lib/lab/LabSources.svelte';
  import LabMap from '$lib/lab/LabMap.svelte';
  import DroppedClaims from '$lib/components/briefing/DroppedClaims.svelte';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';

  interface Props { run: RunState; model: LabModel; entry: GalleryEntry }
  let { run, model }: Props = $props();

  const KIND = { question: 'Question', address: 'Address', district: 'District' } as const;
  const TIER_WORDS: Record<Tier, string> = {
    empirical: 'Measured',
    modeled: 'Modeled',
    proxy: 'Proxy',
    synthetic: 'Synthetic'
  };
  // A leading figure in a card headline: "82 calls", "3.3%", "0.3/wk", "0 m²".
  const FIGURE_RE = /^\d[\d,.]*(?:%|\/\w+)?(?:\s?(?:m²|km|cm|mm|ft|in|m|calls|events)\b)?/;

  let title = $derived(model.question ?? model.place);
  let consulted = $derived(model.lists.consulted ?? []);
  let failed = $derived(consulted.filter((s) => s.failed).length);
  /** "Yes" and "No" read as words and take a full stop; a count does not. */
  let lead = $derived(
    model.leadWord ? (/^\d/.test(model.leadWord) ? model.leadWord : `${model.leadWord}.`) : null
  );
  let method = $derived(model.metaCard?.metaRows?.find((r) => r.k === 'mode')?.v ?? null);
  let groups = $derived(
    STONE_ORDER.map((key) => ({ key, meta: STONE_META[key], cards: model.cards.filter((c) => c.stone === key) })).filter(
      (g) => g.cards.length
    )
  );
  /** Doc ids the answer itself cites (model.cited also counts the sections). */
  let answerCites = $derived(new Set(model.answer.flat().flatMap((p) => (p.cite ? [p.cite] : []))));
  let absentNames = $derived([...new Set(model.absent.map((c) => c.source))]);
  let jumps = $derived([
    { href: '#bc-answer', label: 'Answer' },
    { href: '#bc-evidence', label: 'Evidence' },
    ...(model.body.length ? [{ href: '#bc-sections', label: 'Sections' }] : []),
    { href: '#bc-map', label: 'Map' },
    { href: '#bc-sources', label: 'Sources' }
  ]);

  function citationOf(c: Card) {
    return (c.citeId && model.citationsById[c.citeId]) || model.citationsById[c.docId] || null;
  }

  function finding(c: Card) {
    return c.body ?? c.sub ?? c.headline ?? '';
  }

  function figure(c: Card): { value: string; label: string | null } | null {
    const s = c.scalars?.[0];
    if (s) return { value: s.unit ? `${s.value} ${s.unit}` : s.value, label: s.label };
    const m = c.headline ? FIGURE_RE.exec(c.headline) : null;
    return m ? { value: m[0].trim(), label: null } : null;
  }

  /** ISO timestamps show their date; the full value stays in the title. */
  function asOf(v: string) {
    return /^\d{4}-\d{2}-\d{2}T/.test(v) ? v.slice(0, 10) : v;
  }

  /** Same behaviour as LabProse: mark active, focus the note, scroll once. */
  function activate(e: MouseEvent, id: string) {
    e.preventDefault();
    cstore.active = id;
    const el = document.getElementById(`cite-${id}`);
    if (!el) return;
    el.focus({ preventScroll: true });
    el.scrollIntoView({ block: 'nearest' });
  }
</script>

<article class="bc">
  <header class="bc-head">
    <h1 class="bc-h1">{title}</h1>
    <dl class="bc-kv">
      {#if model.question}
        <div><dt>Place</dt><dd>{model.place}</dd></div>
      {/if}
      <div><dt>Kind</dt><dd>{KIND[model.kind]}</dd></div>
      <div><dt>Snapshot</dt><dd class="bc-mono">{model.generated}</dd></div>
      <div>
        <dt>Sources</dt>
        <dd><span class="bc-mono">{consulted.length}</span> consulted{#if failed}, <span class="bc-mono">{failed}</span> failed to respond{/if}</dd>
      </div>
      {#if model.checks}
        <div><dt>Checks</dt><dd>ran, <a href="#bc-how">see how this briefing was made</a></dd></div>
      {:else if method}
        <div><dt>Method</dt><dd>{method}</dd></div>
      {/if}
    </dl>
    <nav class="bc-jumps" aria-label="On this page">
      <ul>
        {#each jumps as j (j.href)}
          <li><a href={j.href}>{j.label}</a></li>
        {/each}
        <li class="bc-jumps-gallery"><a href={resolve('/(app)/lab/[dir]', { dir: 'c' })}>Gallery</a></li>
      </ul>
    </nav>
  </header>

  <div class="bc-grid">
    <section id="bc-answer" class="bc-answer" aria-labelledby="bc-answer-h">
      <h2 id="bc-answer-h" class="bc-answer-label">{model.leadLabel ?? 'Answer'}</h2>
      {#if lead}<p class="bc-lead">{lead}</p>{/if}
      {#each model.answer as parts, i (i)}
        <LabProse {parts} citations={model.citationsById} cite="bracket" class="bc-answer-p" />
      {/each}
    </section>

    <section id="bc-evidence" class="bc-evidence" aria-labelledby="bc-evidence-h">
      <h2 id="bc-evidence-h" class="bc-h2">Evidence</h2>
      <table class="bc-table">
        <thead>
          <tr>
            <th scope="col">Source</th>
            <th scope="col">Finding</th>
            <th scope="col" class="bc-num">Figure</th>
            <th scope="col">Tier</th>
            <th scope="col">Data as of</th>
            <th scope="col">Cite</th>
          </tr>
        </thead>
        {#each groups as g (g.key)}
          <tbody>
            <tr class="bc-group">
              <th colspan="6" scope="colgroup">{g.meta.name}, {g.meta.role}</th>
            </tr>
            {#each g.cards as c (c.id)}
              {@const fig = figure(c)}
              {@const cit = citationOf(c)}
              <tr>
                <td class="bc-source" data-label="Source">
                  {c.source}{#if c.experimental}<span class="bc-badge">Experimental</span>{/if}
                </td>
                <td class="bc-finding" data-label="Finding"><strong>{c.title}.</strong> {finding(c)}</td>
                <td class="bc-num" data-label="Figure">
                  {#if fig}
                    <span class="bc-mono">{fig.value}</span>
                    {#if fig.label}<span class="bc-fig-label">{fig.label}</span>{/if}
                  {/if}
                </td>
                <td class="bc-tier" data-label="Tier">
                  <span class="bc-tier-mark" style:color="var(--tier-{c.tier})" aria-hidden="true"><TierGlyph tier={c.tier} size={10} /></span>
                  {TIER_WORDS[c.tier] ?? c.tier}
                </td>
                <td class="bc-mono bc-asof" data-label="Data as of" title={c.vintage}>{asOf(c.vintage)}</td>
                <td class="bc-cite" data-label="Cite">
                  {#if cit}
                    <a
                      href="#cite-{cit.id}"
                      class="bc-cite-link"
                      onclick={(e) => activate(e, cit.id)}
                      aria-label="Citation {cit.n}: {cit.source}, {cit.title}"
                    >[{cit.n}]</a>
                    {#if answerCites.has(cit.id)}<span class="bc-in-answer">in answer</span>{/if}
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        {/each}
      </table>
      {#if absentNames.length}
        <p class="bc-absent"><strong>No result:</strong> {absentNames.join('; ')}.</p>
      {/if}
    </section>

    <section id="bc-map" class="bc-map" aria-labelledby="bc-map-h">
      <div class="bc-map-sticky">
        <h2 id="bc-map-h" class="bc-h2">Map</h2>
        <LabMap {run} height="var(--bc-map-h)" class="bc-labmap" />
      </div>
    </section>
  </div>

  {#if model.body.length}
    <section id="bc-sections" class="bc-sections" aria-labelledby="bc-sections-h">
      <h2 id="bc-sections-h" class="bc-h2">Report sections</h2>
      <div class="bc-sections-grid">
        {#each model.body as s, i (i)}
          <div class="bc-section">
            {#if s.label}<h3 class="bc-h3">{s.label}</h3>{/if}
            {#each s.paras as parts, j (j)}
              <LabProse {parts} citations={model.citationsById} cite="bracket" class="bc-section-p" />
            {/each}
          </div>
        {/each}
      </div>
    </section>
  {/if}

  <section id="bc-sources" class="bc-end" aria-labelledby="bc-sources-h">
    <h2 id="bc-sources-h" class="bc-h2">Sources and method</h2>
    <LabSources lists={model.lists} class="bc-lists" />
    <LabNotes citations={model.citations} heading="Citations" headingLevel={3} class="bc-notes" />
    <DroppedClaims claims={model.dropped} />

    <div id="bc-how" class="bc-how">
      <h3 class="bc-h3">How this briefing was made</h3>
      <p>{model.modeLine}</p>
      {#if model.checks}<p>{model.checks}</p>{/if}
      <p>
        Snapshot <span class="bc-mono">{model.generated}</span>, commit <span class="bc-mono">{model.commit}</span>.
        {#if model.stamp}{model.stamp}.{/if}
      </p>
      {#each model.scope as parts, i (i)}
        <LabProse {parts} citations={model.citationsById} cite="bracket" />
      {/each}
      {#each model.outOfScope as parts, i (i)}
        <LabProse {parts} citations={model.citationsById} cite="bracket" />
      {/each}
      {#if model.metaCard?.models?.length}
        <table class="bc-models">
          <caption>Models in this briefing</caption>
          <thead>
            <tr><th scope="col">Model</th><th scope="col">Where</th><th scope="col">How</th></tr>
          </thead>
          <tbody>
            {#each model.metaCard.models as m, i (i)}
              <tr>
                <td>
                  {m.name}
                  <span class="bc-mono bc-repo">{#if m.href}<a href={m.href} target="_blank" rel="noopener noreferrer">{m.repo}</a>{:else}{m.repo}{/if}</span>
                </td>
                <td>{m.where}</td>
                <td>{m.how}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
    <p class="bc-back"><a href={resolve('/(app)/lab/[dir]', { dir: 'c' })}>Back to the gallery</a></p>
  </section>
</article>

<style>
  .bc {
    --bc-map-h: 460px;
    max-width: 1440px;
    margin: 0 auto;
    padding: 20px 32px 48px;
    color: var(--ink);
    font-family: var(--font-sans);
    font-size: 15px;
    line-height: 1.5;
  }
  .bc :global(:focus-visible) {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  .bc a {
    color: var(--accent);
  }
  .bc-mono {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }

  /* Header row */
  .bc-h1 {
    margin: 0 0 8px;
    font-size: 28px;
    font-weight: 600;
    line-height: 1.2;
    max-width: 60ch;
  }
  .bc-kv {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 24px;
    margin: 0;
  }
  .bc-kv div {
    display: flex;
    gap: 6px;
    align-items: baseline;
  }
  .bc-kv dt {
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .bc-kv dd {
    margin: 0;
    font-size: 14px;
  }
  .bc-jumps ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0 16px;
    margin: 6px 0 0;
    padding: 0;
    list-style: none;
    font-size: 14px;
  }
  .bc-jumps a {
    display: inline-block;
    min-height: 24px;
    line-height: 24px;
  }
  .bc-jumps-gallery {
    margin-left: auto;
  }

  /* Grid: text left, map right and sticky at desktop */
  .bc-grid {
    display: grid;
    grid-template-columns: minmax(0, 58fr) minmax(0, 42fr);
    grid-template-rows: auto auto 1fr;
    grid-template-areas:
      'answer map'
      'evidence map'
      '. map';
    gap: 0 32px;
    margin-top: 16px;
  }
  .bc-answer { grid-area: answer; }
  .bc-evidence { grid-area: evidence; }
  .bc-map { grid-area: map; }
  .bc-map-sticky {
    position: sticky;
    /* Below the sticky app header. */
    top: 72px;
  }
  .bc section,
  .bc :global(.lab-note) {
    scroll-margin-top: 72px;
  }
  .bc-map-sticky .bc-h2 {
    margin-top: 0;
  }

  .bc-h2 {
    margin: 32px 0 8px;
    font-size: 20px;
    font-weight: 600;
    line-height: 1.25;
  }
  .bc-h3 {
    margin: 0 0 4px;
    font-size: 16px;
    font-weight: 600;
    line-height: 1.3;
  }

  /* Answer */
  .bc-answer {
    border: 1px solid var(--rule-soft);
    background: var(--riprap-paper-inset);
    padding: 14px 20px 16px;
  }
  .bc-answer-label {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: var(--ink-secondary);
  }
  .bc-lead {
    margin: 0;
    font-size: 32px;
    font-weight: 700;
    line-height: 1.15;
  }
  .bc :global(.bc-answer-p) {
    margin: 6px 0 0;
    font-size: 17px;
    line-height: 1.5;
    max-width: 70ch;
  }
  .bc :global(.lab-cite) {
    font-family: var(--font-mono);
    font-size: 0.85em;
    text-decoration: none;
    margin-left: 2px;
  }

  /* Evidence table */
  .bc-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    line-height: 1.4;
  }
  .bc-table th,
  .bc-table td {
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  .bc-table th:first-child,
  .bc-table td:first-child {
    padding-left: 0;
  }
  .bc-table th:last-child,
  .bc-table td:last-child {
    padding-right: 0;
  }
  .bc-table thead th {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-secondary);
    border-bottom: 1px solid var(--rule);
  }
  .bc-group th {
    padding-top: 14px;
    font-size: 15px;
    font-weight: 600;
    color: var(--ink);
    border-bottom: 1px solid var(--rule-soft);
  }
  .bc-source {
    width: 15%;
    font-size: 13px;
    color: var(--ink-secondary);
    overflow-wrap: anywhere;
  }
  .bc-finding strong {
    font-weight: 600;
  }
  .bc-table .bc-num {
    text-align: right;
    white-space: nowrap;
  }
  td.bc-num .bc-mono {
    display: block;
  }
  .bc-fig-label {
    display: block;
    max-width: 16ch;
    margin-left: auto;
    white-space: normal;
    font-size: 13px;
    line-height: 1.3;
    color: var(--ink-secondary);
  }
  .bc-tier,
  .bc-asof,
  .bc-cite {
    white-space: nowrap;
  }
  .bc-tier-mark {
    display: inline-block;
    margin-right: 4px;
    vertical-align: -1px;
  }
  .bc-asof {
    font-size: 13px;
  }
  .bc-cite-link {
    display: inline-block;
    min-width: 24px;
    min-height: 24px;
    font-family: var(--font-mono);
    text-decoration: none;
  }
  .bc-in-answer {
    display: block;
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .bc-badge {
    display: inline-block;
    margin-left: 6px;
    padding: 0 5px;
    border: 1px solid var(--rule-soft);
    border-radius: 3px;
    font-size: 12px;
    color: var(--ink-secondary);
  }
  .bc-absent {
    margin: 10px 0 0;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .bc-absent strong {
    font-weight: 600;
    color: var(--ink);
  }

  /* Map column */
  .bc :global(.bc-labmap) {
    font-size: 14px;
  }
  .bc :global(.lab-map-skip) {
    position: absolute;
    left: -9999px;
  }
  .bc :global(.lab-map-skip:focus) {
    position: static;
    display: inline-block;
    margin-bottom: 6px;
  }
  .bc :global(.lab-map-layers) {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 16px;
    margin: 10px 0 0;
    padding: 0;
    border: 0;
  }
  .bc :global(.lab-map-layers legend) {
    padding: 0;
    margin-bottom: 2px;
    font-weight: 600;
  }
  .bc :global(.lab-map-layers label) {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 24px;
  }
  .bc :global(.lab-map-points) {
    margin-top: 8px;
    border-top: 1px solid var(--riprap-rule-hairline);
    padding-top: 6px;
  }
  .bc :global(.lab-map-points summary) {
    min-height: 24px;
    cursor: pointer;
    font-weight: 600;
  }
  .bc :global(.lab-map-points ul) {
    max-height: 260px;
    overflow-y: auto;
    margin: 4px 0 0;
    padding: 0;
    list-style: none;
  }
  .bc :global(.lab-map-point) {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0 12px;
    width: 100%;
    min-height: 32px;
    padding: 4px 0;
    border: 0;
    border-bottom: 1px solid var(--riprap-rule-hairline);
    background: none;
    font: inherit;
    text-align: left;
    color: var(--ink);
    cursor: pointer;
  }
  .bc :global(.lab-map-point-meta) {
    color: var(--ink-secondary);
  }
  .bc :global(.lab-map-note) {
    margin: 8px 0 0;
    font-size: 13px;
    color: var(--ink-secondary);
  }

  /* Report sections */
  .bc-sections-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px 32px;
  }
  .bc :global(.bc-section-p) {
    margin: 0 0 6px;
    font-size: 15px;
    line-height: 1.5;
  }

  /* Sources and method */
  .bc-end {
    margin-top: 16px;
    border-top: 1px solid var(--rule);
  }
  .bc :global(.bc-lists) {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px 32px;
    font-size: 14px;
  }
  .bc :global(.bc-lists summary) {
    min-height: 24px;
    cursor: pointer;
    font-weight: 600;
  }
  .bc :global(.bc-lists ul) {
    margin: 4px 0 0;
    padding-left: 18px;
  }
  .bc :global(.bc-lists li) {
    margin: 1px 0;
  }
  .bc :global(.lab-sources-none) {
    margin: 0;
  }
  .bc :global(.bc-notes) {
    margin-top: 24px;
    max-width: 1200px;
  }
  .bc :global(.lab-notes-heading) {
    margin: 0 0 4px;
    font-size: 16px;
    font-weight: 600;
  }
  .bc :global(.lab-notes-list) {
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 14px;
    line-height: 1.4;
  }
  .bc :global(.lab-note) {
    display: grid;
    grid-template-columns: 2.5rem minmax(0, 1fr) 15rem 11rem;
    gap: 0 12px;
    padding: 6px 0;
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  .bc :global(.lab-note-n) {
    grid-column: 1;
    grid-row: 1 / span 2;
    font-family: var(--font-mono);
    text-align: right;
  }
  .bc :global(.lab-note-source) { grid-column: 2; grid-row: 1; font-weight: 600; }
  .bc :global(.lab-note-title) { grid-column: 2; grid-row: 2; overflow-wrap: anywhere; }
  .bc :global(.lab-note-badge) {
    grid-column: 3;
    grid-row: 1;
    justify-self: start;
    align-self: start;
    padding: 0 5px;
    border: 1px solid var(--rule-soft);
    border-radius: 3px;
    font-size: 12px;
    color: var(--ink-secondary);
  }
  .bc :global(.lab-note-vintage) {
    grid-column: 3;
    grid-row: 2;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .bc :global(.lab-note-tier) { grid-column: 4; grid-row: 1; }
  .bc :global(.lab-note-docid) {
    grid-column: 4;
    grid-row: 2;
    font-size: 13px;
    color: var(--ink-secondary);
    overflow-wrap: anywhere;
  }
  .bc-how {
    margin-top: 24px;
    max-width: 90ch;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .bc-how p,
  .bc-how :global(p) {
    margin: 0 0 6px;
  }
  .bc-models {
    margin-top: 10px;
    border-collapse: collapse;
    font-size: 14px;
  }
  .bc-models caption {
    text-align: left;
    font-weight: 600;
    color: var(--ink);
    padding-bottom: 4px;
  }
  .bc-models th,
  .bc-models td {
    padding: 5px 16px 5px 0;
    text-align: left;
    vertical-align: top;
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  .bc-models th {
    font-size: 13px;
    font-weight: 600;
    border-bottom-color: var(--rule-soft);
  }
  .bc-repo {
    display: block;
    font-size: 13px;
    overflow-wrap: anywhere;
  }
  .bc-back {
    margin: 24px 0 0;
  }

  @media (max-width: 834px) {
    .bc {
      --bc-map-h: 300px;
      padding: 16px 16px 40px;
    }
    .bc-h1 {
      font-size: 24px;
    }
    .bc-grid {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: none;
      grid-template-areas: 'answer' 'evidence' 'map';
    }
    .bc-map-sticky {
      position: static;
    }
    .bc-map-sticky .bc-h2 {
      margin-top: 32px;
    }
    .bc-sections-grid,
    .bc :global(.bc-lists) {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  /* Phone: each evidence row becomes a stacked block. */
  @media (max-width: 640px) {
    .bc-table thead {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip-path: inset(50%);
    }
    .bc-table,
    .bc-table tbody,
    .bc-table tr,
    .bc-table th,
    .bc-table td {
      display: block;
    }
    .bc-table tr {
      padding: 8px 0;
      border-bottom: 1px solid var(--riprap-rule-hairline);
    }
    .bc-table tr.bc-group {
      padding: 14px 0 4px;
      border-bottom: 1px solid var(--rule-soft);
    }
    .bc-table th,
    .bc-table td {
      padding: 0;
      border: 0;
    }
    .bc-group th {
      padding: 0;
      border: 0;
    }
    .bc-source {
      width: auto;
    }
    .bc-table td.bc-num,
    .bc-table td.bc-tier,
    .bc-table td.bc-asof,
    .bc-table td.bc-cite {
      display: inline-block;
      margin-right: 14px;
      text-align: left;
      white-space: normal;
      vertical-align: baseline;
    }
    .bc-table td.bc-num:empty {
      display: none;
    }
    td.bc-num .bc-mono,
    .bc-fig-label,
    .bc-in-answer {
      display: inline;
      margin-left: 4px;
    }
    .bc-finding {
      margin: 2px 0 4px;
    }
    .bc :global(.lab-note) {
      grid-template-columns: 2rem minmax(0, 1fr);
    }
    .bc :global(.lab-note-n) { grid-row: 1 / span 5; }
    .bc :global(.lab-note-source),
    .bc :global(.lab-note-title),
    .bc :global(.lab-note-badge),
    .bc :global(.lab-note-vintage),
    .bc :global(.lab-note-tier),
    .bc :global(.lab-note-docid) {
      grid-column: 2;
      grid-row: auto;
    }
  }
</style>
