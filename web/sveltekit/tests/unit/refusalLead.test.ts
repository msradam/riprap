import { describe, it, expect } from 'vitest';
import { splitSentence } from '$lib/client/briefingModel';

describe('splitSentence', () => {
  it('takes the refusal sentence off its paragraph', () => {
    const r = splitSentence([{ text: 'Riprap does not answer this question. It reports public flood evidence.' }]);
    expect(r?.sentence).toBe('Riprap does not answer this question.');
    expect(r?.parts).toEqual([{ text: 'It reports public flood evidence.' }]);
  });

  it('leaves a cited or unpunctuated opening alone', () => {
    expect(splitSentence([{ text: 'Outside the extent.', cite: 'sandy' }])).toBeNull();
    expect(splitSentence([{ text: 'no full stop' }])).toBeNull();
  });
});
