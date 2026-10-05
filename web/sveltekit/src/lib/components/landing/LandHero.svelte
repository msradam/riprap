<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { STATIC_SITE, QUICKSTART_URL } from '$lib/staticSite';
  import LandSpecimen, { type Specimen } from './LandSpecimen.svelte';

  /** Landing top: kind line, h1, subhead, the query box (or, on the
   *  static site, the gallery and the quickstart), real questions as
   *  chips, and a real gallery briefing as the specimen. The specimen
   *  comes after the form in DOM order, so the input stays an early Tab
   *  stop; on a phone it is set between the actions and the chips. */
  interface Chip {
    label: string;
    slug: string;
    /** The entry's own question or address, which the live app answers. */
    query: string;
  }
  interface Props {
    chips: Chip[];
    specimen: Specimen;
    /** Saved briefings in the gallery. */
    count: number;
  }
  let { chips, specimen, count }: Props = $props();

  let q = $state('');
  let input: HTMLInputElement | undefined;
  // Set by an empty submit, cleared by the next keystroke. The button stays
  // enabled and the input has no `required`, so the browser shows no bubble.
  let empty = $state(false);

  // "Edit query" from a briefing arrives as /?q=<query>. Attachments run
  // on the client only, which matters because the landing is prerendered.
  // It also keeps the node for the empty-submit focus.
  function prefill(node: HTMLInputElement) {
    input = node;
    const v = new URLSearchParams(window.location.search).get('q');
    if (v) {
      q = v;
      node.focus();
    }
  }

  const briefHref = (v: string) => resolve('/(app)/q/[queryId]', { queryId: encodeURIComponent(v) });
  const galleryHref = (slug: string) => `${resolve('/(app)/gallery/[slug]', { slug })}/`;

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const v = q.trim();
    if (v) {
      goto(briefHref(v));
    } else {
      empty = true;
      input?.focus();
    }
  }
</script>

<section class="land-section land-hero" aria-labelledby="land-h1">
  <div class="land-frame hero-grid">
    <p class="hero-kind">Riprap, open-source flood and heat evidence for New York City</p>
    <div class="hero-main">
      <h1 id="land-h1">The flood and heat record for any New York City block, cited line by line.</h1>
      <p class="hero-sub">
        Riprap joins street sensors, 311 complaints, flood maps and storm records for an address or
        community district into one page. For heat it reads satellite surface temperature, tree
        canopy, the Health Department's Heat Vulnerability Index and the Weather Service forecast.
        Rules or an open Granite model read your question and choose the evidence. Every sentence of evidence is written by code from a public record and cites its source and date.
      </p>

      {#if STATIC_SITE}
        <ul class="land-actions hero-actions">
          <li><a class="land-button" href="{resolve('/(app)/gallery')}/">Browse {count} briefings</a></li>
          <li><a class="land-button is-secondary" href={QUICKSTART_URL}>Run it yourself</a></li>
        </ul>
      {:else}
        <form class="hero-query" role="search" onsubmit={submit}>
          <label for="land-query-input">Address, community district, or a flood or heat question</label>
          <div class="hero-query-row">
            <input
              id="land-query-input"
              type="text"
              {@attach prefill}
              bind:value={q}
              oninput={() => (empty = false)}
              aria-describedby={empty ? 'land-query-hint' : undefined}
              aria-invalid={empty || undefined}
              placeholder="90-01 183rd Street, Queens or QN12"
              autocomplete="off"
              enterkeyhint="search"
            />
            <button type="submit" class="land-button">Get the briefing</button>
          </div>
          <!-- Always in the DOM so screen readers announce the message when it appears. -->
          <p id="land-query-hint" class="hero-hint" role="status">{#if empty}Type an address, a community district such as QN12, or a question.{/if}</p>
        </form>
      {/if}
      <p class="land-small hero-note">
        {#if STATIC_SITE}This site has saved briefings. Run it yourself to ask your own question.{/if}
        Runs in seconds on a laptop: no GPU, no API keys.
      </p>

      <p class="hero-chips-head" id="land-try">Try a real question or place</p>
      <ul class="hero-chips" aria-labelledby="land-try">
        {#each chips as c (c.slug)}
          <li><a class="hero-chip" href={STATIC_SITE ? galleryHref(c.slug) : briefHref(c.query)}>{c.label}</a></li>
        {/each}
      </ul>
    </div>
    <div class="hero-specimen">
      <LandSpecimen {specimen} />
    </div>
  </div>
</section>

<style>
  .land-hero {
    padding-top: 48px;
  }
  .hero-grid {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    column-gap: 32px;
  }
  .hero-kind {
    grid-column: 1 / -1;
    margin: 0 0 16px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .hero-main {
    grid-column: 1 / span 7;
  }
  .hero-specimen {
    grid-column: 8 / span 5;
    align-self: start;
  }
  h1 {
    margin: 0;
    font-size: 52px;
    font-weight: 700;
    line-height: 1.05;
    letter-spacing: -0.02em;
    text-wrap: balance;
  }
  .hero-sub {
    margin: 24px 0 0;
    max-width: 56ch;
    font-size: 20px;
    line-height: 1.5;
    color: var(--ink-secondary);
    text-wrap: pretty;
  }

  .hero-query {
    margin-top: 32px;
  }
  label {
    display: block;
    margin-bottom: 8px;
    font-size: 17px;
    font-weight: 600;
  }
  .hero-query-row {
    display: flex;
    gap: 8px;
  }
  input {
    flex: 1;
    min-width: 0;
    height: 56px;
    padding: 0 16px;
    border: 1px solid var(--ink-secondary);
    border-radius: 0;
    background: var(--riprap-white);
    font: inherit;
    font-size: 19px;
    color: var(--ink);
  }
  input::placeholder {
    color: var(--ink-tertiary);
  }
  input:focus-visible {
    outline-offset: 0;
  }
  .hero-query .land-button {
    white-space: nowrap;
  }
  /* Small in ink: a prompt, not an error, so no red. */
  .hero-hint {
    margin: 0;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink);
  }
  .hero-hint:not(:empty) {
    margin-top: 8px;
  }
  .hero-note {
    margin: 12px 0 0;
    max-width: 56ch;
  }

  .hero-chips-head {
    margin: 32px 0 8px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .hero-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .hero-chip {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    padding: 8px 16px;
    border-radius: 3px;
    background: var(--sky);
    color: var(--ink);
    font-size: 17px;
    line-height: 1.3;
    text-decoration: none;
  }
  .hero-chip:hover,
  .hero-chip:focus-visible {
    text-decoration: underline;
  }

  @media (max-width: 1099px) {
    .hero-main,
    .hero-specimen {
      grid-column: 1 / -1;
    }
    .hero-specimen {
      margin-top: 48px;
    }
  }
  @media (max-width: 640px) {
    .land-hero {
      padding-top: 24px;
    }
    h1 {
      font-size: 34px;
      line-height: 1.1;
    }
    .hero-sub {
      font-size: 18px;
    }
    .hero-query-row {
      flex-direction: column;
    }
    input {
      flex: none;
    }
    .hero-specimen {
      margin-top: 32px;
    }
  }
  /* Phone: the briefing window after the actions, so they stay near the
     fold, and before the chips. Only the visual order changes. */
  @media (max-width: 480px) {
    .hero-grid {
      display: flex;
      flex-direction: column;
    }
    .hero-main {
      display: contents;
    }
    .hero-chips-head,
    .hero-chips {
      order: 2;
    }
    /* Stretch, or the window would be only as wide as its content. */
    .hero-specimen {
      order: 1;
      align-self: stretch;
      margin-top: 32px;
    }
  }
</style>
