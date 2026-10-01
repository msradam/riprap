import { error } from '@sveltejs/kit';
import { galleryIndex, loadGalleryEntry } from '$lib/client/gallery';
import { RunState } from '$lib/client/runState.svelte';
import { briefingModel } from '$lib/client/briefingModel';
import { CHIPS, PROOF, SPECIMEN_SLUG } from '$lib/landing';
import type { Citation } from '$lib/types/claim';

// Read at build time: the landing ships the gallery count, the specimen
// answer and the quoted entries' index fields, not the snapshots.
export async function load() {
  const bySlug = (slug: string) => {
    const s = galleryIndex.find((e) => e.slug === slug);
    if (!s) error(500, `The landing quotes gallery entry "${slug}", which is not in the gallery`);
    return s;
  };

  // The specimen is built the way /gallery/[slug] builds the page, so its
  // key sentence and source notes are the briefing's own.
  const entry = await loadGalleryEntry(SPECIMEN_SLUG);
  if (!entry?.question) error(500, `Gallery entry "${SPECIMEN_SLUG}" is not a question`);
  const model = briefingModel(RunState.fromFinal(entry.final, entry.address), entry.question);
  const cites: Citation[] = model.citations.filter((c) => model.cited.includes(c.id));
  const specimen = {
    slug: SPECIMEN_SLUG,
    question: entry.question,
    lead: model.lead,
    key: model.answer[0] ?? [],
    citations: cites,
    date: entry.generated_at.slice(0, 10)
  };

  const chips = CHIPS.map((c) => {
    const s = bySlug(c.slug);
    return { ...c, query: s.question ?? s.address };
  });
  const proof = PROOF.map((p) => {
    const s = bySlug(p.slug);
    return { ...p, question: s.question ?? null, place: s.neighborhood, date: s.generated_at.slice(0, 10) };
  });

  return { count: galleryIndex.length, specimen, chips, proof };
}
