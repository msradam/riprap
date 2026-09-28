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
 * confabulation); a specialist that fired with no usable shape becomes
 * a `meta` card listing whatever scalars it returned.
 */
import type {
  Card, CardVariant, FindingsData, StoneKey, StoneMember, StoneTrace
} from '$lib/types/card';
import type { TraceNode, TraceStatus } from '$lib/types/trace';
import { citationList, type FinalResult } from '$lib/client/agentStream';
import { pebbleManifest, type PebbleManifest } from '$lib/stores/pebbleManifest.svelte';

/** Reasonable defaults — when the FSM doesn't supply a vintage, fall
 *  back to the Riprap publication date. */
const RIPRAP_VINTAGE = '2026-05';

/** Card-header source: the part of `source_name` before a spaced dash or
 *  an em dash. Splitting on any hyphen cut "NOAA CO-OPS" to "NOAA CO"
 *  and "NYC flood-policy corpus" to "NYC flood". */
function shortSource(name: string): string {
  return name.split(/\s[-–—]\s|—/)[0].trim();
}

/** Reader-facing labels for the value fields that scalar and meta cards
 *  show. Each label restates the field as the pebble's own narrative
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
  hand_m: 'Height above nearest drainage (m)',
  twi: 'TWI',
  // fema_nfhl
  effective_year: 'FIRM panel effective year',
  // floodnet
  n_sensors: 'Sensors nearby',
  n_flood_events_3y: 'Flood events, last 3 years',
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
 */
function formatTemplate(template: string, value: unknown): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const v = value as Record<string, unknown>;
  let missing = false;
  const out = template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const x = v[key];
    if (x === undefined || x === null || x === '') {
      missing = true;
      return '';
    }
    return String(x);
  });
  return missing ? null : out.trim();
}

const UNFILLED = /\{\w+\}/;
const TEXT_FIELDS = ['headline', 'subhead', 'body', 'sub', 'sparkSub', 'spatialNote'] as const;

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
  const rows = card.metaRows?.filter((r) => !UNFILLED.test(r.v));
  if (rows && rows.length !== card.metaRows?.length) out = { ...out, metaRows: rows };
  return out;
}

/** Map the FSM trace's TraceStatus into the v0.4.5 5-state SpecialistStatus.
 *  Crucial split: a specialist that "returned no data" is `silent_by_design`,
 *  not `errored`. The FSM marks both as `silent` in the trace; we
 *  conservatively classify any successful trace-`silent` as
 *  silent_by_design (the spec voice). Anything that raised in the FSM
 *  becomes `errored`. `fan`/`merge` are structural; the few callers
 *  that look at them treat them as fired.
 */
function mapStatus(s: TraceStatus): StoneMember['status'] {
  if (s === 'fan' || s === 'merge') return 'fired';
  if (s === 'silent') return 'silent_by_design';
  if (s === 'error') return 'errored';
  return 'fired';
}

function flattenTrace(node: TraceNode): TraceNode[] {
  return [node, ...(node.children ?? []).flatMap(flattenTrace)];
}

/** Group leaf specialist nodes by the Stone their pebble belongs to.
 *  Source of truth: pebbleManifest.byId — populated from /api/pebbles
 *  at app load, so every manifest in the active deployment is recognised
 *  by definition. A small alias map keeps legacy step names (the
 *  Capstone reconciler emits e.g. `reconcile_granite41`, not a
 *  manifest id) routing to the right Stone. */
const _LEGACY_STEP_TO_STONE: Record<string, StoneKey> = {
  // NTA / neighborhood-aggregate steps don't have their own manifests yet
  sandy_nta: 'cornerstone',
  dep_extreme_2080_nta: 'cornerstone',
  dep_moderate_2050_nta: 'cornerstone',
  dep_moderate_current_nta: 'cornerstone',
  microtopo_nta: 'cornerstone',
  nyc311_nta: 'touchstone',
  rag_nta: 'capstone',
  // Asset-exposure step names that pre-date the matching pebble ids
  mta_entrance_exposure: 'keystone',
  nycha_development_exposure: 'keystone',
  doe_school_exposure: 'keystone',
  doh_hospital_exposure: 'keystone',
  // Specialist clusters not yet ported to manifests
  terramind_synthesis: 'keystone',
  terramind_buildings: 'keystone',
  terramind_lulc: 'touchstone',
  eo_chip_fetch: 'keystone',
  prithvi_eo_v2: 'cornerstone',
  // Capstone reconciler variants
  reconcile_granite41: 'capstone',
  reconcile_neighborhood: 'capstone',
  reconcile_development: 'capstone',
  reconcile_live_now: 'capstone',
  reconcile_templated: 'capstone',
  reconcile_claims: 'capstone',
  rag_granite_embedding: 'capstone',
  gliner_extract: 'capstone',
};

function stoneForStep(name: string): StoneKey | null {
  const n = name.toLowerCase();
  // Manifest is the truth: any pebble id in the active deployment maps
  // to its stone by definition.
  const pebble = pebbleManifest.byId[n];
  if (pebble) return pebble.stone;
  return _LEGACY_STEP_TO_STONE[n] ?? null;
}

/** Project the live trace against the deployment's pebble roster.
 *
 *  v0.4.5 §3: every Stone's expander shows the full intended roster —
 *  present specialists keep their live status; absent ones land as
 *  `not_invoked` with their declared fallback message. The roster
 *  source is the active deployment's manifests (pebbleManifest.byStone),
 *  not a frontend-hardcoded list, so adding a city = no TS edits.
 */
function fillRosterFromManifests(
  stone: StoneKey,
  liveByName: Map<string, StoneMember>,
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
    } else {
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

function buildStoneTraces(root: TraceNode | undefined | null): StoneTrace[] {
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
    members: fillRosterFromManifests(key, buckets[key]),
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

function buildTerramindBuildings(state: Final): Card | null {
  const tmb = obj(state.terramind_buildings);
  if (!tmb?.ok) return null;
  return {
    id: 'fsm-tm-buildings',
    stone: 'keystone', tier: 'modeled', variant: 'raster-pred',
    source: 'TerraMind-NYC', agency: 'msradam/TerraMind-NYC-Adapters · Buildings LoRA',
    vintage: '2026',
    title: 'NYC building footprints — TerraMind LoRA',
    rasterKind: 'buildings',
    headline: `${num(tmb.pct_buildings) ?? 0}%`,
    subhead: 'building-footprint coverage in chip',
    sub: `${num(tmb.n_building_components) ?? 0} distinct components · test mIoU 0.5511`,
    illustrative: true,
    docId: 'tm_buildings', citeId: 'tm_buildings', mapLayer: 'buildings',
  };
}

/** Conventional LULC palette — matches the design handoff's LULC card
 *  visual (urban / water / vegetation / barren / wetland). The colors
 *  are layer conventions, NOT new tier signals. */
const LULC_PALETTE: Record<string, string> = {
  urban: '#C66',
  water: '#5B7FB4',
  vegetation: '#5B8A4A',
  barren: '#A89A78',
  wetland: '#D9C75A',
};

function buildTerramindLulc(state: Final): Card | null {
  const t = obj(state.terramind_lulc);
  if (!t?.ok) return null;
  // Translate the FSM's class_fractions dict into the design-system's
  // expected ordered class-mix (urban / water / vegetation / barren /
  // wetland). Unknown class names land in barren as a catch-all.
  const fractions = (obj(t.class_fractions) ?? {}) as Record<string, number>;
  const buckets: Record<keyof typeof LULC_PALETTE, number> = {
    urban: 0, water: 0, vegetation: 0, barren: 0, wetland: 0,
  };
  for (const [k, v] of Object.entries(fractions)) {
    const lk = k.toLowerCase();
    if (lk.includes('urban') || lk.includes('built') || lk.includes('impervious')) buckets.urban += v;
    else if (lk.includes('water')) buckets.water += v;
    else if (lk.includes('tree') || lk.includes('vegetation') || lk.includes('crop') || lk.includes('grass')) buckets.vegetation += v;
    else if (lk.includes('bare') || lk.includes('barren') || lk.includes('soil')) buckets.barren += v;
    else if (lk.includes('wet') || lk.includes('marsh')) buckets.wetland += v;
    else buckets.barren += v;
  }
  const classMix = (Object.entries(buckets) as [keyof typeof LULC_PALETTE, number][])
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ k, pct: Math.round(v), color: LULC_PALETTE[k] }));

  return {
    id: 'fsm-tm-lulc',
    stone: 'touchstone', tier: 'synthetic', variant: 'lulc',
    source: 'TerraMind v1.2', agency: 'IBM TerraMind v1.2 · Sentinel-2 inputs',
    vintage: 'Sentinel-2',
    title: 'Land use / land cover · TerraMind v1.2',
    rasterKind: 'lulc',
    classMix: classMix.length ? classMix : undefined,
    sub: 'Synthetic prior. LULC palette is a layer convention, not a tier signal.',
    illustrative: true,
    docId: 'tm_lulc', citeId: 'tm_lulc', mapLayer: 'terramind-lulc',
  };
}

// ─── Type-keyed bespoke variant renderers ─────────────────────────
//
// The framework move (per the user's "type-specific, not city-specific"
// note): bespoke builders are kept for value shapes that earn rich
// rendering — forecasts, ML rasters, asset registers, lulc class
// breakdowns — but each builder is keyed by VALUE SHAPE / display
// variant, not by a hardcoded pebble id. Any pebble that emits the
// expected shape and declares the right `display.variant` gets the
// same bespoke card.
//
// Below: `buildTimeseriesForecast` unifies the previous
// buildTtmForecast + buildTtmBatterySurge. The pebble's value shape
// declares the unit and horizon ("ft" + minutes vs "cm" + hours,
// derived from which `forecast_peak_*` keys are present). The
// manifest's display.variant ('timeseries' | 'timeseries-ft') picks
// the chrome (fine-tune footer for `timeseries-ft`). Future TTM /
// forecast / surge pebbles use this same renderer — drop the
// curated id-keyed builders.

type ForecastValue = {
  available?: boolean;
  interesting?: boolean;
  // Surge — zero-shot (ft / minutes) and fine-tune (m / hours).
  forecast_peak_ft?: number;
  forecast_peak_minutes_ahead?: number;
  forecast_peak_m?: number;
  forecast_peak_hours_ahead?: number;
  // 311 weekly forecast — per-day peak, day offset.
  forecast_peak_day?: number;
  forecast_peak_day_offset?: number;
  forecast_weekly_equivalent?: number;
  // FloodNet sensor — per-day-value peak, day offset.
  forecast_peak_day_value?: number;
  forecast_28d_expected_events?: number;
  history_recent_28d_events?: number;
  // Fine-tune footer fields (only on timeseries-ft variant).
  rmse_m?: number;
  hf_model_card?: string;
  skill_vs_persistence?: string;
  hardware_badge?: string;
  spatial_note?: string;
};

function buildTimeseriesForecast(m: PebbleManifest, value: unknown): Card | null {
  const t = value as ForecastValue | null;
  if (!t || !t.available) return null;
  // `interesting` is the explicit-hide gate (surge floor). If absent,
  // default to showing the card: every available forecast should surface.
  if (t.interesting === false) return null;
  // Detect unit from which fields the adapter populated. Each branch is
  // its own pebble-family contract:
  //   ft + minutes_ahead       → surge (zero-shot)
  //   m + hours_ahead          → surge (fine-tune, cm display)
  //   peak_day + day_offset    → weekly cadence (311 forecasts)
  //   peak_day_value + offset  → daily cadence (FloodNet sensor)
  let peakLabel: string;
  let headline: string;
  let timeseries: NonNullable<Card['timeseries']>;
  let subhead: string;
  if (num(t.forecast_peak_ft) != null && num(t.forecast_peak_minutes_ahead) != null) {
    const peak = num(t.forecast_peak_ft)!;
    const ahead = num(t.forecast_peak_minutes_ahead)!;
    peakLabel = `${peak} ft @ +${Math.round(ahead / 60)}h`;
    headline = `${peak} ft`;
    timeseries = { hours: 96, peak: { x: 38, y: 47 }, peakLabel };
    subhead = m.narration.short ?? 'peak surge residual';
  } else if (num(t.forecast_peak_m) != null
             && num(t.forecast_peak_hours_ahead) != null) {
    const peak = num(t.forecast_peak_m)!;
    const ahead = num(t.forecast_peak_hours_ahead)!;
    peakLabel = `${(peak * 100).toFixed(0)} cm @ +${ahead}h`;
    headline = `${(peak * 100).toFixed(0)} cm`;
    timeseries = {
      hours: 96,
      peak: { x: ahead, y: Math.round(peak * 100) },
      peakLabel,
    };
    subhead = m.narration.short ?? 'peak surge';
  } else if (num(t.forecast_peak_day) != null
             && num(t.forecast_peak_day_offset) != null) {
    const peak = num(t.forecast_peak_day)!;
    const offset = num(t.forecast_peak_day_offset)!;
    const weekly = num(t.forecast_weekly_equivalent);
    peakLabel = `${peak.toFixed(2)}/day @ +${offset}d`;
    headline = weekly != null
      ? `${weekly.toFixed(1)}/wk`
      : `${peak.toFixed(2)}/day`;
    timeseries = { hours: 96, peak: { x: offset, y: peak }, peakLabel };
    subhead = m.narration.short ?? 'forecast peak';
  } else if (num(t.forecast_peak_day_value) != null
             && num(t.forecast_peak_day_offset) != null) {
    const peak = num(t.forecast_peak_day_value)!;
    const offset = num(t.forecast_peak_day_offset)!;
    const expected = num(t.forecast_28d_expected_events);
    peakLabel = `${peak.toFixed(2)}/day @ +${offset}d`;
    headline = expected != null
      ? `${expected.toFixed(1)} events`
      : `${peak.toFixed(2)}/day`;
    timeseries = { hours: 96, peak: { x: offset, y: peak }, peakLabel };
    subhead = m.narration.short ?? 'sensor forecast peak';
  } else {
    return null;
  }
  const variant: CardVariant =
    (m.display.variant === 'timeseries-ft' || m.display.variant === 'timeseries')
      ? m.display.variant
      : 'timeseries';
  const tier = (m.tier ?? 'modeled') as Card['tier'];
  const source = shortSource(m.provenance.source_name);
  return {
    id: `fsm-${m.id.replace(/_/g, '-')}`,
    stone: m.stone, tier, variant,
    source, agency: m.provenance.source_name,
    vintage: m.provenance.date_modified?.toString() ?? RIPRAP_VINTAGE,
    title: m.title,
    timeseries,
    headline,
    subhead,
    sub: m.narration.template ? formatTemplate(m.narration.template, t) ?? undefined : undefined,
    spatialNote: t.spatial_note,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
    // Fine-tune footer: only when the variant is timeseries-ft AND
    // the manifest's provenance carries an HF model card url. Each
    // fine-tuned pebble's adapter emits rmse_m / skill_vs_persistence
    // / hardware_badge alongside the forecast — same shape across
    // any future model-specialised forecast pebble.
    hfModelCard: variant === 'timeseries-ft' ? t.hf_model_card : undefined,
    rmse: variant === 'timeseries-ft' && num(t.rmse_m) != null
      ? `${num(t.rmse_m)!.toFixed(3)} m` : undefined,
    skillVsPersistence: variant === 'timeseries-ft' ? t.skill_vs_persistence : undefined,
    hardwareBadge: variant === 'timeseries-ft' ? t.hardware_badge : undefined,
  };
}

// ── Type-keyed composite register card renderer ─────────────────
//
// Multi-pebble dispatch: when several pebbles in the same stone
// declare `display.variant: register`, this renderer collects rows
// from ALL of them into a single card (vs one card per pebble).
//
// Per-pebble item-extraction heuristic: the adapter emits its rows
// under whichever field name fits the asset class (entrances /
// developments / schools / hospitals / items / features). The
// renderer scans known field names; an explicit `items` array
// always wins so future BYOD registers don't need a heuristic.
//
// `reg` label comes from the manifest icon or the first capitalized
// token of the title — no per-id hardcoding.
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

function _regLabelFromManifest(m: PebbleManifest): string {
  // Prefer a short SOURCE acronym from the manifest's source_name
  // ("MTA — subway/rail entrances register" → "MTA"); else fall back
  // to first capitalized token of the title.
  const src = m.provenance.source_name;
  const dashIdx = Math.min(...['—', '-', ':'].map(c => {
    const i = src.indexOf(c);
    return i < 0 ? Number.MAX_SAFE_INTEGER : i;
  }));
  const head = (dashIdx < Number.MAX_SAFE_INTEGER ? src.slice(0, dashIdx) : src).trim();
  // If the head is short enough (≤6 chars) use it; else first word.
  if (head.length > 0 && head.length <= 6) return head.toUpperCase();
  return (head.split(/\s+/)[0] || m.id).toUpperCase().slice(0, 6);
}

function _itemRow(reg: string, item: RegisterItem): NonNullable<Card['registers']>[number] {
  const label = (str(item.station_name) ?? str(item.development)
                ?? str(item.loc_name) ?? str(item.facility_name)
                ?? str(item.label) ?? str(item.name) ?? 'item');
  const distance = num(item.distance_m);
  const detail_bits: string[] = [];
  if (distance != null) detail_bits.push(`${distance} m`);
  const borough = str(item.borough);
  const routes = str(item.daytime_routes);
  if (routes) detail_bits.push(routes);
  else if (borough) detail_bits.push(borough);
  const sourceId = (str(item.station_id) ?? str(item.tds_num)
                    ?? str(item.loc_code) ?? str(item.fac_id)
                    ?? str(item.source_id) ?? null);
  return {
    reg, tier: 'empirical',
    label, detail: detail_bits.join(' · ') || null,
    sourceId, note: null,
  };
}

function buildRegisterComposite(
  registerManifests: PebbleManifest[],
  state: Final,
): Card | null {
  if (!registerManifests.length) return null;
  const rows: NonNullable<Card['registers']> = [];
  const docIds: string[] = [];
  const agencies: string[] = [];
  // Per-pebble cap so one super-dense register doesn't dominate.
  const PER_PEBBLE_CAP = 4;
  for (const m of registerManifests) {
    const v = (state as Record<string, unknown>)[m.id] as RegisterValue | undefined;
    if (!v) continue;
    const reg = _regLabelFromManifest(m);
    const items = _itemsFromRegisterValue(v);
    if (v.available === false || items.length === 0) {
      // Unavailable is not zero: only a register that could not be read
      // says so; one read with nothing in range reports 0.
      const radius = num((v as Record<string, unknown>).radius_m);
      rows.push({
        reg, tier: 'empirical',
        label: null, detail: null, sourceId: null,
        note: v.available === false
          ? (m.fallback.message ?? `${reg} register unavailable`)
          : `0 within ${radius != null ? `${radius} m` : 'range'}`,
      });
      continue;
    }
    for (const it of items.slice(0, PER_PEBBLE_CAP)) {
      rows.push(_itemRow(reg, it));
    }
    const doc = m.provenance.doc_id ?? m.id;
    docIds.push(doc);
    agencies.push(m.provenance.source_name);
  }
  if (!rows.length) return null;
  const fired = rows.filter(r => r.label).length;
  return {
    id: 'fsm-registers',
    stone: 'keystone', tier: 'empirical', variant: 'register',
    source: 'Civic OpenData', agency: `${agencies.length} register${agencies.length === 1 ? '' : 's'} · multi-agency join`,
    vintage: RIPRAP_VINTAGE,
    title: 'Nearby exposed assets',
    registers: rows,
    sub: `${fired} of ${rows.length} register rows have items · joined within range`,
    docId: docIds[0] ?? 'registers',
    citeId: 'registers',
    mapLayer: 'registers',
  };
}

// ── Type-keyed histogram card renderer ──────────────────────────
//
// Pebbles that declare `display.variant: histogram` and emit a
// normalized value shape:
//   { n, histogram: number[], headline_value, subhead_text, narrative,
//     radius_m?, years? }
// nyc311 is the canonical case; future "count me over time" pebbles
// (e.g. boston 311 trended, sea-level rise count series) get the same
// bespoke chrome by declaring the variant + emitting the shape.
type HistogramValue = {
  n?: number;
  histogram?: number[];
  headline_value?: string;
  subhead_text?: string;
  narrative?: string;
  radius_m?: number;
  years?: number;
};

function buildHistogramCard(m: PebbleManifest, value: unknown): Card | null {
  const t = value as HistogramValue | null;
  if (!t) return null;
  const n = num(t.n) ?? 0;
  // Honest negative ("0 calls") still surfaces — same all-clear contract
  // as the NWS / ida_hwm cards. The narrative explains the zero.
  const hist = Array.isArray(t.histogram) ? t.histogram : [];
  const headline = t.headline_value ?? `${n} calls`;
  const radius = num(t.radius_m);
  const years = num(t.years);
  const sparkSub = (radius != null && years != null)
    ? `Within ${radius} m · ${years} y window. Filtered to flood-relevant descriptors.`
    : undefined;
  const tier = (m.tier ?? 'proxy') as Card['tier'];
  const source = shortSource(m.provenance.source_name);
  return {
    id: `fsm-${m.id.replace(/_/g, '-')}`,
    stone: m.stone, tier, variant: 'histogram',
    source, agency: m.provenance.source_name,
    vintage: m.provenance.date_modified?.toString() ?? RIPRAP_VINTAGE,
    title: m.title,
    headline,
    subhead: t.subhead_text,
    histogram: hist.length ? hist : Array.from({ length: 12 }, () => Math.round(n / 12)),
    sparkSub,
    sub: t.narrative,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
    mapLayer: m.display.map_layer ? m.id : null,
  };
}

// ── Type-keyed raster card renderer ─────────────────────────────
//
// Pebbles that declare `display.variant: raster` or `raster-pred`
// and emit a normalized value shape:
//   { headline_value, subhead_text, narrative, raster_kind, illustrative,
//     ok?: bool }
// All raster pebbles (prithvi_water, future flood-mask
// models) flow through here — no per-pebble id check.
type RasterValue = {
  ok?: boolean;
  available?: boolean;
  headline_value?: string;
  subhead_text?: string;
  narrative?: string;
  raster_kind?: string;
  illustrative?: boolean;
  spatial_note?: string;
};

function buildRasterCard(m: PebbleManifest, value: unknown): Card | null {
  const t = value as RasterValue | null;
  if (!t) return null;
  // Both shapes used: raster-pred (model) sets `ok`; raster (baked)
  // doesn't gate. Drop only when an explicit ok=false is present
  // (the inference-offline case).
  if (t.ok === false || t.available === false) return null;
  const headline = t.headline_value;
  if (!headline) return null;  // adapter didn't emit the contract shape
  const variant: CardVariant =
    (m.display.variant === 'raster' || m.display.variant === 'raster-pred')
      ? m.display.variant
      : 'raster';
  const tier = (m.tier ?? 'modeled') as Card['tier'];
  const source = shortSource(m.provenance.source_name);
  return {
    id: `fsm-${m.id.replace(/_/g, '-')}`,
    stone: m.stone, tier, variant,
    source, agency: m.provenance.source_name,
    vintage: m.provenance.date_modified?.toString() ?? RIPRAP_VINTAGE,
    title: m.title,
    rasterKind: (t.raster_kind ?? 'prithvi') as 'prithvi' | 'buildings' | 'lulc',
    headline,
    subhead: t.subhead_text,
    sub: t.narrative,
    illustrative: t.illustrative ?? false,
    spatialNote: t.spatial_note,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
    mapLayer: m.display.map_layer ? m.id : null,
  };
}

function buildCapstoneMeta(final: FinalResult, wallSeconds?: number): Card {
  // How the briefing was produced, read from final.grounding and
  // final.compliance. `compliance` is a set of substring checks for
  // required disclosure phrases, not a quality score.
  const g = final.grounding;
  const isLlm = g?.tier === 'llm';
  const kept = g?.claims?.length ?? 0;
  const dropped = g?.dropped_claims?.length ?? 0;
  const c = final.compliance;
  const cites = citationList(final.citations).length;
  return {
    id: 'fsm-capstone-meta',
    stone: 'capstone', tier: 'modeled', variant: 'meta',
    source: isLlm ? 'LLM' : 'No LLM',
    agency: isLlm
      ? `Capstone synthesis · ${g?.model ?? 'LLM'} · ${g?.answer_mode === 'extractive'
          ? 'answer quoted word for word, other claims checked against cited sources'
          : 'claims checked against cited sources'}`
      : 'Capstone synthesis · evidence briefing built from source values (no LLM)',
    vintage: RIPRAP_VINTAGE,
    title: 'How this briefing was written',
    metaRows: [
      { k: 'mode', v: isLlm ? `LLM${g?.model ? `: ${g.model}` : ''}` : 'evidence briefing (no LLM)' },
      { k: 'claims checked', v: isLlm ? `${kept} kept, ${dropped} dropped` : 'n/a (no LLM)' },
      { k: 'disclosure checks', v: c ? `${c.n_passed}/${c.n_total} present` : '—' },
      { k: 'citations resolved', v: `${cites}` },
      { k: 'wall-clock', v: wallSeconds != null ? `${wallSeconds.toFixed(1)} s` : '—' },
    ],
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
 *    list     → tabular    (features[] becomes rows)
 *    chart    → meta       (no canonical chart shape yet; falls back to meta)
 *    map_only → null       (no card body; data only appears on the map)
 *
 * Chrome (source / agency / title / docId / cites) comes from
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
  headline: true, tabular: true, scalars: true, spark: true, histogram: true,
  timeseries: true, 'timeseries-ft': true, forecast: true, raster: true,
  'raster-pred': true, lulc: true, register: true, comparison: true, meta: true,
};

/** Set of pebble ids that already have a special builder above. The
 *  templated pass skips these; they appear via the curated path. */
const SPECIAL_BUILT_IDS = new Set<string>([
  // Migration in progress: each pebble drops out of this set as its
  // manifest gains a usable narration.template + (if needed) a
  // shaper. Migrated so far: sandy, noaa_tides, water_level,
  // lake_michigan_water_level, nws_obs, nws_alerts — all now flow
  // through the templated path using `{narrative}` placeholders
  // computed in each pebble's Python adapter.
  // microtopo migrated to templated scalars path
  // (manifest narration.template + adapter {narrative} field).
  // Touchstone
  // nyc311 dispatched via buildHistogramCard (display.variant: histogram).
  // Lodestone: the forecast pebbles (ttm_battery_surge, ttm_311_forecast,
  // floodnet_forecast) now flow through the type-keyed
  // buildTimeseriesForecast renderer below (display.variant + value shape).
  // Keystone — the four register pebbles now dispatch via
  // buildRegisterComposite (multi-pebble, variant: register). Drop
  // from this set so they participate in the type-keyed dispatch.
]);

/** Intents that run polygon (neighborhood) pebbles instead of point ones. */
const POLYGON_INTENTS = new Set(['neighborhood', 'development_check']);

/** True when a pebble belongs to the given intent's card scaffold. Keeps
 *  neighborhood-only pebbles off address pages (and vice versa) instead
 *  of rendering them as "No data" cards. */
export function pebbleInScope(m: PebbleManifest, intent: string | null | undefined): boolean {
  const want = intent && POLYGON_INTENTS.has(intent) ? 'polygon' : 'point';
  return (m.scope ?? 'point') === want;
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
  const tier = m.type === 'model' ? 'modeled'
             : m.type === 'live'  ? 'empirical'
             : 'empirical';
  const source = shortSource(m.provenance.source_name);
  const vintage = m.provenance.date_modified ?? RIPRAP_VINTAGE;
  const base: Card = {
    id: `pebble-${m.id}`,
    stone: m.stone,
    tier,
    variant: variant ?? 'meta',
    source,
    agency: m.provenance.source_name,
    vintage,
    title: m.title,
    docId: m.provenance.doc_id ?? m.id,
    citeId: m.provenance.doc_id ?? m.id,
    mapLayer: m.display.map_layer ? m.id : null,
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
      // both are present (Boston, Chicago) the card would show the
      // same value twice.
      'observed_ft_mllw', 'predicted_ft_mllw',
    ]);
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
        const label = FIELD_LABELS[k];
        if (SCALAR_IGNORE.has(k) || !label) continue;
        if (typeof v === 'number' && Number.isFinite(v)) {
          scalars.push({ value: `${v}`, label });
        }
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
    const v = value as {
      features?: { properties?: Record<string, unknown>; distance_m?: number }[];
      // socrata / ckan-records adapters: summary-shape with n_records +
      // a sample[] of plain row objects + top_by_*.
      // n_truncated=true means n_records hit the SQL LIMIT cap, so
      // the real count is >= n_records — render as "N+ records".
      sample?: Record<string, unknown>[];
      n_records?: number;
      n_truncated?: boolean;
      radius_m?: number;
      // local_corpus_with_ner (policy_corpus): retrieved passages, not
      // geospatial features or a records sample.
      rag_hits?: { doc_id?: string; citation?: string; page?: number;
                    text?: string; score?: number }[];
      n_hits?: number;
    };
    // Path A — GeoJSON-style features
    const feats = Array.isArray(v?.features) ? v.features : [];
    if (feats.length) {
      const cols = Object.keys(feats[0]?.properties ?? {});
      const rows: (string | number)[][] = [];
      for (const f of feats.slice(0, 8)) {
        const row: (string | number)[] = [];
        for (const c of cols) {
          const val = f.properties?.[c];
          row.push(typeof val === 'number' || typeof val === 'string' ? val : '—');
        }
        rows.push(row);
      }
      return { ...base, columns: cols.length ? cols : ['feature'], rows,
               sub: `${feats.length} feature${feats.length === 1 ? '' : 's'} within range` };
    }
    // Path B — socrata / ckan-records summary shape (city_311 pebbles).
    // Boston / Chicago / SF emit { n_records, sample, top_by_reason }.
    // Without this branch the card silently returned null, so users
    // saw "Boston 311 received 283 records" in the briefing paragraph
    // but no card under the Touchstone Stone.
    const sample = Array.isArray(v?.sample) ? v.sample : [];
    if (sample.length) {
      const cols = Object.keys(sample[0]);
      const rows: (string | number)[][] = sample.slice(0, 8).map((row) =>
        cols.map((c) => {
          const val = row[c];
          return typeof val === 'number' || typeof val === 'string' ? val : '—';
        }),
      );
      // Humanize the column headers so the card reads "Case title"
      // instead of "case_title". The raw API field names are kept on
      // the underlying data; only the rendered header swaps.
      const HEADER_LABELS: Record<string, string> = {
        // Boston Analyze CKAN — 311
        case_title: 'Case', reason: 'Reason', type: 'Type',
        open_dt: 'Opened', neighborhood: 'Neighborhood',
        // Chicago Socrata — 311
        sr_type: 'Type', sr_short_code: 'Code',
        status: 'Status', created_date: 'Opened',
        // SF Socrata — 311
        service_name: 'Service', service_subtype: 'Subtype',
        status_description: 'Status',
        requested_datetime: 'Opened',
        analysis_neighborhood: 'Neighborhood',
      };
      const prettyCols = cols.map((c) => HEADER_LABELS[c] ?? c);
      const n = v?.n_records ?? sample.length;
      const nLabel = v?.n_truncated ? `${n}+` : String(n);
      const rad = v?.radius_m;
      return {
        ...base, columns: prettyCols, rows,
        sub: rad
          ? `${nLabel} record${n === 1 ? '' : 's'} within ${rad} m`
          : `${nLabel} record${n === 1 ? '' : 's'}`,
      };
    }
    // Path C — local_corpus_with_ner's retrieved-passage shape
    // ({rag_hits: [{doc_id, citation, page, text, score}]}). Neither a
    // geospatial feature list nor a records sample, so it fell through
    // to the generic "no records" fallback message before this — a
    // real retrieval success (n_hits=1, n_entities=5 in the trace)
    // rendered as "Policy-corpus index unavailable" regardless.
    const ragHits = Array.isArray(v?.rag_hits) ? v.rag_hits : [];
    if (ragHits.length) {
      const rows: (string | number)[][] = ragHits.slice(0, 8).map((h) => [
        h.citation ?? h.doc_id ?? '—',
        h.page ?? '—',
        h.text ? `${h.text.slice(0, 140)}${h.text.length > 140 ? '…' : ''}` : '—',
      ]);
      const n = v?.n_hits ?? ragHits.length;
      return {
        ...base, columns: ['Source', 'Page', 'Excerpt'], rows,
        sub: `${n} passage${n === 1 ? '' : 's'} matched`,
      };
    }
    // No features, sample, or rag_hits — fall back to the pebble's
    // narration.template formatted against the value (e.g. nws_alerts
    // returns {n_active: 0, alerts: [], narrative: "No active NWS..."};
    // the narrative is the human-readable card body). If the template
    // also can't format, render the manifest's fallback message.
    const tabularNarrative = m.narration.template
      ? formatTemplate(m.narration.template, value)
      : null;
    if (tabularNarrative) return { ...base, variant: 'headline', headline: tabularNarrative };
    return { ...base, variant: 'headline', absent: 'Not available',
             sub: m.fallback.message ?? 'No records within range' };
  }
  // meta fallback (chart pebbles without a special builder)
  const metaRows: { k: string; v: string }[] = [];
  if (typeof value === 'object' && value !== null) {
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      const label = FIELD_LABELS[k];
      if (!label || v === null || typeof v === 'object') continue;
      metaRows.push({ k: label, v: String(v) });
      if (metaRows.length >= 6) break;
    }
  }
  return { ...base, variant: 'meta', metaRows,
           sub: m.narration.short ?? undefined };
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
  // Neighborhood evidence (sandy_nta, dep_*_nta, nyc311_nta, microtopo_nta,
  // dob_permits_nta) and every other pebble render through the manifest
  // loop below; only non-manifest outputs keep a curated builder.
  const cards: (Card | null)[] = [
    buildTerramindBuildings(f),
    buildTerramindLulc(f),
    // Capstone (only once we have something to summarise)
    hasFinal ? buildCapstoneMeta((final ?? { paragraph: '' }) as FinalResult, wallSeconds) : null,
  ];

  const curatedCards = cards.filter((c): c is Card => c != null);

  // Phase 2 — templated cards for every manifest pebble that didn't get a
  // curated special-builder card. New BYOD pebbles defined only in YAML
  // appear here automatically.
  const templatedCards: Card[] = [];
  const handledIds = new Set<string>();
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
  const inScope = (stoneId: string) =>
    (pebbleManifest.byStone[stoneId] ?? []).filter((m) => pebbleInScope(m, intent));
  for (const stone of pebbleManifest.stones) {
    // Multi-pebble composite dispatch: collect all variant: register
    // pebbles in this stone, render once via buildRegisterComposite.
    // Each register pebble is marked handled so the per-pebble loop
    // below skips it.
    const registerMs = inScope(stone.id)
      .filter(m => m.display.variant === 'register'
                   && !SPECIAL_BUILT_IDS.has(m.id));
    if (registerMs.length) {
      const composite = buildRegisterComposite(registerMs, f);
      if (composite) {
        composite.experimental = registerMs.some((m) => m.maturity === 'experimental');
        templatedCards.push(composite);
      }
      for (const m of registerMs) {
        handledIds.add(m.id);
        const v = obj((f as Record<string, unknown>)[m.id]);
        if (v?.available === false && !failedIds.has(m.id)) noData.push({ id: m.id, title: m.title });
      }
    }
    // Per-pebble loop — single-pebble bespoke variants + the generic
    // templated fallback. Type-keyed dispatch by display.variant.
    for (const m of inScope(stone.id)) {
      if (SPECIAL_BUILT_IDS.has(m.id) || handledIds.has(m.id)) continue;
      const value = (f as Record<string, unknown>)[m.id];
      let card: Card | null = null;
      if (m.display.variant === 'timeseries' || m.display.variant === 'timeseries-ft') {
        card = buildTimeseriesForecast(m, value);
      } else if (m.display.variant === 'raster' || m.display.variant === 'raster-pred') {
        card = buildRasterCard(m, value);
      } else if (m.display.variant === 'histogram') {
        card = buildHistogramCard(m, value);
      }
      if (!card) card = buildTemplated(m, value, failedIds.has(m.id));
      if (card?.absent === 'Not available' && !failedIds.has(m.id)) noData.push({ id: m.id, title: m.title });
      if (card) templatedCards.push({ ...card, experimental: m.maturity === 'experimental' });
    }
  }

  return {
    cards: [...curatedCards, ...templatedCards].map(dropUnfilled),
    stones: buildStoneTraces(trace),
    wallSeconds,
    emissions: (f as { emissions?: FindingsData['emissions'] }).emissions,
    noData,
  };
}

/** Per-step-event live-state mapper. The FSM action `step_X` writes to
 *  state key `X` (sometimes munged — e.g. `step_311` writes `nyc311`,
 *  `step_terramind` writes `terramind`). The SSE `step.result` payload
 *  is a slim summary (not the full doc body); cards adapt to whichever
 *  fields are present.
 *
 *  Mutates `live` in place and returns the keys that changed so callers
 *  can decide whether to re-render. */
export function applyStepEventToLiveState(
  live: Record<string, unknown>,
  stepName: string,
  result: unknown,
  ok: boolean,
): string[] {
  const STEP_TO_STATE: Record<string, string> = {
    sandy_inundation: 'sandy',
    dep_stormwater: 'dep',
    floodnet: 'floodnet',
    nyc311: 'nyc311',
    noaa_tides: 'noaa_tides',
    nws_alerts: 'nws_alerts',
    nws_obs: 'nws_obs',
    ttm_311_forecast: 'ttm_311_forecast',
    ttm_battery_surge: 'ttm_battery_surge',
    floodnet_forecast: 'floodnet_forecast',
    ida_hwm_2021: 'ida_hwm',
    prithvi_eo_v2: 'prithvi_water',
    microtopo_lidar: 'microtopo',
    mta_entrance_exposure: 'mta_entrances',
    nycha_development_exposure: 'nycha_developments',
    doe_school_exposure: 'doe_schools',
    doh_hospital_exposure: 'doh_hospitals',
    terramind_synthesis: 'terramind',
    terramind_lulc: 'terramind_lulc',
    terramind_buildings: 'terramind_buildings',
    eo_chip_fetch: 'eo_chip',
    geocode: 'geocode',
    // Neighborhood NTA chain
    sandy_nta: 'sandy_nta',
    dep_extreme_2080_nta: 'dep_extreme_2080_nta',
    dep_moderate_2050_nta: 'dep_moderate_2050_nta',
    dep_moderate_current_nta: 'dep_moderate_current_nta',
    nyc311_nta: 'nyc311_nta',
    microtopo_nta: 'microtopo_nta',
  };
  const key = STEP_TO_STATE[stepName];
  if (!key) return [];
  // A pebble the planner did not select reports {skipped: ...}: it did not
  // run, so it has no value (its card says "Not run"), never a finding.
  if ((result as Record<string, unknown> | null)?.skipped) return [];

  // Translate the slim summary shapes the FSM emits into the
  // doc-payload shapes the card builders expect. Mostly identity
  // (the summaries already nest the relevant fields), with a few
  // exceptions documented inline.
  if (stepName === 'sandy_inundation') {
    // FSM summary: { inside: bool }. Adapter expects state.sandy === true.
    const r = result as Record<string, unknown> | null;
    live[key] = ok && r?.inside === true ? true : (ok ? false : null);
  } else if (stepName === 'dep_stormwater') {
    // FSM summary: { dep_extreme_2080: 'label', dep_moderate_2050: 'label', ... }.
    // Adapter expects state.dep[scen] = { depth_class, depth_label }.
    // Reconstruct depth_class>0 from any non-empty label.
    const r = (result as Record<string, unknown>) ?? {};
    const dep: Record<string, unknown> = {};
    for (const [scen, label] of Object.entries(r)) {
      const lbl = typeof label === 'string' ? label : '';
      if (!lbl) continue;
      dep[scen] = { depth_class: 1, depth_label: lbl };
    }
    live[key] = Object.keys(dep).length ? dep : null;
  } else if (ok && result != null) {
    live[key] = result;
  } else {
    live[key] = null;
  }

  return [key];
}

/** What produced the briefing, in words: the mode line on screen and in
 *  print. An extractive answer is quoted, not model prose, so it does not
 *  say "LLM claims checked" for it. */
export function modeLine(g: { tier: string; model?: string; answer_mode?: string;
                              claims?: unknown[]; dropped_claims?: unknown[] } | null | undefined): string | null {
  if (!g) return null;
  if (g.tier !== 'llm') return 'Evidence briefing (no LLM)';
  const model = g.model ? ` (${g.model})` : '';
  const counts = `${g.claims?.length ?? 0} kept, ${g.dropped_claims?.length ?? 0} dropped`;
  if (g.answer_mode === 'extractive') {
    return `Extractive answer: sentences quoted word for word from the cited sources, chosen by the model${model} ` +
      `and checked by the lead rules. Other claims checked against cited sources: ${counts}`;
  }
  return `LLM claims checked against cited sources: ${counts}${model}`;
}
