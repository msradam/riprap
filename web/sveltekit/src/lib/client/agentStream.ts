/**
 * SSE client for the Riprap agent stream (`GET /api/agent/stream?q=…`).
 *
 * The FastAPI backend emits these events:
 *   hello            { query }
 *   plan_token       { delta }                     planner JSON, token-by-token
 *   plan             { intent, targets, rationale } planner finished
 *   deployment       { name, city, state }          routed deployment
 *   step             { step, ok, elapsed_s, result?, err?, target_label? }
 *   stone_start / stone_done                        Stone boundaries (unused here)
 *   final            { paragraph, grounding, citations, compliance, ... }
 *   error            { err }
 *   done             {}
 *
 * The briefing is not streamed: it arrives whole in `final`.
 */
import type { Tier } from '$lib/types/tier';

export interface PlanInfo {
  intent: string;
  targets?: unknown;
  specialists?: string[];
  rationale?: string;
  /** The user's question; empty for a bare address. */
  question?: string;
  focus?: { hazard?: string | null; time?: string | null; asset?: string | null };
  /** Pebble ids the planner chose to run. */
  pebbles?: string[];
}

/** A source in `final.consulted` / `final.not_checked`. */
export interface SourceRef {
  id: string;
  title: string;
  stone?: string;
}

export interface StepEvent {
  step: string;
  ok: boolean;
  elapsed_s?: number;
  result?: unknown;
  err?: string | null;
  tier?: Tier | null;
  claims?: number;
  /** Present on compare-intent step events: "PLACE A" or "PLACE B". */
  target_label?: string;
}

export type Maturity = 'production' | 'experimental';

export interface CitationMeta {
  doc_id: string;
  source?: string;
  title?: string;
  url?: string;
  license?: string;
  date_modified?: string;
  retrieved_at?: string;
  vintage?: string;
  maturity?: Maturity;
}

export interface GroundedClaim {
  section: string;
  text: string;
  doc_ids: string[];
  numbers: string[];
  place?: string;
}

export interface DroppedClaim extends GroundedClaim {
  reason: string;
}

/** How the briefing was produced. `llm`: model-written claims checked
 *  against their cited sources (failures land in dropped_claims).
 *  `no_llm`: evidence briefing built directly from pebble values. */
export interface Grounding {
  tier: 'llm' | 'no_llm';
  model?: string;
  attempts?: number;
  claims?: GroundedClaim[];
  dropped_claims?: DroppedClaim[];
  retried_claims?: GroundedClaim[];
  fallback_reason?: string;
  question?: string;
  answered?: boolean;
  /** "extractive": the answer quotes source sentences under a model-chosen lead. */
  answer_mode?: string;
  /** Set when LLM mode skipped the LLM because no question was asked. */
  note?: string;
}

/** Substring checks for required disclosure phrases. Not a quality score. */
export interface ComplianceChecks {
  passed: boolean;
  n_passed: number;
  n_total: number;
  failed: string[];
}

export interface FinalResult {
  paragraph: string;
  grounding?: Grounding;
  /** Keyed by doc_id. Legacy backends sent an array; handle both. */
  citations?: Record<string, CitationMeta> | CitationMeta[];
  compliance?: ComplianceChecks;
  audit?: unknown;
  intent?: string;
  plan?: PlanInfo;
  nta?: { nta_code: string; nta_name: string; borough: string; bbox: number[] } | null;
  /** The place the backend resolved the query to; null when it could not. */
  geocode?: { address?: string; borough?: string; lat?: number; lon?: number; match?: "exact" | "closest" } | null;
  trace?: StepEvent[];
  /** Present when intent === "compare". */
  targets?: Array<{ label: string; address: string }>;
  /** Per-call emissions ledger from app/emissions.py. Optional. */
  emissions?: EmissionsSummary;
  /** Sources that ran for this query. */
  consulted?: SourceRef[];
  /** Sources available here but not run for this question. */
  not_checked?: SourceRef[];
  /** Neighbourhood and district runs: the area outline (GeoJSON geometry, EPSG:4326). */
  area_boundary?: { geojson?: unknown; narrative?: string } | null;
  /** Models that contributed to this briefing. Missing on older gallery entries. */
  models?: ModelRow[];
  /** The deployment the query was routed to ("nyc"); null out of coverage. */
  deployment?: string | null;
}

/** One model row from the backend's `final.models`. */
export interface ModelRow {
  name: string;
  repo: string;
  where: string;
  how: 'loaded' | 'precomputed' | 'endpoint';
  latency_s?: number | null;
  pebble?: string;
  detail?: string;
  calls?: number;
}

/** Normalise `final.citations` (object keyed by doc_id, or legacy array). */
export function citationList(c: FinalResult['citations']): CitationMeta[] {
  if (!c) return [];
  return Array.isArray(c) ? c : Object.values(c);
}

/** How an energy figure was obtained. Hosted endpoints are always
 *  'unknown'; 'none' means no inference calls were made. */
export type EnergyStatus = 'measured' | 'estimated' | 'unknown' | 'mixed' | 'none';

export interface EmissionsCall {
  kind: string;
  model?: string;
  endpoint?: string;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  duration_s?: number;
  energy_status?: EnergyStatus;
  wh?: number | null;
  energy_note?: string;
}

/** Per-query inference ledger from app/emissions.py. Every field is
 *  optional because older gallery JSON may predate this shape.
 *  `total_wh` is null unless every call has a figure. */
export interface EmissionsSummary {
  n_calls?: number;
  n_measured?: number;
  energy_status?: EnergyStatus;
  total_wh?: number | null;
  total_duration_s?: number;
  tokens?: { prompt?: number | null; completion?: number | null; total?: number | null };
  calls?: EmissionsCall[];
  method?: string;
}

export interface AgentStreamHandlers {
  onHello?: (q: string) => void;
  onPlanToken?: (delta: string) => void;
  onPlan?: (plan: PlanInfo) => void;
  onStep?: (s: StepEvent) => void;
  onFinal?: (f: FinalResult) => void;
  onError?: (err: string) => void;
  onDone?: () => void;
  /** Fired after the backend resolves the deployment for this query
   *  (post-geocode). `name` is the deployment directory name (e.g.
   *  `boston`) or null when out-of-coverage. Used by /q/[queryId] to
   *  swap the header chip + reload the pebble scaffold so the UI
   *  renders the routed-to city, not the server's boot deployment. */
  onDeployment?: (d: { name: string | null; city?: string | null; state?: string | null }) => void;
}

export interface AgentStream {
  close(): void;
}

export function openAgentStream(query: string, handlers: AgentStreamHandlers): AgentStream {
  const url = `/api/agent/stream?q=${encodeURIComponent(query)}`;
  const es = new EventSource(url);

  function on<T>(name: string, fn: (data: T) => void) {
    es.addEventListener(name, (e) => {
      try {
        fn(JSON.parse((e as MessageEvent).data) as T);
      } catch {
        /* ignore parse errors */
      }
    });
  }

  on<{ query: string }>('hello', (d) => handlers.onHello?.(d.query));
  on<{ delta: string }>('plan_token', (d) => handlers.onPlanToken?.(d.delta));
  on<PlanInfo>('plan', (d) => handlers.onPlan?.(d));
  on<{ name: string | null; city?: string | null; state?: string | null }>(
    'deployment', (d) => handlers.onDeployment?.(d));
  on<StepEvent>('step', (d) => handlers.onStep?.(d));
  on<FinalResult>('final', (d) => handlers.onFinal?.(d));
  on<{ err: string }>('error', (d) => handlers.onError?.(d.err));
  es.addEventListener('done', () => {
    handlers.onDone?.();
    es.close();
  });
  es.addEventListener('error', () => {
    handlers.onError?.('SSE connection error');
    es.close();
  });

  return { close: () => es.close() };
}
