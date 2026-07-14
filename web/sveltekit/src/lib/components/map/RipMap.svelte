<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
  import { POSITRON_NO_LABELS } from './baseStyle';
  import { registerSynStripe } from './synStripe';
  import { MapboxOverlay } from '@deck.gl/mapbox';
  import { GeoJsonLayer, ScatterplotLayer } from '@deck.gl/layers';
  import { HeatmapLayer } from '@deck.gl/aggregation-layers';
  import { PathStyleExtension } from '@deck.gl/extensions';

  /** Reads a --riprap-* custom property (possibly a var()-chain of
   *  primitives) off the live DOM and returns it as a deck.gl RGB(A)
   *  color array — deck.gl layers take [r,g,b,a] 0-255, not CSS
   *  strings. Custom properties resolve var() chains at computed-value
   *  time, same as any other property, so one getComputedStyle read is
   *  enough regardless of how many primitive layers the token aliases. */
  function tokenColor(name: string, alpha = 255): [number, number, number, number] {
    const hex = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
    if (!m) return [100, 100, 100, alpha]; // fallback: neutral gray, never invisible
    return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16), alpha];
  }

  interface QueriedAddress {
    label: string;
    lat: number;
    lon: number;
  }

  interface Props {
    address: QueriedAddress;
    /**
     * GeoJSON FeatureCollections per tier-layer.
     * Caller wires these from FastAPI /api/layers/* or static fixtures.
     */
    sandyEmpirical?: GeoJSON.FeatureCollection;
    depModeled?: GeoJSON.FeatureCollection;
    syntheticPrior?: GeoJSON.FeatureCollection;
    proxy311?: GeoJSON.FeatureCollection;
    /** Asset-register pins: subway entrances, schools, hospitals
     *  (Points) plus NYCHA developments (Polygons). Each feature
     *  carries `kind`, `name`, `doc_id`, `inside_sandy_2012`,
     *  optional `pct_inside_sandy` (NYCHA only). Always rendered;
     *  not gated by `activeLayers`. */
    registerPoints?: GeoJSON.FeatureCollection;
    registerPolygons?: GeoJSON.FeatureCollection;
    /** TerraMind-synthesis LULC polygons from the SSE final payload
     *  (terramind.polygons_geojson). Categorical fill by `fill_color`
     *  property; synthetic tier; controlled by the SYN master toggle. */
    terramindLulc?: GeoJSON.FeatureCollection;
    /** TerraMind Buildings LoRA polygons (terramind_buildings.polygons_geojson).
     *  Synthetic tier; purple outline to distinguish from LULC fill. */
    terramindBuildings?: GeoJSON.FeatureCollection;
    /** Prithvi-NYC-Pluvial flood prediction polygons (prithvi_live.polygons_geojson).
     *  Modeled tier; teal fill at low opacity. */
    prithviLive?: GeoJSON.FeatureCollection;
    /** USGS Ida 2021 high-water mark points. Empirical tier; amber fill.
     *  Controlled by EMP master toggle. */
    idaHwm?: GeoJSON.FeatureCollection;
    activeLayers?: { empirical: boolean; modeled: boolean; synthetic: boolean; proxy: boolean };
    /** v0.4.5 §8 — when a Findings card is hovered/focused, its
     *  `mapLayer` key flows in as `linkedKey`. The map root gains
     *  `is-link-{key}` so existing layers can be visually emphasised
     *  via scoped CSS. */
    linkedKey?: string | null;
  }

  let {
    address,
    sandyEmpirical,
    depModeled,
    syntheticPrior,
    proxy311,
    registerPoints,
    registerPolygons,
    terramindLulc,
    terramindBuildings,
    prithviLive,
    idaHwm,
    activeLayers = { empirical: true, modeled: true, synthetic: true, proxy: true },
    linkedKey = null,
  }: Props = $props();

  let container: HTMLDivElement | null = $state(null);
  let map: MapLibreMap | null = null;
  let overlay: MapboxOverlay | null = null;
  let ready = $state(false);

  const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };

  function setSourceData(id: string, fc: GeoJSON.FeatureCollection | undefined) {
    if (!map || !ready) return;
    const src = map.getSource(id) as GeoJSONSource | undefined;
    if (src) src.setData(fc ?? EMPTY);
  }

  function setLayerVisibility(id: string, visible: boolean) {
    if (!map || !ready) return;
    if (!map.getLayer(id)) return;
    map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
  }

  /** docs/design/handoff/CLAUDE-CODE-PROMPT.md Task 7 — Sandy/DEP/Ida
   *  move to deck.gl over the MapLibre basemap via an interleaved
   *  MapboxOverlay, so deck layers sort correctly with basemap labels.
   *  Colors are read live off the --riprap-tier-* tokens (tokenColor
   *  above), never hard-coded, so the map legend and these layers can
   *  never drift from the report body's marks.
   *
   *  Deviation from the handoff's layer table: 311 flood requests are
   *  tagged PROXY here, not empirical — matching this codebase's own
   *  established epistemic taxonomy (tierForDocId: 'nyc311'/'311' ->
   *  'proxy', an indirect indicator, not a direct measurement). The
   *  handoff's table appears to use "empirical" loosely for "point
   *  data" rather than the strict tier; following the app's own tested
   *  taxonomy rather than silently taking on a tier regression. */
  function buildDeckLayers() {
    return [
      new GeoJsonLayer({
        id: 'deck-sandy-empirical',
        data: sandyEmpirical ?? EMPTY,
        visible: activeLayers.empirical,
        stroked: true,
        filled: true,
        getFillColor: tokenColor('--riprap-tier-empirical', 102), // ~40% opacity
        getLineColor: tokenColor('--riprap-tier-empirical'),
        lineWidthMinPixels: 1.5,
      }),
      new GeoJsonLayer({
        id: 'deck-dep-modeled',
        data: depModeled ?? EMPTY,
        visible: activeLayers.modeled,
        stroked: true,
        filled: true,
        getFillColor: tokenColor('--riprap-tier-modeled', 41), // ~16% opacity
        getLineColor: tokenColor('--riprap-tier-modeled'),
        lineWidthMinPixels: 1.5,
        getDashArray: [4, 3],
        dashJustified: true,
        extensions: [new PathStyleExtension({ dash: true })],
      }),
      new ScatterplotLayer({
        id: 'deck-ida-hwm',
        data: idaHwm?.features ?? [],
        visible: activeLayers.empirical,
        pickable: true,
        stroked: true,
        getPosition: (f: GeoJSON.Feature) => {
          const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates;
          return [lon, lat] as [number, number];
        },
        getFillColor: tokenColor('--riprap-amber-800', 235),
        getLineColor: tokenColor('--riprap-white'),
        lineWidthMinPixels: 1.5,
        getRadius: (f: GeoJSON.Feature) => {
          const h = Number((f.properties as Record<string, unknown> | null)?.height_above_gnd_ft ?? 0.5);
          return 5 + Math.min(h, 5) * 1.4;
        },
        radiusUnits: 'pixels',
        onClick: ({ object }: { object?: GeoJSON.Feature }) => {
          if (!object || !map) return;
          const p = (object.properties ?? {}) as Record<string, unknown>;
          const site = String(p.site_description ?? '?');
          const elev = p.elev_ft != null ? `${Number(p.elev_ft).toFixed(1)} ft NAVD88` : '—';
          const height = p.height_above_gnd_ft != null ? `${Number(p.height_above_gnd_ft).toFixed(2)} ft above ground` : '—';
          const html = `
            <div style="font-family: 'Sofia Sans', system-ui; font-size: 12px; max-width: 220px;">
              <div style="font-weight: 600; color: #92400E; font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase;">Ida 2021 HWM · USGS</div>
              <div style="margin-top: 4px; color: #0F172A; font-size: 12px;">${site}</div>
              <div style="margin-top: 6px; font-family: 'Overpass Mono', monospace; font-size: 10.5px; color: #4E5A6E;">elev: ${elev}<br>mark: ${height}</div>
            </div>`;
          import('maplibre-gl').then(({ Popup }) => {
            if (!map) return;
            const coords = (object.geometry as GeoJSON.Point).coordinates as [number, number];
            new Popup({ closeButton: true, offset: 12 }).setLngLat(coords).setHTML(html).addTo(map);
          });
        },
      }),
      new HeatmapLayer({
        id: 'deck-proxy-311',
        data: proxy311?.features ?? [],
        visible: activeLayers.proxy,
        getPosition: (f: GeoJSON.Feature) => {
          const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates;
          return [lon, lat] as [number, number];
        },
        getWeight: (f: GeoJSON.Feature) => Number((f.properties as Record<string, unknown> | null)?.count ?? 1),
        colorRange: [
          [...tokenColor('--riprap-surface-sunken')].slice(0, 3),
          [...tokenColor('--riprap-tier-proxy')].slice(0, 3),
        ] as [number, number, number][],
        radiusPixels: 40,
      }),
    ];
  }

  $effect(() => { setSourceData('syn-prior', syntheticPrior); });
  $effect(() => { setSourceData('register-points', registerPoints); });
  $effect(() => { setSourceData('register-polygons', registerPolygons); });
  $effect(() => { setSourceData('terramind-lulc', terramindLulc); });
  $effect(() => { setSourceData('terramind-buildings', terramindBuildings); });
  $effect(() => { setSourceData('prithvi-live', prithviLive); });

  $effect(() => {
    setLayerVisibility('tier-synthetic-fill', activeLayers.synthetic);
    setLayerVisibility('tier-synthetic-line', activeLayers.synthetic);
    setLayerVisibility('terramind-lulc-fill', activeLayers.synthetic);
    setLayerVisibility('terramind-lulc-line', activeLayers.synthetic);
    setLayerVisibility('terramind-buildings-fill', activeLayers.synthetic);
    setLayerVisibility('terramind-buildings-line', activeLayers.synthetic);
    setLayerVisibility('prithvi-live-fill', activeLayers.modeled);
    setLayerVisibility('prithvi-live-line', activeLayers.modeled);
  });

  // Sandy / DEP / Ida HWM / 311 now live entirely in deck.gl — rebuild
  // and hand the overlay a fresh layer array whenever their data or
  // visibility changes. deck.gl diffs by layer `id` internally, so this
  // is cheap even though it reconstructs the array each time.
  $effect(() => {
    void sandyEmpirical; void depModeled; void idaHwm; void proxy311; void activeLayers;
    if (!overlay || !ready) return;
    overlay.setProps({ layers: buildDeckLayers() });
  });

  $effect(() => {
    if (!map || !ready) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion) {
      map.jumpTo({ center: [address.lon, address.lat], zoom: 15 });
    } else {
      map.flyTo({ center: [address.lon, address.lat], zoom: 15, essential: true });
    }
  });

  onMount(async () => {
    if (!container) return;
    const maplibre = await import('maplibre-gl');
    map = new maplibre.Map({
      container,
      style: POSITRON_NO_LABELS,
      center: [address.lon, address.lat],
      zoom: 15,
      attributionControl: { compact: true }
    });

    map.addControl(new maplibre.NavigationControl({ visualizePitch: false }), 'top-right');
    map.addControl(new maplibre.ScaleControl({ maxWidth: 100, unit: 'imperial' }), 'bottom-left');

    map.on('load', () => {
      if (!map) return;

      // Expose for E2E tests. Harmless in production — just a global
      // ref to the live map instance, which Playwright reads to assert
      // on syn-stripe-45 image registration, layer wiring, etc.
      (window as unknown as { __riprapMap?: typeof map }).__riprapMap = map;

      // v0.4.2 §14 — synthetic-prior fill pattern (SVG source, 2 densities)
      registerSynStripe(map);

      // sources — sandy-empirical / dep-modeled / proxy-311 / ida-hwm
      // moved to deck.gl (see buildDeckLayers above); no MapLibre source
      // needed for them any more.
      const fcEmpty = (): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features: [] });
      map.addSource('syn-prior', { type: 'geojson', data: syntheticPrior ?? fcEmpty() });
      map.addSource('register-points', { type: 'geojson', data: registerPoints ?? fcEmpty() });
      map.addSource('register-polygons', { type: 'geojson', data: registerPolygons ?? fcEmpty() });
      map.addSource('terramind-lulc', { type: 'geojson', data: terramindLulc ?? fcEmpty() });
      map.addSource('terramind-buildings', { type: 'geojson', data: terramindBuildings ?? fcEmpty() });
      map.addSource('prithvi-live', { type: 'geojson', data: prithviLive ?? fcEmpty() });
      map.addSource('queried-address', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [{
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [address.lon, address.lat] },
            properties: { label: address.label }
          }]
        }
      });

      // empirical (Sandy) + modeled (DEP) fill/line: deck.gl now (buildDeckLayers).

      // synthetic fill (pattern) + dashed line
      map.addLayer({
        id: 'tier-synthetic-fill', type: 'fill', source: 'syn-prior',
        paint: { 'fill-pattern': 'syn-stripe-45', 'fill-opacity': 0.65 }
      });
      map.addLayer({
        id: 'tier-synthetic-line', type: 'line', source: 'syn-prior',
        paint: { 'line-color': '#2A6FA8', 'line-width': 1.5, 'line-dasharray': [4, 3] }
      });

      // proxy 311 requests: deck.gl HeatmapLayer now (buildDeckLayers).

      // TerraMind-synthesis LULC categorical fill (synthetic prior tier).
      // Per-feature fill_color property carries class-specific color from
      // LULC_FILL_COLORS in terramind_synthesis.py. Rendered below register
      // pins so asset markers stay dominant. Opacity kept low (0.25) so the
      // Sandy/DEP flood-zone blues read through.
      map.addLayer({
        id: 'terramind-lulc-fill', type: 'fill', source: 'terramind-lulc',
        paint: { 'fill-color': ['get', 'fill_color'], 'fill-opacity': 0.25 }
      });
      map.addLayer({
        id: 'terramind-lulc-line', type: 'line', source: 'terramind-lulc',
        paint: { 'line-color': ['get', 'fill_color'], 'line-width': 0.75, 'line-opacity': 0.45, 'line-dasharray': [3, 2] }
      });

      // TerraMind Buildings LoRA — purple outline, synthetic tier.
      map.addLayer({
        id: 'terramind-buildings-fill', type: 'fill', source: 'terramind-buildings',
        paint: { 'fill-color': '#7C3AED', 'fill-opacity': 0.15 }
      });
      map.addLayer({
        id: 'terramind-buildings-line', type: 'line', source: 'terramind-buildings',
        paint: { 'line-color': '#7C3AED', 'line-width': 1.0, 'line-opacity': 0.6, 'line-dasharray': [2, 2] }
      });

      // Prithvi-NYC-Pluvial flood prediction — teal fill, modeled tier.
      map.addLayer({
        id: 'prithvi-live-fill', type: 'fill', source: 'prithvi-live',
        paint: { 'fill-color': '#0D9488', 'fill-opacity': 0.20 }
      });
      map.addLayer({
        id: 'prithvi-live-line', type: 'line', source: 'prithvi-live',
        paint: { 'line-color': '#0D9488', 'line-width': 1.0, 'line-opacity': 0.55 }
      });

      // Register-asset polygons (NYCHA developments only). Fill graded
      // by pct_inside_sandy_2012 — denser if more of the development is
      // in the 2012 zone. Outline always-on so the boundary is legible.
      map.addLayer({
        id: 'register-polygons-fill', type: 'fill', source: 'register-polygons',
        paint: {
          'fill-color': '#0B5394',
          'fill-opacity': [
            'interpolate', ['linear'],
            ['coalesce', ['get', 'pct_inside_sandy'], 0],
            0, 0.10, 25, 0.20, 50, 0.32, 75, 0.45
          ]
        }
      });
      map.addLayer({
        id: 'register-polygons-line', type: 'line', source: 'register-polygons',
        paint: { 'line-color': '#0B5394', 'line-width': 1.0, 'line-opacity': 0.85 }
      });

      // Ida 2021 HWM points — deck.gl ScatterplotLayer now (buildDeckLayers);
      // click popup lives in that layer's onClick.

      // Register-asset points (subway entrances, schools, hospitals).
      // Color: empirical-blue if inside_sandy_2012, ink-tertiary grey
      // otherwise. Radius by kind (subway 4, school 5, hospital 6) so
      // they're distinguishable at a glance.
      map.addLayer({
        id: 'register-points-circle', type: 'circle', source: 'register-points',
        paint: {
          'circle-color': [
            'case',
            ['==', ['get', 'inside_sandy_2012'], true], '#0B5394',
            '#6B6B6B'
          ],
          'circle-stroke-color': '#F4F6F9',
          'circle-stroke-width': 1.25,
          'circle-radius': [
            'match', ['get', 'kind'],
            'subway', 4,
            'school', 5,
            'hospital', 6,
            'nycha', 7,
            4
          ],
          'circle-opacity': 0.9
        }
      });

      // Hover/click affordance: cursor change.
      map.on('mouseenter', 'register-points-circle', () => {
        if (map) map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'register-points-circle', () => {
        if (map) map.getCanvas().style.cursor = '';
      });
      // Click popup for register-asset auditability — surface name +
      // doc_id so the citation in the briefing can be cross-referenced
      // back to the asset on the map.
      map.on('click', 'register-points-circle', (e) => {
        if (!map || !e.features?.length) return;
        const f = e.features[0];
        const p = (f.properties ?? {}) as Record<string, unknown>;
        const name = String(p.name ?? '?');
        const kind = String(p.kind ?? '?');
        const inside = p.inside_sandy_2012 === true || p.inside_sandy_2012 === 'true';
        const docId = String(p.doc_id ?? '');
        const html = `
          <div style="font-family: 'Sofia Sans', system-ui; font-size: 12px;">
            <div style="font-weight: 600; color: #0F172A;">${name}</div>
            <div style="color: #6B6B6B; font-size: 11px; margin-top: 2px;">${kind}</div>
            <div style="margin-top: 6px;">
              <span style="font-family: 'Overpass Mono', monospace; font-size: 10.5px; color: ${inside ? '#0B5394' : '#6B6B6B'};">
                inside_sandy_2012=${inside}
              </span>
            </div>
            ${docId ? `<div style="margin-top: 4px; font-family: 'Overpass Mono', monospace; font-size: 10.5px; color: #005EA2;">[${docId}]</div>` : ''}
          </div>`;
        const popup = new maplibre.Popup({ closeButton: true, offset: 12 });
        const coords = (f.geometry as GeoJSON.Point).coordinates as [number, number];
        popup.setLngLat(coords).setHTML(html).addTo(map);
      });

      // queried-address pin: federal-blue halo + dot, dominant
      map.addLayer({
        id: 'queried-halo', type: 'circle', source: 'queried-address',
        paint: {
          'circle-color': 'rgba(209, 124, 0, 0.20)',
          'circle-radius': 16
        }
      });
      map.addLayer({
        id: 'queried-pin', type: 'circle', source: 'queried-address',
        paint: {
          'circle-color': '#005EA2',
          'circle-stroke-color': '#F4F6F9',
          'circle-stroke-width': 2,
          'circle-radius': 7
        }
      });
      map.addLayer({
        id: 'queried-label', type: 'symbol', source: 'queried-address',
        layout: {
          'text-field': ['get', 'label'],
          'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold'],
          'text-size': 12,
          'text-offset': [0, -1.6],
          'text-anchor': 'bottom'
        },
        paint: {
          'text-color': '#0F172A',
          'text-halo-color': '#F4F6F9',
          'text-halo-width': 1.5
        }
      });

      // Interleaved deck.gl overlay — sorts with basemap labels rather
      // than always drawing on top of them. Layers start empty; the
      // $effect above fills them in once `ready` flips true below.
      overlay = new MapboxOverlay({ interleaved: true, layers: [] });
      map.addControl(overlay);

      ready = true;
      overlay.setProps({ layers: buildDeckLayers() });
    });
  });

  onDestroy(() => {
    map?.remove();
    map = null;
    overlay = null;
  });
</script>

<div class="map-frame" data-linked={linkedKey ?? ''}>
  <div
    bind:this={container}
    role="application"
    aria-label="Flood-exposure map for {address.label}"
    class="rip-map-container"
  ></div>
  {#if linkedKey}
    <span class="link-badge" aria-hidden="true">linked: {linkedKey}</span>
  {/if}
</div>

<style>
  .rip-map-container {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
  .map-frame {
    aspect-ratio: 8 / 5.6;
    position: relative;
    transition: outline-color 200ms ease;
    outline: 0 solid transparent;
    outline-offset: 0;
  }
  .map-frame[data-linked]:not([data-linked='']) {
    outline: 2px solid var(--accent-graphical);
  }
  .link-badge {
    position: absolute;
    bottom: 8px;
    right: 8px;
    padding: 3px 8px;
    background: var(--ink);
    color: var(--paper);
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: lowercase;
    z-index: 5;
    pointer-events: none;
  }
</style>
