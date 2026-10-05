<script lang="ts">
  import { resolve } from '$app/paths';
  import type { Proof } from '$lib/landing';

  /** Proof: real gallery answers as cards. The district card is wide and
   *  comes first; each question card is headed by its question and quotes
   *  the snapshot word for word (tests/unit/landing.test.ts checks it).
   *  One sentence after the cards names who it is for. */
  export interface ProofCard extends Proof {
    question: string | null;
    place: string;
    date: string;
  }
  interface Props {
    cards: ProofCard[];
    /** Saved briefings in the gallery. */
    count: number;
  }
  let { cards, count }: Props = $props();

  // Keep house numbers such as "90-01" on one line in a headline.
  const parts = (t: string) => t.split(/(\d+-\d+)/);
</script>

<section class="land-section land-band" aria-labelledby="proof-h">
  <div class="land-frame">
    <h2 id="proof-h" class="land-h2">Real questions, answered from the record</h2>
    <p class="land-intro">Each answer below is a saved briefing. Open one and check any sentence against its source.</p>
    <ul class="land-cards">
      {#each cards as c, i (c.slug)}
        <li class={['land-card', i === 0 && 'is-wide']}>
          <p class="land-kind">{c.kind}</p>
          {#if c.figure}
            <p class="proof-figure">
              <span class="proof-figure-n">{c.figure.text}</span>
              {#if c.figure.label}<span class="proof-figure-label">{c.figure.label}</span>{/if}
            </p>
          {/if}
          <h3>
            <a href="{resolve('/(app)/gallery/[slug]', { slug: c.slug })}/"
              >{#each parts(c.question ?? c.place) as p, j (j)}{#if j % 2}<span class="nowrap">{p}</span
                  >{:else}{p}{/if}{/each}</a
            >
          </h3>
          <blockquote class="proof-quote">
            {#each c.quotes as q (q)}<p>{q}</p>{/each}
          </blockquote>
          {#if c.note}<p class="proof-note">{c.note}</p>{/if}
          <p class="proof-byline">
            <span>{c.place}</span>
            <time class="data" datetime={c.date}>{c.date}</time>
          </p>
        </li>
      {/each}
    </ul>
    <p class="proof-for">
      Made for people who have to cite it: reporters quoting a block's record on deadline, community
      boards and council offices taking a district to the meeting in one printable briefing, planners
      checking which schools, subway entrances and public housing sit in a flood extent, and
      researchers who want <a href="#developers">the same evidence in code</a>.
    </p>
    <p class="proof-more">
      <a class="land-link" href="{resolve('/(app)/gallery')}/">See all {count} briefings in the gallery</a>
    </p>
  </div>
</section>

<style>
  .is-wide {
    grid-column: 1 / -1;
  }
  .proof-figure {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  /* Figures stay in Sofia: Mono at this size is a label voice. */
  .proof-figure-n {
    font-size: 44px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
    color: var(--ink);
  }
  .proof-figure-label {
    max-width: 48ch;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  h3 a {
    color: var(--ink);
    text-decoration: none;
  }
  h3 a:hover {
    text-decoration: underline;
  }
  .nowrap {
    white-space: nowrap;
  }
  .proof-quote {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 0;
  }
  .proof-note {
    margin: 0;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .proof-byline {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 4px 16px;
    margin-top: auto;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .proof-for {
    margin: 32px 0 0;
    max-width: 68ch;
    font-size: 17px;
    line-height: 1.55;
  }
  .proof-more {
    margin: 16px 0 0;
    font-size: 17px;
  }
</style>
