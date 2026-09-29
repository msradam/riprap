/**
 * The register row reads each pebble's own narrative, which says whether
 * it counts every asset in range or only flood-exposed ones (gallery
 * critique: "8 exposed MTA entrances" when 40 were in range).
 */
import { describe, it, expect } from 'vitest';
import { RunState } from '$lib/client/runState.svelte';
import { pebbleManifest, type PebbleManifestResponse } from '$lib/stores/pebbleManifest.svelte';
import type { FinalResult } from '$lib/client/agentStream';
import g from '$lib/gallery/brooklyn-heights.json';

describe('register row', () => {
  pebbleManifest.setFromResponse(g.pebbles as unknown as PebbleManifestResponse, 'nyc');
  const card = RunState.fromFinal(g.final as unknown as FinalResult, g.address).findingsData.cards
    .find((c) => c.id === 'fsm-registers');
  const text = JSON.stringify(card);

  it('states the MTA count the pebble reported, not the listed rows', () => {
    const n = (g.final as unknown as { mta_entrances: { n_entrances: number } }).mta_entrances.n_entrances;
    expect(text).toContain(`${n} MTA subway entrances within 800 m`);
    expect(text).not.toMatch(/exposed MTA/);
  });

  it('says the school register lists only flood-exposed schools', () => {
    expect(text).toMatch(/flood-exposed NYC DOE schools/);
  });
});
