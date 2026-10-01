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
import type { PrintSnapshot } from '$lib/stores/briefingState.svelte';

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
    // No gallery entry has an experimental source, so the snapshot gets
    // one as the gallery page saves it: the closed group evidenceGroups
    // (briefingModel) builds for such a source, holding a copy of the
    // first evidence row.
    await page.addInitScript(() => {
      const setItem = Storage.prototype.setItem;
      Storage.prototype.setItem = function (this: Storage, key: string, value: string) {
        if (key.startsWith('riprap:print:')) {
          const snap = JSON.parse(value) as PrintSnapshot;
          const groups = snap.evidence?.groups;
          if (groups?.length && !groups.some((g) => g.closed)) {
            groups.push({ key: 'experimental', name: 'Experimental sources (1)', role: null,
              cards: [{ ...groups[0].cards[0], experimental: true }], closed: true });
            value = JSON.stringify(snap);
          }
        }
        setItem.call(this, key, value);
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
    // briefing page does.
    await expect(page.locator('.ev-asof').filter({ hasText: /\blive\b/ })).toHaveCount(0);
    await expect(page.locator('.ev-asof').filter({ hasText: /fetched \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC/ }).first()).toBeVisible();
    // The folded experimental group is there and prints open: a closed
    // one would print as its summary only.
    const folded = page.locator('.print-doc details.ev-folded');
    await expect(folded).toHaveCount(1);
    await expect(folded.locator('summary')).toHaveText('Experimental sources (1)');
    await expect(folded).toHaveJSProperty('open', true);
    await expect(folded.locator('tr.ev-row')).toBeVisible();

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
