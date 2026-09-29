/** A small Battery surge forecast (below the old display floor) still gets
 *  its evidence row, since the written briefing cites it. */
import { describe, it, expect } from 'vitest';
import { RunState } from '$lib/client/runState.svelte';
import { pebbleManifest, type PebbleManifestResponse } from '$lib/stores/pebbleManifest.svelte';
import type { FinalResult } from '$lib/client/agentStream';
import { isExperimentalRow } from '$lib/client/briefingModel';
import g from '$lib/gallery/hollis.json';

describe('Battery surge row', () => {
  it('is a card, grouped with the folded forecasts', () => {
    pebbleManifest.setFromResponse(g.pebbles as unknown as PebbleManifestResponse, 'nyc');
    const run = RunState.fromFinal(g.final as unknown as FinalResult, g.address);
    const surge = run.findingsData.cards.find((c) => c.docId.startsWith('ttm_battery'));
    expect((g.final as unknown as { ttm_battery_surge: { interesting: boolean } }).ttm_battery_surge.interesting).toBe(false);
    expect(surge).toBeTruthy();
    expect(isExperimentalRow(surge!)).toBe(true);
  });
});
