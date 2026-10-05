/**
 * Each register is its own evidence row: its own finding (the pebble's
 * narrative, which says whether it counts every asset in range or only
 * flood-exposed ones), its own citation and its own date (gallery
 * critique: one row cited only NYCHA for four registers, and said
 * "8 exposed MTA entrances" when 40 were in range).
 */
import { describe, it, expect } from 'vitest';
import { RunState } from '$lib/client/runState.svelte';
import { pebbleManifest, type PebbleManifestResponse } from '$lib/stores/pebbleManifest.svelte';
import type { FinalResult } from '$lib/client/agentStream';
import g from '$lib/gallery/brooklyn-heights.json';

pebbleManifest.setFromResponse(g.pebbles as unknown as PebbleManifestResponse, 'nyc');
const cards = RunState.fromFinal(g.final as unknown as FinalResult, g.address).findingsData.cards
  .filter((c) => c.variant === 'register');

describe('register rows', () => {
  it('gives each register its own row, citation and date', () => {
    expect(cards.length).toBeGreaterThan(1);
    const cites = cards.map((c) => c.citeId);
    expect(new Set(cites).size).toBe(cards.length);
    for (const c of cards) expect(c.vintage).toBeTruthy();
  });

  it('states the MTA count the pebble reported, not the listed rows', () => {
    const n = (g.final as unknown as { mta_entrances: { n_entrances: number } }).mta_entrances.n_entrances;
    const mta = cards.find((c) => /MTA/.test(c.sub ?? ''));
    expect(mta?.sub).toContain(`${n} MTA subway entrances within 800 m`);
    expect(mta?.sub).not.toMatch(/exposed MTA/);
  });

  it('says the school register lists only schools inside a mapped flood extent', () => {
    expect(cards.some((c) => /public schools? inside a mapped flood extent/.test(c.sub ?? '') && /not every school/.test(c.sub ?? ''))).toBe(true);
  });

  it('closes each register sentence', () => {
    for (const c of cards) if (!c.absent) expect(c.sub).toMatch(/[.!?]$/);
  });
});
