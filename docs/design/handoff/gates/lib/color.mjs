// Zero-dependency color math for the deterministic gates.
// WCAG 2.x relative luminance / contrast ratio, plus Rec.601 luma for the
// grayscale gate. No npm packages — this must run with a bare `node`.

/** '#RRGGBB' or '#RGB' -> [r, g, b] in 0-255. */
export function hexToRgb(hex) {
  const h = hex.trim().replace(/^#/, '');
  const full = h.length === 3
    ? h.split('').map((c) => c + c).join('')
    : h;
  if (!/^[0-9a-fA-F]{6}$/.test(full)) {
    throw new Error(`not a hex color: ${hex}`);
  }
  const n = parseInt(full, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** WCAG 2.x relative luminance from sRGB 0-255 channels. */
export function relativeLuminance([r, g, b]) {
  const chan = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const [rl, gl, bl] = [chan(r), chan(g), chan(b)];
  return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
}

/** WCAG 2.x contrast ratio between two hex colors, >= 1. */
export function contrastRatio(hexA, hexB) {
  const lA = relativeLuminance(hexToRgb(hexA));
  const lB = relativeLuminance(hexToRgb(hexB));
  const [lighter, darker] = lA >= lB ? [lA, lB] : [lB, lA];
  return (lighter + 0.05) / (darker + 0.05);
}

/** Rec.601 luma (perceptual grayscale) for a hex color, 0-255. Distinct
 * from WCAG relative luminance on purpose: Rec.601 is what a real
 * grayscale desaturation (or a black-and-white photocopy) actually
 * produces, which is what the grayscale gate needs to reproduce. */
export function rec601Luma(hex) {
  const [r, g, b] = hexToRgb(hex);
  return 0.299 * r + 0.587 * g + 0.114 * b;
}

/** Desaturate a hex color to its Rec.601 gray equivalent, as a hex string. */
export function toGrayscale(hex) {
  const y = Math.round(rec601Luma(hex));
  const h = y.toString(16).padStart(2, '0');
  return `#${h}${h}${h}`;
}

/** APCA Lc is advisory-only per docs/PRINCIPLES.md — not implemented here
 * since nothing gates on it; WCAG 2.x contrastRatio is the sole pass/fail
 * measure. If APCA is wanted later, add it as a printed-but-non-blocking
 * value, not a second gate. */
