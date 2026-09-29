/** Map list labels say 311 descriptors and FloodNet statuses in words. */
import { describe, it, expect } from 'vitest';
import { plainDescriptor, sensorStatusWords } from '$lib/client/runState.svelte';

describe('plain map labels', () => {
  it('drops 311 descriptor codes', () => {
    expect(plainDescriptor('Sewer Backup (Use Comments) (SA)')).toBe('Sewer backup');
    expect(plainDescriptor('Catch Basin Clogged/Flooding (Use Comments) (SC)')).toBe('Catch basin clogged or flooding');
    expect(plainDescriptor('Street Flooding (SJ)')).toBe('Street flooding');
    expect(plainDescriptor('')).toBeNull();
  });
  it('says FloodNet statuses in words', () => {
    expect(sensorStatusWords('good - fs')).toBe('in good working order');
    expect(sensorStatusWords('needs_driverail')).toBe('flagged by FloodNet for maintenance');
    expect(sensorStatusWords(undefined)).toBeNull();
  });
});
