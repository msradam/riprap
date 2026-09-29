/**
 * Static worked example: the prerendered gallery briefing /gallery/hollis/.
 *
 * It renders every briefing piece without an SSE connection or a working
 * LLM backend, so it is the cheapest probe for design-system regressions.
 * (It replaces the old /q/sample demo route, which no longer exists.)
 */
import { test, expect } from '@playwright/test';

const PAGE = '/gallery/hollis/';

test.describe('/gallery/hollis/ (prerendered worked example)', () => {
  test('renders the briefing: place title, report sections, cite anchors', async ({ page }) => {
    await page.goto(PAGE);

    await expect(page.locator('.riprap-wordmark')).toContainText('riprap');
    await expect(page.locator('h1.brief-title')).toContainText('183');

    // Four report sections in one closed disclosure after the evidence
    // table, each headed with its Stone name and role, unnumbered.
    const heads = page.locator('.brief-written .brief-section h3');
    await expect(heads).toHaveCount(4);
    await expect(heads.nth(0)).toHaveText('Cornerstone, the hazard reader');

    // Tier marks moved out of the prose into the evidence table.
    expect(await page.locator('.ev-mark svg').count()).toBeGreaterThan(5);
    expect(await page.locator('.brief-answer-p svg, .brief-body svg').count()).toBe(0);

    // Inline citations link to source entries.
    const cites = page.locator('a.inline-cite');
    expect(await cites.count()).toBeGreaterThan(5);
  });

  test('renders the full source list with every cited source', async ({ page }) => {
    await page.goto(PAGE);
    const items = page.locator('.source-list .source-entry');
    expect(await items.count()).toBeGreaterThanOrEqual(10);
    // Each entry carries the source name, the tier in words and the doc id.
    await expect(items.first().locator('.source-entry-name')).not.toBeEmpty();
    await expect(items.first().locator('.source-entry-line')).toContainText(/Measured|Modeled|Proxy|Synthetic/);
  });

  test('records how the briefing was made, closed, with the trace per Stone', async ({ page }) => {
    await page.goto(PAGE);
    const how = page.locator('details#how-made');
    await expect(how).not.toHaveAttribute('open', '');
    await page.getByRole('link', { name: 'How this briefing was made' }).click();
    await expect(how).toHaveAttribute('open', '');
    await expect(how).toContainText('registered source functions');
    await how.locator('details.how-made-stone').first().locator('summary').click();
    expect(await how.locator('.prov-row').count()).toBeGreaterThan(0);
  });

  test('renders the evidence table grouped with the cited rows first', async ({ page }) => {
    await page.goto(PAGE);
    expect(await page.locator('.ev-row').count()).toBeGreaterThan(8);
    await expect(page.locator('.ev-group th').first()).toHaveText('Behind the summary');
    for (const t of ['Measured', 'Modeled', 'Proxy']) {
      expect(await page.locator('.ev-tier', { hasText: t }).count()).toBeGreaterThan(0);
    }
    // A dataset name is never set as the finding (the Sandy misreading).
    await expect(page.locator('.ev-find').first()).toContainText(/outside/i);
  });

  test('map layer switches hide layers with zero features and use words', async ({ page }) => {
    await page.goto(PAGE);
    // The map loads when it nears the viewport; bring it into view first.
    await page.locator('#brief-map').scrollIntoViewIfNeeded();
    await expect(page.locator('.maplibregl-canvas')).toBeVisible({ timeout: 15_000 });
    // The gallery fetches no live layers; only the evidence points in the
    // snapshot (Ida marks and FloodNet sensors, 311 complaints) get a switch.
    await expect(page.locator('.map-layers label')).toHaveCount(2);
    await expect(page.locator('.map-layers label').first()).toContainText('Measured (empirical), 4');
    await expect(page.getByText(/\b(EMP|MOD|PRX|SYN) ON\b/)).toHaveCount(0);
  });

  test('MapLibre map mounts and registers syn-stripe-45 pattern', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    await page.goto(PAGE);

    // The map loads when it nears the viewport; bring it into view first.
    await page.locator('#brief-map').scrollIntoViewIfNeeded();
    await expect(page.locator('.maplibregl-canvas')).toBeVisible({ timeout: 15_000 });
    await page.waitForFunction(
      () => Boolean((window as unknown as { __riprapMap?: unknown }).__riprapMap),
      undefined,
      { timeout: 15_000 }
    );
    await page.waitForFunction(
      () => {
        const m = (window as unknown as { __riprapMap?: { hasImage: (s: string) => boolean } }).__riprapMap;
        return Boolean(m && m.hasImage('syn-stripe-45'));
      },
      undefined,
      { timeout: 5_000 }
    );

    const mapState = await page.evaluate(() => {
      type MlMap = {
        hasImage: (id: string) => boolean;
        getStyle: () => { sources: Record<string, unknown>; layers: Array<{ id: string }> };
      };
      const map = (window as unknown as { __riprapMap?: MlMap }).__riprapMap;
      if (!map) return null;
      const style = map.getStyle();
      return {
        hasStripe: map.hasImage('syn-stripe-45'),
        hasStripe2x: map.hasImage('syn-stripe-45-2x'),
        hasStripeLow: map.hasImage('syn-stripe-45-low'),
        sources: Object.keys(style.sources),
        layers: style.layers.map((l) => l.id)
      };
    });
    expect(mapState, 'map instance should be reachable from the DOM').not.toBeNull();
    if (!mapState) return;

    expect(mapState.sources).toEqual(expect.arrayContaining(['syn-prior', 'register-points', 'queried-address']));
    expect(mapState.layers).toEqual(expect.arrayContaining([
      'tier-synthetic-fill', 'tier-synthetic-line', 'register-points-circle', 'queried-pin'
    ]));
    // The register points behind the map point list are on the map.
    const points = await page.evaluate(() => {
      type Src = { _data?: { features?: unknown[] } } | undefined;
      const map = (window as unknown as { __riprapMap?: { getSource: (id: string) => Src } }).__riprapMap;
      return map?.getSource('register-points')?._data?.features?.length ?? 0;
    });
    expect(points).toBeGreaterThan(0);

    expect(mapState.hasStripe, 'syn-stripe-45 image should be registered').toBe(true);
    expect(mapState.hasStripe2x, 'syn-stripe-45-2x image should be registered').toBe(true);
    expect(mapState.hasStripeLow, 'syn-stripe-45-low image should be registered').toBe(true);

    expect(consoleErrors.filter((e) => !e.includes('favicon'))).toEqual([]);
  });
});
