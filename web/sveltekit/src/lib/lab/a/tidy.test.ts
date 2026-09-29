import { describe, expect, it } from 'vitest';
import { tidy, dropLead } from './tidy';

describe('tidy', () => {
  it('moves the full stop before the citation mark', () => {
    const out = tidy([{ text: 'NAVD88 ', cite: 'a' }, { text: '.' }, { text: ' Next' }]);
    expect(out.map((p) => p.text).join('|')).toBe('NAVD88.|| Next');
  });
  it('puts punctuation on the first part of a multi-source run', () => {
    const out = tidy([{ text: 'rise ', cite: 'a' }, { text: '', cite: 'b' }, { text: '. 82', cite: 'c' }]);
    expect(out.map((p) => p.text)).toEqual(['rise.', '', ' 82']);
  });
  it('drops a leading count but not a lead word', () => {
    expect(dropLead([{ text: '533 street' }], '533')[0].text).toBe('street');
    expect(dropLead([{ text: 'Yes x' }], 'Yes')[0].text).toBe('Yes x');
  });
});
