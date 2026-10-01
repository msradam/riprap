<script lang="ts">
  import { resolve } from '$app/paths';

  /** Open models, open problems: the three experimental models, each
   *  with its measured accuracy and the baseline it has to beat. The
   *  numbers are from docs/MODELS.md and the README model table. */
  const HF = 'https://huggingface.co/msradam';
  const galleryHref = (slug: string) => `${resolve('/(app)/gallery/[slug]', { slug })}/`;
  const MODELS = [
    {
      title: 'Storm surge at the Battery',
      does: 'Forecasts how far the water may run above the predicted tide over the next four days. A Granite TTM r2 fine-tune.',
      measured: 'Mean error of 11.5 cm against 13.3 cm for a simple baseline, over 635 four-day windows since January 2025.',
      problem: 'It foresaw 1 of the 23 windows that reached minor flood stage. Catching those is the next result to earn.',
      card: `${HF}/Granite-TTM-r2-Battery-Surge`,
      slug: 'battery-surge'
    },
    {
      title: 'Surface water from orbit',
      does: 'Maps new surface water in Sentinel-2 scenes after Ida and other heavy rains. A Prithvi-EO 2.0 fine-tune.',
      measured: 'New water within 500 m of 17 of 153 surveyed Ida high-water marks (11%), where chance gives 14%.',
      problem: 'Street and basement flooding is hard to see from orbit. Beating chance at the surveyed marks is the bar.',
      card: `${HF}/Prithvi-EO-2.0-NYC-Pluvial`,
      slug: 'bk18-satellite'
    },
    {
      title: 'Paved and green land',
      does: 'Labels how much of a place is paved or green, in 2018, 2021, 2024 and 2026. A TerraMind fine-tune.',
      measured: '87.1% agreement with ESA WorldCover on paved, green or water for 2021.',
      problem: 'Two images of one year differ by under 3.7 points 19 times in 20, so a change between years has to clear that noise.',
      card: `${HF}/TerraMind-NYC-Adapters`,
      slug: 'qn12-paved'
    }
  ];
</script>

<section class="land-section" aria-labelledby="frontier-h">
  <div class="land-frame">
    <h2 id="frontier-h" class="land-h2">Open models, open problems</h2>
    <p class="land-intro">
      Riprap's author fine-tuned three open models for New York. They answer questions about the days
      and years ahead, labelled experimental, with their tested accuracy in every sentence. Each one
      has a measured baseline to beat.
    </p>
    <ul class="land-cards is-three">
      {#each MODELS as m (m.slug)}
        <li class="land-card">
          <div class="frontier-head">
            <h3>{m.title}</h3>
            <span class="exp-badge">Experimental</span>
          </div>
          <p>{m.does}</p>
          <dl class="frontier-facts">
            <dt>Measured</dt>
            <dd>{m.measured}</dd>
            <dt>The open problem</dt>
            <dd>{m.problem}</dd>
          </dl>
          <ul class="frontier-links land-card-link">
            <li><a class="land-link" href={m.card}>Model card</a></li>
            <li><a class="land-link" href={galleryHref(m.slug)}>See it answer</a></li>
          </ul>
        </li>
      {/each}
    </ul>
    <ul class="frontier-more">
      <li><a class="land-link" href="https://github.com/msradam/riprap/blob/main/docs/MODELS.md">Read the backtests</a></li>
      <li><a class="land-link" href="https://github.com/msradam/riprap-models">Reproduce the models</a></li>
    </ul>
  </div>
</section>

<style>
  /* The badge sits under the heading in every card, whatever its length. */
  .frontier-head {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .frontier-facts {
    margin: 0;
    font-size: 17px;
    line-height: 1.55;
  }
  dt {
    margin-top: 12px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  dt:first-child {
    margin-top: 0;
  }
  dd {
    margin: 2px 0 0;
  }
  .frontier-links,
  .frontier-more {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 24px;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 17px;
  }
  .frontier-more {
    margin-top: 32px;
  }
</style>
