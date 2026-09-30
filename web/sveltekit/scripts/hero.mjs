// Retake the README hero images from the served build:
//   node scripts/hero.mjs http://127.0.0.1:7860
// Writes ../../assets/screenshots/hero.png (1440x900) and hero-mobile.png (390x844).
import { chromium } from '@playwright/test';

const base = process.argv[2] || 'http://127.0.0.1:7860';
const url = `${base}/gallery/hollis-since-ida/`;
const browser = await chromium.launch();
for (const [name, width, height] of [['hero.png', 1440, 900], ['hero-mobile.png', 390, 844]]) {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `../../assets/screenshots/${name}` });
  await page.close();
}
await browser.close();
