<script lang="ts">
  import { resolve } from '$app/paths';
  import { formatGeneratedAt, llmStamp, modeLabel } from '$lib/client/gallery';
  import type { PageProps } from './$types';

  let { data }: PageProps = $props();
</script>

<svelte:head>
  <title>Gallery · Riprap</title>
  <meta name="description" content="Precomputed Riprap flood-exposure briefings for New York City neighborhoods, served as static pages." />
</svelte:head>

<section class="hero-band">
  <div class="hero-band-inner">
    <div class="app-region app-region-brief" aria-labelledby="gallery-h1">
      <header class="region-head">
        <span class="section-label">Gallery</span>
      </header>
      <h1 id="gallery-h1" class="brief-h1">Precomputed briefings</h1>
      <p class="region-head-meta gallery-intro">
        Snapshots generated ahead of time and saved as static pages. Opening one does not
        contact the Riprap backend, so the data is as of the generation date shown.
      </p>
      <ol class="citation-list">
        {#each data.entries as e (e.slug)}
          <li class="citation-item">
            <span class="citation-num" aria-hidden="true">·</span>
            <div class="citation-body">
              <div class="citation-line-1">
                <span class="citation-source">{e.neighborhood}</span>
                <span class="citation-vintage">{formatGeneratedAt(e.generated_at)}</span>
              </div>
              <div class="citation-title">
                <a href="{resolve('/gallery/[slug]', { slug: e.slug })}/">{e.address}</a>
              </div>
              {#if e.question}
                <div class="citation-title">Question: {e.question}</div>
              {/if}
              <div class="citation-meta">
                <span>{llmStamp(e) ?? modeLabel(e.mode)}</span>
              </div>
            </div>
          </li>
        {/each}
      </ol>
    </div>
  </div>
</section>

<style>
  .gallery-intro {
    margin: 0 0 20px;
    max-width: 70ch;
  }
</style>
