<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { EXAMPLES } from '$lib/samples';

  /** Landing hero. A static headline (New York City is the production
   *  deployment; the other cities are experimental and listed below in
   *  CityPicker), the query box, and one runnable example per kind of
   *  input the backend accepts. Nothing rotates: WCAG 2.2.2. */

  let q = $state('');

  // "Edit query" from a briefing arrives as /?q=<query>. Attachments run
  // on the client only, which matters because the landing is prerendered.
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

  function submit() {
    const v = q.trim();
    if (!v) return;
    goto(briefHref(v));
  }
</script>

<!-- +layout.svelte already wraps every page in <main>. -->
<section class="land-hero">
  <h1 class="land-hero-h1">
    <span class="land-hero-headline">
      <span class="land-hero-headline-intro">A flood-exposure briefing for</span>
      <span class="land-hero-headline-city"><span class="city">New York City</span>.</span>
    </span>
    <span class="land-hero-deck">
      Type an address, a community district, or a flood question. Get a written
      briefing on flood exposure. Every claim cites a public record from FEMA,
      NOAA, USGS, or city open data.
    </span>
  </h1>

  <form class="land-query" onsubmit={(e) => { e.preventDefault(); submit(); }} role="search">
    <span class="land-query-prompt" aria-hidden="true">›</span>
    <input
      id="land-query-input"
      type="text"
      {@attach prefill}
      bind:value={q}
      placeholder="Address, district such as QN 12, or a question"
      class="land-query-input"
      autocomplete="off"
      enterkeyhint="search"
      aria-label="Address, community district, or flood question"
    />
    <button type="submit" class="land-query-submit">Brief this place →</button>
  </form>

  <div class="land-try">
    <span class="land-try-label" id="land-try-label">Try:</span>
    <ul class="land-try-list" aria-labelledby="land-try-label">
      {#each EXAMPLES as ex (ex.kind)}
        <li>
          <span class="land-try-kind">{ex.kind}</span>
          <a class="land-try-link" href={briefHref(ex.q)}>{ex.q}</a>
        </li>
      {/each}
    </ul>
  </div>
  <p class="land-gallery">
    <a href="{resolve('/(app)/gallery')}/">See precomputed briefings</a> in the gallery.
  </p>
</section>

<style>
  .land-hero { padding: 64px 32px 48px; }
  .land-hero-h1 {
    display: flex;
    flex-direction: column;
    gap: 18px;
    margin: 0 0 30px;
    max-width: 880px;
  }
  .land-hero-headline {
    font-family: var(--font-serif);
    font-weight: 500;
    font-size: 52px;
    line-height: 1.08;
    color: var(--ink);
    letter-spacing: -0.015em;
  }
  .land-hero-headline-intro,
  .land-hero-headline-city {
    display: block;
  }
  /* Ink, not federal blue: blue is reserved for things a reader can
     act on (DESIGN.md, the Checkable Blue Rule). */
  .city {
    font-style: italic;
    white-space: nowrap;
  }
  .land-hero-deck {
    font-family: var(--font-serif);
    font-size: 18px;
    line-height: 1.55;
    color: var(--ink-secondary);
    max-width: 64ch;
  }

  .land-query {
    display: flex;
    align-items: stretch;
    gap: 0;
    max-width: 760px;
    border: 1px solid var(--ink);
    background: white;
    font-size: 18px;
  }
  .land-query-prompt {
    display: flex;
    align-items: center;
    padding: 0 14px;
    font-family: var(--font-mono);
    font-size: 22px;
    color: var(--ink-tertiary);
    background: var(--paper-deep);
    border-right: 1px solid var(--rule-soft);
  }
  .land-query-input {
    flex: 1;
    min-width: 0;
    padding: 18px 16px;
    font: inherit;
    font-family: var(--font-sans);
    border: none;
    outline: none;
    background: white;
    color: var(--ink);
  }
  /* Inset ring so it sits inside the ink border: 3px federal blue on
     white is 7:1. */
  .land-query-input:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: -3px;
  }
  .land-query-input::placeholder { color: var(--ink-tertiary); }
  .land-query-submit {
    padding: 0 22px;
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: 14px;
    background: var(--ink);
    color: var(--paper);
    border: none;
    cursor: pointer;
    white-space: nowrap;
    letter-spacing: 0.02em;
  }
  .land-query-submit:hover { background: #000; }

  .land-try {
    margin-top: 18px;
    display: flex;
    align-items: baseline;
    gap: 10px;
    max-width: 760px;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink-tertiary);
  }
  .land-try-label {
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-size: 12px;
    flex: 0 0 auto;
  }
  .land-try-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 2px;
    min-width: 0;
  }
  .land-try-list li {
    display: flex;
    align-items: baseline;
    gap: 10px;
  }
  .land-try-kind {
    flex: 0 0 9ch;
    font-size: 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .land-try-link {
    display: inline-block;
    padding: 3px 0;
    min-height: 24px;
    color: var(--ink);
    text-decoration: underline dotted var(--ink-tertiary);
    text-underline-offset: 3px;
  }
  .land-try-link:hover { text-decoration-style: solid; }

  .land-gallery {
    margin: 14px 0 0;
    font-family: var(--font-sans);
    font-size: 15px;
    color: var(--ink-secondary);
  }
  .land-gallery a {
    display: inline-block;
    min-height: 24px;
    color: var(--accent);
    text-underline-offset: 2px;
  }

  @media (max-width: 640px) {
    .land-hero-headline { font-size: 38px; }
    .land-hero { padding: 40px 16px 32px; }
    .land-try { flex-direction: column; gap: 6px; }
    .land-try-list li { flex-direction: column; gap: 0; }
    .land-try-kind { flex-basis: auto; }
  }
</style>
