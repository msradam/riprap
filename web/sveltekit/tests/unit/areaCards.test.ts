/**
 * Refactor 6: district and neighbourhood (*_nta) cards show their value,
 * say "Not available" when the source failed (never 0), and "Not run"
 * when the planner did not select them. One case per card type, built
 * through the same path the gallery uses (RunState.fromFinal).
 */
import { describe, it, expect } from 'vitest';
import { RunState } from '$lib/client/runState.svelte';
import { pebbleManifest, type PebbleManifestResponse } from '$lib/stores/pebbleManifest.svelte';
import type { FinalResult } from '$lib/client/agentStream';
import g from '$lib/gallery/qn12-complaints.json';

pebbleManifest.setFromResponse(g.pebbles as unknown as PebbleManifestResponse, 'nyc');
const base = g.final as unknown as Record<string, unknown>;
const ids = ['sandy_nta', 'dep_extreme_2080_nta', 'dep_moderate_2050_nta', 'dep_moderate_current_nta',
             'microtopo_nta', 'nyc311_nta', 'dob_permits_nta'];

function card(id: string, value: unknown, stepOk = true) {
  const trace = (base.trace as Record<string, unknown>[]).map((t) =>
    t.step === id ? { ...t, ok: stepOk, result: stepOk ? value : null, err: stepOk ? null : 'HTTP 503' } : t);
  // A skipped pebble is only in the trace; the backend writes no value for it.
  const skipped = !!(value as Record<string, unknown> | null)?.skipped;
  const final = { ...base, trace } as Record<string, unknown>;
  if (skipped) delete final[id]; else final[id] = value;
  return RunState.fromFinal(final as unknown as FinalResult, g.address).findingsData.cards
    .find((c) => c.id === `pebble-${id}`);
}

const VALUES: Record<string, Record<string, unknown>> = {
  sandy_nta: { fraction: 0.0075, headline_value: '0.8% inside the 2012 Sandy extent', narrative: '0.8% of this area lies inside the 2012 Hurricane Sandy inundation extent.' },
  dep_extreme_2080_nta: { fraction_any: 0.164, headline_value: '16.4% modeled to flood', narrative: 'DEP Extreme: 16.4% of this area is modeled to flood.' },
  dep_moderate_2050_nta: { fraction_any: 0.033, headline_value: '3.3% modeled to flood', narrative: 'DEP Moderate 2050: 3.3% of this area is modeled to flood.' },
  dep_moderate_current_nta: { fraction_any: 0.02, headline_value: '2.0% modeled to flood', narrative: 'DEP Moderate current: 2.0% of this area is modeled to flood.' },
  microtopo_nta: { elev_median_m: 12.3, headline_value: 'median ground elevation 12.3 m', narrative: 'Median ground elevation 12.3 m.' },
  nyc311_nta: { n: 4376, headline_value: '4376 calls', narrative: '4376 NYC 311 flood and sewer complaints filed inside this area in the last 3 years.' },
  dob_permits_nta: { n_total: 57, headline_value: '57 active permits', narrative: '57 active NYC DOB construction permits inside this area.' },
};

describe('area cards', () => {
  for (const id of ids) {
    it(`${id}: leads with its value`, () => {
      const c = card(id, VALUES[id]);
      expect(c?.absent).toBeUndefined();
      expect(c?.headline).toBe(VALUES[id].headline_value);
      expect(c?.body).toBe(VALUES[id].narrative);
    });
    it(`${id}: a failed source is Not available, not zero`, () => {
      const c = card(id, null, false);
      expect(c?.absent).toBe('Not available');
      expect(c?.headline ?? '').not.toMatch(/\b0\b/);
    });
    it(`${id}: an unselected source is Not run`, () => {
      const c = card(id, { skipped: 'not selected for this question' });
      expect(c?.absent).toBe('Not run');
      expect(c?.sub).toBe('Not checked for this question.');
    });
  }
});
