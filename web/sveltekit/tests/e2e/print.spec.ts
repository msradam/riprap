/**
 * Export-PDF flow:
 *  - the header button is hidden until the briefing is ready
 *  - on /q/sample (prerendered) it appears immediately on mount
 *  - a gallery entry's "Print this briefing" saves a snapshot and opens
 *    /print/<id>
 *  - that route renders the report: title, answer and its source notes,
 *    then the evidence table and the source lists. No app header, no map.
 *  - the route auto-fires window.print()
 */
import { test, expect } from '@playwright/test';

// Gallery pages come from the static build (journeys.spec.ts does the same).
const STATIC = process.env.RIPRAP_STATIC_URL || 'http://127.0.0.1:4179';
const QUERY = '80 Pioneer Street, Brooklyn, NY';
const SNAP_KEY = `riprap:print:${QUERY}`;

test.describe('export-PDF curated print flow', () => {
  test('header export button visible on /q/sample, hidden when no snapshot', async ({ page }) => {
    await page.goto('/q/sample');
    await expect(page.locator('button').filter({ hasText: /export PDF/i })).toBeVisible();
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
        // @ts-expect-error
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
    // A gallery print dates its live readings to the snapshot, as the
    // briefing page does, and prints the folded experimental group open.
    await expect(page.locator('.ev-asof').filter({ hasText: /^\s*live\s*$/ })).toHaveCount(0);
    await expect(page.locator('.ev-asof').filter({ hasText: 'at snapshot' }).first()).toBeVisible();
    await expect(page.locator('.print-doc details.ev-folded')).toHaveJSProperty('open', true);

    // App chrome is excluded (the @-page break breaks out of root layout).
    await expect(page.locator('.app-header')).toHaveCount(0);
    await expect(page.locator('.app-region-map')).toHaveCount(0);
    await expect(page.locator('.trace-ui')).toHaveCount(0);

    // window.print() fired automatically.
    await page.waitForFunction(
      // @ts-expect-error
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
