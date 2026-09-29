/**
 * Direction B: pick the evidence cards that carry a clear number and set
 * them as figure bands. A scalars card with two or more cells is a band of
 * its own; single figures (a number that opens the card headline, or a
 * one-cell scalars card) are grouped three to a band. Everything else goes
 * to the "More from the sources" list.
 */
import type { Card } from '$lib/types/card';

export type Figure = { cardId: string; value: string; unit?: string; label: string; source: string; vintage: string };
export type Band = { key: string; title: string | null; figures: Figure[] };

const NUM_RE = /^(\d[\d,]*(?:\.\d+)?%?)\s*(.*)$/;
// A bare year is a date, not a magnitude, so it never becomes a big figure.
const YEAR_RE = /^(1[89]|20)\d\d$/;

/** "2026-09-28T01:37:58+0000" to "2026-09-28"; "live" and "2024-07" as is. */
export const shortDate = (v: string) => (/^\d{4}-\d\d-\d\dT/.test(v) ? v.slice(0, 10) : v);

/** One number from a card, or null when the card has none worth setting large. */
function single(c: Card): Figure | null {
  const base = { cardId: c.id, source: c.source, vintage: c.vintage };
  if (c.scalars?.length === 1) {
    const s = c.scalars[0];
    return YEAR_RE.test(s.value) ? null : { ...base, value: s.value, unit: s.unit, label: s.label };
  }
  const m = c.headline ? NUM_RE.exec(c.headline) : null;
  if (!m || YEAR_RE.test(m[1])) return null;
  // A short remainder ("calls", "cm") reads as a unit; a long one repeats the title.
  const short = m[2] && m[2].split(/\s+/).length <= 2;
  return { ...base, value: m[1], unit: short ? m[2] : undefined, label: c.title };
}

export function figureBands(cards: Card[], cited: Set<string>, max = 2) {
  // Cards the answer cites come first; experimental and synthetic readings
  // stay in the list, where they carry their label.
  const pool = cards
    .filter((c) => !c.experimental && c.tier !== 'synthetic')
    .sort((a, b) => Number(cited.has(b.citeId ?? '')) - Number(cited.has(a.citeId ?? '')));
  const bands: Band[] = [];
  let open: Band | null = null;
  for (const c of pool) {
    if ((c.scalars?.length ?? 0) >= 2) {
      bands.push({
        key: c.id,
        title: c.title,
        figures: c.scalars!.slice(0, 3).map((s) => ({ ...s, cardId: c.id, source: c.source, vintage: c.vintage }))
      });
      continue;
    }
    const f = single(c);
    if (!f) continue;
    if (!open || open.figures.length === 3) {
      open = { key: c.id, title: null, figures: [] };
      bands.push(open);
    }
    open.figures.push(f);
  }
  const kept = bands.slice(0, max);
  const shown = new Set(kept.flatMap((b) => b.figures.map((f) => f.cardId)));
  return { bands: kept, rest: cards.filter((c) => !shown.has(c.id)) };
}
