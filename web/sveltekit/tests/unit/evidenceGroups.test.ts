import { describe, expect, it } from 'vitest';
import { evidenceGroups, mergeDepScenarios, splitLead } from '$lib/client/briefingModel';
import type { Card, StoneKey } from '$lib/types/card';

const card = (id: string, stone: StoneKey, citeId?: string): Card => ({
  id, stone, tier: 'empirical', variant: 'headline', source: id,
  vintage: '2024', title: id, docId: id, citeId
});

describe('evidenceGroups', () => {
  const cards = [
    card('sandy', 'cornerstone'),
    card('ida', 'cornerstone'),
    card('floodnet', 'touchstone', 'floodnet_doc'),
    card('nyc311', 'touchstone'),
    card('npcc4', 'lodestone')
  ];

  it('leads with the cards the answer cites, in the answer order', () => {
    const groups = evidenceGroups(cards, ['nyc311', 'floodnet_doc', 'ida']);
    expect(groups[0]).toMatchObject({ key: 'answer', name: 'Behind the answer', role: null });
    expect(groups[0].cards.map((c) => c.id)).toEqual(['nyc311', 'floodnet', 'ida']);
  });

  it('groups the rest by Stone in Stone order with name and role, skipping empty Stones', () => {
    const groups = evidenceGroups(cards, ['ida']);
    expect(groups.map((g) => g.key)).toEqual(['answer', 'cornerstone', 'touchstone', 'lodestone']);
    expect(groups[1]).toMatchObject({ name: 'Cornerstone', role: 'Mapped hazards' });
    expect(groups[1].cards.map((c) => c.id)).toEqual(['sandy']);
    // Every card appears exactly once.
    expect(groups.flatMap((g) => g.cards).length).toBe(cards.length);
  });

  it('has no first group when the answer cites nothing, and takes a label', () => {
    expect(evidenceGroups(cards, [])[0].key).toBe('cornerstone');
    expect(evidenceGroups(cards, ['sandy'], 'Behind the summary')[0].name).toBe('Behind the summary');
  });
});

describe('DEP scenarios and experimental sources', () => {
  const dep = (docId: string, vintage = '2024-07-03'): Card => ({
    ...card(`pebble-${docId}`, 'cornerstone'), docId, tier: 'modeled', vintage, source: 'NYC DEP Stormwater Flood Map, Moderate'
  });
  const exp = (id: string, stone: StoneKey, experimental = true): Card => ({ ...card(id, stone), experimental });

  it('merges the DEP scenario cards into one Modeled row in scenario order, where the first stood', () => {
    const rows = mergeDepScenarios([card('sandy', 'cornerstone'), dep('dep_extreme_2080'), card('ida', 'cornerstone'), dep('dep_moderate_current'), dep('dep_moderate_2050')]);
    expect(rows.map((r) => r.id)).toEqual(['sandy', 'dep-scenarios', 'ida']);
    const row = rows[1];
    expect(row.parts?.map((p) => p.docId)).toEqual(['dep_moderate_current', 'dep_moderate_2050', 'dep_extreme_2080']);
    expect(row).toMatchObject({ tier: 'modeled', source: 'NYC DEP Stormwater Flood Map', headline: undefined, scalars: undefined });
  });

  it('merges the district (_nta) variants and leaves a single scenario alone', () => {
    expect(mergeDepScenarios([dep('dep_moderate_2050_nta'), dep('dep_extreme_2080_nta')])[0].parts?.length).toBe(2);
    expect(mergeDepScenarios([dep('dep_moderate_2050')]).map((r) => r.id)).toEqual(['pebble-dep_moderate_2050']);
  });

  it('puts the merged row behind the answer when the answer cites any scenario', () => {
    const groups = evidenceGroups([card('sandy', 'cornerstone'), dep('dep_moderate_current'), dep('dep_moderate_2050')], ['dep_moderate_2050']);
    expect(groups[0].cards.map((c) => c.id)).toEqual(['dep-scenarios']);
    expect(groups[1].cards.map((c) => c.id)).toEqual(['sandy']);
  });

  it('closes the table with one folded group of experimental sources, counted', () => {
    const cards = [
      card('fema', 'cornerstone'),
      exp('city-311', 'touchstone'),
      exp('water-level', 'touchstone'),
      { ...card('water-forecast', 'lodestone'), docId: 'nws_water_forecast' },
      { ...card('npcc4', 'lodestone'), docId: 'npcc4_slr' },
      { ...card('alerts', 'lodestone'), docId: 'nws_alerts' }
    ];
    const groups = evidenceGroups(cards, []);
    const last = groups[groups.length - 1];
    expect(last).toMatchObject({ key: 'experimental', name: 'Experimental sources (2)', closed: true });
    expect(last.cards.map((c) => c.id)).toEqual(['city-311', 'water-level']);
    // The Weather Service forecast, NPCC4 and the NWS alerts stay open; nothing is lost.
    expect(groups.find((g) => g.key === 'lodestone')?.cards.map((c) => c.id)).toEqual(['water-forecast', 'npcc4', 'alerts']);
    expect(groups.flatMap((g) => g.cards).length).toBe(cards.length);
    expect(groups.filter((g) => g.closed).length).toBe(1);
  });

  it('keeps an experimental source the answer cites behind the answer, open', () => {
    const groups = evidenceGroups([exp('city-311', 'touchstone'), exp('water-level', 'touchstone')], ['city-311']);
    expect(groups[0]).toMatchObject({ key: 'answer' });
    expect(groups[0].closed).toBeUndefined();
    expect(groups[0].cards.map((c) => c.id)).toEqual(['city-311']);
    expect(groups[1]).toMatchObject({ name: 'Experimental sources (1)', closed: true });
  });
});

describe('splitLead', () => {
  it('takes "Yes." off the sentence', () => {
    expect(splitLead([{ text: 'Yes. USGS surveyed 2 marks' }])).toEqual({ word: 'Yes', parts: [{ text: 'USGS surveyed 2 marks' }] });
  });
  it('sets a count large but keeps its sentence whole', () => {
    expect(splitLead([{ text: '4273 complaints were filed' }])).toEqual({ word: '4273', parts: [{ text: '4273 complaints were filed' }] });
  });
  it('has no lead for plain prose', () => {
    expect(splitLead([{ text: 'This address is outside' }]).word).toBeNull();
  });
});
