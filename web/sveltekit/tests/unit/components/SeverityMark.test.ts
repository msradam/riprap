/**
 * SeverityMark inverts app/score.py's tier (1 = High exposure .. 4 =
 * Limited exposure) into the --riprap-sev-* ramp's direction (sev-1 =
 * gray/mild .. sev-4 = red/worst). Getting this backwards would color
 * "Limited exposure" red and "High exposure" gray — the whole point of
 * a severity axis, silently inverted.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import SeverityMark from '$lib/components/glyphs/SeverityMark.svelte';

describe('SeverityMark scoreTier -> visual severity inversion', () => {
  it('scoreTier 1 (High exposure) renders the reddest, fullest step', () => {
    const { container } = render(SeverityMark, { props: { scoreTier: 1, size: 12 } });
    const rect = container.querySelector('rect');
    expect(rect?.getAttribute('fill')).toBe('var(--riprap-sev-4)');
  });

  it('scoreTier 4 (Limited exposure) renders the grayest, smallest step', () => {
    const { container } = render(SeverityMark, { props: { scoreTier: 4, size: 12 } });
    const rect = container.querySelector('rect');
    expect(rect?.getAttribute('fill')).toBe('var(--riprap-sev-1)');
  });

  it('scoreTier 0 (No flagged exposure) renders nothing', () => {
    const { container } = render(SeverityMark, { props: { scoreTier: 0, size: 12 } });
    expect(container.querySelector('svg')).toBeNull();
  });
});
