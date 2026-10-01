<script lang="ts">
  /** What Riprap is for, and the official sources it works alongside, as plain prose
   *  directly under the hero. */
  import { STATIC_SITE } from '$lib/staticSite';
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
  <p>
    Three experimental models, fine-tuned by Riprap's author, answer a few questions about the days
    and years ahead: a surge forecast for the Battery, new surface water in satellite scenes after
    storms, and land cover by year. Whatever they say is labelled experimental, with its limits and
    tested accuracy beside it, and it never sets a yes or no about past flooding.
  </p>
  <p>Riprap is built to work alongside the official sources, and links to them where they are the authority:</p>
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
    <li>
      A district's people and housing in the floodplain, on a city-made page: NYC Planning's
      <a href="https://communityprofiles.planning.nyc.gov/">Community District Profiles</a>.
    </li>
    <li>
      Maps to explore: Rebuild by Design's
      <a href="https://rebuildbydesign.org/rainproof-nyc-map/">Rainproof NYC Flood Map</a>.
    </li>
  </ul>
  {#if STATIC_SITE}
    <p>This public copy shows saved briefings only; your own questions need a local install.</p>
  {/if}
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
