import { describe, it, expect } from 'vitest';
import { modelLines } from '$lib/client/cardAdapter';

describe('modelLines', () => {
  it('builds Hugging Face links, latency text and the endpoint label', () => {
    const lines = modelLines([
      { name: 'LLM', repo: 'ibm-granite/granite-4.1-8b', where: 'LLM endpoint api.example.org', how: 'endpoint', latency_s: 1.4 },
      { name: 'LLM', repo: 'hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M',
        where: 'Ollama on this machine (localhost:11434)', how: 'endpoint', latency_s: 30.5, calls: 2 },
      { name: 'Local tag', repo: 'granite4:8b', where: 'Ollama', how: 'endpoint', latency_s: null },
    ]);
    expect(lines.map((l) => l.href)).toEqual([
      'https://huggingface.co/ibm-granite/granite-4.1-8b',
      'https://huggingface.co/ibm-granite/granite-4.1-8b-GGUF',
      null,
    ]);
    expect(lines.map((l) => l.latency)).toEqual(['1.4 s', '30.5 s over 2 calls', null]);
    expect(lines.map((l) => l.how)).toEqual(['LLM endpoint', 'LLM endpoint', 'LLM endpoint']);
  });

  it('returns nothing when models is missing', () => {
    expect(modelLines(undefined)).toEqual([]);
  });
});
