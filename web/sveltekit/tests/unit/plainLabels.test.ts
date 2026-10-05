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
    expect(sensorStatusWords('good - fs')).toBe('listed as "good - fs" in FloodNet\'s API when this was read');
    expect(sensorStatusWords('needs_driverail')).toBe('listed as "needs_driverail" in FloodNet\'s API when this was read');
    expect(sensorStatusWords('noisy')).not.toMatch(/flagged|maintenance/);
    expect(sensorStatusWords(undefined)).toBeNull();
  });
});
