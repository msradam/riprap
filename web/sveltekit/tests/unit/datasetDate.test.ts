/** The FEMA row takes its citation's effective date instead of "at snapshot". */
import { describe, it, expect } from 'vitest';
import { withDatasetDate } from '$lib/client/briefingModel';
import type { Card } from '$lib/types/card';
import type { Citation } from '$lib/types/claim';

const card = (vintage: string) => ({ id: 'x', docId: 'fema_nfhl', citeId: 'fema_nfhl', vintage } as Card);
const cites = { fema_nfhl: { id: 'fema_nfhl', vintage: '2007-09-05' } as Citation };

describe('withDatasetDate', () => {
  it('uses the citation date when the card only says live', () => {
    expect(withDatasetDate(card('live'), cites).vintage).toBe('2007-09-05');
  });
  it('keeps a card date it already has, and a live source with no dataset date', () => {
    expect(withDatasetDate(card('2024-07-03'), cites).vintage).toBe('2024-07-03');
    expect(withDatasetDate(card('live'), { fema_nfhl: { id: 'fema_nfhl', vintage: 'live' } as Citation }).vintage).toBe('live');
    // A live source's fetch time is not a dataset date.
    expect(withDatasetDate(card('live'), { fema_nfhl: { id: 'fema_nfhl', vintage: '2026-09-29T21:38Z' } as Citation }).vintage).toBe('live');
  });
});
