import { describe, expect, it } from 'vitest';
import { keyedAnswer, splitLead } from '$lib/client/briefingModel';
import { parseBriefing } from '$lib/client/parseBriefing';
import { tidy } from '$lib/client/briefingText';
import type { ClaimPart } from '$lib/types/claim';

function answerOf(md: string): ClaimPart[][] {
  const paras = parseBriefing(`**Answer.**\n${md}`).blocks.flatMap((b) => (b.kind === 'prose' ? [b.parts] : []));
  return [splitLead(paras[0]).parts, ...paras.slice(1)];
}
const words = (parts: ClaimPart[]) => tidy(parts).map((p) => p.text).join('').replace(/\s+/g, ' ').trim();
const isExp = (id: string) => id === 'lake_michigan_water_level';

// An answer in the shape of hollis-since-ida's: an experimental source
// sits between the Ida marks and the 311 count.
const IDA =
  'Yes. USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address [ida_hwm]. ' +
  'Experimental: the nearest gauge read 579.4 ft, 18.1 km from this address [lake_michigan_water_level]. ' +
  'The reading is for the lake, not for this street [lake_michigan_water_level]. ' +
  '82 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years [nyc311].';

describe('keyedAnswer', () => {
  it('puts paragraphs from experimental sources last, each opening with the badge', () => {
    const r = keyedAnswer(answerOf(IDA), { doc_id: 'nyc311', in_lead: false }, isExp)!;
    expect(words(r.key!)).toMatch(/^82 NYC 311/);
    expect(r.paras.map((p) => !!p[0].exp)).toEqual([false, false, true]);
    expect(words(r.paras[1])).toMatch(/^USGS surveyed/);
    const last = r.paras[2];
    // The badge takes the place of the sentence's own "Experimental:" label.
    expect(words(last)).toBe('The nearest gauge read 579.4 ft, 18.1 km from this address. The reading is for the lake, not for this street.');
    expect(last.some((p) => p.cite === 'lake_michigan_water_level')).toBe(true);
  });

  it('never makes an experimental sentence the key sentence', () => {
    const r = keyedAnswer(answerOf(IDA), { doc_id: 'lake_michigan_water_level', in_lead: false }, isExp)!;
    expect(r.key).toBeNull();
    expect(r.paras.map((p) => !!p[0].exp)).toEqual([false, false, true]);
    expect(words(r.paras[0])).toMatch(/^USGS surveyed/);
    expect(words(r.paras[1])).toMatch(/^82 NYC 311/);
  });

  it('leaves an answer with no lead fact alone', () => {
    expect(keyedAnswer(answerOf(IDA), null, isExp)).toBeNull();
  });
});
