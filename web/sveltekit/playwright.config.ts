import { defineConfig, devices } from '@playwright/test';

/**
 * Headless E2E for the Riprap UI. Targets a *running* uvicorn on
 * 127.0.0.1:7860 (RIPRAP_BASE_URL overrides it); the live route depends
 * on the FastAPI backend (planner, SSE, layer endpoints), and the same
 * server serves the prerendered gallery pages from the committed build,
 * so the gallery specs need no second server (RIPRAP_STATIC_URL points
 * them at another build).
 *
 * Run with `pnpm test:e2e` (uvicorn must already be up). The matrix
 * `pnpm check:all` fails loudly if uvicorn is not on the port, by design.
 */
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: process.env.RIPRAP_BASE_URL || 'http://127.0.0.1:7860',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    headless: true
  },
  projects: [
    // PW_CHANNEL=chrome runs on the installed Chrome when Playwright's own browser build is not cached.
    { name: 'chromium', use: { ...devices['Desktop Chrome'], channel: process.env.PW_CHANNEL || undefined } }
  ]
});
