#!/usr/bin/env node
// Re-runs the contrast check through Rec.601 grayscale desaturation —
// the same math a black-and-white photocopy, a grayscale print preview,
// or a colorblind reader's grayscale accessibility mode actually
// performs. WCAG 1.4.1: color is never the sole carrier of meaning.
//
// The 4.5:1/3:1 thresholds are fixed (same law as contrast-gate.mjs).
// The role list is a placeholder — same configuration shape as
// contrast-gate.mjs, fill in once the design session's tokens exist.
import { readBlocks, composeGround, resolve } from './lib/tokens.mjs';
import { contrastRatio, toGrayscale } from './lib/color.mjs';

const PREFIX = 'riprap';
const TOKENS_PATH = new URL('../tokens/tokens.css', import.meta.url).pathname;
const GROUNDS = ['light'];
const DEFAULT_GROUND = 'light';

// Roles whose DISTINCTNESS from each other must survive desaturation —
// e.g. if your design uses color to distinguish several status/severity
// states, list each one here paired with the minimum contrast it must
// still hit against its surface once grayscale. This is the check that
// catches "these two colors read identically once printed on a
// black-and-white photocopier."
const ROLES = [
  // Text roles must still clear 4.5:1 once desaturated (Rec.601).
  ['riprap-text-primary',   'riprap-surface-page',   4.5],
  ['riprap-text-secondary', 'riprap-surface-page',   4.5],
  ['riprap-text-tertiary',  'riprap-surface-sunken', 4.5],
  ['riprap-text-link',      'riprap-surface-sunken', 4.5],
  // Evidence-tier + severity marks: each must stay >=3:1 legible in
  // grayscale. NOTE: their distinctness FROM EACH OTHER is carried by
  // SHAPE/PATTERN in the component (solid/hatched/hollow/stippled square;
  // filled-step triangle), which this color math cannot see — this check
  // only confirms each mark's ink survives desaturation, not that two
  // hues stay apart. That is the point of encoding tier by shape.
  ['riprap-tier-empirical', 'riprap-surface-card',   3.0],
  ['riprap-tier-modeled',   'riprap-surface-card',   3.0],
  ['riprap-tier-proxy',     'riprap-surface-card',   3.0],
  ['riprap-tier-synthetic', 'riprap-surface-card',   3.0],
  ['riprap-sev-1',          'riprap-surface-card',   3.0],
  ['riprap-sev-2',          'riprap-surface-card',   3.0],
  ['riprap-sev-4',          'riprap-surface-card',   3.0],
];

function main() {
  if (ROLES.length === 0) {
    console.log('grayscale-gate: no roles configured yet — this is a template.');
    console.log('Fill in ROLES once your token file exists, then re-run.');
    process.exit(0);
  }

  const blocks = readBlocks(TOKENS_PATH, PREFIX);
  const problems = [];
  let checked = 0;

  for (const ground of GROUNDS) {
    const map = composeGround(blocks, ground, DEFAULT_GROUND);
    for (const [tok, surface, min] of ROLES) {
      const fg = toGrayscale(resolve(tok, map, PREFIX));
      const bg = toGrayscale(resolve(surface, map, PREFIX));
      const ratio = contrastRatio(fg, bg);
      const pass = ratio >= min;
      const line = `${pass ? 'PASS' : 'FAIL'}  ${ground}/${tok} on ${surface}, grayscale  ${ratio.toFixed(2)}:1 (need ${min}:1)`;
      if (!pass) problems.push(line);
      checked++;
    }
  }

  if (problems.length) {
    console.error(`grayscale-gate: FAIL (${problems.length}/${checked} checks failed)\n`);
    for (const p of problems) console.error('  ' + p);
    process.exit(1);
  }
  console.log(`grayscale-gate: PASS (${checked} checks)`);
}

main();
