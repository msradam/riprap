/**
 * Build-time switch for the public GitHub Pages build, which has no
 * backend. Set PUBLIC_RIPRAP_STATIC=1 when running `pnpm build`; unset or
 * empty is the normal build that the FastAPI server ships.
 *
 * vite.config.ts inlines the value through `define`, so it is a
 * constant in every bundle and still resolves to '' in `pnpm build` and
 * vitest when the variable is not set. `$env/static/public` would fail
 * those builds, because it only exports variables that exist at build time.
 */
export const STATIC_SITE: boolean = import.meta.env.PUBLIC_RIPRAP_STATIC === '1';

/** Where the static site sends readers who want to run their own query. */
export const QUICKSTART_URL = 'https://github.com/msradam/riprap#quickstart';
