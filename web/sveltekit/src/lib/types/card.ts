/**
 * Findings card schema — v0.4.4.
 *
 * The Findings region renders a stack of cards grouped by Stone. Each card
 * is one specialist's structured output, with explicit epistemic tiering
 * and a citation fan-out that ties back into the briefing prose.
 *
 * Body fields are variant-specific: only the fields a given variant
 * needs are populated. The renderer dispatches on `variant`.
 */
import type { Tier } from './tier';

/** Stone keys, fixed order. */
export type StoneKey =
  | 'cornerstone'
  | 'keystone'
  | 'touchstone'
  | 'lodestone'
  | 'capstone';

export const STONE_ORDER: StoneKey[] = [
  'cornerstone', 'keystone', 'touchstone', 'lodestone', 'capstone',
];

export type StoneMeta = { name: string; role: string; tag: string };

// Stone taglines — kept city-agnostic here since they're the *fallback*
// when a deployment's stones.yaml description hasn't loaded yet (or is
// empty in the out-of-coverage state). The city-specific phrasing comes from
// pebbleManifest.stones[].description, applied by StoneRegion and
// MapLegend so a per-query render reflects the routed deployment.
export const STONE_META: Record<StoneKey, StoneMeta> = {
  cornerstone: { name: 'Cornerstone', role: 'the hazard reader',  tag: "what the ground remembers" },
  keystone:    { name: 'Keystone',    role: 'the asset register', tag: "what's exposed" },
  touchstone:  { name: 'Touchstone',  role: 'the live observer',  tag: 'what has been reported and measured' },
  lodestone:   { name: 'Lodestone',   role: 'the projector',      tag: "what's coming" },
  capstone:    { name: 'Capstone',    role: 'the synthesizer',    tag: 'writes it all down with citations' },
};

/** Card body variants, one renderer per shape. */
export type CardVariant =
  | 'headline'
  | 'tabular'
  | 'scalars'
  | 'histogram'
  | 'register'
  | 'meta';

export type ScalarCell = { value: string; label: string; unit?: string };

/** One line of the capstone "Models in this briefing" list. */
export type ModelLine = {
  name: string;
  repo: string;
  /** Hugging Face page for the repo, or null when it is not a Hugging Face id. */
  href: string | null;
  where: string;
  how: string;
  latency: string | null;
};

/** A single Findings card. Most fields are variant-specific. */
export type Card = {
  /** Stable id used as the Svelte key. */
  id: string;
  stone: StoneKey;
  tier: Tier;
  variant: CardVariant;

  /** Header chrome — always shown. */
  source: string;       // short label, e.g. "FEMA"
  vintage: string;      // e.g. "2024-09" or "2024-Q3"

  /** Title row. */
  title: string;

  /** Footer chrome — always shown. */
  docId: string;
  citeId?: string | null;

  /** Set when the source produced nothing: a short label such as "Not
   *  available" or "Not run". The card renders as a muted absence line,
   *  never as a finding; `sub` carries the reason when there is one. */
  absent?: string;

  /** The pebble behind this card is marked experimental in its manifest. */
  experimental?: boolean;

  /** Variant-specific body fields. Only the relevant ones are populated. */
  headline?: string;
  body?: string;
  sub?: string;

  // scalars
  scalars?: ScalarCell[];

  // meta
  models?: ModelLine[];
};

/** Per-specialist run-state. v0.4.5 splits the v0.4.4 `ok|warn|error|silent`
 *  enum into distinct epistemic outcomes so the run-health tally
 *  stops conflating "spec'd silent" with "specialist crashed":
 *
 *    fired             — completed and produced output the reconciler used
 *    silent_by_design  — completed and correctly produced no output
 *                        (e.g. "no entrances within radius")
 *    errored           — failed to complete, no usable output
 *    not_invoked       — FSM skipped the specialist (precondition unmet
 *                        / feature flag off / never wired)
 *
 *  See V0.4.5_SPEC.md §1 for the full rationale and message-voice rules.
 */
export type SpecialistStatus =
  | 'fired'
  | 'silent_by_design'
  | 'errored'
  | 'not_invoked';

/** Per-Stone provenance member (specialist) summary used by the trace. */
export type StoneMember = {
  id: string;
  name: string;
  status: SpecialistStatus;
  tier?: Tier | null;
  ms?: number;
  /** One-line engineering-honest message ("no entrances within radius",
   *  "PLUTO join skipped: queried address not in NYC PLUTO dataset",
   *  "311 history fetch failed: HTTP 503 at NYC OpenData (3 retries)").
   *  Match v0.4.1–v0.4.4 voice — precise, slightly understated. */
  note?: string;
};

/** A Stone's provenance + counts, fed by the FSM trace. */
export type StoneTrace = {
  key: StoneKey;
  members: StoneMember[];
};

/** What the page loader hands the FindingsRegion. */
export type FindingsData = {
  cards: Card[];
  stones: StoneTrace[];
  /** Wall-clock seconds for the run; surfaced in RunHealthStrip. */
  wallSeconds?: number;
  /** Per-call inference emissions (energy + tokens). Surfaced as a
   *  chip in RunHealthStrip; full breakdown available via tooltip. */
  emissions?: import('$lib/client/agentStream').EmissionsSummary;
  /** Sources that ran but returned no value or were marked unavailable
   *  (failed steps excluded). Feeds the "Ran but returned no data" list. */
  noData?: { id: string; title: string }[];
};
