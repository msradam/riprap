/**
 * Typesetting and table helpers for the briefing page. None of them change
 * a word of the briefing; they move punctuation, pick out figures and
 * choose which card text reads as the finding.
 */
import type { ClaimPart } from '$lib/types/claim';
import type { Card } from '$lib/types/card';
import { formatGeneratedAt } from './gallery';

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

/** A figure and its unit ("200 m", "2.13 in/hr") or a hyphenated number
 *  (a date such as 2021-09-02, a house number such as 90-01). */
const KEEP_RE = /(\d[\d.,]*\s(?:m²|km|mm|cm|ft|in\/hr|m)(?![\w/])|\d+(?:-\d+)+)/;

/** Text split so the odd-indexed pieces can be set on one line: a narrow
 *  column otherwise breaks "200 m" after the number or a date at its
 *  hyphen. Joined back, the pieces are the text unchanged. */
export function keepTogether(text: string): string[] {
  return text.split(KEEP_RE);
}

/** Doc ids cited in these paragraphs, in reading order. */
export function citedIn(paras: ClaimPart[][]): string[] {
  return [...new Set(paras.flat().flatMap((p) => (p.cite ? [p.cite] : [])))];
}

/** A figure and its unit at the start of a headline: a unit symbol ("22
 *  cm", "0.2/wk") or, when the headline is the figure and its noun alone
 *  ("82 complaints", "57 permits"), that noun. */
const FIGURE_RE = /^\d[\d.,]*(?:\s?(?:%|m²|cm|mm|ft|in|m\b|\/wk)|\s[a-z]+(?=$|[.,;:]))?/;

/** A scalar that places or dates the finding ("Distance to station (km)",
 *  "FIRM panel effective year", "Gauges in the area") rather than measuring
 *  it, or a temperature, which is a frozen weather reading on a snapshot,
 *  not flood evidence. */
const NOT_FIGURE_RE = /distance|effective|year|date|temperature|gauges/i;
const TEMPERATURE_RE = /°/;

/** The plural that ends a phrase's leading noun phrase, cut at its first
 *  preposition ("active NYC DOB construction permits inside this area"
 *  gives "permits"). "NYC 311 complaints filed within 200 m" gives
 *  nothing: "filed" is no noun, and a wrong noun is worse than none. */
const NOUN_PHRASE_RE = /^([A-Za-z][\w-]*(?:\s[A-Za-z][\w-]*){0,5})\s(?:inside|within|in|at|of|since|from|per|for|with|on|to|by)\b/;
function countNoun(phrase: string): string | null {
  const noun = NOUN_PHRASE_RE.exec(phrase)?.[1].split(' ').pop();
  return noun && /[a-z]s$/.test(noun) ? noun : null;
}

/** The evidence table's figure: the finding's own quantity, the first
 *  scalar that is not a distance or a year. With scalars but none of
 *  those, nothing. Without scalars, a leading number in the headline
 *  with its unit or noun, else nothing. A bare count ("73") takes its
 *  noun from the rest of the headline or from the dataset's title
 *  ("Active DOB construction permits inside the neighborhood" gives
 *  "73 permits"). */
export function figureOf(c: Pick<Card, 'scalars' | 'headline' | 'title'>): { value: string; label: string | null } | null {
  if (c.scalars?.length) {
    const s = c.scalars.find((x) => !NOT_FIGURE_RE.test(x.label) && !TEMPERATURE_RE.test(`${x.value}${x.unit ?? ''}`));
    return s ? { value: s.unit ? `${s.value} ${s.unit}` : s.value, label: s.label } : null;
  }
  const m = c.headline ? FIGURE_RE.exec(c.headline) : null;
  if (!m || TEMPERATURE_RE.test(c.headline!.charAt(m[0].length))) return null;
  const value = m[0].trim();
  const noun = /^[\d.,]+$/.test(value)
    ? countNoun(c.headline!.slice(m[0].length).trim()) ?? (c.title ? countNoun(c.title) : null)
    : null;
  return { value: noun ? `${value} ${noun}` : value, label: null };
}

/** The space after a full stop that starts a new sentence. */
const SENTENCE_GAP = /(?<=\.)\s+(?=[A-Z0-9])/;

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
  const m = SENTENCE_GAP.exec(t);
  return m ? { first: t.slice(0, m.index), rest: t.slice(m.index + m[0].length) } : { first: t, rest: '' };
}

const EXP_LABEL = /^Experimental(?: forecast)?: /;

/** A finding sentence split after its first clause, at the first ";" or
 *  ":" outside parentheses, so a narrow table can set only that clause
 *  heavier. A short label, or the label of an experimental sentence
 *  ("Experimental:", "Experimental forecast:"), is not a clause; a
 *  sentence with no such break is all lead. */
export function leadClause(s: string): { lead: string; tail: string } {
  const from = Math.max(16, EXP_LABEL.exec(s)?.[0].length ?? 0);
  let depth = 0;
  for (let i = 0; i < s.length - 1; i++) {
    const ch = s[i];
    if (ch === '(') depth++;
    else if (ch === ')') depth = Math.max(0, depth - 1);
    else if (depth === 0 && (ch === ';' || ch === ':') && s[i + 1] === ' ' && i >= from) {
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

const ISO_TIME_RE = /^\d{4}-\d{2}-\d{2}T/;

/** When a source's data is from, in words, the same on the evidence
 *  table, the source lists and the print packet. A dataset with a
 *  modification date reads "data as of 2024-07-03"; one with only a
 *  retrieval date reads "retrieved 2026-07-11"; a live reading reads
 *  "fetched 2026-09-30 16:05 UTC", the time it was fetched. The backend
 *  dates a live reading to its fetch (`vintage` equal to `retrieved_at`)
 *  or calls it "live"; the word "live" is never shown as a date. */
export function asOfPhrase(vintage: string, retrieved?: string | null): { label: string; date: string | null } {
  const v = vintage.trim();
  const at = retrieved && !/^live$/i.test(retrieved) ? retrieved : null;
  if (/^live$/i.test(v)) return at ? { label: 'fetched', date: formatGeneratedAt(at) } : { label: 'live reading', date: null };
  if (ISO_TIME_RE.test(v) && v === at) return { label: 'fetched', date: formatGeneratedAt(v) };
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
    term: 'MLLW',
    re: /\bMLLW\b/,
    reading: "mean lower low water, the average of each day's lower low tide; NOAA tide readings are measured against it."
  },
  {
    term: 'above-curb flood event',
    re: /above-curb/i,
    reading:
      "a flood event logged by a FloodNet street sensor, which measures the depth of water on the street; the count uses FloodNet's own event records."
  }
];

const TIER_TERM = {
  term: 'Measured, Modeled, Proxy',
  reading:
    'how directly a source observes flooding. Measured sources record it; modeled sources simulate a scenario; proxy sources, such as 311 complaints, indicate it indirectly.'
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


/** Hosts a sentence may name in passing ("FEMA's Flood Map Service Center
 *  (msc.fema.gov)"), linked without changing the words. */
const LINK_HOSTS = /\b(msc\.fema\.gov|floodhelpny\.org)\b/g;

/** Text split into plain pieces and linked host names, in order. */
export function linkHosts(text: string): { text: string; href?: string }[] {
  const out: { text: string; href?: string }[] = [];
  let last = 0;
  for (const m of text.matchAll(LINK_HOSTS)) {
    if (m.index! > last) out.push({ text: text.slice(last, m.index) });
    out.push({ text: m[0], href: `https://${m[0]}/` });
    last = m.index! + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}
