/**
 * Real-usage journeys (Impeccable pass, phase 5). Each journey runs an axe
 * check on every state it passes through.
 *
 * Needs the backend on 127.0.0.1:7860 (no LLM required); it also serves
 * the prerendered gallery pages from the committed build (RIPRAP_STATIC_URL
 * points at another build of them). Question journeys stub the SSE stream
 * with a recorded gallery result, so they need no LLM and run in seconds.
 * RIPRAP_E2E_LLM=1 enables one journey against the live LLM stream.
 */
import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

const STATIC = process.env.RIPRAP_STATIC_URL || process.env.RIPRAP_BASE_URL || 'http://127.0.0.1:7860';
const QUESTION = 'Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?';
const ADDRESS = '90-01 183rd Street, Queens';

function gallery(slug: string) {
  return JSON.parse(fs.readFileSync(path.resolve('src/lib/gallery', `${slug}.json`), 'utf8')).final;
}

/** An SSE body that replays a recorded result: hello, plan, deployment, steps, final, done. */
function sse(final: Record<string, unknown>, opts: { failStep?: string } = {}) {
  const ev = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
  const plan = (final.plan as Record<string, unknown>) || { intent: final.intent };
  let out = ev('hello', { query: final.query }) + ev('plan', plan) + ev('deployment', { name: 'nyc', city: 'New York City', state: 'NY' });
  if (opts.failStep) {
    out += ev('step', { kind: 'step', step: opts.failStep, ok: false, err: 'simulated HTTP 503', elapsed_s: 0.1 });
  }
  return out + ev('final', final) + 'event: done\ndata: {}\n\n';
}

async function stubStream(page: Page, final: Record<string, unknown>, opts: { delayMs?: number; failStep?: string } = {}) {
  await page.route('**/api/agent/stream**', async (route) => {
    if (opts.delayMs) await new Promise((r) => setTimeout(r, opts.delayMs));
    await route.fulfill({ status: 200, headers: { 'content-type': 'text/event-stream' }, body: sse(final, opts) });
  });
}

async function noAxeViolations(page: Page, state: string) {
  // Scan the settled state: a fade-in in progress blends text with the ground.
  await page
    .waitForFunction(() => document.getAnimations().every((a) => a.playState !== 'running' || a.effect?.getTiming().iterations === Infinity), null, { timeout: 5_000 })
    .catch(() => {});
  // @axe-core/playwright types a newer Playwright Page than @playwright/test; the runtime object is the same.
  const res = await new AxeBuilder({ page: page as never }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
  const summary = res.violations.map((v) => `${v.id} (${v.nodes.length}): ${v.nodes[0]?.target.join(' ')}`);
  expect(summary, `axe violations at state: ${state}`).toEqual([]);
}

async function ask(page: Page, text: string, viaKeyboard = false) {
  await page.goto('/');
  await noAxeViolations(page, 'landing');
  const input = page.locator('form[role=search] input');
  if (viaKeyboard) {
    for (let i = 0; i < 25 && !(await input.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press('Tab');
    await expect(input).toBeFocused();
    await page.keyboard.type(text);
    await page.keyboard.press('Enter');
  } else {
    await input.fill(text);
    await input.press('Enter');
  }
}

async function answerThenSource(page: Page, viaKeyboard = false, answerTimeout = 30_000) {
  const answer = page.getByRole('heading', { name: 'Answer' });
  await expect(answer).toBeVisible({ timeout: answerTimeout });
  await expect(page.getByText('Briefing for:')).toBeVisible();
  await noAxeViolations(page, 'answer shown');
  const cite = page.locator('a.inline-cite:visible').first();
  const id = await cite.getAttribute('data-cite');
  if (viaKeyboard) {
    for (let i = 0; i < 80 && !(await cite.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press('Tab');
    await expect(cite).toBeFocused();
    await page.keyboard.press('Enter');
  } else {
    await cite.click();
  }
  const entry = page.locator(`#cite-${id}`);
  await expect(entry).toBeInViewport();
  await expect(entry).toHaveClass(/is-active/);
  const source = entry.locator('a[href^="http"]').first();
  await expect(source).toHaveAttribute('href', /^https?:\/\//);
  if (viaKeyboard) {
    // Enter moves focus to the entry itself; one Tab then reaches its source.
    await expect(entry).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(source).toBeFocused();
  }
  await noAxeViolations(page, 'citation open');
}

test.describe('journeys', () => {
  test('1. question, answer, citation, source link', async ({ page }) => {
    await stubStream(page, gallery('hollis-since-ida'));
    await ask(page, QUESTION);
    await answerThenSource(page);
  });

  test('2. bare address, full briefing, print route', async ({ page }) => {
    // Live no-LLM run: the recorded address snapshot predates the source lists.
    test.setTimeout(240_000);
    await ask(page, ADDRESS);
    await expect(page.getByText('Briefing for:')).toBeVisible({ timeout: 200_000 });
    await expect(page.getByText('Sources consulted')).toBeVisible();
    await noAxeViolations(page, 'briefing');
    await page.goto(`/print/${encodeURIComponent(ADDRESS)}`);
    await expect(page.getByText(/Briefing for:/)).toBeVisible();
    await noAxeViolations(page, 'print');
  });

  test('3. static gallery with the backend stopped', async ({ page }) => {
    await page.route('**/api/**', (route) => route.abort());
    await page.goto(`${STATIC}/gallery/`);
    await noAxeViolations(page, 'gallery index');
    await page.getByRole('link', { name: /183rd Street|Hollis/ }).first().click();
    await expect(page.getByText('Briefing for:')).toBeVisible();
    await noAxeViolations(page, 'gallery entry');
  });

  test('4. out-of-scope question gets the refusal', async ({ page }) => {
    await ask(page, 'Should I buy the house at 2017 East 17th Street, Brooklyn?');
    await expect(page.getByText('Riprap does not answer this question')).toBeVisible({ timeout: 60_000 });
    await noAxeViolations(page, 'refusal');
  });

  test('5. journey 1 with the keyboard only', async ({ page }) => {
    await stubStream(page, gallery('hollis-since-ida'));
    await ask(page, QUESTION, true);
    await answerThenSource(page, true);
  });

  test('6. journey 1 on a phone', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await stubStream(page, gallery('hollis-since-ida'));
    await ask(page, QUESTION);
    await expect(page.getByRole('heading', { name: 'Answer' })).toBeVisible({ timeout: 30_000 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await answerThenSource(page);
  });

  test('7. journey 1 with reduced motion', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await stubStream(page, gallery('hollis-since-ida'));
    await ask(page, QUESTION);
    await answerThenSource(page);
    const running = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length);
    expect(running).toBe(0);
  });

  test('8. slow backend, then a failing source', async ({ page }) => {
    await stubStream(page, gallery('hollis'), { delayMs: 12_000, failStep: 'nyc311' });
    await ask(page, ADDRESS);
    await expect(page.getByText(/\d+\s*s\b/).first()).toBeVisible({ timeout: 11_000 });
    await noAxeViolations(page, 'loading');
    await expect(page.getByText(/failed to respond/).first()).toBeVisible({ timeout: 30_000 });
    await noAxeViolations(page, 'failed source');
  });

  test('10. district question in no-LLM mode resolves the named district', async ({ page }) => {
    // Refactor 5: the no-LLM resolver used to send any question naming a
    // borough to that borough's first neighbourhood (Astoria).
    test.setTimeout(240_000);
    await ask(page, 'How many flood complaints has Queens Community Board 12 had?');
    const place = page.locator('.resolved-place');
    await expect(place).toBeVisible({ timeout: 200_000 });
    await expect(place).toContainText('QN12');
    await expect(place).not.toContainText('Astoria');
    await noAxeViolations(page, 'district briefing');
  });

  // Refactor 6: the map point list in a real browser (the static Hollis page).
  async function openMapList(page: Page) {
    await page.route('**/api/**', (route) => route.abort());
    await page.goto(`${STATIC}/gallery/hollis/`);
    // The map loads lazily and sits beside the evidence, below the fold.
    await page.locator('#brief-map').scrollIntoViewIfNeeded();
    await expect(page.locator('.maplibregl-canvas')).toBeVisible({ timeout: 30_000 });
    const summary = page.locator('summary', { hasText: 'Map points as a list' });
    await summary.click();
    const rows = page.locator('.map-points-list button');
    await expect(rows.first()).toBeVisible();
    await noAxeViolations(page, 'map list open');
    return rows;
  }

  test('11. map list: a row chosen with the mouse selects its point', async ({ page }) => {
    const rows = await openMapList(page);
    const name = (await rows.first().locator('.map-point-name').textContent())!.trim();
    await rows.first().click();
    await expect(rows.first()).toHaveAttribute('aria-pressed', 'true');
    const popup = page.locator('.maplibregl-popup');
    await expect(popup).toBeVisible();
    await expect(popup).toContainText(name);
    await noAxeViolations(page, 'map point selected with the mouse');
    // Closing the popup clears the selection.
    await popup.locator('.maplibregl-popup-close-button').click();
    await expect(popup).toHaveCount(0);
    await expect(rows.first()).toHaveAttribute('aria-pressed', 'false');
  });

  test('12. map list: a row chosen with the keyboard selects its point and keeps focus', async ({ page }) => {
    const rows = await openMapList(page);
    const second = rows.nth(1);
    const name = (await second.locator('.map-point-name').textContent())!.trim();
    await rows.first().focus();
    await page.keyboard.press('Tab');
    await expect(second).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(second).toHaveAttribute('aria-pressed', 'true');
    await expect(rows.first()).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('.maplibregl-popup')).toContainText(name);
    // Focus stays in the list so the reader can move on to the next point.
    await expect(second).toBeFocused();
    await page.keyboard.press('Tab');
    await page.keyboard.press('Space');
    await expect(rows.nth(2)).toHaveAttribute('aria-pressed', 'true');
    await expect(second).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('.maplibregl-popup')).toHaveCount(1);
    await noAxeViolations(page, 'map point selected with the keyboard');
  });

  test('9. optional: live LLM question', async ({ page }) => {
    test.skip(!process.env.RIPRAP_E2E_LLM, 'set RIPRAP_E2E_LLM=1 with an LLM-backed server');
    test.setTimeout(360_000);
    await ask(page, QUESTION);
    await answerThenSource(page, false, 300_000);
  });
});
