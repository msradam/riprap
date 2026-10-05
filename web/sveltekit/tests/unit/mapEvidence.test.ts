/**
 * The evidence points on Figure 1 come from `final`: Ida high-water marks,
 * FloodNet sensors and 311 complaints, each with the words the map popup
 * and the map point list print, plus the answer's search radii.
 */
import { describe, it, expect } from 'vitest';
import {
  build311Fc, buildFloodnetFc, buildIdaHwmFc, evidencePointRows, searchRadii
} from '$lib/client/runState.svelte';

const final = {
  ida_hwm: {
    radius_m: 800,
    points: [
      { lat: 40.711216, lon: -73.779756, site: 'Intersection of 182nd St. and 90th Ave.', elev_ft: 48,
        height_above_gnd_ft: 0.7, distance_m: 173.9 },
      { site: 'No coordinates', height_above_gnd_ft: 1 }
    ]
  },
  floodnet: {
    radius_m: 600,
    sensors: [{ name: 'Q - 184th St/91st Ave', street: '184th Street', status: 'good', lat: 40.71, lon: -73.77 }]
  },
  nyc311: {
    radius_m: 200,
    points: [{ lat: 40.7099, lon: -73.7763, descriptor: 'Sewer Backup', date: '2026-05-25', address: '91-11 184 STREET' }]
  }
};

describe('evidence point builders', () => {
  it('builds Ida marks with lon/lat order, a unique pid and a data-only detail', () => {
    const fc = buildIdaHwmFc(final)!;
    expect(fc.features).toHaveLength(1);
    const f = fc.features[0];
    expect(f.geometry).toEqual({ type: 'Point', coordinates: [-73.779756, 40.711216] });
    expect(f.properties).toMatchObject({
      pid: 'ida-0', kind: 'ida', name: 'Intersection of 182nd St. and 90th Ave.',
      detail: 'Ida high-water mark, 0.7 ft above ground, 174 m', elev_ft: 48
    });
  });

  it('builds FloodNet sensors and 311 complaints', () => {
    expect(buildFloodnetFc(final)!.features[0].properties).toMatchObject({
      pid: 'floodnet-0', name: 'Q - 184th St/91st Ave',
      detail: 'FloodNet flood sensor, on 184th Street, listed as "good" in FloodNet\'s API when this was read'
    });
    expect(build311Fc(final)!.features[0].properties).toMatchObject({
      pid: 'nyc311-0', name: '91-11 184 STREET', detail: '311 complaint, Sewer backup, 2026-05-25'
    });
  });

  it('reads the district (_nta) variant and is undefined without points', () => {
    const district = { nyc311_nta: { radius_m: null, points: [] } };
    expect(build311Fc(district)).toBeUndefined();
    expect(buildIdaHwmFc({})).toBeUndefined();
    expect(buildFloodnetFc({ floodnet: { sensors: 'bad' } })).toBeUndefined();
    const nta = { ida_hwm_nta: { points: [{ lat: 40.6, lon: -73.9, site: 'S' }] } };
    expect(buildIdaHwmFc(nta)!.features[0].properties?.detail).toBe('Ida high-water mark');
  });

  it('lists the plotted points as rows in the order given', () => {
    const rows = evidencePointRows(buildIdaHwmFc(final), undefined, build311Fc(final));
    expect(rows.map((r) => r.id)).toEqual(['ida-0', 'nyc311-0']);
    expect(rows[1]).toEqual({ id: 'nyc311-0', name: '91-11 184 STREET', meta: '311 complaint, Sewer backup, 2026-05-25' });
  });

  it('reports the search radii that the blocks give, skipping missing ones', () => {
    expect(searchRadii(final)).toEqual([
      { label: 'high-water marks', radius_m: 800, tier: 'empirical' },
      { label: 'FloodNet sensors', radius_m: 600, tier: 'empirical' },
      { label: '311 complaints', radius_m: 200, tier: 'proxy' }
    ]);
    expect(searchRadii({ nyc311_nta: { radius_m: null } })).toEqual([]);
  });
});
