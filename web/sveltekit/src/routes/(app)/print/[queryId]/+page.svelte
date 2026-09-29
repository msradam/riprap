<script lang="ts">
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { onMount, tick } from 'svelte';
  import AnswerProse from '$lib/components/briefing/AnswerProse.svelte';
  import SourceNotes from '$lib/components/briefing/SourceNotes.svelte';
  import SourceList from '$lib/components/briefing/SourceList.svelte';
  import SourcesChecked from '$lib/components/briefing/SourcesChecked.svelte';
  import EvidenceTable from '$lib/components/briefing/EvidenceTable.svelte';
  import { loadSnapshot, type PrintSnapshot } from '$lib/stores/briefingState.svelte';
  import { formatGeneratedAt } from '$lib/client/gallery';
  import { APP_VERSION } from '$lib/version';
  import { STATIC_SITE, QUICKSTART_URL } from '$lib/staticSite';

  /** The print packet: the briefing as a public report on Letter paper.
   *  Page one carries the title, the meta line, the answer and its source
   *  notes; the evidence table and the source lists start on page two.
   *  Built from the snapshot the briefing page saved in this browser. */
  let queryId = $derived(page.params.queryId ?? '');
  let snapshot = $state<PrintSnapshot | null>(null);
  let hydrationFailed = $state(false);
  let printed = $state(false);

  onMount(async () => {
    const s = loadSnapshot(queryId);
    // Snapshots saved before the report layout carry no answer.
    if (!s?.answer) {
      hydrationFailed = true;
      return;
    }
    snapshot = s;
    await tick();
    // A closed list prints as its summary only.
    for (const d of document.querySelectorAll<HTMLDetailsElement>('.print-doc details')) d.open = true;
    // Wait one frame so the DOM lays out before opening the print dialog.
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

  const norm = (t: string) => t.replace(/\s+/g, ' ').trim().toLowerCase();

  let title = $derived(snapshot ? snapshot.question || snapshot.queryText : '');
  let place = $derived(
    snapshot?.resolvedPlace && norm(snapshot.resolvedPlace) === norm(title) ? 'the place named above' : snapshot?.resolvedPlace
  );
  let kindLine = $derived(snapshot?.kind ? `Flood-exposure briefing, ${snapshot.kind}` : 'Flood-exposure briefing');
  let citations = $derived(snapshot ? Object.values(snapshot.citations).sort((a, b) => a.n - b.n) : []);
  let answerCites = $derived(citations.filter((c) => snapshot?.cited?.includes(c.id)));
  let cardCount = $derived(snapshot?.evidence?.groups.reduce((n, g) => n + g.cards.length, 0) ?? 0);
  let findings = $derived(new Map(Object.entries(snapshot?.evidence?.findings ?? {})));
  let summary = $derived(snapshot?.leadLabel === 'In brief' ? 'summary' : 'answer');
  // SourcesChecked reads the page's source lists; the snapshot keeps them
  // without ids.
  let lists = $derived(
    snapshot
      ? {
          consulted: snapshot.consulted?.map((c, i) => ({ id: `${i}-${c.title}`, ...c })),
          hasConsultedList: !!snapshot.consulted?.some((c) => !c.failed),
          noData: snapshot.noData ?? [],
          notChecked: snapshot.notChecked
        }
      : null
  );
  let showLists = $derived(!!lists && (!!lists.consulted || lists.noData.length > 0 || lists.notChecked !== undefined));
  // "2026-09-27 17:05 UTC": when the briefing was generated (for a gallery
  // entry, when the snapshot was built), not the time of printing.
  let generated = $derived(snapshot ? formatGeneratedAt(snapshot.generatedAt) : '');

  /** A CSS string literal that is safe inside a <style> element. */
  function cssString(s: string): string {
    return JSON.stringify(s.replace(/\s+/g, ' ')).replace(/</g, '\\3c ');
  }
  // The @page running header is plain CSS and cannot read the snapshot,
  // so the place, date and version are written into it here.
  let pageStyle = $derived(
    snapshot
      ? `<style>@page { @top-left { content: ${cssString(`Riprap: ${snapshot.resolvedPlace || snapshot.queryText}`)}; } ` +
        `@top-right { content: ${cssString(`Generated ${generated}, v${APP_VERSION}`)}; } }</style>`
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
    <div class="print-controls no-print">
      <button type="button" onclick={reprint}>print / save as PDF</button>
      <span class="hint">
        {printed ? 'Print dialog opened. Print again at any time.' : 'Opening the print dialog.'}
      </span>
    </div>

    <header class="print-head">
      <p class="print-kind">{kindLine}</p>
      <h1 class="print-title">{title}</h1>
      <p class="print-meta">
        {#if place}<span><span class="print-meta-label">Briefing for:</span> {place}</span>{/if}
        <span>Generated <span class="data">{generated}</span></span>
        <span>Riprap <span class="data">v{APP_VERSION}</span></span>
      </p>
    </header>

    <section class="print-answer" aria-labelledby="print-answer-h">
      <h2 id="print-answer-h" class="visually-hidden">{snapshot.leadLabel}</h2>
      {#if snapshot.lead}<p class="print-lead">{snapshot.lead}</p>{/if}
      {#each snapshot.answer ?? [] as parts, i (i)}
        <AnswerProse {parts} citations={snapshot.citations} class="print-answer-p" />
      {/each}
      {#if snapshot.unanswered}
        <p class="print-answer-p">
          This question was not answered directly. Riprap is running without a language model here,
          so this is the evidence briefing for the place above.
        </p>
      {/if}
      {#if snapshot.checks}<p class="print-quiet">{snapshot.checks}</p>{/if}
      {#if snapshot.mode}<p class="print-quiet">{snapshot.mode}</p>{/if}
      {#each snapshot.scope ?? [] as parts, i (i)}
        <AnswerProse {parts} citations={snapshot.citations} class="print-quiet" />
      {/each}
    </section>

    {#if answerCites.length}
      <section class="print-notes" aria-labelledby="print-notes-h">
        <h3 id="print-notes-h" class="print-h3">Sources for the {summary}</h3>
        <SourceNotes citations={answerCites} label="Sources for the {summary}" />
      </section>
    {/if}

    <div class="print-rest">
      {#if cardCount && snapshot.evidence}
        <section class="print-block" aria-labelledby="print-evidence-h">
          <h2 id="print-evidence-h" class="print-h2">Evidence</h2>
          <EvidenceTable
            groups={snapshot.evidence.groups}
            {findings}
            citations={snapshot.citations}
            notRun={snapshot.evidence.notRun}
            labelledby="print-evidence-h"
          />
        </section>
      {/if}

      {#each snapshot.body ?? [] as s, i (i)}
        <section class="print-block" aria-labelledby={s.label ? `print-sec-${i}` : undefined}>
          {#if s.label}<h2 id="print-sec-{i}" class="print-h2">{s.label}</h2>{/if}
          {#each s.paras as parts, j (j)}
            <AnswerProse {parts} citations={snapshot.citations} class="print-body" />
          {/each}
        </section>
      {/each}

      <section class="print-block" aria-labelledby="print-sources-h">
        <h2 id="print-sources-h" class="print-h2">Sources and method</h2>
        {#if citations.length}
          <div class="print-citations">
            <h3 class="print-h3">Sources cited</h3>
            <SourceList {citations} noted={snapshot.cited ?? []} />
          </div>
        {/if}
        {#if showLists && lists}
          <h3 class="print-h3">What was checked</h3>
          <SourcesChecked {lists} />
        {/if}
        {#if snapshot.outOfScope?.length}
          <h3 class="print-h3">Out of scope</h3>
          {#each snapshot.outOfScope as parts, i (i)}
            <AnswerProse {parts} citations={snapshot.citations} class="print-quiet" />
          {/each}
        {/if}
      </section>
    </div>

    <footer class="print-foot">
      Riprap briefings are built from cited source values, or written by a language model with
      each claim checked against its cited sources. A number without a citation is not present
      in a source document.
    </footer>
  </article>
{:else}
  <div class="empty"><p>Loading the briefing.</p></div>
{/if}

<style>
  .print-doc {
    max-width: 7in;
    margin: 32px auto 64px;
    padding: 0 32px;
    font-family: var(--font-sans);
    font-size: 15px;
    line-height: 1.5;
    color: var(--ink);
  }
  .print-doc :global(a) {
    color: var(--riprap-text-link);
  }
  .print-doc :global(:focus-visible) {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }

  .print-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 16px;
    margin-bottom: 32px;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .print-controls button {
    min-height: 36px;
    padding: 0 16px;
    border: 0;
    border-radius: 3px;
    background: var(--ink);
    color: var(--paper);
    font: 600 15px var(--font-sans);
    cursor: pointer;
  }

  .print-kind,
  .print-meta {
    margin: 0;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .print-title {
    margin: 2px 0 0;
    max-width: 30ch;
    font-size: 30px;
    font-weight: 600;
    line-height: 1.18;
    letter-spacing: -0.01em;
    text-wrap: balance;
    overflow-wrap: anywhere;
  }
  .print-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0 20px;
    margin-top: 6px;
  }
  .print-meta-label {
    font-weight: 600;
  }

  .print-answer {
    margin-top: 24px;
  }
  .print-lead {
    margin: 0 0 6px;
    font-size: 48px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
  }
  .print-doc :global(.print-answer-p) {
    margin: 0 0 12px;
    max-width: 54ch;
    font-size: 18px;
    line-height: 1.5;
  }
  .print-doc :global(.print-quiet) {
    margin: 0 0 6px;
    max-width: 54ch;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .print-doc :global(.print-body) {
    margin: 0 0 12px;
    max-width: 54ch;
    font-size: 15px;
  }
  .print-doc :global(.inline-cite) {
    text-decoration: none;
  }
  .print-doc :global(.inline-cite sup) {
    padding-left: 0.15em;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 0;
  }

  .print-notes {
    margin-top: 16px;
  }
  .print-notes :global(.source-notes) {
    columns: 2;
    column-gap: 32px;
  }
  .print-notes :global(.source-note) {
    break-inside: avoid;
  }

  .print-h2 {
    margin: 0 0 8px;
    font-size: 20px;
    font-weight: 600;
    line-height: 1.25;
    break-after: avoid;
  }
  .print-h3 {
    margin: 24px 0 8px;
    font-size: 15px;
    font-weight: 600;
    line-height: 1.3;
    break-after: avoid;
  }
  .print-notes .print-h3 {
    margin-top: 0;
  }
  .print-block {
    margin-top: 32px;
  }
  .print-rest > .print-block:first-child {
    margin-top: 48px;
  }
  .print-citations :global(.source-list) {
    columns: 2;
    column-gap: 32px;
  }
  .print-citations :global(.source-entry) {
    break-inside: avoid;
  }

  .print-foot {
    margin-top: 32px;
    max-width: 54ch;
    font-size: 13px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }

  .empty {
    max-width: 600px;
    margin: 96px auto;
    padding: 0 24px;
    font-family: var(--font-sans);
    font-size: 17px;
    line-height: 1.55;
    color: var(--ink);
  }
  .empty h1 {
    margin: 0 0 12px;
    font-size: 30px;
    font-weight: 600;
    line-height: 1.2;
  }
  .empty a {
    color: var(--riprap-text-link);
  }
  .empty .empty-action {
    display: inline-block;
    min-height: 24px;
    padding: 8px 16px;
    border-radius: 3px;
    background: var(--ink);
    color: var(--paper);
    font-weight: 600;
    text-decoration: none;
  }

  @media (max-width: 640px) {
    .print-doc {
      margin: 16px auto 48px;
      padding: 0 16px;
    }
    .print-title {
      font-size: 26px;
    }
    .print-lead {
      font-size: 40px;
    }
    .print-notes :global(.source-notes),
    .print-citations :global(.source-list) {
      columns: auto;
    }
    .empty {
      margin: 48px auto;
      padding: 0 16px;
    }
  }

  @media print {
    .no-print {
      display: none !important;
    }
    .print-doc {
      max-width: none;
      margin: 0;
      padding: 0;
      font-size: 10.5pt;
    }
    .print-doc :global(a) {
      color: inherit;
      text-decoration: none;
    }
    .print-doc :global(.inline-cite) {
      color: #005ea2;
    }
    .print-title {
      font-size: 22pt;
    }
    .print-lead {
      font-size: 34pt;
    }
    .print-doc :global(.print-answer-p) {
      font-size: 13pt;
    }
    .print-doc :global(.source-notes),
    .print-doc :global(.source-list),
    .print-doc :global(.sources-checked),
    .print-doc :global(.ev-table),
    .print-doc :global(.ev-not-run) {
      font-size: 9.5pt;
    }
    .print-doc :global(.ev-row),
    .print-doc :global(.source-entry),
    .print-doc :global(.sources-checked li) {
      break-inside: avoid;
    }
    /* The evidence and the source lists start on page two. */
    .print-rest {
      break-before: page;
    }
    .print-rest > .print-block:first-child {
      margin-top: 0;
    }
    /* The app layout's paper ground and min-height printed as a grey block
       after the last line. */
    :global(html),
    :global(body),
    :global(main) {
      background: white !important;
      min-height: 0 !important;
    }
    @page {
      size: letter;
      margin: 0.75in;
      @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font: 9pt "Sofia Sans";
        color: #334155;
      }
      @bottom-left {
        content: "github.com/msradam/riprap";
        font: 9pt "Sofia Sans";
        color: #334155;
      }
    }
  }
</style>
