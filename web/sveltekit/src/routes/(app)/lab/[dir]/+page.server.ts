import { error } from '@sveltejs/kit';
import { galleryIndex, loadGalleryEntry } from '$lib/client/gallery';
import { DIRECTIONS, kindOf, type Direction, type Story } from '$lib/lab/labModel';
import type { EntryGenerator, PageServerLoad } from './$types';

export const prerender = true;

export const entries: EntryGenerator = () => DIRECTIONS.map((dir) => ({ dir }));

const SECTION_RE = /\*\*(?:Answer|In brief)\.\*\*\s*([\s\S]*?)(?=\n\s*\n|\*\*[^*]+\.\*\*|$)/;
const LEAD_WORD_RE = /^(Yes|No|Partly|Not clear|Unclear)\.$/;

/** First sentence of the Answer or In brief section, `[doc_id]` markers
 *  removed. A bare "Yes." keeps the sentence after it. */
function lead(paragraph: string): string {
  const body = SECTION_RE.exec(paragraph)?.[1] ?? '';
  const clean = body.replace(/\s*\[[a-z0-9_]+\]/gi, '').replace(/\s+/g, ' ').trim();
  const sentences = clean.split(/(?<=[.!?])\s+(?=[A-Z0-9"])/);
  return LEAD_WORD_RE.test(sentences[0] ?? '') && sentences[1]
    ? `${sentences[0]} ${sentences[1]}`
    : (sentences[0] ?? '');
}

export const load: PageServerLoad = async ({ params }) => {
  if (!(DIRECTIONS as readonly string[]).includes(params.dir)) error(404, 'No such design direction');
  const stories: Story[] = [];
  for (const e of galleryIndex) {
    const entry = await loadGalleryEntry(e.slug);
    if (!entry) continue;
    stories.push({
      slug: e.slug,
      neighborhood: e.neighborhood,
      address: e.address,
      question: e.question ?? null,
      mode: e.mode,
      generated_at: e.generated_at,
      kind: kindOf(entry),
      lead: lead(entry.final.paragraph)
    });
  }
  return { dir: params.dir as Direction, stories };
};
