import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import ResultsView from '$lib/components/results/ResultsView.svelte';
import { briefingModel, countLead } from '$lib/client/briefingModel';
import { RunState } from '$lib/client/runState.svelte';
import type { FinalResult } from '$lib/client/agentStream';

const SENTENCE =
  'From the sources consulted: 34 NYC 311 complaints about flooding and sewer backups filed within 200 m of this location in the last 5 years: 16 catch basin, 12 sewer backup, 6 street flooding';
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
    const npcc = 'From the sources consulted: NPCC4 (2024) projects sea-level rise in New York City of 14 to 19 in (0.36 to 0.48 m) by the 2050s.';
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

describe('a place briefing that opens with a figure', () => {
  const BRIEF = '0.8% of this area lies inside the 2012 Sandy inundation extent [sandy_inundation]. ' +
    '4226 complaints to 311 about flooding and sewer backups were filed in Community District QN12 in the last 3 years [nyc311_nta].';
  const brief = (intent: string, place: string) => briefingModel(RunState.fromFinal({
    intent, paragraph: `**In brief.**\n${BRIEF}`, citations: {}, grounding: { tier: 'no_llm', note: 'no question' }
  } as unknown as FinalResult, place), place);

  it.each(['neighborhood', 'development_check'])('sets no figure large on a %s briefing, and keeps its In brief text', (intent) => {
    const m = brief(intent, 'QN12');
    expect(m.lead).toBeNull();
    expect(m.leadLabel).toBe('In brief');
    expect(m.answer[0].map((p) => p.text).join('')).toContain('0.8% of this area lies inside the 2012 Sandy inundation extent');
  });

  it('still leads an address briefing with its opening count', () => {
    expect(brief('single_address', '90-01 183rd Street, Queens').lead).toBe('0.8%');
  });
});

describe('a question neither a rule nor a model answered', () => {
  const final = {
    intent: 'single_address',
    paragraph: 'Scope.\n\n**Hazard Reader.**\nThis address sits in FEMA flood zone X [fema_nfhl].',
    citations: {},
    grounding: { tier: 'no_llm', question: QUESTION, answered: false, answer_mode: 'rules', claims: [] }
  } as unknown as FinalResult;
  const m = briefingModel(RunState.fromFinal(final, '2017 East 17th Street, Brooklyn'), QUESTION);

  it('is flagged unanswered, with the mode line saying why', () => {
    expect(m.unanswered).toBe(true);
    expect(m.lead).toBeNull();
    expect(m.modeLine).toBe('No rule and no language model answered the question, so the evidence briefing is shown.');
  });

  it('says so plainly on the page, in a status line', () => {
    const run = RunState.fromFinal(final, '2017 East 17th Street, Brooklyn');
    const { container } = render(ResultsView, { props: { run, queryText: QUESTION, snapshot: true } });
    expect(container.querySelector('.brief-status[role=status]')?.textContent)
      .toBe('This question was not answered. The evidence for the place is shown below.');
  });
});
