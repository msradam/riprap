import { describe, expect, it } from 'vitest';
import { bySource, keySentence, sentencesOf, splitLead } from '$lib/client/briefingModel';
import { parseBriefing } from '$lib/client/parseBriefing';
import { tidy } from '$lib/client/briefingText';
import type { ClaimPart } from '$lib/types/claim';

/** The answer paragraphs as the page gets them: parsed, lead word off. */
function answerOf(md: string): ClaimPart[][] {
  const paras = parseBriefing(`**Answer.**\n${md}`).blocks.flatMap((b) => (b.kind === 'prose' ? [b.parts] : []));
  return [splitLead(paras[0]).parts, ...paras.slice(1)];
}
/** The text as the page sets it (tidy moves a full stop onto its cite). */
const words = (parts: ClaimPart[]) => tidy(parts).map((p) => p.text).join('').replace(/\s+/g, ' ').trim();
const cites = (paras: ClaimPart[][]) => paras.flat().flatMap((p) => (p.cite ? [p.cite] : []));

const QN12 =
  '533 street flooding complaints, counting the 311 descriptors "Street Flooding (SJ)" and "Flooding on Street". ' +
  'From the sources consulted: 4273 NYC 311 flood-related complaints filed inside this area in the last 3 years: 2663 sewer backup, 932 catch basin, 533 street flooding, 145 manhole overflow [nyc311_nta].';
const IDA =
  'Yes. USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address [ida_hwm]. ' +
  'Nearest mark: 174 m away [ida_hwm]. 2 FloodNet community sensors within 600 m have logged 14 above-curb flood events in the last 3 years [floodnet]. ' +
  '82 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years [nyc311]. Peak depth: 1172 mm [floodnet].';

describe('keySentence', () => {
  it('in_lead: the lead sentence before "From the sources consulted:", with the total as support', () => {
    const k = keySentence(answerOf(QN12), { doc_id: 'nyc311_nta', in_lead: true })!;
    expect(words(k.key)).toBe('533 street flooding complaints, counting the 311 descriptors "Street Flooding (SJ)" and "Flooding on Street".');
    // The count comes from the lead fact's source: the key carries its mark, after the full stop.
    expect(cites([k.key])).toEqual(['nyc311_nta']);
    expect(k.key.at(-1)).toEqual({ text: '', cite: 'nyc311_nta' });
    expect(k.rest).toHaveLength(1);
    expect(words(k.rest[0])).toMatch(/^From the sources consulted: 4273 NYC 311/);
    expect(cites(k.rest)).toEqual(['nyc311_nta']);
  });

  it('not in the lead: the first sentence citing the doc leads, the rest keep their order', () => {
    const answer = answerOf(IDA);
    const k = keySentence(answer, { doc_id: 'nyc311', in_lead: false })!;
    expect(words(k.key)).toBe('82 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years.');
    expect(cites([k.key])).toEqual(['nyc311']);
    expect(cites(k.rest)).toEqual(['ida_hwm', 'ida_hwm', 'floodnet', 'floodnet']);
    // No words lost or added.
    const bag = (t: string) => t.split(/\s+/).map((w) => w.replace(/[.]$/, '')).sort();
    expect(bag(`${words(k.key)} ${k.rest.map(words).join(' ')}`)).toEqual(bag(words(answer.flat())));
  });

  it('picks the first of several sentences citing the doc', () => {
    const k = keySentence(answerOf(IDA), { doc_id: 'floodnet', in_lead: false })!;
    expect(words(k.key)).toMatch(/^2 FloodNet community sensors/);
  });

  it('singles out nothing without a lead fact, or when the sentence is not there', () => {
    expect(keySentence(answerOf(IDA), null)).toBeNull();
    expect(keySentence(answerOf(IDA), undefined)).toBeNull();
    expect(keySentence(answerOf(IDA), { doc_id: 'sandy_inundation', in_lead: false })).toBeNull();
    expect(keySentence(answerOf(IDA), { doc_id: 'nyc311', in_lead: true })).toBeNull();
  });
});

describe('sentencesOf', () => {
  it('splits at the gap between sentences, not inside a cited sentence', () => {
    expect(sentencesOf(answerOf(IDA)[0]).map(words)).toHaveLength(5);
  });
});

describe('bySource', () => {
  it('breaks the support into one paragraph per cited source, in order, keeping every sentence and mark', () => {
    const rest = keySentence(answerOf(IDA), { doc_id: 'nyc311', in_lead: false })!.rest;
    const paras = rest.flatMap(bySource);
    expect(paras.map((p) => [...new Set(cites([p]))])).toEqual([['ida_hwm'], ['floodnet']]);
    expect(cites(paras)).toEqual(cites(rest));
    expect(paras.map(words).join(' ')).toBe(rest.map(words).join(' '));
  });

  it('keeps an uncited sentence with the one before it, and a returning source in a new paragraph', () => {
    const [p] = answerOf('A one [a]. A two. B one [b]. A three [a].');
    expect(bySource(p).map(words)).toEqual(['A one. A two.', 'B one.', 'A three.']);
  });
});
