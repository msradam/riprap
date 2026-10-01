/**
 * Landing components. These are exempted from the NYC-leak audit because
 * they intentionally name shipped cities as features. These tests assert
 * they mount and render the city list, the Stones and the plain statements
 * that replaced the old banner, stat row and badge row.
 */
import { describe, it, expect } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import LandHero from '$lib/components/landing/LandHero.svelte';
import CityPicker from '$lib/components/landing/CityPicker.svelte';
import UseBand from '$lib/components/landing/UseBand.svelte';
import LandFor from '$lib/components/landing/LandFor.svelte';
import LandStones from '$lib/components/landing/LandStones.svelte';
import LandStories from '$lib/components/landing/LandStories.svelte';

describe('Landing smoke', () => {
  it('LandStories shows an entry\'s reason under its title only when the index gives one', () => {
    const base = { neighborhood: 'Red Hook, Brooklyn', address: '80 Pioneer Street', question: null, generated_at: '2026-09-29T12:34Z', lead: '' };
    const { container } = render(LandStories, {
      stories: [
        { ...base, slug: 'red-hook', reason: 'Two NYCHA developments inside the 2012 Sandy extent.' },
        { ...base, slug: 'gowanus', neighborhood: 'Gowanus, Brooklyn' }
      ]
    });
    const reasons = [...container.querySelectorAll('.place-reason')].map((p) => p.textContent);
    expect(reasons).toEqual(['Two NYCHA developments inside the 2012 Sandy extent.']);
  });

  it('CityPicker links every shipped city', () => {
    const { container } = render(CityPicker);
    const text = container.textContent ?? '';
    for (const city of ['NYC', 'Chicago', 'Seattle', 'Albany']) {
      expect(text, `CityPicker missing ${city}`).toContain(city);
    }
    expect(container.querySelectorAll('a')).toHaveLength(4);
  });

  it('UseBand says evidence, not advice', () => {
    const { container } = render(UseBand);
    expect(container.textContent).toContain('Riprap returns evidence, not advice.');
  });

  it('LandFor says what Riprap is for, and links the tools that do other jobs better', () => {
    const { container } = render(LandFor);
    expect([...container.querySelectorAll('h2')].map((h) => h.textContent)).toEqual([
      'What Riprap is for, and what it is not'
    ]);
    expect([...container.querySelectorAll('li a')].map((a) => a.getAttribute('href'))).toEqual([
      'https://dataviz.floodnet.nyc/',
      'https://www.weather.gov/okx/',
      'https://a858-nycnotify.nyc.gov/',
      'https://msc.fema.gov/portal/home',
      'https://www.floodhelpny.org/',
      'https://communityprofiles.planning.nyc.gov/',
      'https://rebuildbydesign.org/rainproof-nyc-map/'
    ]);
    // The saved-briefings sentence is for the static site only.
    expect(container.textContent).not.toContain('This public copy shows saved briefings only');
  });

  it('says the three experimental models are there, and that a claim may cite one', () => {
    const text = (c: typeof LandFor) => (render(c).container.textContent ?? '').replace(/\s+/g, ' ');
    expect(text(LandFor)).toContain('Whatever they say is labelled experimental');
    expect(text(LandStones)).toContain('or, where it is labelled experimental, one of three models.');
  });

  it('LandStones names all five Stones', () => {
    const { container } = render(LandStones);
    const text = container.textContent ?? '';
    for (const name of ['Cornerstone', 'Touchstone', 'Keystone', 'Lodestone', 'Capstone']) {
      expect(text).toContain(name);
    }
    expect(container.querySelectorAll('dt')).toHaveLength(5);
  });
});

describe('LandHero empty submit', () => {
  const HINT = 'Type an address, a community district such as QN12, or a question.';

  it('focuses the input and shows the hint in a status region, then clears it on typing', async () => {
    const { container, getByRole } = render(LandHero);
    const input = getByRole('textbox') as HTMLInputElement;
    const status = container.querySelector('#land-query-hint');
    expect(status).toHaveAttribute('role', 'status');
    expect(status).toBeEmptyDOMElement();

    await fireEvent.submit(container.querySelector('form[role=search]')!);
    expect(status).toHaveTextContent(HINT);
    expect(document.activeElement).toBe(input);
    expect(input).toHaveAttribute('aria-describedby', 'land-query-hint');
    expect(input).not.toHaveAttribute('required');
    expect(getByRole('button', { name: 'Brief this place' })).toBeEnabled();

    await userEvent.type(input, 'Q');
    expect(status).toBeEmptyDOMElement();
    expect(input).not.toHaveAttribute('aria-describedby');
  });
});
