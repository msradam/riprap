/**
 * Fix pass 5: evidence cards show readable field labels (never a
 * snake_case key), source headers are not cut at a hyphen, and sources
 * that ran but returned nothing are collected for the Sources block.
 * Uses a recorded gallery payload (Red Hook, 2026-09-27).
 */
import { describe, it, expect } from 'vitest';
import { RunState } from '$lib/client/runState.svelte';
import { pebbleManifest, type PebbleManifestResponse } from '$lib/stores/pebbleManifest.svelte';
import type { FinalResult } from '$lib/client/agentStream';
import redHook from '$lib/gallery/red-hook.json';

describe('card labels and no-data sources', () => {
  pebbleManifest.setFromResponse(redHook.pebbles as unknown as PebbleManifestResponse, 'nyc');
  const final = redHook.final as unknown as FinalResult;
  // The gallery route's path: rebuild the run from the saved payload.
  const data = RunState.fromFinal(final, redHook.address).findingsData;

  it('shows no raw field keys on scalar or meta cards', () => {
    const labels = data.cards.flatMap((c) => [
      ...(c.scalars ?? []).map((s) => s.label),
      ...(c.metaRows ?? []).map((r) => r.k),
    ]);
    expect(labels.length).toBeGreaterThan(0);
    expect(labels.filter((l) => /_/.test(l))).toEqual([]);
  });

  it('keeps hyphenated source names whole', () => {
    expect(data.cards.map((c) => c.source)).toContain('NOAA CO-OPS');
  });

  it('lists unavailable registers and null or unavailable pebbles as no data', () => {
    const ids = (data.noData ?? []).map((s) => s.id);
    expect(ids).toContain('mta_entrances');
    expect(ids).toContain('floodnet_forecast');
    // A register with items is not "no data".
    expect(ids).not.toContain('doe_schools');
  });
});
