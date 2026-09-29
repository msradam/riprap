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

  const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
  /** What is plotted, in counts from the data. */
  let plotted = $derived.by(() => {
    const n = (fc: typeof run.idaHwmFc) => fc?.features.length ?? 0;
    const measured = [
      n(run.idaHwmFc) && `${count(n(run.idaHwmFc), 'Ida high-water mark', 'Ida high-water marks')} (amber)`,
      n(run.floodnetFc) && `${count(n(run.floodnetFc), 'FloodNet sensor', 'FloodNet sensors')} (blue)`
    ].filter(Boolean);
    const out = measured.length ? [`${measured.join(' and ')}, measured`] : [];
    const p = n(run.proxyFc);
    if (p) {
      const total = (run.finalResult as { nyc311?: { n?: unknown } } | null)?.nyc311?.n;
      const of = typeof total === 'number' && total > p ? `${p} of the ${total}` : `${p}`;
      out.push(`${of} ${of === '1' ? 'complaint' : 'complaints'} to 311 (hollow rings, proxy)`);
    }
    const a = n(run.registerPointsFc);
    if (a) out.push(count(a, 'public asset from the register', 'public assets from the register'));
    return out;
  });
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
        floodnet={run.floodnetFc}
        radii={run.radii}
        registerPoints={run.registerPointsFc}
        terramindLulc={run.terramindLulcFc}
        terramindBuildings={run.terramindBuildingsFc}
        areaBoundary={run.areaBoundary}
        {selectedPoint}
        onSelectPoint={(pid) => (selectedPoint = pid)}
      />
    </div>
    <figcaption>
      Figure 1. {plotted.length ? `Plotted: ${plotted.join('; ')}.` : 'The place.'}{#if run.areaBoundary}{` The outline is the ${AREA_BOUNDARY_LEGEND.label}.`}{/if}{#if run.radii.length}{` Search radii (rings): ${run.radii.map((r) => `${r.label} ${r.radius_m} m`).join(', ')}.`}{/if}
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
          <!-- One flex item, so the count shares the label's baseline. -->
          <span>{l.label}, <span class="data">{run.mapFeatureCounts[l.key]}</span></span>
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
              <span class="map-point-meta">{row.meta}</span>
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
  /* 64ch of Small is about 75 characters (the Measure Rule). */
  figcaption {
    margin: 8px 0 0;
    max-width: 64ch;
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
