export type ErrorKey = 'geocoder' | 'all-silent' | 'grounding' | 'backend';

// Refusal classification was considered (Granite Guardian, then a
// planner-level shim) and dropped. Grounding is enforced by checking
// each written claim against its cited sources (see final.grounding).
// See experiments/06_granite_guardian/RESULTS.md for the decision record.
