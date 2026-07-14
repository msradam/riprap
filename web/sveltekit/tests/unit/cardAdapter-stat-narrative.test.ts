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
import { adaptFinalToFindings } from '$lib/client/cardAdapter';
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
    citation: 'NYC Sandy Inundation Zone', doc_id: 'sandy_inundation', last_updated: null,
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
    expect(card?.body ?? card?.headline).toContain('unavailable');
  });
});

/** Real production bug found 2026-07-14: policy_corpus.yaml declares
 * `display: {kind: list, variant: list}` — 'list' isn't a real
 * CardVariant (the real value is 'tabular'), and local_corpus_with_ner's
 * value shape (`{rag_hits: [...], n_hits, n_entities}`) matched neither
 * of the 'tabular' branch's two recognized shapes (GeoJSON `features` or
 * a records `sample`). With no narration.template to fall back to
 * either, a genuine retrieval success (real hits, real entities)
 * rendered as "Policy-corpus index unavailable" — confirmed live: the
 * FSM trace showed n_hits=1, n_entities=5 for the same query. */
const POLICY_CORPUS_MANIFEST: PebbleManifest = {
  id: 'policy_corpus',
  type: 'live',
  title: 'NYC flood-policy corpus — agency reports + plans',
  stone: 'cornerstone',
  tier: 'empirical',
  display: { order: 60, kind: 'list', variant: 'list' as never, map_layer: false, icon: null },
  narration: { short: 'NYC flood-policy passages and typed entities extracted from agency reports relevant to this address.', template: null },
  provenance: {
    source_name: 'NYC flood-policy corpus',
    source_url: null, license: null,
    citation: 'NYC flood-policy corpus', doc_id: 'policy_corpus', last_updated: null,
  },
  fallback: { on_offline: 'skip', message: 'Policy-corpus index unavailable (RAG embeddings or NER model offline).' },
};

describe('cardAdapter — policy_corpus rag_hits shape', () => {
  it('renders retrieved passages as a table, not fallback.message', () => {
    seedManifest([POLICY_CORPUS_MANIFEST]);
    const final = {
      geocode: { address: '80 Pioneer St', lat: 40.678, lon: -74.01 },
      policy_corpus: {
        query: 'flood risk, resilience',
        rag_hits: [
          { doc_id: 'rag_nycha', citation: 'NYCHA, Flood Resilience: Lessons Learned', page: 3, text: 'Hurricane Sandy devastated New York City in October 2012.', score: 0.87 },
        ],
        entities: {},
        n_hits: 1,
        n_entities: 5,
      },
      trace: [],
    };
    const findings = adaptFinalToFindings(final as never, null, 1.0);
    const card = findings.cards.find((c) => c.id === 'pebble-policy_corpus' || c.id === 'policy_corpus');
    expect(card, 'no card rendered for policy_corpus').toBeTruthy();
    expect(card?.rows?.flat().join(' ')).toContain('NYCHA, Flood Resilience: Lessons Learned');
    expect(JSON.stringify(card)).not.toContain('unavailable');
  });

  it('still falls back to fallback.message when there really are no hits', () => {
    seedManifest([POLICY_CORPUS_MANIFEST]);
    const final = {
      geocode: { address: '80 Pioneer St', lat: 40.678, lon: -74.01 },
      policy_corpus: { query: 'flood risk', rag_hits: [], entities: {}, n_hits: 0, n_entities: 0 },
      trace: [],
    };
    const findings = adaptFinalToFindings(final as never, null, 1.0);
    const card = findings.cards.find((c) => c.id === 'pebble-policy_corpus' || c.id === 'policy_corpus');
    expect(card?.headline).toContain('unavailable');
  });
});
