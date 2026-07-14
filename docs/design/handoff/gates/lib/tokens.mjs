// Parses a CSS custom-property file into per-block name -> value maps,
// then composes named "grounds" (e.g. light/dark, paper/night — whatever
// the design session calls them) from them. Zero dependencies: a small
// brace-depth scanner, not a full CSS parser — good enough for a token
// file that is itself generated/hand-authored in a predictable shape.
//
// Adapted from a sibling design-system handoff (Hanji, for the Calluna
// project) where this exact parser caught two real bugs before anything
// shipped on top of it:
//   1. A naive "match every --prefix-*: value; in the whole file" regex
//      let a ground-override block (e.g. [data-ground="night"]) silently
//      clobber :root's values in a flat map, since both declare the same
//      custom-property names and the override block comes later in the
//      file.
//   2. A single-pass regex (`/([^{}]+)\{([^{}]*)\}/g`) cannot handle a
//      nested block (`@media print { :root { ... } }`): `[^{}]*` cannot
//      span the inner braces, so the match silently breaks apart. This
//      file strips comments first and walks brace depth explicitly
//      instead of leaning on regex to do it.
//
// Prefix-agnostic on purpose: pass your own custom-property prefix (e.g.
// "riprap" if your tokens are --riprap-text-primary etc.) rather than
// hardcoding one, since the design session — not this file — decides the
// token naming.
import { readFileSync } from 'node:fs';

function declRe(prefix) {
  return new RegExp(`--(${prefix}-[a-z0-9-]+)\\s*:\\s*([^;]+);`, 'g');
}

function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

/** Split top-level CSS into { selector, body, isAtRule } blocks by
 * walking brace depth. At-rule blocks (@media ...) are NOT recursed
 * into here — their raw body is returned as-is; parseBlocks below
 * re-invokes this splitter on an at-rule's body to get its inner
 * blocks, one explicit level of nesting (extend if your file nests
 * deeper than that). */
function splitBlocks(css) {
  const blocks = [];
  let i = 0;
  while (i < css.length) {
    const openIdx = css.indexOf('{', i);
    if (openIdx === -1) break;
    const selector = css.slice(i, openIdx).trim();
    let depth = 1;
    let j = openIdx + 1;
    while (j < css.length && depth > 0) {
      if (css[j] === '{') depth++;
      else if (css[j] === '}') depth--;
      j++;
    }
    const body = css.slice(openIdx + 1, j - 1);
    if (selector) {
      blocks.push({ selector, body, isAtRule: selector.startsWith('@') });
    }
    i = j;
  }
  return blocks;
}

function declsFromBody(body, prefix) {
  const map = new Map();
  const re = declRe(prefix);
  let m;
  while ((m = re.exec(body))) {
    map.set(m[1], m[2].trim());
  }
  return map;
}

/** Parse a CSS file into Map<selector, Map<name, rawValue>>. `@media`
 * blocks are walked one level deeper and keyed as
 * "<media query> > <inner selector>". Comments are stripped first so
 * they never leak into selector text. `prefix` is your custom-property
 * prefix without the leading `--` (e.g. "riprap"). */
export function parseBlocks(cssText, prefix) {
  const clean = stripComments(cssText);
  const blocks = new Map();
  for (const { selector, body, isAtRule } of splitBlocks(clean)) {
    if (isAtRule) {
      for (const inner of splitBlocks(body)) {
        const key = `${selector} > ${inner.selector}`;
        blocks.set(key, declsFromBody(inner.body, prefix));
      }
      continue;
    }
    const existing = blocks.get(selector) ?? new Map();
    for (const [k, v] of declsFromBody(body, prefix)) existing.set(k, v);
    blocks.set(selector, existing);
  }
  return blocks;
}

export function readBlocks(path, prefix) {
  return parseBlocks(readFileSync(path, 'utf8'), prefix);
}

/** Flat name -> rawValue map across the WHOLE file, ignoring block
 * scope. Only correct for a file with no overriding blocks (e.g. a
 * hand-typed reference file that is deliberately :root-only). Do not
 * use this on a file with ground-override blocks; use readBlocks +
 * composeGround instead. */
export function parseDeclarations(cssText, prefix) {
  const flat = new Map();
  for (const [, decls] of parseBlocks(cssText, prefix)) {
    for (const [k, v] of decls) flat.set(k, v);
  }
  return flat;
}

export function readDeclarations(path, prefix) {
  return parseDeclarations(readFileSync(path, 'utf8'), prefix);
}

/** Compose the effective token map for one named ground: :root as the
 * base, with [data-ground="<ground>"]'s declarations layered on top
 * (the default ground has no override block — it IS the :root default).
 * `defaultGround` names whichever ground needs no override block. */
export function composeGround(blocks, ground, defaultGround) {
  const root = blocks.get(':root') ?? new Map();
  const map = new Map(root);
  if (ground !== defaultGround) {
    const override = blocks.get(`[data-ground="${ground}"]`) ?? new Map();
    for (const [k, v] of override) map.set(k, v);
  }
  return map;
}

/** Resolve `var(--prefix-x)` chains to a final literal value (typically
 * a hex color), given a flat name -> rawValue map for one ground. Throws
 * on a cycle or an unresolvable reference — both indicate a real bug in
 * the token file, not something to silently fall back on. */
export function resolve(name, map, prefix, seen = new Set()) {
  if (seen.has(name)) {
    throw new Error(`token cycle: ${[...seen, name].join(' -> ')}`);
  }
  const raw = map.get(name);
  if (raw === undefined) {
    throw new Error(`unknown token: --${name}`);
  }
  const varMatch = raw.match(new RegExp(`^var\\(--(${prefix}-[a-z0-9-]+)\\)$`));
  if (!varMatch) {
    return raw;
  }
  return resolve(varMatch[1], map, prefix, new Set([...seen, name]));
}

export function isHex(value) {
  return /^#[0-9a-fA-F]{3,6}$/.test(value);
}
