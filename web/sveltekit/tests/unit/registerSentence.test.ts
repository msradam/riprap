import { describe, expect, it } from 'vitest';
import { registerSentence } from '$lib/client/cardAdapter';

const row = (label: string, detail: string | null) => ({ label, detail });

describe('registerSentence', () => {
  it('states the count, the flags and the listed assets from the values returned', () => {
    const items = [{}, {}];
    const v = { radius_m: 2000, n_inside_sandy_2012: 2, n_in_dep_extreme_2080: 0 };
    expect(registerSentence('NYCHA developments', v, items, [row('RED HOOK WEST', '267 m'), row('RED HOOK EAST', '546 m')])).toBe(
      '2 NYCHA developments listed within 2000 m, 2 inside the 2012 Sandy extent and 0 in the DEP 2080 scenario: RED HOOK WEST (267 m), RED HOOK EAST (546 m).'
    );
  });

  it('uses the singular for one asset and names only the nearest when some are not listed', () => {
    expect(registerSentence('NYC DOH hospitals', { radius_m: 3000 }, [{}], [row('A', '10 m')])).toBe(
      '1 NYC DOH hospital listed within 3000 m: A (10 m).'
    );
    expect(registerSentence('NYC DOE schools', {}, [{}, {}, {}], [row('A', null)])).toBe(
      '3 NYC DOE schools listed within range; the nearest 1: A.'
    );
  });

  it('says so in one short sentence when the register has nothing in range', () => {
    expect(registerSentence('MTA subway/rail entrances', { radius_m: 800 }, [], [])).toBe(
      'No MTA subway/rail entrances listed within 800 m.'
    );
  });
});
