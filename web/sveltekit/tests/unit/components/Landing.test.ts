/**
 * Landing components. These are exempted from the NYC-leak audit because
 * they intentionally name shipped cities as features. These tests assert
 * they mount and render the city list, the Stones and the plain statements
 * that replaced the old banner, stat row and badge row.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import CityPicker from '$lib/components/landing/CityPicker.svelte';
import UseBand from '$lib/components/landing/UseBand.svelte';
import LandFooter from '$lib/components/landing/LandFooter.svelte';
import LandStones from '$lib/components/landing/LandStones.svelte';
import LandHeader from '$lib/components/landing/LandHeader.svelte';

describe('Landing smoke', () => {
  it('CityPicker links every shipped city', () => {
    const { container } = render(CityPicker);
    const text = container.textContent ?? '';
    for (const city of ['NYC', 'Boston', 'Chicago', 'Seattle', 'San Francisco', 'Albany']) {
      expect(text, `CityPicker missing ${city}`).toContain(city);
    }
    expect(container.querySelectorAll('a')).toHaveLength(6);
  });

  it('UseBand says evidence, not advice', () => {
    const { container } = render(UseBand);
    expect(container.textContent).toContain('Riprap returns evidence, not advice.');
  });

  it('LandFooter carries the beta status and the standards', () => {
    const { container } = render(LandFooter);
    const text = container.textContent ?? '';
    expect(text).toContain('This is open beta.');
    expect(text).toMatch(/WCAG 2\.2 AA/);
    expect(text).toContain('Riprap');
  });

  it('LandStones names all five Stones', () => {
    const { container } = render(LandStones);
    const text = container.textContent ?? '';
    for (const name of ['Cornerstone', 'Touchstone', 'Keystone', 'Lodestone', 'Capstone']) {
      expect(text).toContain(name);
    }
    expect(container.querySelectorAll('dt')).toHaveLength(5);
  });

  it('LandHeader renders the riprap wordmark', () => {
    const { container } = render(LandHeader);
    expect(container.textContent?.toLowerCase()).toContain('riprap');
  });
});
