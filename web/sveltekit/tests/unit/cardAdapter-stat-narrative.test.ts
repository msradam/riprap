/**
 * Regression test for a real production bug found 2026-07-13 verifying
 * the Modal deployment end-to-end: sandy.yaml declares `display: {kind:
 * stat, variant: headline}` — an explicit per-pebble override, since its
 * boolean_zone shaper output (`{inside, inside_phrasing,
 * inside_or_outside}`) has no numeric fields and can't render as a
 * scalar grid. cardAdapter's buildTemplated computed variant from
 * `KIND_TO_VARIANT[m.display.kind]` alone and never consulted
 * `m.display.variant` at all, so the explicit override was silently
 * ignored: 'stat' -> 'scalars', found zero numeric scalars, and fell to
 * `m.fallback.message` — "Sandy raster + GeoJSON both unavailable." —
 * even though the pebble had genuinely succeeded (ok=true, err=null)
 * with a real, meaningful result. Confirmed live against the deployed
 * Modal app: the FSM trace and the /api/pebbles-served manifest both
 * carried the correct data; only the card rendering ignored it.
 *
 * Two layers are tested: the primary fix (respect display.variant when
 * it names a real CardVariant) and a defensive fallback (try
 * narration.template before fallback.message even with no override) for
 * any other `stat`-kind pebble whose value is non-numeric.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { adaptFinalToFindings, dropUnfilled } from '$lib/client/cardAdapter';
import { findingOf } from '$lib/client/briefingText';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import type { PebbleManifest, PebbleStone } from '$lib/stores/pebbleManifest.svelte';

const STONES: PebbleStone[] = [
  { id: 'cornerstone', name: 'Cornerstone', tagline: '', description: '', order: 1 },
];

function seedManifest(pebbles: PebbleManifest[]): void {
  const byId: Record<string, PebbleManifest> = {};
  const byStone: Record<string, PebbleManifest[]> = {};
  for (const p of pebbles) {
    byId[p.id] = p;
    (byStone[p.stone] ||= []).push(p);
  }
  pebbleManifest.byId = byId;
  pebbleManifest.stones = STONES;
  pebbleManifest.byStone = byStone;
  pebbleManifest.loaded = true;
  pebbleManifest.error = null;
}

beforeEach(() => {
  pebbleManifest.byId = {};
  pebbleManifest.stones = [];
  pebbleManifest.byStone = {};
  pebbleManifest.loaded = false;
  pebbleManifest.error = null;
});

/** Exact shape of deployments/nyc/manifests/sandy.yaml as served by
 *  /api/pebbles — kind: stat WITH an explicit variant: headline override. */
const SANDY_MANIFEST: PebbleManifest = {
  id: 'sandy',
  type: 'live',
  title: 'NYC Sandy Inundation Zone (2012 empirical extent)',
  stone: 'cornerstone',
  tier: 'empirical',
  display: { order: 10, kind: 'stat', variant: 'headline', map_layer: true, icon: null },
  narration: {
    short: 'This address is within the empirical 2012 Hurricane Sandy inundation footprint.',
    template: 'This address {inside_phrasing} the empirical 2012 Hurricane Sandy inundation footprint (NYC OEM).',
  },
  provenance: {
    source_name: 'NYC Open Data — Sandy Inundation Zone',
    source_url: null, license: null,
    citation: 'NYC Sandy Inundation Zone', doc_id: 'sandy_inundation', date_modified: null,
  },
  fallback: { on_offline: 'skip', message: 'Sandy raster + GeoJSON both unavailable.' },
};

/** Same value shape, but no explicit display.variant override — exercises
 *  the defensive narration.template-before-fallback fallback instead of
 *  the primary variant-override fix. */
const NO_OVERRIDE_MANIFEST: PebbleManifest = {
  ...SANDY_MANIFEST,
  id: 'sandy_no_override',
  display: { ...SANDY_MANIFEST.display, variant: null },
};

describe('cardAdapter — stat-kind pebble with a non-numeric shaped value', () => {
  it('respects an explicit display.variant override (the real bug: sandy.yaml)', () => {
    seedManifest([SANDY_MANIFEST]);
    const final = {
      geocode: { address: '350 5th Ave', lat: 40.748, lon: -73.985 },
      sandy: { inside: false, inside_phrasing: 'sits outside', inside_or_outside: 'outside' },
      trace: [],
    };
    const findings = adaptFinalToFindings(final as never, null, 1.0);
    const card = findings.cards.find((c) => c.id === 'pebble-sandy' || c.id === 'sandy');
    expect(card, 'no card rendered for sandy').toBeTruthy();
    expect(card?.body ?? card?.headline).toContain('sits outside');
    expect(card?.body ?? card?.headline).not.toContain('unavailable');
  });

  it('falls back to narration.template even with no explicit override (defensive fix)', () => {
    seedManifest([NO_OVERRIDE_MANIFEST]);
    const final = {
      geocode: { address: '350 5th Ave', lat: 40.748, lon: -73.985 },
      sandy_no_override: { inside: false, inside_phrasing: 'sits outside', inside_or_outside: 'outside' },
      trace: [],
    };
    const findings = adaptFinalToFindings(final as never, null, 1.0);
    const card = findings.cards.find((c) => c.id === 'pebble-sandy_no_override' || c.id === 'sandy_no_override');
    expect(card, 'no card rendered for sandy_no_override').toBeTruthy();
    expect(card?.body ?? card?.headline).toContain('sits outside');
    expect(card?.body ?? card?.headline).not.toContain('unavailable');
  });

  it('still falls back to fallback.message when the pebble genuinely has no value', () => {
    seedManifest([SANDY_MANIFEST]);
    const final = {
      geocode: { address: '350 5th Ave', lat: 40.748, lon: -73.985 },
      sandy: null,
      trace: [],
    };
    const findings = adaptFinalToFindings(final as never, null, 1.0);
    const card = findings.cards.find((c) => c.id === 'pebble-sandy' || c.id === 'sandy');
    // An absence, not a finding: muted label plus the reason, no headline.
    expect(card?.absent).toBe('Not available');
    expect(card?.headline).toBeUndefined();
    expect(card?.sub).toContain('unavailable');
  });
});

/** sandy.yaml's template ends with `{edge_note}`: "" for most addresses,
 *  a clause starting with a comma near the mapped edge, and absent from
 *  snapshots saved before the field existed. */
describe('cardAdapter: an optional template clause', () => {
  const EDGE_MANIFEST: PebbleManifest = {
    ...SANDY_MANIFEST,
    narration: {
      ...SANDY_MANIFEST.narration,
      template: 'This address {inside_phrasing} the empirical 2012 Hurricane Sandy inundation footprint (NYC Open Data){edge_note}.',
    },
  };
  const body = (sandy: Record<string, unknown>) => {
    seedManifest([EDGE_MANIFEST]);
    const findings = adaptFinalToFindings({ sandy: { inside: true, inside_phrasing: 'is inside', ...sandy }, trace: [] } as never, null, 1.0);
    return findings.cards.find((c) => c.id === 'pebble-sandy')?.body;
  };
  const PLAIN = 'This address is inside the empirical 2012 Hurricane Sandy inundation footprint (NYC Open Data).';

  it('renders an empty or missing edge_note as no text, never as braces', () => {
    expect(body({ edge_note: '' })).toBe(PLAIN);
    expect(body({})).toBe(PLAIN);
    expect(body({ edge_note: null })).toBe(PLAIN);
  });

  it('prints the clause when the source gives one', () => {
    expect(body({ edge_note: ', about 40 m from the mapped edge (the outline is not exact to a building)' }))
      .toBe('This address is inside the empirical 2012 Hurricane Sandy inundation footprint (NYC Open Data), about 40 m from the mapped edge (the outline is not exact to a building).');
  });

  it('still refuses a template whose required field is missing', () => {
    expect(body({ inside_phrasing: '' })).toBeUndefined();
  });
});

/** A city 311 value (deployments/chicago/manifests/chicago_311.yaml):
 *  `n_records` is the count after the flood filter, and `n_truncated`
 *  says the fetch hit its limit before the filter. */
describe('cardAdapter: a city 311 card states the backend sentence', () => {
  const LIST_MANIFEST: PebbleManifest = {
    ...SANDY_MANIFEST,
    id: 'chicago_311',
    display: { ...SANDY_MANIFEST.display, kind: 'list', variant: null },
    narration: {
      short: 'Flood-related Chicago 311 service requests within 200 m of this address.',
      template: '{n_kept} of {n_before_phrase} Chicago 311 service requests within {radius_m} m of this address {filter_note}.',
    },
  };
  const finding = (manifest: PebbleManifest, value: Record<string, unknown>) => {
    seedManifest([manifest]);
    const card = adaptFinalToFindings({ chicago_311: value, trace: [] } as never, null, 1.0)
      .cards.find((c) => c.id === 'pebble-chicago_311');
    return card && findingOf(card, manifest.narration.short)?.first;
  };

  it('says how many of the fetched requests are flood-related, with no "+" on the filtered count', () => {
    expect(finding(LIST_MANIFEST, {
      n_records: 3, n_truncated: true, radius_m: 200, sample: [{ sr_type: 'Water On Street Complaint' }],
      n_before: 200, n_kept: 3, n_before_phrase: 'the latest 200', filter_note: 'are in categories reviewed as flood-related',
    })).toBe('3 of the latest 200 Chicago 311 service requests within 200 m of this address are in categories reviewed as flood-related.');
  });

  it('marks a capped count where the sentence prints the count itself', () => {
    const albany = { ...LIST_MANIFEST, narration: { ...LIST_MANIFEST.narration, template: 'Reports within {radius_m} m of this address: {n_records}.' } };
    expect(finding(albany, { n_records: 100, n_truncated: true, radius_m: 800, sample: [{}] }))
      .toBe('Reports within 800 m of this address: 100+.');
    expect(finding(albany, { n_records: 12, n_truncated: false, radius_m: 800, sample: [{}] }))
      .toBe('Reports within 800 m of this address: 12.');
  });
});

describe('cardAdapter: absent sources and unfilled templates', () => {
  it('marks a pebble that never ran as Not run', () => {
    seedManifest([SANDY_MANIFEST]);
    const findings = adaptFinalToFindings({ trace: [] } as never, null, 1.0);
    const card = findings.cards.find((c) => c.id === 'pebble-sandy');
    expect(card?.absent).toBe('Not run');
  });

  it('never renders a line that still holds a {field} placeholder', () => {
    const card = dropUnfilled({
      id: 'x', stone: 'lodestone', tier: 'modeled', variant: 'scalars',
      source: 'S', vintage: 'v', title: 'T', docId: 'd',
      headline: '5.9 ft',
      sub: 'forecasts a peak water level of {forecast_peak_ft_mllw} ft',
    });
    expect(card.headline).toBe('5.9 ft');
    expect(card.sub).toBeUndefined();
  });
});
