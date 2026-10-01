/**
 * Build-time summaries of the static gallery for the landing and the
 * gallery index: each entry's index fields plus its standfirst and
 * answer mode, so neither page ships the full snapshots.
 */
import { galleryIndex, loadGalleryEntry, withGrounding, type GalleryIndexEntry } from '$lib/client/gallery';
import { citationList, type FinalResult } from '$lib/client/agentStream';
import { parseBriefing } from '$lib/client/parseBriefing';
import { keyedAnswer, leadAnswer } from '$lib/client/briefingModel';
import { tidy } from '$lib/client/briefingText';

export interface GalleryStory extends GalleryIndexEntry {
  lead: string;
  answerMode: string | null;
  answerLead: string | null;
  /** The answer quotes an experimental model. */
  quotesExperimental: boolean;
  /** A language model planned the query, whatever answered it. */
  planned: boolean;
  /** The query was refused: the entry is a statement, not an answer. */
  refused: boolean;
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

const MARKER_RE = /\s*\[[a-z][a-z0-9_]*(?:\s*,\s*[a-z][a-z0-9_]*)*\]/gi;

/** The first sentence of the briefing text that cites `docId`, `[doc_id]`
 *  markers removed; empty when no sentence cites it. */
export function featureSentence(paragraph: string, docId: string): string {
  const cites = new RegExp(`\\[[^\\]]*\\b${docId.replace(/[^a-z0-9_]/gi, '')}\\b[^\\]]*\\]`, 'i');
  for (const para of paragraph.replace(/\*\*[^*]+\.\*\*/g, '\n').split('\n')) {
    const hit = para.trim().split(/(?<=[.!?])\s+(?=[A-Z0-9"])/).find((s) => cites.test(s));
    if (hit) return hit.replace(MARKER_RE, '').replace(/\s+/g, ' ').trim();
  }
  return '';
}

/** The standfirst: with a lead fact, the lead word and the key sentence
 *  the page sets large, chosen by the page's own keyedAnswer; otherwise
 *  leadSentence. */
export function standfirst(final: Pick<FinalResult, 'paragraph' | 'grounding' | 'citations'>): string {
  const { first, answer } = leadAnswer(parseBriefing(final.paragraph).blocks);
  const exp = new Set(citationList(final.citations).filter((c) => c.maturity === 'experimental').map((c) => c.doc_id));
  const keyed = keyedAnswer(answer, final.grounding?.lead_fact, (id) => exp.has(id))?.key;
  if (!keyed) return leadSentence(final.paragraph);
  const key = tidy(keyed).map((p) => p.text).join('').replace(/\s+/g, ' ').trim();
  // A count lead keeps its sentence whole, so only a word such as "Yes" is added.
  return first.word && /^[A-Z]/.test(first.word) ? `${first.word}. ${key}` : key;
}

/** An entry's snippet: the sentence citing its `feature_doc` when it has
 *  one and the briefing cites it, else the standfirst. */
export function storyLead(e: Pick<GalleryIndexEntry, 'feature_doc'>, final: Pick<FinalResult, 'paragraph' | 'grounding' | 'citations'>): string {
  return (e.feature_doc && featureSentence(final.paragraph, e.feature_doc)) || standfirst(final);
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
    out.push({ ...withGrounding(e, entry?.final.grounding, entry?.final.plan, entry?.final.citations), lead: entry ? storyLead(e, entry.final) : '' });
  }
  return out;
}
