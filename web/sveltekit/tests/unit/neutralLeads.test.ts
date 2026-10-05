/**
 * The two leads set only by code, `experimental` and `no_prediction`, are
 * phrases with no yes, no or count. No word or figure is set large for
 * them. The answer is one paragraph per source in the order given, and a
 * model's sentence carries the Experimental badge.
 */
import { describe, expect, it } from 'vitest';
import { briefingModel, countLead, splitLead } from '$lib/client/briefingModel';
import { RunState } from '$lib/client/runState.svelte';
import type { FinalResult, Grounding } from '$lib/client/agentStream';

const EXPERIMENTAL = 'From an experimental model, not a measurement:';
const NO_PREDICTION =
  'Riprap cannot predict whether a particular place floods on a given day: no source or model here does that. What the Weather Service expects, and what the maps show:';
const SURGE =
  'Experimental forecast: the surge model projects a peak of 0.42 ft above the predicted tide at the Battery in the next 96 hours [ttm_battery_surge].';
const NWS = 'NWS forecasts a peak water level of 5.1 ft above MLLW at the Battery [nws_water_forecast].';
const QUESTION = 'Will 80 Pioneer Street, Brooklyn flood this week?';

function model(body: string, grounding: Partial<Grounding>) {
  const final = {
    paragraph: `**Answer.**\n${body}`,
    citations: {
      ttm_battery_surge: { doc_id: 'ttm_battery_surge', source: 'Riprap', title: 'Battery surge forecast', maturity: 'experimental' },
      nws_water_forecast: { doc_id: 'nws_water_forecast', source: 'NWS', title: 'Water-level forecast', maturity: 'production' }
    },
    grounding: { tier: 'no_llm', question: QUESTION, answer_mode: 'rules', answered: true, ...grounding }
  } as unknown as FinalResult;
  return briefingModel(RunState.fromFinal(final, '80 Pioneer Street, Brooklyn'), QUESTION);
}
const words = (m: ReturnType<typeof model>, i = 0) => m.answer[i].map((p) => p.text).join('').replace(/\s+/g, ' ').trim();

describe('the lead phrases themselves', () => {
  it.each([EXPERIMENTAL, NO_PREDICTION])('give no lead word and no count: %s', (phrase) => {
    expect(splitLead([{ text: `${phrase} ${NWS}` }]).word).toBeNull();
    expect(countLead([{ text: `${phrase} ${NWS}` }])).toBeNull();
  });
});

describe('an answer formed by an experimental model alone', () => {
  it('sets no word large, opens with the lead phrase and badges the sentence under it', () => {
    const m = model(`${EXPERIMENTAL} ${SURGE}`, { answer_lead: 'experimental', lead_fact: null });
    expect(m.lead).toBeNull();
    expect(words(m)).toBe('From an experimental model, not a measurement:');
    expect(m.answer[1][0].exp).toBe('Experimental forecast');
    expect(words(m, 1)).toMatch(/^The surge model projects a peak of 0.42 ft/);
  });

  it('does not move its paragraphs behind another source, even with a lead fact', () => {
    // A lead fact would otherwise lift the NWS sentence out as the key
    // sentence and send the paragraph that opens with the lead phrase last.
    const m = model(`${EXPERIMENTAL} ${SURGE} ${NWS}`, {
      answer_lead: 'experimental', lead_fact: { doc_id: 'nws_water_forecast', in_lead: false }
    });
    expect(m.lead).toBeNull();
    expect(words(m)).toBe('From an experimental model, not a measurement:');
    expect(m.answer[1][0].exp).toBe('Experimental forecast');
    expect(words(m, 2)).toMatch(/^NWS forecasts a peak water level/);
  });
});

describe('a question that asks whether a place will flood', () => {
  it('sets nothing large and opens with the statement that no source predicts it', () => {
    const m = model(`${NO_PREDICTION} ${NWS} ${SURGE}`, { answer_lead: 'no_prediction', lead_fact: null });
    expect(m.lead).toBeNull();
    expect(words(m)).toMatch(/^Riprap cannot predict whether a particular place floods on a given day.* NWS forecasts a peak/);
    // The model's sentence is its own paragraph, badged, after the official forecast.
    expect(m.answer).toHaveLength(2);
    expect(m.answer[1][0].exp).toBe('Experimental forecast');
  });

  it('sets no figure large even when its first paragraph opens with one', () => {
    expect(model(`96 hours are forecast. ${NWS}`, { answer_lead: 'no_prediction' }).lead).toBeNull();
    expect(model(`96 hours are forecast. ${NWS}`, { answer_lead: 'experimental' }).lead).toBeNull();
    // The same paragraph under a lead that may carry a figure does set it.
    expect(model(`96 hours are forecast. ${NWS}`, { answer_lead: 'facts' }).lead).toBe('96');
  });
});

describe('the leads added for advice, a missing house number and land cover over time', () => {
  const NO_ADVICE =
    'Riprap reports public records about a place. It does not price flood insurance, value property or give advice on buying, renting or whether a home is safe. The FEMA flood zone here, from the effective map (the one FEMA uses for the National Flood Insurance Program) first:';
  const NEEDS_ADDRESS =
    'Riprap read this question for the neighbourhood or district as a whole, because it names no house number, and the USGS high-water marks surveyed after Hurricane Ida are read around a street address. Type the address with its house number, such as 90-01 183rd Street, Queens, to get the marks near it.';
  const NO_CHANGE = 'Riprap has no like-for-like record of change in land cover here. What the sources below show is one year each, not a change:';

  it.each([
    ['no_advice', NO_ADVICE],
    ['needs_address', NEEDS_ADDRESS],
    ['no_change_record', NO_CHANGE]
  ] as const)('%s sets no Yes, No or figure large and opens with its statement', (lead, phrase) => {
    const m = model(`${phrase} ${NWS}`, { answer_lead: lead, lead_fact: null });
    expect(m.lead).toBeNull();
    expect(m.leadWord).toBeNull();
    expect(words(m).startsWith(phrase.slice(0, 40))).toBe(true);
    // Even a paragraph that opens with a figure sets none under these leads.
    expect(model(`96 hours are forecast. ${NWS}`, { answer_lead: lead }).lead).toBeNull();
  });
});

describe('the paragraph that names the place', () => {
  it('is left to the page place line, which already carries it', () => {
    const final = {
      paragraph: `Scope sentence.\n\nPlace described: QN12, Queens. The shape used for QN12 is an approximation.\n\n**Answer.**\nFrom the sources consulted: ${NWS}`,
      citations: { nws_water_forecast: { doc_id: 'nws_water_forecast', source: 'NWS', title: 'Water-level forecast', maturity: 'production' } },
      grounding: { tier: 'no_llm', question: QUESTION, answer_mode: 'rules', answered: true, answer_lead: 'facts' }
    } as unknown as FinalResult;
    const m = briefingModel(RunState.fromFinal(final, 'QN12'), QUESTION);
    const scope = m.scope.map((p) => p.map((x) => x.text).join('')).join(' ');
    expect(scope).toContain('Scope sentence.');
    expect(scope).not.toContain('Place described');
  });
});
