<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import ResultsView from '$lib/components/results/ResultsView.svelte';
  import { RunState } from '$lib/client/runState.svelte';
  import { briefingState, persistSnapshot } from '$lib/stores/briefingState.svelte';
  import { snapshotFromRun } from '$lib/client/briefingModel';
  import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
  import { deployment } from '$lib/stores/deployment.svelte';
  import { openAgentStream, hazardLabel, isHeat, NO_BACKEND } from '$lib/client/agentStream';
  import {
    fetchSandy, fetchDep,
    fetchIdaHwm, fetchSandyNta, fetchDepNta
  } from '$lib/client/mapLayers';

  let queryId = $derived(page.params.queryId ?? '');
  // SvelteKit already decodes route params; decoding again would rewrite
  // a question that contains a literal "%20" or similar.
  let queryText = $derived(queryId);
  const run = new RunState();
  // The tab names the place first, so several briefings can be told apart.
  let title = $derived(
    queryText
      ? `${queryText.length > 60 ? `${queryText.slice(0, 59).trimEnd()}…` : queryText}, ${hazardLabel(run.plan).toLowerCase()}, Riprap`
      : 'Riprap: flood and heat briefings'
  );
  const STOPPED_LABEL: Record<string, string> = {
    geocoder: 'stopped: could not resolve the place',
    'all-silent': 'stopped: no evidence found for this place',
    grounding: 'stopped: no written claim passed verification',
  };
  // True once the SSE `deployment` event has fired, i.e. the pebble
  // manifest and deployment chip reflect the routed-to city. An error
  // before that must clear the boot (NYC) scaffold.
  let deploymentResolved = false;
  let runStartedAt: number | null = null;

  // Live-only map layers from /api/layers/*, once the address resolves.
  // Ida marks and 311 points come from `final` instead
  // (RunState.applyFinal), so the map plots what the answer found.
  // A heat run draws no flood layers (MapFigure adds its own overlay).
  $effect(() => {
    if (!run.address || isHeat(run.plan)) return;
    const { lat, lon, source } = run.address;
    if (source === 'nta' && run.ntaCode) {
      fetchSandyNta(run.ntaCode).then((fc) => { run.sandyFc = fc; });
      fetchDepNta(run.ntaCode).then((fc) => { run.depFc = fc; });
    } else {
      fetchSandy(lat, lon).then((fc) => { run.sandyFc = fc; });
      fetchDep(lat, lon).then((fc) => { run.depFc = fc; });
    }
  });
  $effect(() => {
    if (!run.compareAddressA || isHeat(run.plan)) return;
    const { lat, lon } = run.compareAddressA;
    fetchSandy(lat, lon).then((fc) => { run.sandyFcA = fc; });
    fetchDep(lat, lon).then((fc) => { run.depFcA = fc; });
    fetchIdaHwm(lat, lon).then((fc) => { run.idaHwmFcA = fc; });
  });
  $effect(() => {
    if (!run.compareAddressB || isHeat(run.plan)) return;
    const { lat, lon } = run.compareAddressB;
    fetchSandy(lat, lon).then((fc) => { run.sandyFcB = fc; });
    fetchDep(lat, lon).then((fc) => { run.depFcB = fc; });
    fetchIdaHwm(lat, lon).then((fc) => { run.idaHwmFcB = fc; });
  });

  onMount(() => {
    briefingState.reset();
    // Idempotent. cardAdapter reads the store to render BYOD pebbles.
    void pebbleManifest.load();
    if (!queryText) return;
    runStartedAt = Date.now();
    briefingState.phase = 'planning';
    // The header names no hazard until the plan says which briefing this is.
    briefingState.hazard = hazardLabel(null);
    const stream = openAgentStream(queryText, {
      onPlan: (p) => {
        run.plan = p;
        briefingState.hazard = isHeat(p) ? hazardLabel(p) : null;
        briefingState.phase = 'specialists';
      },
      onDeployment: async (d) => {
        // Pivot the header chip and pebble scaffold to the routed-to
        // city. '__none__' means out of coverage.
        const name = d.name && d.name !== '__none__' ? d.name : null;
        await Promise.all([
          deployment.setForQuery(name),
          pebbleManifest.loadForDeployment(name),
        ]);
        deploymentResolved = true;
      },
      onStep: (s) => {
        // Header status pill: the reconcile steps are not sources.
        if (!s.step.startsWith('reconcile')) briefingState.activeStep = s.step;
        run.applyStep(s, queryText);
      },
      onFinal: (f) => run.applyFinal(f),
      onError: (err) => {
        // Any error ends the run without a briefing, unless the briefing
        // already landed.
        if (!run.finalResult) run.errorState = err === NO_BACKEND ? 'no-backend' : 'backend';
        briefingState.markError(err);
        // Failed before the `deployment` event: clear the boot-time NYC
        // scaffold so no NYC ghost rows show under a non-NYC query. The
        // query was never routed, so the chip names no city: it does not
        // say the place is outside the covered cities, which nothing
        // checked. With no backend at all the chip keeps its fallback text.
        if (!deploymentResolved && err !== NO_BACKEND) {
          void pebbleManifest.loadForDeployment(null);
          deployment.clear();
        }
      },
      onDone: () => {
        if (runStartedAt != null) run.runWallSeconds = (Date.now() - runStartedAt) / 1000;
        run.finish();
        // Snapshot for the /print/<queryId> route.
        if (!run.errorState && run.briefing.blocks.length > 0) {
          persistSnapshot(snapshotFromRun(run, queryId, queryText, run.finishedAt ?? undefined));
        }
        // End the header pill on a final state; a stopped run must not
        // keep saying "gathering evidence".
        const stopped = STOPPED_LABEL[run.errorState ?? '']
          ?? (run.notImplemented ? 'not available' : run.refused ? 'refused' : null);
        if (stopped) briefingState.markStopped(stopped);
        else if (!run.errorState) briefingState.markReady();
      }
    });
    return () => stream.close();
  });
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content="Riprap: cited flood and heat briefings for New York City places, from public data. Open source, Apache-2.0." />
</svelte:head>

<ResultsView {run} {queryText} />
