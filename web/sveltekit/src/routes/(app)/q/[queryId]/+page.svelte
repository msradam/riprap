<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import ResultsView from '$lib/components/results/ResultsView.svelte';
  import { RunState } from '$lib/client/runState.svelte';
  import { briefingState, persistSnapshot } from '$lib/stores/briefingState.svelte';
  import { snapshotFromRun } from '$lib/client/briefingModel';
  import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
  import { deployment } from '$lib/stores/deployment.svelte';
  import { openAgentStream, NO_BACKEND } from '$lib/client/agentStream';
  import {
    fetchSandy, fetchDep, fetchProxyDots,
    fetchIdaHwm, fetchSandyNta, fetchDepNta
  } from '$lib/client/mapLayers';

  let queryId = $derived(page.params.queryId ?? '');
  // SvelteKit already decodes route params; decoding again would rewrite
  // a question that contains a literal "%20" or similar.
  let queryText = $derived(queryId);

  const run = new RunState();
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
  // Ida marks, FloodNet sensors and 311 points come from `final` instead
  // (RunState.applyFinal), so the map plots what the answer found.
  $effect(() => {
    if (!run.address) return;
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
    if (!run.compareAddressA) return;
    const { lat, lon } = run.compareAddressA;
    fetchSandy(lat, lon).then((fc) => { run.sandyFcA = fc; });
    fetchDep(lat, lon).then((fc) => { run.depFcA = fc; });
    fetchProxyDots(lat, lon).then((fc) => { run.proxyFcA = fc; });
    fetchIdaHwm(lat, lon).then((fc) => { run.idaHwmFcA = fc; });
  });
  $effect(() => {
    if (!run.compareAddressB) return;
    const { lat, lon } = run.compareAddressB;
    fetchSandy(lat, lon).then((fc) => { run.sandyFcB = fc; });
    fetchDep(lat, lon).then((fc) => { run.depFcB = fc; });
    fetchProxyDots(lat, lon).then((fc) => { run.proxyFcB = fc; });
    fetchIdaHwm(lat, lon).then((fc) => { run.idaHwmFcB = fc; });
  });

  onMount(() => {
    briefingState.reset();
    // Idempotent. cardAdapter reads the store to render BYOD pebbles.
    void pebbleManifest.load();
    if (!queryText) return;
    runStartedAt = Date.now();
    briefingState.phase = 'planning';
    const stream = openAgentStream(queryText, {
      onPlanToken: (d) => (run.planTokens += d),
      onPlan: (p) => {
        run.plan = p;
        briefingState.phase = 'specialists';
        briefingState.totalSpecialists = p.specialists?.length ?? 0;
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
        // Header status pill: reconcile steps do not count as fired
        // specialists.
        if (!s.step.startsWith('reconcile')) {
          briefingState.activeStep = s.step;
          if (s.ok) briefingState.firedCount = briefingState.firedCount + 1;
        }
        run.applyStep(s, queryText);
      },
      onFinal: (f) => run.applyFinal(f),
      onError: (err) => {
        // Any error ends the run without a briefing, unless the briefing
        // already landed.
        if (!run.finalResult) run.errorState = err === NO_BACKEND ? 'no-backend' : 'backend';
        briefingState.markError(err);
        // Failed before the `deployment` event: clear the boot-time NYC
        // scaffold so no NYC ghost rows show under a non-NYC query. With
        // no backend at all the chip keeps its fallback text.
        if (!deploymentResolved && err !== NO_BACKEND) {
          void pebbleManifest.loadForDeployment(null);
          void deployment.setForQuery(null);
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
  <title>Riprap: flood-exposure briefing</title>
  <meta name="description" content="Riprap: cited flood-exposure briefings for New York City places, from public data. Open source, Apache-2.0." />
</svelte:head>

<ResultsView {run} {queryText} />
