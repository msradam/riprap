import { describe, it, expect } from 'vitest';
import { featureSentence, leadSentence, modelName, standfirst, storyLead } from '$lib/server/galleryStories';

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

describe('standfirst', () => {
  const answer =
    'Preamble.\n\n**Answer.**\nYes. USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address [ida_hwm]. ' +
    '82 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years [nyc311].\n\n**Out of scope.** No.';

  it('with a lead fact, sets the lead word before the key sentence the page shows', () => {
    const lead_fact = { doc_id: 'nyc311', in_lead: false };
    expect(standfirst({ paragraph: answer, grounding: { lead_fact } as never })).toBe(
      'Yes. 82 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years.'
    );
  });

  it('without a lead fact, falls back to the first sentence', () => {
    expect(standfirst({ paragraph: answer, grounding: undefined })).toBe(
      'Yes. USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address.'
    );
  });
});

describe('modelName', () => {
  it('drops a repeated quantization tag', () => {
    const e = { slug: 's', neighborhood: 'n', address: 'a', generated_at: '2026-09-26T19:33Z' };
    expect(modelName({ ...e, mode: 'llm', model: 'hf.co/x-GGUF:Q4_K_M', quantization: 'Q4_K_M' })).toBe('hf.co/x-GGUF (Q4_K_M)');
    expect(modelName({ ...e, mode: 'no_llm' })).toBeNull();
  });
});

describe('featureSentence', () => {
  const p =
    'Preamble.\n\n**In brief.**\nThis address is outside the 2012 Sandy footprint [sandy_inundation]. 82 complaints were filed [nyc311].\n\n' +
    '**Live Observer.**\n2 FloodNet sensors within 600 m logged 14 events [floodnet]. Peak depth: 1172 mm [floodnet, nyc311_nta].';

  it('takes the first sentence citing the doc id, markers removed', () => {
    expect(featureSentence(p, 'floodnet')).toBe('2 FloodNet sensors within 600 m logged 14 events.');
    expect(featureSentence(p, 'nyc311')).toBe('82 complaints were filed.');
  });

  it('is the entry snippet when the index names a feature doc, else the standfirst', () => {
    expect(storyLead({ feature_doc: 'floodnet' }, { paragraph: p, grounding: undefined })).toBe('2 FloodNet sensors within 600 m logged 14 events.');
    expect(storyLead({ feature_doc: 'ida_hwm' }, { paragraph: p, grounding: undefined })).toBe('This address is outside the 2012 Sandy footprint.');
    expect(storyLead({}, { paragraph: p, grounding: undefined })).toBe('This address is outside the 2012 Sandy footprint.');
  });

  it('matches whole ids only and is empty when nothing cites the id', () => {
    expect(featureSentence(p, 'nyc311_nta')).toBe('Peak depth: 1172 mm.');
    expect(featureSentence(p, 'ida_hwm')).toBe('');
  });
});
