<script lang="ts">
  import { resolve } from '$app/paths';
  import { modeLabel } from '$lib/client/gallery';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();

  let questions = $derived(data.entries.filter((e) => e.question));
  let addresses = $derived(data.entries.filter((e) => !e.question));

  // The note depends on how each answer was made, read from the entry's own
  // grounding. In extractive mode code sets the lead (and any refusal); the
  // model only picks the quoted sentences. A refusal ran no model and no
  // rule, and has no note.
  const NOTE_EXTRACTIVE =
    'The lead (Yes, No or a count) is set by rules in code, and so is a refusal or a note that the sources do not answer. The model chose which source sentences answer the question, and they are quoted word for word.';
  const NOTE_WRITTEN = 'Written by a language model, with each claim checked against its cited sources.';
  const NOTE_RULES = "Answered by rules in code over the question's words, with no language model.";
  const NOTE_RULES_PLANNED =
    "The answer was chosen by rules in code over the question's words; a language model was used only to read the place and choose the sources.";
  type Entry = (typeof data.entries)[number];
  const note = (e: Entry) =>
    e.refused ? null
      : e.modelName
      ? e.answerMode === 'extractive' ? NOTE_EXTRACTIVE : NOTE_WRITTEN
      : e.answerMode === 'rules' ? (e.planned ? NOTE_RULES_PLANNED : NOTE_RULES)
      : e.mode !== 'llm' ? `${modeLabel(e.mode)}.` : null;
  let notes = $derived([...new Set(questions.map(note).filter((n) => n !== null))]);
  let sharedNote = $derived(notes.length === 1 ? notes[0] : null);

  // The model is named once when every answered question used the same
  // one; otherwise each entry that used a model names its own.
  let models = $derived([...new Set(questions.filter(note).map((e) => e.modelName))]);
  let sharedModel = $derived(models.length === 1 ? models[0] : null);
  // One generation date for the whole gallery is said once, not per row.
  let dates = $derived([...new Set(data.entries.map((e) => e.generated_at.slice(0, 10)))]);
  let sharedDate = $derived(dates.length === 1 ? dates[0] : null);
</script>

<svelte:head>
  <title>Riprap gallery</title>
  <meta name="description" content="Precomputed Riprap flood-exposure briefings for New York City neighborhoods, served as static pages." />
</svelte:head>

{#snippet row(place: string, generatedAt: string, href: string, label: string, lead: string, reason?: string | null)}
  <span class="gallery-place">{place}</span>
  {#if !sharedDate}<time class="gallery-date" datetime={generatedAt.slice(0, 10)}>{generatedAt.slice(0, 10)}</time>{/if}
  <a class="gallery-link" {href}>{label}</a>
  {#if reason}<p class="gallery-reason">{reason}</p>{/if}
  {#if lead}<p class="gallery-lead">{lead}</p>{/if}
{/snippet}

<div class="gallery-page">
  <section aria-labelledby="gallery-h1">
    <p class="gallery-kind">Gallery</p>
    <h1 id="gallery-h1" class="gallery-title">Precomputed briefings</h1>
    <p class="gallery-note">
      Snapshots generated ahead of time and saved as static pages. Opening one does not contact the
      Riprap backend, so the data is as of the generation date{#if sharedDate}, <time class="data" datetime={sharedDate}>{sharedDate}</time>{:else} shown{/if}.
    </p>

    <h2 class="gallery-group">Questions</h2>
    {#if sharedNote}<p class="gallery-note">{sharedNote}</p>{/if}
    <ul class="gallery-list">
      {#each questions as e (e.slug)}
        <li class="gallery-item">
          {@render row(
            e.neighborhood,
            e.generated_at,
            `${resolve('/(app)/gallery/[slug]', { slug: e.slug })}/`,
            e.question ?? '',
            e.lead,
            e.reason
          )}
          {#if (!sharedModel && e.modelName) || (!sharedNote && note(e))}
            <p class="gallery-meta">
              {#if !sharedModel && e.modelName}Language model <span class="gallery-model">{e.modelName}</span>.{/if}
              {#if !sharedNote}{note(e)}{/if}
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
            e.generated_at,
            `${resolve('/(app)/gallery/[slug]', { slug: e.slug })}/`,
            e.address,
            e.lead,
            e.reason
          )}
        </li>
      {/each}
    </ul>

    {#if sharedModel}
      <p class="gallery-colophon">
        The question briefings were answered with the language model
        <span class="gallery-model">{sharedModel}</span>.
      </p>
    {/if}
  </section>
</div>

<style>
  /* The landing's frame: 1040px wide, centred, 32px sides (16px on phones). */
  .gallery-page {
    max-width: 1040px;
    margin: 0 auto;
    padding: 32px 32px 64px;
  }
  /* Kind line and Title, as on a briefing. */
  .gallery-kind {
    margin: 0 0 2px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .gallery-title {
    margin: 0 0 16px;
    font-size: 34px;
    font-weight: 600;
    line-height: 1.18;
    letter-spacing: -0.01em;
  }
  /* 54ch of Sofia Sans is about 75 characters of prose. */
  .gallery-note {
    margin: 0 0 12px;
    max-width: 54ch;
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
    margin: 48px 0 4px;
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
  .gallery-reason,
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
  .gallery-reason,
  .gallery-lead,
  .gallery-meta {
    margin: 2px 0 0;
    max-width: 54ch;
    font-size: 14px;
    line-height: 1.45;
  }
  .gallery-reason,
  .gallery-meta {
    color: var(--ink-secondary);
  }
  /* The link's 2px padding plus 2px sets the reason 4px under it; the
     lead keeps 4px from the reason, so the two do not read as one block. */
  .gallery-reason + .gallery-lead {
    margin-top: 4px;
  }
  .gallery-colophon {
    margin: 32px 0 0;
    max-width: 54ch;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  @media (max-width: 720px) {
    .gallery-title {
      font-size: 26px;
    }
  }
  @media (max-width: 640px) {
    .gallery-page {
      padding: 16px 16px 48px;
    }
    .gallery-item {
      grid-template-columns: minmax(0, 1fr);
    }
    .gallery-date {
      text-align: left;
    }
  }
</style>
