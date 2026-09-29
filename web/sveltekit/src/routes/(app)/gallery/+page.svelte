<script lang="ts">
  import { resolve } from '$app/paths';
  import { formatGeneratedAt, modeLabel } from '$lib/client/gallery';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let questions = $derived(data.entries.filter((e) => e.question));
  let addresses = $derived(data.entries.filter((e) => !e.question));

  // The model is named once when every question briefing used the same one;
  // otherwise each entry says how it was made.
  let models = $derived([...new Set(questions.map((e) => e.modelName))]);
  let sharedModel = $derived(models.length === 1 ? models[0] : null);

  // The note depends on how each answer was made. In extractive mode the
  // answer is source sentences quoted under a lead the model chose.
  const NOTE_EXTRACTIVE =
    'The model chose the lead and which source sentences answer the question; the sentences are quoted from the sources.';
  const NOTE_WRITTEN = 'Written by a language model, with each claim checked against its cited sources.';
  const note = (mode: string | null) => (mode === 'extractive' ? NOTE_EXTRACTIVE : NOTE_WRITTEN);
  let modes = $derived([...new Set(questions.filter((e) => e.modelName).map((e) => e.answerMode === 'extractive'))]);
  let sharedNote = $derived(modes.length === 1 ? (modes[0] ? NOTE_EXTRACTIVE : NOTE_WRITTEN) : null);
</script>

<svelte:head>
  <title>Riprap gallery</title>
  <meta name="description" content="Precomputed Riprap flood-exposure briefings for New York City neighborhoods, served as static pages." />
</svelte:head>

{#snippet row(place: string, date: string, href: string, label: string, lead: string)}
  <span class="gallery-place">{place}</span>
  <span class="gallery-date">{date}</span>
  <a class="gallery-link" {href}>{label}</a>
  {#if lead}<p class="gallery-lead">{lead}</p>{/if}
{/snippet}

<section class="hero-band">
  <div class="hero-band-inner">
    <section class="app-region app-region-brief" aria-labelledby="gallery-h1">
      <p class="gallery-kind">Gallery</p>
      <h1 id="gallery-h1" class="brief-h1">Precomputed briefings</h1>
      <p class="gallery-note">
        Snapshots generated ahead of time and saved as static pages. Opening one does not contact the
        Riprap backend, so the data is as of the generation date shown.
      </p>

      <h2 class="gallery-group">Questions</h2>
      <p class="gallery-note">
        {#if sharedModel}
          Each question briefing was made with the language model
          <span class="gallery-model">{sharedModel}</span>.
        {/if}
        {#if sharedNote}{sharedNote}{/if}
      </p>
      <ul class="gallery-list">
        {#each questions as e (e.slug)}
          <li class="gallery-item">
            {@render row(
              e.neighborhood,
              formatGeneratedAt(e.generated_at),
              `${resolve('/(app)/gallery/[slug]', { slug: e.slug })}/`,
              e.question ?? '',
              e.lead
            )}
            {#if !sharedModel || !sharedNote}
              <p class="gallery-meta">
                {#if !sharedModel}
                  {#if e.modelName}Language model <span class="gallery-model">{e.modelName}</span>.{:else}{modeLabel(e.mode)}.{/if}
                {/if}
                {#if !sharedNote && e.modelName}{note(e.answerMode)}{/if}
              </p>
            {/if}
          </li>
        {/each}
      </ul>

      <h2 class="gallery-group">Addresses</h2>
      <p class="gallery-note">Evidence briefings built from cited source values, with no language model.</p>
      <ul class="gallery-list">
        {#each addresses as e (e.slug)}
          <li class="gallery-item">
            {@render row(
              e.neighborhood,
              formatGeneratedAt(e.generated_at),
              `${resolve('/(app)/gallery/[slug]', { slug: e.slug })}/`,
              e.address,
              e.lead
            )}
          </li>
        {/each}
      </ul>
    </section>
  </div>
</section>

<style>
  .gallery-kind {
    margin: 0 0 8px;
    font-size: 15px;
    color: var(--ink-secondary);
  }
  .gallery-note {
    margin: 0 0 12px;
    max-width: 68ch;
    font-size: 15px;
    line-height: 1.5;
    color: var(--ink-secondary);
  }
  .gallery-model {
    font-family: var(--font-mono);
    font-size: 13px;
    overflow-wrap: anywhere;
  }
  @media (min-width: 640px) {
    .gallery-model {
      white-space: nowrap;
    }
  }
  .gallery-group {
    margin: 40px 0 4px;
    font-size: 22px;
    line-height: 1.25;
    font-weight: 600;
  }
  .gallery-list {
    list-style: none;
    margin: 0;
    padding: 0;
    max-width: 760px;
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  /* Place and date share the first line; the date column is right-aligned
     to the list edge, which the row hairlines make visible. */
  .gallery-item {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    column-gap: 24px;
    align-items: baseline;
    padding: 12px 0;
    border-top: 1px solid var(--riprap-rule-hairline);
  }
  .gallery-place {
    font-size: 16px;
    font-weight: 600;
  }
  .gallery-date {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink-secondary);
    text-align: right;
    white-space: nowrap;
  }
  .gallery-link,
  .gallery-lead,
  .gallery-meta {
    grid-column: 1 / -1;
    justify-self: start;
  }
  /* WCAG 2.5.8: at least 24px tall, even for a one-line address. */
  .gallery-link {
    min-height: 24px;
    padding: 2px 0;
    font-size: 16px;
    line-height: 1.4;
    color: var(--riprap-text-link);
    text-underline-offset: 2px;
  }
  .gallery-link:hover {
    text-decoration-thickness: 2px;
  }
  .gallery-lead,
  .gallery-meta {
    margin: 2px 0 0;
    max-width: 68ch;
    font-size: 14px;
    line-height: 1.45;
  }
  .gallery-meta {
    color: var(--ink-secondary);
  }
  @media (max-width: 640px) {
    .gallery-item {
      grid-template-columns: minmax(0, 1fr);
    }
    .gallery-date {
      text-align: left;
    }
  }
</style>
