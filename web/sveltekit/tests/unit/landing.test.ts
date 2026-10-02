/**
 * The landing quotes the gallery word for word. When scripts/build_gallery.py
 * reruns and a figure changes, this fails, so the card copy in
 * src/lib/landing.ts is updated from the new snapshot instead of going stale.
 */
import { describe, it, expect } from 'vitest';
import { CHIPS, PROOF, SPECIMEN_SLUG } from '$lib/landing';
import { galleryIndex, liveQuery, loadGalleryEntry } from '$lib/client/gallery';
import { load } from '../../src/routes/+page.server';

/** A briefing paragraph as a reader sees it: `[doc_id]` markers removed. */
async function plainBriefing(slug: string): Promise<string> {
  const entry = await loadGalleryEntry(slug);
  if (!entry) throw new Error(`no gallery entry ${slug}`);
  return entry.final.paragraph
    .replace(/\s*\[[a-z][a-z0-9_]*(?:\s*,\s*[a-z][a-z0-9_]*)*\]/gi, '')
    .replace(/\s+/g, ' ');
}

describe('landing proof cards', () => {
  for (const p of PROOF) {
    it(`${p.slug}: every quote and the figure's source text are in the snapshot verbatim`, async () => {
      const text = await plainBriefing(p.slug);
      for (const q of p.quotes) expect(text, `quote missing from ${p.slug}`).toContain(q);
      if (!p.figure) return;
      expect(text, `figure source missing from ${p.slug}`).toContain(p.figure.from);
      const numbers = p.figure.text.match(/\d+(?:\.\d+)?/g);
      if (numbers) {
        for (const n of numbers) expect(p.figure.from).toMatch(new RegExp(`(^|\\D)${n}(\\D|$)`));
      } else {
        expect(p.figure.from.startsWith(p.figure.text)).toBe(true);
      }
    });
  }

  it('has heat cards, quoted from heat snapshots', () => {
    const heat = PROOF.filter((p) => galleryIndex.find((e) => e.slug === p.slug)?.hazard === 'heat');
    expect(heat.map((p) => p.slug)).toEqual(['hunts-point-heat', 'hollis-heat-week']);
    // The surface figure says it is the surface, in the label and in its source sentence.
    expect(heat[0].figure!.label).toMatch(/surface/);
    expect(heat[0].figure!.from).toContain('surface temperature, not air temperature');
  });

  it('the "No." figure and its quote read together in the snapshot', async () => {
    const hunts = PROOF.find((p) => p.slug === 'hunts-point-311')!;
    expect(await plainBriefing(hunts.slug)).toContain(`${hunts.figure!.text} ${hunts.quotes[0]}`);
  });
});

describe('liveQuery', () => {
  it('is the question, else the place, with "heat" before the place of a bare heat entry', () => {
    expect(liveQuery({ question: 'Is it hot?', address: 'QN12', hazard: 'heat' })).toBe('Is it hot?');
    expect(liveQuery({ address: 'QN12', hazard: 'heat' })).toBe('heat QN12');
    expect(liveQuery({ address: 'QN12', hazard: 'flood' })).toBe('QN12');
    expect(liveQuery({ question: null, address: '80 Pioneer Street, Brooklyn, NY' })).toBe('80 Pioneer Street, Brooklyn, NY');
  });
  it('keeps the heat and flood entries of one place apart', () => {
    const at = (slug: string) => liveQuery(galleryIndex.find((e) => e.slug === slug)!);
    expect(at('qn12-heat')).not.toBe(at('qn12'));
  });
});

describe('landing chips', () => {
  it('has at most six, two of them heat', () => {
    expect(CHIPS.length).toBeLessThanOrEqual(6);
    const heat = CHIPS.filter((c) => galleryIndex.find((e) => e.slug === c.slug)?.hazard === 'heat');
    expect(heat.map((c) => c.slug)).toEqual(['hollis-heat-week', 'qn12-heat']);
  });

  it('every chip opens a gallery entry that exists', () => {
    const slugs = new Set(galleryIndex.map((e) => e.slug));
    for (const c of CHIPS) expect(slugs, c.slug).toContain(c.slug);
  });
});

describe('landing load', () => {
  it("sends each chip's live query as the entry's own question or address", async () => {
    const data = await load();
    const hollis = data.chips.find((c) => c.slug === 'hollis-since-ida')!;
    expect(hollis.query).toBe('Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?');
    expect(data.chips.find((c) => c.slug === 'qn12')!.query).toBe('QN12');
    // A bare heat entry runs as "heat <place>", as scripts/build_gallery.py runs it.
    expect(data.chips.find((c) => c.slug === 'qn12-heat')!.query).toBe('heat QN12');
    expect(data.chips.find((c) => c.slug === 'hollis-heat-week')!.query).toBe(
      'Will it be dangerously hot this week at 90-01 183rd Street, Queens?'
    );
    expect(data.count).toBe(galleryIndex.length);
  });

  it("sets the specimen from the snapshot: the entry's own question, whose briefing answers Yes as the image alt says", async () => {
    const { specimen } = await load();
    const entry = await loadGalleryEntry(SPECIMEN_SLUG);
    expect(specimen.slug).toBe(SPECIMEN_SLUG);
    expect(specimen.question).toBe(entry!.question);
    expect(specimen.question).toBe('Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?');
    // The briefing's answer opens with the lead word, then its key sentence.
    expect(await plainBriefing(SPECIMEN_SLUG)).toMatch(/\*\*Answer\.\*\* Yes\. \d+ FloodNet community sensors? /);
  });
});
