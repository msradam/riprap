/**
 * Static gallery: precomputed briefings written by scripts/build_gallery.py
 * into src/lib/gallery/*.json. Pages built from these make no backend
 * requests; everything they show comes from the JSON.
 */
import type { FinalResult } from './agentStream';
import type { PebbleManifestResponse } from '$lib/stores/pebbleManifest.svelte';
import type { Deployment } from '$lib/stores/deployment.svelte';
import index from '$lib/gallery/index.json';

export interface GalleryIndexEntry {
  slug: string;
  neighborhood: string;
  address: string;
  generated_at: string;
  mode: 'llm' | 'no_llm' | string;
}

export interface GalleryEntry extends GalleryIndexEntry {
  riprap_commit: string;
  model: string | null;
  deployment: Deployment;
  pebbles: PebbleManifestResponse;
  final: FinalResult;
}

export const galleryIndex = index as GalleryIndexEntry[];

const files = import.meta.glob<GalleryEntry>(
  ['/src/lib/gallery/*.json', '!/src/lib/gallery/index.json'],
  { import: 'default' }
);

export async function loadGalleryEntry(slug: string): Promise<GalleryEntry | null> {
  const load = files[`/src/lib/gallery/${slug}.json`];
  return load ? await load() : null;
}

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
