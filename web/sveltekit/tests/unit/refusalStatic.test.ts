/**
 * The public static build (PUBLIC_RIPRAP_STATIC=1) has no query box and no
 * backend, so a refusal there offers no "Edit query" or district link.
 * The live-server case is in refusalActions.test.ts.
 */
import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/svelte';
import ResultsView from '$lib/components/results/ResultsView.svelte';
import { RunState } from '$lib/client/runState.svelte';
import { REFUSAL, REFUSAL_QUERY } from './fixtures/refusal';

vi.mock('$lib/staticSite', () => ({ STATIC_SITE: true, QUICKSTART_URL: 'https://example.org/quickstart' }));

describe('a refusal on the static build', () => {
  it('keeps the statement and offers no action that needs a backend', () => {
    const run = RunState.fromFinal(REFUSAL, REFUSAL_QUERY);
    const { container } = render(ResultsView, { props: { run, queryText: REFUSAL_QUERY, snapshot: true } });
    expect(container.textContent).toContain('Did you mean QN14?');
    expect(container.querySelector('.error-card-actions')).toBeNull();
    expect(container.textContent).not.toMatch(/Edit query|Briefing for QN14/);
  });
});
