/**
 * Build-time summaries of the static gallery for the landing and the
 * gallery index: each entry's index fields plus its standfirst and
 * answer mode, so neither page ships the full snapshots.
 */
import { galleryIndex, loadGalleryEntry, type GalleryIndexEntry } from '$lib/client/gallery';
import type { FinalResult } from '$lib/client/agentStream';
import { parseBriefing } from '$lib/client/parseBriefing';
import { keySentence, leadAnswer } from '$lib/client/briefingModel';
import { tidy } from '$lib/client/briefingText';

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

/** The standfirst: with a lead fact, the lead word and the key sentence
 *  the page sets large, chosen by the page's own keySentence; otherwise
 *  leadSentence. */
export function standfirst(final: Pick<FinalResult, 'paragraph' | 'grounding'>): string {
  const { first, answer } = leadAnswer(parseBriefing(final.paragraph).blocks);
  const keyed = keySentence(answer, final.grounding?.lead_fact);
  if (!keyed) return leadSentence(final.paragraph);
  const key = tidy(keyed.key).map((p) => p.text).join('').replace(/\s+/g, ' ').trim();
  // A count lead keeps its sentence whole, so only a word such as "Yes" is added.
  return first.word && /^[A-Z]/.test(first.word) ? `${first.word}. ${key}` : key;
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
      lead: entry ? standfirst(entry.final) : '',
      answerMode: entry?.final.grounding?.answer_mode ?? null
    });
  }
  return out;
}
