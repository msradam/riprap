import { error } from '@sveltejs/kit';
import { galleryIndex, loadGalleryEntry } from '$lib/client/gallery';
import { DIRECTIONS, type Direction } from '$lib/lab/labModel';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import { deployment } from '$lib/stores/deployment.svelte';
import type { EntryGenerator, PageLoad } from './$types';

export const prerender = true;

export const entries: EntryGenerator = () =>
  DIRECTIONS.flatMap((dir) => galleryIndex.map((e) => ({ dir, slug: e.slug })));

export const load: PageLoad = async ({ params }) => {
  if (!(DIRECTIONS as readonly string[]).includes(params.dir)) error(404, 'No such design direction');
  const entry = await loadGalleryEntry(params.slug);
  if (!entry) error(404, 'No gallery entry with that name');
  // Same as /gallery/[slug]: install the snapshot's manifest and
  // deployment before anything renders, so nothing fetches /api/*.
  pebbleManifest.setFromResponse(entry.pebbles, entry.deployment.name);
  deployment.setStatic(entry.deployment);
  return { entry, dir: params.dir as Direction };
};
