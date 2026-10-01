/**
 * Print flow:
 *  - the header print link is hidden until a live briefing is ready, then shown
 *  - a gallery entry's "Print this briefing" saves a snapshot and opens
 *    /print/<id>
 *  - that route renders the report: title, answer and its source notes,
 *    then the evidence table and the source lists. No app header, no map.
 *  - the route auto-fires window.print()
 */
import { test, expect } from '@playwright/test';

// The backend serves the gallery pages from the committed build; point
// RIPRAP_STATIC_URL elsewhere to test another build of them.
const STATIC = process.env.RIPRAP_STATIC_URL || process.env.RIPRAP_BASE_URL || 'http://127.0.0.1:7860';
const QUERY = '80 Pioneer Street, Brooklyn, NY';
const SNAP_KEY = `riprap:print:${QUERY}`;

test.describe('curated print flow', () => {
  test('header print link appears once a live briefing is ready', async ({ page }) => {
    await page.goto(`/q/${encodeURIComponent(QUERY)}`);
    const link = page.locator('.app-header a.app-header-link').filter({ hasText: /^print$/ });
    await expect(link).toHaveCount(0);
    await expect(link).toBeVisible({ timeout: 200_000 });
  });

  test('print route hydrates from localStorage and shows curated layout', async ({ page }) => {
    // A gallery snapshot, not a live query: this tests printing, not
    // geocoding. The static pages need no backend.
    await page.route('**/api/**', (route) => route.abort());
    // Stub window.print so the page mounts without the OS dialog popping.
    await page.addInitScript(() => {
      // @ts-expect-error — instrument print for test
      window.__printed = 0;
      window.print = () => {
        // @ts-expect-error: __printed is a global only this test defines
        window.__printed += 1;
      };
    });
    // networkidle: the button works once the page has hydrated.
    await page.goto(`${STATIC}/gallery/red-hook/`, { waitUntil: 'networkidle' });
    await expect(page.locator('#brief-answer')).toBeVisible();
    await page.getByRole('button', { name: 'Print this briefing' }).click();
    await expect(page).toHaveURL(/\/print\//);

    // Confirm a snapshot landed for the entry's query.
    const snapKey = await page.evaluate((k) => (localStorage.getItem(k) ? k : null), SNAP_KEY);
    expect(snapKey).toBe(SNAP_KEY);

    // The curated artifact renders.
    await expect(page.locator('.print-doc')).toBeVisible();
    // The title is the query as typed; the meta line names the place it
    // resolved to.
    await expect(page.locator('.print-title')).toHaveText(QUERY);
    await expect(page.locator('.print-meta')).toContainText(/Pioneer/i);
    await expect(page.locator('.print-answer')).toBeVisible();
    await expect(page.locator('.print-citations h3')).toHaveText('Sources cited');
    // A gallery print dates its live readings to their fetch, as the
    // briefing page does, and prints any folded experimental group open
    // (New York City has no experimental source, so there may be none).
    await expect(page.locator('.ev-asof').filter({ hasText: /\blive\b/ })).toHaveCount(0);
    await expect(page.locator('.ev-asof').filter({ hasText: /fetched \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC/ }).first()).toBeVisible();
    await expect(page.locator('.print-doc details.ev-folded:not([open])')).toHaveCount(0);

    // App chrome is excluded (the @-page break breaks out of root layout).
    await expect(page.locator('.app-header')).toHaveCount(0);
    await expect(page.locator('.app-region-map')).toHaveCount(0);
    await expect(page.locator('.trace-ui')).toHaveCount(0);

    // window.print() fired automatically.
    await page.waitForFunction(
      // @ts-expect-error: __printed is a global only this test defines
      () => window.__printed > 0,
      undefined,
      { timeout: 4000 }
    );
  });

  test('print route shows empty-state when no snapshot exists', async ({ page }) => {
    await page.addInitScript(() => localStorage.clear());
    await page.goto('/print/no-such-query');
    await expect(page.locator('.empty')).toBeVisible();
    await expect(page.locator('.empty')).toContainText(/has not run in this browser/i);
  });
});
