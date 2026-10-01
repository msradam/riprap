<script lang="ts">
  import { deployment } from '$lib/stores/deployment.svelte';
  import { APP_VERSION } from '$lib/version';

  const FEEDBACK = 'https://github.com/msradam/riprap/issues/new/choose';
  // NYC-only "for residents, see" resource links. Only render when
  // the active deployment is NYC. Under a Chicago / Seattle / Albany /
  // out-of-coverage chip these resources would be either out of scope
  // (FloodHelpNY covers New York City) or misdirection (FloodNet NYC
  // has no Chicago coverage).
  let showNycResources = $derived(deployment.current?.name === 'nyc');

  /** False on briefing pages, whose scope note already carries the
   *  disclaimer and whose answer carries the resident pointer. */
  let { disclaimer = true }: { disclaimer?: boolean } = $props();
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
    <p class="app-footer-beta">
      This is open beta. Methodology and source attribution are stable. New York City is the
      production city; Chicago, Seattle and Albany are experimental. <a href={FEEDBACK} target="_blank" rel="noopener">Send feedback</a>.
    </p>
    <p class="app-footer-build">
      Built to USWDS, WCAG 2.2 AA, Section 508 and the Plain Writing Act. Riprap is open source
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
  .app-footer-beta,
  .app-footer-build,
  .app-footer-author,
  .app-footer-credits {
    max-width: 54ch;
  }
</style>
