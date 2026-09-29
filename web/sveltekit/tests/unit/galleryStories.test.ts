import { describe, it, expect } from 'vitest';
import { leadSentence, modelName } from '$lib/server/galleryStories';

describe('leadSentence', () => {
  it('keeps the sentence after a bare lead word and drops citation markers', () => {
    const p = 'Preamble.\n\n**Answer.**\nYes. USGS surveyed 2 marks; the highest stood 0.76 ft [ida_hwm]. Nearest mark: 174 m [ida_hwm].';
    expect(leadSentence(p)).toBe('Yes. USGS surveyed 2 marks; the highest stood 0.76 ft.');
  });

  it('reads the In brief section and stops at the next bold heading', () => {
    const p = '**In brief.** This address is outside the 2012 Sandy extent [sandy]. It is in zone X.\n\n**Out of scope.** No.';
    expect(leadSentence(p)).toBe('This address is outside the 2012 Sandy extent.');
  });

  it('returns an empty string when there is no answer section', () => {
    expect(leadSentence('No sections here.')).toBe('');
  });
});

describe('modelName', () => {
  it('drops a repeated quantization tag', () => {
    const e = { slug: 's', neighborhood: 'n', address: 'a', generated_at: '2026-09-26T19:33Z' };
    expect(modelName({ ...e, mode: 'llm', model: 'hf.co/x-GGUF:Q4_K_M', quantization: 'Q4_K_M' })).toBe('hf.co/x-GGUF (Q4_K_M)');
    expect(modelName({ ...e, mode: 'no_llm' })).toBeNull();
  });
});
