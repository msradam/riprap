/**
 * Test fixtures — small, self-contained API-response shapes for the
 * cardAdapter unit tests. Kept hand-written (not generated from the
 * Python probe JSON) so the test is reproducible without a running
 * server, and so the shape we're asserting against is visibly pinned
 * here rather than buried in an opaque blob.
 *
 * If the backend pebble shapes drift, the corresponding fields here
 * need a deliberate update — that's the point.
 */

import type { PebbleManifest, PebbleStone } from '$lib/stores/pebbleManifest.svelte';

/** The five Stones in display order — identical across deployments. */
export const STONES: PebbleStone[] = [
  { id: 'cornerstone', name: 'Cornerstone', tagline: 'The Hazard Reader',
    description: '', order: 1 },
  { id: 'touchstone',  name: 'Touchstone',  tagline: 'The Live Observer',
    description: '', order: 2 },
  { id: 'keystone',    name: 'Keystone',    tagline: 'The Asset Register',
    description: '', order: 3 },
  { id: 'lodestone',   name: 'Lodestone',   tagline: 'The Projector',
    description: '', order: 4 },
  { id: 'capstone',    name: 'Capstone',    tagline: 'The Synthesiser',
    description: '', order: 5 },
];

/** Generic factory — keeps each fixture row tiny. */
function manifest(
  id: string,
  stone: PebbleManifest['stone'],
  opts: Partial<PebbleManifest> = {},
): PebbleManifest {
  return {
    id,
    type: 'live',
    title: opts.title ?? id,
    stone,
    tier: opts.tier ?? 'empirical',
    display: {
      order: opts.display?.order ?? null,
      kind: opts.display?.kind ?? 'text',
      variant: opts.display?.variant ?? null,
      map_layer: opts.display?.map_layer ?? false,
      icon: opts.display?.icon ?? null,
    },
    narration: { short: null, template: null, ...(opts.narration ?? {}) },
    provenance: {
      source_name: opts.provenance?.source_name ?? id,
      source_url: null, license: null,
      citation: null, doc_id: id, date_modified: null,
    },
    fallback: { on_offline: 'skip', message: null },
  };
}

/** NYC manifest: the point pebbles deployments/nyc ships. */
export const NYC_MANIFEST: PebbleManifest[] = [
  // Cornerstone
  manifest('sandy', 'cornerstone'),
  manifest('ida_hwm', 'cornerstone'),
  manifest('microtopo', 'cornerstone'),
  manifest('dep_extreme_2080', 'cornerstone'),
  manifest('dep_moderate_2050', 'cornerstone'),
  manifest('dep_moderate_current', 'cornerstone'),
  // Touchstone
  manifest('floodnet', 'touchstone'),
  manifest('nyc311', 'touchstone'),
  manifest('nws_obs', 'touchstone'),
  manifest('noaa_tides', 'touchstone'),
  // Lodestone
  manifest('nws_alerts', 'lodestone'),
  manifest('nws_water_forecast', 'lodestone'),
  manifest('npcc4_slr', 'lodestone'),
  // Keystone
  manifest('mta_entrances', 'keystone'),
  manifest('nycha_developments', 'keystone'),
  manifest('doe_schools', 'keystone'),
  manifest('doh_hospitals', 'keystone'),
];

/** Chicago manifest: what /api/pebbles SHOULD return for a Chicago route. */
export const CHICAGO_MANIFEST: PebbleManifest[] = [
  manifest('chicago_311', 'touchstone'),
  manifest('lake_michigan_water_level', 'touchstone'),
  manifest('nws_obs', 'touchstone'),
  manifest('nws_alerts', 'lodestone'),
];

/** Pebble-id sets we assert against. The bug-fix seal: a Chicago
 *  render must contain only Chicago ids and no NYC-only ids. */
export const NYC_ONLY_IDS = new Set([
  'sandy', 'ida_hwm',
  'microtopo', 'floodnet', 'nyc311', 'noaa_tides',
  'mta_entrances', 'nycha_developments', 'doe_schools', 'doh_hospitals',
  'nws_water_forecast', 'npcc4_slr',
  'dep_extreme_2080', 'dep_moderate_2050', 'dep_moderate_current',
]);

/** A trimmed Chicago `/api/agent` response: only the keys cardAdapter reads. */
export const CHICAGO_FINAL = {
  intent: 'single_address',
  paragraph: '',
  geocode: {
    address: 'Willis Tower, 233, South Wacker Drive, Loop, Chicago, Cook County, Illinois, 60606, United States',
    lat: 41.878738, lon: -87.6359612, borough: 'Loop',
  },
  lat: 41.878738,
  lon: -87.6359612,
  deployment: 'chicago',
  // Pebble fan-out values (what reduce wrote)
  chicago_311: { n_records: 3, radius_m: 200, sample: [], top_by_sr_type: [] },
  nws_obs:     { station_id: 'KORD', precip_last_hour_mm: 0, distance_km: 22.0 },
  lake_michigan_water_level: { station_id: '9087044', observed_ft: 579.4, distance_km: 18.1 },
  nws_alerts:  { n_active: 0, alerts: [] },
  citations: [],
  grounding: { tier: 'no_llm', claims: [], dropped_claims: [] },
};

/** A trimmed NYC `/api/agent` response — Coney Island shape (sandy=true). */
export const NYC_FINAL = {
  intent: 'single_address',
  paragraph: '',
  geocode: {
    address: '1208 Surf Avenue, Brooklyn, NY, USA',
    lat: 40.5739, lon: -73.9819, borough: 'Brooklyn',
  },
  lat: 40.5739,
  lon: -73.9819,
  deployment: 'nyc',
  sandy: true,
  ida_hwm: { n_within_radius: 0, max_height_above_gnd_ft: null },
  dep_extreme_2080: { depth_label: 'shallow', depth_class: 1 },
  dep_moderate_2050: { depth_label: 'outside', depth_class: 0 },
  dep_moderate_current: { depth_label: 'outside', depth_class: 0 },
  microtopo: { aoi_max_m: 4.2, aoi_min_m: 0.1, basin_relief_m: 0.9 },
  floodnet: { n_sensors: 2, n_flood_events_3y: 7 },
  nyc311: { n: 12, by_descriptor: {} },
  nws_obs: { station_id: 'KJFK', precip_last_hour_mm: 0 },
  noaa_tides: { station_id: '8518750', observed_ft_mllw: 4.8 },
  nws_alerts: { n_active: 0, alerts: [] },
  mta_entrances: { n_ada_accessible: 1, entrances: [] },
  nycha_developments: { n_developments: 0, developments: [] },
  doe_schools: { n_schools: 0, schools: [] },
  doh_hospitals: { n_hospitals: 0, hospitals: [] },
  citations: [],
  grounding: { tier: 'no_llm', claims: [], dropped_claims: [] },
};
