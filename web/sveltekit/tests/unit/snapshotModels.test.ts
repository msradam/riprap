import { describe, expect, it } from 'vitest';
import { snapshotModels } from '$lib/client/briefingModel';

const line = (where: string) => ({ name: 'LLM', repo: 'hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M', href: null, where, how: 'LLM endpoint', latency: null });

describe('snapshotModels', () => {
  it('names no local endpoint on a snapshot', () => {
    expect(snapshotModels([line('Ollama on this machine (localhost:11434)')])[0].where).toBe('Ollama, run when the snapshot was generated');
    expect(snapshotModels([line('(127.0.0.1:8080)')])[0].where).toBe('Run when the snapshot was generated');
  });
  it('does not say a model ran in this server', () => {
    expect(snapshotModels([line('CPU, in this server')])[0].where).toBe('CPU, in the server that made the snapshot');
  });
  it('keeps other places as they are', () => {
    expect(snapshotModels([line('CPU'), line('Apple GPU (MPS), in the batch run'), line('An earlier batch run; its saved output is read')]).map((m) => m.where))
      .toEqual(['CPU', 'Apple GPU (MPS), in the batch run', 'An earlier batch run; its saved output is read']);
  });
});
