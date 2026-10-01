/** The product version shown in the UI (landing footer, app footer, print
 *  packet). It is the Riprap release in the repository's pyproject.toml;
 *  web/sveltekit/package.json has its own unrelated package version.
 *  tests/unit/version.test.ts fails when the two drift. */
export const APP_VERSION = '0.8.0';
