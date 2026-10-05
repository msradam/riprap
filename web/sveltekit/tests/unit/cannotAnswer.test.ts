import { describe, expect, it } from 'vitest';
import { briefingModel } from '$lib/client/briefingModel';
import { RunState } from '$lib/client/runState.svelte';
import type { FinalResult } from '$lib/client/agentStream';

const QUESTION = 'Have the FloodNet sensors near 189 Atlantic Avenue, Brooklyn recorded flooding?';
// With no fact to show, the backend's line does not end "Here is what they show." (synthesis.NOTHING_TO_SHOW).
const LINE = 'The sources consulted do not answer this question directly, and none of them returned a record that bears on it for this place.';

describe('cannot-answer briefing', () => {
  const final = {
    paragraph: `Scope.\n\n**Answer.**\n${LINE}\n\n**Out of scope.** Title is not assessed.\n\n` +
      'Checks run: citations and numbers on every claim; lead rules on the answer, which is the cited text word for word.',
    citations: {},
    grounding: { tier: 'llm', question: QUESTION, answer_mode: 'extractive', answer_lead: 'cannot_answer', answered: false, claims: [] }
  } as unknown as FinalResult;
  const m = briefingModel(RunState.fromFinal(final, '189 Atlantic Avenue, Brooklyn'), QUESTION);

  it('sets the line at the answer position with no lead word', () => {
    expect(m.lead).toBeNull();
    expect(m.answer.map((p) => p.map((x) => x.text).join('')).join(' ')).toContain('do not answer this question');
  });

  it('does not claim a quoted answer', () => {
    expect(m.checks).toBe('Checks run: citations and numbers on every claim; lead rules on the answer.');
    expect(m.modeLine).not.toContain('word for word');
  });

  it('keeps the clause on an answer that does quote its sources', () => {
    const quoted = { ...final, grounding: { ...final.grounding, answer_lead: 'facts', answered: true } } as unknown as FinalResult;
    expect(briefingModel(RunState.fromFinal(quoted, '189 Atlantic Avenue, Brooklyn'), QUESTION).checks)
      .toBe('Checks run: citations and numbers on every claim; lead rules on the answer, which is the cited text word for word.');
  });
});
