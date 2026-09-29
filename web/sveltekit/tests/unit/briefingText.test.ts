import { describe, expect, it } from 'vitest';
import { asOfDate, asOfPhrase, citedIn, figureOf, findingOf, termsIn, tidy } from '$lib/client/briefingText';
import type { Card } from '$lib/types/card';

const card = (over: Partial<Card>): Card => ({
  id: 'pebble-x', stone: 'cornerstone', tier: 'empirical', variant: 'headline',
  source: 'Open Data', agency: 'Open Data', vintage: '2024-07-03', title: 'Dataset title', docId: 'x',
  ...over
});

describe('tidy', () => {
  it('moves the full stop before the citation mark', () => {
    const out = tidy([{ text: 'NAVD88 ', cite: 'a' }, { text: '.' }, { text: ' Next' }]);
    expect(out.map((p) => p.text).join('|')).toBe('NAVD88.|| Next');
  });
  it('puts punctuation on the first part of a multi-source run', () => {
    const out = tidy([{ text: 'rise ', cite: 'a' }, { text: '', cite: 'b' }, { text: '. 82', cite: 'c' }]);
    expect(out.map((p) => p.text)).toEqual(['rise.', '', ' 82']);
  });
  it('leaves uncited text alone', () => {
    expect(tidy([{ text: 'a ' }, { text: '.' }]).map((p) => p.text)).toEqual(['a ', '.']);
  });
});

describe('citedIn', () => {
  it('lists doc ids once, in reading order', () => {
    expect(citedIn([[{ text: 'a', cite: 'b' }, { text: 'c', cite: 'a' }], [{ text: 'd', cite: 'b' }]])).toEqual(['b', 'a']);
  });
});

describe('figureOf', () => {
  it('prefers the first scalar with its unit and label', () => {
    expect(figureOf(card({ scalars: [{ value: '2', label: 'Sensors nearby' }] }))).toEqual({ value: '2', label: 'Sensors nearby' });
    expect(figureOf(card({ scalars: [{ value: '37', unit: 'cm', label: 'Peak' }] }))?.value).toBe('37 cm');
  });
  it('skips a distance to a station or a year and takes the next scalar', () => {
    const gauge = card({
      scalars: [
        { value: '5.7', label: 'Distance to station (km)' },
        { value: '0.33', unit: 'ft', label: 'Stage' }
      ]
    });
    expect(figureOf(gauge)).toEqual({ value: '0.33 ft', label: 'Stage' });
  });
  it('leaves the figure empty when only a distance or a year is left', () => {
    expect(figureOf(card({ scalars: [{ value: '7.8', label: 'Distance to station (km)' }] }))).toBeNull();
    expect(figureOf(card({ scalars: [{ value: '2007', label: 'FIRM panel effective year' }], headline: '2007 panel' }))).toBeNull();
  });
  it('falls back to a leading number in the headline', () => {
    expect(figureOf(card({ headline: '82 calls' }))?.value).toBe('82');
    expect(figureOf(card({ headline: '0 m² new water within 500 m' }))?.value).toBe('0 m²');
    expect(figureOf(card({ headline: 'No active alerts' }))).toBeNull();
  });
});

describe('findingOf', () => {
  it('uses the templated body, not the narration headline (the Sandy misreading)', () => {
    const sandy = card({
      headline: 'The 2012 Hurricane Sandy inundation extent (NYC OEM) at this address.',
      body: 'This address sits outside the empirical 2012 Hurricane Sandy inundation footprint (NYC OEM).'
    });
    expect(findingOf(sandy)?.first).toBe('This address sits outside the empirical 2012 Hurricane Sandy inundation footprint (NYC OEM).');
  });
  it('splits after the first sentence', () => {
    expect(findingOf(card({ sub: 'Two sensors. Peak 1172 mm.' }))).toEqual({ first: 'Two sensors.', rest: 'Peak 1172 mm.' });
  });
  it('drops a headline that only repeats the source narration', () => {
    const short = 'The 2012 extent at this address.';
    expect(findingOf(card({ headline: short }), short)).toBeNull();
    expect(findingOf(card({ headline: 'No active alerts at this point.' }), short)?.first).toBe('No active alerts at this point.');
  });
});

describe('dates', () => {
  it('shortens ISO timestamps and retrieval stamps', () => {
    expect(asOfDate('2026-09-29T01:40Z')).toBe('2026-09-29');
    expect(asOfDate('retrieved 2026-07-11')).toBe('2026-07-11');
    expect(asOfDate('live')).toBe('live');
  });
  it('phrases a vintage for a source note', () => {
    expect(asOfPhrase('2024-07-03')).toEqual({ label: 'data as of', date: '2024-07-03' });
    expect(asOfPhrase('retrieved 2026-07-11')).toEqual({ label: 'retrieved', date: '2026-07-11' });
    expect(asOfPhrase('live')).toEqual({ label: 'live data', date: null });
  });
});

describe('termsIn', () => {
  it('shows only the terms the page uses, plus the tier words with a table', () => {
    expect(termsIn('elevation 48.2 ft NAVD88', false).map((t) => t.term)).toEqual(['NAVD88']);
    expect(termsIn('2050 SLR; 14 above-curb flood events', true).map((t) => t.term))
      .toEqual(['SLR', 'above-curb flood event', 'Measured, Modeled, Proxy, Synthetic']);
    expect(termsIn('SLRs and slurry', false)).toEqual([]);
  });
});
