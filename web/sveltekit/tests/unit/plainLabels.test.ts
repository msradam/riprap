/** Map list labels say 311 descriptors in words. */
import { describe, it, expect } from 'vitest';
import { plainDescriptor } from '$lib/client/runState.svelte';

describe('plain map labels', () => {
  it('drops 311 descriptor codes', () => {
    expect(plainDescriptor('Sewer Backup (Use Comments) (SA)')).toBe('Sewer backup');
    expect(plainDescriptor('Catch Basin Clogged/Flooding (Use Comments) (SC)')).toBe('Catch basin clogged or flooding');
    expect(plainDescriptor('Street Flooding (SJ)')).toBe('Street flooding');
    expect(plainDescriptor('')).toBeNull();
  });
});
