#!/usr/bin/env node
// Parses the design session's built component CSS and checks structural
// rules against it. Unlike contrast-gate/grayscale-gate (fixed WCAG
// math), most of what this file checks is CONFIGURABLE: the design
// session decides its own motion budget, radius policy, and elevation
// policy, and states them here as an explicit, machine-checked decision
// — the point is that whatever the session decides gets enforced
// automatically from then on, not that this file dictates the decision.
//
// Two checks ARE fixed, because they're accessibility requirements, not
// aesthetic choices:
//   - every interactive class must declare :focus-visible (WCAG 2.4.7)
//   - no raw hex color literal outside the token file (drift prevention
//     — see drift-gate.mjs; this just catches the CSS-authoring half of
//     the same problem, a hardcoded color slipping into the component
//     layer instead of a var() reference)
import { readFileSync } from 'node:fs';

const CSS_PATH = new URL('../css/components.css', import.meta.url).pathname;

// ---- CONFIGURE ONCE THE DESIGN SESSION HAS DECIDED THESE ---------------
// Set to null to skip a check entirely (e.g. if the session hasn't
// decided a motion budget yet). Fill in once decided; the gate then
// enforces it on every future change.
const MOTION_BUDGET_MS = 150; // one budget: no transition/animation may exceed 150ms (Calm Tech principle 7)
const RADIUS_POLICY = { surfaces: '2px', controls: '2px' }; // near-square; documents the decision (not auto-enforced by this gate)
const ALLOW_ELEVATION = false; // flat civic register — hierarchy from rules/weight/type, never shadow
// --------------------------------------------------------------------------

function main() {
  let css;
  try {
    css = readFileSync(CSS_PATH, 'utf8');
  } catch {
    console.log('rules-lint: no built CSS yet at', CSS_PATH, '— nothing to check.');
    process.exit(0);
  }

  const problems = [];

  // Fixed: focus-visible presence. Find every class selector that looks
  // interactive (button, a, input, [role="button"], etc. — adjust the
  // pattern to your actual class naming once it exists) and confirm a
  // matching :focus-visible rule exists somewhere in the file.
  const classSelectors = [...css.matchAll(/\.([a-zA-Z][\w-]*)\s*\{/g)].map((m) => m[1]);
  const interactiveGuess = classSelectors.filter((c) => /btn|button|link|input|field|toggle|tab|control/i.test(c));
  for (const cls of new Set(interactiveGuess)) {
    const hasFocusVisible = css.includes(`.${cls}:focus-visible`) || css.includes(`.${cls}:focus-within`);
    if (!hasFocusVisible) {
      problems.push(`missing :focus-visible rule for interactive class .${cls}`);
    }
  }

  // Fixed-ish: no raw hex in the component layer — everything should
  // come from var(--your-prefix-...). Adjust the exclusion if a hex
  // literal is genuinely needed somewhere (rare; document why inline).
  const hexInComponents = [...css.matchAll(/:\s*#[0-9a-fA-F]{3,8}\b/g)];
  if (hexInComponents.length) {
    problems.push(`${hexInComponents.length} raw hex color literal(s) in the component layer — use var() token references instead`);
  }

  // Configurable: motion budget.
  if (MOTION_BUDGET_MS !== null) {
    const durations = [...css.matchAll(/(?:transition|animation)[^;]*?(\d+)ms/g)].map((m) => Number(m[1]));
    for (const d of durations) {
      if (d > MOTION_BUDGET_MS) {
        problems.push(`transition/animation duration ${d}ms exceeds the configured budget of ${MOTION_BUDGET_MS}ms`);
      }
    }
  }

  // Configurable: elevation.
  if (ALLOW_ELEVATION === false) {
    if (/box-shadow\s*:\s*(?!none)/.test(css) || /filter\s*:\s*blur/.test(css)) {
      problems.push('box-shadow or blur present, but ALLOW_ELEVATION is set to false');
    }
  }

  if (RADIUS_POLICY === null && MOTION_BUDGET_MS === null && ALLOW_ELEVATION === null) {
    console.log('rules-lint: radius/motion/elevation policy not yet configured — skipping those checks (template).');
  }

  if (problems.length) {
    console.error(`rules-lint: FAIL (${problems.length} problems)\n`);
    for (const p of problems) console.error('  - ' + p);
    process.exit(1);
  }
  console.log('rules-lint: PASS');
}

main();
