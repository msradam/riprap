import { error } from '@sveltejs/kit';
import { galleryIndex, liveQuery, loadGalleryEntry } from '$lib/client/gallery';
import { CHIPS, PROOF, SPECIMEN_SLUG } from '$lib/landing';

// Read at build time: the landing ships the gallery count, the specimen's
// question and the quoted entries' index fields, not the snapshots.
export async function load() {
  const bySlug = (slug: string) => {
    const s = galleryIndex.find((e) => e.slug === slug);
    if (!s) error(500, `The landing quotes gallery entry "${slug}", which is not in the gallery`);
    return s;
  };

  // The hero types the specimen's question, so the entry must have one.
  const entry = await loadGalleryEntry(SPECIMEN_SLUG);
  if (!entry?.question) error(500, `Gallery entry "${SPECIMEN_SLUG}" is not a question`);
  const specimen = { slug: SPECIMEN_SLUG, question: entry.question };

  const chips = CHIPS.map((c) => {
    const s = bySlug(c.slug);
    return { ...c, query: liveQuery(s) };
  });
  const proof = PROOF.map((p) => {
    const s = bySlug(p.slug);
    return { ...p, question: s.question ?? null, place: s.neighborhood, date: s.generated_at.slice(0, 10) };
  });

  return { count: galleryIndex.length, specimen, chips, proof };
}
