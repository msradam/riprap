/**
 * Grounding surfaces: dropped claims stay out of the briefing but are
 * listed, collapsed, with their reason; experimental citations carry a
 * badge; Stone-tagline sections parse as headed sections.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import DroppedClaims from '$lib/components/briefing/DroppedClaims.svelte';
import SourceList from '$lib/components/briefing/SourceList.svelte';
import { briefingFromFinal } from '$lib/client/runState.svelte';

const DROPPED = [
  { section: 'Hazard Reader', text: 'The site flooded 3 m in 2012.', doc_ids: ['sandy_inundation'],
    numbers: ['3'], reason: 'number 3 not found in sandy_inundation' },
  { section: 'Projector', text: 'Surge will peak at 9 ft.', doc_ids: ['ttm_battery_surge'],
    numbers: ['9'], reason: 'cited source does not state 9 ft' },
];

describe('DroppedClaims', () => {
  it('renders nothing when no claims were dropped', () => {
    const { container } = render(DroppedClaims, { props: { claims: [] } });
    expect(container.querySelector('details')).toBeNull();
  });

  it('renders a collapsed details list with count, text and reason', () => {
    const { container } = render(DroppedClaims, { props: { claims: DROPPED } });
    const details = container.querySelector('details');
    expect(details).not.toBeNull();
    expect(details?.open).toBe(false);
    const summary = container.querySelector('summary')?.textContent ?? '';
    expect(summary).toContain('Dropped claims (2)');
    expect(summary).toContain('not part of the briefing');
    const text = container.textContent ?? '';
    expect(text).toContain('Surge will peak at 9 ft.');
    expect(text).toContain('cited source does not state 9 ft');
    expect(container.querySelectorAll('li')).toHaveLength(2);
  });
});

describe('briefingFromFinal', () => {
  const final = {
    paragraph: [
      'This is an automated briefing. It is informational only.',
      '',
      '**Hazard Reader.**',
      'Outside the 2012 Sandy extent [sandy_inundation].',
      '',
      '**Projector.**',
      'Experimental surge forecast of 0.59 m [ttm_battery_surge].',
      '',
      '**Out of scope.** No structural assessment.',
    ].join('\n'),
    citations: {
      sandy_inundation: { doc_id: 'sandy_inundation', source: 'NYC Open Data', maturity: 'production' as const },
      ttm_battery_surge: { doc_id: 'ttm_battery_surge', source: 'TTM', maturity: 'experimental' as const,
        retrieved_at: '2026-09-26T19:33Z' },
    },
  };

  it('keeps the scope sentence and heads each Stone section', () => {
    const { blocks } = briefingFromFinal(final);
    const heads = blocks.filter((b) => b.kind === 'head').map((b) => (b.kind === 'head' ? b.label : ''));
    expect(heads).toEqual(['Hazard Reader', 'Projector', 'Out of scope']);
    expect(blocks[0].kind).toBe('prose');
    const flat = JSON.stringify(blocks);
    expect(flat).toContain('informational only');
    expect(flat).not.toContain('**');
  });

  it('carries citation maturity and retrieval date, and the source list badges experimental ones', () => {
    const { citations } = briefingFromFinal(final);
    expect(citations.ttm_battery_surge.maturity).toBe('experimental');
    expect(citations.ttm_battery_surge.retrieved).toBe('2026-09-26');
    const { container } = render(SourceList, { props: { citations: Object.values(citations), noted: [] } });
    const badges = container.querySelectorAll('.exp-badge');
    expect(badges).toHaveLength(1);
    expect(badges[0].closest('li')?.id).toBe('cite-ttm_battery_surge');
  });
});

describe('gallery snapshot replay (hollis.json)', () => {
  it('rebuilds briefing and cards offline, flagging experimental pebbles', async () => {
    const { pebbleManifest } = await import('$lib/stores/pebbleManifest.svelte');
    const { RunState } = await import('$lib/client/runState.svelte');
    const entry = (await import('$lib/gallery/hollis.json')).default as unknown as {
      address: string;
      pebbles: Parameters<typeof pebbleManifest.setFromResponse>[0];
      final: Parameters<typeof RunState.fromFinal>[0];
    };
    pebbleManifest.setFromResponse(entry.pebbles, 'nyc');
    const run = RunState.fromFinal(entry.final, entry.address);
    expect(run.errorState).toBeNull();
    expect(run.address?.lat).toBeCloseTo(40.711, 2);
    expect(run.briefing.blocks.length).toBeGreaterThan(3);
    const cards = run.findingsData.cards;
    expect(cards.find((c) => c.docId === 'prithvi_water')?.experimental).toBe(true);
    expect(cards.find((c) => c.docId === 'sandy_inundation')?.experimental).toBe(false);
  });
});

describe('run facts inference energy', () => {
  const facts = async (emissions: Record<string, unknown>) => {
    const { runFacts } = await import('$lib/client/briefingModel');
    const run = { findingsData: { cards: [], stones: [], emissions }, runWallSeconds: undefined };
    return runFacts(run as never).join(' ');
  };
  it('labels a supplied figure and leaves an unknown one out', async () => {
    expect(await facts({ n_calls: 2, energy_status: 'estimated', total_wh: 0.42, tokens: { total: 900 } }))
      .toContain('2 language-model calls, 900 tokens, 0.42 Wh (estimated).');
    const unknown = await facts({ n_calls: 1, energy_status: 'unknown', total_wh: null });
    expect(unknown).toContain('1 language-model call.');
    expect(unknown).not.toMatch(/unknown|Wh/);
    // Older payload: a number with no label is not shown as a figure.
    const legacy = await facts({ n_calls: 1, total_wh: 0.5 });
    expect(legacy).not.toContain('0.50 Wh');
    expect(await facts({ n_calls: 0, energy_status: 'none' })).not.toContain('language-model');
  });
  it('drops an unknown wall clock instead of printing it', async () => {
    expect(await facts({})).not.toMatch(/took|wall/);
  });
});
