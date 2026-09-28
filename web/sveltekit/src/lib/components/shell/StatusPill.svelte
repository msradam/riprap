<script lang="ts">
  import { briefingState } from '$lib/stores/briefingState.svelte';

  /** v0.4.5 — live status pill for the AppHeader.
   *
   *  Tracks pipeline phase + active step + fired-count so a user staring at a half-rendered briefing knows what's
   *  actually being crunched. Reads from the briefingState rune store
   *  which q/[queryId]/+page.svelte writes into from SSE callbacks.
   *
   *  Visible only during a live run (phase != idle && != done). Hidden
   *  before a briefing starts and after the streamed run settles.
   */

  // Pretty short labels for FSM step names. Lifted from the legacy
  // agent.js label set; only the short names land here — the trace
  // panel still owns the long form. Anything not mapped just shows
  // its raw step name, which is mono-cased and readable.
  const SHORT: Record<string, string> = {
    geocode: 'geocoding',
    nta_resolve: 'resolving NTA',
    sandy_inundation: 'Sandy 2012',
    dep_stormwater: 'DEP scenarios',
    floodnet: 'FloodNet sensors',
    nyc311: 'NYC 311 history',
    noaa_tides: 'NOAA tides',
    nws_alerts: 'NWS alerts',
    nws_obs: 'NWS hourly obs',
    ttm_311_forecast: 'TTM r2 weekly 311',
    ttm_battery_surge: 'TTM Battery (NYC fine-tune)',
    floodnet_forecast: 'FloodNet recurrence forecast',
    ida_hwm_2021: 'Ida 2021 HWMs',
    prithvi_water: 'Ida surface water (experimental)',
    microtopo_lidar: 'LiDAR microtopo',
    mta_entrance_exposure: 'MTA entrances',
    nycha_development_exposure: 'NYCHA developments',
    doe_school_exposure: 'DOE schools',
    doh_hospital_exposure: 'NYS DOH hospitals',
    terramind_synthesis: 'TerraMind v1 synthesis',
    terramind_lulc: 'TerraMind LULC',
    terramind_buildings: 'TerraMind Buildings',
    eo_chip_fetch: 'fetching S2/S1/DEM chip',
    rag_granite_embedding: 'RAG retrieval',
    gliner_extract: 'GLiNER typed extraction',
  };

  let visible = $derived(
    briefingState.phase !== 'idle' && briefingState.phase !== 'done'
  );

  let phaseLabel = $derived.by(() => {
    switch (briefingState.phase) {
      case 'planning':    return 'planning intent';
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
    return SHORT[s] ?? s;
  });

  let progress = $derived.by(() => {
    if (briefingState.phase !== 'specialists' && briefingState.phase !== 'reconciling') return null;
    const fired = briefingState.firedCount;
    const total = briefingState.totalSpecialists;
    if (!total) return fired > 0 ? `${fired}` : null;
    return `${fired}/${total}`;
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
      <span class="status-sep status-step-sep">·</span>
      <span class="status-step">{stepLabel}</span>
    {/if}
    {#if progress}
      <span class="status-sep">·</span>
      <span class="status-progress">{progress}</span>
    {/if}
    {#if briefingState.phase === 'error' && briefingState.errorMessage}
      <span class="status-sep">·</span>
      <span class="status-err">{briefingState.errorMessage}</span>
    {/if}
  </span>
{/if}

<style>
  .status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 2px 10px;
    background: var(--paper-deep);
    border: 1px solid var(--rule-soft);
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-secondary);
    letter-spacing: 0.04em;
    line-height: 18px;
    max-width: min(60ch, 50vw);
    /* Shrinks inside the header row; the step, then the phase, truncate.
       The full text stays in the DOM, so the live region reads all of it. */
    flex: 0 1 auto;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }
  .status[data-kind='err'] {
    border-color: #B91C1C;
    color: #B91C1C;
  }
  .status-dot {
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
    text-transform: lowercase;
    letter-spacing: 0.05em;
    font-weight: 600;
  }
  .status-sep { flex: none; color: var(--ink-tertiary); opacity: 0.6; }
  .status-step {
    flex: 0 100 auto;
    min-width: 0;
    color: var(--ink-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .status-progress { flex: none; color: var(--ink); font-weight: 600; }
  .status-err { min-width: 0; overflow: hidden; text-overflow: ellipsis; color: #B91C1C; }
  @keyframes pulse {
    0%, 100% { opacity: 0.35; transform: scale(0.85); }
    50%      { opacity: 1; transform: scale(1.1); }
  }
  @media (prefers-reduced-motion: reduce) {
    .status-dot { animation: none; opacity: 0.7; }
  }
  /* A narrow header row has no room for the step name beside the phase
     and count, so it is hidden visually but still read by the live region. */
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
