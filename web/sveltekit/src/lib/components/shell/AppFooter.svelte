<script lang="ts">
  import { resolve } from '$app/paths';
  import { deployment } from '$lib/stores/deployment.svelte';
  import { APP_VERSION } from '$lib/version';

  const FEEDBACK = 'https://github.com/msradam/riprap/issues/new/choose';
  // NYC-only "for residents, see" resource links. Only render when
  // the active deployment is NYC. Under a Chicago / Seattle / Albany /
  // out-of-coverage chip these resources would be either out of scope
  // (FloodHelpNY covers New York City) or misdirection (FloodNet NYC
  // has no Chicago coverage).
  /** `disclaimer` is false on briefing pages, whose scope note already
   *  carries the disclaimer and whose answer carries the resident pointer.
   *  `nycPage` is true on the pages that are about New York City whatever
   *  the server's deployment (the landing, the gallery, the about and
   *  accessibility pages), which never load the deployment. */
  let { disclaimer = true, nycPage = false }: { disclaimer?: boolean; nycPage?: boolean } = $props();
  let showNycResources = $derived(nycPage || deployment.current?.name === 'nyc');
</script>

<footer class="app-footer no-print">
  <div class="app-footer-inner">
    {#if disclaimer}
      <p class="app-footer-guard">
        <strong>Riprap is a reference dossier, not a stamped engineering memo, risk score, or disclosure.</strong>
        It is informational only; not a substitute for a licensed professional, and
        not designed for personal property decisions, real-estate transactions, or
        mortgage / insurance underwriting. {#if showNycResources}For residents, see
          <!-- nyc-leak-ok: links gated on showNycResources (deployment === 'nyc') -->
          <a href="https://www.floodhelpny.org">FloodHelpNY</a>
          <!-- nyc-leak-ok: same gate as the FloodHelpNY link above -->
          and <a href="https://www.floodnet.nyc">FloodNet NYC</a>.{/if}
      </p>
    {/if}
    <!-- On every page, in this order (WCAG 3.2.6, consistent help): where to
         go for help Riprap does not give, whose project this is, then the
         site's own pages and the feedback link. -->
    <p class="app-footer-help">
      <strong>Riprap is not an alert or emergency service.</strong>
      {#if showNycResources}
        <!-- nyc-leak-ok: links gated on showNycResources (an NYC page or deployment === 'nyc') -->
        For emergency alerts, sign up with <a href="https://a858-nycnotify.nyc.gov/">Notify NYC</a>; to report flooding or ask the city for help, use
        <a href="https://portal.311.nyc.gov/">311</a>; for flood insurance questions, see
        <!-- nyc-leak-ok: same gate as the alert link above -->
        <a href="https://www.floodhelpny.org/">FloodHelpNY</a>.
      {:else}
        For warnings, follow your local emergency management office and the National Weather Service.
      {/if}
    </p>
    <p class="app-footer-independent">
      Riprap is an independent project and not a government product.
      {#if showNycResources}
        It is not endorsed by or affiliated with FloodNet, New York University, the City University
        of New York, FEMA, NOAA, USGS or the City of New York. The City publishes its open data for
        information only and does not warrant its completeness, accuracy, content or fitness for
        any use.
      {:else}
        It is not endorsed by or affiliated with any agency or institution whose data it reads, and
        those publishers do not warrant the data.
      {/if}
    </p>
    <nav class="app-footer-nav" aria-label="About this site">
      <ul>
        <li><a href="{resolve('/(site)/about')}/">About, method and AI disclosure</a></li>
        <li><a href="{resolve('/(site)/accessibility')}/">Accessibility statement</a></li>
      </ul>
    </nav>
    <p class="app-footer-beta">
      This is open beta. Methodology and source attribution are stable. New York City is the
      production city; Chicago, Seattle and Albany are experimental. <a href={FEEDBACK} target="_blank" rel="noopener">Send feedback</a>.
    </p>
    <p class="app-footer-build">
      Built to meet WCAG 2.2 AA, with USWDS patterns and plain language; the accessibility statement
      says how that was tested and what has not been shown. Riprap is open source
      under Apache-2.0. The records come from public federal, state and city sources; the
      experimental layers also read Copernicus Sentinel satellite imagery. No commercial data APIs are used; the map's background tiles come from CARTO. Riprap <span class="data">v{APP_VERSION}</span>.
    </p>
    <p class="app-footer-author">
      Built by <a href="https://github.com/msradam">Adam Munawar Rahman</a>.
    </p>
    <p class="app-footer-credits">
      Dam mark: <a href="https://thenounproject.com/icon/dam-4516918/">"Dam" by Chintuza</a> via the Noun Project, CC-BY 3.0.
    </p>
  </div>
</footer>

<style>
  /* Measure: no footer line runs past 75 characters (54ch of Sofia Sans). */
  .app-footer-guard,
  .app-footer-help,
  .app-footer-independent,
  .app-footer-beta,
  .app-footer-build,
  .app-footer-author,
  .app-footer-credits {
    max-width: 54ch;
  }
</style>
