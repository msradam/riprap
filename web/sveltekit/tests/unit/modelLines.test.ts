import { describe, it, expect } from 'vitest';
import { modelLines } from '$lib/client/cardAdapter';

describe('modelLines', () => {
  it('builds Hugging Face links, latency text and precomputed detail', () => {
    const lines = modelLines([
      { name: 'Granite TTM r2, Battery surge fine-tune', repo: 'msradam/Granite-TTM-r2-Battery-Surge',
        where: 'CPU', how: 'loaded', latency_s: 1.4 },
      { name: 'Prithvi-EO 2.0, NYC pluvial fine-tune', repo: 'msradam/Prithvi-EO-2.0-NYC-Pluvial',
        where: 'Apple GPU (MPS), in the batch run', how: 'precomputed', detail: 'batch output for 2021-09-01' },
      { name: 'LLM', repo: 'hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M',
        where: 'Ollama on this machine (localhost:11434)', how: 'endpoint', latency_s: 30.5, calls: 2 },
      { name: 'Local tag', repo: 'granite4:8b', where: 'Ollama', how: 'endpoint', latency_s: null, detail: 'ignored' },
    ]);
    expect(lines.map((l) => l.href)).toEqual([
      'https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge',
      'https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial',
      'https://huggingface.co/ibm-granite/granite-4.1-8b-GGUF',
      null,
    ]);
    expect(lines.map((l) => l.latency)).toEqual(['1.4 s', null, '30.5 s over 2 calls', null]);
    expect(lines.map((l) => l.how)).toEqual(['loaded', 'precomputed', 'LLM endpoint', 'LLM endpoint']);
    expect(lines.map((l) => l.detail)).toEqual([null, 'batch output for 2021-09-01', null, null]);
  });

  it('returns nothing when models is missing', () => {
    expect(modelLines(undefined)).toEqual([]);
  });
});
