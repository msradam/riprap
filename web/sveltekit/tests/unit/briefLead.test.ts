/** The "In brief" paragraph's bold first sentence, and report section heads
 *  named with their Stone. */
import { describe, it, expect } from 'vitest';
import { boldFirstSentence, stoneHead } from '$lib/client/briefingModel';

describe('boldFirstSentence', () => {
  it('bolds parts up to the first full stop and splits the part it ends in', () => {
    const out = boldFirstSentence([
      { text: 'Outside the 2012 extent', cite: 'sandy' },
      { text: ', in zone X', cite: 'fema' },
      { text: '. 82 complaints were filed', cite: 'nyc311' }
    ]);
    expect(out).toEqual([
      { text: 'Outside the 2012 extent', cite: 'sandy', bold: true },
      { text: ', in zone X', cite: 'fema', bold: true },
      { text: '.', cite: undefined, bold: true },
      { text: ' 82 complaints were filed', cite: 'nyc311' }
    ]);
  });

  it('keeps the cite on a head that ends its part, and ignores decimals', () => {
    const out = boldFirstSentence([{ text: 'Rain of 2.13 in/hr.', cite: 'dep' }, { text: ' More.' }]);
    expect(out[0]).toEqual({ text: 'Rain of 2.13 in/hr.', cite: 'dep', bold: true });
    expect(out[1]).toEqual({ text: ' More.' });
  });
});

describe('stoneHead', () => {
  it('names a role head with its Stone and keeps other heads', () => {
    expect(stoneHead('Hazard Reader')).toBe('Cornerstone, the hazard reader');
    expect(stoneHead('Live Observer.')).toBe('Touchstone, the live observer');
    expect(stoneHead('Projector')).toBe('Lodestone, the projector');
    expect(stoneHead('Something else')).toBe('Something else');
  });
});
