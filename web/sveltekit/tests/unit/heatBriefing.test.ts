/**
 * Heat briefings: the hazard label and cross-link query come from the
 * plan, and the evidence table shows labelled figures, never a raw key.
 * The fixture is a recorded heat run for an address (2026-10-02) with
 * the manifests of the pebbles it ran.
 */
import { describe, it, expect } from 'vitest';
import { hazardLabel, isHeat, placeQuery, type FinalResult } from '$lib/client/agentStream';
import { figureOf } from '$lib/client/briefingText';
import { RunState } from '$lib/client/runState.svelte';
import { heatCompareRows } from '$lib/client/briefingModel';
import { render } from '@testing-library/svelte';
import CompareBriefing from '$lib/components/briefing/CompareBriefing.svelte';
import { pebbleManifest, type PebbleManifestResponse } from '$lib/stores/pebbleManifest.svelte';
import heat from './fixtures/heat-address.json';

describe('hazardLabel', () => {
  it('is neutral until the plan arrives', () => {
    expect(hazardLabel(null)).toBe('Briefing');
    expect(hazardLabel(undefined)).toBe('Briefing');
    expect(hazardLabel({ intent: 'not_implemented' })).toBe('Briefing');
    expect(hazardLabel({ intent: 'not_implemented', focus: { hazard: 'heat' } })).toBe('Heat briefing');
  });
  it('names a heat run from the plan', () => {
    expect(hazardLabel({ focus: { hazard: 'heat' } })).toBe('Heat briefing');
    expect(isHeat({ focus: { hazard: 'heat' } })).toBe(true);
  });
  it('calls any other planned run a flood briefing', () => {
    expect(hazardLabel({})).toBe('Flood-exposure briefing');
    expect(hazardLabel({ focus: null })).toBe('Flood-exposure briefing');
    expect(hazardLabel({ focus: { hazard: 'flood' } })).toBe('Flood-exposure briefing');
    expect(isHeat({ focus: null })).toBe(false);
  });
});

describe('placeQuery', () => {
  it("uses the planner's single target", () => {
    const plan = { targets: [{ type: 'address', text: '90-01 183rd Street, Queens' }] };
    expect(placeQuery('extreme heat at 90-01 183rd Street, Queens', plan)).toBe('90-01 183rd Street, Queens');
  });
  it('otherwise drops a leading or trailing heat word', () => {
    expect(placeQuery('heat QN12')).toBe('QN12');
    expect(placeQuery('Extreme heat, QN12')).toBe('QN12');
    expect(placeQuery('QN12 heat', { targets: [] })).toBe('QN12');
    expect(placeQuery('QN12')).toBe('QN12');
    expect(placeQuery('Heath Avenue, Bronx')).toBe('Heath Avenue, Bronx');
  });
});

describe('heat evidence cards', () => {
  pebbleManifest.setFromResponse(heat.pebbles as unknown as PebbleManifestResponse, 'nyc');
  const cards = RunState.fromFinal(heat.final as unknown as FinalResult, '90-01 183rd Street, Queens').findingsData.cards;
  const figure = (id: string) => figureOf(cards.find((c) => c.id === `pebble-${id}`)!);

  it('labels every scalar in words', () => {
    const scalars = cards.flatMap((c) => c.scalars ?? []);
    expect(scalars.length).toBeGreaterThan(0);
    expect(scalars.filter((s) => /_|\(/.test(s.label))).toEqual([]);
    // Arrays and objects (by_year, highs) are never scalar cells.
    expect(scalars.filter((s) => !/^-?[\d.]+$/.test(s.value))).toEqual([]);
  });

  it("gives each row the figure its source states, the quantity apart from its label", () => {
    expect(figure('hvi')).toEqual({ value: '5 of 5', label: 'Jamaica', whole: '5 of 5 (Jamaica)' });
    expect(figure('heat_visits')).toEqual({ value: '79 visits', label: '7.6 per 100,000 a year', whole: '79 visits, 7.6 per 100,000 a year' });
    expect(figure('heat_station')).toEqual({
      value: '10 days', label: 'at 90°F or above in 2026 (JFK Airport)', whole: '10 days at 90°F or above in 2026 (JFK Airport)'
    });
    // A register card has its own id.
    expect(figureOf(cards.find((c) => c.docId === 'cool_features')!)).toMatchObject({ value: '2 spray shower sites', label: '0 pools' });
  });

  it('shows a temperature where the temperature is the finding', () => {
    expect(figure('heat_surface')).toEqual({
      value: '+7.5°F', label: "against the city's land average", whole: "+7.5°F against the city's land average"
    });
    expect(figure('heat_obs')).toMatchObject({ value: '72°F', label: 'at JFK Airport' });
    expect(figure('nws_heat_forecast')).toMatchObject({ value: 'high of 82°F', label: 'forecast in the next week' });
  });

  it('labels the land cover percentage', () => {
    expect(figure('city_landcover')).toMatchObject({ value: '11.5% tree canopy', label: '83.5% paved or built (2017)' });
    expect(figure('landcover')).toMatchObject({ value: '83.7% paved or built' });
  });

  it('gives a row with no stated figure none: alerts and projections', () => {
    expect(cards.find((c) => c.id === 'pebble-nws_heat_alerts')?.figure).toBeUndefined();
    expect(figure('npcc4_heat')).toBeNull();
  });

  it('keeps a temperature out of a flood row: the stated figure is for heat sources only', () => {
    // The same reading from a source registered as a flood source, on a flood run.
    const flood = structuredClone(heat) as typeof heat;
    for (const p of flood.pebbles.pebbles) if (p.hazard === 'heat') p.hazard = 'flood';
    flood.final.plan.focus.hazard = 'flood';
    pebbleManifest.setFromResponse(flood.pebbles as unknown as PebbleManifestResponse, 'nyc');
    const rows = RunState.fromFinal(flood.final as unknown as FinalResult, '90-01 183rd Street, Queens').findingsData.cards;
    pebbleManifest.setFromResponse(heat.pebbles as unknown as PebbleManifestResponse, 'nyc');
    const obs = rows.find((c) => c.id === 'pebble-heat_obs')!;
    expect(obs.figure).toBeUndefined();
    expect(figureOf(obs)).toBeNull();
    expect(figureOf(rows.find((c) => c.id === 'pebble-heat_surface')!)).toBeNull();
  });

  it('states every card in a sentence, with no raw key or JSON', () => {
    const text = cards.map((c) => [c.headline, c.body, c.sub].join(' ')).join(' ');
    expect(text).not.toMatch(/[a-z]_[a-z]|[{}[\]]/);
  });
});

describe('method roster on a heat run', () => {
  it('lists no source of the flood briefing, or of the other kind of place, as not run', () => {
    const both = structuredClone(heat) as typeof heat;
    const obs = both.pebbles.pebbles.find((p) => p.id === 'heat_obs')!;
    both.pebbles.pebbles.push({ ...obs, id: 'nws_obs', hazard: 'flood' }, { ...obs, id: 'heat_obs_nta', scope: 'polygon' });
    pebbleManifest.setFromResponse(both.pebbles as unknown as PebbleManifestResponse, 'nyc');
    const stones = RunState.fromFinal(both.final as unknown as FinalResult, '90-01 183rd Street, Queens').findingsData.stones;
    pebbleManifest.setFromResponse(heat.pebbles as unknown as PebbleManifestResponse, 'nyc');
    const ids = stones.flatMap((s) => s.members.map((m) => m.id));
    expect(ids).toContain('heat_obs');
    expect(ids).toContain('city_landcover');
    expect(ids).not.toContain('nws_obs');
    expect(ids).not.toContain('heat_obs_nta');
  });
});

describe('heat comparison', () => {
  // Place A is the fixture's address. Place B is an area, whose values are keyed with _nta.
  const a = heat.final as unknown as Record<string, unknown>;
  const b = {
    heat_surface_nta: { mean_diff_f: -6.8, n_images: 18 },
    hvi_nta: { available: true, hvi: 1, year: 2023 },
    city_landcover_nta: { year: 2017, built_pct: 38.3, tree_canopy_pct: 48.6 },
    heat_visits_nta: { available: true, age_adjusted_rate: 11.9, district: 'BX08', period: '2018 to 2022' },
    heat_station_nta: { year: 2026, days_ge_90: 20, station: 'LaGuardia Airport' },
    nyc311_nta: { n: 40 }
  };
  const rows = heatCompareRows(a, b);

  it('sets each heat record both places have, labelled with what it is', () => {
    expect(rows.map((r) => [r.label, r.aVal, r.bVal])).toEqual([
      ["Surface temperature against the city's land average", '+7.5°F over 18 images', '-6.8°F over 18 images'],
      ['Heat Vulnerability Index (2023)', '5 of 5', '1 of 5'],
      ["Tree canopy, the city's 2017 land cover map", '11.5%', '48.6%'],
      ["Paved or built over, the city's 2017 land cover map", '83.5%', '38.3%'],
      ['Heat illness emergency visits, 2018 to 2022', '7.6 per 100,000 a year (QN12)', '11.9 per 100,000 a year (BX08)'],
      ['Days at 90°F or above in 2026', '10 (JFK Airport)', '20 (LaGuardia Airport)']
    ]);
  });

  it('says the surface row is the surface, not the air', () => {
    expect(rows[0].ctx).toContain('the surface of the ground, not the air');
    expect(rows.map((r) => r.label).join(' ')).not.toMatch(/air temperature/i);
  });

  it('leaves out a record one place lacks, or that its source withheld', () => {
    const rest = heatCompareRows(a, { ...b, hvi_nta: { available: false }, heat_station_nta: undefined });
    expect(rest.map((r) => r.label)).not.toContain('Heat Vulnerability Index (2023)');
    expect(rest).toHaveLength(4);
    expect(heatCompareRows(a, {})).toEqual([]);
  });

  it('renders the heat rows and no flood rows', () => {
    const { container } = render(CompareBriefing, {
      props: {
        paragraph: '', citations: {}, heat: true,
        targets: [{ label: 'PLACE A', address: 'Jamaica', state: a }, { label: 'PLACE B', address: 'Riverdale', state: b }],
        // Flood step payloads that would make flood rows on a flood comparison.
        structuredA: { nyc311: { n: 5 } }, structuredB: { nyc311: { n: 20 } }
      }
    });
    const text = (container.querySelector('.compare-delta-bar')?.textContent ?? '').replace(/\s+/g, ' ');
    expect(text).toContain('Heat records, side by side');
    expect(text).toContain("Surface temperature against the city's land average");
    expect(text).toContain('-6.8°F over 18 images');
    expect(text).not.toContain('311 complaints');
    expect(container.querySelectorAll('.compare-delta-table tbody tr')).toHaveLength(6);
  });
});
