#!/usr/bin/env node
// Runs the deterministic gates in order. The first non-zero exit blocks.
// Behavioral checks (real-browser keyboard/target-size/axe) need
// Playwright and are not part of this zero-dependency chain — run
// behavioral-gate.mjs separately once the design session's components
// are live in a real page.
import { spawnSync } from 'node:child_process';

const GATES = ['contrast-gate.mjs', 'rules-lint.mjs', 'grayscale-gate.mjs', 'drift-gate.mjs'];

for (const gate of GATES) {
  const path = new URL('./' + gate, import.meta.url).pathname;
  const result = spawnSync('node', [path], { stdio: 'inherit' });
  if (result.status !== 0) {
    console.error(`\nverify.mjs: ${gate} failed, stopping.`);
    process.exit(result.status ?? 1);
  }
}

console.log('\nverify.mjs: all deterministic gates PASS (or are unconfigured templates — see individual output above)');
