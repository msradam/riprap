/**
 * Per-query deployment routing — the regression seal in the live HTTP
 * path. Hits `/api/agent` against three city addresses + one in-CONUS
 * out-of-city, asserts the routing decision and
 * scrutinises pebble fan-out for cross-city leakage.
 *
 * Requires uvicorn already running on the configured baseURL (the
 * suite's standing convention). Run with no-LLM tier for speed:
 *
 *   RIPRAP_RECONCILER_TIER=no_llm RIPRAP_HEAVY_SPECIALISTS=0 \
 *     uvicorn web.main:app --host 127.0.0.1 --port 7860
 *   pnpm exec playwright test routing.spec.ts
 *
 * Each case asserts:
 *   - out.deployment === expected
 *   - lat / lon non-null
 *   - every fired pebble has ok=True (no KeyError(pebble_id) regressions
 *     of the kind 0a45710 fixed)
 *   - no NYC-only pebble id appears in a non-NYC trace
 */
import { test, expect, request } from '@playwright/test';

const NYC_ONLY_PEBBLES = [
  'sandy', 'ida_hwm',
  'microtopo', 'floodnet',
  'nyc311', 'noaa_tides', 'npcc4_slr', 'nws_water_forecast',
  'mta_entrances', 'nycha_developments', 'doe_schools', 'doh_hospitals',
  'dep_extreme_2080', 'dep_moderate_2050', 'dep_moderate_current',
];

const CITY_PREFIXED: Record<string, string> = {
  chicago_: 'chicago',
  lake_michigan_: 'chicago',
  seattle_: 'seattle',
  albany_:  'albany',
};

type Probe = { addr: string; expected: string | null };

const PROBES: Probe[] = [
  { addr: '189 Atlantic Avenue, Brooklyn, NY',                    expected: 'nyc' },
  { addr: '233 S Wacker Drive, Chicago, IL',                      expected: 'chicago' },
  { addr: '600 4th Avenue, Seattle, WA',                          expected: 'seattle' },
  { addr: '1 Civic Plaza NW, Albuquerque, NM',                    expected: null },
];

const PIPELINE_STEPS = new Set([
  'plan_heuristic', 'plan_intent', 'geocode', 'select_deployment',
  'assemble_legacy_state', 'reconcile_templated', 'step_reconcile',
]);

for (const { addr, expected } of PROBES) {
  test(`routes "${addr}" → ${expected ?? '(no-coverage)'}`, async ({ baseURL }) => {
    const ctx = await request.newContext({ baseURL, timeout: 90_000 });
    const r = await ctx.get('/api/agent?q=' + encodeURIComponent(addr));
    expect(r.ok()).toBeTruthy();
    const out = await r.json();

    if (expected === null) {
      // Out-of-coverage: deployment must be null AND only federal
      // (us_conus) pebbles may fire — never a NYC-only id.
      expect(out.deployment).toBeNull();
    } else {
      expect(out.deployment).toBe(expected);
      expect(out.lat).not.toBeNull();
      expect(out.lon).not.toBeNull();
    }

    // Per-pebble scrutiny: every fired pebble OK, no cross-city leakage.
    const trace = out.trace ?? [];
    for (const rec of trace) {
      const step = rec.step;
      if (PIPELINE_STEPS.has(step)) continue;
      expect(rec.ok, `pebble ${step} returned ok=False: ${rec.err}`).toBe(true);
      if (expected !== 'nyc') {
        expect(NYC_ONLY_PEBBLES, `NYC pebble ${step} fired for ${expected ?? 'no-coverage'} run`)
          .not.toContain(step);
      }
      for (const [prefix, owner] of Object.entries(CITY_PREFIXED)) {
        if (step.startsWith(prefix) && expected !== owner) {
          throw new Error(
            `City-specific pebble ${step} fired for ${expected ?? 'no-coverage'} (owner: ${owner})`
          );
        }
      }
    }
  });
}
