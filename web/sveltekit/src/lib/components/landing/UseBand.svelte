<script lang="ts">
  /** Evidence, not advice: one line, the official sources Riprap works
   *  alongside, and the independence line. The last block above the
   *  footer, which drops its own disclaimer on the landing. */
  const SOURCES = [
    {
      need: 'Flooding right now',
      links: [
        { name: 'FloodNet sensor dashboard', href: 'https://dataviz.floodnet.nyc/' },
        { name: 'National Weather Service', href: 'https://www.weather.gov/okx/' },
        { name: 'Notify NYC', href: 'https://a858-nycnotify.nyc.gov/' }
      ]
    },
    {
      need: 'An official flood zone determination',
      links: [{ name: 'FEMA Flood Map Service Center', href: 'https://msc.fema.gov/portal/home' }]
    },
    {
      need: 'Flood insurance and what to do at home',
      links: [{ name: 'FloodHelpNY', href: 'https://www.floodhelpny.org/' }]
    },
    {
      need: 'People and housing in the floodplain',
      links: [{ name: 'NYC Planning Community District Profiles', href: 'https://communityprofiles.planning.nyc.gov/' }]
    },
    {
      need: 'Maps to explore',
      links: [{ name: 'Rainproof NYC Flood Map', href: 'https://rebuildbydesign.org/rainproof-nyc-map/' }]
    }
  ];
</script>

<section class="land-section" aria-labelledby="use-h">
  <div class="land-frame">
    <h2 id="use-h" class="land-h2">Riprap reports evidence, not advice.</h2>
    <p class="use-lead">It works alongside the official sources:</p>
    <dl class="use-sources">
      {#each SOURCES as s (s.need)}
        <div>
          <dt>{s.need}</dt>
          <dd>
            {#each s.links as l, i (l.href)}<a class="land-link" href={l.href}>{l.name}</a
              >{i < s.links.length - 1 ? ', ' : ''}{/each}
          </dd>
        </div>
      {/each}
    </dl>
    <p class="land-small use-independent">
      Independent and open source. Not affiliated with FEMA, NOAA, USGS or the City of New York.
    </p>
  </div>
</section>

<style>
  .use-lead {
    margin: 0 0 16px;
    font-size: 17px;
    line-height: 1.55;
  }
  .use-sources {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px 32px;
    margin: 0;
  }
  dt {
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  dd {
    margin: 2px 0 0;
    font-size: 17px;
    line-height: 1.55;
  }
  .use-independent {
    margin: 32px 0 0;
  }
  @media (max-width: 719px) {
    .use-sources {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
