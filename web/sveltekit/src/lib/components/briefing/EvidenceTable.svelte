<script lang="ts">
  import type { Citation } from '$lib/types/claim';
  import { citationOf, type EvidenceCard } from '$lib/client/briefingModel';
  import { TIER_WORDS } from '$lib/types/tier';
  import { asOfDate, figureOf, leadClause, sharedStem, snapshotNote, withoutSubject } from '$lib/client/briefingText';
  import { activateCitation } from '$lib/stores/citations.svelte';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';

  /** The evidence exhibit: one row per source that found something, the
   *  rows the answer cites first, then one group per Stone. A `closed`
   *  group (experimental and forecast sources) follows the table as its own
   *  folded table. On phones each row is a stacked block; the cells keep
   *  their table semantics. In a narrow column (a place briefing's main
   *  column) the Source, Tier and Data as of cells are clipped to one
   *  pixel for assistive tech and the finding cell shows the same words
   *  on a line above the finding, so the finding keeps the width. */
  interface Props {
    groups: { key: string; name: string; role: string | null; cards: EvidenceCard[]; closed?: boolean }[];
    findings: Map<string, { first: string; rest: string } | null>;
    citations: Record<string, Citation>;
    notRun: string[];
    labelledby: string;
    /** Where the page lists the sources not run; the footer then points
     *  there instead of repeating the list. */
    notRunHref?: string;
    /** Gallery pages: when the snapshot was made ("2026-09-29 12:34 UTC").
     *  A live reading is dated to it; a forecast or alert says so. */
    snapshotAt?: string | null;
  }
  let { groups, findings, citations, notRun, labelledby, notRunHref, snapshotAt = null }: Props = $props();

  let snapshotDate = $derived(snapshotAt?.slice(0, 10) ?? null);

  let open = $derived(groups.filter((g) => !g.closed));
  let folded = $derived(groups.filter((g) => g.closed));

  /** A figure label longer than this reads in the finding cell instead of
   *  wrapping down the narrow Figure column. */
  const SHORT_LABEL = 16;

  /** A live reading on a gallery page was read when the snapshot was made. */
  const atSnapshot = (vintage: string) => !!snapshotDate && /^live$/i.test(vintage.trim());

  /** Open the linked list if it is a closed disclosure; the link then
   *  scrolls to it as usual. */
  function openTarget() {
    const el = notRunHref ? document.querySelector(notRunHref) : null;
    if (el instanceof HTMLDetailsElement) el.open = true;
  }

  // Explicit headers: the group heading is a second level of th, which
  // scope alone does not resolve for every checker. Each table has its
  // own column ids.
  const uid = $props.id();
  type Col = 'source' | 'finding' | 'figure' | 'tier' | 'asof' | 'cite';
  const col = (t: string, name: Col) => `${uid}-${t}-col-${name}`;
  /** A merged row's parts share one date column only when they share a date. */
  const oneDate = (c: EvidenceCard) => !c.parts || new Set(c.parts.map((p) => p.vintage)).size === 1;
  /** A merged row whose findings differ only in a closing parenthetical
   *  shows the shared stem once and each scenario's parenthetical. */
  const stemOf = (c: EvidenceCard) => {
    const firsts = (c.parts ?? []).map((p) => findings.get(p.id)?.first);
    return firsts.every((f) => f) ? sharedStem(firsts as string[]) : null;
  };
</script>

{#snippet head(t: string)}
  <thead>
    <tr>
      <th scope="col" id={col(t, 'source')}>Source</th>
      <th scope="col" id={col(t, 'finding')}>Finding</th>
      <th scope="col" class="ev-num" id={col(t, 'figure')}>Figure</th>
      <th scope="col" id={col(t, 'tier')}>Tier</th>
      <th scope="col" id={col(t, 'asof')}>Data as of</th>
      <th scope="col" class="ev-num" id={col(t, 'cite')}>Cite</th>
    </tr>
  </thead>
{/snippet}

{#snippet date(vintage: string)}
  {#if atSnapshot(vintage)}at snapshot, <span class="data ev-date">{snapshotDate}</span>{:else}<span class="data" title={vintage}>{asOfDate(vintage)}</span>{/if}
{/snippet}

{#snippet sentence(first: string)}
  {@const lc = leadClause(withoutSubject(first))}
  <span class="ev-find"><span class="ev-lead">{lc.lead}</span>{lc.tail}</span>
{/snippet}

{#snippet cite(cit: Citation, sup: boolean)}
  <a
    href="#cite-{cit.id}"
    class={sup ? 'inline-cite' : 'data'}
    onclick={(e) => activateCitation(e, cit.id)}
    aria-label="Citation {cit.n}: {cit.source}, {cit.title}"
  >{#if sup}<sup>{cit.n}</sup>{:else}{cit.n}{/if}</a>
{/snippet}

{#snippet row(c: EvidenceCard, t: string, gid: string | null)}
  {@const fig = figureOf(c)}
  {@const find = findings.get(c.id)}
  {@const cit = c.parts ? null : citationOf(c, citations)}
  {@const longLabel = !!fig?.label && fig.label.length > SHORT_LABEL}
  {@const same = oneDate(c)}
  {@const note = snapshotNote(c.docId, snapshotAt, find?.first)}
  {@const h = (name: Col) => (gid ? `${col(t, name)} ${gid}` : col(t, name))}
  <tr class="ev-row">
    <td class="ev-source" headers={h('source')}>
      {#if c.experimental}{c.source} <span class="exp-badge">Experimental</span>{:else}{c.source}{/if}
    </td>
    <td class="ev-finding" headers={h('finding')}>
      <!-- Shown only in the narrow layout, where the Source, Tier and Data
           as of cells are clipped; hidden from assistive tech, which reads
           those cells. -->
      <span class="ev-source-line" aria-hidden="true">
        {#if c.experimental}{c.source} <span class="exp-badge">Experimental</span>{:else}{c.source}{/if}
        <span class="ev-meta"><span class="ev-mark" style:color="var(--tier-{c.tier})"><TierGlyph tier={c.tier} size={11} /></span>{TIER_WORDS[c.tier] ?? c.tier}{#if same}{#if atSnapshot(c.vintage)}, {@render date(c.vintage)}{:else}, data as of {@render date(c.vintage)}{/if}{/if}</span>
      </span>
      {#if c.parts}
        {@const st = stemOf(c)}
        <!-- One finding per scenario, each with its own citation. When the
             findings share a stem it is set once, above the scenarios. -->
        {#if st}<div class="ev-stem">{@render sentence(`${st.stem}:`)}</div>{/if}
        <ul class="ev-scenarios">
          {#each c.parts as p, i (p.id)}
            {@const pf = findings.get(p.id)}
            {@const pc = citationOf(p, citations)}
            <li>
              {#if st}{st.tails[i]}{#if pf?.rest}{` ${pf.rest}`}{/if}{:else if pf}{@render sentence(pf.first)}{#if pf.rest}{` ${pf.rest}`}{/if}{:else}{p.title}{/if}{#if !same}&#32;(data as of {@render date(p.vintage)}){/if}{#if pc}{@render cite(pc, true)}{/if}
            </li>
          {/each}
        </ul>
      {:else}
        <div class="ev-measure">
          {#if find}{@render sentence(find.first)}{#if find.rest}{` ${find.rest}`}{/if}{/if}
          {#if note}<span class="ev-snap">{note}</span>{/if}
          <span class="ev-dataset">{c.title}</span>
          {#if longLabel}<span class="ev-dataset">Figure: {fig?.label}</span>{/if}
        </div>
      {/if}
    </td>
    <td class={['ev-num', 'ev-figure', !fig && 'is-empty']} headers={h('figure')}>
      {#if fig}
        <span class="ev-label" aria-hidden="true">Figure</span>
        <span class="data ev-fig">{fig.value}</span>
        {#if fig.label && !longLabel}<span class="ev-fig-label">{fig.label}</span>{/if}
      {/if}
    </td>
    <td class="ev-tier" headers={h('tier')}>
      <span class="ev-mark" style:color="var(--tier-{c.tier})" aria-hidden="true"><TierGlyph tier={c.tier} size={11} /></span>
      {TIER_WORDS[c.tier] ?? c.tier}
    </td>
    <td class={['ev-asof', !same && 'is-empty']} headers={h('asof')}>
      {#if same}
        <!-- "at snapshot" is its own label; "Data as of at snapshot" is not English. -->
        {#if !atSnapshot(c.vintage)}<span class="ev-label" aria-hidden="true">Data as of</span>{/if}
        {@render date(c.vintage)}
      {/if}
    </td>
    <td class={['ev-num', 'ev-cite', !cit && 'is-empty']} headers={h('cite')}>
      {#if cit}
        <span class="ev-label" aria-hidden="true">Cite</span>
        {@render cite(cit, false)}
      {/if}
    </td>
  </tr>
{/snippet}

<div class="ev-wrap">
<table class="ev-table" aria-labelledby={labelledby}>
  {@render head('main')}
  {#each open as g, gi (g.key)}
    {@const gid = `${uid}-group-${gi}`}
    <tbody>
      <tr class="ev-group">
        <th colspan="6" scope="rowgroup" id={gid}>{g.name}{#if g.role}, {g.role}{/if}</th>
      </tr>
      {#each g.cards as c (c.id)}{@render row(c, 'main', gid)}{/each}
    </tbody>
  {/each}
</table>
<!-- Experimental and forecast sources the answer does not cite: worth
     seeing, folded so they do not sit at the weight of the records. A
     citation mark pointing inside opens it (activateCitation). -->
{#each folded as g (g.key)}
  <details class="ev-folded">
    <summary id="{uid}-{g.key}-h">{g.name}</summary>
    <table class="ev-table" aria-labelledby="{uid}-{g.key}-h">
      {@render head(g.key)}
      <tbody>
        {#each g.cards as c (c.id)}{@render row(c, g.key, null)}{/each}
      </tbody>
    </table>
  </details>
{/each}
{#if notRun.length && notRunHref}
  <p class="ev-not-run">
    Sources not run for this question are listed under <a href={notRunHref} onclick={openTarget}>Sources and method</a>.
  </p>
{:else if notRun.length}
  <p class="ev-not-run">Not run for this question: {notRun.join(', ')}.</p>
{/if}
</div>

<style>
  .ev-wrap {
    container: ev / inline-size;
  }
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
    width: 17%;
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
  .ev-date {
    white-space: nowrap;
  }
  .ev-mark {
    display: inline-block;
    margin-right: 4px;
    vertical-align: -1px;
  }
  .ev-scenarios {
    max-width: 54ch;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .ev-stem {
    max-width: 54ch;
    margin-bottom: 4px;
  }
  .ev-scenarios li + li {
    margin-top: 4px;
  }
  .ev-folded {
    margin-top: 16px;
  }
  .ev-folded > summary {
    min-height: 24px;
    padding: 4px 0;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }
  .ev-folded > .ev-table {
    margin-top: 8px;
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
  .ev-label,
  .ev-source-line {
    display: none;
  }
  .ev-not-run {
    margin: 12px 0 0;
    max-width: 54ch;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }

  /* Narrow column on a wider screen (a place briefing's main column; the
     question page's full-width table and phones keep their layouts): the
     Source, Tier and Data as of columns shrink to a clipped pixel that
     assistive tech still reads, and the finding cell shows the source,
     tier and date on one secondary line above the finding. Only the
     finding's first clause is heavy. */
  @media screen and (min-width: 641px) {
    @container ev (max-width: 760px) {
      .ev-table {
        table-layout: fixed;
      }
      thead th:nth-child(1),
      thead th:nth-child(4),
      thead th:nth-child(5),
      .ev-source,
      .ev-tier,
      .ev-asof {
        width: 1px;
        padding: 0;
        overflow: hidden;
        white-space: nowrap;
        clip-path: inset(50%);
      }
      thead th.ev-num:nth-child(3) {
        width: 88px;
      }
      thead th.ev-num:nth-child(6) {
        width: 36px;
      }
      .ev-source-line {
        display: block;
        margin-bottom: 2px;
        color: var(--ink-secondary);
        overflow-wrap: anywhere;
      }
      /* The tier mark separates the source from its tier and date. */
      .ev-meta .ev-mark {
        margin-left: 4px;
      }
      .ev-find {
        font-weight: 400;
      }
      .ev-lead {
        font-weight: 600;
      }
    }
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
      padding: 24px 0 0;
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
    .ev-figure.is-empty,
    .ev-asof.is-empty,
    .ev-cite.is-empty {
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
