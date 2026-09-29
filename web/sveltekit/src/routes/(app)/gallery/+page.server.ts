import { galleryStories, modelName } from '$lib/server/galleryStories';

export const prerender = true;

// Read once at build time: the page gets each entry's lead, answer mode and
// model name, not the whole snapshot.
export async function load() {
  const entries = (await galleryStories()).map((e) => ({ ...e, modelName: modelName(e) }));
  return { entries };
}
