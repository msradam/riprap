<script lang="ts">
  import { asset, resolve } from '$app/paths';

  /** A real gallery briefing beside the headline: a window onto its
   *  screenshot, which scrolls slowly, and the question with its lead
   *  word as text. The image comes from scripts/capture-hero-preview.mjs;
   *  the question and the lead come from the snapshot at build time. */
  export interface Specimen {
    slug: string;
    question: string;
    lead: string | null;
  }
  let { specimen }: { specimen: Specimen } = $props();

  // Keep house numbers such as "90-01" on one line.
  let qParts = $derived(specimen.question.split(/(\d+-\d+)/));
  let href = $derived(`${resolve('/(app)/gallery/[slug]', { slug: specimen.slug })}/`);
</script>

<figure class="specimen">
  <a class="window" {href}>
    <span class="window-bar" aria-hidden="true">riprap / gallery / {specimen.slug}</span>
    <span class="window-view">
      <!-- The size matches CLIP in scripts/capture-hero-preview.mjs (the 1x file). The window spans the frame below 1100px and is about 455px wide above. -->
      <img
        src={asset('/landing/hero-briefing.webp')}
        srcset="{asset('/landing/hero-briefing-712.webp')} 712w, {asset('/landing/hero-briefing.webp')} 1424w"
        sizes="(max-width: 640px) calc(100vw - 32px), (max-width: 1099px) calc(100vw - 64px), 455px"
        width="712"
        height="1400"
        decoding="async"
        alt="The Riprap briefing for this question: the answer Yes. over its cited sentences on FloodNet sensor events, Hurricane Ida high-water marks and 311 flood complaints, then a map of those points around the address."
      />
    </span>
  </a>
  <figcaption class="specimen-caption">
    <p class="specimen-q">
      {#each qParts as p, i (i)}{#if i % 2}<span class="nowrap">{p}</span>{:else}{p}{/if}{/each}
    </p>
    {#if specimen.lead}<p class="specimen-lead">{specimen.lead}</p>{/if}
    <a class="land-link" {href}>Read the full briefing</a>
  </figcaption>
</figure>

<style>
  .specimen {
    margin: 0;
  }
  .window {
    display: block;
    border: 1px solid var(--rule-soft);
    background: var(--riprap-white);
    color: var(--ink-secondary);
    text-decoration: none;
  }
  .window:focus-visible {
    outline-offset: 3px;
  }
  .window-bar {
    display: block;
    padding: 6px 12px;
    border-bottom: 1px solid var(--rule-soft);
    background: var(--paper-deep);
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* A fixed shape, so the image cannot shift the layout as it loads.
     Size containment lets the scroll end be written as 100cqh. */
  .window-view {
    display: block;
    aspect-ratio: 4 / 5;
    /* Full width on a tablet: no taller than the desktop window. */
    max-height: 600px;
    overflow: hidden;
    container-type: size;
  }
  img {
    display: block;
    width: 100%;
    height: auto;
  }
  /* Down and back up over 28s, holding briefly at the top and the foot. */
  @media (prefers-reduced-motion: no-preference) {
    img {
      animation: specimen-scroll 28s ease-in-out infinite;
    }
    .window:hover img,
    .window:focus-within img {
      animation-play-state: paused;
    }
  }
  @keyframes specimen-scroll {
    0%,
    6% {
      transform: translateY(0);
    }
    47%,
    53% {
      transform: translateY(calc(100cqh - 100%));
    }
    94%,
    100% {
      transform: translateY(0);
    }
  }

  .specimen-caption {
    margin-top: 16px;
  }
  .specimen-q {
    margin: 0;
    font-size: 17px;
    font-weight: 600;
    line-height: 1.4;
    text-wrap: balance;
  }
  .nowrap {
    white-space: nowrap;
  }
  .specimen-lead {
    margin: 4px 0 0;
    font-size: 22px;
    font-weight: 700;
    line-height: 1.2;
  }
  .specimen-caption .land-link {
    margin-top: 4px;
  }

  /* Phone: a shorter window, so the actions stay near the fold. */
  @media (max-width: 480px) {
    .window-view {
      aspect-ratio: auto;
      height: 380px;
    }
  }
</style>
