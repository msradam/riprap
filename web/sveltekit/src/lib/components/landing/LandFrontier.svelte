<script lang="ts">
  import { resolve } from '$app/paths';

  /** Open models, open problems: the experimental land-cover model with
   *  its measured accuracy, and the surge forecast as a labelled negative
   *  result (out of default briefings since 2026-10-05, when damped
   *  persistence beat it on held-out data), then one sentence on the
   *  satellite water layer retired on 2026-10-02. The numbers are from
   *  docs/MODELS.md and the README model table. */
  const DOCS = 'https://github.com/msradam/riprap/blob/main/docs';
  const MODELS_DOC = `${DOCS}/MODELS.md`;
  const galleryHref = (slug: string) => `${resolve('/(app)/gallery/[slug]', { slug })}/`;
  interface Model {
    title: string;
    badge: string;
    does: string;
    measured: string;
    problem: string;
    card: string;
    cardLabel: string;
    /** The gallery entry that quotes the model, when a briefing still does. */
    slug?: string;
  }
  const MODELS: Model[] = [
    {
      title: 'Paved, green and tree canopy',
      badge: 'Experimental',
      does: "Estimates how much of each 10 m pixel is tree canopy, grass, paving or roof, in 2018, 2021, 2024 and 2026. A TerraMind fine-tune, trained on the city's 2017 six-inch map. A briefing quotes that map first, and the model's estimate follows it.",
      measured: "On squares it never trained on, it reads a typical district's paved share 1.7 points above The Nature Conservancy's 2021 map. Its citywide tree canopy reads 4.2 to 5.0 points below the city's 2017 map in three of its four yearly maps.",
      problem: 'Maps of different summers differ by more than two images of one summer, so it cannot yet show change between years. Telling real change from the images is the next result to earn.',
      card: `${MODELS_DOC}#nyc-land-cover-model`,
      cardLabel: 'Model card',
      slug: 'qn12-paved'
    },
    {
      title: 'Storm surge at the Battery',
      badge: 'Negative result, off by default',
      does: 'Forecasts how far the water may run above the predicted tide over the next four days. A Granite TTM r2 fine-tune. It is out of default briefings since 2026-10-05.',
      measured: 'On 639 held-out four-day windows from January 2025 to October 2026, its mean error was 0.115 m. Damped persistence, a one-line rule, scored 0.108 m and beats it. The tide table alone scored 0.167 m.',
      problem: 'It foresaw 1 of the 23 windows that reached flood stage, which are 5 distinct events. A forecast that a simple rule beats adds nothing to the Weather Service forecast a briefing already quotes. The model card on Hugging Face was corrected to say so on 2026-10-05.',
      card: `${DOCS}/model-cards/Granite-TTM-r2-Battery-Surge.md`,
      cardLabel: 'Corrected model card'
    }
  ];
</script>

<section class="land-section" aria-labelledby="frontier-h">
  <div class="land-frame">
    <h2 id="frontier-h" class="land-h2">Open models, open problems</h2>
    <p class="land-intro">
      I fine-tuned open models for New York and tested each against a simple baseline. One, which maps
      paved, green and tree-covered land, is in briefings, labelled experimental, with its tested
      accuracy in every sentence. One, a surge forecast, lost to its baseline and was taken out. The
      results are published either way.
    </p>
    <ul class="land-cards">
      {#each MODELS as m (m.title)}
        <li class="land-card">
          <div class="frontier-head">
            <h3>{m.title}</h3>
            <span class="exp-badge">{m.badge}</span>
          </div>
          <p>{m.does}</p>
          <dl class="frontier-facts">
            <dt>Measured</dt>
            <dd>{m.measured}</dd>
            <dt>The open problem</dt>
            <dd>{m.problem}</dd>
          </dl>
          <ul class="frontier-links land-card-link">
            <li><a class="land-link" href={m.card}>{m.cardLabel}</a></li>
            {#if m.slug}<li><a class="land-link" href={galleryHref(m.slug)}>See it answer</a></li>{/if}
          </ul>
        </li>
      {/each}
    </ul>
    <p class="frontier-retired">
      A third model, a satellite water layer, was retired on 2026-10-02 after two tests, one on
      Hurricane Ida and one on coastal and tidal floods that FloodNet sensors recorded at the moment
      of a satellite pass: in both it found recorded floods no more often than chance.
    </p>
    <ul class="frontier-more">
      <li><a class="land-link" href={MODELS_DOC}>Read the backtests</a></li>
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
  .frontier-retired {
    margin: 32px 0 0;
    max-width: 68ch;
    font-size: 17px;
    line-height: 1.55;
  }
  .frontier-more {
    margin-top: 16px;
  }
</style>
