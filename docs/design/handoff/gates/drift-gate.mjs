#!/usr/bin/env node
// Compares the built token CSS against a hand-typed reference file,
// name by name. The point: nothing in the docs should ever assert a
// value that the shipped CSS doesn't actually have. If you change a
// token, this fails until you update BOTH the built file and the
// reference — it's supposed to be mildly annoying, that's what keeps
// docs and shipped code from drifting apart silently.
//
// Optional until the design session has a token file to check — exits 0
// with a note if either file is missing.
import { existsSync, readFileSync } from 'node:fs';
import { readDeclarations } from './lib/tokens.mjs';

const PREFIX = 'riprap';
const BUILT_PATH = new URL('../tokens/tokens.css', import.meta.url).pathname;
const REFERENCE_PATH = new URL('../tokens/reference.css', import.meta.url).pathname;

function main() {
  if (!existsSync(BUILT_PATH) || !existsSync(REFERENCE_PATH)) {
    console.log('drift-gate: tokens.css and/or reference.css not present yet — nothing to compare (template).');
    process.exit(0);
  }

  const built = readDeclarations(BUILT_PATH, PREFIX);
  const reference = readDeclarations(REFERENCE_PATH, PREFIX);

  const problems = [];
  for (const [name, refValue] of reference) {
    const builtValue = built.get(name);
    if (builtValue === undefined) {
      problems.push(`reference.css declares --${name} but tokens.css does not`);
    } else if (builtValue !== refValue) {
      problems.push(`--${name}: reference says "${refValue}", built CSS says "${builtValue}"`);
    }
  }
  for (const name of built.keys()) {
    if (!reference.has(name)) {
      problems.push(`tokens.css declares --${name} but reference.css does not (reference.css is out of date)`);
    }
  }

  if (problems.length) {
    console.error(`drift-gate: FAIL (${problems.length} mismatches)\n`);
    for (const p of problems) console.error('  - ' + p);
    process.exit(1);
  }
  console.log(`drift-gate: PASS (${reference.size} reference tokens agree)`);
}

main();
