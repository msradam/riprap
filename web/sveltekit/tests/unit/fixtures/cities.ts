/**
 * Per-city test fixtures — captures the shape /api/pebbles +
 * /api/deployment + /api/agent return for each shipped deployment.
 *
 * Fixtures are HAND-MAINTAINED, not generated. The reason: tests using
 * them assert exact strings ("Chicago", "Reads what Chicago's ground
 * remembers about flooding…") and we want a deliberate edit when those strings
 * drift, not silent regeneration from a live server. If a backend
 * change makes a fixture stale, the test FAILS — that's the contract.
 *
 * Coverage: NYC, Chicago, Seattle, plus an out-of-coverage
 * "elsewhere" fixture for Albuquerque to assert the neutral chip path.
 */
import type {
  PebbleManifest, PebbleManifestResponse, PebbleStone,
} from '$lib/stores/pebbleManifest.svelte';
import type { Deployment } from '$lib/stores/deployment.svelte';
import type { FinalResult } from '$lib/client/agentStream';

export type CityFixture = {
  /** Short directory name — matches deployments/<key>/ on disk. */
  key: string;
  /** /api/deployment response. */
  deployment: Deployment;
  /** /api/pebbles response. */
  manifest: PebbleManifestResponse;
  /** /api/agent response (trimmed to the fields the UI consumes). */
  agent: Partial<FinalResult> & Record<string, unknown>;
  /** Expected geocode result for the city's anchor address. */
  geocode: { address: string; lat: number; lon: number };
};

const STONES: PebbleStone[] = [
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

function pebble(
  id: string, stone: PebbleManifest['stone'],
  opts: Partial<PebbleManifest> & { map_layer?: boolean; title?: string } = {},
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
      map_layer: opts.map_layer ?? opts.display?.map_layer ?? false,
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

function deploymentStones(cityDescriptions: Record<PebbleManifest['stone'], string>): PebbleStone[] {
  return STONES.map((s) => ({ ...s, description: cityDescriptions[s.id] }));
}

// ─────────────────────────────────────────────────────────── NYC
export const NYC: CityFixture = {
  key: 'nyc',
  deployment: { name: 'nyc', city: 'NYC', hazard: 'Flood-exposure briefing' },
  geocode: { address: '189 ATLANTIC AVENUE, Brooklyn, NY, USA',
             lat: 40.690135, lon: -73.993242 },
  manifest: {
    stones: deploymentStones({
      cornerstone: "Reads what NYC's ground remembers about flooding.",
      touchstone:  "Watches the current state of the city's flood signals and EO.",
      keystone:    "Counts the public assets and built fabric exposed to the hazards.",
      lodestone:   "Projects what's coming — alerts, surge, and recurrence forecasts.",
      capstone:    "Writes the cited briefing, with or without an LLM.",
    }),
    pebbles: [
      pebble('sandy',                'cornerstone', { map_layer: true,  title: 'NYC Sandy Inundation Zone (2012 empirical extent)' }),
      pebble('ida_hwm',              'cornerstone', { map_layer: true,  title: 'Hurricane Ida 2021 — USGS high-water marks' }),
      pebble('microtopo',            'cornerstone', { tier: 'proxy' }),
      pebble('dep_extreme_2080',     'cornerstone', { map_layer: true,  tier: 'modeled' }),
      pebble('dep_moderate_2050',    'cornerstone', { map_layer: true,  tier: 'modeled' }),
      pebble('dep_moderate_current', 'cornerstone', { map_layer: true,  tier: 'modeled' }),
      pebble('floodnet',             'touchstone',  { map_layer: true,  tier: 'proxy' }),
      pebble('nyc311',               'touchstone',  { map_layer: true,  tier: 'proxy' }),
      pebble('nws_obs',              'touchstone'),
      pebble('noaa_tides',           'touchstone'),
      pebble('nws_alerts',           'lodestone',   { tier: 'modeled' }),
      pebble('nws_water_forecast',   'lodestone',   { tier: 'modeled' }),
      pebble('npcc4_slr',            'lodestone',   { tier: 'modeled' }),
      pebble('mta_entrances',        'keystone',    { map_layer: true,  title: 'MTA subway entrances exposed nearby' }),
      pebble('nycha_developments',   'keystone',    { map_layer: true,  title: 'NYCHA developments exposed nearby' }),
      pebble('doe_schools',          'keystone',    { map_layer: true,  title: 'NYC DOE schools exposed nearby' }),
      pebble('doh_hospitals',        'keystone',    { map_layer: true,  title: 'NYC DOH hospitals exposed nearby' }),
    ],
  },
  agent: {
    intent: 'single_address',
    paragraph: 'Templated reconciliation paragraph for NYC.',
    geocode: { address: '189 ATLANTIC AVENUE, Brooklyn, NY, USA',
               lat: 40.690135, lon: -73.993242, borough: 'Brooklyn' },
    lat: 40.690135,
    lon: -73.993242,
    deployment: 'nyc',
    sandy: false,
    ida_hwm: { n_within_radius: 0 },
    dep_extreme_2080: { depth_label: 'outside', depth_class: 0 },
    dep_moderate_2050: { depth_label: 'outside', depth_class: 0 },
    dep_moderate_current: { depth_label: 'outside', depth_class: 0 },
    microtopo: { aoi_max_m: 4.2, basin_relief_m: 0.9 },
    floodnet: { n_sensors: 2, n_flood_events_3y: 7 },
    nyc311: { n: 29 },
    nws_obs: { station_id: 'KJFK', precip_last_hour_mm: 0 },
    noaa_tides: { station_id: '8518750', station_name: 'The Battery, NY',
                  observed_ft_mllw: 4.5, distance_km: 0.8 },
    nws_alerts: { n_active: 0, alerts: [] },
    nws_water_forecast: { gauge_id: 'BATN6', gauge_name: 'The Battery', distance_km: 0.8,
                          forecast_peak_ft_mllw: 5.9, flood_category: null },
    npcc4_slr: { '2050': 12, '2100': 24, available: true },
    mta_entrances: { n_ada_accessible: 1 },
    nycha_developments: { n_developments: 0 },
    doe_schools: { n_schools: 0 },
    doh_hospitals: { n_hospitals: 0 },
    citations: [],
    grounding: { tier: 'no_llm', claims: [], dropped_claims: [] },
  },
};

// ─────────────────────────────────────────────────────────── Chicago
export const CHICAGO: CityFixture = {
  key: 'chicago',
  deployment: { name: 'chicago', city: 'Chicago', hazard: 'Flood-exposure briefing' },
  geocode: { address: 'Willis Tower, 233, South Wacker Drive, Chicago, IL',
             lat: 41.878738, lon: -87.6359612 },
  manifest: {
    stones: deploymentStones({
      cornerstone: "Reads what Chicago's ground remembers about flooding — FEMA floodplains, lake-level baselines, stormwater modeling.",
      touchstone:  "Watches the current state of the city's flood signals — Chicago 311 flood complaints, Lake Michigan tide gauge, NWS observations.",
      keystone:    "Counts public assets exposed — CHA developments, CPS schools, hospitals — and their accessibility from this address.",
      lodestone:   "Projects what's coming — NWS forecasts, Great Lakes water-level projections, FEMA scenario maps.",
      capstone:    "Writes the cited briefing, with or without an LLM.",
    }),
    pebbles: [
      pebble('chicago_311',               'touchstone', { map_layer: true, tier: 'proxy',
        title: 'Chicago 311 service requests near this address' }),
      pebble('lake_michigan_water_level', 'touchstone', { tier: 'empirical',
        title: 'Lake Michigan water level — NOAA Calumet Harbor' }),
      pebble('nws_obs',                   'touchstone'),
      pebble('nws_alerts',                'lodestone',  { tier: 'modeled' }),
    ],
  },
  agent: {
    intent: 'single_address',
    paragraph: 'Templated reconciliation paragraph for Chicago.',
    geocode: { address: 'Willis Tower, Chicago, IL',
               lat: 41.878738, lon: -87.6359612, borough: 'Loop' },
    lat: 41.878738,
    lon: -87.6359612,
    deployment: 'chicago',
    chicago_311:               { n_records: 200, radius_m: 500 },
    nws_obs:                   { station_id: 'KORD', distance_km: 22.0 },
    lake_michigan_water_level: { station_id: '9087044', distance_km: 18.1 },
    nws_alerts:                { n_active: 0 },
    citations: [],
    grounding: { tier: 'no_llm', claims: [], dropped_claims: [] },
  },
};

// ─────────────────────────────────────────────────────────── Seattle
export const SEATTLE: CityFixture = {
  key: 'seattle',
  deployment: { name: 'seattle', city: 'Seattle', hazard: 'Flood-exposure briefing' },
  geocode: { address: 'Seattle City Hall, 600, 4th Avenue, Seattle, WA',
             lat: 47.6038904, lon: -122.3300986 },
  manifest: {
    stones: deploymentStones({
      cornerstone: "Reads what Seattle remembers about flooding — Puget Sound shoreline, salmon-corridor streams, and Pacific Northwest precipitation.",
      touchstone:  "Watches current flood signals — Seattle CSR (Find It Fix It), NWS Seattle, Puget Sound water levels.",
      keystone:    "Counts public assets exposed — Seattle Public Schools, King County libraries, hospitals.",
      lodestone:   "Projects what's coming — NWS Pacific Northwest forecasts, NOAA Puget Sound projections.",
      capstone:    "Writes the cited briefing, with or without an LLM.",
    }),
    pebbles: [
      pebble('water_level', 'touchstone', { tier: 'empirical',
        title: 'Local water level — NOAA Seattle, WA (station 9447130)' }),
      pebble('nws_obs',     'touchstone'),
      pebble('nws_alerts',  'lodestone',  { tier: 'modeled' }),
    ],
  },
  agent: {
    intent: 'single_address',
    paragraph: 'Templated reconciliation paragraph for Seattle.',
    geocode: { address: 'Seattle City Hall, Seattle, WA',
               lat: 47.6038904, lon: -122.3300986, borough: 'First Hill' },
    lat: 47.6038904,
    lon: -122.3300986,
    deployment: 'seattle',
    water_level: { station_id: '9447130', distance_km: 0.8 },
    nws_obs:     { station_id: 'KBFI', distance_km: 4.5 },
    nws_alerts:  { n_active: 0 },
    citations: [],
    grounding: { tier: 'no_llm', claims: [], dropped_claims: [] },
  },
};

// ─────────────────────────────────────────────────────────── Out-of-coverage
export const ELSEWHERE: CityFixture = {
  key: 'federal',
  deployment: { name: 'federal', city: 'Outside the covered cities: federal sources only',
                hazard: 'Flood-exposure briefing' },
  geocode: { address: '1 Civic Plaza NW, Albuquerque, NM',
             lat: 35.0844, lon: -106.6504 },
  manifest: { stones: deploymentStones({
    cornerstone: '', touchstone: '', keystone: '', lodestone: '', capstone: '',
  }), pebbles: [] },
  agent: {
    intent: 'single_address',
    paragraph: 'No shipped deployment covers this point.',
    geocode: { address: '1 Civic Plaza NW, Albuquerque, NM',
               lat: 35.0844, lon: -106.6504 },
    lat: 35.0844,
    lon: -106.6504,
    deployment: null,
    citations: [],
    grounding: { tier: 'no_llm', claims: [], dropped_claims: [] },
  },
};

export const ALL_CITIES: readonly CityFixture[] = [NYC, CHICAGO, SEATTLE, ELSEWHERE] as const;

/** Strings that, if seen in a non-NYC render, indicate NYC content leakage.
 *  These are the substrings the user has actually screenshotted appearing
 *  in non-NYC renders. */
export const NYC_LEAK_NEEDLES: readonly string[] = [
  // Stone-tagline leak (StoneRegion's `tag` from STONE_META)
  "what NYC's ground remembers",
  // Map-layer-panel leaks (MapLegend's hardcoded NYC layer rows)
  'Sandy Inundation Zone',
  'Ida HWM',
  'MTA subway entrances',
  'NYCHA developments',
  'DOE schools',
  'DOH hospitals',
  'FloodNet sensors',
  'TerraMind',
  // Trust-signal / footer leaks
  'FloodHelpNY',
  'FloodNet NYC',
] as const;
