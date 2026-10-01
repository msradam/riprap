/**
 * The public static build (PUBLIC_RIPRAP_STATIC=1) has no backend, so no
 * landing call to action may lead to a live briefing at /q/.
 */
import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/svelte';
import LandHero from '$lib/components/landing/LandHero.svelte';
import LandCollab from '$lib/components/landing/LandCollab.svelte';
import { load } from '../../../src/routes/+page.server';

vi.mock('$lib/staticSite', () => ({ STATIC_SITE: true, QUICKSTART_URL: 'https://example.org/quickstart' }));

const data = await load();

describe('the landing on the static build', () => {
  it('offers the gallery and the quickstart instead of the query box, and chips open gallery entries', () => {
    const { container, getByRole } = render(LandHero, { chips: data.chips, specimen: data.specimen, count: data.count });
    expect(container.querySelector('form')).toBeNull();
    expect(getByRole('link', { name: `Browse ${data.count} briefings` })).toHaveAttribute('href', '/gallery/');
    expect(getByRole('link', { name: 'Run it yourself' })).toHaveAttribute('href', 'https://example.org/quickstart');
    expect(container.textContent).toContain('To ask your own question, run Riprap on your laptop');
    const chips = [...getByRole('list', { name: 'Try a real question' }).querySelectorAll('a')];
    expect(chips.map((a) => a.getAttribute('href'))).toEqual([
      '/gallery/hollis-since-ida/',
      '/gallery/qn12-complaints/',
      '/gallery/bk06-nycha/',
      '/gallery/qn12/'
    ]);
    expect(container.querySelector('a[href^="/q/"]')).toBeNull();
  });

  it('names the cities without their live sample links', () => {
    const { container } = render(LandCollab);
    for (const city of ['NYC', 'Chicago', 'Seattle', 'Albany']) expect(container.textContent).toContain(city);
    expect(container.textContent).not.toContain('Try a sample address');
    expect(container.querySelector('a[href^="/q/"]')).toBeNull();
  });
});
