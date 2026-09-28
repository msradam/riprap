import { describe, it, expect } from 'vitest';
import { citedDocIds, parseBriefing } from '$lib/client/parseBriefing';

describe('citedDocIds', () => {
  it('returns the doc ids cited in the text, not the whole registry', () => {
    const seed = {
      uncited: { id: 'uncited', n: 1, tier: 'empirical', source: '', title: '', docId: 'uncited', url: '', vintage: '', retrieved: '' },
    } as const;
    const { blocks, citations } = parseBriefing(
      '**Answer.**\nYes [fema_nfhl]. Outside the footprint [sandy_inundation].\n\n**Hazard Reader.**\nZone X [fema_nfhl].',
      { ...seed }
    );
    expect(citations.uncited).toBeDefined();
    expect([...citedDocIds(blocks)].sort()).toEqual(['fema_nfhl', 'sandy_inundation']);
  });

  it('is empty for a briefing with no citations', () => {
    expect(citedDocIds(parseBriefing('**Answer.**\nNo grounded evidence.').blocks).size).toBe(0);
  });
});
