<script lang="ts">
  import { resolve } from '$app/paths';

  /** The gallery's question briefings as stories: the question as the
   *  headline, the answer's first sentence as the standfirst, place and
   *  snapshot date as the byline; the two named in TOP lead. The address
   *  briefings, whose standfirsts read alike, follow as a compact list. */
  export interface LandStory {
    slug: string;
    neighborhood: string;
    address: string;
    question: string | null;
    generated_at: string;
    lead: string;
    /** One editorial line on why the entry is in the gallery. */
    reason?: string | null;
  }
  interface Props { stories: LandStory[] }
  let { stories }: Props = $props();

  // Keep house numbers such as "90-01" on one line in a headline.
  const parts = (t: string) => t.split(/(\d+-\d+)/);

  const TOP = ['hollis-since-ida', 'qn12-complaints'];
  let top = $derived(TOP.map((slug) => stories.find((s) => s.slug === slug)).filter((s) => !!s));
  let rest = $derived(stories.filter((s) => s.question && !TOP.includes(s.slug)));
  let places = $derived(stories.filter((s) => !s.question && !TOP.includes(s.slug)));
</script>

{#snippet story(s: LandStory, big: boolean)}
  <li class={['story', big && 'is-top']}>
    <h3>
      <a href="{resolve('/(app)/gallery/[slug]', { slug: s.slug })}/"
        >{#each parts(s.question ?? s.neighborhood) as p, i (i)}{#if i % 2}<span class="nowrap">{p}</span
            >{:else}{p}{/if}{/each}</a
      >
    </h3>
    {#if s.reason}<p class="story-reason">{s.reason}</p>{/if}
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
  {#if places.length}
    <h3 id="places-h" class="places-h">Address briefings</h3>
    <ul class="places" aria-labelledby="places-h">
      {#each places as s (s.slug)}
        <li>
          <a href="{resolve('/(app)/gallery/[slug]', { slug: s.slug })}/">{s.neighborhood}</a>
          <span class="place-address">{#each parts(s.address) as p, i (i)}{#if i % 2}<span class="nowrap">{p}</span>{:else}{p}{/if}{/each}</span>
          <time datetime={s.generated_at.slice(0, 10)}>{s.generated_at.slice(0, 10)}</time>
          {#if s.reason}<p class="place-reason">{s.reason}</p>{/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .stories {
    margin-top: 96px;
  }
  h2 {
    margin: 0;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }
  .stories-note {
    margin: 6px 0 32px;
    font-size: 14px;
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
    gap: 48px;
    margin-bottom: 48px;
  }
  .stories-rest {
    gap: 32px 48px;
  }
  /* Headlines wrap to two to four lines, so they get 1.3 leading. */
  h3 {
    margin: 0;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.3;
    text-wrap: balance;
  }
  .is-top h3 {
    font-size: 28px;
    font-weight: 700;
    line-height: 1.3;
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
  /* Why the entry is in the gallery, in Small under its headline. */
  .story-reason {
    margin: 6px 0 0;
    max-width: 60ch;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .story-lead {
    margin: 8px 0 0;
    max-width: 60ch;
    font-size: 17px;
    line-height: 1.5;
    text-wrap: pretty;
  }
  .is-top .story-lead {
    font-size: 20px;
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
  .places-h {
    margin-top: 64px;
    font-size: 17px;
    line-height: 1.3;
  }
  /* One row per address briefing: the place as the link, its address,
     the snapshot date; hairlines between rows. */
  ul.places {
    display: block;
    margin-top: 8px;
    border-top: 1px solid var(--riprap-rule-hairline);
  }
  .places li {
    display: grid;
    grid-template-columns: minmax(0, 14rem) minmax(0, 1fr) auto;
    gap: 2px 24px;
    align-items: baseline;
    padding: 8px 0;
    border-bottom: 1px solid var(--riprap-rule-hairline);
    font-size: 15px;
    line-height: 1.45;
  }
  .places a {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    font-weight: 600;
  }
  .place-address {
    color: var(--ink-secondary);
  }
  .places time {
    color: var(--ink-secondary);
  }
  .place-reason {
    grid-column: 1 / -1;
    margin: 0;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  @media (max-width: 720px) {
    .stories {
      margin-top: 48px;
    }
    ul {
      grid-template-columns: minmax(0, 1fr);
    }
    .places li {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .place-address {
      grid-column: 1 / -1;
      grid-row: 2;
    }
    .is-top h3 {
      font-size: 25px;
    }
    h3 {
      font-size: 22px;
    }
  }
</style>
