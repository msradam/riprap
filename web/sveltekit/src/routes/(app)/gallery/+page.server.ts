import { galleryIndex, loadGalleryEntry } from '$lib/client/gallery';

export const prerender = true;

// Server load so the entry JSON is read once at build time; the page only
// gets each question entry's answer mode, not the whole snapshot.
export async function load() {
  const answerModes: Record<string, string | null> = {};
  for (const e of galleryIndex.filter((e) => e.question)) {
    const entry = await loadGalleryEntry(e.slug);
    answerModes[e.slug] = entry?.final.grounding?.answer_mode ?? null;
  }
  return { entries: galleryIndex, answerModes };
}
