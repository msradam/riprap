<script lang="ts">
  /** The public sources behind a briefing, grouped by the five Stones:
   *  a plain label leads each row, the Stone's name is its tag. The count
   *  in the heading is docs/DATA-SOURCES.md's: 25 flood sources and 11
   *  heat sources, less the two read for both.
   *  Source names are the manifests' own (deployments/nyc/manifests and
   *  deployments/federal/manifests); the experimental model layers are in
   *  LandFrontier. */
  import { resolve } from '$app/paths';
  import { STONE_META, STONE_ORDER, type StoneKey } from '$lib/types/card';

  const SOURCES: Record<StoneKey, string> = {
    cornerstone:
      "FEMA's effective and preliminary flood maps, the city's four modelled stormwater flood maps for today, 2050 and 2080, the 2012 Sandy inundation extent, USGS Hurricane Ida high-water marks, USGS terrain",
    touchstone:
      'FloodNet street sensors, NYC 311 complaints about flooding and sewer backups, NOAA tide gauges, USGS stream gauges, National Weather Service observations',
    keystone:
      "NYC public schools, MTA subway entrances, NYCHA developments, hospitals, NYC Planning's floodplain counts; DOB construction permits only when a question asks",
    lodestone: 'National Weather Service alerts and water-level forecasts, NPCC4 sea-level projections',
    capstone:
      "Code turns each record into one cited sentence, and rules set the answer's lead (Yes, No, a count). An optional open Granite model may route a question the rules do not match and choose among those sentences; it never writes one, and code checks its choice."
  };
  /** The heat briefing's sources, set under each Stone's flood sources.
   *  The land cover map is read for both. */
  const HEAT: Partial<Record<StoneKey, string>> = {
    cornerstone:
      "Landsat surface temperature, the NYC Health Department's Heat Vulnerability Index and heat illness emergency visits, the city's 2017 land cover map (tree canopy)",
    touchstone: 'Weather station records of 90 degree days, the latest air temperature at the nearest station',
    keystone: 'NYC Parks spray showers and pools',
    lodestone: 'The National Weather Service forecast and heat alerts, NPCC4 heat projections'
  };
  const LABELS: Record<StoneKey, string> = {
    cornerstone: 'Hazard maps and storm records',
    keystone: 'Places at risk',
    touchstone: 'Live sensors and complaints',
    lodestone: 'Forecasts and projections',
    capstone: 'How answers are written'
  };
  const DOCS = 'https://github.com/msradam/riprap/blob/main/docs';
</script>

<section class="land-section" id="methodology" aria-labelledby="stones-h">
  <div class="land-frame">
    <h2 id="stones-h" class="land-h2">Built on 34 public sources</h2>
    <p class="land-intro">
      City, state and federal records, read live or from their published files and sorted into five
      Stones: 25 for a flood briefing and 11 for a heat briefing, two of them shared. No commercial
      data and no scores. Each record has its own portal; Riprap reads them together for one
      place and links back to each.
    </p>
    <dl class="stones">
      {#each STONE_ORDER as key (key)}
        <div class="stone">
          <dt>{LABELS[key]} <span class="stone-tag">{STONE_META[key].name}</span></dt>
          <dd>
            {SOURCES[key]}
            {#if HEAT[key]}<span class="stone-heat">For heat: {HEAT[key]}</span>{/if}
          </dd>
        </div>
      {/each}
    </dl>
    <p class="land-small stones-licence">
      FloodNet data is licensed CC-BY-NC-SA 4.0 and the NPCC4 projections CC-BY-NC 4.0; the other
      sources are public domain or open. <a href="{DOCS}/DATA-SOURCES.md">See every source and licence</a>.
    </p>
    <p class="land-small stones-links">
      <a class="land-link" href="{DOCS}/METHODOLOGY.md">How a briefing is made</a>
    </p>
    <p class="land-small stones-links">
      <a class="land-link" href="{resolve('/(site)/about')}/">Where a language model can run, what the data cannot say, and how Riprap was built</a>
    </p>
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
  /* The Stone's name: Small, secondary ink, on its own line under the label. */
  .stone-tag {
    display: block;
    font-size: 14px;
    font-weight: 400;
    color: var(--ink-secondary);
  }
  /* A Stone's heat sources, on their own line under its flood sources. */
  .stone-heat {
    display: block;
    margin-top: 4px;
  }
  .stones-licence {
    margin: 24px 0 0;
    max-width: 68ch;
  }
  .stones-links {
    margin: 8px 0 0;
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
