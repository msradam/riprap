<script lang="ts">
  /** What a briefing contains: the Five Stones as a definition list, with
   *  the taglines from STONE_META. */
  import { STONE_META, STONE_ORDER } from '$lib/types/card';

  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
</script>

<section class="land-section" id="methodology" aria-labelledby="stones-h">
  <h2 id="stones-h">What a briefing contains</h2>
  <p>
    Every claim cites its source: a public record from FEMA, NOAA, USGS or city open data, or, where
    it is labelled experimental, one of three models. Riprap reads 23 public data sources for New
    York City; the methodology was last updated
    <time datetime="2026-10-01">2026-10-01</time>.
  </p>
  <p>
    Each briefing routes through a fixed taxonomy of public-record specialists. Each Stone is a class
    of evidence. Together they form the briefing, and every claim in the output traces back to the
    Stone that produced it.
  </p>
  <dl>
    {#each STONE_ORDER as key (key)}
      <div>
        <dt>{STONE_META[key].name}, {STONE_META[key].role}</dt>
        <dd>{cap(STONE_META[key].tag)}.</dd>
      </div>
    {/each}
  </dl>
</section>

<style>
  .land-section {
    margin-top: 64px;
    max-width: 60ch;
  }
  h2 {
    margin: 0 0 12px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }
  p {
    margin: 0 0 12px;
    font-size: 17px;
    line-height: 1.55;
  }
  time {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 400;
  }
  dl {
    margin: 20px 0 0;
  }
  dl div {
    padding: 10px 0;
    border-top: 1px solid var(--riprap-rule-hairline);
  }
  dt {
    font-size: 17px;
    font-weight: 600;
  }
  dd {
    margin: 2px 0 0;
    font-size: 17px;
    color: var(--ink-secondary);
  }
  @media (max-width: 640px) {
    .land-section {
      margin-top: 48px;
    }
  }
</style>
