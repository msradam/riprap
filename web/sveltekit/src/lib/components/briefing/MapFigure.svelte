<script lang="ts">
  import LazyMap from '$lib/components/map/LazyMap.svelte';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import { AREA_BOUNDARY_LEGEND, type RunState } from '$lib/client/runState.svelte';

  /** The single-place map as a figure: the frame and its caption, layer
   *  switches labelled in words with counts, and the map points as a
   *  keyboard list. The frame height comes from `--map-h` on an ancestor. */
  interface Props {
    run: RunState;
  }
  let { run }: Props = $props();

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

<div class="map-figure">
  <a class="map-skip" href="#after-map">Skip the map</a>
  <figure class="map-figure-fig">
    <div class="map-figure-frame">
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
    <figcaption>
      Figure 1. The place and the mapped evidence around it.{#if run.areaBoundary}{` The outline is the ${AREA_BOUNDARY_LEGEND.label}.`}{/if}
      Everything on the map is also listed in the briefing and its sources.
    </figcaption>
  </figure>
  {#if shown.length}
    <fieldset class="map-layers">
      <legend>Map layers</legend>
      {#each shown as l (l.key)}
        <label>
          <!-- A new object, not a mutation: RipMap tracks activeLayers by identity. -->
          <input
            type="checkbox"
            checked={active[l.key]}
            onchange={() => (active = { ...active, [l.key]: !active[l.key] })}
          />
          <span class="map-layer-mark" style:color="var(--tier-{l.key})" aria-hidden="true"><TierGlyph tier={l.key} size={11} /></span>
          {l.label}, <span class="data">{run.mapFeatureCounts[l.key]}</span>
        </label>
      {/each}
    </fieldset>
  {/if}
  {#if run.address && run.mapPoints.length}
    <details class="map-points">
      <summary>Map points as a list ({run.mapPoints.length})</summary>
      <ul class="map-points-list">
        {#each run.mapPoints as row (row.id)}
          <li>
            <button
              type="button"
              class={['map-point', selectedPoint === row.id && 'is-selected']}
              aria-pressed={selectedPoint === row.id}
              onclick={() => (selectedPoint = row.id)}
            >
              <span class="map-point-name">{row.name}</span>
              <span class="map-point-meta">{row.distance}; scenarios: {row.scenarios}</span>
            </button>
          </li>
        {/each}
      </ul>
    </details>
  {/if}
  <!-- tabindex: the skip link's target takes focus, so the next Tab
       continues after the map. -->
  <div id="after-map" tabindex="-1"></div>
</div>

<style>
  .map-figure {
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink);
  }
  .map-skip {
    position: absolute;
    left: -9999px;
  }
  .map-skip:focus {
    position: static;
    display: inline-block;
    margin-bottom: 8px;
  }
  .map-figure-fig {
    margin: 0;
  }
  .map-figure-frame :global(.map-frame) {
    height: var(--map-h, 360px);
    aspect-ratio: auto;
  }
  figcaption {
    margin: 8px 0 0;
    max-width: 54ch;
    color: var(--ink-secondary);
  }
  .map-layers {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 20px;
    margin: 8px 0 0;
    padding: 0;
    border: 0;
  }
  .map-layers legend {
    float: left;
    margin-right: 4px;
    padding: 0;
    color: var(--ink-secondary);
  }
  .map-layers label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 24px;
    cursor: pointer;
  }
  .map-layers input {
    width: 18px;
    height: 18px;
    margin: 0;
    accent-color: var(--ink);
  }
  .map-layer-mark {
    display: inline-flex;
  }
  .map-points {
    margin-top: 8px;
  }
  .map-points summary {
    min-height: 24px;
    cursor: pointer;
    font-weight: 600;
  }
  .map-points-list {
    list-style: none;
    margin: 4px 0 0;
    padding: 0;
    max-height: 30vh;
    overflow-y: auto;
  }
  .map-point {
    display: flex;
    flex-wrap: wrap;
    gap: 0 12px;
    width: 100%;
    min-height: 32px;
    padding: 4px 8px;
    border: 0;
    background: none;
    font: inherit;
    text-align: left;
    color: var(--ink);
    cursor: pointer;
  }
  .map-point:hover,
  .map-point.is-selected {
    background: var(--paper-deep);
  }
  .map-point.is-selected .map-point-name {
    font-weight: 600;
  }
  .map-point:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: -3px;
  }
  .map-point-meta {
    color: var(--ink-secondary);
  }
  #after-map:focus-visible {
    outline: none;
  }
</style>
