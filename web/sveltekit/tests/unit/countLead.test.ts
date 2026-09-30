import { describe, expect, it } from 'vitest';
import { briefingModel, countLead } from '$lib/client/briefingModel';
import { RunState } from '$lib/client/runState.svelte';
import type { FinalResult } from '$lib/client/agentStream';

const SENTENCE =
  'From the sources consulted: 34 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years: 16 catch basin, 12 sewer backup, 6 street flooding';
const QUESTION = 'How many flooding complaints have people near 2017 East 17th Street, Brooklyn made to 311?';

/** A question briefing whose count sits inside its key sentence. */
function model(answerLead: string) {
  const final = {
    paragraph: `**Answer.**\n${SENTENCE} [nyc311].`,
    citations: { nyc311: { doc_id: 'nyc311', source: 'NYC 311', title: '311 service requests', maturity: 'production' } },
    grounding: { tier: 'llm', question: QUESTION, answer_lead: answerLead, lead_fact: { doc_id: 'nyc311', in_lead: false } }
  } as unknown as FinalResult;
  return briefingModel(RunState.fromFinal(final, '2017 East 17th Street, Brooklyn'), QUESTION);
}
const words = (m: ReturnType<typeof model>) => m.answer.map((p) => p.map((x) => x.text).join('')).join(' ');

describe('countLead', () => {
  it('takes the first number of the key sentence', () => {
    expect(countLead([{ text: `${SENTENCE}.`, cite: 'nyc311' }])).toBe('34');
    expect(countLead([{ text: 'No figure here.' }])).toBeNull();
  });

  it('takes no number from inside a word or later in the sentence', () => {
    // Live: "How much sea-level rise ... by the 2050s?" led with a bare "4".
    const npcc = 'From the sources consulted: NPCC4 (2024) projects sea-level rise at the Battery of 0.38 m (15 in) by the 2050s.';
    expect(countLead([{ text: npcc, cite: 'npcc4_slr' }])).toBeNull();
  });

  it('leads a count answer with that number and keeps the sentence whole below it', () => {
    const m = model('count');
    expect(m.lead).toBe('34');
    expect(m.keyed).toBe(true);
    expect(words(m)).toContain(SENTENCE);
  });

  it('adds no lead word to an answer that is not a count', () => {
    expect(model('yes').lead).toBeNull();
  });
});
