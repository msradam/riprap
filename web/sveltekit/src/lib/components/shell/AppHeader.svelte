<script lang="ts">
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { briefingState } from '$lib/stores/briefingState.svelte';
  import { deployment } from '$lib/stores/deployment.svelte';
  import { STATIC_SITE } from '$lib/staticSite';
  import { hazardLabel, isHeat } from '$lib/client/agentStream';
  import RipMark from './RipMark.svelte';
  import StatusPill from './StatusPill.svelte';

  interface Props {
    query?: string | null;
    onResetCold?: () => void;
    /** Static snapshot pages (gallery): no /api/* calls. */
    offline?: boolean;
  }
  let { query = null, onResetCold, offline: offlinePage = false }: Props = $props();
  // The public static build has no backend on any page.
  const offline = $derived(offlinePage || STATIC_SITE);

  // Fetch the active-deployment descriptor on mount; cheap, cached
  // by the store, returns hazard + city pulled from stones.yaml.
  $effect(() => {
    if (!offline && !deployment.loaded) {
      void deployment.load();
    }
  });

  // Chip text:
  //   - hazard text (e.g. "Flood-exposure briefing") rendered lowercase
  //     to match the existing chip register
  //   - city rendered as a pill on the right side of the chip
  // Falls back to the hardcoded string while the API call is in flight
  // or if it fails (offline-graceful). A heat briefing names its own
  // hazard: the live route sets it from the plan, and a gallery snapshot
  // carries its plan in the page data.
  const hazardText = $derived.by(() => {
    const entry = page.data?.entry;
    const plan = entry?.final?.plan;
    const own = briefingState.hazard ?? (isHeat(plan) ? hazardLabel(plan) : null);
    // Off a briefing page (the landing, the gallery index) the line names
    // both New York City briefings, not the deployment's flood line.
    if (!own && !entry && !page.params.queryId && (deployment.current?.name ?? 'nyc') === 'nyc') {
      return 'flood and heat briefings';
    }
    return (own ?? deployment.current?.hazard)?.toLowerCase() ?? 'flood-exposure briefing';
  });
  const cityText = $derived(
    deployment.current ? `${deployment.current.city}${deployment.current.experimental ? ' (experimental)' : ''}` : null
  );
</script>

<header class="app-header no-print" data-screen-label="App header">
  <div class="app-header-inner">
    <div class="app-header-left">
      <a href={resolve('/')} class="riprap-wordmark" aria-label="Riprap home"><RipMark size={20} />riprap</a>
      <span class="app-header-sep">/</span>
      <span class="app-header-context">{hazardText}</span>
      {#if cityText}
        <span class="app-header-city-pill"><span class="visually-hidden">Active deployment: </span>{cityText}</span>
      {/if}
    </div>
    <div class="app-header-mid">
      {#if query && !offline}
        <button
          type="button"
          class="app-header-query"
          onclick={onResetCold}
          aria-label="Edit query"
        >
          <span class="app-header-query-icon" aria-hidden="true"></span>
          <span class="app-header-query-text">{query}</span>
          <span class="app-header-query-edit">edit</span>
        </button>
      {/if}
    </div>
    <div class="app-header-right">
      <a class="app-header-link" href={`${resolve('/')}#methodology`}>methodology</a>
      <a class="app-header-link" href="{resolve('/(app)/gallery')}/">gallery</a>
      {#if briefingState.ready && !offline && page.params.queryId}
        <!-- The browser print view, built from the snapshot this run saved. -->
        <a
          class="app-header-link"
          href={resolve('/(app)/print/[queryId]', { queryId: encodeURIComponent(page.params.queryId) })}
        >print</a>
      {/if}
      <StatusPill />
    </div>
  </div>
</header>

<style>
  /* Desktop: the left group keeps its natural width and the query column
     is capped, so a long question shrinks the query button (it truncates)
     instead of wrapping the wordmark and context one word per line. The
     cap leaves the links column room for the print link at 1101px.
     The tablet and phone rows in chrome.css put the query on its own row. */
  @media (min-width: 1101px) {
    .app-header-inner {
      grid-template-columns: minmax(max-content, 1fr) fit-content(min(560px, 40%)) 1fr;
    }
  }
  /* The active deployment, in words after the context. */
  .app-header-city-pill {
    font-weight: 600;
    color: var(--ink);
  }
</style>
