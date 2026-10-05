/** The tier mark's accessible name says what each tier is. */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import EvidenceMark from '$lib/components/glyphs/EvidenceMark.svelte';

describe('EvidenceMark tier descriptions', () => {
  it('does not call a scenario a prediction, and covers an index', () => {
    const name = render(EvidenceMark, { tier: 'modeled' }).getByRole('img').getAttribute('aria-label') ?? '';
    expect(name).toContain('a simulated scenario (not a forecast)');
    expect(name).toContain('an index (a rank from a statistical model)');
    expect(name).not.toMatch(/prediction/);
  });
  it('says a proxy is reports people filed', () => {
    const name = render(EvidenceMark, { tier: 'proxy' }).getByRole('img').getAttribute('aria-label') ?? '';
    expect(name).toContain('reports people filed with 311');
  });
});
