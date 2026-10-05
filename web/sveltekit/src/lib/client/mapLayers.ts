/**
 * Fetch Riprap GeoJSON layers from FastAPI for a queried address.
 *
 * The legacy custom-element bundle (web/static/agent.js) wires the same
 * endpoints — keep these in sync. Failures are swallowed because the map
 * is supplementary; the briefing is the deliverable.
 */
import type { FeatureCollection } from 'geojson';
import { asset } from '$app/paths';

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };

async function fetchFc(url: string): Promise<FeatureCollection> {
  try {
    const r = await fetch(url);
    if (!r.ok) return EMPTY;
    const j = (await r.json()) as FeatureCollection;
    if (!j || j.type !== 'FeatureCollection') return EMPTY;
    return j;
  } catch {
    return EMPTY;
  }
}

export async function fetchSandy(lat: number, lon: number, r = 1500): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/sandy?lat=${lat}&lon=${lon}&r=${r}`);
}

export async function fetchDep(lat: number, lon: number, r = 1500): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/dep_extreme_2080?lat=${lat}&lon=${lon}&r=${r}`);
}

/**
 * Neighborhood / development_check intents emit `nta_resolve` instead of
 * `geocode`. The matching layer endpoints clip to the NTA polygon's bbox
 * — same FeatureCollection contract as the address-mode endpoints.
 */
export async function fetchSandyNta(code: string): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/sandy_clipped?code=${encodeURIComponent(code)}`);
}

export async function fetchDepNta(
  code: string,
  scenario: 'dep_extreme_2080' | 'dep_moderate_2050' | 'dep_moderate_current' = 'dep_extreme_2080'
): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/dep_clipped?code=${encodeURIComponent(code)}&scenario=${scenario}`);
}

/**
 * USGS Hurricane Ida 2021 high-water marks within radius_m of the queried
 * address. Returns Points with site_description, elev_ft,
 * height_above_gnd_ft, hwm_quality, waterbody, distance_m properties.
 * Empirical tier — surveyed ground-truth water marks.
 */
export async function fetchIdaHwm(lat: number, lon: number, r = 1500): Promise<FeatureCollection> {
  return fetchFc(`/api/layers/ida_hwm?lat=${lat}&lon=${lon}&r=${r}`);
}

/** The heat briefing's map overlay (static/heat/surface.json): one
 *  citywide image of mean summer surface temperature against the city's
 *  land average, its corners for a MapLibre image source, and its colour
 *  stops in degrees F. */
export interface HeatSurface {
  /** URL of the image. */
  image: string;
  coordinates: [[number, number], [number, number], [number, number], [number, number]];
  stops_f: { diff_f: number; rgb: [number, number, number] }[];
  n_images: number;
  first: string;
  last: string;
}

/** Null when the overlay cannot be read; the map then shows the place alone. */
export async function fetchHeatSurface(): Promise<HeatSurface | null> {
  // asset() puts the static file under the base path (BASE_PATH builds).
  const url = asset('/heat/surface.json');
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    const j = (await r.json()) as HeatSurface;
    // `image` is a file name in the same folder as the JSON.
    return { ...j, image: url.replace(/[^/]*$/, j.image) };
  } catch {
    return null;
  }
}
