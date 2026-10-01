<script lang="ts">
  /** What Riprap is for and what other tools do better, then responsible
   *  use: evidence, not advice, and the non-affiliation note, as plain
   *  prose. */
</script>

<section class="land-section" aria-labelledby="for-h">
  <h2 id="for-h">What Riprap is for, and what it is not</h2>
  <p>
    The flood records for a New York City block are public, and they sit in separate places: FEMA's
    flood maps, the city's stormwater scenarios, the Sandy inundation extent, Ida high-water marks,
    311 requests, street sensors. Riprap reads them for one address or one community district and
    quotes each with its source and date, so a sentence can go into a story or a board memo with its
    citation.
  </p>
  <p>
    For a district it names the schools, subway entrances, public housing developments and hospitals
    inside the mapped flood extents. The same evidence is available as JSON over HTTP and MCP, for
    code and AI agents.
  </p>
  <p>Other tools do these jobs better, and Riprap points to them:</p>
  <ul>
    <li>
      What is flooding right now: the
      <a href="https://dataviz.floodnet.nyc/">FloodNet sensor dashboard</a>, the
      <a href="https://www.weather.gov/okx/">National Weather Service</a> and
      <a href="https://a858-nycnotify.nyc.gov/">Notify NYC</a>.
    </li>
    <li>
      An official flood zone determination: FEMA's
      <a href="https://msc.fema.gov/portal/home">Flood Map Service Center</a>.
    </li>
    <li>
      Flood insurance and what to do at home:
      <a href="https://www.floodhelpny.org/">FloodHelpNY</a>.
    </li>
  </ul>
</section>

<section class="land-section" aria-labelledby="use-h">
  <h2 id="use-h">Riprap returns evidence, not advice.</h2>
  <p>
    Riprap composes public-record data into a written briefing. It does not predict damage to
    specific properties or substitute for professional engineering judgment. For personal property
    decisions, contact your local resilience office or hazard-mitigation program.
  </p>
  <p>
    Independent open-source project. Not affiliated with FEMA, NOAA, USGS, or any city government.
    Data is used under each source's open-data terms.
  </p>
</section>

<style>
  .land-section {
    margin-top: 64px;
    max-width: 60ch;
  }
  h2 {
    margin: 0 0 8px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }
  p,
  ul {
    margin: 0 0 12px;
    font-size: 17px;
    line-height: 1.55;
  }
  ul {
    padding-left: 1.2em;
  }
  li {
    padding: 2px 0;
  }
  a {
    color: var(--riprap-text-link);
    text-underline-offset: 0.2em;
  }
  a:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  @media (max-width: 640px) {
    .land-section {
      margin-top: 48px;
    }
  }
</style>
