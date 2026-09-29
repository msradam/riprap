/** The "Briefing for:" line: OpenStreetMap strings compact to the Geosearch style. */
import { describe, it, expect } from 'vitest';
import { compactAddress } from '$lib/client/runState.svelte';

describe('compactAddress', () => {
  it('compacts OpenStreetMap strings', () => {
    expect(compactAddress('4970, Broadway, Inwood, Manhattan Community Board 12, Manhattan, New York County, New York, 10034, United States'))
      .toBe('4970 Broadway, Inwood, Manhattan');
    expect(compactAddress('Orchard Beach, The Bronx, Bronx County, New York, United States')).toBe('Orchard Beach, The Bronx');
  });
  it('leaves Geosearch addresses alone', () => {
    expect(compactAddress('90-01 183 STREET, Hollis, NY, USA')).toBe('90-01 183 STREET, Hollis, NY, USA');
  });
});
