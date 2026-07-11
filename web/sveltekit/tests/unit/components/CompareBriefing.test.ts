/**
 * CompareBriefing — the two-place compare-mode briefing. Renders the
 * reconciler paragraph, both target labels, and per-place structured
 * step data.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import CompareBriefing from '$lib/components/briefing/CompareBriefing.svelte';
import type { Citation } from '$lib/types/claim';

const PARAGRAPH = 'PLACE A is inside the 2012 Sandy zone. PLACE B is outside.';
const CITATIONS: Record<string, Citation> = {};
const TARGETS = [
  { label: 'PLACE A', address: '189 Atlantic Avenue, Brooklyn, NY' },
  { label: 'PLACE B', address: '200 East Houston Street, New York, NY' },
];

describe('CompareBriefing rendering', () => {
  it('renders the reconciler paragraph + both target labels', () => {
    const { container } = render(CompareBriefing, {
      props: {
        paragraph: PARAGRAPH,
        citations: CITATIONS,
        targets: TARGETS,
      },
    });
    const text = container.textContent ?? '';
    expect(text).toContain('PLACE A');
    expect(text).toContain('PLACE B');
  });

  it('crash-free when targets is empty', () => {
    const { container } = render(CompareBriefing, {
      props: { paragraph: '', citations: {}, targets: [] },
    });
    expect(container).toBeTruthy();
  });

  // Guards against step/field-name drift between the pebble outputs and the
  // "Key differences" bar. The structured payloads use the live step names
  // (microtopo_lidar, floodnet) and current field names (point_elev_m,
  // n_flood_events_3y); a rename on either side must update both.
  it('derives Key-differences rows from current pebble field names', () => {
    const { container } = render(CompareBriefing, {
      props: {
        paragraph: PARAGRAPH,
        citations: CITATIONS,
        targets: TARGETS,
        structuredA: {
          microtopo_lidar: { point_elev_m: 2.1 },
          floodnet: { n_flood_events_3y: 12 },
          nyc311: { n: 5 },
        },
        structuredB: {
          microtopo_lidar: { point_elev_m: 6.0 },
          floodnet: { n_flood_events_3y: 2 },
          nyc311: { n: 20 },
        },
      },
    });
    const text = container.textContent ?? '';
    expect(text).toContain('Elevation');
    expect(text).toContain('2.1 m');
    expect(text).toContain('6.0 m');
    expect(text).toContain('Sensor events');
    expect(text).toContain('311 complaints');
  });
});
