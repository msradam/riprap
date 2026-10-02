/**
 * Static gallery: precomputed briefings written by scripts/build_gallery.py
 * into src/lib/gallery/*.json. Pages built from these make no backend
 * requests; everything they show comes from the JSON.
 */
import { citationList, planned, refusedIntent, type FinalResult } from './agentStream';
import type { PebbleManifestResponse } from '$lib/stores/pebbleManifest.svelte';
import type { Deployment } from '$lib/stores/deployment.svelte';
import index from '$lib/gallery/index.json';

export interface GalleryIndexEntry {
  slug: string;
  neighborhood: string;
  address: string;
  generated_at: string;
  mode: 'llm' | 'no_llm' | string;
  question?: string | null;
  model?: string | null;
  quantization?: string | null;
  /** One editorial line on why the entry is in the gallery. */
  reason?: string | null;
  /** A doc id whose first sentence in the briefing is the entry's snippet. */
  feature_doc?: string | null;
  /** 'heat' for a heat briefing; 'flood' or missing for a flood one. */
  hazard?: string | null;
}

export interface GalleryEntry extends GalleryIndexEntry {
  riprap_commit: string;
  deployment: Deployment;
  pebbles: PebbleManifestResponse;
  final: FinalResult;
}

export const galleryIndex = index as GalleryIndexEntry[];

/** What a reader types to run the entry's briefing live: its question,
 *  or its place, with "heat" before the place of a bare heat entry (as
 *  scripts/build_gallery.py runs it). The bare place alone starts the
 *  flood briefing. */
export const liveQuery = (e: Pick<GalleryIndexEntry, 'question' | 'address' | 'hazard'>): string =>
  e.question ?? (e.hazard === 'heat' ? `heat ${e.address}` : e.address);

/** An entry with `mode`, `model` and `answerMode` read from its own
 *  `final.grounding`, so every label says how that entry was made. The
 *  index fields stand for an entry saved without a grounding. `planned`
 *  says whether a language model planned the query (`final.plan`), and
 *  `refused` whether the plan refused it. `answerLead` is the grounding's
 *  lead, and `quotesExperimental` says the answer quotes an experimental
 *  model: its lead is one only such an answer takes, or a claim in its
 *  answer cites a source whose citation is experimental. */
export function withGrounding<T extends GalleryIndexEntry>(
  e: T, g: FinalResult['grounding'], plan?: FinalResult['plan'], citations?: FinalResult['citations']
): T & { answerMode: string | null; answerLead: string | null; quotesExperimental: boolean; planned: boolean; refused: boolean } {
  const exp = new Set(citationList(citations).filter((c) => c.maturity === 'experimental').map((c) => c.doc_id));
  return {
    ...e, mode: g?.tier ?? e.mode, model: g ? g.model ?? null : e.model, answerMode: g?.answer_mode ?? null,
    answerLead: g?.answer_lead ?? null,
    quotesExperimental: g?.answer_lead === 'experimental' || g?.answer_lead === 'no_prediction' ||
      !!g?.claims?.some((c) => c.section === 'answer' && c.doc_ids.some((id) => exp.has(id))),
    planned: planned(plan), refused: refusedIntent(plan?.intent)
  };
}

const files = import.meta.glob<GalleryEntry>(
  ['/src/lib/gallery/*.json', '!/src/lib/gallery/index.json'],
  { import: 'default' }
);

export async function loadGalleryEntry(slug: string): Promise<GalleryEntry | null> {
  const load = files[`/src/lib/gallery/${slug}.json`];
  return load ? await load() : null;
}

/** The present instant as an ISO timestamp, the form a snapshot's
 *  generatedAt takes. */
export const isoNow = () => new Date().toISOString();

/** "2026-09-26T19:33Z" → "2026-09-26 19:33 UTC". */
export function formatGeneratedAt(s: string): string {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(s);
  return m ? `${m[1]} ${m[2]} UTC` : s;
}

export function modeLabel(mode: string, model?: string | null): string {
  if (mode === 'llm') return model ? `LLM: ${model}` : 'LLM';
  if (mode === 'no_llm') return 'Evidence briefing (no LLM)';
  return mode;
}

/** "Generated with <model> (<quant>) on <date>" for LLM entries, else null.
 *  The quantization tag is dropped from the model name when it repeats it. */
export function llmStamp(e: GalleryIndexEntry): string | null {
  if (e.mode !== 'llm' || !e.model) return null;
  const q = e.quantization;
  const model = q && e.model.endsWith(`:${q}`) ? e.model.slice(0, -(q.length + 1)) : e.model;
  return `Generated with ${model}${q ? ` (${q})` : ''} on ${e.generated_at.slice(0, 10)}`;
}
