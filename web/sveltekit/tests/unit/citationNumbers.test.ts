import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { briefingModel, citationOf, numberByAppearance, sortMarks } from '$lib/client/briefingModel';
import { citationFromMeta } from '$lib/client/parseBriefing';
import { RunState } from '$lib/client/runState.svelte';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import type { Citation, ClaimPart } from '$lib/types/claim';

const registry = (...ids: string[]) => Object.fromEntries(ids.map((id, i) => [id, citationFromMeta(i + 1, id)]));
const marks = (paras: ClaimPart[][], c: Record<string, Citation>) =>
  paras.flat().flatMap((p) => (p.cite ? [c[p.cite].n] : []));

describe('numberByAppearance', () => {
  it('numbers by first appearance, keeps ids, and puts uncited sources last in their old order', () => {
    const c = numberByAppearance(registry('sandy', 'dep_2080', 'dep_2050', 'dep_now', 'ida', 'nyc311'), ['sandy', 'dep_now', 'dep_2050', 'dep_2080', 'nyc311', 'sandy', 'ghost']);
    expect(Object.values(c).map((x) => `${x.n}:${x.id}`)).toEqual(['1:sandy', '2:dep_now', '3:dep_2050', '4:dep_2080', '5:nyc311', '6:ida']);
    expect(c.dep_now.docId).toBe('dep_now');
  });
});

describe('sortMarks', () => {
  it('sets the marks on one claim in ascending order', () => {
    const c = numberByAppearance(registry('a', 'b', 'c'), ['a', 'b', 'c']);
    const parts: ClaimPart[] = [
      { text: 'Outside the scenarios ', cite: 'c', tier: 'modeled' },
      { text: '', cite: 'a', tier: 'empirical' },
      { text: '', cite: 'b', tier: 'proxy' },
      { text: '. Next claim ', cite: 'a' }
    ];
    const out = sortMarks(parts, c);
    expect(out.map((p) => p.cite)).toEqual(['a', 'b', 'c', 'a']);
    expect(out.map((p) => p.tier)).toEqual(['empirical', 'proxy', 'modeled', undefined]);
    expect(out[0].text).toBe('Outside the scenarios ');
  });
});

describe('the Hollis address briefing', () => {
  const e = JSON.parse(readFileSync('src/lib/gallery/hollis.json', 'utf8'));
  pebbleManifest.setFromResponse(e.pebbles, e.deployment.name);
  const m = briefingModel(RunState.fromFinal(e.final, e.address), e.address);

  it('reads 1, 2, 3 ... in its In brief (was 1 2 5 4 3 11)', () => {
    // A later sentence may cite the stormwater maps again, so the test is on each number's first appearance.
    const first = [...new Set(marks(m.answer, m.citationsById))];
    expect(first).toEqual(first.map((_, i) => i + 1));
  });

  it('numbers the open evidence table in ascending order, the same numbers as the text', () => {
    const open = m.evidenceGroups.filter((g) => !g.closed).flatMap((g) => g.cards.flatMap((r) => r.parts ?? [r]));
    const n = open.map((c) => citationOf(c, m.citationsById)?.n).filter((x): x is number => !!x);
    expect(n).toEqual([...n].sort((a, b) => a - b));
    expect(m.citations.map((c) => c.n)).toEqual(m.citations.map((_, i) => i + 1));
    expect(m.citationsById.nyc311.id).toBe('nyc311');
  });
});
