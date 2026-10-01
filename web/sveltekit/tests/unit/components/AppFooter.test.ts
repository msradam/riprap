/**
 * AppFooter — footer with the "informational only" disclaimer.
 * Previously hardcoded the NYC-only residents-resource links
 * (FloodHelpNY, FloodNet NYC) into every footer render. Now those
 * are gated on the active deployment being NYC.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { render } from '@testing-library/svelte';
import AppFooter from '$lib/components/shell/AppFooter.svelte';
import { resetStores, seedForCity } from '../helpers/stores';
import { ALL_CITIES, CHICAGO, NYC } from '../fixtures/cities';

beforeEach(resetStores);

describe('AppFooter NYC-only resource links are deployment-gated', () => {
  it('renders FloodHelpNY + FloodNet NYC under NYC chip', () => {
    seedForCity(NYC);
    const { container } = render(AppFooter);
    const text = container.textContent ?? '';
    expect(text).toContain('FloodHelpNY');
    expect(text).toContain('FloodNet NYC');
  });

  it('hides FloodHelpNY + FloodNet NYC under Chicago chip', () => {
    seedForCity(CHICAGO);
    const { container } = render(AppFooter);
    const text = container.textContent ?? '';
    expect(text).not.toContain('FloodHelpNY');
    expect(text).not.toContain('FloodNet NYC');
  });

  it.each(ALL_CITIES.filter((c) => c.key !== 'nyc').map((c) => [c.key, c] as const))(
    '%s footer contains zero NYC-only resource link',
    (_key, city) => {
      resetStores();
      seedForCity(city);
      const { container } = render(AppFooter);
      const text = container.textContent ?? '';
      expect(text).not.toContain('FloodHelpNY');
      expect(text).not.toContain('FloodNet NYC');
      expect(text).not.toContain('floodhelpny.org');
      expect(text).not.toContain('floodnet.nyc');
    },
  );

  it('always shows the universal disclaimer regardless of deployment', () => {
    seedForCity(CHICAGO);
    const { container } = render(AppFooter);
    const text = container.textContent ?? '';
    expect(text).toContain('Riprap is a reference dossier');
    expect(text).toContain('informational only');
  });
});

describe('AppFooter site lines (the landing uses this footer too)', () => {
  it('carries the beta status with its feedback link and the standards', () => {
    const { container, getByRole } = render(AppFooter);
    const text = container.textContent ?? '';
    expect(text).toContain('This is open beta.');
    expect(text).toMatch(/WCAG 2\.2 AA/);
    expect(getByRole('link', { name: 'Send feedback' })).toHaveAttribute('href', expect.stringContaining('/issues/new'));
  });

  it('says which cities are experimental and that the experimental layers read satellite imagery', () => {
    const text = (render(AppFooter).container.textContent ?? '').replace(/\s+/g, ' ');
    expect(text).toContain('New York City is the production city; Chicago, Seattle and Albany are experimental.');
    expect(text).toContain('the experimental layers also read Copernicus Sentinel satellite imagery.');
    expect(text).not.toMatch(/coverage is expanding|All data comes from/);
  });

  it('drops the disclaimer when the page already carries it', () => {
    const { container } = render(AppFooter, { props: { disclaimer: false } });
    expect(container.textContent).not.toContain('Riprap is a reference dossier');
    expect(container.textContent).toContain('This is open beta.');
  });
});
