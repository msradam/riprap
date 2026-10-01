/**
 * The briefing's polite live region says what a live run is doing, then
 * that the briefing has landed. A static snapshot and an errored run are
 * not loading, so they announce no loading status.
 */
import { describe, expect, it, beforeEach } from 'vitest';
import { render } from '@testing-library/svelte';
import { tick } from 'svelte';
import ResultsView from '$lib/components/results/ResultsView.svelte';
import { RunState } from '$lib/client/runState.svelte';
import { resetStores } from './helpers/stores';
import type { FinalResult } from '$lib/client/agentStream';

const PLACE = '90-01 183rd Street, Queens';
const final = {
  intent: 'single_address',
  paragraph: '**In brief.**\nThis address is outside the 2012 Sandy extent [sandy_inundation].',
  citations: {},
  grounding: { tier: 'no_llm', note: 'no question' }
} as unknown as FinalResult;
const region = (c: HTMLElement) => c.querySelector('#region-briefing > [aria-live="polite"]')?.textContent;

beforeEach(resetStores);

describe('the briefing live region', () => {
  it('announces the loading status while a live run is loading', () => {
    const { container } = render(ResultsView, { props: { run: new RunState(), queryText: PLACE } });
    expect(region(container)).toBe('Resolving the place');
  });

  it('announces no loading status on a static snapshot', () => {
    const { container } = render(ResultsView, { props: { run: RunState.fromFinal(final, PLACE), queryText: PLACE, snapshot: true } });
    expect(region(container)).toBe('');
  });

  it('drops the loading status when a live run errors', async () => {
    const run = new RunState();
    const { container } = render(ResultsView, { props: { run, queryText: PLACE } });
    expect(region(container)).toBe('Resolving the place');
    run.errorState = 'backend';
    await tick();
    expect(region(container)).toBe('');
    // The error card is the alert.
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
  });

  it('announces a live briefing once it lands', async () => {
    const run = new RunState();
    const { container } = render(ResultsView, { props: { run, queryText: PLACE } });
    run.applyFinal(final);
    run.finish();
    await tick();
    expect(region(container)).toMatch(/^Briefing ready\./);
  });
});
