/**
 * FSM-state → Findings Card[] adapter.
 *
 * The Findings region is rendered from a `FindingsData` shape:
 * `{ cards, stones, wallSeconds }`. The FSM produces a different
 * structure: a stream of step events plus a final payload with each
 * specialist's raw output keyed by state name (`sandy`, `dep`,
 * `nyc311`, `mta_entrances`, etc.).
 *
 * This module bridges the two. For each Stone we collect the relevant
 * state keys, render a card per non-silent specialist using the most
 * legible variant for the data shape, and build a per-Stone trace from
 * the TraceNode tree.
 *
 * Best-effort: a missing specialist drops out (silence over
 * confabulation).
 */
import type {
  Card, CardVariant, FindingsData, ModelLine, StoneKey, StoneMember, StoneTrace
} from '$lib/types/card';
import type { TraceNode, TraceStatus } from '$lib/types/trace';
import { isHeat, type FinalResult, type ModelRow } from '$lib/client/agentStream';
import { pebbleManifest, type PebbleManifest } from '$lib/stores/pebbleManifest.svelte';

/** Reasonable defaults — when the FSM doesn't supply a vintage, fall
 *  back to the Riprap publication date. */
const RIPRAP_VINTAGE = '2026-05';

/** The publisher part of a source name: "NOAA CO-OPS, tide gauge water
 *  level" is "NOAA CO-OPS". Splits at a spaced dash or at the first comma
 *  outside parentheses (titles use a comma now), never at a hyphen. */
export function shortSource(name: string): string {
  const head = name.split(/\s[-–—]\s|—/)[0];
  let depth = 0;
  for (let i = 0; i < head.length; i++) {
    const ch = head[i];
    if (ch === '(') depth++;
    else if (ch === ')') depth = Math.max(0, depth - 1);
    else if (ch === ',' && depth === 0) return head.slice(0, i).trim();
  }
  return head.trim();
}

/** Reader-facing labels for the value fields that scalar cards show.
 *  Each label restates the field as the pebble's own narrative
 *  describes it. A field with no label here is not shown: a snake_case
 *  key tells a reader nothing. */
const FIELD_LABELS: Record<string, string> = {
  // microtopo
  point_elev_m: 'Elevation (m)',
  rel_elev_pct_200m: 'Elevation percentile, 200 m window',
  rel_elev_pct_750m: 'Elevation percentile, 750 m window',
  basin_relief_m: 'Local basin relief (m)',
  aoi_min_m: 'Lowest elevation in the area (m)',
  aoi_max_m: 'Highest elevation in the area (m)',
  resolution_m: 'DEM resolution (m)',
  // No label, so no row, for height above nearest drainage or the wetness
  // index: both rest on synthetic drainage channels on a 30 m grid.
  // fema_nfhl
  effective_year: 'FIRM panel effective year',
  // dcp_floodplain_nta (no parentheses: a closing one reads as a unit)
  n_buildings: 'Buildings in the floodplain',
  n_residential_units: 'Residential units in the floodplain',
  n_residents_2010: 'Residents in the floodplain, 2010 census',
  // nws_water_forecast
  forecast_peak_ft_mllw: 'Forecast peak water level (ft above MLLW)',
  // floodnet
  n_sensors: 'Sensors nearby',
  n_flood_events_3y: 'Verified flood events, up to 3 years',
  n_sensors_with_events: 'Sensors with flood events',
  // nws_obs, noaa_tides, usgs_gauges
  distance_km: 'Distance to station (km)',
  temp_c: 'Temperature (°C)',
  precip_last_hour_mm: 'Precipitation, last hour (mm)',
  precip_last_3h_mm: 'Precipitation, last 3 hours (mm)',
  precip_last_6h_mm: 'Precipitation, last 6 hours (mm)',
  observed_ft: 'Observed water level (ft)',
  residual_ft: 'Difference from predicted tide (ft)',
  stage_ft: 'Stream stage (ft)',
  discharge_cfs: 'Discharge (cfs)',
  n_gauges_in_area: 'Gauges in the area',
  // heat_surface
  mean_diff_f: "Surface against the city's land average (°F)",
  min_diff_f: 'Smallest difference in one image (°F)',
  max_diff_f: 'Largest difference in one image (°F)',
  n_images: 'Clear summer images',
  latest_surface_f: 'Surface in the latest image (°F)',
  latest_city_mean_f: 'City land average in the latest image (°F)',
  // hvi
  hvi: 'Heat Vulnerability Index (of 5)',
  ac_pct: 'Households with air conditioning (%)',
  median_income: 'Median household income ($)',
  // heat_visits
  age_adjusted_rate: 'Age-adjusted rate (per 100,000 a year)',
  citywide_age_adjusted_rate: 'Citywide age-adjusted rate (per 100,000 a year)',
  // city_landcover, landcover (hvi also gives green_pct)
  built_pct: 'Paved or built over (%)',
  green_pct: 'Green cover (%)',
  tree_canopy_pct: 'Tree canopy (%)',
  water_pct: 'Water (%)',
  bare_pct: 'Bare ground (%)',
  // heat_obs. humidity_pct has no label on purpose: the evidence table's
  // figure is the first scalar that is not a temperature, and humidity
  // would stand as the figure of an air temperature row.
  temp_f: 'Air temperature (°F)',
  heat_index_f: 'Heat index (°F)',
  // heat_station
  days_ge_90: 'Days at 90°F or above',
  days_ge_90_last_year: 'Days at 90°F or above, last year',
  normal_days_ge_90: 'Days at 90°F or above, long-term average',
  max_f: 'Highest air temperature (°F)',
  // nws_heat_forecast
  max_high_f: 'Highest forecast high (°F)',
  max_apparent_f: 'Highest forecast apparent temperature (°F)',
  // cool_features
  n_spray_shower_sites: 'Parks or playgrounds with spray showers',
  n_outdoor_pools: 'Outdoor pools',
  n_indoor_pools: 'Indoor pools',
  n_wading_pools: 'Wading pools',
};

/**
 * Format a pebble's `narration.template` against its value dict.
 * Mirrors the backend templated_reconciler's _format_template logic
 * — strict placeholder substitution, returns null when any required
 * field is missing or null so the caller can fall back to
 * narration.short rather than emit a "{field?}" literal.
 *
 * Numbers / booleans are coerced to string; objects raise "missing".
 * Empty / null fields raise "missing" too — without this, a sandy
 * card for an outside address would print "NYC's footprint  this
 * address" with a doubled space where {inside_phrasing} silently
 * resolved to "".
 *
 * OPTIONAL_FIELDS are clauses the backend leaves empty on purpose
 * (sandy's `{edge_note}` is "" or ", about 40 m from the mapped edge
 * ..."); empty or absent (a snapshot saved before the field existed),
 * they render as no text.
 */
const OPTIONAL_FIELDS = new Set(['edge_note']);

function formatTemplate(template: string, value: unknown): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const v = { ...(value as Record<string, unknown>) };
  // As the backend sentence does: a count that hit the fetch limit reads "200+".
  if (v.n_truncated === true && typeof v.n_records === 'number') v.n_records = `${v.n_records}+`;
  let missing = false;
  const out = template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const x = v[key];
    if (x === undefined || x === null || x === '') {
      if (!OPTIONAL_FIELDS.has(key)) missing = true;
      return '';
    }
    return String(x);
  });
  return missing ? null : out.trim();
}

const UNFILLED = /\{\w+\}/;
const TEXT_FIELDS = ['headline', 'body', 'sub'] as const;

/** Drop any card text line that still holds a `{field}` placeholder: an
 *  unfilled template is worse than no line. Every card passes through
 *  here, whichever builder made it. */
export function dropUnfilled(card: Card): Card {
  let out = card;
  for (const k of TEXT_FIELDS) {
    const v = card[k];
    if (typeof v === 'string' && UNFILLED.test(v)) {
      if (out === card) out = { ...card };
      out[k] = undefined;
    }
  }
  return out;
}

/** Map the FSM trace's TraceStatus into the v0.4.5 5-state SpecialistStatus.
 *  Crucial split: a specialist that "returned no data" is `silent_by_design`,
 *  not `errored`. The FSM marks both as `silent` in the trace; we
 *  conservatively classify any successful trace-`silent` as
 *  silent_by_design (the spec voice). Anything that raised in the FSM
 *  becomes `errored`.
 */
function mapStatus(s: TraceStatus): StoneMember['status'] {
  if (s === 'silent') return 'silent_by_design';
  if (s === 'error') return 'errored';
  return 'fired';
}

function flattenTrace(node: TraceNode): TraceNode[] {
  return [node, ...(node.children ?? []).flatMap(flattenTrace)];
}

/** Group leaf specialist nodes by the Stone their pebble belongs to.
 *  Source of truth: pebbleManifest.byId, populated from /api/pebbles at
 *  app load, so every manifest in the active deployment is recognised
 *  by definition. The two Capstone reconciler steps are not pebbles. */
const RECONCILE_STEPS: Record<string, StoneKey> = {
  reconcile_templated: 'capstone',
  reconcile_claims: 'capstone',
};

function stoneForStep(name: string): StoneKey | null {
  const n = name.toLowerCase();
  return pebbleManifest.byId[n]?.stone ?? RECONCILE_STEPS[n] ?? null;
}

/** Project the live trace against the deployment's pebble roster.
 *
 *  v0.4.5 §3: every Stone's expander shows the roster for this run
 *  (`inScope`: the run's hazard and kind of place). Present specialists
 *  keep their live status; absent ones in scope land as
 *  `not_invoked` with their declared fallback message. The roster
 *  source is the active deployment's manifests (pebbleManifest.byStone),
 *  not a frontend-hardcoded list, so adding a city = no TS edits.
 */
function fillRosterFromManifests(
  stone: StoneKey,
  liveByName: Map<string, StoneMember>,
  inScope: (m: PebbleManifest) => boolean,
): StoneMember[] {
  const roster = pebbleManifest.byStone[stone] ?? [];
  const out: StoneMember[] = [];
  const used = new Set<string>();
  for (const p of roster) {
    const live = liveByName.get(p.id);
    if (live) {
      used.add(p.id);
      out.push({
        ...live,
        // Override id/name with the manifest's display strings so
        // provenance row chrome is consistent across deployments.
        id: p.id,
        name: p.title,
        tier: live.tier ?? p.tier ?? null,
      });
    } else if (inScope(p)) {
      // A source of the other briefing, or of the other kind of place,
      // could not have run: it is not listed as "not run".
      out.push({
        id: p.id,
        name: p.title,
        status: 'not_invoked',
        tier: p.tier ?? null,
        note: p.narration?.short ?? undefined,
      });
    }
  }
  // Any live members the manifest doesn't know about (legacy aliases
  // like `reconcile_granite41`) get appended so we never silently drop
  // a trace row.
  for (const [k, m] of liveByName) {
    if (!used.has(k)) out.push(m);
  }
  return out;
}

function buildStoneTraces(root: TraceNode | undefined | null, inScope: (m: PebbleManifest) => boolean): StoneTrace[] {
  const buckets: Record<StoneKey, Map<string, StoneMember>> = {
    cornerstone: new Map(), keystone: new Map(),
    touchstone: new Map(), lodestone: new Map(), capstone: new Map(),
  };
  if (root) {
    for (const node of flattenTrace(root)) {
      const stone = stoneForStep(node.name);
      if (!stone) continue;
      buckets[stone].set(node.name, {
        id: node.id || node.name,
        name: node.name,
        status: mapStatus(node.status),
        tier: node.tier,
        ms: node.ms,
        note: node.note ?? node.error ?? undefined,
      });
    }
  }
  return (Object.keys(buckets) as StoneKey[]).map((key) => ({
    key,
    members: fillRosterFromManifests(key, buckets[key], inScope),
  }));
}

/* ── Per-specialist card builders. Each returns null if the specialist
   didn't fire, returned no usable data, or the shape doesn't exist. ── */

type Final = Record<string, unknown> & FinalResult;

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === 'string' ? v : null;
}

function obj(v: unknown): Record<string, unknown> | null {
  return v && typeof v === 'object' && !Array.isArray(v)
    ? (v as Record<string, unknown>) : null;
}

// buildSandy was a curated builder that hardcoded the NYC-specific
// "Hurricane Sandy 2012 inundation" phrasing in the UI. The
// architecture (location-agnostic pebbles → stones, location-
// specific content from each pebble's manifest) wants this in
// deployments/nyc/manifests/sandy.yaml's narration.template
// instead. The `boolean_zone` shaper wraps the bare bool so the
// template can phrase inside-vs-outside correctly. The templated
// path renders the card.

// ── Type-keyed register card renderer ───────────────────────────
//
// One card per pebble that declares `display.variant: register`, so each
// register is its own evidence row with its own source, citation and date.
//
// Per-pebble item-extraction heuristic: the adapter emits its rows
// under whichever field name fits the asset class (entrances /
// developments / schools / hospitals / items / features). The
// renderer scans known field names; an explicit `items` array
// always wins so future BYOD registers don't need a heuristic.
type RegisterItem = Record<string, unknown>;
type RegisterValue = {
  available?: boolean;
  items?: RegisterItem[];
  entrances?: RegisterItem[];
  developments?: RegisterItem[];
  schools?: RegisterItem[];
  hospitals?: RegisterItem[];
  features?: RegisterItem[];
};

function _itemsFromRegisterValue(v: RegisterValue): RegisterItem[] {
  if (Array.isArray(v.items)) return v.items;
  if (Array.isArray(v.entrances)) return v.entrances;
  if (Array.isArray(v.developments)) return v.developments;
  if (Array.isArray(v.schools)) return v.schools;
  if (Array.isArray(v.hospitals)) return v.hospitals;
  if (Array.isArray(v.features)) return v.features;
  return [];
}

/** An asset's name and what places it: its distance and subway routes. */
function _itemRow(item: RegisterItem): { label: string; detail: string | null } {
  const label = (str(item.station_name) ?? str(item.development)
                ?? str(item.loc_name) ?? str(item.facility_name)
                ?? str(item.label) ?? str(item.name) ?? 'item');
  const distance = num(item.distance_m);
  const detail_bits: string[] = [];
  if (distance != null) detail_bits.push(`${Math.round(distance)} m`);
  const routes = str(item.daytime_routes);
  if (routes) detail_bits.push(routes);
  return { label, detail: detail_bits.join(', ') || null };
}

/** "2 NYCHA developments", "1 NYCHA development". */
const countOf = (n: number, noun: string) => `${n} ${n === 1 ? noun.replace(/s$/, '') : noun}`;

/** One register's finding as a plain sentence, from the values it
 *  returned: how many listed assets are within its radius, how many sit in
 *  the 2012 Sandy extent and the DEP 2080 scenario, and the nearest ones
 *  by name. Used only when the pebble gave no narrative; it counts the
 *  listed assets, since some registers hold only flood-exposed ones. */
export function registerSentence(
  noun: string,
  v: Record<string, unknown>,
  items: RegisterItem[],
  listed: { label: string; detail: string | null }[],
): string {
  const radius = num(v.radius_m);
  const within = radius != null ? `within ${radius} m` : 'within range';
  if (!items.length) return `No ${noun} listed ${within}.`;
  const sandy = num(v.n_inside_sandy_2012);
  const dep = num(v.n_in_dep_extreme_2080);
  const flags = [
    sandy != null && `${sandy} inside the 2012 Sandy extent`,
    dep != null && `${dep} in a category of the Extreme Flood 2080 stormwater map`,
  ].filter(Boolean).join(' and ');
  const names = listed.map((r) => (r.detail ? `${r.label} (${r.detail})` : r.label)).join(', ');
  const nearest = listed.length < items.length ? `; the nearest ${listed.length}: ${names}` : `: ${names}`;
  return `${countOf(items.length, noun)} listed ${within}${flags ? `, ${flags}` : ''}${names ? nearest : ''}.`;
}

/** One register's card: its finding (the pebble's own narrative, which
 *  says whether it counts every asset in range or only flood-exposed
 *  ones) and its own citation and date. A register that could not be read
 *  is a muted absence, not a finding; one read with nothing in range
 *  reports 0. */
function buildRegisterCard(m: PebbleManifest, value: unknown): Card | null {
  const v = obj(value) as (RegisterValue & Record<string, unknown>) | null;
  if (!v) return null;
  const items = _itemsFromRegisterValue(v);
  const noun = m.title.replace(/\s+exposed nearby$/i, '');
  const said = str(v.narrative)?.replace(/\s*\[[a-z0-9_]+\]/g, '').trim();
  const sentence = said || registerSentence(noun, v, items, items.slice(0, 4).map(_itemRow));
  const doc = m.provenance.doc_id ?? m.id;
  const card: Card = {
    id: `fsm-${m.id.replace(/_/g, '-')}`,
    stone: m.stone, tier: (m.tier ?? 'empirical') as Card['tier'], variant: 'register',
    source: shortSource(m.provenance.source_name),
    vintage: m.provenance.date_modified
      ?? (m.provenance.retrieved_at ? `retrieved ${m.provenance.retrieved_at}` : RIPRAP_VINTAGE),
    title: m.title,
    // Pebble narratives carry no closing stop.
    sub: /[.!?]$/.test(sentence) ? sentence : `${sentence}.`,
    docId: doc,
    citeId: doc,
  };
  return v.available === false
    ? { ...card, absent: 'Not available',
        sub: m.fallback.message ?? `The ${noun} list was not available when this briefing ran.` }
    : card;
}

// ── Type-keyed histogram card renderer ──────────────────────────
//
// Pebbles that declare `display.variant: histogram` and emit
// `{ n, headline_value, narrative }`. nyc311 is the canonical case.
type HistogramValue = {
  n?: number;
  headline_value?: string;
  narrative?: string;
};

function buildHistogramCard(m: PebbleManifest, value: unknown): Card | null {
  const t = value as HistogramValue | null;
  if (!t) return null;
  // An honest negative ("0 complaints") still shows; the narrative explains the zero.
  const n = num(t.n) ?? 0;
  return {
    id: `fsm-${m.id.replace(/_/g, '-')}`,
    stone: m.stone, tier: (m.tier ?? 'proxy') as Card['tier'], variant: 'histogram',
    source: shortSource(m.provenance.source_name),
    vintage: m.provenance.date_modified?.toString() ?? RIPRAP_VINTAGE,
    title: m.title,
    headline: t.headline_value ?? `${n} complaint${n === 1 ? '' : 's'}`,
    sub: t.narrative,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
  };
}

/** How a model took part, in plain words. An experimental model either ran
 *  for this briefing (`loaded`) or ran earlier and its saved output was
 *  read (`precomputed`). */
const HOW_LABEL: Record<ModelRow['how'], string> = {
  endpoint: 'LLM endpoint',
  loaded: 'run for this briefing',
  precomputed: 'not run for this briefing',
};

/** Hugging Face page for a repo id ("org/name") or an Ollama "hf.co/org/name:tag" id. */
function hfHref(repo: string): string | null {
  const id = repo.startsWith('hf.co/') ? repo.slice(6).split(':')[0] : repo;
  return id.includes('/') && !id.includes(':') ? `https://huggingface.co/${id}` : null;
}

/** Shape `final.models` into the capstone card's model list. A row with
 *  no latency (a precomputed model) prints none. `where` opens a sentence
 *  in the list, so it takes a capital. */
export function modelLines(rows: ModelRow[] | undefined): ModelLine[] {
  return (rows ?? []).map((r) => {
    let latency = r.latency_s != null ? `${r.latency_s.toFixed(1)} s` : null;
    if (latency && r.calls) latency += ` over ${r.calls} call${r.calls === 1 ? '' : 's'}`;
    return {
      name: r.name,
      // An unpublished model has no repository (repo: null): say so, with no link.
      repo: r.repo ?? 'weights not published',
      href: r.repo ? hfHref(r.repo) : null,
      where: r.where.charAt(0).toUpperCase() + r.where.slice(1),
      how: HOW_LABEL[r.how] ?? r.how,
      latency,
    };
  });
}

/** The capstone card: the models behind the briefing (`final.models`). */
function buildCapstoneMeta(final: FinalResult): Card {
  const g = final.grounding;
  const isLlm = g?.tier === 'llm';
  return {
    id: 'fsm-capstone-meta',
    stone: 'capstone', tier: 'modeled', variant: 'meta',
    source: isLlm ? 'LLM' : 'No LLM',
    vintage: RIPRAP_VINTAGE,
    title: 'How this briefing was written',
    models: modelLines(final.models),
    sub: g?.fallback_reason
      ? `The LLM was unavailable (${g.fallback_reason}), so the evidence briefing is shown.`
      : 'Capstone writes prose, not cards. This card records how the briefing was produced.',
    docId: 'capstone',
  };
}

/* ── Templated card builder (BYOD path).
 *
 * For every pebble in `/api/pebbles` that doesn't have a special builder
 * above, we render a generic evidence card driven entirely by the
 * manifest + the pebble's value dict. This is what makes BYOD work:
 * declaring a new pebble in YAML produces a real card with zero
 * frontend code edits.
 *
 * Mapping from `display.kind` → CardVariant:
 *    text     → headline   (narration.short fills `headline`)
 *    stat     → scalars    (every numeric field becomes a scalar cell)
 *    list     → tabular    (the templated sentence)
 *    chart    → meta       (no canonical chart shape yet; falls back to meta)
 *    map_only → null       (no card body; data only appears on the map)
 *
 * Chrome (source / title / docId / cites) comes from
 * `manifest.provenance` + `manifest.title`.
 */
const KIND_TO_VARIANT: Record<PebbleManifest['display']['kind'], CardVariant | null> = {
  text: 'headline',
  stat: 'scalars',
  list: 'tabular',
  chart: 'meta',
  map_only: null,
};

/** Valid CardVariant values, for validating manifest.display.variant
 *  (typed as a loose `string | null` since it's server-supplied JSON)
 *  before trusting it as an override in buildTemplated. */
const VALID_CARD_VARIANTS: Record<CardVariant, true> = {
  headline: true, tabular: true, scalars: true, histogram: true,
  register: true, meta: true,
};

/** The city's land cover map and the land-cover model, for a point or an area. */
const LANDCOVER_ID = /^(city_)?landcover(_nta)?$/;

/** Intents that run polygon (neighborhood) pebbles instead of point ones. */
export const POLYGON_INTENTS = new Set(['neighborhood', 'development_check']);

/** True when a pebble belongs to the given intent's card scaffold. Keeps
 *  neighborhood-only pebbles off address pages (and vice versa) instead
 *  of rendering them as "No data" cards. A pebble with scope `any` runs
 *  for both. The other briefing's pebbles (flood sources on a heat run,
 *  heat sources on a flood run) are out of scope too, so they are not
 *  listed as "Not run". */
export function pebbleInScope(m: PebbleManifest, intent: string | null | undefined, heat = false): boolean {
  if (m.hazard && m.hazard !== 'any' && m.hazard !== (heat ? 'heat' : 'flood')) return false;
  const want = intent && POLYGON_INTENTS.has(intent) ? 'polygon' : 'point';
  const scope = m.scope ?? 'point';
  return scope === 'any' || scope === want;
}

/** A scalar with its unit apart from its label ("Elevation (m)" is 14.87
 *  with the unit m, labelled Elevation), so the figure column prints the
 *  unit with the number. A water level is stated against its datum, as
 *  the sentence states it ("6.6 ft above MLLW"). */
function scalarCell(key: string, v: number, label: string, value: Record<string, unknown>): NonNullable<Card['scalars']>[number] {
  const m = /^(.*) \(([^()]+)\)$/.exec(label);
  const datum = key === 'observed_ft' ? str(value.datum) : null;
  const unit = datum ? `ft above ${datum}` : m?.[2];
  return { value: `${v}`, label: m ? m[1] : label, ...(unit && { unit }) };
}

function buildTemplated(m: PebbleManifest, value: unknown, failed = false): Card | null {
  // The manifest's `display.variant` is an explicit per-pebble override
  // of the kind→variant default (e.g. sandy.yaml: `kind: stat, variant:
  // headline` — a boolean_zone result has no numeric fields, so the
  // 'scalars' builder KIND_TO_VARIANT['stat'] would derive would always
  // fall through to fallback.message even on success). Prefer it when
  // it names a real CardVariant; this was silently ignored before,
  // which made every kind:stat pebble with a non-numeric shaped value
  // render as "unavailable" regardless of success.
  const explicitVariant = m.display.variant as CardVariant | null;
  const variant = (explicitVariant && explicitVariant in VALID_CARD_VARIANTS)
    ? explicitVariant
    : KIND_TO_VARIANT[m.display.kind];
  if (variant === null) return null;
  // The manifest's declared tier is the authority (DEP scenarios are
  // modeled, 311 is proxy); the type only fills in when none is declared.
  const tier = m.tier ?? (m.type === 'model' ? 'modeled' : 'empirical');
  const source = shortSource(m.provenance.source_name);
  const vintage = m.provenance.date_modified ?? RIPRAP_VINTAGE;
  const base: Card = {
    id: `pebble-${m.id}`,
    stone: m.stone,
    tier,
    variant: variant ?? 'meta',
    source,
    vintage,
    title: m.title,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
  };
  // No value: keep the pebble visible with its provenance, but as a muted
  // absence, not a finding. A step that errored, or ran and returned
  // null, is "Not available"; a step that never ran is "Not run".
  if (value === null || value === undefined) {
    const notRun = value === undefined && !failed;
    return { ...base, variant: 'headline',
             absent: notRun ? 'Not run' : 'Not available',
             sub: notRun ? 'Not checked for this question.' : (m.fallback.message ?? undefined) };
  }
  // The source ran and said it has nothing (e.g. a forecast with too
  // little history). Its own reason, when given, beats the manifest's
  // "offline" fallback, which would be untrue here.
  const rec = obj(value);
  if (rec?.available === false) {
    return { ...base, variant: 'headline', absent: 'Not available',
             sub: str(rec.reason) ?? m.fallback.message ?? undefined };
  }
  if (variant === 'headline') {
    // Format manifest.narration.template against the pebble value
    // (the shaper's job is to ensure value carries the placeholders
    // — sandy's `boolean_zone` shaper emits inside_phrasing /
    // inside / outside_phrasing for the template to consume).
    // Mirrors the backend templated_reconciler's _format_template
    // — if a placeholder is missing, fall back to narration.short.
    const formatted = m.narration.template
      ? formatTemplate(m.narration.template, value)
      : null;
    // Lead with the pebble's own figure when it gives one ("0.8% inside the
    // 2012 Sandy extent"); the manifest's short line only describes the source.
    return { ...base,
             headline: str(rec?.headline_value) ?? m.narration.short ?? m.title,
             body: formatted ?? (typeof value === 'string' ? value : undefined) };
  }
  if (variant === 'scalars') {
    const scalars: NonNullable<Card['scalars']> = [];
    // Fields that are metadata, not user-facing measurements: drop
    // them from the scalar grid (they're noise — station_id is in
    // the card title, station_lat/lon are implied by station_name +
    // distance_km, version/cache fields don't help a reader). The
    // Chicago Lake Michigan card was rendering with only lat/lon
    // because the observed/predicted values came back null and the
    // junk fields took over.
    const SCALAR_IGNORE = new Set([
      'station_lat', 'station_lon', 'station_id',
      'aoi_radius_m', 'radius_m', 'cache_age_s',
      // Back-compat alias of observed_ft (the datum-aware key) the
      // noaa_tides adapter keeps for legacy LLM-citation paths; if
      // both are present (Chicago) the card would show the same value
      // twice.
      'observed_ft_mllw', 'predicted_ft_mllw',
    ]);
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
        const label = FIELD_LABELS[k];
        if (SCALAR_IGNORE.has(k) || !label) continue;
        if (typeof v === 'number' && Number.isFinite(v)) scalars.push(scalarCell(k, v, label, value as Record<string, unknown>));
      }
    } else if (typeof value === 'number') {
      scalars.push({ value: `${value}`, label: m.title });
    } else if (typeof value === 'boolean') {
      scalars.push({ value: value ? 'yes' : 'no', label: m.title });
    }
    if (!scalars.length) {
      // No *numeric* measurement scalars — but the pebble may still have
      // succeeded with a real, meaningful non-numeric result (sandy's
      // boolean_zone shaper: {inside, inside_phrasing, ...}, no numbers
      // at all). Try the manifest's narration.template first; only a
      // pebble that's genuinely offline/errored should fall to
      // fallback.message. Without this, every `display.kind: stat`
      // pebble whose value happens to be boolean/string-shaped rendered
      // as "unavailable" even when it succeeded — sandy, dep_stormwater,
      // etc. all falsely read as broken infrastructure.
      const templated = m.narration.template
        ? formatTemplate(m.narration.template, value)
        : null;
      if (templated) {
        return { ...base, variant: 'headline',
                 headline: m.narration.short ?? m.title,
                 body: templated };
      }
      // Look for an `error` string the pebble may have surfaced and
      // render that as the headline so the user knows the source was
      // unreachable — not silent.
      const errStr = (typeof value === 'object' && value !== null
        ? (value as Record<string, unknown>).error
        : null);
      return { ...base, variant: 'headline',
               absent: 'Not available',
               sub: typeof errStr === 'string'
                 ? errStr.split('\n')[0].slice(0, 80)
                 : (m.fallback.message ?? undefined) };
    }
    // If the manifest carries a narration.template with the
    // pebble-adapter-built `{narrative}` (or any other placeholder
    // the value supplies), format it as the card's `sub` line so
    // the user reads both the scalar grid AND a sentence-level
    // summary the LLM-citation path also consumes.
    const narrative = m.narration.template
      ? formatTemplate(m.narration.template, value)
      : null;
    return { ...base, scalars, sub: narrative ?? undefined };
  }
  if (variant === 'tabular') {
    // GeoJSON-style features: the count.
    const feats = (value as { features?: unknown[] } | null)?.features;
    if (Array.isArray(feats) && feats.length) {
      return { ...base, sub: `${feats.length} feature${feats.length === 1 ? '' : 's'} within range` };
    }
    // Otherwise the pebble's narration.template formatted against the
    // value: a city 311 card states what the backend sentence states
    // ("3 of 17 ... requests ... are in categories reviewed as
    // flood-related"), and nws_alerts its own narrative. If the template
    // cannot be filled, the manifest's fallback message.
    const tabularNarrative = m.narration.template
      ? formatTemplate(m.narration.template, value)
      : null;
    if (tabularNarrative) return { ...base, variant: 'headline', headline: tabularNarrative };
    return { ...base, variant: 'headline', absent: 'Not available',
             sub: m.fallback.message ?? 'No records within range' };
  }
  // meta fallback (chart pebbles without a special builder)
  return { ...base, variant: 'meta', sub: m.narration.short ?? undefined };
}

/** Public adapter. Combines per-specialist card builders with the trace
 *  → StoneTrace mapper into a single FindingsData payload.
 *
 *  Accepts either a real FinalResult (at end-of-stream) or a partial
 *  one synthesized from in-flight step events (during streaming). Each
 *  builder returns null when its slice of state is missing — so cards
 *  pop into the rail as their specialist completes, without waiting
 *  for the full reconcile. */
export function adaptFinalToFindings(
  final: FinalResult | Partial<FinalResult> | null | undefined,
  trace: TraceNode | undefined | null,
  wallSeconds?: number,
  /** When true, the Capstone meta card renders even with a stub final
   *  (we always want the run-summary). When false (no final at all),
   *  the meta card is skipped — there's nothing to summarise yet. */
  hasFinal: boolean = true,
): FindingsData {
  const f = (final ?? {}) as Final;
  // Every pebble renders through the manifest loop below. The Capstone
  // run summary is the one curated card, and only once there is
  // something to summarise.
  const curatedCards: Card[] = hasFinal
    ? [buildCapstoneMeta((final ?? { paragraph: '' }) as FinalResult)]
    : [];

  // Phase 2 — templated cards for every manifest pebble that didn't get a
  // curated special-builder card. New BYOD pebbles defined only in YAML
  // appear here automatically.
  const templatedCards: Card[] = [];
  // Sources that ran and came back empty or marked unavailable: the same
  // pebbles the muted "Not available" cards and silent register rows show.
  // Failed steps are left out; the sources list flags those already.
  const noData: { id: string; title: string }[] = [];
  const intent = str(f.intent);
  const failedIds = new Set<string>();
  const walk = (n: TraceNode | null | undefined) => {
    if (!n) return;
    if (n.status === 'error') failedIds.add(n.name);
    for (const c of n.children ?? []) walk(c);
  };
  walk(trace);
  const inScope = (m: PebbleManifest) => pebbleInScope(m, intent, isHeat(f.plan));
  for (const stone of pebbleManifest.stones) {
    // Per-pebble loop — single-pebble bespoke variants + the generic
    // templated fallback. Type-keyed dispatch by display.variant.
    for (const m of (pebbleManifest.byStone[stone.id] ?? []).filter(inScope)) {
      const value = (f as Record<string, unknown>)[m.id];
      let card: Card | null = null;
      if (m.display.variant === 'register') {
        // A register that did not run has no card (it never had one).
        card = buildRegisterCard(m, value);
        if (!card) continue;
      } else if (m.display.variant === 'histogram') {
        card = buildHistogramCard(m, value);
      }
      if (!card) card = buildTemplated(m, value, failedIds.has(m.id));
      if (card?.absent === 'Not available' && !failedIds.has(m.id)) noData.push({ id: m.id, title: m.title });
      // A heat source, and the land cover map on either briefing, states
      // its figure in words; the evidence table shows that (figureOf).
      const figure = card && !card.absent && (m.hazard === 'heat' || LANDCOVER_ID.test(m.id))
        ? str(obj(value)?.headline_value) : null;
      if (card) templatedCards.push({ ...card, ...(figure && { figure }), experimental: m.maturity === 'experimental' });
    }
  }

  return {
    cards: [...curatedCards, ...templatedCards].map(dropUnfilled),
    stones: buildStoneTraces(trace, inScope),
    wallSeconds,
    emissions: (f as { emissions?: FindingsData['emissions'] }).emissions,
    noData,
  };
}

/** Said above the evidence when a question got the place's evidence and
 *  no answer (no rule named what it asks and no model answered). The
 *  backend now says so itself in an Answer section, so this line is for
 *  results saved before it did. */
export const UNANSWERED = 'This question was not answered. The evidence for the place is shown below.';

/** What produced the briefing, in words: the mode line on screen and in
 *  print. An extractive answer is quoted, not model prose, so it does not
 *  say "LLM claims checked" for it. A question the rules answered, one
 *  they found no source for, or one that neither a rule nor a model
 *  answered, says so. A refusal has no mode line: the callers pass none
 *  for a refused run (`RunState.refused`). `planned` is true
 *  when a language model planned the query (`final.plan.llm_calls`), so a
 *  rules answer does not claim that no model was used. */
export function modeLine(g: { tier: string; model?: string; answer_mode?: string | null; answer_lead?: string | null; note?: string;
                              question?: string; answered?: boolean | null;
                              claims?: unknown[]; dropped_claims?: unknown[]; fallback_reason?: string } | null | undefined,
                         planned = false): string | null {
  if (!g) return null;
  if (g.tier !== 'llm') {
    if (g.note) return 'Evidence briefing: no question was asked, so no LLM was needed';
    const unavailable = g.fallback_reason ? ` The LLM was unavailable (${g.fallback_reason}).` : '';
    // No answer lead at all: the evidence briefing stands in for an answer.
    if (g.question && g.answered === false && (!g.answer_lead || g.answer_lead === 'not_recognised')) {
      return `No rule and no language model answered the question, so the evidence briefing is shown.${unavailable}`;
    }
    // The rules ran and found nothing that answers: the answer says so, and
    // this line must not say the question was answered.
    // The rules read the question and what it asks for is not in the records
    // (or it is not in English): the answer's first sentence says which.
    if (g.question && g.answer_mode === 'rules' && (g.answer_lead === 'not_held' || g.answer_lead === 'not_english')) {
      return (g.answer_lead === 'not_held'
        ? 'The rules read the question as asking for something Riprap does not hold, so it is not answered'
        : 'The question was not read as English, so it is not answered')
        + (planned ? '; a language model was used only to read the place and choose the sources.' : '; no language model was used.');
    }
    if (g.question && g.answer_mode === 'rules' && g.answer_lead === 'cannot_answer') {
      return (planned
        ? 'The rules found no source that answers the question; a language model was used only to read the place and choose the sources.'
        : 'The rules found no source that answers the question; no language model was used.') + unavailable;
    }
    if (g.question && g.answer_mode === 'rules') {
      return (planned
        ? "The answer was chosen by rules over the question's words; a language model was used only to read the place and choose the sources."
        : "Answered by rules over the question's words; no language model was used.") + unavailable;
    }
    return g.fallback_reason
      ? `Evidence briefing (no LLM). The LLM was unavailable (${g.fallback_reason}), so the evidence briefing is shown.`
      : 'Evidence briefing (no LLM)';
  }
  const model = g.model ? ` (${g.model})` : '';
  const counts = `${g.claims?.length ?? 0} kept, ${g.dropped_claims?.length ?? 0} dropped`;
  // A cannot-answer line quotes nothing: code sets it when the lead rules
  // find no source that answers, so it is not described as quoted.
  if (g.answer_mode === 'extractive' && g.answer_lead === 'cannot_answer') {
    return 'Extractive answer: no source sentence answers the question, so the answer says so in a line set by the lead rules';
  }
  if (g.answer_mode === 'extractive') {
    // The answer's facts are listed as claims in section "answer"; say "other
    // claims" only when the model wrote any outside the answer.
    const other = (g.claims ?? []).filter((c) => (c as { section?: string })?.section !== 'answer').length;
    const otherDropped = (g.dropped_claims ?? []).filter((c) => (c as { section?: string })?.section !== 'answer').length;
    return `Extractive answer: sentences quoted word for word from the cited sources, chosen by the model${model} ` +
      'and checked by the lead rules' + (other || otherDropped
        ? `. Other claims checked against cited sources: ${other} kept, ${otherDropped} dropped` : '');
  }
  return `LLM claims checked against cited sources: ${counts}${model}`;
}
