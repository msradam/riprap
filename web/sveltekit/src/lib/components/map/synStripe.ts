/**
 * v0.4.2 §14: the syn-stripe-45 fill pattern for `tier-synthetic-fill`.
 *
 * The SVG source is the canonical 12×12 tile from the spec page;
 * registerSynStripe loads it into MapLibre as a named image so
 * `paint.fill-pattern: 'syn-stripe-45'` resolves at render time.
 */
import type { Map as MapLibreMap } from 'maplibre-gl';

export const SYN_STRIPE_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">
  <rect width="12" height="12" fill="rgba(42,111,168,0.18)"/>
  <g stroke="#2A6FA8" stroke-width="1.4">
    <line x1="-2" y1="2"  x2="14" y2="-14"/>
    <line x1="-2" y1="8"  x2="14" y2="-8"/>
    <line x1="-2" y1="14" x2="14" y2="-2"/>
    <line x1="-2" y1="20" x2="14" y2="4"/>
  </g>
</svg>`;

async function svgToImage(src: string): Promise<HTMLImageElement> {
  const blob = new Blob([src], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  try {
    return await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image(12, 12);
      i.onload = () => resolve(i);
      i.onerror = (err) => reject(err);
      i.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Register syn-stripe-45. Call once after `map.on('style.load', ...)`. */
export async function registerSynStripe(map: MapLibreMap): Promise<void> {
  if (map.hasImage('syn-stripe-45')) return;
  try {
    map.addImage('syn-stripe-45', await svgToImage(SYN_STRIPE_SVG));
  } catch (err) {
    console.warn('syn-stripe registration failed', err);
  }
}
