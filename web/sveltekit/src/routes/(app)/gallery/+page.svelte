<script lang="ts">
  import { resolve } from '$app/paths';
  import { formatGeneratedAt, llmStamp, modeLabel } from '$lib/client/gallery';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let questions = $derived(data.entries.filter((e) => e.question));
  let addresses = $derived(data.entries.filter((e) => !e.question));

  // The note depends on how each answer was made. In extractive mode the
  // answer is source sentences quoted under a lead the model chose.
  const NOTE_EXTRACTIVE =
    'The model chose the lead and which source sentences answer the question; the sentences are quoted from the sources.';
  const NOTE_WRITTEN = 'Written by a language model, with each claim checked against its cited sources.';
  const isExtractive = (slug: string) => data.answerModes[slug] === 'extractive';
  let allExtractive = $derived(questions.every((e) => isExtractive(e.slug)));
  let noneExtractive = $derived(questions.every((e) => !isExtractive(e.slug)));
  let mixed = $derived(!allExtractive && !noneExtractive);
</script>

<svelte:head>
  <title>Gallery · Riprap</title>
  <meta name="description" content="Precomputed Riprap flood-exposure briefings for New York City neighborhoods, served as static pages." />
</svelte:head>

<section class="hero-band">
  <div class="hero-band-inner">
    <section class="app-region app-region-brief" aria-labelledby="gallery-h1">
      <header class="region-head">
        <span class="section-label">Gallery</span>
      </header>
      <h1 id="gallery-h1" class="brief-h1">Precomputed briefings</h1>
      <p class="gallery-intro">
        Snapshots generated ahead of time and saved as static pages. Opening one does not
        contact the Riprap backend, so the data is as of the generation date shown.
      </p>

      <h2 class="gallery-group">Questions</h2>
      {#if !mixed}
        <p class="gallery-group-note">{allExtractive ? NOTE_EXTRACTIVE : NOTE_WRITTEN}</p>
      {/if}
      <ul class="gallery-list">
        {#each questions as e (e.slug)}
          <li class="gallery-item">
            <div class="gallery-line-1">
              <span class="gallery-place">{e.neighborhood}</span>
              <span class="gallery-date">{formatGeneratedAt(e.generated_at)}</span>
            </div>
            <a class="gallery-link" href="{resolve('/(app)/gallery/[slug]', { slug: e.slug })}/">{e.question}</a>
            <div class="gallery-meta">{llmStamp(e) ?? modeLabel(e.mode)}</div>
            {#if mixed}
              <p class="gallery-group-note">{isExtractive(e.slug) ? NOTE_EXTRACTIVE : NOTE_WRITTEN}</p>
            {/if}
          </li>
        {/each}
      </ul>

      <h2 class="gallery-group">Addresses</h2>
      <p class="gallery-group-note">
        Evidence briefings built from cited source values, with no language model.
      </p>
      <ul class="gallery-list">
        {#each addresses as e (e.slug)}
          <li class="gallery-item">
            <div class="gallery-line-1">
              <span class="gallery-place">{e.neighborhood}</span>
              <span class="gallery-date">{formatGeneratedAt(e.generated_at)}</span>
            </div>
            <a class="gallery-link" href="{resolve('/(app)/gallery/[slug]', { slug: e.slug })}/">{e.address}</a>
          </li>
        {/each}
      </ul>
    </section>
  </div>
</section>

<style>
  .region-head .section-label { font-size: 12px; }
  .gallery-intro {
    margin: 0 0 8px;
    max-width: 70ch;
    font-size: 15px;
    color: var(--ink-secondary);
  }
  .gallery-group {
    margin: 32px 0 4px;
    font-size: 22px;
    line-height: 1.25;
    font-weight: 600;
  }
  .gallery-group-note {
    margin: 0 0 12px;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .gallery-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 8px;
    max-width: 80ch;
  }
  .gallery-item {
    padding: 8px 12px;
    border-left: 2px solid var(--rule-soft);
  }
  .gallery-line-1 {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 4px 12px;
  }
  .gallery-place { font-weight: 600; }
  .gallery-date {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-tertiary);
  }
  /* WCAG 2.5.8: at least 24px tall, even for a one-line address. */
  .gallery-link {
    display: inline-block;
    min-height: 24px;
    padding: 2px 0;
    font-size: 15px;
    line-height: 1.4;
    color: var(--accent);
    text-underline-offset: 2px;
  }
  .gallery-link:hover { text-decoration-thickness: 2px; }
  .gallery-meta {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-tertiary);
  }
</style>
