import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import ResultsView from '$lib/components/results/ResultsView.svelte';
import { RunState } from '$lib/client/runState.svelte';
import { firstSentence, suggestedDistrict } from '$lib/client/briefingModel';
import { REFUSAL, REFUSAL_QUERY } from './fixtures/refusal';

describe('suggestedDistrict', () => {
  it('finds the district a refusal suggests', () => {
    expect(suggestedDistrict('Riprap covers community districts. Did you mean QN14?')).toBe('QN14');
  });

  it('is null without a suggestion or with a malformed one', () => {
    expect(suggestedDistrict('Give a street address on that block.')).toBeNull();
    expect(suggestedDistrict('Did you mean Queens?')).toBeNull();
    expect(suggestedDistrict('Did you mean QN14 instead')).toBeNull();
  });
});

describe('firstSentence', () => {
  it('takes the first sentence across cited parts', () => {
    expect(firstSentence([{ text: 'Yes, it flooded', cite: 'sandy' }, { text: '. Twice since.' }])).toBe('Yes, it flooded.');
  });

  it('is null for an empty paragraph', () => {
    expect(firstSentence(undefined)).toBeNull();
    expect(firstSentence([])).toBeNull();
  });
});

describe('a refusal on a live server', () => {
  it('offers the suggested district and the query box', () => {
    const run = RunState.fromFinal(REFUSAL, REFUSAL_QUERY);
    const { container } = render(ResultsView, { props: { run, queryText: REFUSAL_QUERY } });
    const links = [...container.querySelectorAll('.error-card-actions a')].map((a) => a.textContent);
    expect(links).toEqual(['Briefing for QN14', 'Edit query']);
  });
});
