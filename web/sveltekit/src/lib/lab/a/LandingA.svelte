<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { EXAMPLES } from '$lib/samples';
  import { STATIC_SITE, QUICKSTART_URL } from '$lib/staticSite';
  import type { Story } from '$lib/lab/labModel';

  /** Direction A landing, "report cover": title, deck, the query box, then
   *  one real gallery answer set as a miniature report page. */
  interface Props { stories: Story[] }
  let { stories }: Props = $props();

  const SPECIMEN = 'hollis-since-ida';
  const LEAD_RE = /^(Yes|No|Partly|Not clear|Unclear)\.\s*/;

  let specimen = $derived(stories.find((s) => s.slug === SPECIMEN) ?? null);
  let specimenLead = $derived.by(() => {
    if (!specimen) return null;
    const m = LEAD_RE.exec(specimen.lead);
    return m ? { word: `${m[1]}.`, text: specimen.lead.slice(m[0].length) } : { word: null, text: specimen.lead };
  });
  let others = $derived(stories.filter((s) => s.slug !== SPECIMEN));

  let q = $state('');

  // Same as LandHero: "Edit query" arrives as ?q=<query>, client only.
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

  const storyHref = (slug: string) => resolve('/(app)/lab/[dir]/gallery/[slug]', { dir: 'a', slug });
</script>

<div class="a-cover">
  <p class="a-kicker">Riprap, New York City</p>
  <h1 class="a-h1">Flood-exposure briefings for New York City</h1>
  <p class="a-deck">
    Riprap turns an address, a community district, or a flood question into a written briefing on flood exposure.
  </p>

  {#if STATIC_SITE}
    <!-- The public site has no backend: the gallery replaces the query box. -->
    <p class="a-static">
      <a class="a-button" href="{resolve('/(app)/gallery')}/">Read the precomputed briefings</a>
    </p>
    <p class="a-note">
      This public copy has no backend. <a href={QUICKSTART_URL}>Run locally to ask your own question</a>.
    </p>
  {:else}
    <form class="a-query" role="search" onsubmit={submit}>
      <label class="a-query-label" for="a-query-input">Address, community district, or flood question</label>
      <div class="a-query-row">
        <input
          id="a-query-input"
          type="text"
          {@attach prefill}
          bind:value={q}
          placeholder="Address, district such as QN 12, or a question"
          autocomplete="off"
          enterkeyhint="search"
        />
        <button type="submit">Brief this place</button>
      </div>
    </form>
    <p class="a-try-head" id="a-try">Or try one of these:</p>
    <ul class="a-try" aria-labelledby="a-try">
      {#each EXAMPLES as ex (ex.kind)}
        <li><span class="a-try-kind">{ex.kind}</span> <a href={briefHref(ex.q)}>{ex.q}</a></li>
      {/each}
    </ul>
  {/if}

  {#if specimen && specimenLead}
    <section class="a-specimen-wrap" aria-labelledby="a-spec-h">
      <h2 id="a-spec-h" class="a-h2">A specimen page</h2>
      <figure class="a-specimen">
        <a class="a-page" href={storyHref(specimen.slug)}>
          <span class="a-page-kind">Flood-exposure briefing, question</span>
          <span class="a-page-title">{specimen.question ?? specimen.neighborhood}</span>
          {#if specimenLead.word}<span class="a-page-lead">{specimenLead.word}</span>{/if}
          <span class="a-page-text">{specimenLead.text}</span>
          <span class="a-page-more">Read the full briefing</span>
        </a>
        <figcaption>
          A precomputed snapshot from the gallery, {specimen.neighborhood}, generated
          <time>{specimen.generated_at.slice(0, 10)}</time>.
        </figcaption>
      </figure>
    </section>
  {/if}

  {#if others.length}
    <section aria-labelledby="a-more-h">
      <h2 id="a-more-h" class="a-h2">More briefings</h2>
      <ul class="a-stories">
        {#each others as s (s.slug)}
          <li>
            <a href={storyHref(s.slug)}>{s.neighborhood}</a>
            <span>{s.question ?? 'Address briefing'}</span>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  <section aria-labelledby="a-what-h">
    <h2 id="a-what-h" class="a-h2">What a briefing is</h2>
    <p class="a-prose">
      Every claim cites a public record from FEMA, NOAA, USGS, or city open data, and each citation links to the
      dataset with its vintage. The briefing also lists the sources it consulted and the ones it did not check.
    </p>
    <p class="a-prose">
      Riprap reports evidence. It does not give advice, predict a particular day, or make a regulatory flood
      determination.
    </p>
  </section>
</div>

<style>
  .a-cover {
    max-width: 760px;
    margin: 0 auto;
    padding: 56px 32px 96px;
    font-family: var(--font-sans);
    color: var(--ink);
  }
  a {
    color: var(--riprap-text-link);
  }
  .a-cover :global(:focus-visible) {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  .a-kicker {
    margin: 0 0 10px;
    font-size: 16px;
    color: var(--ink-secondary);
  }
  .a-h1 {
    margin: 0;
    max-width: 18ch;
    font-size: 48px;
    font-weight: 600;
    line-height: 1.08;
    letter-spacing: -0.015em;
    text-wrap: balance;
  }
  .a-deck {
    margin: 16px 0 32px;
    max-width: 58ch;
    font-size: 20px;
    line-height: 1.5;
    color: var(--ink-secondary);
  }

  .a-query-label {
    display: block;
    margin-bottom: 6px;
    font-size: 15px;
    color: var(--ink-secondary);
  }
  .a-query-row {
    display: flex;
    gap: 8px;
  }
  .a-query input {
    flex: 1;
    min-width: 0;
    min-height: 52px;
    padding: 0 14px;
    font: inherit;
    font-size: 18px;
    color: var(--ink);
    background: var(--riprap-white);
    border: 1px solid var(--ink-secondary);
    border-radius: 2px;
  }
  .a-query input::placeholder {
    color: var(--ink-tertiary);
  }
  .a-query input:focus-visible {
    outline-offset: 0;
  }
  .a-query button,
  .a-button {
    display: inline-flex;
    align-items: center;
    min-height: 52px;
    padding: 0 20px;
    font: inherit;
    font-size: 16px;
    font-weight: 600;
    color: var(--paper);
    background: var(--ink);
    border: 0;
    border-radius: 2px;
    cursor: pointer;
    white-space: nowrap;
    text-decoration: none;
  }
  .a-query button:hover,
  .a-button:hover {
    background: #000;
  }
  .a-try-head {
    margin: 20px 0 4px;
    font-size: 15px;
    color: var(--ink-secondary);
  }
  .a-try {
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 16px;
  }
  .a-try li {
    padding: 2px 0;
  }
  .a-try-kind {
    display: inline-block;
    min-width: 5.5em;
    color: var(--ink-secondary);
  }
  .a-try a,
  .a-stories a,
  .a-note a {
    display: inline-block;
    min-height: 24px;
  }
  .a-static {
    margin: 0 0 12px;
  }
  .a-note {
    margin: 0;
    font-size: 15px;
    color: var(--ink-secondary);
  }

  .a-h2 {
    margin: 64px 0 16px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }

  /* The specimen: a miniature of the report page, on white like a sheet. */
  .a-specimen {
    margin: 0;
  }
  .a-page {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 520px;
    padding: 28px 32px 24px;
    background: var(--riprap-white);
    border: 1px solid var(--rule-soft);
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
    color: var(--ink);
    text-decoration: none;
  }
  .a-page-kind {
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .a-page-title {
    font-size: 22px;
    font-weight: 600;
    line-height: 1.15;
    text-wrap: balance;
  }
  .a-page-lead {
    margin-top: 8px;
    font-size: 34px;
    font-weight: 700;
    line-height: 1;
  }
  .a-page-text {
    font-size: 16px;
    line-height: 1.5;
  }
  .a-page-more {
    margin-top: 6px;
    font-size: 15px;
    color: var(--riprap-text-link);
    text-decoration: underline;
    text-underline-offset: 0.2em;
  }
  .a-page:hover .a-page-more {
    text-decoration-thickness: 2px;
  }
  .a-specimen figcaption {
    margin-top: 10px;
    max-width: 520px;
    font-size: 15px;
    color: var(--ink-secondary);
  }

  .a-stories {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .a-stories li {
    display: grid;
    grid-template-columns: 11em minmax(0, 1fr);
    column-gap: 20px;
    padding: 10px 0;
    border-bottom: 1px solid var(--riprap-rule-hairline);
    font-size: 16px;
    line-height: 1.45;
  }
  .a-stories span {
    color: var(--ink-secondary);
  }
  .a-specimen time {
    white-space: nowrap;
  }
  .a-prose {
    margin: 0 0 12px;
    max-width: 64ch;
    font-size: 17px;
    line-height: 1.55;
  }

  @media (max-width: 640px) {
    .a-cover {
      padding: 32px 16px 64px;
    }
    .a-h1 {
      font-size: 36px;
    }
    .a-deck {
      font-size: 18px;
    }
    .a-query-row {
      flex-direction: column;
    }
    .a-page {
      padding: 20px 18px;
    }
    .a-stories li {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
