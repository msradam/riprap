/**
 * Sticky map containment on a place briefing (the prerendered
 * /gallery/hollis/ page, no backend needed).
 *
 * At 1100px and wider the map sits in a sticky right column beside the
 * evidence table and report sections. Its sticky containing block is the
 * two-column grid, so it must release before the Sources and method
 * section below the grid. The sticky column is capped at the viewport
 * and scrolls on its own, so the map point list under the map stays
 * reachable from any scroll position.
 */
import { test, expect } from '@playwright/test';

// The backend serves the gallery pages from the committed build (as in journeys.spec.ts).
const STATIC = process.env.RIPRAP_STATIC_URL || process.env.RIPRAP_BASE_URL || 'http://127.0.0.1:7860';
const PAGE = `${STATIC}/gallery/hollis/`;

async function mapReady(page: import('@playwright/test').Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(PAGE);
  // The map loads lazily and starts under the rail, below the fold.
  await page.locator('#brief-map').scrollIntoViewIfNeeded();
  await page.waitForFunction(
    () => Boolean((window as unknown as { __riprapMap?: unknown }).__riprapMap),
    undefined,
    { timeout: 15_000 }
  );
}

test.describe('sticky map containment', () => {
  test('does not overlap Sources and method when scrolled to it', async ({ page }) => {
    await mapReady(page);
    await page.locator('#brief-sources').scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);

    const rects = await page.evaluate(() => ({
      m: document.querySelector('.brief-sticky')?.getBoundingClientRect(),
      t: document.getElementById('brief-sources')?.getBoundingClientRect()
    }));
    expect(rects.m, 'map rect').toBeTruthy();
    expect(rects.t, 'sources rect').toBeTruthy();
    if (!rects.m || !rects.t) return;

    const xOverlap = !(rects.m.right <= rects.t.left || rects.t.right <= rects.m.left);
    const yOverlap = !(rects.m.bottom <= rects.t.top || rects.t.bottom <= rects.m.top);
    expect(xOverlap && yOverlap,
      `map should not overlap Sources and method. Map: ${JSON.stringify(rects.m)}; Sources: ${JSON.stringify(rects.t)}.`
    ).toBe(false);
    expect(rects.m.bottom).toBeLessThanOrEqual(rects.t.top + 1);
  });

  test('map column is sticky under the header, with the point list after the map (DOM order)', async ({ page }) => {
    await mapReady(page);
    const facts = await page.evaluate(() => {
      const rail = document.querySelector('.brief-sticky') as HTMLElement | null;
      if (!rail) return null;
      const cs = getComputedStyle(rail);
      const map = rail.querySelector('.map-frame');
      const list = rail.querySelector('.map-points');
      const order = map && list && (map.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING) ? 'map-first' : 'wrong';
      return { position: cs.position, top: cs.top, overflowY: cs.overflowY, order };
    });
    expect(facts).toBeTruthy();
    if (!facts) return;
    expect(facts.position).toBe('sticky');
    // Below the 52px sticky app header.
    expect(facts.top).toBe('68px');
    expect(facts.overflowY).toBe('auto');
    expect(facts.order).toBe('map-first');
  });

  test('the map point list is reachable from the sticky column (not buried under the map)', async ({ page }) => {
    await mapReady(page);
    await page.evaluate(() => window.scrollTo({ top: 1400, behavior: 'instant' }));
    await page.waitForTimeout(250);

    const inside = await page.evaluate(() => {
      const rail = document.querySelector('.brief-sticky') as HTMLElement | null;
      const list = document.querySelector('.map-points') as HTMLElement | null;
      if (!rail || !list) return null;
      const r = rail.getBoundingClientRect();
      const map = rail.querySelector('.map-frame');
      return {
        inside: rail.contains(list),
        railVisible: r.top < window.innerHeight && r.bottom > 0,
        railFits: r.height <= window.innerHeight,
        mapBeforeList: Boolean(map && map.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING)
      };
    });
    expect(inside, 'rail / list geometry').toBeTruthy();
    if (!inside) return;
    expect(inside.inside, 'point list inside the sticky column').toBe(true);
    expect(inside.railVisible, 'sticky column visible in viewport').toBe(true);
    expect(inside.railFits, 'sticky column capped at the viewport height').toBe(true);
    expect(inside.mapBeforeList, 'map renders before the list in DOM').toBe(true);
  });
});
