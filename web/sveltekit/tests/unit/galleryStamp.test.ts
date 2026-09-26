import { describe, it, expect } from 'vitest';
import { llmStamp } from '$lib/client/gallery';

const base = { slug: 's', neighborhood: 'n', address: 'a', generated_at: '2026-09-26T20:11Z' };

describe('llmStamp', () => {
  it('stamps LLM entries without repeating the quantization tag', () => {
    expect(llmStamp({ ...base, mode: 'llm', model: 'hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M', quantization: 'Q4_K_M' }))
      .toBe('Generated with hf.co/ibm-granite/granite-4.1-8b-GGUF (Q4_K_M) on 2026-09-26');
  });
  it('returns null for no-LLM entries', () => {
    expect(llmStamp({ ...base, mode: 'no_llm' })).toBeNull();
  });
});
