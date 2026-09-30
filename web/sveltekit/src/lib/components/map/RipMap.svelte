<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  // Loaded with this component (see LazyMap), not in the global sheet.
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { Map as MapLibreMap, GeoJSONSource, Popup as PopupT } from 'maplibre-gl';
  import { POSITRON_NO_LABELS } from './baseStyle';
  import { registerSynStripe } from './synStripe';
  import { MapboxOverlay } from '@deck.gl/mapbox';
  import { GeoJsonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
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
    /** USGS Ida 2021 high-water mark points. Empirical tier; amber fill.
     *  Controlled by EMP master toggle. */
    idaHwm?: GeoJSON.FeatureCollection;
    /** FloodNet street sensors. Empirical tier; solid tier-blue fill. */
    floodnet?: GeoJSON.FeatureCollection;
    /** Search radii around the address, drawn as labelled hairline rings
     *  and hidden with their tier's layer. */
    radii?: { label: string; radius_m: number; tier: 'empirical' | 'proxy' }[];
    activeLayers?: { empirical: boolean; modeled: boolean; synthetic: boolean; proxy: boolean };
    /** Neighbourhood or district outline. When set, the map fits to it
     *  and hides the centroid pin, which is not an address. */
    areaBoundary?: GeoJSON.Polygon | GeoJSON.MultiPolygon;
    /** `pid` of the selected register point; the list below the map and
     *  a click on the map both set it through `onSelectPoint`. */
    selectedPoint?: string | null;
    onSelectPoint?: (pid: string | null) => void;
  }

  let {
    address,
    sandyEmpirical,
    depModeled,
    syntheticPrior,
    proxy311,
    registerPoints,
    idaHwm,
    floodnet,
    radii = [],
    activeLayers = { empirical: true, modeled: true, synthetic: true, proxy: true },
    areaBoundary,
    selectedPoint = null,
    onSelectPoint,
  }: Props = $props();

  let container: HTMLDivElement | null = $state(null);
  let map: MapLibreMap | null = null;
  let overlay: MapboxOverlay | null = null;
  let ready = $state(false);

  const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };

  function boundaryFc(): GeoJSON.FeatureCollection {
    return areaBoundary
      ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: areaBoundary, properties: {} }] }
      : EMPTY;
  }

  /** [[west, south], [east, north]] of a 2D Polygon or MultiPolygon. */
  function boundsOf(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): [[number, number], [number, number]] {
    const xy = (g.coordinates as unknown[]).flat(Infinity) as number[];
    let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity];
    for (let i = 0; i + 1 < xy.length; i += 2) {
      w = Math.min(w, xy[i]); e = Math.max(e, xy[i]);
      s = Math.min(s, xy[i + 1]); n = Math.max(n, xy[i + 1]);
    }
    return [[w, s], [e, n]];
  }

  let PopupCtor: typeof PopupT | null = null;
  let popup: PopupT | null = null;
  /** pid of the register point whose popup is open. */
  let shownPoint: string | null = null;

  const esc = (v: unknown) =>
    String(v).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

  function registerPopupHtml(p: Record<string, unknown>): string {
    // Evidence points (Ida marks, FloodNet, 311) carry the list row's words.
    if (p.detail != null) {
      return `
          <div style="font-family: 'Sofia Sans', system-ui; font-size: 12px; max-width: 240px;">
            <div style="font-weight: 600; color: #0F172A;">${esc(p.name ?? '?')}</div>
            <div style="color: #334155; font-size: 12px; margin-top: 2px;">${esc(p.detail)}</div>
          </div>`;
    }
    const name = esc(p.name ?? p.site_description ?? '?');
    const kind = esc(p.kind ?? '?');
    const inside = p.inside_sandy_2012 === true || p.inside_sandy_2012 === 'true';
    const docId = esc(p.doc_id ?? '');
    return `
          <div style="font-family: 'Sofia Sans', system-ui; font-size: 12px;">
            <div style="font-weight: 600; color: #0F172A;">${name}</div>
            <div style="color: #475569; font-size: 12px; margin-top: 2px;">${kind}</div>
            <div style="margin-top: 6px;">
              <span style="font-family: 'Overpass Mono', monospace; font-size: 12px; color: ${inside ? '#0B5394' : '#6B6B6B'};">
                inside_sandy_2012=${inside}
              </span>
            </div>
            ${docId ? `<div style="margin-top: 4px; font-family: 'Overpass Mono', monospace; font-size: 12px; color: #005EA2;">[${docId}]</div>` : ''}
          </div>`;
  }

  /** Open the register point's popup, replacing any open one. Closing it
   *  (button, map click, Escape) clears the selection. */
  function showRegisterPoint(f: GeoJSON.Feature) {
    if (!map || !PopupCtor) return;
    const p = (f.properties ?? {}) as Record<string, unknown>;
    const coords = (f.geometry as GeoJSON.Point).coordinates as [number, number];
    // Keep focus where the user is (e.g. a list row); the popup repeats that row's information.
    const next = new PopupCtor({ closeButton: true, offset: 12, focusAfterOpen: false }).setLngLat(coords).setHTML(registerPopupHtml(p));
    const prev = popup;
    popup = next;
    shownPoint = String(p.pid ?? '');
    prev?.remove();
    next.on('close', () => {
      if (popup !== next) return;
      popup = null;
      shownPoint = null;
      onSelectPoint?.(null);
    });
    next.addTo(map);
  }

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
  type Radius = { label: string; radius_m: number; tier: 'empirical' | 'proxy' };
  const shownRadii = () => radii.filter((r) => activeLayers[r.tier]);
  const getPosition = (f: GeoJSON.Feature) => (f.geometry as GeoJSON.Point).coordinates as [number, number];

  /** A click on an evidence point opens its popup and selects its list row. */
  function pickPoint({ object }: { object?: GeoJSON.Feature }) {
    if (!object) return;
    showRegisterPoint(object);
    onSelectPoint?.(shownPoint || null);
  }

  /** Every plotted point, for list selection and the initial view. */
  const pointSets = () => [registerPoints, idaHwm, floodnet, proxy311];

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
        getPosition,
        getFillColor: tokenColor('--riprap-amber-800', 235),
        getLineColor: tokenColor('--riprap-white'),
        lineWidthMinPixels: 1.5,
        getRadius: (f: GeoJSON.Feature) => {
          const h = Number((f.properties as Record<string, unknown> | null)?.height_above_gnd_ft ?? 0.5);
          return 5 + Math.min(h, 5) * 1.4;
        },
        radiusUnits: 'pixels',
        onClick: pickPoint,
      }),
      new ScatterplotLayer({
        id: 'deck-floodnet',
        data: floodnet?.features ?? [],
        visible: activeLayers.empirical,
        pickable: true,
        stroked: true,
        getPosition,
        getFillColor: tokenColor('--riprap-tier-empirical'),
        getLineColor: tokenColor('--riprap-white'),
        lineWidthMinPixels: 1.5,
        getRadius: 6,
        radiusUnits: 'pixels',
        onClick: pickPoint,
      }),
      // Proxy is hollow, as its tier mark is: a ring per 311 complaint.
      new ScatterplotLayer({
        id: 'deck-proxy-311',
        data: proxy311?.features ?? [],
        visible: activeLayers.proxy,
        pickable: true,
        stroked: true,
        filled: false,
        getPosition,
        getLineColor: tokenColor('--riprap-tier-proxy', 220),
        lineWidthMinPixels: 1.5,
        getRadius: 4,
        radiusUnits: 'pixels',
        onClick: pickPoint,
      }),
      new ScatterplotLayer({
        id: 'deck-radii',
        data: shownRadii(),
        stroked: true,
        filled: false,
        getPosition: () => [address.lon, address.lat],
        getRadius: (r: Radius) => r.radius_m,
        radiusUnits: 'meters',
        getLineColor: tokenColor('--riprap-slate-tertiary', 200),
        lineWidthMinPixels: 1,
      }),
      new TextLayer({
        id: 'deck-radii-labels',
        data: shownRadii(),
        // Just inside the top of each ring (1 degree of latitude is about 111 km).
        getPosition: (r: Radius) => [address.lon, address.lat + r.radius_m / 111_320],
        getText: (r: Radius) => `${r.label}, ${r.radius_m} m`,
        getSize: 12,
        getColor: tokenColor('--riprap-slate-tertiary'),
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'top',
        fontFamily: 'Sofia Sans, system-ui, sans-serif',
        background: true,
        getBackgroundColor: tokenColor('--riprap-paper', 220),
        backgroundPadding: [3, 1],
      }),
    ];
  }

  $effect(() => { setSourceData('syn-prior', syntheticPrior); });
  $effect(() => { setSourceData('register-points', registerPoints); });
  $effect(() => { setSourceData('area-boundary', boundaryFc()); });

  // `ready` is read first so these run once the style has loaded.
  $effect(() => {
    if (!ready || !map) return;
    for (const id of ['queried-halo', 'queried-pin', 'queried-label']) setLayerVisibility(id, !areaBoundary);
    if (!areaBoundary) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    map.fitBounds(boundsOf(areaBoundary), { padding: 24, animate: !reducedMotion });
  });

  // A row in the map point list was chosen: bring the point into view and
  // open the same popup a click on it opens.
  $effect(() => {
    const pid = selectedPoint;
    if (!ready || !map || !pid || pid === shownPoint) return;
    const f = pointSets().flatMap((fc) => fc?.features ?? []).find((x) => x.properties?.pid === pid);
    if (!f) return;
    const center = (f.geometry as GeoJSON.Point).coordinates as [number, number];
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion) map.jumpTo({ center });
    else map.easeTo({ center });
    showRegisterPoint(f);
  });

  $effect(() => {
    setLayerVisibility('tier-synthetic-fill', activeLayers.synthetic);
    setLayerVisibility('tier-synthetic-line', activeLayers.synthetic);
    setLayerVisibility('area-boundary-fill', activeLayers.empirical);
    setLayerVisibility('area-boundary-line', activeLayers.empirical);
  });

  // Sandy / DEP / Ida HWM / 311 now live entirely in deck.gl — rebuild
  // and hand the overlay a fresh layer array whenever their data or
  // visibility changes. deck.gl diffs by layer `id` internally, so this
  // is cheap even though it reconstructs the array each time.
  $effect(() => {
    void sandyEmpirical; void depModeled; void idaHwm; void floodnet; void proxy311; void radii; void activeLayers;
    if (!overlay || !ready) return;
    overlay.setProps({ layers: buildDeckLayers() });
  });

  // The first view holds the address and the plotted evidence points.
  $effect(() => {
    if (!map || !ready || areaBoundary) return;
    const pts: [number, number][] = [[address.lon, address.lat],
      ...[idaHwm, floodnet, proxy311].flatMap((fc) => (fc?.features ?? []).map(getPosition))];
    const animate = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (pts.length === 1) {
      if (animate) map.flyTo({ center: pts[0], zoom: 15, essential: true });
      else map.jumpTo({ center: pts[0], zoom: 15 });
      return;
    }
    const xs = pts.map((p) => p[0]); const ys = pts.map((p) => p[1]);
    map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]],
      { padding: 48, maxZoom: 16, animate });
  });

  onMount(async () => {
    if (!container) return;
    const maplibre = await import('maplibre-gl');
    PopupCtor = maplibre.Popup;
    map = new maplibre.Map({
      container,
      style: POSITRON_NO_LABELS,
      center: [address.lon, address.lat],
      zoom: 15,
      attributionControl: { compact: true }
    });

    map.addControl(new maplibre.NavigationControl({ visualizePitch: false }), 'top-right');
    map.addControl(new maplibre.ScaleControl({ maxWidth: 100, unit: 'imperial' }), 'bottom-left');
    // On narrow screens the attribution starts folded into its (i)
    // button, so it does not cover the 300px map. MapLibre opens a compact
    // attribution once when its text first arrives, so fold it after the
    // first full render; the button still opens it.
    if (window.matchMedia('(max-width: 1099px)').matches) {
      map.once('idle', () => {
        container?.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show');
      });
    }

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
      map.addSource('area-boundary', { type: 'geojson', data: boundaryFc() });
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

      // proxy 311 complaints: deck.gl hollow rings now (buildDeckLayers).

      // Neighbourhood / district outline (NYC DCP 2020 NTAs), drawn in
      // the queried-address blue because it stands in for that pin.
      map.addLayer({
        id: 'area-boundary-fill', type: 'fill', source: 'area-boundary',
        paint: { 'fill-color': '#005EA2', 'fill-opacity': 0.05 }
      });
      map.addLayer({
        id: 'area-boundary-line', type: 'line', source: 'area-boundary',
        paint: { 'line-color': '#005EA2', 'line-width': 2, 'line-opacity': 0.9 }
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
        showRegisterPoint(f);
        onSelectPoint?.(shownPoint);
      });

      // queried-address pin: federal-blue halo + dot, dominant
      map.addLayer({
        id: 'queried-halo', type: 'circle', source: 'queried-address',
        paint: {
          'circle-color': 'rgba(0, 94, 162, 0.20)', // Federal Blue halo (was an off-palette orange)
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

<div class="map-frame">
  <div
    bind:this={container}
    role="application"
    aria-label="Flood-exposure map for {address.label}"
    class="rip-map-container"
  ></div>
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
  }
  /* MapLibre's own focus is a cyan (#0096ff) glow and none at all on the
     canvas; both take the app's focus token instead. */
  /* !important: MapLibre sets `outline: none` inline on the canvas. */
  .map-frame :global(.maplibregl-canvas:focus-visible) {
    outline: 3px solid var(--riprap-focus) !important;
    outline-offset: -3px;
  }
  /* The attribution toggle had no hover; match MapLibre's other buttons. */
  .map-frame :global(.maplibregl-ctrl-attrib-button:hover) {
    background-color: rgb(0 0 0 / 5%);
  }
  .map-frame :global(.maplibregl-ctrl-group button:focus),
  .map-frame :global(.maplibregl-ctrl-attrib-button:focus) {
    box-shadow: none;
  }
  .map-frame :global(.maplibregl-ctrl-group button:focus-visible),
  .map-frame :global(.maplibregl-ctrl-attrib-button:focus-visible) {
    position: relative;
    z-index: 1;
    box-shadow: 0 0 0 3px var(--riprap-focus);
  }
  /* Twelve Pixel Floor: MapLibre's scale and attribution text in the
     data face at 13px. */
  .map-frame :global(.maplibregl-ctrl-scale),
  .map-frame :global(.maplibregl-ctrl-attrib) {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 400;
  }
  /* An opaque card so the scale and attribution text keep AA contrast
     over any tile; attribution links in Federal Blue. The inner text box
     carries the card too: on a narrow map it overlaps the scale bar, and
     axe cannot resolve a background it has to look through. */
  .map-frame :global(.maplibregl-ctrl-scale),
  .map-frame :global(.maplibregl-ctrl-attrib),
  .map-frame :global(.maplibregl-ctrl-attrib-inner) {
    background-color: var(--riprap-surface-card);
    color: var(--ink);
  }
  .map-frame :global(.maplibregl-ctrl-attrib a) {
    color: var(--riprap-text-link);
  }
  /* The open attribution wraps short of the scale bar (100px at most,
     from the left edge) instead of sliding under it. */
  .map-frame :global(.maplibregl-ctrl-bottom-right) {
    max-width: calc(100% - 132px);
  }
</style>
