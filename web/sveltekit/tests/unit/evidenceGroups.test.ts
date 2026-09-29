import { describe, expect, it } from 'vitest';
import { evidenceGroups, splitLead } from '$lib/client/briefingModel';
import type { Card, StoneKey } from '$lib/types/card';

const card = (id: string, stone: StoneKey, citeId?: string): Card => ({
  id, stone, tier: 'empirical', variant: 'headline', source: id, agency: id,
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
    expect(groups[1]).toMatchObject({ name: 'Cornerstone', role: 'the hazard reader' });
    expect(groups[1].cards.map((c) => c.id)).toEqual(['sandy']);
    // Every card appears exactly once.
    expect(groups.flatMap((g) => g.cards).length).toBe(cards.length);
  });

  it('has no first group when the answer cites nothing, and takes a label', () => {
    expect(evidenceGroups(cards, [])[0].key).toBe('cornerstone');
    expect(evidenceGroups(cards, ['sandy'], 'Behind the summary')[0].name).toBe('Behind the summary');
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
