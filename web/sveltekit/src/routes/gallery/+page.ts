import { galleryIndex } from '$lib/client/gallery';

export const prerender = true;

export function load() {
  return { entries: galleryIndex };
}
