<script lang="ts">
  import { resolve } from '$app/paths';

  /** The gallery as stories: the question (or the place) as the headline,
   *  the answer's first sentence as the standfirst, place and snapshot date
   *  as the byline. The two question briefings named in TOP lead. */
  export interface LandStory {
    slug: string;
    neighborhood: string;
    address: string;
    question: string | null;
    generated_at: string;
    lead: string;
  }
  interface Props { stories: LandStory[] }
  let { stories }: Props = $props();

  // Keep house numbers such as "90-01" on one line in a headline.
  const parts = (t: string) => t.split(/(\d+-\d+)/);

  const TOP = ['hollis-since-ida', 'qn12-complaints'];
  let top = $derived(TOP.map((slug) => stories.find((s) => s.slug === slug)).filter((s) => !!s));
  let rest = $derived(
    stories.filter((s) => !TOP.includes(s.slug)).sort((a, b) => Number(!a.question) - Number(!b.question))
  );
</script>

{#snippet story(s: LandStory, big: boolean)}
  <li class={['story', big && 'is-top']}>
    <h3>
      <a href="{resolve('/(app)/gallery/[slug]', { slug: s.slug })}/"
        >{#each parts(s.question ?? s.neighborhood) as p, i (i)}{#if i % 2}<span class="nowrap">{p}</span
            >{:else}{p}{/if}{/each}</a
      >
    </h3>
    {#if s.lead}<p class="story-lead">{s.lead}</p>{/if}
    <p class="story-byline">
      <span>{s.question ? s.neighborhood : s.address}</span>
      <time datetime={s.generated_at.slice(0, 10)}>{s.generated_at.slice(0, 10)}</time>
    </p>
  </li>
{/snippet}

<section class="stories" aria-labelledby="stories-h">
  <h2 id="stories-h">Briefings from the gallery</h2>
  <p class="stories-note">
    Precomputed snapshots, saved as static pages. <a href="{resolve('/(app)/gallery')}/">See them as a list</a>
    in the gallery.
  </p>
  <ul class="stories-top">
    {#each top as s (s.slug)}{@render story(s, true)}{/each}
  </ul>
  <ul class="stories-rest">
    {#each rest as s (s.slug)}{@render story(s, false)}{/each}
  </ul>
</section>

<style>
  .stories {
    margin-top: 80px;
  }
  h2 {
    margin: 0;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }
  .stories-note {
    margin: 6px 0 32px;
    font-size: 15px;
    color: var(--ink-secondary);
  }
  a {
    color: var(--riprap-text-link);
    text-underline-offset: 0.2em;
  }
  a:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .stories-top {
    gap: 40px 56px;
    margin-bottom: 56px;
  }
  .stories-rest {
    gap: 36px 56px;
  }
  h3 {
    margin: 0;
    font-size: 23px;
    font-weight: 600;
    line-height: 1.25;
    text-wrap: balance;
  }
  .is-top h3 {
    font-size: 28px;
    font-weight: 700;
    line-height: 1.18;
  }
  h3 a {
    color: var(--ink);
    text-decoration: none;
  }
  .nowrap {
    white-space: nowrap;
  }
  h3 a:hover {
    text-decoration: underline;
  }
  .story-lead {
    margin: 8px 0 0;
    max-width: 60ch;
    font-size: 17px;
    line-height: 1.5;
    text-wrap: pretty;
  }
  .is-top .story-lead {
    font-size: 19px;
  }
  .story-byline {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 16px;
    margin: 8px 0 0;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  time {
    font-family: var(--font-mono);
    font-size: 13px;
  }
  @media (max-width: 720px) {
    .stories {
      margin-top: 56px;
    }
    ul {
      grid-template-columns: minmax(0, 1fr);
    }
    .is-top h3 {
      font-size: 25px;
    }
    h3 {
      font-size: 22px;
    }
  }
</style>
