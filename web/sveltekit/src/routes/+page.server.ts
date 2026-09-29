import { galleryStories } from '$lib/server/galleryStories';

// Read at build time: the landing ships each gallery entry's lead, not the snapshots.
export async function load() {
  const stories = (await galleryStories()).map(({ slug, neighborhood, address, question, generated_at, lead, reason }) => ({
    slug,
    neighborhood,
    address,
    question: question ?? null,
    generated_at,
    lead,
    reason: reason ?? null
  }));
  return { stories };
}
