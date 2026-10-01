/**
 * SSE client for the Riprap agent stream (`GET /api/agent/stream?q=…`).
 *
 * The FastAPI backend emits these events:
 *   hello            { query }                      (unused here)
 *   plan             { intent, targets, rationale } planner finished
 *   deployment       { name, city, state }          routed deployment
 *   step             { step, ok, elapsed_s, result?, err?, target_label? }
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
  rationale?: string;
  /** The user's question; empty for a bare address. */
  question?: string;
  focus?: { hazard?: string | null; time?: string | null; asset?: string | null };
  /** Pebble ids the planner chose to run. */
  pebbles?: string[];
  /** On `final.plan` only: the planner's model calls; absent or empty
   *  when rules planned the query. */
  llm_calls?: unknown[];
}

/** True when a language model planned the query. */
export const planned = (plan: PlanInfo | null | undefined): boolean => !!plan?.llm_calls?.length;

/** True for an intent the planner answers with a statement instead of a
 *  briefing: the question is out of scope, or asks for something not built. */
export const refusedIntent = (intent: string | null | undefined): boolean =>
  intent === 'out_of_scope' || intent === 'not_implemented';

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

/** The kind of lead an answer takes. "yes", "no" and "partly" open it with
 *  that word and "count" with a figure. "facts" is the facts with no lead
 *  word, and "cannot_answer" says the sources do not answer. Two are set
 *  only by code and have no yes, no or count: "experimental" (the answer is
 *  formed by an experimental model alone) and "no_prediction" (the question
 *  asked whether a place will flood). */
export type AnswerLead =
  | 'yes' | 'no' | 'partly' | 'count' | 'facts' | 'cannot_answer' | 'experimental' | 'no_prediction';

/** How the briefing was produced. `llm`: model-written claims checked
 *  against their cited sources (failures land in dropped_claims).
 *  `no_llm`: no model was called. The answer was picked by code rules
 *  from the question's words (`answer_mode: "rules"`), or nothing
 *  answered and the evidence briefing stands (`answered: false`), or the
 *  query was refused. */
export interface Grounding {
  tier: 'llm' | 'no_llm';
  model?: string;
  attempts?: number;
  claims?: GroundedClaim[];
  dropped_claims?: DroppedClaim[];
  fallback_reason?: string;
  question?: string;
  /** False when the question got no answer; null when none was asked. */
  answered?: boolean | null;
  /** "extractive": the answer quotes model-chosen source sentences under a lead set by rule in code.
   *  "rules": lead and facts were chosen by code rules; no model was called.
   *  Null when neither a rule nor a model answered. */
  answer_mode?: 'extractive' | 'rules' | null;
  /** The fact the answer's lead rests on (synthesis.py `_lead_fact`):
   *  `in_lead` when the backend's lead sentence states it, else the doc
   *  whose first answer sentence does. Null or absent: none singled out. */
  lead_fact?: { doc_id: string; in_lead: boolean } | null;
  /** Null when no question was asked. */
  answer_lead?: AnswerLead | null;
  /** Set when LLM mode skipped the LLM because no question was asked. */
  note?: string;
}

export interface FinalResult {
  paragraph: string;
  grounding?: Grounding;
  /** Keyed by doc_id. Legacy backends sent an array; handle both. */
  citations?: Record<string, CitationMeta> | CitationMeta[];
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
  /** `endpoint`: an LLM endpoint was called. `loaded`: an experimental
   *  model ran in the server. `precomputed`: its saved output was read. */
  how: 'endpoint' | 'loaded' | 'precomputed';
  latency_s?: number | null;
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
  onPlan?: (plan: PlanInfo) => void;
  onStep?: (s: StepEvent) => void;
  onFinal?: (f: FinalResult) => void;
  onError?: (err: string) => void;
  onDone?: () => void;
  /** Fired after the backend resolves the deployment for this query
   *  (post-geocode). `name` is the deployment directory name (e.g.
   *  `chicago`) or null when out-of-coverage. Used by /q/[queryId] to
   *  swap the header chip + reload the pebble scaffold so the UI
   *  renders the routed-to city, not the server's boot deployment. */
  onDeployment?: (d: { name: string | null; city?: string | null; state?: string | null }) => void;
}

export interface AgentStream {
  close(): void;
}

/** The error reported when nothing answered at /api: the public static
 *  copy, or a server that is down. */
export const NO_BACKEND = 'no backend at /api';

export function openAgentStream(query: string, handlers: AgentStreamHandlers): AgentStream {
  const url = `/api/agent/stream?q=${encodeURIComponent(query)}`;
  const es = new EventSource(url);
  let opened = false;
  es.addEventListener('open', () => { opened = true; });

  function on<T>(name: string, fn: (data: T) => void) {
    es.addEventListener(name, (e) => {
      try {
        fn(JSON.parse((e as MessageEvent).data) as T);
      } catch {
        /* ignore parse errors */
      }
    });
  }

  on<PlanInfo>('plan', (d) => handlers.onPlan?.(d));
  on<{ name: string | null; city?: string | null; state?: string | null }>(
    'deployment', (d) => handlers.onDeployment?.(d));
  on<StepEvent>('step', (d) => handlers.onStep?.(d));
  on<FinalResult>('final', (d) => handlers.onFinal?.(d));
  es.addEventListener('done', () => {
    handlers.onDone?.();
    es.close();
  });
  // One listener for two events named "error": the backend's own event
  // (a MessageEvent with data) and the browser's connection failure.
  es.addEventListener('error', (e) => {
    const data = (e as MessageEvent).data;
    if (typeof data === 'string') {
      // The backend's error ends the run; closing here stops the browser
      // reconnecting and re-running the query.
      let err = data;
      try { err = (JSON.parse(data) as { err?: string }).err ?? data; } catch { /* plain text */ }
      handlers.onError?.(err);
    } else {
      // A connection that never opened found nothing listening at /api.
      handlers.onError?.(opened ? 'SSE connection error' : NO_BACKEND);
    }
    es.close();
  });

  return { close: () => es.close() };
}
