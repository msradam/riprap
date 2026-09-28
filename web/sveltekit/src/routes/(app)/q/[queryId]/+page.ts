import { error } from '@sveltejs/kit';
import { STATIC_SITE } from '$lib/staticSite';

// Live route: SSE-driven, must NOT be prerendered (the queryId is dynamic
// and the data comes from the FastAPI backend at runtime).
export const prerender = false;
export const ssr = false;

// The public static site has no backend to stream from, so an old /q/
// link shows the error page (gallery and Quickstart links) instead.
export function load() {
  if (STATIC_SITE) error(404, 'Live briefings need the local backend');
}
