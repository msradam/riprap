<script lang="ts">
  /** Evidence, not advice: one compact line with the official sources
   *  Riprap works alongside (for heat, the ones its own briefings name),
   *  then where to go for alerts and help, then the independence line
   *  (the warranty sentence follows Local Law 11 of 2012, section 23-504).
   *  It sits just above "Build it with us"; the footer drops its own
   *  disclaimer on the landing. */
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
      need: 'what to do in extreme heat',
      links: [
        { name: 'NYC Health Department', href: 'https://www.nyc.gov/health' },
        { name: 'National Weather Service heat safety', href: 'https://www.weather.gov/safety/heat' },
        { name: 'NYC Cooling Center Finder', href: 'https://finder.nyc.gov/coolingcenters' }
      ]
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
  </p>
  <p>
    <strong>Riprap is not an alert or emergency service.</strong> For emergency alerts, sign up with
    <a href="https://a858-nycnotify.nyc.gov/">Notify NYC</a>; to report flooding or ask the city for
    help, use <a href="https://portal.311.nyc.gov/">311</a>; for flood insurance questions, see
    <a href="https://www.floodhelpny.org/">FloodHelpNY</a>.
  </p>
  <p>
    Riprap is independent and open source, and it is not a City product. It is not endorsed by or
    affiliated with FloodNet, New York University, the City University of New York, FEMA, NOAA, USGS
    or the City of New York. The City publishes its open data for information only and does not
    warrant its completeness, accuracy, content or fitness for any use.
  </p>
</div>

<style>
  /* One ruled block of three paragraphs. */
  .use-line p {
    margin: 0;
    max-width: 96ch;
    font-size: 14px;
    line-height: 1.6;
    color: var(--ink-secondary);
  }
  .use-line p + p {
    margin-top: 8px;
  }
  .use-line p:first-child {
    padding-top: 24px;
    border-top: 1px solid var(--riprap-rule-hairline);
  }
  .use-line p:last-child {
    padding-bottom: 24px;
    border-bottom: 1px solid var(--riprap-rule-hairline);
  }
  .use-line strong {
    color: var(--ink);
  }
</style>
