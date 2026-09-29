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
import LandStones from '$lib/components/landing/LandStones.svelte';

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
