<script lang="ts">
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { onMount } from 'svelte';
  import Briefing from '$lib/components/briefing/Briefing.svelte';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import TierKey from '$lib/components/glyphs/TierKey.svelte';
  import { loadSnapshot, type PrintSnapshot } from '$lib/stores/briefingState.svelte';
  import { formatGeneratedAt } from '$lib/client/gallery';
  import { APP_VERSION } from '$lib/version';
  import { splitBriefing } from '$lib/client/parseBriefing';
  import { STATIC_SITE, QUICKSTART_URL } from '$lib/staticSite';

  let queryId = $derived(page.params.queryId ?? '');
  let snapshot = $state<PrintSnapshot | null>(null);
  let hydrationFailed = $state(false);
  let printed = $state(false);

  onMount(() => {
    const s = loadSnapshot(queryId);
    if (!s) {
      hydrationFailed = true;
      return;
    }
    snapshot = s;
    // Wait one rAF so the DOM lays out before opening the print dialog.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        window.print();
        printed = true;
      });
    });
  });

  function reprint() {
    window.print();
  }

  let citationEntries = $derived(
    snapshot ? Object.values(snapshot.citations).sort((a, b) => a.n - b.n) : []
  );
  // "2026-09-27 17:05 UTC": the time the briefing was generated (for a
  // gallery entry, when the snapshot was built), not the time of printing.
  let generated = $derived(snapshot ? formatGeneratedAt(snapshot.generatedAt) : '');
  let blocks = $derived(snapshot?.blocks ?? []);
  // Same split as on screen: the Answer leads, the scope preamble and the
  // Out of scope section print as quiet notes, the sources lists sit
  // between the lead and the body.
  let split = $derived(splitBriefing(blocks));
  let subLine = $derived.by(() => {
    if (!snapshot) return '';
    const n = citationEntries.length;
    const parts = [snapshot.mode, `${n} ${n === 1 ? 'source' : 'sources'} cited`];
    if (snapshot.noData?.length) parts.push(`${snapshot.noData.length} with no data`);
    if (snapshot.notChecked) parts.push(`${snapshot.notChecked.length} not checked for this question`);
    return parts.filter(Boolean).join(' · ');
  });

  /** A CSS string literal that is safe inside a <style> element. */
  function cssString(s: string): string {
    return JSON.stringify(s.replace(/\s+/g, ' ')).replace(/</g, '\\3c ');
  }
  // The @page running header is plain CSS and cannot read the snapshot,
  // so the place, date and version are written into it here.
  let pageStyle = $derived(
    snapshot
      ? `<style>@page { @top-left { content: ${cssString(`riprap · ${snapshot.resolvedPlace || snapshot.queryText}`)}; } ` +
        `@top-right { content: ${cssString(`Generated ${generated} · v${APP_VERSION}`)}; } }</style>`
      : ''
  );
</script>

<svelte:head>
  <title>Riprap briefing: {snapshot?.question || snapshot?.queryText || 'print'}</title>
  <!-- eslint-disable-next-line svelte/no-at-html-tags -- string built from escaped CSS literals above -->
  {@html pageStyle}
</svelte:head>

{#if hydrationFailed}
  <div class="empty">
    <h1>This briefing has not run in this browser</h1>
    <p>
      The print view is built from a briefing that has already run in this browser. Nothing
      is stored on a server, so a print link opened in another browser starts empty.
    </p>
    {#if STATIC_SITE}
      <p>
        <a class="empty-action" href="{resolve('/(app)/gallery')}/">Open the gallery</a>
      </p>
      <p>Choose <strong>Print this briefing</strong> on a gallery entry, or <a href={QUICKSTART_URL}>run locally to ask your own question</a>.</p>
    {:else}
      <p>
        <a class="empty-action" href={resolve('/(app)/q/[queryId]', { queryId: encodeURIComponent(queryId) })}>Run this briefing</a>
      </p>
      <p>When it finishes, choose <strong>print</strong> in the header to come back here.</p>
    {/if}
  </div>
{:else if snapshot}
  <article class="print-doc">
    <header class="print-head">
      <div class="print-head-top">
        <span class="wordmark">riprap</span>
        <span class="meta">flood-exposure briefing · v{APP_VERSION} · generated {generated}</span>
      </div>
      {#if snapshot.question}
        <p class="print-eyebrow">Question</p>
        <h1 class="print-title">{snapshot.question}</h1>
      {:else}
        <h1 class="print-title">{snapshot.queryText}</h1>
      {/if}
      {#if snapshot.resolvedPlace}
        <p class="print-place"><span class="print-place-label">Briefing for:</span> {snapshot.resolvedPlace}</p>
      {/if}
      {#if subLine}
        <div class="print-sub">{subLine}</div>
      {/if}
    </header>

    <div class="print-controls no-print">
      <button type="button" onclick={reprint}>print / save as PDF</button>
      <span class="hint">
        {printed ? 'Print dialog opened. Re-print anytime.' : 'Opening print dialog…'}
      </span>
    </div>

    <!-- The answer is short: keep it on one page. -->
    <div class="print-lead">
      {#if split.lead.length}
        <Briefing blocks={split.lead} citations={snapshot.citations} streaming={false} />
      {/if}
      {#if snapshot.unanswered}
        <p class="print-unanswered">
          This question was not answered directly. Riprap is running without a language model here,
          so this is the evidence briefing for the place above.
        </p>
      {/if}
    </div>
    {#if split.scope.length}
      <div class="scope-note"><Briefing blocks={split.scope} citations={snapshot.citations} streaming={false} /></div>
    {/if}

    {#if snapshot.consulted || snapshot.noData?.length || snapshot.notChecked}
      <section class="print-sources" aria-label="Sources consulted, sources with no data, and sources not checked">
        {#if snapshot.consulted}
          <div class="print-sources-col">
            <h2>Sources consulted ({snapshot.consulted.length})</h2>
            <ul>
              {#each snapshot.consulted as c, i (`${i}-${c.title}`)}
                <li>{c.title}{#if c.failed}: failed to respond{/if}</li>
              {/each}
            </ul>
          </div>
        {/if}
        {#if snapshot.noData?.length}
          <div class="print-sources-col">
            <h2>Ran but returned no data ({snapshot.noData.length})</h2>
            <ul>
              {#each snapshot.noData as t, i (`${i}-${t}`)}
                <li>{t}</li>
              {/each}
            </ul>
          </div>
        {/if}
        {#if snapshot.notChecked}
          <div class="print-sources-col">
            {#if snapshot.notChecked.length}
              <h2>Not checked for this question ({snapshot.notChecked.length})</h2>
              <ul>
                {#each snapshot.notChecked as t, i (`${i}-${t}`)}
                  <li>{t}</li>
                {/each}
              </ul>
            {:else}
              <h2>Not checked for this question</h2>
              <p>None of the sources for this kind of place were skipped.</p>
            {/if}
          </div>
        {/if}
      </section>
    {/if}

    {#if split.body.length}
      <Briefing blocks={split.body} citations={snapshot.citations} streaming={false} />
    {/if}
    {#if split.outOfScope.length}
      <div class="scope-note scope-note-end print-keep">
        <p class="scope-note-label">Out of scope</p>
        <Briefing blocks={split.outOfScope} citations={snapshot.citations} streaming={false} />
      </div>
    {/if}

    {#if citationEntries.length}
      <section class="print-citations">
        <h2>Citations</h2>
        <div class="print-tier-key"><TierKey /></div>
        <ol>
          {#each citationEntries as c (c.id)}
            <li>
              <span class="cn">[{c.n}]</span>
              <span class="cglyph"><TierGlyph tier={c.tier} size={9} color="var(--tier-{c.tier})" /></span>
              <span class="csrc">{c.source}</span>
              <span class="cvint">v. {c.vintage}</span>
              <div class="ctitle">{c.title}</div>
              {#if c.url && c.url.startsWith('http')}
                <div class="curl">{c.url}</div>
              {/if}
              <div class="cdocid">doc_id <code>{c.docId}</code></div>
            </li>
          {/each}
        </ol>
      </section>
    {/if}

    <footer class="print-foot">
      Generated {generated} ·
      Riprap briefings are built from cited source values, or written by an LLM
      with each claim checked against its cited sources.
      Numbers without bracketed citations are not present in source documents.
    </footer>
  </article>
{:else}
  <div class="empty"><p>Loading…</p></div>
{/if}

<style>
  .print-doc {
    max-width: 7.5in;
    margin: 0.5in auto;
    padding: 0 0.5in;
    font-family: var(--font-serif), Georgia, serif;
    color: #0F172A;
    background: white;
  }
  .print-head { border-bottom: 1pt solid #0F172A; padding-bottom: 8pt; margin-bottom: 14pt; }
  .print-head-top {
    display: flex; justify-content: space-between; align-items: baseline; gap: 12pt;
    flex-wrap: wrap;
    font: 9pt var(--font-mono, "Overpass Mono"); color: #4E5A6E;
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .wordmark { font-weight: 600; color: #0F172A; }
  .print-eyebrow {
    margin: 10pt 0 0;
    font: 9pt var(--font-mono, "Overpass Mono"); color: #4E5A6E;
    text-transform: uppercase; letter-spacing: 0.06em;
  }
  .print-title {
    font: 600 22pt var(--font-sans, "Sofia Sans");
    margin: 8pt 0 4pt; line-height: 1.15;
  }
  .print-eyebrow + .print-title { margin-top: 2pt; }
  .print-place {
    margin: 4pt 0; font: 12pt var(--font-sans, "Sofia Sans"); color: #0F172A;
  }
  .print-place-label { font-weight: 600; }
  .print-sub {
    font: 10pt var(--font-mono, "Overpass Mono"); color: #4E5A6E;
  }
  .print-controls {
    display: flex; gap: 12px; align-items: center;
    margin: 12pt 0; padding: 8pt 10pt;
    background: #F4F6F9; border: 1px solid #DCE2EA; border-radius: 4px;
    font: 10pt var(--font-sans, "Sofia Sans");
  }
  .print-controls button {
    font: 10pt var(--font-sans, "Sofia Sans");
    padding: 4pt 10pt; background: #0F172A; color: white; border: 0;
    border-radius: 3px; cursor: pointer;
  }
  .hint { color: #4E5A6E; font-size: 9pt; }
  .print-unanswered {
    margin: 10pt 0; font: 11pt var(--font-sans, "Sofia Sans"); color: #334155;
  }
  .print-sources {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150pt, 1fr)); gap: 12pt 16pt;
    margin: 12pt 0 16pt; padding: 8pt 0; border-top: 1pt solid #CBD5E1; border-bottom: 1pt solid #CBD5E1;
    font: 10pt var(--font-sans, "Sofia Sans"); line-height: 1.4;
  }
  /* A long list (17 sources not checked) may split across pages; keeping
     it whole pushed the lists to page 2 and left page 1 half empty. Each
     item and each heading stays with its neighbour instead. */
  .print-sources li { break-inside: avoid; }
  .print-sources h2 { font: 600 11pt var(--font-sans, "Sofia Sans"); margin: 0 0 4pt; break-after: avoid; }
  .print-lead { break-inside: avoid; }
  .print-keep { break-inside: avoid; }
  .scope-note-label { break-after: avoid; }
  .print-tier-key { margin: 0 0 10pt; break-inside: avoid; }
  .print-sources ul { margin: 0; padding-left: 12pt; }
  .print-sources p { margin: 0; }
  /* No forced page break before the citations: it left page 2 mostly
     blank. The heading stays with the first entries instead. */
  .print-citations {
    margin-top: 18pt; padding-top: 8pt; border-top: 1pt solid #0F172A;
    font-variant-numeric: tabular-nums;
  }
  .print-citations h2 {
    font: 600 13pt var(--font-sans, "Sofia Sans"); margin: 0 0 8pt;
    break-after: avoid;
  }
  .print-citations ol { list-style: none; padding: 0; margin: 0; }
  .print-citations li {
    margin-bottom: 8pt; padding-left: 28pt; position: relative;
    font-size: 10pt; line-height: 1.4;
    break-inside: avoid;
  }
  .cn {
    position: absolute; left: 0; top: 0;
    font: 600 10pt var(--font-mono, "Overpass Mono"); color: #005EA2;
  }
  .cglyph { display: inline-block; vertical-align: middle; margin-right: 4pt; }
  .csrc { font-weight: 600; }
  .cvint { color: #4E5A6E; margin-left: 6pt; font-size: 9pt; }
  .ctitle { color: #0F172A; }
  .curl { font: 9pt var(--font-mono, "Overpass Mono"); color: #005EA2; word-break: break-all; }
  .cdocid { font: 9pt var(--font-mono, "Overpass Mono"); color: #4E5A6E; }
  .print-foot {
    margin-top: 18pt; padding-top: 6pt; border-top: 1pt solid #CBD5E1;
    font: 9pt var(--font-mono, "Overpass Mono"); color: #4E5A6E;
    line-height: 1.5;
  }
  .empty {
    max-width: 600px; margin: 100px auto; padding: 24px;
    font-family: var(--font-sans, "Sofia Sans");
    color: #0F172A;
  }
  .empty h1 { font-size: 20pt; margin-bottom: 8pt; line-height: 1.2; }
  .empty a { color: #005EA2; }
  .empty-action {
    display: inline-block;
    padding: 8px 16px;
    min-height: 24px;
    background: var(--ink);
    color: var(--paper) !important;
    font-weight: 600;
    text-decoration: none;
  }
  .empty-action:hover { background: #0F172A; }

  @media (max-width: 640px) {
    .print-doc { margin: 24px auto; padding: 0 16px; }
    .print-sources { grid-template-columns: 1fr; }
    .empty { margin: 48px auto; padding: 16px; }
  }

  @media print {
    .no-print { display: none !important; }
    .print-doc { margin: 0; padding: 0; max-width: none; }
    /* The app layout's paper ground and min-height printed as a grey block
       after the last line. */
    :global(html), :global(body), :global(main) { background: white !important; min-height: 0 !important; }
    @page {
      size: letter;
      margin: 0.85in 0.85in 0.85in 1in;
      @bottom-right {
        content: "page " counter(page) " of " counter(pages);
        font: 9pt "Overpass Mono"; color: #4E5A6E;
      }
      @bottom-left {
        content: "github.com/msradam/riprap";
        font: 9pt "Overpass Mono"; color: #4E5A6E;
      }
    }
  }
</style>
