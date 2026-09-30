/** A row is dated as its citation is, so the table and the source lists agree. */
import { describe, it, expect } from 'vitest';
import { withDatasetDate } from '$lib/client/briefingModel';
import type { Card } from '$lib/types/card';
import type { Citation } from '$lib/types/claim';

const card = (vintage: string) => ({ id: 'x', docId: 'fema_nfhl', citeId: 'fema_nfhl', vintage } as Card);
const cites = (vintage: string) => ({ fema_nfhl: { id: 'fema_nfhl', vintage } as Citation });

describe('withDatasetDate', () => {
  it('takes the citation date over the manifest date, whatever each says', () => {
    expect(withDatasetDate(card('live'), cites('2007-09-05')).vintage).toBe('2007-09-05');
    expect(withDatasetDate(card('2026-05'), cites('retrieved 2026-07-11')).vintage).toBe('retrieved 2026-07-11');
    // A live reading is dated to its fetch; the phrase says "fetched".
    expect(withDatasetDate(card('live'), cites('2026-09-29T21:38Z')).vintage).toBe('2026-09-29T21:38Z');
  });
  it('keeps the manifest date on a card with no citation', () => {
    expect(withDatasetDate(card('2024-07-03'), {}).vintage).toBe('2024-07-03');
  });
});
