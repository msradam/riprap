/**
 * Heat journeys against the live backend (no LLM needed: heat questions are
 * answered by rules). Each runs an axe check on the state it ends in.
 *
 * The figures on the page move with the weather and the records, so the
 * checks are of kind and wording, never of a number.
 */
import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

async function noAxeViolations(page: Page, state: string) {
  await page
    .waitForFunction(() => document.getAnimations().every((a) => a.playState !== 'running' || a.effect?.getTiming().iterations === Infinity), null, { timeout: 5_000 })
    .catch(() => {});
  const res = await new AxeBuilder({ page: page as never }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
  expect(res.violations.map((v) => `${v.id} (${v.nodes.length}): ${v.nodes[0]?.target.join(' ')}`), `axe violations at state: ${state}`).toEqual([]);
}

async function ask(page: Page, text: string) {
  await page.goto('/');
  const input = page.locator('form[role=search] input');
  await input.fill(text);
  await input.press('Enter');
}

test('an address gets a heat briefing with its traps and a way to the flood briefing', async ({ page }) => {
  await ask(page, 'heat 355 Food Center Drive, Bronx');
  await expect(page.locator('.brief-kind')).toContainText('Heat briefing', { timeout: 30_000 });
  const briefing = page.locator('#region-briefing');
  await expect(briefing).toContainText('surface temperature, not air temperature');
  await expect(briefing).toContainText('a rank among neighbourhoods and not a measurement');
  await expect(briefing).not.toContainText('FloodNet');
  await expect(page.getByRole('link', { name: 'Flood briefing for this place' })).toBeVisible();
  await noAxeViolations(page, 'heat address briefing');
});

test('a district gets a heat briefing of heat sources only', async ({ page }) => {
  await ask(page, 'heat QN12');
  await expect(page.locator('.brief-kind')).toContainText('Heat briefing', { timeout: 30_000 });
  const briefing = page.locator('#region-briefing');
  await expect(briefing).toContainText('emergency department visits for heat illness');
  await expect(briefing).not.toContainText('Sandy');
  await noAxeViolations(page, 'heat district briefing');
});

test('a score is refused and the Health Department index is quoted as what it is', async ({ page }) => {
  await ask(page, 'What is the heat score for 2940 Brighton 3rd St, Brooklyn?');
  await expect(page.getByRole('heading', { name: 'Answer' })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#brief-answer')).toContainText('Riprap computes no score or rating of its own');
  await expect(page.locator('#brief-answer')).toContainText('Heat Vulnerability Index');
  await noAxeViolations(page, 'heat score refusal');
});

test('the forecast is the Weather Service’s, and a building is not predicted', async ({ page }) => {
  await ask(page, 'Will my apartment at 80 Pioneer Street, Brooklyn overheat this weekend?');
  await expect(page.getByRole('heading', { name: 'Answer' })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#brief-answer')).toContainText('Riprap cannot predict what will happen in one building');
  await expect(page.locator('#brief-answer')).toContainText('National Weather Service');
  await noAxeViolations(page, 'heat prediction refusal');
});

test('a cold apartment is named as indoor heating, not briefed as heat', async ({ page }) => {
  await ask(page, 'no heat or hot water in my apartment at 80 Pioneer Street, Brooklyn');
  await expect(page.locator('.brief-lead')).toContainText('indoor heating', { timeout: 30_000 });
  await expect(page.locator('#region-briefing')).not.toContainText('Landsat');
  await noAxeViolations(page, 'indoor heating redirect');
});

test('a heat gallery entry reads without a backend', async ({ page }) => {
  await page.goto('/gallery/hunts-point-heat/');
  await expect(page.locator('.brief-kind')).toContainText('Heat briefing');
  await expect(page.locator('#region-briefing')).toContainText('surface temperature, not air temperature');
  await noAxeViolations(page, 'heat gallery entry');
});
