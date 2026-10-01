<script lang="ts">
  /** The public sources behind a briefing, grouped by the five Stones.
   *  Source names are the manifests' own (deployments/nyc/manifests and
   *  deployments/federal/manifests); the experimental model layers are in
   *  LandFrontier. */
  import { STONE_META, STONE_ORDER, type StoneKey } from '$lib/types/card';

  const SOURCES: Record<StoneKey, string> = {
    cornerstone:
      "FEMA's effective and preliminary flood maps, NYC DEP stormwater scenarios for today, 2050 and 2080, the 2012 Sandy inundation extent, USGS Hurricane Ida high-water marks, USGS terrain",
    touchstone:
      'FloodNet street sensors, NYC 311 flood complaints, NOAA tide gauges, USGS stream gauges, National Weather Service observations',
    keystone:
      "NYC public schools, MTA subway entrances, NYCHA developments, hospitals, active DOB construction permits, NYC Planning's floodplain counts",
    lodestone: 'National Weather Service alerts and water-level forecasts, NPCC4 sea-level projections',
    capstone: 'Writes one cited sentence per record, and answers a question by rules over its words'
  };
  const DOCS = 'https://github.com/msradam/riprap/blob/main/docs';
</script>

<section class="land-section" id="methodology" aria-labelledby="stones-h">
  <div class="land-frame">
    <h2 id="stones-h" class="land-h2">Built on 23 public sources</h2>
    <p class="land-intro">
      City, state and federal records, read live or from their published files and sorted into five
      Stones. No commercial data and no scores.
    </p>
    <dl class="stones">
      {#each STONE_ORDER as key (key)}
        <div class="stone">
          <dt>{STONE_META[key].name}, {STONE_META[key].role}</dt>
          <dd>{SOURCES[key]}</dd>
        </div>
      {/each}
    </dl>
    <ul class="stones-links land-small">
      <li><a class="land-link" href="{DOCS}/DATA-SOURCES.md">Every source, with its licence and date</a></li>
      <li><a class="land-link" href="{DOCS}/METHODOLOGY.md">How a briefing is made</a></li>
    </ul>
  </div>
</section>

<style>
  .stones {
    margin: 0;
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  /* A table row per Stone: the Stone in 4 columns, its sources in 8. */
  .stone {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    column-gap: 32px;
    padding: 16px 0;
    border-top: 1px solid var(--riprap-rule-hairline);
  }
  dt {
    grid-column: span 4;
    font-size: 17px;
    font-weight: 600;
    line-height: 1.45;
  }
  dd {
    grid-column: span 8;
    margin: 0;
    max-width: 68ch;
    font-size: 17px;
    line-height: 1.55;
    color: var(--ink-secondary);
  }
  .stones-links {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 24px;
    margin: 24px 0 0;
    padding: 0;
    list-style: none;
  }
  @media (max-width: 720px) {
    .stone {
      display: block;
    }
    dd {
      margin-top: 4px;
    }
  }
</style>
