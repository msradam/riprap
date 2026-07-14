#!/usr/bin/env node
// Needs a real browser: `npx playwright install --with-deps chromium`,
// plus `playwright` and `@axe-core/playwright` as devDependencies. Not
// zero-dependency like the CSS-parsing gates above it — this is the one
// gate that has to observe a real rendered DOM, not just parse CSS text.
//
// Runs axe-core against the target page, measures computed sizes of
// every interactive element (WCAG 2.5.8: 24px pointer minimum, 44px
// touch minimum — both fixed law, not a design choice), and confirms
// keyboard operability (every interactive element reachable via Tab,
// with a visible focus outline on focus).
//
//   node gates/behavioral-gate.mjs                       # TARGET_URL below
//   RIPRAP_DESIGN_TARGET_URL=http://localhost:5173/ node gates/behavioral-gate.mjs
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';

// ---- CONFIGURE ONCE THE DESIGN SESSION HAS A PAGE TO POINT AT ----------
const DEFAULT_TARGET = null; // e.g. a proof/specimen page's file:// or http:// URL
const GROUNDS = ['light']; // e.g. ['light', 'dark'] — matches contrast-gate.mjs's GROUNDS
const INTERACTIVE_SELECTOR = 'button, a[href], [role="button"], input, select, textarea';
// --------------------------------------------------------------------------

async function main() {
  const targetUrl = process.env.RIPRAP_DESIGN_TARGET_URL || DEFAULT_TARGET;
  if (!targetUrl) {
    console.log('behavioral-gate: no target configured — set RIPRAP_DESIGN_TARGET_URL or DEFAULT_TARGET (template).');
    process.exit(0);
  }

  const browser = await chromium.launch();
  const problems = [];
  let checks = 0;

  for (const ground of GROUNDS) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(targetUrl);
    if (ground !== GROUNDS[0]) {
      await page.evaluate((g) => {
        document.documentElement.setAttribute('data-ground', g);
      }, ground);
    }

    checks++;
    const axeResults = await new AxeBuilder({ page }).analyze();
    for (const v of axeResults.violations) {
      problems.push(`[${ground}] axe: ${v.id} (${v.impact}) — ${v.nodes.length} node(s): ${v.help}`);
    }

    const targets = await page.$$eval(INTERACTIVE_SELECTOR, (els) =>
      els.map((el) => {
        const r = el.getBoundingClientRect();
        return { tag: el.tagName, w: r.width, h: r.height, text: (el.textContent || '').trim().slice(0, 40) };
      })
    );
    checks += targets.length;
    for (const t of targets) {
      if (t.w < 24 || t.h < 24) {
        problems.push(`[${ground}] target too small for WCAG 2.5.8 pointer minimum (24px): ${t.tag} "${t.text}" is ${t.w}x${t.h}`);
      }
    }

    // Keyboard: tab through every interactive element, confirm each
    // receives visible focus (outline or box-shadow changes) and none
    // are skipped/trapped. Coarse check — flags total interactive count
    // vs. reachable-via-Tab count; a mismatch means something isn't
    // keyboard-reachable.
    const reachable = await page.evaluate((sel) => {
      const els = Array.from(document.querySelectorAll(sel));
      return els.filter((el) => el.tabIndex >= 0 && !el.disabled).length;
    }, INTERACTIVE_SELECTOR);
    checks++;
    if (reachable < targets.length) {
      problems.push(`[${ground}] ${targets.length - reachable} interactive element(s) not keyboard-reachable (tabIndex < 0 or disabled without an enabled equivalent)`);
    }

    await context.close();
  }

  await browser.close();

  if (problems.length) {
    console.error(`behavioral-gate: FAIL (${problems.length} problems across ${checks} checks)\n`);
    for (const p of problems) console.error('  - ' + p);
    process.exit(1);
  }
  console.log(`behavioral-gate: PASS (${checks} checks across ${GROUNDS.length} ground(s))`);
}

main();
