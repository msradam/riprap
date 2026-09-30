/**
 * Cross-component "briefing is done" signal + snapshot for export-PDF.
 *
 * `ready` flips true only after the streaming pipeline has produced a
 * grounded briefing. The header's "export PDF" button keys off this —
 * premature print of a half-streamed briefing is bad UX.
 *
 * `persistSnapshot` stashes the curated payload in localStorage under
 * `riprap:print:<queryId>` so the dedicated print tab (opened with
 * `window.open`) can hydrate from it without re-running the pipeline.
 */
import type { BriefingBlock, Citation, ClaimPart } from '$lib/types/claim';
import type { RunState } from '$lib/client/runState.svelte';
import type { EvidenceCard, Kind, Section } from '$lib/client/briefingModel';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';

export interface PrintSnapshot {
  queryId: string;
  queryText: string;
  /** A gallery snapshot or a live run. Older snapshots lack it and print
   *  their live readings as "live". */
  origin?: 'gallery' | 'live';
  intent: string | null;
  specialists: number;
  blocks: BriefingBlock[];
  citations: Record<string, Citation>;
  generatedAt: string;
  /** The place the backend resolved the query to (address, or district
   *  with its NTA name). Optional: older snapshots lack it. */
  resolvedPlace?: string | null;
  /** The fields below are optional for the same reason. */
  question?: string | null;
  /** The reader-facing mode line, e.g. "Evidence briefing (no LLM)". */
  mode?: string | null;
  /** A question run in no-LLM mode that produced no Answer section. */
  unanswered?: boolean;
  /** Undefined when the payload predates the consulted list. */
  consulted?: { title: string; failed: boolean }[];
  /** Sources that ran but returned no data or were unavailable. */
  noData?: string[];
  notChecked?: string[];
  /** The report as the briefing page sets it (briefingModel). Snapshots
   *  saved before the report layout lack these and print as missing. */
  kind?: Kind;
  lead?: string | null;
  leadLabel?: string;
  answer?: ClaimPart[][];
  /** The first answer paragraph is the key sentence; the rest support it. */
  keyed?: boolean;
  scope?: ClaimPart[][];
  body?: Section[];
  outOfScope?: ClaimPart[][];
  checks?: string | null;
  /** Doc ids the answer cites, in reading order. */
  cited?: string[];
  evidence?: {
    groups: { key: string; name: string; role: string | null; cards: EvidenceCard[]; closed?: boolean }[];
    findings: Record<string, { first: string; rest: string } | null>;
    notRun: string[];
  };
}

/** The three source lists shown above the briefing body and in print.
 *  Each says only what the payload knows:
 *  - consulted: the sources chosen for the question, with steps that
 *    reported ok: false flagged (and added when missing from the list).
 *    Undefined when the payload predates the list and nothing failed.
 *  - noData: sources that ran and returned nothing or were marked
 *    unavailable (the muted "Not available" cards).
 *  - notChecked: sources available for this kind of place that were not
 *    run for the question. Undefined on payloads that predate it. */
export function sourceLists(run: RunState) {
  const f = run.finalResult;
  const failed = run.failedSteps;
  let consulted: { id: string; title: string; failed: boolean }[] | undefined;
  if (f?.consulted || failed.length) {
    consulted = (f?.consulted ?? []).map((c) => ({ id: c.id, title: c.title, failed: failed.includes(c.id) }));
    // Plain arrays: these are local lookups in a pure function, not reactive state.
    const known = [...(f?.consulted ?? []), ...(f?.not_checked ?? [])].map((c) => c.id);
    for (const id of failed) {
      if (!known.includes(id)) consulted.push({ id, title: pebbleManifest.byId[id]?.title ?? id, failed: true });
    }
    // Failures first, so a closed list still leads with them.
    consulted.sort((x, y) => Number(y.failed) - Number(x.failed));
  }
  // With a consulted list, only its members ran; older payloads ran all.
  const ran = f?.consulted ? f.consulted.map((c) => c.id) : null;
  const noData = (run.findingsData.noData ?? [])
    .filter((s) => !ran || ran.includes(s.id))
    .map((s) => s.title);
  return {
    consulted,
    /** False when `consulted` holds only failed steps (older payloads). */
    hasConsultedList: !!f?.consulted,
    noData,
    notChecked: f?.not_checked?.map((c) => c.title),
  };
}

/** Coarse pipeline phase, surfaced in the AppHeader status indicator
 *  so a user staring at a half-rendered page knows what's happening.
 *  Phases are picked from the SSE event stream in /q/[queryId]/+page.svelte. */
export type RunPhase =
  | 'idle'
  | 'planning'      // planner JSON is streaming
  | 'specialists'   // FSM is firing data Stones (cornerstone → lodestone)
  | 'reconciling'   // Capstone is composing the briefing (arrives whole in `final`)
  | 'done'
  | 'stopped'       // ended on purpose: refused, or the place did not resolve
  | 'error';

class BriefingState {
  ready = $state(false);

  /** Live phase indicator. AppHeader reads these to render the status
   *  pill. /q/[queryId]/+page.svelte is the canonical writer.
   */
  phase = $state<RunPhase>('idle');
  /** The most recent step name the FSM emitted, e.g. `floodnet` or
   *  `nyc311`. Pretty-printed by AppHeader via STEP_LABELS. */
  activeStep = $state<string | null>(null);
  /** How many specialists have fired (any non-error status) so far. */
  firedCount = $state(0);
  /** Total specialists registered for this run. Set when the planner
   *  resolves an intent or when the FSM trace settles. */
  totalSpecialists = $state(0);
  /** Last error message — shown in the header status when phase = error. */
  errorMessage = $state<string | null>(null);

  reset() {
    this.ready = false;
    this.phase = 'idle';
    this.activeStep = null;
    this.firedCount = 0;
    this.totalSpecialists = 0;
    this.errorMessage = null;
  }

  markReady() {
    this.ready = true;
    this.phase = 'done';
    this.activeStep = null;
  }

  markError(msg: string) {
    this.phase = 'error';
    this.errorMessage = msg;
  }

  /** A run that ended without a briefing on purpose (a refusal, an
   *  unresolved place). Not an error: the pill shows it in neutral ink. */
  markStopped(msg: string) {
    this.phase = 'stopped';
    this.activeStep = null;
    this.errorMessage = msg;
  }
}

export const briefingState = new BriefingState();

const STORAGE_PREFIX = 'riprap:print:';

export function snapshotKey(queryId: string): string {
  return STORAGE_PREFIX + queryId;
}

export function persistSnapshot(snap: PrintSnapshot): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(snapshotKey(snap.queryId), JSON.stringify(snap));
  } catch {
    /* quota / private mode — print tab will fall back to "no snapshot" */
  }
}

export function loadSnapshot(queryId: string): PrintSnapshot | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(snapshotKey(queryId));
    return raw ? (JSON.parse(raw) as PrintSnapshot) : null;
  } catch {
    return null;
  }
}
