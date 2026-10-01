<script lang="ts">
  /** Evidence, not advice: one compact line with the seven official
   *  sources Riprap works alongside, and the independence line. It sits
   *  just above "Build it with us"; the footer drops its own disclaimer
   *  on the landing. */
  const SOURCES = [
    {
      need: 'flooding right now',
      links: [
        { name: 'FloodNet sensor dashboard', href: 'https://dataviz.floodnet.nyc/' },
        { name: 'National Weather Service', href: 'https://www.weather.gov/okx/' },
        { name: 'Notify NYC', href: 'https://a858-nycnotify.nyc.gov/' }
      ]
    },
    {
      need: 'an official flood zone',
      links: [{ name: 'FEMA Flood Map Service Center', href: 'https://msc.fema.gov/portal/home' }]
    },
    {
      need: 'insurance and what to do at home',
      links: [{ name: 'FloodHelpNY', href: 'https://www.floodhelpny.org/' }]
    },
    {
      need: 'people and housing in the floodplain',
      links: [{ name: 'NYC Planning Community District Profiles', href: 'https://communityprofiles.planning.nyc.gov/' }]
    },
    {
      need: 'maps to explore',
      links: [{ name: 'Rainproof NYC Flood Map', href: 'https://rebuildbydesign.org/rainproof-nyc-map/' }]
    }
  ];
</script>

<div class="land-frame use-line">
  <p>
    <strong>Riprap reports evidence, not advice.</strong> For {#each SOURCES as s, i (s.need)}{s.need},
      {#each s.links as l, j (l.href)}<a href={l.href}>{l.name}</a>{j < s.links.length - 1 ? ', ' : ''}{/each}{i < SOURCES.length - 1 ? '; ' : '.'}{/each}
    Independent and open source. Not affiliated with FEMA, NOAA, USGS or the City of New York.
  </p>
</div>

<style>
  .use-line p {
    margin: 0;
    padding: 24px 0;
    max-width: 96ch;
    border-top: 1px solid var(--riprap-rule-hairline);
    border-bottom: 1px solid var(--riprap-rule-hairline);
    font-size: 14px;
    line-height: 1.6;
    color: var(--ink-secondary);
  }
  .use-line strong {
    color: var(--ink);
  }
</style>
