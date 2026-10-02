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

  it('labels the experimental models in plain words, with no latency for a precomputed one', () => {
    const lines = modelLines([
      { name: 'Granite TTM r2 Battery Surge (experimental)', repo: 'msradam/granite-ttm-r2-battery-surge',
        where: 'CPU, in this server', how: 'loaded', latency_s: 0.42 },
      { name: 'A saved model (experimental)', repo: 'example/saved-model',
        where: 'an earlier batch run; its saved output is read', how: 'precomputed', latency_s: null },
      { name: 'LLM', repo: 'ibm-granite/granite-4.1-8b', where: 'LLM endpoint api.example.org', how: 'endpoint', latency_s: 2, calls: 1 },
    ]);
    expect(lines.map((l) => l.how)).toEqual(['run for this briefing', 'not run for this briefing', 'LLM endpoint']);
    expect(lines.map((l) => l.latency)).toEqual(['0.4 s', null, '2.0 s over 1 call']);
    // Each `where` opens a sentence in the list.
    expect(lines.map((l) => l.where)).toEqual([
      'CPU, in this server', 'An earlier batch run; its saved output is read', 'LLM endpoint api.example.org',
    ]);
    expect(lines[1].href).toBe('https://huggingface.co/example/saved-model');
  });

  it('prints an unpublished model (repo: null) with no link, and does not throw', () => {
    // The land-cover model is trained in the repository and has no Hugging Face page.
    const [line] = modelLines([
      { name: 'NYC land-cover model (experimental)', repo: null,
        where: 'an earlier batch run; its saved output is read', how: 'precomputed', latency_s: null },
    ]);
    expect(line.repo).toBe('weights not published');
    expect(line.href).toBeNull();
  });

  it('returns nothing when models is missing', () => {
    expect(modelLines(undefined)).toEqual([]);
  });
});
