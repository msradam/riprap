import type { Tier } from './tier';

/** v0.4.2 §15 — asset-pin shapes for the four register specialists. */
export type AssetKind = 'subway' | 'nycha' | 'school' | 'hospital';

export type ErrorKey = 'geocoder' | 'all-silent' | 'grounding' | 'backend';

// Refusal classification was considered (Granite Guardian, then a
// planner-level shim) and dropped. Grounding is enforced by checking
// each written claim against its cited sources (see final.grounding).
// See experiments/06_granite_guardian/RESULTS.md for the decision record.

export interface RegisterRow {
  name: string;
  elev: string;
  ada: boolean;
  fema: string;
  sandy: string;
  dep: string;
  asset: AssetKind;
  primaryTier: Tier;
}

export interface RegisterData {
  type: string;
  radius: string;
  count: number;
  rows: RegisterRow[];
  sourceLabel?: string;
  vintage?: string;
}
