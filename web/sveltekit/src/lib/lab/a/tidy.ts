import type { ClaimPart } from '$lib/types/claim';
import type { Card } from '$lib/types/card';

const PUNCT_RE = /^[.,;:]/;

/** Typesetting only, no words change. A cited claim ends in a space and the
 *  next part opens with its punctuation ("NAVD88 " + "."), which puts the
 *  citation mark before the full stop. Move that punctuation onto the first
 *  cited part of the run, so the mark lands after it: "NAVD88.1". */
export function tidy(parts: ClaimPart[]): ClaimPart[] {
  const out = parts.map((p) => ({ ...p }));
  for (let i = 1; i < out.length; i++) {
    const m = PUNCT_RE.exec(out[i].text);
    if (!m || !out[i - 1].cite) continue;
    // Walk back over empty cited parts (several sources on one claim).
    let j = i - 1;
    while (j > 0 && out[j].text === '' && out[j - 1].cite) j--;
    out[j].text = out[j].text.trimEnd() + m[0];
    out[i].text = out[i].text.slice(1);
  }
  return out;
}

/** Drop a leading count that the page sets large above the sentence. */
export function dropLead(parts: ClaimPart[], word: string | null): ClaimPart[] {
  const [first, ...rest] = parts;
  if (!word || !first || !first.text.startsWith(word) || /^[A-Z]/.test(word)) return parts;
  return [{ ...first, text: first.text.slice(word.length).trimStart() }, ...rest];
}

/** Doc ids cited in these paragraphs, in reading order. */
export function citedIn(paras: ClaimPart[][]): string[] {
  return [...new Set(paras.flat().flatMap((p) => (p.cite ? [p.cite] : [])))];
}

const FIGURE_RE = /^\d[\d.,]*(?:\s?(?:%|m²|cm|mm|ft|in|m\b|\/wk))?/;

/** The exhibit table's figure: the first scalar, else a leading number in
 *  the headline, else nothing. */
export function figureOf(c: Card): { value: string; label: string | null } | null {
  const s = c.scalars?.[0];
  if (s) return { value: s.unit ? `${s.value} ${s.unit}` : s.value, label: s.label };
  const m = c.headline ? FIGURE_RE.exec(c.headline) : null;
  return m ? { value: m[0].trim(), label: null } : null;
}

/** The finding sentence(s) for a card, split after the first sentence so
 *  the page can set the first one heavier. */
export function findingOf(c: Card): { first: string; rest: string } | null {
  const t = c.body ?? c.sub ?? c.headline;
  if (!t) return null;
  const m = /(?<=\.)\s+(?=[A-Z0-9])/.exec(t);
  return m ? { first: t.slice(0, m.index), rest: t.slice(m.index + m[0].length) } : { first: t, rest: '' };
}
