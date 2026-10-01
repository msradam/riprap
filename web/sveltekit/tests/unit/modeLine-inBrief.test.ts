/**
 * Refactor 5, phase 5: an extractive answer is not described as "LLM
 * claims checked", and a bare-address briefing's "In brief" lead renders
 * where the Answer goes, not as a numbered section.
 */
import { describe, it, expect } from 'vitest';
import { modeLine } from '$lib/client/cardAdapter';
import { parseBriefing, splitBriefing } from '$lib/client/parseBriefing';
import { briefingModel, snapshotFromRun } from '$lib/client/briefingModel';
import { RunState } from '$lib/client/runState.svelte';
import type { FinalResult, PlanInfo } from '$lib/client/agentStream';

describe('mode line', () => {
  it('describes an extractive answer as quoted, not as LLM claims', () => {
    const line = modeLine({ tier: 'llm', model: 'granite', answer_mode: 'extractive', claims: [1, 2], dropped_claims: [] });
    expect(line).toMatch(/^Extractive answer: sentences quoted word for word/);
    expect(line).not.toMatch(/^LLM claims/);
  });
  it('does not call a cannot-answer line quoted', () => {
    const line = modeLine({ tier: 'llm', answer_mode: 'extractive', answer_lead: 'cannot_answer', claims: [] });
    expect(line).toMatch(/^Extractive answer: no source sentence answers the question/);
    expect(line).not.toContain('word for word');
  });
  it('keeps the guarded and no-LLM wording', () => {
    expect(modeLine({ tier: 'llm', answer_mode: 'guarded', claims: [1], dropped_claims: [1] }))
      .toBe('LLM claims checked against cited sources: 1 kept, 1 dropped');
    expect(modeLine({ tier: 'no_llm' })).toBe('Evidence briefing (no LLM)');
    expect(modeLine(null)).toBeNull();
  });
  it('says no LLM was needed when no question was asked', () => {
    expect(modeLine({ tier: 'no_llm', note: 'x' }))
      .toBe('Evidence briefing: no question was asked, so no LLM was needed');
  });
  it('says a question was answered by rules, with no language model', () => {
    const g = { tier: 'no_llm', answer_mode: 'rules', question: 'How many complaints?', answered: true, answer_lead: 'count' };
    expect(modeLine(g)).toBe("Answered by rules over the question's words; no language model was used.");
    expect(modeLine({ ...g, fallback_reason: 'LLM unavailable: timeout' }))
      .toBe("Answered by rules over the question's words; no language model was used. The LLM was unavailable (LLM unavailable: timeout).");
  });
  it('says a language model planned the query when the rules answered it', () => {
    const g = { tier: 'no_llm', answer_mode: 'rules', question: 'How many complaints?', answered: true, answer_lead: 'count' };
    const planned = "The answer was chosen by rules over the question's words; a language model was used only to read the place and choose the sources.";
    expect(modeLine(g, true)).toBe(planned);
    expect(modeLine(g, false)).toBe("Answered by rules over the question's words; no language model was used.");
    // The page reads it from final.plan.llm_calls: one entry when the planner model was called.
    const final = { paragraph: '**Answer.**\n12 complaints [nyc311].', intent: 'neighborhood', grounding: g as never };
    const line = (plan: PlanInfo) => briefingModel(RunState.fromFinal({ ...final, plan }, 'QN12'), 'QN12').modeLine;
    expect(line({ intent: 'neighborhood', llm_calls: [{ model: 'granite' }] })).toBe(planned);
    expect(line({ intent: 'neighborhood', llm_calls: [] })).toBe("Answered by rules over the question's words; no language model was used.");
  });
  it('says plainly when neither a rule nor a model answered', () => {
    const g = { tier: 'no_llm', answer_mode: 'rules', question: 'Is the roof sound?', answered: false };
    expect(modeLine(g)).toBe('No rule and no language model answered the question, so the evidence briefing is shown.');
    expect(modeLine({ ...g, answer_mode: 'extractive', fallback_reason: 'LLM unavailable: timeout' }))
      .toMatch(/^No rule and no language model answered the question.*The LLM was unavailable \(LLM unavailable: timeout\)\.$/);
  });
  it('says the same when the backend sends no answer mode for an unanswered question', () => {
    expect(modeLine({ tier: 'no_llm', answer_mode: null, question: 'Is the roof sound?', answered: false }))
      .toBe('No rule and no language model answered the question, so the evidence briefing is shown.');
  });
  it('does not say the rules answered when they found no source that answers', () => {
    const g = { tier: 'no_llm', answer_mode: 'rules', answer_lead: 'cannot_answer', question: 'Have the sensors recorded flooding?', answered: false };
    expect(modeLine(g)).toBe('The rules found no source that answers the question; no language model was used.');
    expect(modeLine(g, true)).toBe('The rules found no source that answers the question; a language model was used only to read the place and choose the sources.');
    expect(modeLine(g)).not.toMatch(/^Answered/);
  });
  it('gives a refused query no mode line, on the page or in print', () => {
    const final = {
      intent: 'out_of_scope', paragraph: 'Riprap does not answer this question. It reports public flood evidence for a place.',
      plan: { intent: 'out_of_scope' }, grounding: { tier: 'no_llm', claims: [], dropped_claims: [] }
    } as unknown as FinalResult;
    const run = RunState.fromFinal(final, '80 Pioneer Street, Brooklyn');
    expect(run.refused).toBe(true);
    expect(briefingModel(run, 'Should I buy the house at 80 Pioneer Street, Brooklyn?').modeLine).toBeNull();
    expect(snapshotFromRun(run, 'q', 'Should I buy the house at 80 Pioneer Street, Brooklyn?').mode).toBeNull();
  });
  it('omits "Other claims" when every extractive claim is in the answer', () => {
    const line = modeLine({ tier: 'llm', answer_mode: 'extractive', claims: [{ section: 'answer' }, { section: 'answer' }] });
    expect(line).not.toContain('Other claims');
  });
});

describe('In brief lead', () => {
  const md = 'Scope.\n\n**In brief.**\nThis address is in FEMA flood zone X [fema_nfhl].\n\n' +
    '**Hazard Reader.**\nThis address sits in FEMA flood zone X [fema_nfhl].';
  it('is the lead, and the first Stone section is still numbered 01', () => {
    const { lead, body } = splitBriefing(parseBriefing(md).blocks);
    expect(lead.some((b) => b.kind === 'head' && b.label === 'In brief')).toBe(true);
    const first = body.find((b) => b.kind === 'head');
    expect(first && first.kind === 'head' ? [first.label, first.n] : null).toEqual(['Hazard Reader', '01']);
  });
});
