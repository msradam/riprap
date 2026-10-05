// The about and accessibility pages build to <name>/index.html, like the
// gallery, so every static host and the FastAPI static mount serve them
// without rewrites.
export const prerender = true;
export const trailingSlash = 'always';
