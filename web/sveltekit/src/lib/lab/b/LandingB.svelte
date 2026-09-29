<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { formatGeneratedAt } from '$lib/client/gallery';
  import type { Story } from '$lib/lab/labModel';
  import { STATIC_SITE, QUICKSTART_URL } from '$lib/staticSite';

  interface Props { stories: Story[] }
  let { stories }: Props = $props();

  const TOP = ['hollis-since-ida', 'qn12-complaints'];
  let top = $derived(TOP.map((slug) => stories.find((s) => s.slug === slug)).filter((s) => !!s));
  let rest = $derived(stories.filter((s) => !TOP.includes(s.slug)));

  let q = $state('');

  // Same as LandHero: "Edit query" arrives as ?q=<query>, client only.
  function prefill(node: HTMLInputElement) {
    const v = new URLSearchParams(window.location.search).get('q');
    if (v) {
      q = v;
      node.focus();
    }
  }

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const v = q.trim();
    if (v) goto(resolve('/(app)/q/[queryId]', { queryId: encodeURIComponent(v) }));
  }

  const href = (s: Story) => resolve('/(app)/lab/[dir]/gallery/[slug]', { dir: 'b', slug: s.slug });
</script>

{#snippet story(s: Story, big: boolean)}
  <li class={['story', big && 'is-top']}>
    <h3><a href={href(s)}>{s.question ?? s.neighborhood}</a></h3>
    {#if s.lead}<p class="story-dek">{s.lead}</p>{/if}
    <p class="story-byline">
      <span>{s.question ? s.neighborhood : s.address}</span>
      <span class="story-date">{formatGeneratedAt(s.generated_at)}</span>
    </p>
  </li>
{/snippet}

<div class="lb">
  <header class="lb-head">
    <h1>Flood-exposure briefings for New York City</h1>
    <p class="lb-dek">
      {#if STATIC_SITE}
        Riprap turns an address, a community district, or a flood question into a written briefing
        on flood exposure.
      {:else}
        Type an address, a community district, or a flood question. Get a written briefing on flood
        exposure.
      {/if}
      Every claim cites a public record from FEMA, NOAA, USGS, or city open data.
    </p>

    {#if STATIC_SITE}
      <p class="lb-static">
        This public copy has no backend. Read the briefings below, or
        <a href={QUICKSTART_URL}>run Riprap locally to ask your own question</a>.
      </p>
    {:else}
      <form class="lb-query" role="search" onsubmit={submit}>
        <label for="lb-q" class="lb-q-label">Ask about a place</label>
        <div class="lb-q-row">
          <input
            id="lb-q"
            type="text"
            {@attach prefill}
            bind:value={q}
            placeholder="Address, district such as QN 12, or a question"
            autocomplete="off"
            enterkeyhint="search"
          />
          <button type="submit">Get the briefing</button>
        </div>
      </form>
    {/if}
  </header>

  <section class="lb-stories" aria-labelledby="lb-stories-h">
    <h2 id="lb-stories-h">Briefings from the gallery</h2>
    <ul class="lb-top">
      {#each top as s (s.slug)}{@render story(s, true)}{/each}
    </ul>
    <ul class="lb-rest">
      {#each rest as s (s.slug)}{@render story(s, false)}{/each}
    </ul>
  </section>
</div>

<style>
  .lb {
    max-width: 1040px;
    margin: 0 auto;
    padding: 72px 16px 96px;
    font-family: var(--font-sans);
    color: var(--ink);
  }
  .lb-head {
    max-width: 800px;
  }
  h1 {
    margin: 0;
    font-size: 68px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.03em;
    text-wrap: balance;
  }
  .lb-dek {
    max-width: 640px;
    margin: 24px 0 0;
    font-size: 22px;
    line-height: 1.4;
    color: var(--ink-secondary);
    text-wrap: pretty;
  }
  .lb-static {
    margin: 24px 0 0;
    font-size: 18px;
  }
  .lb-static a {
    color: var(--riprap-blue-60v);
  }

  .lb-query {
    margin-top: 36px;
    max-width: 720px;
  }
  .lb-q-label {
    display: block;
    margin-bottom: 8px;
    font-size: 16px;
    font-weight: 600;
  }
  .lb-q-row {
    display: flex;
    gap: 8px;
  }
  input {
    flex: 1;
    min-width: 0;
    min-height: 56px;
    padding: 0 16px;
    border: 2px solid var(--ink);
    border-radius: 0;
    background: var(--riprap-white);
    font: inherit;
    font-size: 20px;
    color: var(--ink);
  }
  input::placeholder {
    color: var(--ink-tertiary);
  }
  button {
    min-height: 56px;
    padding: 0 24px;
    border: 0;
    background: var(--ink);
    color: var(--paper);
    font: inherit;
    font-size: 18px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }
  button:hover {
    background: #000;
  }
  input:focus-visible,
  button:focus-visible,
  a:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }

  .lb-stories {
    margin-top: 88px;
  }
  h2 {
    margin: 0 0 24px;
    font-size: 20px;
    font-weight: 700;
    color: var(--ink-secondary);
  }
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .lb-top {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 40px 56px;
    margin-bottom: 64px;
  }
  .lb-rest {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 36px 56px;
  }
  h3 {
    margin: 0;
    font-size: 25px;
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: -0.01em;
    text-wrap: balance;
  }
  .is-top h3 {
    font-size: 36px;
    line-height: 1.1;
    letter-spacing: -0.02em;
  }
  h3 a {
    color: var(--ink);
    text-decoration: none;
  }
  h3 a:hover {
    text-decoration: underline;
  }
  .story-dek {
    margin: 10px 0 0;
    font-size: 18px;
    line-height: 1.45;
    color: var(--ink);
    text-wrap: pretty;
  }
  .is-top .story-dek {
    font-size: 20px;
  }
  .story-byline {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 16px;
    margin: 10px 0 0;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .story-date {
    font-family: var(--font-mono);
    font-size: 13px;
  }

  @media (max-width: 720px) {
    .lb {
      padding-top: 40px;
    }
    h1 {
      font-size: 44px;
    }
    .lb-dek {
      font-size: 19px;
    }
    .lb-q-row {
      flex-direction: column;
    }
    .lb-top,
    .lb-rest {
      grid-template-columns: 1fr;
    }
    .is-top h3 {
      font-size: 30px;
    }
  }
</style>
