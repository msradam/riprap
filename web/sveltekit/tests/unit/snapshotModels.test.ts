import { describe, expect, it } from 'vitest';
import { snapshotModels } from '$lib/client/briefingModel';

const line = (where: string) => ({ name: 'LLM', repo: 'hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M', href: null, where, how: 'LLM endpoint', latency: null, detail: null });

describe('snapshotModels', () => {
  it('names no local endpoint on a snapshot', () => {
    expect(snapshotModels([line('Ollama on this machine (localhost:11434)')])[0].where).toBe('Ollama, run when the snapshot was generated');
    expect(snapshotModels([line('(127.0.0.1:8080)')])[0].where).toBe('Run when the snapshot was generated');
  });
  it('keeps other places as they are', () => {
    expect(snapshotModels([line('CPU'), line('Apple GPU (MPS), in the batch run')]).map((m) => m.where)).toEqual(['CPU', 'Apple GPU (MPS), in the batch run']);
  });
});
