/**
 * The map point list and the map's register layer are built from the same
 * FeatureCollection, and the area outline is read from `final.area_boundary`.
 */
import { describe, it, expect } from 'vitest';
import { areaBoundaryGeometry, buildRegisterPointsFc, mapPointRows, RunState } from '$lib/client/runState.svelte';
import type { FinalResult } from '$lib/client/agentStream';

describe('mapPointRows', () => {
  const fc = buildRegisterPointsFc({
    mta_entrances: {
      entrances: [
        { station_name: 'Carroll St', daytime_routes: 'F G', station_id: 'F21', entrance_lat: 40.68,
          entrance_lon: -73.99, distance_m: 212.4, inside_sandy_2012: true, dep_extreme_2080_category: 'future high tides',
          dep_moderate_2050_category: 'outside' },
        { station_name: 'Carroll St', daytime_routes: 'F G', station_id: 'F21', entrance_lat: 40.681,
          entrance_lon: -73.991, distance_m: 250, inside_sandy_2012: false, dep_extreme_2080_category: null }
      ]
    },
    doh_hospitals: { hospitals: [{ facility_name: 'No coords' }] }
  });

  it('gives one row per mapped point, with a unique id, distance and scenarios', () => {
    expect(mapPointRows(fc)).toEqual([
      { id: 'subway-0', name: 'Carroll St (F G)', distance: '212 m',
        // The kind of category is said: the tidal category is not stormwater flooding.
        scenarios: 'Sandy 2012 extent, Extreme Flood 2080 stormwater map (future high tides)' },
      { id: 'subway-1', name: 'Carroll St (F G)', distance: '250 m', scenarios: 'none' }
    ]);
  });

  it('is empty when there are no points', () => {
    expect(mapPointRows(undefined)).toEqual([]);
  });

  it('maps the schools of an area briefing, which have no distance', () => {
    const final = {
      paragraph: '',
      doe_schools_nta: {
        schools: [{ loc_name: 'P.S. 15', loc_code: 'K015', school_lat: 40.676, school_lon: -74.01,
          distance_m: null, inside_sandy_2012: true, dep_extreme_2080_category: 'outside' }]
      }
    };
    const areaFc = buildRegisterPointsFc(final);
    expect(areaFc.features).toHaveLength(1);
    expect(mapPointRows(areaFc)).toEqual([
      { id: 'school-0', name: 'P.S. 15', distance: '', scenarios: 'Sandy 2012 extent' }
    ]);
    const run = new RunState();
    run.applyFinal(final as FinalResult);
    expect(run.mapPoints).toEqual([{ id: 'school-0', name: 'P.S. 15', meta: 'scenarios: Sandy 2012 extent' }]);
  });
});

describe('areaBoundaryGeometry', () => {
  const ring = [[-74, 40.6], [-73.9, 40.6], [-73.9, 40.7], [-74, 40.6]];

  it('returns a Polygon or MultiPolygon geometry', () => {
    const f = { paragraph: '', area_boundary: { geojson: { type: 'Polygon', coordinates: [ring] } } } as FinalResult;
    expect(areaBoundaryGeometry(f)?.type).toBe('Polygon');
  });

  it('ignores address runs and malformed geometry', () => {
    expect(areaBoundaryGeometry({ paragraph: '' })).toBeUndefined();
    const point = { paragraph: '', area_boundary: { geojson: { type: 'Point', coordinates: [-74, 40.6] } } };
    expect(areaBoundaryGeometry(point as FinalResult)).toBeUndefined();
  });
});
