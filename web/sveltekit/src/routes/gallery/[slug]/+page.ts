import { error } from '@sveltejs/kit';
import { galleryIndex, loadGalleryEntry } from '$lib/client/gallery';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import { deployment } from '$lib/stores/deployment.svelte';
import type { EntryGenerator, PageLoad } from './$types';

export const prerender = true;

export const entries: EntryGenerator = () => galleryIndex.map((e) => ({ slug: e.slug }));

export const load: PageLoad = async ({ params }) => {
  const entry = await loadGalleryEntry(params.slug);
  if (!entry) error(404, 'No gallery entry with that name');
  // Install the snapshot's manifest and deployment before anything
  // renders, so the header and cards never fetch /api/*.
  // ponytail: module-level stores are shared during prerender; safe while
  // kit.prerender.concurrency stays at its default of 1.
  pebbleManifest.setFromResponse(entry.pebbles, entry.deployment.name);
  deployment.setStatic(entry.deployment);
  return { entry };
};
