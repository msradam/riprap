// Retake the landing hero's briefing preview from the served build:
//   node scripts/capture-hero-preview.mjs http://127.0.0.1:7860
// Opens the Hollis "since Ida" gallery briefing at a 1200px desktop
// viewport and crops the answer column (CLIP: the question, the answer and
// the map, without the side rail or the wide evidence table), so its
// sentences stay legible at the hero's size. Writes the crop at 2x as
// static/landing/hero-briefing.webp and at 1x as hero-briefing-712.webp.
// Rerun it after scripts/build_gallery.py changes that entry, or the
// briefing layout moves the column, then `pnpm build`.
//
// The encoder is the browser's own canvas WebP, so no image tool is needed.
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const WIDTH = 1200;
// The answer column with 16px either side, from below the app bar.
// LandSpecimen.svelte sets the 1x size on the <img>: keep the two in step.
const CLIP = { x: 80, y: 52, width: 712, height: 1400 };
const QUALITY = 0.8;

const base = process.argv[2] || 'http://127.0.0.1:7860';
const outDir = fileURLToPath(new URL('../static/landing/', import.meta.url));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: WIDTH, height: 900 }, deviceScaleFactor: 2 });
await page.goto(`${base}/gallery/hollis-since-ida/`, { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);
await page.waitForSelector('.maplibregl-canvas');
// The map fades its tiles in after the network goes quiet.
await page.waitForLoadState('networkidle');
await page.waitForTimeout(2000);

const png = await page.screenshot({ fullPage: true, clip: CLIP });
const widths = [CLIP.width * 2, CLIP.width];
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
  const name = w === CLIP.width ? `hero-briefing-${w}.webp` : 'hero-briefing.webp';
  writeFileSync(`${outDir}${name}`, webp);
  console.log(`${name}: ${w}px wide, ${Math.round(webp.length / 1024)} KB`);
});
