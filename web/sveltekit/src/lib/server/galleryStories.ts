/**
 * Build-time summaries of the static gallery for the landing and the
 * gallery index: each entry's index fields plus its lead sentence and
 * answer mode, so neither page ships the full snapshots.
 */
import { galleryIndex, loadGalleryEntry, type GalleryIndexEntry } from '$lib/client/gallery';

export interface GalleryStory extends GalleryIndexEntry {
  lead: string;
  answerMode: string | null;
}

const SECTION_RE = /\*\*(?:Answer|In brief)\.\*\*\s*([\s\S]*?)(?=\n\s*\n|\*\*[^*]+\.\*\*|$)/;
const LEAD_WORD_RE = /^(Yes|No|Partly|In part|Not clear|Unclear)\.$/;

/** First sentence of the Answer or In brief section, `[doc_id]` markers
 *  removed. A bare "Yes." keeps the sentence after it. */
export function leadSentence(paragraph: string): string {
  const body = SECTION_RE.exec(paragraph)?.[1] ?? '';
  const clean = body.replace(/\s*\[[a-z0-9_]+\]/gi, '').replace(/\s+/g, ' ').trim();
  const sentences = clean.split(/(?<=[.!?])\s+(?=[A-Z0-9"])/);
  return LEAD_WORD_RE.test(sentences[0] ?? '') && sentences[1]
    ? `${sentences[0]} ${sentences[1]}`
    : (sentences[0] ?? '');
}

/** "<model> (<quant>)", the quantization tag dropped from the name when it
 *  repeats it; null for entries made without a language model. */
export function modelName(e: GalleryIndexEntry): string | null {
  if (e.mode !== 'llm' || !e.model) return null;
  const q = e.quantization;
  const model = q && e.model.endsWith(`:${q}`) ? e.model.slice(0, -(q.length + 1)) : e.model;
  return q ? `${model} (${q})` : model;
}

export async function galleryStories(): Promise<GalleryStory[]> {
  const out: GalleryStory[] = [];
  for (const e of galleryIndex) {
    const entry = await loadGalleryEntry(e.slug);
    out.push({
      ...e,
      lead: entry ? leadSentence(entry.final.paragraph) : '',
      answerMode: entry?.final.grounding?.answer_mode ?? null
    });
  }
  return out;
}
