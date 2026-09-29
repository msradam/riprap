<script lang="ts">
  import LazyMap from '$lib/components/map/LazyMap.svelte';
  import type { RunState } from '$lib/client/runState.svelte';

  /** ResultsView's single-place map with a plain checkbox legend in place
   *  of MapLegend, then the keyboard list of map points. */
  interface Props {
    run: RunState;
    /** CSS length for the map frame. */
    height?: string;
    class?: string;
  }
  let { run, height = '420px', class: className }: Props = $props();

  type TierKey = 'empirical' | 'modeled' | 'synthetic' | 'proxy';
  const LAYERS: { key: TierKey; label: string }[] = [
    { key: 'empirical', label: 'Measured (empirical)' },
    { key: 'modeled', label: 'Modeled scenarios' },
    { key: 'synthetic', label: 'Synthetic' },
    { key: 'proxy', label: '311 complaints (proxy)' }
  ];

  let active = $state({ empirical: true, modeled: true, synthetic: true, proxy: true });
  /** pid of the register point selected on the map or in its list; a new
   *  run starts with none. */
  let selectedPoint = $derived.by<string | null>(() => (void run, null));
  let shown = $derived(LAYERS.filter((l) => run.mapFeatureCounts[l.key] > 0));
</script>

<div class={['lab-map', className]}>
  <a class="lab-map-skip" href="#lab-after-map">Skip the map</a>
  <div class="lab-map-frame" style:--lab-map-h={height}>
    <LazyMap
      address={run.address}
      activeLayers={active}
      sandyEmpirical={run.sandyFc}
      depModeled={run.depFc}
      syntheticPrior={run.synFc}
      proxy311={run.proxyFc}
      idaHwm={run.idaHwmFc}
      registerPoints={run.registerPointsFc}
      terramindLulc={run.terramindLulcFc}
      terramindBuildings={run.terramindBuildingsFc}
      areaBoundary={run.areaBoundary}
      {selectedPoint}
      onSelectPoint={(pid) => (selectedPoint = pid)}
    />
  </div>
  {#if shown.length}
    <fieldset class="lab-map-layers">
      <legend>Map layers</legend>
      {#each shown as l (l.key)}
        <label>
          <!-- A new object, not a mutation: RipMap tracks activeLayers by identity. -->
          <input
            type="checkbox"
            checked={active[l.key]}
            onchange={() => (active = { ...active, [l.key]: !active[l.key] })}
          />
          {l.label} ({run.mapFeatureCounts[l.key]})
        </label>
      {/each}
    </fieldset>
  {/if}
  {#if run.address && run.mapPoints.length}
    <details class="lab-map-points">
      <summary>Map points as a list ({run.mapPoints.length})</summary>
      <ul>
        {#each run.mapPoints as row (row.id)}
          <li>
            <button
              type="button"
              class={['lab-map-point', selectedPoint === row.id && 'is-selected']}
              aria-pressed={selectedPoint === row.id}
              onclick={() => (selectedPoint = row.id)}
            >
              <span class="lab-map-point-name">{row.name}</span>
              <span class="lab-map-point-meta">{row.distance}; scenarios: {row.scenarios}</span>
            </button>
          </li>
        {/each}
      </ul>
    </details>
  {/if}
  <p class="lab-map-note">Everything shown on the map is also listed in the briefing and its sources.</p>
  <!-- tabindex: the skip link's target takes focus, so the next Tab
       continues after the map. -->
  <div id="lab-after-map" tabindex="-1"></div>
</div>

<style>
  .lab-map-frame :global(.map-frame) {
    height: var(--lab-map-h);
    aspect-ratio: auto;
  }
  .lab-map-point.is-selected {
    font-weight: 600;
  }
  #lab-after-map:focus-visible {
    outline: none;
  }
</style>
