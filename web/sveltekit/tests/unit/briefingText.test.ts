import { describe, expect, it } from 'vitest';
import { asOfDate, asOfPhrase, citedIn, figureOf, findingOf, keepTogether, leadClause, sharedStem, termsIn, tidy, withoutSubject } from '$lib/client/briefingText';
import type { Card } from '$lib/types/card';

const card = (over: Partial<Card>): Card => ({
  id: 'pebble-x', stone: 'cornerstone', tier: 'empirical', variant: 'headline',
  source: 'Open Data', vintage: '2024-07-03', title: 'Dataset title', docId: 'x',
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
  it('never shows a temperature', () => {
    expect(figureOf(card({ scalars: [{ value: '17.0', unit: '°C', label: 'Air temp' }] }))).toBeNull();
    expect(figureOf(card({ scalars: [{ value: '17.0', label: 'Temperature (C)' }, { value: '0.4', unit: 'in', label: 'Rain' }] }))).toEqual({ value: '0.4 in', label: 'Rain' });
    expect(figureOf(card({ headline: '17.0°C at JFK' }))).toBeNull();
  });
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
  it('falls back to a leading number in the headline, with its unit or noun', () => {
    expect(figureOf(card({ headline: '82 complaints' }))?.value).toBe('82 complaints');
    expect(figureOf(card({ headline: '0.5 events' }))?.value).toBe('0.5 events');
    expect(figureOf(card({ headline: '0 m² new water within 500 m' }))?.value).toBe('0 m²');
    // A noun is kept only when it closes the headline.
    expect(figureOf(card({ headline: '3 of 5 listed' }))?.value).toBe('3');
    expect(figureOf(card({ headline: 'No active alerts' }))).toBeNull();
  });
  it('names a bare count by the plural that ends its noun phrase', () => {
    expect(figureOf(card({ headline: '73 active NYC DOB construction permits inside this area since 2025-04-08: 0 inside the 2012 Sandy extent.' }))?.value).toBe('73 permits');
    // A bare headline value takes the noun from the dataset's title.
    expect(figureOf(card({ headline: '73', title: 'Active DOB construction permits inside the neighborhood' }))?.value).toBe('73 permits');
    // "filed" ends the phrase: no noun rather than a wrong one.
    expect(figureOf(card({ headline: '82 NYC 311 flood-related complaints filed within 200 m of this location.', title: 'NYC 311 flood-related complaints (5y)' }))?.value).toBe('82');
  });
  it('shows no figure for a gauge count: it is not a reading', () => {
    expect(figureOf(card({ scalars: [{ value: '0', label: 'Gauges in the area' }] }))).toBeNull();
    expect(figureOf(card({ scalars: [{ value: '3', label: 'Gauges in the area' }, { value: '0.28', unit: 'ft', label: 'Stream stage' }] })))
      .toEqual({ value: '0.28 ft', label: 'Stream stage' });
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
  });
  it('dates a live reading to its fetch and never prints "live" as a date', () => {
    // The backend dates a live reading to its fetch, or says "live".
    expect(asOfPhrase('2026-09-30T16:05Z', '2026-09-30T16:05Z')).toEqual({ label: 'fetched', date: '2026-09-30 16:05 UTC' });
    expect(asOfPhrase('live', '2026-09-30T16:05Z')).toEqual({ label: 'fetched', date: '2026-09-30 16:05 UTC' });
    expect(asOfPhrase('live', 'live')).toEqual({ label: 'live reading', date: null });
    expect(asOfPhrase('live')).toEqual({ label: 'live reading', date: null });
    // A dataset modified at a known time is a dataset date, not a fetch.
    expect(asOfPhrase('2026-09-30T01:38:23+0000', '2026-09-30T16:05Z')).toEqual({ label: 'data as of', date: '2026-09-30' });
  });
});

describe('termsIn', () => {
  it('shows only the terms the page uses, plus the tier words with a table', () => {
    expect(termsIn('elevation 48.2 ft NAVD88', false).map((t) => t.term)).toEqual(['NAVD88']);
    expect(termsIn('2050 SLR; 14 above-curb flood events', true).map((t) => t.term))
      .toEqual(['SLR', 'above-curb flood event', 'Measured, Modeled, Proxy']);
    expect(termsIn('SLRs and slurry', false)).toEqual([]);
    expect(termsIn('water level 1.2 ft above MLLW', false).map((t) => t.term)).toEqual(['MLLW']);
  });

  it('names the three tiers, and no synthetic one', () => {
    expect(termsIn('', true)).toEqual([{
      term: 'Measured, Modeled, Proxy',
      reading: expect.stringMatching(/indicate it indirectly\.$/)
    }]);
    expect(termsIn('', true)[0].reading).not.toMatch(/synthetic/i);
  });
});

describe('leadClause', () => {
  it('ends the lead at the first semicolon or colon outside parentheses', () => {
    expect(leadClause('Elevation 14.87 m; higher than 29% (the 29th percentile; low); HAND 0.0 m.')).toEqual({
      lead: 'Elevation 14.87 m;',
      tail: ' higher than 29% (the 29th percentile; low); HAND 0.0 m.'
    });
  });
  it('skips a short label and keeps a sentence without a break whole', () => {
    expect(leadClause('Experimental: 34 complaints in 512 days; about 0.3 a week.').lead).toBe('Experimental: 34 complaints in 512 days;');
    expect(leadClause('This address sits in FEMA flood zone X.')).toEqual({ lead: 'This address sits in FEMA flood zone X.', tail: '' });
  });
  it('does not take the label of an experimental forecast for a clause', () => {
    expect(leadClause('Experimental forecast: a peak surge of 0.4 ft at the Battery in the next 96 hours; the model is not a measurement.').lead)
      .toBe('Experimental forecast: a peak surge of 0.4 ft at the Battery in the next 96 hours;');
  });
});

describe('withoutSubject', () => {
  it('drops a leading subject and capitalises the rest', () => {
    expect(withoutSubject('This address sits in FEMA flood zone X, per NFHL.')).toBe('In FEMA flood zone X, per NFHL.');
    expect(withoutSubject('This address is outside the modeled flooding.')).toBe('Outside the modeled flooding.');
    expect(withoutSubject('This area sits near a sensor.')).toBe('Near a sensor.');
    expect(withoutSubject('This area is low.')).toBe('Low.');
  });
  it('leaves other sentences alone', () => {
    expect(withoutSubject('82 calls. This address sits in zone X.')).toBe('82 calls. This address sits in zone X.');
    expect(withoutSubject('this address is low.')).toBe('this address is low.');
  });
});

describe('sharedStem', () => {
  const dep = 'This address is outside the modeled flooding in the NYC DEP stormwater scenario';
  it('splits the DEP scenarios into one stem and three tails', () => {
    expect(sharedStem([
      `${dep} (2.13 in/hr, current sea level).`,
      `${dep} (2.13 in/hr, 2050 SLR).`,
      `${dep} (3.66 in/hr, 2080 SLR).`
    ])).toEqual({ stem: dep, tails: ['2.13 in/hr, current sea level', '2.13 in/hr, 2050 SLR', '3.66 in/hr, 2080 SLR'] });
  });
  it('returns null when the stems differ or there is one sentence', () => {
    expect(sharedStem([
      `${dep} (2.13 in/hr, current sea level).`,
      'This address is inside the modeled flooding in the NYC DEP stormwater scenario (2.13 in/hr, 2050 SLR).'
    ])).toBeNull();
    expect(sharedStem([`${dep} (2.13 in/hr, 2050 SLR).`])).toBeNull();
    expect(sharedStem(['No parenthetical.', 'No parenthetical.'])).toBeNull();
  });
});

describe('keepTogether', () => {
  it('sets a figure with its unit and a date apart, leaving the text unchanged', () => {
    const text = 'within 200 m of it (2.13 in/hr) from 2021-09-02: 0 m² in 3 years';
    const parts = keepTogether(text);
    expect(parts.join('')).toBe(text);
    expect(parts.filter((_, i) => i % 2)).toEqual(['200 m', '2.13 in/hr', '2021-09-02', '0 m²']);
  });
});

import { linkHosts } from '$lib/client/briefingText';

describe('linkHosts', () => {
  it('links a named host without changing the words', () => {
    const s = linkHosts("use FEMA's Flood Map Service Center (msc.fema.gov).");
    expect(s.map((x) => x.text).join('')).toBe("use FEMA's Flood Map Service Center (msc.fema.gov).");
    expect(s.find((x) => x.href)?.href).toBe('https://msc.fema.gov/');
    expect(linkHosts('no host here')).toEqual([{ text: 'no host here' }]);
  });
});
