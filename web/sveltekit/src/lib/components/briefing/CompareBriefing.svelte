<script lang="ts">
  import AnswerProse from './AnswerProse.svelte';
  import SourceNotes from './SourceNotes.svelte';
  import { parseBriefing } from '$lib/client/parseBriefing';
  import { citedIn } from '$lib/client/briefingText';
  import { heatCompareRows, type CompareRow } from '$lib/client/briefingModel';
  import type { Citation } from '$lib/types/claim';

  interface Target {
    label: string;
    address: string;
    /** The place's own result, keyed by source id. */
    state?: Record<string, unknown>;
  }

  interface Props {
    paragraph: string;
    citations: Record<string, Citation>;
    targets: Target[];
    /** Per-place step result payloads from the agent stream, keyed by step name. */
    structuredA?: Record<string, unknown>;
    structuredB?: Record<string, unknown>;
    /** A heat comparison: the table shows the two places' heat records
     *  and no flood rows. */
    heat?: boolean;
  }

  let { paragraph, citations, targets, structuredA = {}, structuredB = {}, heat = false }: Props = $props();

  // Split the merged compare paragraph at the --- divider.
  // Each half begins with `## PLACE A/B: <address>` which we strip to get
  // clean 4-section markdown for parseBriefing.
  // What the backend writes above PLACE A (nothing is scored or ranked, and
  // for heat one comparing sentence) is about both places.
  const PLACE_A = /^##\s+PLACE\s+A:/m;
  const introMd = $derived(PLACE_A.test(paragraph) ? paragraph.split(PLACE_A, 1)[0].trim() : '');

  function splitParagraph(para: string): { address: string; md: string }[] {
    const halves = para.slice(PLACE_A.test(para) ? para.search(PLACE_A) : 0).split(/\n\s*---\s*\n/, 2);
    return halves.map((half, i) => {
      const m = /^##\s+PLACE\s+[AB]:\s+(.+?)(\n|$)/m.exec(half.trim());
      const address = m?.[1]?.trim() ?? targets[i]?.address ?? `Place ${String.fromCharCode(65 + i)}`;
      const md = half.replace(/^##\s+PLACE\s+[AB]:\s+.+(\n|$)/m, '').trim();
      return { address, md };
    });
  }

  const halves = $derived(splitParagraph(paragraph));
  const intro = $derived(parseBriefing(introMd, citations));
  const parsedA = $derived(parseBriefing(halves[0]?.md ?? '', citations));
  const parsedB = $derived(parseBriefing(halves[1]?.md ?? '', citations));

  // Both columns share the merged citation registry so cross-column
  // doc_id numbering stays consistent.
  const allCitations = $derived({
    ...citations,
    ...intro.citations,
    ...parsedA.citations,
    ...parsedB.citations
  });
  // The sources both columns cite, in reading order, as one set of notes.
  const notes = $derived(
    citedIn([intro, parsedA, parsedB].flatMap((p) => p.blocks.flatMap((b) => (b.kind === 'prose' ? [b.parts] : [])))).flatMap(
      (id) => (allCitations[id] ? [allCitations[id]] : [])
    )
  );

  type DeltaRow = CompareRow;

  function getNum(steps: Record<string, unknown>, stepName: string, field: string): number | undefined {
    const r = steps[stepName];
    if (!r || typeof r !== 'object') return undefined;
    const v = (r as Record<string, unknown>)[field];
    return typeof v === 'number' ? v : undefined;
  }

  function getBool(steps: Record<string, unknown>, stepName: string, field: string): boolean | undefined {
    const r = steps[stepName];
    if (!r || typeof r !== 'object') return undefined;
    const v = (r as Record<string, unknown>)[field];
    return typeof v === 'boolean' ? v : undefined;
  }

  // Derive diff rows from structured specialist step payloads.
  // This avoids parsing prose for numbers, which incorrectly picks up
  // address street numbers as "Status" comparisons.
  const deltaRows = $derived.by<DeltaRow[]>(() => {
    const rows: DeltaRow[] = [];

    // Sandy inundation zone membership
    const sandyA = getBool(structuredA, 'sandy_inundation', 'inside');
    const sandyB = getBool(structuredB, 'sandy_inundation', 'inside');
    if (sandyA !== undefined && sandyB !== undefined && sandyA !== sandyB) {
      rows.push({ label: 'Sandy zone', ctx: '', aVal: sandyA ? 'inside' : 'outside', bVal: sandyB ? 'inside' : 'outside' });
    }

    // 311 flood complaints (5-year radius)
    const n311A = getNum(structuredA, 'nyc311', 'n');
    const n311B = getNum(structuredB, 'nyc311', 'n');
    if (n311A !== undefined && n311B !== undefined && n311A !== n311B) {
      rows.push({ label: '311 complaints', ctx: '5 y', aVal: String(n311A), bVal: String(n311B) });
    }

    // Terrain elevation
    const elevA = getNum(structuredA, 'microtopo_lidar', 'point_elev_m');
    const elevB = getNum(structuredB, 'microtopo_lidar', 'point_elev_m');
    if (elevA !== undefined && elevB !== undefined && Math.abs(elevA - elevB) > 0.5) {
      rows.push({ label: 'Elevation', ctx: '', aVal: `${elevA.toFixed(1)} m`, bVal: `${elevB.toFixed(1)} m` });
    }

    // FloodNet sensor flood events (3-year)
    const fnA = getNum(structuredA, 'floodnet', 'n_flood_events_3y');
    const fnB = getNum(structuredB, 'floodnet', 'n_flood_events_3y');
    if (fnA !== undefined && fnB !== undefined && fnA !== fnB) {
      rows.push({ label: 'Sensor events', ctx: 'last 3 y', aVal: String(fnA), bVal: String(fnB) });
    }

    // Ida 2021 high-water mark (nearest within 800 m)
    const idaA = getNum(structuredA, 'ida_hwm_2021', 'max_height_above_gnd_ft');
    const idaB = getNum(structuredB, 'ida_hwm_2021', 'max_height_above_gnd_ft');
    if (idaA !== undefined && idaB !== undefined && Math.abs(idaA - idaB) > 0.1) {
      rows.push({ label: 'Ida 2021 HWM', ctx: 'ft above gnd', aVal: `${idaA.toFixed(2)} ft`, bVal: `${idaB.toFixed(2)} ft` });
    }

    return rows.slice(0, 4);
  });
  // A heat comparison sets every heat record both places have, whether
  // or not they differ; a flood comparison sets up to four differences.
  const rows = $derived(heat ? heatCompareRows(targets[0]?.state ?? {}, targets[1]?.state ?? {}) : deltaRows);
</script>

<div class="compare-layout">
  {#if introMd}
    <section class="compare-intro" aria-label="About this comparison">
      {#each intro.blocks as block, j (j)}
        {#if block.kind === 'prose'}
          <AnswerProse parts={block.parts} citations={allCitations} class="compare-para" />
        {/if}
      {/each}
    </section>
  {/if}
  {#if rows.length > 0}
    <section class="compare-delta-bar" aria-labelledby="compare-delta-h">
      <h2 id="compare-delta-h" class="compare-delta-title">{heat ? 'Heat records, side by side' : 'Key differences'}</h2>
      <table class={['compare-delta-table', heat && 'is-heat']}>
        <thead>
          <tr>
            <th scope="col">Measure</th>
            <th scope="col">{halves[0]?.address ?? 'Place A'}</th>
            <th scope="col">{halves[1]?.address ?? 'Place B'}</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row, j (j)}
            <tr>
              <th scope="row">{row.label}{#if row.ctx}<span class="compare-ctx">{heat ? '' : ', '}{row.ctx}</span>{/if}</th>
              <td class="data">{row.aVal}</td>
              <td class="data">{row.bVal}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}

  <div class="compare-cols">
    {#each halves as half, i (i)}
      <section class="compare-col" aria-labelledby="compare-place-{i}">
        <h2 id="compare-place-{i}" class="compare-address-header address-header">{half.address}</h2>
        {#each (i === 0 ? parsedA : parsedB).blocks as block, j (j)}
          {#if block.kind === 'head'}
            <h3 class="briefing-section-head">{block.label}</h3>
          {:else if block.kind === 'prose'}
            <AnswerProse parts={block.parts} citations={allCitations} class="compare-para" />
          {/if}
        {/each}
      </section>
    {/each}
  </div>

  {#if notes.length}
    <section class="compare-notes" aria-labelledby="compare-notes-h">
      <h2 id="compare-notes-h" class="compare-notes-h">Sources for the comparison</h2>
      <SourceNotes citations={notes} label="Sources for the comparison" />
    </section>
  {/if}
</div>

<style>
  .compare-layout {
    width: 100%;
  }
  .compare-delta-bar {
    margin-bottom: 32px;
  }
  .compare-delta-title,
  .compare-notes-h {
    margin: 0 0 8px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }
  .compare-delta-table {
    border-collapse: collapse;
    font-size: 14px;
    line-height: 1.45;
  }
  .compare-delta-table th,
  .compare-delta-table td {
    padding: 8px 24px 8px 0;
    text-align: left;
    vertical-align: top;
  }
  .compare-delta-table thead th {
    padding-top: 0;
    font-weight: 600;
    color: var(--ink-secondary);
  }
  .compare-delta-table tr {
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  .compare-delta-table thead tr {
    border-bottom-color: var(--rule-soft);
  }
  .compare-delta-table tbody th {
    font-weight: 600;
  }
  /* What a heat measure is, on its own line under its name. */
  .is-heat .compare-ctx {
    display: block;
    max-width: 54ch;
    font-weight: 400;
    color: var(--ink-secondary);
  }

  .compare-cols {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0 48px;
    align-items: start;
  }
  .compare-col {
    min-width: 0;
  }
  .compare-address-header {
    margin: 0 0 12px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
    overflow-wrap: anywhere;
  }
  .briefing-section-head {
    margin: 24px 0 6px;
    font-size: 17px;
    font-weight: 600;
    line-height: 1.3;
  }
  .compare-intro {
    margin-bottom: 32px;
  }
  .compare-intro :global(.compare-para),
  .compare-col :global(.compare-para) {
    margin: 0 0 12px;
    max-width: 60ch;
    font-size: 17px;
    line-height: 1.55;
  }
  .compare-notes {
    margin-top: 32px;
  }
  .compare-notes :global(.source-notes) {
    columns: 2;
    column-gap: 48px;
  }
  .compare-notes :global(.source-note) {
    break-inside: avoid;
  }

  /* Narrow viewport (under 900 px): the columns stack. */
  @media (max-width: 899px) {
    .compare-cols {
      grid-template-columns: minmax(0, 1fr);
      gap: 32px;
    }
    .compare-notes :global(.source-notes) {
      columns: auto;
    }
  }
</style>
