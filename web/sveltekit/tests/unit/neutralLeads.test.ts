/**
 * The two leads set only by code, `experimental` and `no_prediction`, are
 * phrases with no yes, no or count. Nothing is set large for them, and an
 * experimental answer keeps its lead phrase at the start of its paragraph.
 */
import { describe, expect, it } from 'vitest';
import { briefingModel, countLead, splitLead } from '$lib/client/briefingModel';
import { RunState } from '$lib/client/runState.svelte';
import type { FinalResult, Grounding } from '$lib/client/agentStream';

const EXPERIMENTAL = 'From an experimental model, not a measurement:';
const NO_PREDICTION =
  'Riprap cannot say whether a particular place will flood on a given day: no source or model here predicts that. What is forecast and mapped:';
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
  it('sets nothing large and keeps the lead phrase at the start of its sentence', () => {
    const m = model(`${EXPERIMENTAL} ${SURGE}`, { answer_lead: 'experimental', lead_fact: null });
    expect(m.lead).toBeNull();
    expect(m.keyed).toBe(false);
    expect(words(m)).toMatch(/^From an experimental model, not a measurement: Experimental forecast: the surge model/);
  });

  it('does not move its paragraphs behind another source, even with a lead fact', () => {
    // A lead fact would otherwise lift the NWS sentence out as the key
    // sentence and send the paragraph that opens with the lead phrase last.
    const m = model(`${EXPERIMENTAL} ${SURGE} ${NWS}`, {
      answer_lead: 'experimental', lead_fact: { doc_id: 'nws_water_forecast', in_lead: false }
    });
    expect(m.keyed).toBe(false);
    expect(m.lead).toBeNull();
    expect(words(m)).toMatch(/^From an experimental model, not a measurement: Experimental forecast:/);
    expect(m.answer.flat().some((p) => p.exp)).toBe(false);
  });
});

describe('a question that asks whether a place will flood', () => {
  it('sets nothing large and opens with the statement that no source predicts it', () => {
    const m = model(`${NO_PREDICTION} ${NWS} ${SURGE}`, { answer_lead: 'no_prediction', lead_fact: null });
    expect(m.lead).toBeNull();
    expect(m.keyed).toBe(false);
    expect(words(m)).toMatch(/^Riprap cannot say whether a particular place will flood on a given day/);
  });

  it('sets no figure large even when its first paragraph opens with one', () => {
    expect(model(`96 hours are forecast. ${NWS}`, { answer_lead: 'no_prediction' }).lead).toBeNull();
    expect(model(`96 hours are forecast. ${NWS}`, { answer_lead: 'experimental' }).lead).toBeNull();
    // The same paragraph under a lead that may carry a figure does set it.
    expect(model(`96 hours are forecast. ${NWS}`, { answer_lead: 'facts' }).lead).toBe('96');
  });
});
