import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      // 404.html is the SPA fallback GitHub Pages serves for unknown paths.
      // `pnpm build` copies it to 200.html for the FastAPI server (web/main.py).
      fallback: '404.html',
      precompress: false,
      strict: false
    }),
    paths: {
      // Set BASE_PATH=/repo-name to build for a GitHub Pages project site.
      base: process.env.BASE_PATH ?? ''
    },
    alias: {
      $lib: 'src/lib'
    },
    prerender: {
      handleMissingId: 'ignore',
      handleHttpError: 'warn'
    }
  }
};

export default config;
