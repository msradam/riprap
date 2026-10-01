// Retake the landing hero's briefing preview from the served build:
//   node scripts/capture-hero-preview.mjs http://127.0.0.1:7860
// Opens the Hollis "since Ida" gallery briefing at a 1200px desktop
// viewport, takes a full-page screenshot, keeps the top CROP_HEIGHT CSS px
// (the answer, its sources, the map and the start of the evidence) and
// writes static/landing/hero-briefing.webp, plus hero-briefing-720.webp
// scaled down for phones and 1x desktop screens. Rerun it after
// scripts/build_gallery.py changes that entry, then `pnpm build`.
//
// The encoder is the browser's own canvas WebP, so no image tool is needed.
// The hero shows the image about 455px wide, so the 1200px file is the
// 2x one and there is nothing larger.
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const WIDTH = 1200;
// LandSpecimen.svelte sets this height on the <img>: keep the two in step.
const CROP_HEIGHT = 2700;
const QUALITY = 0.8;

const base = process.argv[2] || 'http://127.0.0.1:7860';
const outDir = fileURLToPath(new URL('../static/landing/', import.meta.url));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: WIDTH, height: 900 }, deviceScaleFactor: 1 });
await page.goto(`${base}/gallery/hollis-since-ida/`, { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);
await page.waitForSelector('.maplibregl-canvas');
// The map fades its tiles in after the network goes quiet.
await page.waitForLoadState('networkidle');
await page.waitForTimeout(2000);

const png = await page.screenshot({ fullPage: true, clip: { x: 0, y: 0, width: WIDTH, height: CROP_HEIGHT } });
const widths = [WIDTH, 720];
const dataUrls = await page.evaluate(
  async ({ src, q, widths }) => {
    const img = new Image();
    img.src = src;
    await img.decode();
    return widths.map((w) => {
      const c = document.createElement('canvas');
      c.width = w;
      c.height = Math.round((img.naturalHeight * w) / img.naturalWidth);
      const ctx = c.getContext('2d');
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(img, 0, 0, c.width, c.height);
      return c.toDataURL('image/webp', q);
    });
  },
  { src: `data:image/png;base64,${png.toString('base64')}`, q: QUALITY, widths }
);
await browser.close();

mkdirSync(outDir, { recursive: true });
widths.forEach((w, i) => {
  if (!dataUrls[i].startsWith('data:image/webp')) throw new Error('This browser did not encode WebP');
  const webp = Buffer.from(dataUrls[i].split(',')[1], 'base64');
  const name = w === WIDTH ? 'hero-briefing.webp' : `hero-briefing-${w}.webp`;
  writeFileSync(`${outDir}${name}`, webp);
  console.log(`${name}: ${w}px wide, ${Math.round(webp.length / 1024)} KB`);
});
