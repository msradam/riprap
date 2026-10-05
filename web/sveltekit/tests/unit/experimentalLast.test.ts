import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import AnswerProse from '$lib/components/briefing/AnswerProse.svelte';
import { keyedAnswer, sourceParas, splitLead } from '$lib/client/briefingModel';
import { parseBriefing } from '$lib/client/parseBriefing';
import { tidy } from '$lib/client/briefingText';
import type { ClaimPart } from '$lib/types/claim';

function answerOf(md: string): ClaimPart[][] {
  const paras = parseBriefing(`**Answer.**\n${md}`).blocks.flatMap((b) => (b.kind === 'prose' ? [b.parts] : []));
  return [splitLead(paras[0]).parts, ...paras.slice(1)];
}
const words = (parts: ClaimPart[]) => tidy(parts).map((p) => p.text).join('').replace(/\s+/g, ' ').trim();
const isExp = (id: string) => id === 'lake_michigan_water_level';

// An answer in the shape of hollis-since-ida's: an experimental source
// sits between the Ida marks and the 311 count.
const IDA =
  'Yes. USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address [ida_hwm]. ' +
  'Experimental: the nearest gauge read 579.4 ft, 18.1 km from this address [lake_michigan_water_level]. ' +
  'The reading is for the lake, not for this street [lake_michigan_water_level]. ' +
  '82 NYC 311 complaints about flooding and sewer backups filed within 200 m of this location in the last 5 years [nyc311].';

describe('keyedAnswer', () => {
  it('puts paragraphs from experimental sources last, each opening with the badge', () => {
    const r = keyedAnswer(answerOf(IDA), { doc_id: 'nyc311', in_lead: false }, isExp)!;
    expect(words(r.key!)).toMatch(/^82 NYC 311/);
    expect(r.paras.map((p) => !!p[0].exp)).toEqual([false, false, true]);
    expect(words(r.paras[1])).toMatch(/^USGS surveyed/);
    const last = r.paras[2];
    // The badge takes the place of the sentence's own "Experimental:" label.
    expect(words(last)).toBe('The nearest gauge read 579.4 ft, 18.1 km from this address. The reading is for the lake, not for this street.');
    expect(last.some((p) => p.cite === 'lake_michigan_water_level')).toBe(true);
  });

  it('gives the badge the label the sentence opened with, and the text does not repeat it', () => {
    const FORECAST = IDA.replace('Experimental: the nearest gauge read', 'Experimental forecast: the nearest gauge will read');
    const last = (md: string) => keyedAnswer(answerOf(md), { doc_id: 'nyc311', in_lead: false }, isExp)!.paras[2];
    expect(last(IDA)[0].exp).toBe('Experimental');
    const forecast = last(FORECAST);
    expect(forecast[0].exp).toBe('Experimental forecast');
    expect(words(forecast)).toBe('The nearest gauge will read 579.4 ft, 18.1 km from this address. The reading is for the lake, not for this street.');
    const { container } = render(AnswerProse, { props: { parts: forecast, citations: {} } });
    expect(container.querySelector('.exp-badge')?.textContent).toBe('Experimental forecast');
    expect(container.querySelector('p')?.textContent?.trim()).toMatch(/^Experimental forecast The nearest gauge will read/);
  });

  it('never makes an experimental sentence the key sentence', () => {
    const r = keyedAnswer(answerOf(IDA), { doc_id: 'lake_michigan_water_level', in_lead: false }, isExp)!;
    expect(r.key).toBeNull();
    expect(r.paras.map((p) => !!p[0].exp)).toEqual([false, false, true]);
    expect(words(r.paras[0])).toMatch(/^USGS surveyed/);
    expect(words(r.paras[1])).toMatch(/^82 NYC 311/);
  });

  it('leaves an answer with no lead fact alone', () => {
    expect(keyedAnswer(answerOf(IDA), null, isExp)).toBeNull();
  });
});

describe('sourceParas', () => {
  const surge = (id: string) => id === 'ttm_battery_surge' || id === 'landcover_nta';
  // The "will it flood" answer: a lead phrase set by code, then four sources.
  const NO_PREDICTION =
    'Riprap cannot predict whether a particular place floods on a given day: no source or model here does that. ' +
    'What the Weather Service expects, and what the maps show: No active NWS flood alerts at this point [nws_alerts]. ' +
    'The National Weather Service forecasts a peak water level of 5.9 ft above MLLW at The Battery [nws_water_forecast]. ' +
    'Experimental forecast: the water at The Battery may run up to 0.20 m above the predicted tide [ttm_battery_surge]. ' +
    'Limits: it reads only the gauge [ttm_battery_surge]. Rely on the National Weather Service [ttm_battery_surge].';

  it('breaks an answer with no key sentence into one paragraph per source and badges the model', () => {
    const paras = sourceParas(answerOf(NO_PREDICTION), surge);
    expect(paras).toHaveLength(3);
    expect(words(paras[0])).toMatch(/^Riprap cannot predict .* No active NWS flood alerts at this point\.$/);
    expect(paras.map((p) => p[0].exp ?? false)).toEqual([false, false, 'Experimental forecast']);
    expect(words(paras[2])).toBe('The water at The Battery may run up to 0.20 m above the predicted tide. ' +
      'Limits: it reads only the gauge. Rely on the National Weather Service.');
  });

  it('sets the lead phrase of a model-only answer apart, so the badge sits on the sentence', () => {
    const paras = sourceParas(answerOf('From an experimental model, not a measurement: Experimental: a satellite ' +
      'land-cover model labels 71.0% of this area as paved [landcover_nta]. Limits: a proxy [landcover_nta].'), surge);
    expect(paras).toHaveLength(2);
    expect(words(paras[0])).toBe('From an experimental model, not a measurement:');
    expect(paras[0].some((p) => p.cite)).toBe(false);
    expect(paras[1][0].exp).toBe('Experimental');
    expect(words(paras[1])).toBe('A satellite land-cover model labels 71.0% of this area as paved. Limits: a proxy.');
  });
});
