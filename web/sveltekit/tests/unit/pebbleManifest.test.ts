import { describe, expect, it, beforeEach, vi } from 'vitest';
import { pebbleInScope } from '$lib/client/cardAdapter';
import { pebbleManifest, type PebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import { resetStores, seedForCity } from './helpers/stores';
import { NYC } from './fixtures/cities';

describe('pebbleInScope', () => {
  const pebble = (scope?: PebbleManifest['scope']) => ({ ...NYC.manifest.pebbles[0], scope }) as PebbleManifest;

  it('runs a source with scope any for an address and for a district', () => {
    expect(pebbleInScope(pebble('any'), 'single_address')).toBe(true);
    expect(pebbleInScope(pebble('any'), 'neighborhood')).toBe(true);
    expect(pebbleInScope(pebble('any'), 'development_check')).toBe(true);
    expect(pebbleInScope(pebble('any'), null)).toBe(true);
  });

  it('keeps point and polygon sources to their own kind of place', () => {
    expect(pebbleInScope(pebble('point'), 'single_address')).toBe(true);
    expect(pebbleInScope(pebble('point'), 'neighborhood')).toBe(false);
    expect(pebbleInScope(pebble('polygon'), 'neighborhood')).toBe(true);
    expect(pebbleInScope(pebble('polygon'), 'single_address')).toBe(false);
    expect(pebbleInScope(pebble(undefined), 'single_address')).toBe(true);
    expect(pebbleInScope(pebble(undefined), 'neighborhood')).toBe(false);
  });

  it("keeps each briefing's sources out of the other", () => {
    const of = (hazard?: PebbleManifest['hazard']) => ({ ...pebble('any'), hazard }) as PebbleManifest;
    expect(pebbleInScope(of('heat'), 'single_address')).toBe(false);
    expect(pebbleInScope(of('heat'), 'single_address', true)).toBe(true);
    expect(pebbleInScope(of('flood'), 'single_address')).toBe(true);
    expect(pebbleInScope(of('flood'), 'single_address', true)).toBe(false);
    for (const heat of [false, true]) {
      expect(pebbleInScope(of('any'), 'single_address', heat)).toBe(true);
      // A manifest saved before the field existed is not restricted.
      expect(pebbleInScope(of(undefined), 'single_address', heat)).toBe(true);
    }
  });
});

describe('loadForDeployment when the fetch fails', () => {
  beforeEach(() => {
    resetStores();
    seedForCity(NYC);
  });
  const expectCleared = () => {
    expect(pebbleManifest.byId).toEqual({});
    expect(pebbleManifest.byStone).toEqual({});
    expect(pebbleManifest.stones).toEqual([]);
    expect(pebbleManifest.loaded).toBe(false);
  };

  it('clears the previous manifest when the federal one answers with an error', async () => {
    globalThis.fetch = vi.fn(async () => new Response('{}', { status: 503 })) as unknown as typeof fetch;
    expect(Object.keys(pebbleManifest.byId).length).toBeGreaterThan(0);
    await pebbleManifest.loadForDeployment(null);
    expect(vi.mocked(globalThis.fetch)).toHaveBeenCalledWith('/api/pebbles?deployment=federal');
    expectCleared();
    expect(pebbleManifest.error).toContain('503');
  });

  it('clears it when the request itself fails', async () => {
    globalThis.fetch = vi.fn(async () => { throw new TypeError('Failed to fetch'); }) as unknown as typeof fetch;
    await pebbleManifest.loadForDeployment('chicago');
    expectCleared();
  });
});
