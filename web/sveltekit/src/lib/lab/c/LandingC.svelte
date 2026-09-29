<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import type { Story } from '$lib/lab/labModel';
  import { formatGeneratedAt } from '$lib/client/gallery';
  import { EXAMPLES } from '$lib/samples';
  import { STATIC_SITE, QUICKSTART_URL } from '$lib/staticSite';
  import { STONE_META, STONE_ORDER } from '$lib/types/card';

  interface Props { stories: Story[] }
  let { stories }: Props = $props();

  const KIND = { question: 'Question', address: 'Address', district: 'District' } as const;

  let q = $state('');

  // Same as LandHero: "Edit query" arrives as ?q=<query>.
  function prefill(node: HTMLInputElement) {
    const v = new URLSearchParams(window.location.search).get('q');
    if (v) {
      q = v;
      node.focus();
    }
  }

  function briefHref(v: string) {
    return resolve('/(app)/q/[queryId]', { queryId: encodeURIComponent(v) });
  }

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const v = q.trim();
    if (v) goto(briefHref(v));
  }
</script>

<div class="lc">
  <section class="lc-tool" aria-labelledby="lc-h1">
    <h1 id="lc-h1" class="lc-h1">Flood-exposure briefings for New York City</h1>
    <p class="lc-deck">
      {#if STATIC_SITE}
        Riprap turns an address, a community district, or a flood question into a written briefing on flood exposure.
      {:else}
        Type an address, a community district, or a flood question. Get a written briefing on flood exposure.
      {/if}
      Every claim cites a public record from FEMA, NOAA, USGS, or city open data.
    </p>

    {#if STATIC_SITE}
      <p class="lc-static">
        This public copy has no backend. <a href="#lc-gallery">Read the precomputed briefings</a>, or
        <a href={QUICKSTART_URL}>run locally to ask your own question</a>.
      </p>
    {:else}
      <form class="lc-form" role="search" onsubmit={submit}>
        <label for="lc-q" class="lc-label">Address, community district, or flood question</label>
        <div class="lc-row">
          <input
            id="lc-q"
            type="text"
            {@attach prefill}
            bind:value={q}
            placeholder="90-01 183rd Street, Queens"
            autocomplete="off"
            enterkeyhint="search"
          />
          <button type="submit">Brief this place</button>
        </div>
      </form>
      <ul class="lc-examples" aria-label="Example queries">
        {#each EXAMPLES as ex (ex.kind)}
          <li><span class="lc-ex-kind">{ex.kind}:</span> <a href={briefHref(ex.q)}>{ex.q}</a></li>
        {/each}
      </ul>
    {/if}
  </section>

  <section id="lc-gallery" class="lc-gallery" aria-labelledby="lc-gallery-h">
    <h2 id="lc-gallery-h" class="lc-h2">Precomputed briefings ({stories.length})</h2>
    <table class="lc-table">
      <thead>
        <tr>
          <th scope="col">Place</th>
          <th scope="col">Kind</th>
          <th scope="col">Question</th>
          <th scope="col">Answer</th>
          <th scope="col">Snapshot</th>
        </tr>
      </thead>
      <tbody>
        {#each stories as s (s.slug)}
          <tr>
            <th scope="row" class="lc-place" data-label="Place">
              <a href={resolve('/(app)/lab/[dir]/gallery/[slug]', { dir: 'c', slug: s.slug })}>{s.neighborhood}</a>
              <span class="lc-address">{s.address}</span>
            </th>
            <td data-label="Kind">{KIND[s.kind]}</td>
            <td class="lc-question" data-label="Question">{s.question ?? 'Place briefing'}</td>
            <td class="lc-answer" data-label="Answer"><span class="lc-clamp" title={s.lead}>{s.lead}</span></td>
            <td class="lc-mono lc-date" data-label="Snapshot">{formatGeneratedAt(s.generated_at)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>

  <section class="lc-about" aria-labelledby="lc-about-h">
    <h2 id="lc-about-h" class="lc-h2">What a briefing contains</h2>
    <p>
      Each briefing routes through a fixed taxonomy of public-record specialists. Each Stone is a class of evidence.
      Together they form the briefing, and every claim in the output traces back to the Stone that produced it.
    </p>
    <dl class="lc-stones">
      {#each STONE_ORDER as key (key)}
        <div>
          <dt>{STONE_META[key].name}, {STONE_META[key].role}</dt>
          <dd>{STONE_META[key].tag}</dd>
        </div>
      {/each}
    </dl>
    <p>
      Riprap returns evidence, not advice. It does not predict damage to specific properties or substitute for
      professional engineering judgment.
    </p>
  </section>
</div>

<style>
  .lc {
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 32px 56px;
    font-family: var(--font-sans);
    font-size: 15px;
    line-height: 1.5;
    color: var(--ink);
  }
  .lc :global(:focus-visible) {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  .lc a {
    color: var(--accent);
  }
  .lc-mono {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }
  .lc-h1 {
    margin: 0;
    font-size: 32px;
    font-weight: 600;
    line-height: 1.2;
  }
  .lc-deck {
    margin: 8px 0 0;
    max-width: 70ch;
    font-size: 16px;
    color: var(--ink-secondary);
  }
  .lc-h2 {
    margin: 40px 0 8px;
    font-size: 20px;
    font-weight: 600;
    line-height: 1.25;
  }

  /* Query box */
  .lc-form {
    margin-top: 20px;
    max-width: 760px;
  }
  .lc-label {
    display: block;
    margin-bottom: 4px;
    font-size: 14px;
    font-weight: 600;
  }
  .lc-row {
    display: flex;
    gap: 8px;
  }
  .lc-row input {
    flex: 1;
    min-width: 0;
    min-height: 48px;
    padding: 0 14px;
    border: 1px solid var(--ink-secondary);
    border-radius: 1px;
    background: var(--riprap-white);
    font: inherit;
    font-size: 17px;
    color: var(--ink);
  }
  .lc-row input::placeholder {
    color: var(--ink-tertiary);
  }
  .lc-row button {
    min-height: 48px;
    padding: 0 20px;
    border: 0;
    border-radius: 1px;
    background: var(--accent);
    font: inherit;
    font-size: 16px;
    font-weight: 600;
    color: var(--riprap-white);
    cursor: pointer;
  }
  .lc-row button:hover {
    background: var(--tier-modeled);
  }
  .lc-examples {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 24px;
    margin: 10px 0 0;
    padding: 0;
    list-style: none;
    font-size: 14px;
  }
  .lc-examples a {
    display: inline-block;
    min-height: 24px;
  }
  .lc-ex-kind {
    color: var(--ink-secondary);
  }
  .lc-static {
    margin: 16px 0 0;
    font-size: 16px;
  }

  /* Gallery table */
  .lc-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    line-height: 1.4;
  }
  .lc-table th,
  .lc-table td {
    padding: 8px 12px 8px 0;
    text-align: left;
    vertical-align: top;
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  .lc-table thead th {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-secondary);
    border-bottom: 1px solid var(--rule);
  }
  .lc-place {
    width: 17%;
    font-weight: 400;
  }
  .lc-place a {
    font-weight: 600;
  }
  .lc-address {
    display: block;
    color: var(--ink-secondary);
  }
  .lc-question {
    width: 21%;
  }
  .lc-clamp {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
  }
  .lc-date {
    white-space: nowrap;
    font-size: 13px;
    padding-right: 0;
  }

  /* What a briefing contains */
  .lc-about {
    max-width: 80ch;
  }
  .lc-about p {
    margin: 0 0 10px;
  }
  .lc-stones {
    margin: 0 0 12px;
  }
  .lc-stones div {
    display: flex;
    flex-wrap: wrap;
    gap: 0 8px;
    padding: 4px 0;
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  .lc-stones dt {
    font-weight: 600;
    min-width: 16rem;
  }
  .lc-stones dd {
    margin: 0;
    color: var(--ink-secondary);
  }

  @media (max-width: 720px) {
    .lc {
      padding: 20px 16px 40px;
    }
    .lc-h1 {
      font-size: 26px;
    }
    .lc-row {
      flex-direction: column;
    }
    .lc-table thead {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip-path: inset(50%);
    }
    .lc-table,
    .lc-table tbody,
    .lc-table tr,
    .lc-table th,
    .lc-table td {
      display: block;
      width: auto;
    }
    .lc-table tr {
      padding: 10px 0;
      border-bottom: 1px solid var(--riprap-rule-hairline);
    }
    .lc-table th,
    .lc-table td {
      padding: 0;
      border: 0;
    }
    .lc-table td[data-label='Kind'],
    .lc-date {
      display: inline-block;
      margin-right: 12px;
      color: var(--ink-secondary);
    }
    .lc-question {
      margin-top: 2px;
    }
  }
</style>
