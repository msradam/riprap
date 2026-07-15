/**
 * Regression for a real content duplication found 2026-07-15 evaluating
 * a live briefing: sandy.yaml's narration.short and narration.template
 * paraphrase the same sentence, so HeadlineBody rendered the same fact
 * twice on one card. isRedundantBody is the systemic guard.
 */
import { describe, it, expect } from 'vitest';
import { isRedundantBody } from '$lib/components/findings/cards/headlineRedundancy';

describe('isRedundantBody', () => {
  it('flags the real sandy.yaml paraphrase as redundant', () => {
    const headline = 'This address is within the empirical 2012 Hurricane Sandy inundation footprint.';
    const body = 'This address sits within the empirical 2012 Hurricane Sandy inundation footprint (NYC OEM).';
    expect(isRedundantBody(headline, body)).toBe(true);
  });

  it('does not flag a body that adds real facts (ida_hwm)', () => {
    const headline = 'Hurricane Ida (Sept 2021) empirical high-water marks observed near this location.';
    const body = 'USGS surveyed 1 Hurricane Ida high-water mark(s) within 800 m of this address; the highest observed water elevation was 4.2 ft (up to 0.3 ft above ground). Nearest mark: Visitation Pl., between Van Brunt St. and Richards St., Red Hook, Brooklyn (138 m away).';
    expect(isRedundantBody(headline, body)).toBe(false);
  });

  it('does not flag an unavailable-fallback headline against its descriptive body', () => {
    const headline = 'DEP extreme 2080 raster + GDB both unavailable.';
    const body = 'NYC DEP extreme stormwater scenario (2080 SLR) at this address.';
    expect(isRedundantBody(headline, body)).toBe(false);
  });

  it('empty inputs are never flagged', () => {
    expect(isRedundantBody('', 'something')).toBe(false);
    expect(isRedundantBody('something', '')).toBe(false);
  });
});
