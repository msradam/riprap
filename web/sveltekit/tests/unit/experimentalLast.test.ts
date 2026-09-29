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
const isExp = (id: string) => id === 'prithvi_water';

// hollis-since-ida's answer, shortened: Prithvi (experimental) sits between
// the Ida marks and the 311 count.
const IDA =
  'Yes. USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address [ida_hwm]. ' +
  'Experimental: a satellite model found 0 m² of new surface water within 500 m [prithvi_water]. ' +
  'Street and basement flooding drains within hours [prithvi_water]. ' +
  '82 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years [nyc311].';

describe('keyedAnswer', () => {
  it('puts paragraphs from experimental sources last, each opening with the badge', () => {
    const r = keyedAnswer(answerOf(IDA), { doc_id: 'nyc311', in_lead: false }, isExp)!;
    expect(words(r.key!)).toMatch(/^82 NYC 311/);
    expect(r.paras.map((p) => !!p[0].exp)).toEqual([false, false, true]);
    expect(words(r.paras[1])).toMatch(/^USGS surveyed/);
    const last = r.paras[2];
    // The badge takes the place of the sentence's own "Experimental:" label.
    expect(words(last)).toBe('A satellite model found 0 m² of new surface water within 500 m. Street and basement flooding drains within hours.');
    expect(last.some((p) => p.cite === 'prithvi_water')).toBe(true);
  });

  it('never makes an experimental sentence the key sentence', () => {
    const r = keyedAnswer(answerOf(IDA), { doc_id: 'prithvi_water', in_lead: false }, isExp)!;
    expect(r.key).toBeNull();
    expect(r.paras.map((p) => !!p[0].exp)).toEqual([false, false, true]);
    expect(words(r.paras[0])).toMatch(/^USGS surveyed/);
    expect(words(r.paras[1])).toMatch(/^82 NYC 311/);
  });

  it('leaves an answer with no lead fact alone', () => {
    expect(keyedAnswer(answerOf(IDA), null, isExp)).toBeNull();
  });
});
