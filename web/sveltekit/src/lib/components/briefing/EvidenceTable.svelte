<script lang="ts">
  import type { Citation } from '$lib/types/claim';
  import type { EvidenceCard } from '$lib/client/briefingModel';
  import { TIER_WORDS } from '$lib/types/tier';
  import { asOfDate, figureOf } from '$lib/client/briefingText';
  import { activateCitation } from '$lib/stores/citations.svelte';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';

  /** The evidence exhibit: one row per source that found something, the
   *  rows the answer cites first, then one group per Stone. On phones each
   *  row is a stacked block; the cells keep their table semantics. */
  interface Props {
    groups: { key: string; name: string; role: string | null; cards: EvidenceCard[] }[];
    findings: Map<string, { first: string; rest: string } | null>;
    citations: Record<string, Citation>;
    notRun: string[];
    labelledby: string;
  }
  let { groups, findings, citations, notRun, labelledby }: Props = $props();

  // Explicit headers: the group heading is a second level of th, which
  // scope alone does not resolve for every checker.
  const uid = $props.id();
  const col = (name: 'source' | 'finding' | 'figure' | 'tier' | 'asof' | 'cite') => `${uid}-col-${name}`;

  function citationOf(c: EvidenceCard): Citation | null {
    return (c.citeId && citations[c.citeId]) || citations[c.docId] || null;
  }
</script>

<table class="ev-table" aria-labelledby={labelledby}>
  <thead>
    <tr>
      <th scope="col" id={col('source')}>Source</th>
      <th scope="col" id={col('finding')}>Finding</th>
      <th scope="col" class="ev-num" id={col('figure')}>Figure</th>
      <th scope="col" id={col('tier')}>Tier</th>
      <th scope="col" id={col('asof')}>Data as of</th>
      <th scope="col" class="ev-num" id={col('cite')}>Cite</th>
    </tr>
  </thead>
  {#each groups as g, gi (g.key)}
    {@const gid = `${uid}-group-${gi}`}
    <tbody>
      <tr class="ev-group">
        <th colspan="6" scope="rowgroup" id={gid}>{g.name}{#if g.role}, {g.role}{/if}</th>
      </tr>
      {#each g.cards as c (c.id)}
        {@const fig = figureOf(c)}
        {@const find = findings.get(c.id)}
        {@const cit = citationOf(c)}
        <tr class="ev-row">
          <td class="ev-source" headers="{col('source')} {gid}">
            {#if c.experimental}{c.source} <span class="exp-badge">Experimental</span>{:else}{c.source}{/if}
          </td>
          <td class="ev-finding" headers="{col('finding')} {gid}">
            <div class="ev-measure">
              {#if find}<span class="ev-find">{find.first}</span>{#if find.rest}{` ${find.rest}`}{/if}{/if}
              <span class="ev-dataset">{c.title}</span>
            </div>
          </td>
          <td class={['ev-num', 'ev-figure', !fig && 'is-empty']} headers="{col('figure')} {gid}">
            {#if fig}
              <span class="ev-label" aria-hidden="true">Figure</span>
              <span class="data ev-fig">{fig.value}</span>
              {#if fig.label}<span class="ev-fig-label">{fig.label}</span>{/if}
            {/if}
          </td>
          <td class="ev-tier" headers="{col('tier')} {gid}">
            <span class="ev-mark" style:color="var(--tier-{c.tier})" aria-hidden="true"><TierGlyph tier={c.tier} size={11} /></span>
            {TIER_WORDS[c.tier] ?? c.tier}
          </td>
          <td class="ev-asof" headers="{col('asof')} {gid}">
            <span class="ev-label" aria-hidden="true">Data as of</span>
            <span class="data" title={c.vintage}>{asOfDate(c.vintage)}</span>
          </td>
          <td class="ev-num ev-cite" headers="{col('cite')} {gid}">
            {#if cit}
              <span class="ev-label" aria-hidden="true">Cite</span>
              <a
                href="#cite-{cit.id}"
                class="data"
                onclick={(e) => activateCitation(e, cit.id)}
                aria-label="Citation {cit.n}: {cit.source}, {cit.title}"
              >{cit.n}</a>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  {/each}
</table>
{#if notRun.length}
  <p class="ev-not-run">Not run for this question: {notRun.join(', ')}.</p>
{/if}

<style>
  .ev-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink);
  }
  th,
  td {
    padding: 10px 12px 10px 0;
    text-align: left;
    vertical-align: top;
  }
  th:last-child,
  td:last-child {
    padding-right: 0;
  }
  thead th {
    padding-top: 0;
    padding-bottom: 8px;
    font-weight: 600;
    color: var(--ink-secondary);
  }
  thead tr {
    border-bottom: 1px solid var(--rule-soft);
  }
  .ev-group th {
    padding: 16px 0 2px;
    font-weight: 600;
  }
  /* A hairline between rows; the last row of a group has none, the next
     group's heading and spacing separate it. */
  .ev-row:not(:last-child) {
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  .ev-source {
    width: 20%;
    color: var(--ink-secondary);
    overflow-wrap: anywhere;
  }
  .ev-measure {
    max-width: 54ch;
  }
  .ev-find {
    font-weight: 600;
  }
  .ev-dataset,
  .ev-fig-label {
    display: block;
    margin-top: 2px;
    color: var(--ink-secondary);
  }
  .ev-num {
    text-align: right;
  }
  .ev-figure {
    width: 11%;
  }
  .ev-fig {
    display: block;
    white-space: nowrap;
  }
  .ev-fig-label {
    margin-left: auto;
    max-width: 14ch;
  }
  .ev-tier,
  .ev-asof {
    white-space: nowrap;
  }
  .ev-mark {
    display: inline-block;
    margin-right: 4px;
    vertical-align: -1px;
  }
  .ev-cite a {
    display: inline-block;
    min-width: 24px;
    min-height: 24px;
    color: var(--riprap-text-link);
    text-decoration: none;
    text-align: center;
  }
  .ev-cite a:hover,
  .ev-cite a:focus-visible {
    text-decoration: underline;
  }
  .ev-label {
    display: none;
  }
  .ev-not-run {
    margin: 12px 0 0;
    max-width: 54ch;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }

  /* Phone: each row becomes a stacked block. Source, then the finding,
     then one line of figure, tier, date and citation. */
  @media (max-width: 640px) {
    .ev-table,
    tbody,
    tr,
    th,
    td {
      display: block;
    }
    thead {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip-path: inset(50%);
    }
    tr.ev-row {
      padding: 10px 0;
    }
    .ev-group th {
      padding: 20px 0 0;
    }
    td,
    .ev-num,
    .ev-source,
    .ev-figure {
      padding: 0;
      width: auto;
      text-align: left;
    }
    .ev-finding {
      margin: 2px 0 4px;
    }
    .ev-figure,
    .ev-tier,
    .ev-asof,
    .ev-cite {
      display: inline-block;
      margin-right: 16px;
      white-space: normal;
    }
    .ev-figure.is-empty {
      display: none;
    }
    .ev-fig,
    .ev-fig-label {
      display: inline;
      margin: 0;
    }
    .ev-fig-label::before {
      content: ' ';
    }
    .ev-label {
      display: inline;
      margin-right: 4px;
      color: var(--ink-secondary);
    }
    .ev-cite a {
      min-width: 24px;
    }
  }
</style>
