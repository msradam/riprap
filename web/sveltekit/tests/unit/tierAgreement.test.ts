/**
 * Pass 2 critique P0: the evidence table said "Measured" for sources the
 * source notes called Modeled or Proxy (DEP scenarios, 311, FEMA). Both
 * now read the manifest's declared tier; this fails if they drift apart.
 */
import { describe, it, expect } from 'vitest';
import { RunState } from '$lib/client/runState.svelte';
import { pebbleManifest, type PebbleManifestResponse } from '$lib/stores/pebbleManifest.svelte';
import type { FinalResult } from '$lib/client/agentStream';
import hollis from '$lib/gallery/hollis.json';
import qn12 from '$lib/gallery/qn12-complaints.json';

describe.each([['hollis', hollis], ['qn12-complaints', qn12]])('%s', (_name, g) => {
  pebbleManifest.setFromResponse(g.pebbles as unknown as PebbleManifestResponse, 'nyc');
  const run = RunState.fromFinal(g.final as unknown as FinalResult, g.address);
  const cites = run.briefing.citations;

  it('every found card has the tier of its citation', () => {
    const pairs = run.findingsData.cards
      .filter((c) => !c.absent && cites[c.citeId ?? c.docId])
      .map((c) => [c.docId, c.tier, cites[c.citeId ?? c.docId].tier]);
    expect(pairs.length).toBeGreaterThan(0);
    for (const [doc, card, cite] of pairs) expect(card, doc as string).toBe(cite);
  });

  it('a modeled or proxy manifest tier is never shown as measured', () => {
    for (const c of run.findingsData.cards) {
      const declared = pebbleManifest.get(c.id.replace(/^pebble-/, ''))?.tier;
      if (declared && declared !== 'empirical') expect(c.tier, c.id).not.toBe('empirical');
    }
  });
});
