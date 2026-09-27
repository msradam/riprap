/**
 * State of one briefing run, shared by the live route (/q/[queryId], fed
 * by SSE events) and the static gallery (/gallery/[slug], fed by
 * replaying a saved `final` payload). Both routes hand a RunState to
 * ResultsView, so they render the same way.
 *
 * Map layers that need /api/layers/* fetches are written by the live
 * route only; the gallery leaves them empty.
 */
import type { FeatureCollection } from 'geojson';
import { adaptFinalToFindings, applyStepEventToLiveState } from './cardAdapter';
import { parseBriefing, citationFromMeta } from './parseBriefing';
import { citationList, type FinalResult, type PlanInfo, type StepEvent } from './agentStream';
import type { TraceNode } from '$lib/types/trace';
import type { ErrorKey } from '$lib/types/states';
import type { FindingsData } from '$lib/types/card';
import type { BriefingBlock, Citation } from '$lib/types/claim';
import { tierForStep } from '$lib/types/tier';

// Mirrors _QUESTION_WORDS in app/planner.py. The heuristic (no-LLM)
// planner leaves plan.question empty, so the page decides for itself
// whether the reader typed a question.
// ponytail: word list, so an address with a word such as "Will" in it
// reads as a question; use the planner's answer if that ever bites.
const QUESTION_WORDS = new Set(
  ('what whats how has have had is are was were will would does did do can could should ' +
   'which when where why who whom show tell list compare any many much').split(' ')
);

/** True when the query reads as a question rather than a bare place. */
export function looksLikeQuestion(q: string): boolean {
  if (q.includes('?')) return true;
  return (q.toLowerCase().match(/[a-z]+/g) ?? []).some((w) => QUESTION_WORDS.has(w));
}

export type AddressSource = 'geocode' | 'nta';
export interface Place { label: string; lat: number; lon: number; source: AddressSource }

/** Parse `final.paragraph` into briefing blocks plus a citation registry
 *  seeded from `final.citations` and numbered in registry order. */
export function briefingFromFinal(
  f: FinalResult | null | undefined
): { blocks: BriefingBlock[]; citations: Record<string, Citation> } {
  if (!f?.paragraph) return { blocks: [], citations: {} };
  const seed: Record<string, Citation> = {};
  citationList(f.citations).forEach((c, i) => {
    const docId = c.doc_id ?? (c as unknown as { id?: string }).id ?? `c${i + 1}`;
    seed[docId] = citationFromMeta(i + 1, docId, {
      source: c.source,
      title: c.title,
      url: c.url,
      vintage: c.vintage,
      retrieved: c.retrieved_at?.slice(0, 10),
      maturity: c.maturity
    });
  });
  const r = parseBriefing(f.paragraph, seed);
  const citations: Record<string, Citation> = {};
  let n = 1;
  for (const [id, c] of Object.entries(r.citations)) citations[id] = { ...c, n: n++ };
  return { blocks: r.blocks, citations };
}

/** Steps that share the Granite TTM r2 foundation model, grouped under a
 *  synthetic parent in the trace. */
const TTM_STEPS = new Set(['ttm_311_forecast', 'floodnet_forecast']);
const TTM_PARENT_ID = 'group-ttm-r2';

/** Per-step headline fields for the collapsed trace row. Unknown steps
 *  fall back to their first two scalar fields. */
const STEP_NOTE_KEYS: Record<string, string[]> = {
  sandy_inundation: ['inside'],
  dep_stormwater: ['dep_extreme_2080', 'dep_moderate_2050'],
  floodnet: ['n_sensors', 'n_events_3y'],
  nyc311: ['n'],
  noaa_tides: ['observed_ft_mllw', 'residual_ft', 'station'],
  nws_alerts: ['n_active'],
  nws_obs: ['p1h_mm', 'p6h_mm', 'station'],
  ttm_311_forecast: ['forecast_mean', 'forecast_peak'],
  ida_hwm_2021: ['n_within_800m', 'max_height_above_gnd_ft'],
  prithvi_eo_v2: ['nearest_distance_m'],
  prithvi_water: ['nearest_distance_m', 'n_polygons_within_500m'],
  microtopo_lidar: ['elev_m', 'pct_200m', 'relief_m'],
  mta_entrance_exposure: ['n_entrances', 'n_inside_sandy_2012', 'n_in_dep_extreme_2080'],
  nycha_development_exposure: ['n_developments', 'n_inside_sandy_2012', 'n_in_dep_extreme_2080'],
  doe_school_exposure: ['n_schools', 'n_inside_sandy_2012'],
  doh_hospital_exposure: ['n_hospitals', 'n_inside_sandy_2012'],
  floodnet_forecast: ['sensor_id', 'distance_m', 'forecast_28d'],
  terramind_synthesis: ['tim_chain', 'dem_mean_m'],
  rag_granite_embedding: ['hits'],
  gliner_extract: ['sources']
};

function fmtKV(k: string, v: unknown): string {
  if (typeof v === 'number') return `${k}=${Number.isInteger(v) ? v : v.toFixed(2)}`;
  if (typeof v === 'boolean') return `${k}=${v}`;
  if (typeof v === 'string') return `${k}=${v.length > 24 ? v.slice(0, 22) + '…' : v}`;
  return k;
}

function summarizeStepNote(
  step: string,
  result: unknown,
  err: string | null | undefined,
  status: TraceNode['status']
): string | undefined {
  if (status === 'error') return err ?? undefined;
  if (status === 'silent') return err ?? 'no data';
  if (result == null || typeof result !== 'object') return undefined;
  const r = result as Record<string, unknown>;
  const pairs: string[] = [];
  const fieldOrder = STEP_NOTE_KEYS[step];
  if (fieldOrder) {
    for (const k of fieldOrder) {
      if (r[k] !== undefined) pairs.push(fmtKV(k, r[k]));
      if (pairs.length >= 3) break;
    }
  } else {
    for (const [k, v] of Object.entries(r)) {
      if (v !== null && typeof v !== 'object') {
        pairs.push(fmtKV(k, v));
        if (pairs.length >= 2) break;
      }
    }
  }
  return pairs.join(' · ') || undefined;
}

function countAllNodes(n: TraceNode): number {
  return 1 + (n.children ?? []).reduce((s, c) => s + countAllNodes(c), 0);
}

type Rec = Record<string, unknown>;

/** Register assets (subway entrances, schools, NYCHA, hospitals) as map
 *  points, carrying the properties the map click popup shows. */
function buildRegisterPointsFc(fr: Rec): FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  const add = (
    key: string, listKey: string, kind: string,
    lat: string, lon: string, name: (e: Rec) => string, docId: (e: Rec) => string
  ) => {
    const block = fr[key] as Rec | null | undefined;
    if (!block || !Array.isArray(block[listKey])) return;
    for (const e of block[listKey] as Rec[]) {
      const la = Number(e[lat]); const lo = Number(e[lon]);
      if (!Number.isFinite(la) || !Number.isFinite(lo)) continue;
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lo, la] },
        properties: { kind, name: name(e), doc_id: docId(e), inside_sandy_2012: e['inside_sandy_2012'] === true }
      });
    }
  };
  add('mta_entrances', 'entrances', 'subway', 'entrance_lat', 'entrance_lon',
    (e) => `${e['station_name'] ?? '?'} (${e['daytime_routes'] ?? '?'})`,
    (e) => `mta_entrance_${e['station_id'] ?? ''}`);
  add('doe_schools', 'schools', 'school', 'school_lat', 'school_lon',
    (e) => String(e['loc_name'] ?? e['school_name'] ?? '?'),
    (e) => `doe_school_${e['loc_code'] ?? ''}`);
  // NYCHA carries centroids only; the polygon is not serialized.
  add('nycha_developments', 'developments', 'nycha', 'centroid_lat', 'centroid_lon',
    (e) => String(e['development'] ?? '?'),
    (e) => `nycha_dev_${e['tds_num'] ?? ''}`);
  add('doh_hospitals', 'hospitals', 'hospital', 'hospital_lat', 'hospital_lon',
    (e) => String(e['facility_name'] ?? '?'),
    (e) => `nyc_hospital_${e['fac_id'] ?? ''}`);
  return { type: 'FeatureCollection', features };
}

function polygons(v: unknown): FeatureCollection | undefined {
  const r = v as Rec | null | undefined;
  const pg = r?.ok ? (r.polygons_geojson as FeatureCollection | undefined) : undefined;
  return pg?.type === 'FeatureCollection' && (pg.features?.length ?? 0) > 0 ? pg : undefined;
}

export class RunState {
  plan = $state<PlanInfo | null>(null);
  planTokens = $state('');
  finalResult = $state.raw<FinalResult | null>(null);
  streamDone = $state(false);
  geocodeSucceeded = $state(false);
  errorState = $state<ErrorKey | null>(null);
  runWallSeconds = $state<number | undefined>(undefined);
  traceRoot = $state.raw<TraceNode>({
    id: 'root', name: 'briefing.run', status: 'ok', ms: 0, tier: null, children: []
  });
  /** Per-step results keyed by state name; cards stream in from these
   *  until `final` supersedes them. */
  liveResults = $state<Rec>({});
  liveTick = $state(0);

  address = $state<Place | null>(null);
  ntaCode = $state<string | null>(null);
  registerPointsFc = $state<FeatureCollection | undefined>(undefined);
  terramindLulcFc = $state<FeatureCollection | undefined>(undefined);
  terramindBuildingsFc = $state<FeatureCollection | undefined>(undefined);
  // Written by the live route from /api/layers/*; empty on the gallery.
  sandyFc = $state<FeatureCollection | undefined>(undefined);
  depFc = $state<FeatureCollection | undefined>(undefined);
  synFc = $state<FeatureCollection | undefined>(undefined);
  proxyFc = $state<FeatureCollection | undefined>(undefined);
  idaHwmFc = $state<FeatureCollection | undefined>(undefined);

  compareAddressA = $state<Place | null>(null);
  compareAddressB = $state<Place | null>(null);
  compareStepsA = $state<Rec>({});
  compareStepsB = $state<Rec>({});
  sandyFcA = $state<FeatureCollection | undefined>(undefined);
  depFcA = $state<FeatureCollection | undefined>(undefined);
  synFcA = $state<FeatureCollection | undefined>(undefined);
  proxyFcA = $state<FeatureCollection | undefined>(undefined);
  idaHwmFcA = $state<FeatureCollection | undefined>(undefined);
  sandyFcB = $state<FeatureCollection | undefined>(undefined);
  depFcB = $state<FeatureCollection | undefined>(undefined);
  synFcB = $state<FeatureCollection | undefined>(undefined);
  proxyFcB = $state<FeatureCollection | undefined>(undefined);
  idaHwmFcB = $state<FeatureCollection | undefined>(undefined);

  findingsData = $derived.by<FindingsData>(() => {
    void this.liveTick;
    // The planner's intent picks the card scaffold (point vs polygon
    // pebbles) while steps stream in; `final.intent` wins once it lands.
    const live = { intent: this.plan?.intent, ...this.liveResults };
    if (this.finalResult) {
      const merged = { ...live, ...this.finalResult } as Partial<FinalResult>;
      return adaptFinalToFindings(merged, this.traceRoot, this.runWallSeconds, true);
    }
    return adaptFinalToFindings(live, this.traceRoot, this.runWallSeconds, false);
  });

  briefing = $derived(briefingFromFinal(this.finalResult));

  /** The place the backend resolved, in its own words, so a reader can
   *  see at once when the wrong place was looked up. */
  resolvedPlace = $derived.by<string | null>(() => {
    const a = this.compareAddressA?.label;
    const b = this.compareAddressB?.label;
    if (a || b) return [a && `A: ${a}`, b && `B: ${b}`].filter(Boolean).join('; ');
    const addr = this.finalResult?.geocode?.address ?? this.address?.label ?? null;
    const nta = this.finalResult?.nta?.nta_name;
    if (addr && nta && !addr.includes(nta)) return `${addr} (${nta})`;
    return addr ?? nta ?? null;
  });

  /** Step names whose event reported ok: false, in run order. */
  failedSteps = $derived.by<string[]>(() => {
    const out: string[] = [];
    const walk = (n: TraceNode) => {
      if (n.status === 'error' && !out.includes(n.name)) out.push(n.name);
      for (const c of n.children ?? []) walk(c);
    };
    walk(this.traceRoot);
    return out;
  });

  /** The planner refused the question (out of scope). */
  refused = $derived((this.finalResult?.intent ?? this.plan?.intent) === 'out_of_scope');

  /** The run ended without evidence to show: refused, the place did not
   *  resolve, or the backend failed. Map and findings are hidden. */
  stopped = $derived(this.refused || this.errorState === 'geocoder' || this.errorState === 'backend');

  /** Per-tier feature counts for the map legend; zero-count layers are
   *  hidden from the legend. */
  mapFeatureCounts = $derived({
    empirical: (this.sandyFc?.features.length ?? 0) + (this.idaHwmFc?.features.length ?? 0),
    modeled: this.depFc?.features.length ?? 0,
    synthetic: (this.synFc?.features.length ?? 0) + (this.terramindLulcFc?.features.length ?? 0),
    proxy: this.proxyFc?.features.length ?? 0
  });

  /** Apply one `step` event. `fallbackLabel` names the address when the
   *  geocoder result has none. */
  applyStep(s: StepEvent, fallbackLabel: string): void {
    applyStepEventToLiveState(this.liveResults, s.step, s.result, s.ok);
    this.liveTick += 1;

    if (s.step === 'geocode') {
      const r = s.ok && s.result && typeof s.result === 'object' ? (s.result as Rec) : null;
      if (r && typeof r.lat === 'number' && typeof r.lon === 'number') {
        const place: Place = {
          label: typeof r.address === 'string' ? r.address : fallbackLabel,
          lat: r.lat, lon: r.lon, source: 'geocode'
        };
        if (s.target_label === 'PLACE A') this.compareAddressA = place;
        else if (s.target_label === 'PLACE B') this.compareAddressB = place;
        else this.address = place;
        this.geocodeSucceeded = true;
      } else if (!r) {
        this.errorState = 'geocoder';
      }
    }
    if (s.target_label === 'PLACE A') this.compareStepsA = { ...this.compareStepsA, [s.step]: s.result };
    else if (s.target_label === 'PLACE B') this.compareStepsB = { ...this.compareStepsB, [s.step]: s.result };

    if (s.step === 'nta_resolve' && s.ok && s.result && typeof s.result === 'object') {
      const r = s.result as Rec;
      const bbox = Array.isArray(r.bbox) ? (r.bbox as number[]) : null;
      const code = typeof r.nta_code === 'string' ? r.nta_code : null;
      if (bbox && bbox.length === 4 && code) {
        this.ntaCode = code;
        this.address = {
          label: typeof r.nta_name === 'string' ? r.nta_name : fallbackLabel,
          lon: (bbox[0] + bbox[2]) / 2,
          lat: (bbox[1] + bbox[3]) / 2,
          source: 'nta'
        };
      }
    }

    const status: TraceNode['status'] = !s.ok ? 'error' : (s.result == null && s.err == null ? 'silent' : 'ok');
    const elapsedMs = Math.round((s.elapsed_s ?? 0) * 1000);
    const isTtm = TTM_STEPS.has(s.step);
    const node: TraceNode = {
      id: `step-${countAllNodes(this.traceRoot)}`,
      name: s.step,
      status,
      ms: elapsedMs,
      tier: tierForStep(s.step),
      note: summarizeStepNote(s.step, s.result, s.err, status),
      // Raw structured payload, shown on click in the trace.
      output: s.result != null ? (s.result as object) : (s.err ?? null),
      error: status === 'error' ? (s.err ?? 'unknown error') : undefined,
      model: isTtm ? 'granite-timeseries-ttm-r2' : undefined
    };

    const root = { ...this.traceRoot, ms: (this.traceRoot.ms ?? 0) + elapsedMs };
    const children = [...(root.children ?? [])];
    if (!isTtm) {
      this.traceRoot = { ...root, children: [...children, node] };
      return;
    }
    let parent = children.find((n) => n.id === TTM_PARENT_ID);
    if (!parent) {
      parent = {
        id: TTM_PARENT_ID,
        name: 'forecasting.granite-timeseries-ttm-r2',
        status: 'fan', // auto-expand + excluded from leaf counts
        ms: 0,
        tier: 'modeled',
        model: 'granite-timeseries-ttm-r2',
        children: []
      };
      children.push(parent);
    }
    const kids = [...(parent.children ?? []), node];
    const updated: TraceNode = {
      ...parent,
      ms: (parent.ms ?? 0) + elapsedMs,
      note: `${kids.length} instance${kids.length === 1 ? '' : 's'}`,
      children: kids
    };
    this.traceRoot = { ...root, children: children.map((c) => (c.id === TTM_PARENT_ID ? updated : c)) };
  }

  applyFinal(f: FinalResult): void {
    this.finalResult = f;
    const fr = f as unknown as Rec;
    this.registerPointsFc = buildRegisterPointsFc(fr);
    // TerraMind LULC LoRA wins over the synthesis output when both fired.
    this.terramindLulcFc = polygons(fr.terramind_lulc) ?? polygons(fr.terramind) ?? this.terramindLulcFc;
    this.terramindBuildingsFc = polygons(fr.terramind_buildings) ?? this.terramindBuildingsFc;
  }

  /** Stream closed. Flags the all-silent state when the address resolved
   *  but no briefing came back. */
  finish(): void {
    this.streamDone = true;
    if (!this.finalResult?.paragraph?.trim() && !this.errorState && this.geocodeSucceeded) {
      this.errorState = 'all-silent';
    }
  }

  /** Rebuild a finished run from a saved `final` payload (gallery). */
  static fromFinal(f: FinalResult, label: string): RunState {
    const run = new RunState();
    run.plan = f.plan ?? (f.intent ? { intent: f.intent } : null);
    for (const s of f.trace ?? []) run.applyStep(s, label);
    run.applyFinal(f);
    run.finish();
    return run;
  }
}
