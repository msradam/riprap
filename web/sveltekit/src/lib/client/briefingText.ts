/**
 * Typesetting and table helpers for the briefing page. None of them change
 * a word of the briefing; they move punctuation, pick out figures and
 * choose which card text reads as the finding.
 */
import type { ClaimPart } from '$lib/types/claim';
import type { Card } from '$lib/types/card';

const PUNCT_RE = /^[.,;:]/;

/** A cited claim ends in a space and the next part opens with its
 *  punctuation ("NAVD88 " + "."), which puts the citation mark before the
 *  full stop. Move that punctuation onto the first cited part of the run,
 *  so the mark lands after it: "NAVD88.1". */
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

/** Doc ids cited in these paragraphs, in reading order. */
export function citedIn(paras: ClaimPart[][]): string[] {
  return [...new Set(paras.flat().flatMap((p) => (p.cite ? [p.cite] : [])))];
}

const FIGURE_RE = /^\d[\d.,]*(?:\s?(?:%|m²|cm|mm|ft|in|m\b|\/wk))?/;

/** A scalar that places or dates the finding ("Distance to station (km)",
 *  "FIRM panel effective year") rather than measuring it, or a temperature,
 *  which is a frozen weather reading on a snapshot, not flood evidence. */
const NOT_FIGURE_RE = /distance|effective|year|date|temperature/i;
const TEMPERATURE_RE = /°/;

/** The evidence table's figure: the finding's own quantity, the first
 *  scalar that is not a distance or a year. With scalars but none of
 *  those, nothing. Without scalars, a leading number in the headline
 *  ("82 calls" gives "82"), else nothing. */
export function figureOf(c: Pick<Card, 'scalars' | 'headline'>): { value: string; label: string | null } | null {
  if (c.scalars?.length) {
    const s = c.scalars.find((x) => !NOT_FIGURE_RE.test(x.label) && !TEMPERATURE_RE.test(`${x.value}${x.unit ?? ''}`));
    return s ? { value: s.unit ? `${s.value} ${s.unit}` : s.value, label: s.label } : null;
  }
  const m = c.headline ? FIGURE_RE.exec(c.headline) : null;
  return m && !TEMPERATURE_RE.test(c.headline!.charAt(m[0].length)) ? { value: m[0].trim(), label: null } : null;
}

/** The forecasts, whatever their maturity (district pages add `_nta`). */
export const FORECASTS = ['ttm_battery_surge', 'ttm_311_forecast', 'floodnet_forecast'];

/** Gallery pages: a forecast or an NWS alert was read when the snapshot
 *  was made (`at`, "2026-09-29 12:34 UTC"), so its row says when. */
export function snapshotNote(docId: string, at: string | null | undefined): string | null {
  if (!at) return null;
  const id = docId.replace(/_nta$/, '');
  if (FORECASTS.includes(id)) return `Forecast made at the snapshot, ${at}.`;
  if (id === 'nws_alerts') return `Active at the snapshot, ${at}.`;
  return null;
}

/** The finding sentence(s) for a card, split after the first sentence so
 *  the table can set the first one heavier. The body or sub line (the
 *  templated result) comes first. A headline is used only when it says
 *  something of its own: a headline equal to the source's generic
 *  narration (`narration`, e.g. "The 2012 Hurricane Sandy inundation
 *  extent at this address.") names the dataset, not the result. */
export function findingOf(c: Card, narration?: string | null): { first: string; rest: string } | null {
  const headline = c.headline && c.headline !== narration ? c.headline : undefined;
  const t = c.body ?? c.sub ?? headline;
  if (!t) return null;
  const m = /(?<=\.)\s+(?=[A-Z0-9])/.exec(t);
  return m ? { first: t.slice(0, m.index), rest: t.slice(m.index + m[0].length) } : { first: t, rest: '' };
}

/** A finding sentence split after its first clause, at the first ";" or
 *  ":" outside parentheses, so a narrow table can set only that clause
 *  heavier. A label that short ("Experimental:") is not a clause; a
 *  sentence with no such break is all lead. */
export function leadClause(s: string): { lead: string; tail: string } {
  let depth = 0;
  for (let i = 0; i < s.length - 1; i++) {
    const ch = s[i];
    if (ch === '(') depth++;
    else if (ch === ')') depth = Math.max(0, depth - 1);
    else if (depth === 0 && (ch === ';' || ch === ':') && s[i + 1] === ' ' && i >= 16) {
      return { lead: s.slice(0, i + 1), tail: s.slice(i + 1) };
    }
  }
  return { lead: s, tail: '' };
}

/** ISO timestamps show their date; "retrieved 2026-07-11" shows the
 *  date; other vintages ("live", "2024-Q3") stay as they are. */
export function asOfDate(v: string): string {
  const d = v.replace(/^retrieved\s+/i, '');
  return /^\d{4}-\d{2}-\d{2}T/.test(d) ? d.slice(0, 10) : d;
}

/** The vintage as a phrase for a source note: "data as of 2026-05",
 *  "retrieved 2026-07-11" or "live data". */
export function asOfPhrase(v: string): { label: string; date: string | null } {
  if (/^live$/i.test(v.trim())) return { label: 'live data', date: null };
  return { label: /^retrieved\s/i.test(v) ? 'retrieved' : 'data as of', date: asOfDate(v) };
}

/** Plain readings for terms a reader may not know. Shown only when the
 *  term appears in the rendered briefing. */
export const GLOSSARY: { term: string; re: RegExp; reading: string }[] = [
  {
    term: 'NAVD88',
    re: /NAVD88/,
    reading:
      'an elevation above a fixed survey reference (the North American Vertical Datum of 1988), not a water depth.'
  },
  { term: 'SLR', re: /\bSLR\b/, reading: 'sea-level rise.' },
  {
    term: 'above-curb flood event',
    re: /above-curb/i,
    reading:
      "a flood event logged by a FloodNet street sensor, which measures the depth of water on the street; the count uses FloodNet's own event records."
  }
];

export const TIER_TERM = {
  term: 'Measured, Modeled, Proxy, Synthetic',
  reading:
    'how directly a source observes flooding. Measured sources record it; modeled sources simulate a scenario; proxy sources, such as 311 complaints, indicate it indirectly; synthetic layers are generated, not observed.'
};

/** The glossary entries whose term appears in `text`, plus the tier words
 *  when the evidence table is on the page. */
export function termsIn(text: string, withTiers: boolean): { term: string; reading: string }[] {
  const found = GLOSSARY.filter((g) => g.re.test(text)).map(({ term, reading }) => ({ term, reading }));
  return withTiers ? [...found, TIER_TERM] : found;
}

const SUBJECT_RE = /^This (?:address|area) (?:sits|is) /;

/** The evidence table drops the repeated subject: "This address sits in
 *  FEMA flood zone X" reads "In FEMA flood zone X". Other sentences are
 *  unchanged. */
export function withoutSubject(s: string): string {
  const m = SUBJECT_RE.exec(s);
  if (!m) return s;
  const r = s.slice(m[0].length);
  return r.charAt(0).toUpperCase() + r.slice(1);
}

const STEM_RE = /^(.*) \(([^()]*)\)\.?$/;

/** Sentences that differ only in a closing parenthetical ("... scenario
 *  (2.13 in/hr, 2050 SLR).") as the shared stem and each parenthetical. */
export function sharedStem(sentences: string[]): { stem: string; tails: string[] } | null {
  if (sentences.length < 2) return null;
  const ms = sentences.map((s) => STEM_RE.exec(s));
  if (ms.some((m) => !m || m[1] !== ms[0]![1])) return null;
  return { stem: ms[0]![1], tails: ms.map((m) => m![2]) };
}
