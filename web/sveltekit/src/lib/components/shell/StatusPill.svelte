<script lang="ts">
  import { briefingState } from '$lib/stores/briefingState.svelte';

  /** Live status for the AppHeader.
   *
   *  Tracks pipeline phase and active step so a user staring at a half-rendered briefing knows what's
   *  actually being crunched. Reads from the briefingState rune store
   *  which q/[queryId]/+page.svelte writes into from SSE callbacks.
   *
   *  Visible only during a live run (phase != idle && != done). Hidden
   *  before a briefing starts and after the streamed run settles.
   */

  // Short labels for FSM step names, from the legacy agent.js label
  // set. Anything not mapped shows no step: an internal id is not a
  // label. An empty label hides a bookkeeping step.
  const SHORT: Record<string, string> = {
    select_deployment: 'choosing the deployment',
    geocode: 'geocoding',
    nta_resolve: 'resolving NTA',
    sandy_inundation: 'Sandy 2012',
    dep_stormwater: 'DEP scenarios',
    floodnet: 'FloodNet sensors',
    nyc311: 'NYC 311 history',
    noaa_tides: 'NOAA tides',
    nws_alerts: 'NWS alerts',
    nws_obs: 'NWS hourly obs',
    nws_water_forecast: 'NWS water-level forecast',
    ida_hwm_2021: 'Ida 2021 HWMs',
    microtopo_lidar: 'LiDAR microtopo',
    mta_entrance_exposure: 'MTA entrances',
    nycha_development_exposure: 'NYCHA developments',
    doe_school_exposure: 'DOE schools',
    doh_hospital_exposure: 'NYS DOH hospitals',
    assemble_legacy_state: '',
    fema_pfirm: 'FEMA preliminary map',
    fema_nfhl: 'FEMA flood zones',
    sandy: 'Sandy 2012',
    sandy_nta: 'Sandy 2012',
    dep_extreme_2080: 'DEP scenarios',
    dep_moderate_2050: 'DEP scenarios',
    dep_moderate_current: 'DEP scenarios',
    dep_extreme_2080_nta: 'DEP scenarios',
    dep_moderate_2050_nta: 'DEP scenarios',
    dep_moderate_current_nta: 'DEP scenarios',
    ida_hwm: 'Ida high-water marks',
    usgs_gauges: 'USGS gauges',
    water_level: 'water level',
    lake_michigan_water_level: 'Lake Michigan water level',
    chicago_311: 'Chicago 311 requests',
    seattle_311: 'Seattle service requests',
    albany_flood_311: 'Albany service requests',
    mta_entrances: 'MTA entrances',
    nycha_developments: 'NYCHA developments',
    doe_schools: 'DOE schools',
    doh_hospitals: 'hospitals',
    npcc4_slr: 'sea-level projections',
    npcc4_slr_nta: 'sea-level projections',
    nws_alerts_nta: 'NWS alerts',
    dcp_floodplain_nta: 'City Planning floodplain counts',
    mta_entrances_nta: 'MTA entrances',
    nycha_developments_nta: 'NYCHA developments',
    doe_schools_nta: 'DOE schools',
    doh_hospitals_nta: 'hospitals',
    microtopo: 'terrain',
    microtopo_nta: 'terrain',
    nyc311_nta: 'NYC 311 history',
    dob_permits_nta: 'DOB permits',
    area_boundary: 'area outline',
  };

  let visible = $derived(
    briefingState.phase !== 'idle' && briefingState.phase !== 'done'
  );

  let phaseLabel = $derived.by(() => {
    switch (briefingState.phase) {
      case 'planning':    return 'reading the question';
      case 'specialists': return 'gathering evidence';
      case 'reconciling': return 'reconciling';
      case 'error':       return 'error';
      // A stopped run shows only its reason, e.g. "refused".
      case 'stopped':     return briefingState.errorMessage ?? 'stopped';
      default:            return '';
    }
  });

  let stepLabel = $derived.by(() => {
    const s = briefingState.activeStep;
    if (!s) return null;
    return SHORT[s] || null;
  });

  // Drives the colour: red for real errors, neutral for a run that
  // stopped on purpose, otherwise the accent pulse.
  let kind = $derived(
    briefingState.phase === 'error' ? 'err' : briefingState.phase === 'stopped' ? 'stopped' : 'live'
  );
</script>

{#if visible}
  <span class="status" data-kind={kind} aria-live="polite" aria-atomic="true">
    <span class="status-dot" aria-hidden="true"></span>
    <span class="status-phase">{phaseLabel}</span>
    {#if stepLabel}
      <span class="status-step-sep">:</span>
      <span class="status-step">{stepLabel}</span>
    {/if}
    {#if briefingState.phase === 'error' && briefingState.errorMessage}
      <span class="status-sep">:</span>
      <span class="status-err">{briefingState.errorMessage}</span>
    {/if}
  </span>
{/if}

<style>
  .status {
    display: inline-flex;
    align-items: baseline;
    gap: 0 6px;
    font-family: var(--font-sans);
    font-size: 14px;
    color: var(--ink-secondary);
    line-height: 20px;
    max-width: min(60ch, 50vw);
    /* Shrinks inside the header row; the step, then the phase, truncate.
       The full text stays in the DOM, so the live region reads all of it. */
    flex: 0 1 auto;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }
  .status[data-kind='err'] {
    color: #B91C1C;
  }
  .status-dot {
    align-self: center;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex: none;
    background: var(--accent-graphical);
    animation: pulse 1.4s ease-in-out infinite;
  }
  .status[data-kind='err'] .status-dot {
    background: #B91C1C;
    animation: none;
  }
  .status[data-kind='stopped'] .status-dot {
    background: var(--ink-tertiary);
    animation: none;
  }
  .status[data-kind='stopped'] .status-phase {
    color: var(--ink-secondary);
    font-weight: 500;
  }
  .status-phase {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--ink);
    font-weight: 600;
  }
  .status-sep,
  .status-step-sep { flex: none; margin-left: -6px; }
  .status-step {
    flex: 0 100 auto;
    min-width: 0;
    color: var(--ink-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .status-err { min-width: 0; overflow: hidden; text-overflow: ellipsis; color: #B91C1C; }
  @keyframes pulse {
    0%, 100% { opacity: 0.35; transform: scale(0.85); }
    50%      { opacity: 1; transform: scale(1.1); }
  }
  @media (prefers-reduced-motion: reduce) {
    .status-dot { animation: none; opacity: 0.7; }
  }
  /* A narrow header row has no room for the step name beside the phase,
     so it is hidden visually but still read by the live region. */
  @container (max-width: 380px) {
    .status-step, .status-step-sep {
      position: absolute;
      width: 1px; height: 1px;
      padding: 0; margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      border: 0;
    }
  }
  /* Phones: the pill may use the whole row beside "methodology". */
  @media (max-width: 720px) {
    .status { max-width: 100%; }
  }
</style>
