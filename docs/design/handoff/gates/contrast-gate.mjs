#!/usr/bin/env node
// WCAG 2.x contrast, full cartesian product of every text/mark role
// against every surface it's actually drawn on, in every named ground.
//
// The THRESHOLDS below are fixed — WCAG 1.4.3 / 1.4.11, not a design
// choice. The ROLE LIST (which named tokens to check, and which surface
// each is drawn on) is a placeholder: fill it in once the design
// session's token file exists. This script does not know or assume any
// specific palette, evidence system, or hazard system — that is exactly
// the design work this handoff leaves open.
import { readBlocks, composeGround, resolve } from './lib/tokens.mjs';
import { contrastRatio } from './lib/color.mjs';

// ---- CONFIGURE THESE FOUR THINGS ONCE THE TOKEN FILE EXISTS ----------
const PREFIX = 'riprap'; // your custom-property prefix, e.g. --riprap-text-primary
const TOKENS_PATH = new URL('../tokens/tokens.css', import.meta.url).pathname;
const GROUNDS = ['light']; // e.g. ['light', 'dark'] if you ship a dark ground
const DEFAULT_GROUND = 'light'; // the ground with no [data-ground="..."] override block

// Body text roles: WCAG 1.4.3, 4.5:1 minimum against the surface(s) they
// actually render on. One row per (token, surface) pair you need checked.
const TEXT_ROLES = [
  ['riprap-text-primary',   'riprap-surface-page',   4.5, 'body text on page (WCAG 1.4.3)'],
  ['riprap-text-primary',   'riprap-surface-card',   4.5, 'body text on card'],
  ['riprap-text-primary',   'riprap-surface-sunken', 4.5, 'body text on sunken'],
  ['riprap-text-secondary', 'riprap-surface-page',   4.5, 'secondary text on page'],
  ['riprap-text-secondary', 'riprap-surface-sunken', 4.5, 'secondary text on sunken'],
  ['riprap-text-tertiary',  'riprap-surface-page',   4.5, 'tertiary text on page (replaces the #64748B AA bug)'],
  ['riprap-text-tertiary',  'riprap-surface-sunken', 4.5, 'tertiary text on sunken (the surface the old value failed on)'],
  ['riprap-text-tertiary',  'riprap-surface-card',   4.5, 'tertiary text on card'],
  ['riprap-text-link',      'riprap-surface-page',   4.5, 'citation mark / link on page'],
  ['riprap-text-link',      'riprap-surface-sunken', 4.5, 'citation mark on sunken'],
  ['riprap-text-link',      'riprap-surface-card',   4.5, 'citation mark on card'],
  ['riprap-status-ok',      'riprap-surface-inset',  4.5, 'success/done text on inset meta strip'],
  ['riprap-status-ok',      'riprap-surface-card',   4.5, 'success/done text on card'],
];

// Non-text graphical/UI roles: WCAG 1.4.11, 3:1 minimum against the
// surface(s) they render on. Borders, icons, focus rings, status marks —
// anything conveying information by shape/position rather than as a
// paragraph of text.
const GRAPHICAL_ROLES = [
  ['riprap-tier-empirical', 'riprap-surface-card',   3.0, 'empirical tier mark (WCAG 1.4.11)'],
  ['riprap-tier-empirical', 'riprap-surface-page',   3.0, 'empirical tier mark on page'],
  ['riprap-tier-modeled',   'riprap-surface-card',   3.0, 'modeled tier mark'],
  ['riprap-tier-proxy',     'riprap-surface-card',   3.0, 'proxy tier mark'],
  ['riprap-tier-synthetic', 'riprap-surface-card',   3.0, 'synthetic tier mark'],
  ['riprap-sev-1',          'riprap-surface-card',   3.0, 'severity 1 mark'],
  ['riprap-sev-2',          'riprap-surface-card',   3.0, 'severity 2/3 mark (amber)'],
  ['riprap-sev-4',          'riprap-surface-card',   3.0, 'severity 4 mark (alert red)'],
  ['riprap-sev-4',          'riprap-surface-page',   3.0, 'severity 4 mark on page'],
  ['riprap-focus',          'riprap-surface-page',   3.0, 'focus ring on page'],
  ['riprap-focus',          'riprap-surface-card',   3.0, 'focus ring on card'],
  ['riprap-rule-strong',    'riprap-surface-card',   3.0, 'section rule / table header underline'],
];
// ------------------------------------------------------------------------

function checkRole(blocks, ground, tokenName, surfaceName, minRatio, reason, problems) {
  const map = composeGround(blocks, ground, DEFAULT_GROUND);
  const fg = resolve(tokenName, map, PREFIX);
  const bg = resolve(surfaceName, map, PREFIX);
  const ratio = contrastRatio(fg, bg);
  const pass = ratio >= minRatio;
  const line = `${pass ? 'PASS' : 'FAIL'}  ${ground}/${tokenName} on ${surfaceName}  ${ratio.toFixed(2)}:1 (need ${minRatio}:1)  — ${reason}`;
  if (!pass) problems.push(line);
  return { pass, line };
}

function main() {
  if (TEXT_ROLES.length === 0 && GRAPHICAL_ROLES.length === 0) {
    console.log('contrast-gate: no roles configured yet — this is a template.');
    console.log('Fill in TEXT_ROLES / GRAPHICAL_ROLES once your token file exists, then re-run.');
    process.exit(0);
  }

  const blocks = readBlocks(TOKENS_PATH, PREFIX);
  const problems = [];
  let checked = 0;

  for (const ground of GROUNDS) {
    for (const [tok, surface, min, reason] of TEXT_ROLES) {
      checkRole(blocks, ground, tok, surface, min, reason, problems);
      checked++;
    }
    for (const [tok, surface, min, reason] of GRAPHICAL_ROLES) {
      checkRole(blocks, ground, tok, surface, min, reason, problems);
      checked++;
    }
  }

  if (problems.length) {
    console.error(`contrast-gate: FAIL (${problems.length}/${checked} checks failed)\n`);
    for (const p of problems) console.error('  ' + p);
    process.exit(1);
  }
  console.log(`contrast-gate: PASS (${checked} role/surface/ground checks)`);
}

main();
