/**
 * Refactor 5, phase 5: an extractive answer is not described as "LLM
 * claims checked", and a bare-address briefing's "In brief" lead renders
 * where the Answer goes, not as a numbered section.
 */
import { describe, it, expect } from 'vitest';
import { modeLine } from '$lib/client/cardAdapter';
import { parseBriefing, splitBriefing } from '$lib/client/parseBriefing';

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
