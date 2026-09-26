<script lang="ts">
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import ResultsView from '$lib/components/results/ResultsView.svelte';
  import { RunState } from '$lib/client/runState.svelte';
  import { briefingState, persistSnapshot } from '$lib/stores/briefingState.svelte';
  import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
  import { deployment } from '$lib/stores/deployment.svelte';
  import { openAgentStream } from '$lib/client/agentStream';
  import {
    fetchSandy, fetchDep, fetchPrithviSynthetic, fetchProxyDots,
    fetchIdaHwm, fetchSandyNta, fetchDepNta
  } from '$lib/client/mapLayers';

  let queryId = $derived(page.params.queryId ?? '');
  // SvelteKit already decodes route params; decoding again would rewrite
  // a question that contains a literal "%20" or similar.
  let queryText = $derived(queryId);

  const run = new RunState();
  // True once the SSE `deployment` event has fired, i.e. the pebble
  // manifest and deployment chip reflect the routed-to city. An error
  // before that must clear the boot (NYC) scaffold.
  let deploymentResolved = false;
  let runStartedAt: number | null = null;

  // Live-only map layers from /api/layers/*, once the address resolves.
  $effect(() => {
    if (!run.address) return;
    const { lat, lon, source } = run.address;
    if (source === 'nta' && run.ntaCode) {
      fetchSandyNta(run.ntaCode).then((fc) => { run.sandyFc = fc; });
      fetchDepNta(run.ntaCode).then((fc) => { run.depFc = fc; });
      // No NTA-scope synthetic / proxy endpoint: radius query around the
      // centroid. Tight for Ida polygons, wider for sparse FloodNet dots.
      fetchPrithviSynthetic(lat, lon, 2500).then((fc) => { run.synFc = fc; });
      fetchProxyDots(lat, lon, 3000).then((fc) => { run.proxyFc = fc; });
      fetchIdaHwm(lat, lon, 3000).then((fc) => { run.idaHwmFc = fc; });
    } else {
      fetchSandy(lat, lon).then((fc) => { run.sandyFc = fc; });
      fetchDep(lat, lon).then((fc) => { run.depFc = fc; });
      fetchPrithviSynthetic(lat, lon).then((fc) => { run.synFc = fc; });
      fetchProxyDots(lat, lon).then((fc) => { run.proxyFc = fc; });
      fetchIdaHwm(lat, lon).then((fc) => { run.idaHwmFc = fc; });
    }
  });
  $effect(() => {
    if (!run.compareAddressA) return;
    const { lat, lon } = run.compareAddressA;
    fetchSandy(lat, lon).then((fc) => { run.sandyFcA = fc; });
    fetchDep(lat, lon).then((fc) => { run.depFcA = fc; });
    fetchPrithviSynthetic(lat, lon).then((fc) => { run.synFcA = fc; });
    fetchProxyDots(lat, lon).then((fc) => { run.proxyFcA = fc; });
    fetchIdaHwm(lat, lon).then((fc) => { run.idaHwmFcA = fc; });
  });
  $effect(() => {
    if (!run.compareAddressB) return;
    const { lat, lon } = run.compareAddressB;
    fetchSandy(lat, lon).then((fc) => { run.sandyFcB = fc; });
    fetchDep(lat, lon).then((fc) => { run.depFcB = fc; });
    fetchPrithviSynthetic(lat, lon).then((fc) => { run.synFcB = fc; });
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
        const lower = err.toLowerCase();
        if (lower.includes('connection') || lower.includes('502') || lower.includes('503') ||
            lower.includes('timeout') || lower.includes('routing')) {
          run.errorState = 'backend';
        }
        briefingState.markError(err);
        // Failed before the `deployment` event: clear the boot-time NYC
        // scaffold so no NYC ghost rows show under a non-NYC query.
        if (!deploymentResolved) {
          void pebbleManifest.loadForDeployment(null);
          void deployment.setForQuery(null);
        }
      },
      onDone: () => {
        if (runStartedAt != null) run.runWallSeconds = (Date.now() - runStartedAt) / 1000;
        run.finish();
        const { blocks, citations } = run.briefing;
        // Snapshot for the /print/<queryId> route and PDF export.
        if (!run.errorState && blocks.length > 0) {
          persistSnapshot({
            queryId,
            queryText,
            intent: run.plan?.intent ?? null,
            specialists: run.plan?.specialists?.length ?? 0,
            blocks,
            citations,
            generatedAt: new Date().toISOString(),
          });
        }
        if (!run.errorState) briefingState.markReady();
      }
    });
    return () => stream.close();
  });
</script>

<ResultsView {run} {queryText} />
