export type ErrorKey = 'geocoder' | 'all-silent' | 'grounding' | 'backend' | 'no-backend';

// Refusal classification was considered (Granite Guardian, then a
// planner-level shim) and dropped. Grounding is enforced by checking
// each written claim against its cited sources (see final.grounding).
// See experiments/06_granite_guardian/RESULTS.md at git tag v0.7.0 for the decision record.
