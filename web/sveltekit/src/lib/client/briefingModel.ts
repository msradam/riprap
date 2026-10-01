/**
 * The view model behind a briefing page. Built from a RunState, so the
 * live route (streaming) and the gallery (a replayed `final`) render the
 * same way. Gallery pages add their snapshot meta; live runs have none.
 */
import { looksLikeQuestion, type RunState } from '$lib/client/runState.svelte';
import { splitBriefing } from '$lib/client/parseBriefing';
import { modeLine, POLYGON_INTENTS } from '$lib/client/cardAdapter';
import { formatGeneratedAt } from '$lib/client/gallery';
import { citedIn, findingOf, termsIn } from '$lib/client/briefingText';
import { sourceLists, type PrintSnapshot } from '$lib/stores/briefingState.svelte';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import { deployment } from '$lib/stores/deployment.svelte';
import { STONE_META, STONE_ORDER, type Card, type ModelLine, type StoneTrace } from '$lib/types/card';
import type { BriefingBlock, Citation, ClaimPart } from '$lib/types/claim';

export type Kind = 'question' | 'address' | 'district';
export type Section = { label: string; paras: ClaimPart[][] };
export type SnapshotMeta = { generatedAt: string; commit: string; stamp: string | null };
/** An evidence table row: a card, or several cards merged into one row
 *  (`parts`, the DEP stormwater scenarios), one finding per part. */
export type EvidenceRow = Card & { parts?: Card[] };
/** `closed` groups (experimental sources) start folded. */
export type EvidenceGroup = { key: string; name: string; role: string | null; cards: EvidenceRow[]; closed?: boolean };
/** The card fields the evidence table prints. */
export type EvidenceCard = Pick<Card, 'id' | 'source' | 'experimental' | 'title' | 'tier' | 'vintage' | 'citeId' | 'docId' | 'scalars' | 'headline' | 'variant'> & { parts?: EvidenceCard[] };

const LEAD_RE = /^(Yes|No|Partly|In part|Not clear|Unclear)\.\s*/;
const COUNT_RE = /^([\d,]+(?:\.\d+)?%?)\s+/;
const DISTRICT_RE = /^[A-Z]{2}\s?\d{1,2}$/i;

function sections(blocks: BriefingBlock[]): Section[] {
  const out: Section[] = [];
  for (const b of blocks) {
    if (b.kind === 'head') out.push({ label: b.label, paras: [] });
    else if (b.kind === 'prose') {
      if (!out.length) out.push({ label: '', paras: [] });
      out[out.length - 1].paras.push(b.parts);
    }
  }
  return out.filter((s) => s.paras.length);
}

const text = (parts: ClaimPart[]) => parts.map((p) => p.text).join('');
const sentence = (s: string | null) => (s && !s.endsWith('.') ? `${s}.` : s);

/** A report section head named after a Stone's role ("Hazard Reader")
 *  takes the Stone's name with it ("Cornerstone, the hazard reader"), as
 *  the evidence table's group rows do. Other heads stay as written. */
export function stoneHead(label: string): string {
  const l = label.replace(/\.$/, '').trim().toLowerCase();
  const m = Object.values(STONE_META).find((s) => s.role.replace(/^the /, '') === l);
  return m ? `${m.name}, ${m.role}` : label;
}

/** The first sentence of a paragraph marked bold, split inside the part
 *  where it ends. Used for the "In brief" paragraph. */
export function boldFirstSentence(parts: ClaimPart[]): ClaimPart[] {
  const out: ClaimPart[] = [];
  let done = false;
  for (const p of parts) {
    if (done) { out.push(p); continue; }
    const m = /[.!?](?=\s|$)/.exec(p.text);
    if (!m) { out.push({ ...p, bold: true }); continue; }
    const end = m.index + 1;
    const rest = p.text.slice(end);
    // The cite stays with the words it covers: on the head unless words
    // of this part follow it.
    const tail = !!rest.trim();
    out.push({ ...p, text: p.text.slice(0, end), bold: true, cite: tail ? undefined : p.cite });
    if (rest) out.push({ ...p, text: rest, cite: tail ? p.cite : undefined });
    done = true;
  }
  return out;
}

/** "Yes." comes off the first answer part and is set large on its own. A
 *  count is set large too, but its sentence stays whole below it. */
export function splitLead(parts: ClaimPart[]): { word: string | null; parts: ClaimPart[] } {
  const [first, ...rest] = parts;
  if (!first) return { word: null, parts };
  const yes = LEAD_RE.exec(first.text);
  if (yes) return { word: yes[1], parts: [{ ...first, text: first.text.slice(yes[0].length) }, ...rest] };
  return { word: COUNT_RE.exec(first.text)?.[1] ?? null, parts };
}

/** A count lead taken from a key sentence: the number it opens with
 *  ("From the sources consulted: 34 NYC 311 ..." gives "34"). A sentence
 *  that opens with words gives none: "NPCC4 (2024) projects 0.38 m" once
 *  led with a 4. The sentence stays whole below the lead. */
export function countLead(key: ClaimPart[]): string | null {
  return COUNT_RE.exec(text(key).replace(FACTS_PHRASE, '').trimStart())?.[1] ?? null;
}

/** Where the backend's own lead sentence ends and the quoted facts begin. */
const FACTS_PHRASE = 'From the sources consulted:';

/** A sentence ends at closing punctuation followed by a space and a
 *  capital, a digit or a bracket. parseBriefing splits only before a
 *  capital, so "[floodnet]. 82 complaints" arrives as one part. */
const BOUNDARY = /(?<=[.!?]["”')]?)\s+(?=[A-Z0-9(])/;
const ENDS = /[.!?]["”')]?\s*$/;

/** A paragraph's sentences. A part's citation stays with the words it
 *  follows: the last sentence the part's text reaches. */
export function sentencesOf(parts: ClaimPart[]): ClaimPart[][] {
  const out: ClaimPart[][] = [[]];
  parts.forEach((p, i) => {
    if (!p.cite && !p.text.trim() && i > 0 && ENDS.test(parts[i - 1].text)) {
      out.push([]);
      return;
    }
    const segs = p.text.split(new RegExp(BOUNDARY, 'g'));
    segs.forEach((text, j) => {
      if (j) out.push([]);
      out[out.length - 1].push(j === segs.length - 1 ? { ...p, text } : { text, ...(p.bold && { bold: true }) });
    });
  });
  return out.filter((s) => s.some((p) => p.text.trim() || p.cite));
}

const joinSentences = (ss: ClaimPart[][]) => ss.flatMap((s, i) => (i ? [{ text: ' ' }, ...s] : s));

/** A paragraph broken into one paragraph per cited source, in reading
 *  order: consecutive sentences citing the same sources stay together,
 *  and an uncited sentence stays with the sentence before it. */
export function bySource(parts: ClaimPart[]): ClaimPart[][] {
  const groups: { key: string; ss: ClaimPart[][] }[] = [];
  for (const s of sentencesOf(parts)) {
    const key = citedIn([s]).join(' ');
    const last = groups.at(-1);
    if (last && (!key || !last.key || key === last.key)) {
      last.ss.push(s);
      last.key ||= key;
    } else groups.push({ key, ss: [s] });
  }
  return groups.map((g) => joinSentences(g.ss));
}

/** The answer's key sentence, taken out so it can lead at the answer size,
 *  and the rest of the answer as support. `in_lead`: the backend's lead
 *  sentence, before "From the sources consulted:"; its count comes from
 *  `doc_id`, so it carries that citation mark (no words change).
 *  Otherwise the first sentence citing `doc_id`. Null when there is no
 *  lead fact or the sentence is not found, so nothing is singled out. */
export function keySentence(
  answer: ClaimPart[][],
  fact: { doc_id: string; in_lead: boolean } | null | undefined
): { key: ClaimPart[]; rest: ClaimPart[][] } | null {
  if (!fact?.doc_id || !answer.length) return null;
  if (fact.in_lead) {
    const [first, ...others] = answer;
    const k = first.findIndex((p) => p.text.includes(FACTS_PHRASE));
    if (k < 0) return null;
    const at = first[k].text.indexOf(FACTS_PHRASE);
    const head = first[k].text.slice(0, at).trimEnd();
    const key = [...first.slice(0, k), ...(head ? [{ ...first[k], text: head, cite: undefined }] : [])]
      .filter((p) => p.text.trim() || p.cite);
    if (!key.some((p) => p.text.trim())) return null;
    // The mark sits right after the closing punctuation, with no space.
    key[key.length - 1] = { ...key[key.length - 1], text: key[key.length - 1].text.trimEnd() };
    key.push({ text: '', cite: fact.doc_id });
    const tail = [{ ...first[k], text: first[k].text.slice(at) }, ...first.slice(k + 1)];
    return { key, rest: [tail, ...others] };
  }
  for (let i = 0; i < answer.length; i++) {
    const ss = sentencesOf(answer[i]);
    const j = ss.findIndex((s) => s.some((p) => p.cite === fact.doc_id));
    if (j < 0) continue;
    const own = joinSentences(ss.filter((_, n) => n !== j));
    const rest = [...answer.slice(0, i), own, ...answer.slice(i + 1)].filter((p) => p.length);
    return { key: ss[j], rest };
  }
  return null;
}

const EXP_LABEL = /^\s*Experimental:\s+/;

/** A paragraph from an experimental source opens with the badge part; the
 *  badge replaces the sentence's own "Experimental:" label. The space
 *  after the badge is in the text, where the template cannot trim it. */
function badged(parts: ClaimPart[]): ClaimPart[] {
  const [first, ...rest] = parts;
  const t = first.text.replace(EXP_LABEL, '').trimStart();
  return [{ text: '', exp: true }, { ...first, text: ` ${t.charAt(0).toUpperCase()}${t.slice(1)}` }, ...rest];
}

/** A question's answer with a lead fact: the key sentence (keySentence),
 *  then the rest as one paragraph per cited source (bySource). Paragraphs
 *  citing an experimental source come last, each with the Experimental
 *  badge. An experimental sentence is never the key sentence: then no
 *  sentence is singled out (`key` null) and the paragraphs are the whole
 *  answer. Null when there is no lead fact or its sentence is not found. */
export function keyedAnswer(
  answer: ClaimPart[][],
  fact: { doc_id: string; in_lead: boolean } | null | undefined,
  isExp: (docId: string) => boolean
): { key: ClaimPart[] | null; paras: ClaimPart[][] } | null {
  const k = keySentence(answer, fact);
  if (!k) return null;
  const key = citedIn([k.key]).some(isExp) ? null : k.key;
  const support = (key ? k.rest : answer).flatMap(bySource);
  const exp = (p: ClaimPart[]) => citedIn([p]).some(isExp);
  const paras = [...support.filter((p) => !exp(p)), ...support.filter(exp).map(badged)];
  return { key, paras: key ? [key, ...paras] : paras };
}

/** The Answer or In brief section of a parsed briefing, with the lead word
 *  split off its first paragraph (splitLead). The gallery's standfirsts
 *  read the same paragraphs, so they pick the key sentence the page sets. */
export function leadAnswer(blocks: BriefingBlock[]) {
  const lead = sections(splitBriefing(blocks).lead)[0];
  const leadParas = lead?.paras ?? [];
  const first = splitLead(leadParas[0] ?? []);
  const answer = leadParas.length ? [first.parts, ...leadParas.slice(1)] : [];
  return { lead, leadParas, first, answer };
}

/** The first sentence of a paragraph, for the "Briefing ready" announcement. */
export function firstSentence(parts: ClaimPart[] | undefined): string | null {
  if (!parts?.length) return null;
  return text(sentencesOf(parts)[0] ?? []).trim() || null;
}

/** The community district a refusal suggests ("Did you mean QN14?"). */
export function suggestedDistrict(refusal: string): string | null {
  return /Did you mean ([A-Z]{2}\d{2})\?/.exec(refusal)?.[1] ?? null;
}

/** A refusal's first sentence ("Riprap does not answer this question.")
 *  comes off its first paragraph so it can stand at the answer position. */
export function splitSentence(parts: ClaimPart[]): { sentence: string; parts: ClaimPart[] } | null {
  const [first, ...rest] = parts;
  const m = first && !first.cite ? /^([^.]+\.)\s*/.exec(first.text) : null;
  if (!m) return null;
  const tail = [{ ...first, text: first.text.slice(m[0].length) }, ...rest].filter((p) => p.text || p.cite);
  return { sentence: m[1], parts: tail };
}

/** The DEP stormwater scenarios in reading order (district pages add `_nta`). */
const DEP_SCENARIOS = ['dep_moderate_current', 'dep_moderate_2050', 'dep_extreme_2080'];
const baseDoc = (docId: string) => docId.replace(/_nta$/, '');
const scenario = (c: Card) => DEP_SCENARIOS.indexOf(baseDoc(c.docId));

/** The citation a row's Cite column links to. */
export function citationOf(c: Pick<Card, 'citeId' | 'docId'>, citations: Record<string, Citation>): Citation | null {
  return (c.citeId && citations[c.citeId]) || citations[c.docId] || null;
}

/** Two or more DEP stormwater scenario cards become one row where the
 *  first of them stood, its findings in scenario order (current, 2050,
 *  2080), each keeping its own citation and date. */
export function mergeDepScenarios(cards: Card[]): EvidenceRow[] {
  const dep = cards.filter((c) => scenario(c) >= 0);
  if (dep.length < 2) return cards;
  const parts = [...dep].sort((a, b) => scenario(a) - scenario(b));
  const row: EvidenceRow = {
    ...parts[0],
    id: 'dep-scenarios',
    // District cards name their scenario after a comma; the row names the map.
    source: parts[0].source.split(',')[0],
    tier: 'modeled',
    scalars: undefined,
    headline: undefined,
    parts
  };
  return cards.flatMap((c) => (c === dep[0] ? [row] : scenario(c) >= 0 ? [] : [c]));
}

/** The first found cards cite what the answer cites (in the answer's
 *  order); the rest follow grouped by Stone, and experimental sources the
 *  answer does not cite close the table in one folded group.
 *  The DEP scenarios share one row. Absent and meta cards are not
 *  evidence and are left out by the caller. */
/** A row is dated as its citation is: the backend dates every source it
 *  cites (a dataset date, a retrieval date, or the fetch time of a live
 *  reading) and the source lists show that, so the table shows the same.
 *  The manifest's date stays only on a card with no citation. */
export function withDatasetDate(c: Card, citations: Record<string, Citation>): Card {
  const v = citationOf(c, citations)?.vintage;
  return v ? { ...c, vintage: v } : c;
}

export function evidenceGroups(cards: Card[], cited: string[], firstLabel = 'Behind the answer'): EvidenceGroup[] {
  const rankOne = (c: Card) => {
    const i = cited.indexOf(c.docId);
    const j = c.citeId ? cited.indexOf(c.citeId) : -1;
    return i < 0 ? j : j < 0 ? i : Math.min(i, j);
  };
  const rank = (r: EvidenceRow) => {
    const ranks = (r.parts ?? [r]).map(rankOne).filter((n) => n >= 0);
    return ranks.length ? Math.min(...ranks) : -1;
  };
  const rows = mergeDepScenarios(cards);
  const behind = rows.filter((c) => rank(c) >= 0).sort((a, b) => rank(a) - rank(b));
  const rest = rows.filter((c) => rank(c) < 0);
  const groups: EvidenceGroup[] = behind.length
    ? [{ key: 'answer', name: firstLabel, role: null, cards: behind }]
    : [];
  for (const key of STONE_ORDER) {
    const inStone = rest.filter((c) => c.stone === key && !c.experimental);
    if (inStone.length) groups.push({ key, name: STONE_META[key].name, role: STONE_META[key].role, cards: inStone });
  }
  const trial = STONE_ORDER.flatMap((key) => rest.filter((c) => c.stone === key && c.experimental));
  if (trial.length) {
    groups.push({ key: 'experimental', name: `Experimental sources (${trial.length})`, role: null, cards: trial, closed: true });
  }
  return groups;
}

/** Citation numbers by first appearance on the page: `order` is every
 *  doc id the page cites, top to bottom. Sources never cited follow in
 *  their existing order. Ids and anchors (`cite-{docId}`) do not change. */
export function numberByAppearance(citations: Record<string, Citation>, order: string[]): Record<string, Citation> {
  const first = [...new Set(order)].filter((id) => citations[id]);
  const rest = Object.values(citations)
    .sort((a, b) => a.n - b.n)
    .map((c) => c.id)
    .filter((id) => !first.includes(id));
  return Object.fromEntries([...first, ...rest].map((id, i) => [id, { ...citations[id], n: i + 1 }]));
}

/** Several marks on one claim ("[a][b][c]": the claim part, then empty
 *  cited parts) read in ascending number. */
export function sortMarks(parts: ClaimPart[], citations: Record<string, Citation>): ClaimPart[] {
  const out = parts.map((p) => ({ ...p }));
  const n = (p: Pick<ClaimPart, 'cite'>) => (p.cite && citations[p.cite]?.n) || Infinity;
  for (let i = 0; i < out.length; i++) {
    if (!out[i].cite) continue;
    let j = i + 1;
    while (j < out.length && out[j].cite && out[j].text === '') j++;
    const marks = out.slice(i, j).map(({ cite, tier }) => ({ cite, tier })).sort((a, b) => n(a) - n(b));
    marks.forEach((m, k) => Object.assign(out[i + k], m));
    i = j - 1;
  }
  return out;
}

function flatten(ms: StoneTrace['members']): StoneTrace['members'] {
  return ms.flatMap((m) => (m.children ? [m, ...flatten(m.children)] : [m]));
}

/** RunHealthStrip's facts as plain sentences. Unknown values (no wall
 *  clock, an unlabelled energy figure) are left out, not printed. */
export function runFacts(run: RunState): string[] {
  const d = run.findingsData;
  const all = d.stones.flatMap((s) => flatten(s.members));
  const count = (s: string) => all.filter((m) => m.status === s).length;
  const parts = [
    `${count('fired') + count('warned')} ran`,
    count('silent_by_design') && `${count('silent_by_design')} ran with nothing to report`,
    count('warned') && `${count('warned')} returned a warning`,
    count('errored') && `${count('errored')} failed`,
    count('not_invoked') && `${count('not_invoked')} ${count('not_invoked') === 1 ? 'was' : 'were'} not run`
  ].filter(Boolean);
  const facts = [
    `${d.stones.length} Stone${d.stones.length === 1 ? '' : 's'}, ${all.length} registered source function${all.length === 1 ? '' : 's'}: ${parts.join(', ')}.`
  ];
  const wall = d.wallSeconds ?? run.runWallSeconds;
  if (wall != null && Number.isFinite(wall)) facts.push(`The run took ${wall < 1 ? `${Math.round(wall * 1000)} ms` : `${wall.toFixed(1)} s`}.`);
  if (d.cacheHit != null) facts.push(`${Math.round(d.cacheHit * 100)}% of lookups came from the cache.`);
  const em = d.emissions;
  if (em?.n_calls) {
    const tok = em.tokens?.total;
    let line = `${em.n_calls} language-model call${em.n_calls === 1 ? '' : 's'}`;
    if (tok) line += `, ${tok.toLocaleString('en-US')} tokens`;
    const wh = em.total_wh;
    if (typeof wh === 'number' && Number.isFinite(wh) && em.energy_status && ['measured', 'estimated', 'mixed'].includes(em.energy_status)) {
      line += `, ${wh < 0.1 ? `${(wh * 1000).toFixed(1)} mWh` : `${wh.toFixed(2)} Wh`} (${em.energy_status})`;
    }
    facts.push(`${line}.`);
  }
  return facts;
}

const LOCAL_RE = /\s*(?:on this machine\s*)?\((?:localhost|127\.0\.0\.1):\d+\)/i;

/** A static snapshot names no local endpoint: "Ollama on this machine
 *  (localhost:11434)" reads "Ollama, run when the snapshot was generated". */
export function snapshotModels(models: ModelLine[]): ModelLine[] {
  return models.map((m) => {
    if (!LOCAL_RE.test(m.where)) return m;
    const host = m.where.replace(LOCAL_RE, '').trim();
    return { ...m, where: host ? `${host}, run when the snapshot was generated` : 'Run when the snapshot was generated' };
  });
}

export function briefingModel(run: RunState, queryText: string, meta?: SnapshotMeta) {
  const f = run.finalResult;
  const g = f?.grounding;
  const blocks = run.briefing.blocks;
  const split = splitBriefing(blocks);
  const question = run.plan?.question || g?.question || (looksLikeQuestion(queryText) ? queryText : '') || null;
  const isDistrict = !!f?.area_boundary || DISTRICT_RE.test(queryText.trim());
  const kind: Kind = question ? 'question' : isDistrict ? 'district' : 'address';

  const { lead, leadParas, first, answer: leadAnswerParas } = leadAnswer(blocks);
  const hasAnswer = blocks.some((b) => b.kind === 'head' && b.label === 'Answer');
  // A refused question has no Answer section, only a statement; it is set
  // where the answer would be, its first sentence as the lead.
  const refusalParas = run.refused && !leadParas.length
    ? blocks.flatMap((b) => (b.kind === 'prose' ? [b.parts] : []))
    : [];
  const refusal = refusalParas.length ? splitSentence(refusalParas[0]) : null;
  const answer0 = refusal
    ? [refusal.parts, ...refusalParas.slice(1)].filter((p) => p.length)
    : leadAnswerParas;
  // A question's answer leads with its key sentence; the rest follows,
  // one size smaller, as support, one short paragraph per cited source.
  // Place briefings keep their In brief.
  // Experimental sources come after the answer, badged, and never lead it.
  const isExp = (id: string) => run.briefing.citations[id]?.maturity === 'experimental';
  const answered = question && !refusal ? keyedAnswer(answer0, g?.lead_fact, isExp) : null;
  const keyed = answered?.key ?? null;
  const answerParas = answered?.paras ?? answer0;
  // A count answer whose count sits inside its key sentence leads with that count.
  // An area's In brief opens with its Sandy share ("0.8% of this area ..."),
  // which is not the headline of a district that floods from rain: a
  // district or neighbourhood briefing sets no figure large, only its text.
  const areaBrief = !question && POLYGON_INTENTS.has(f?.intent ?? run.plan?.intent ?? '');
  const leadWord = refusal || areaBrief
    ? null : first.word ?? (keyed && g?.answer_lead === 'count' ? countLead(keyed) : null);

  // "Checks run: ..." closes the Out of scope note; it is its own line here.
  const outParas = sections(split.outOfScope).flatMap((s) => s.paras);
  const checks = outParas.find((p) => text(p).startsWith('Checks run'));
  const outOfScope0 = outParas.filter((p) => p !== checks);
  const scope0 = sections(split.scope).flatMap((s) => s.paras);
  const body0 = refusal ? [] : sections(split.body).map((s) => ({ ...s, label: stoneHead(s.label) }));

  const cited = citedIn(answerParas);
  const allCards: Card[] = run.findingsData.cards;
  const cards = allCards.filter((c) => !c.absent && c.variant !== 'meta')
    .map((c) => withDatasetDate(c, run.briefing.citations));
  const absent = allCards.filter((c) => c.absent);
  const metaCard = allCards.find((c) => c.variant === 'meta') ?? null;
  const leadLabel = refusal ? 'Response' : lead?.label || (question ? 'Answer' : 'In brief');
  const groups = evidenceGroups(cards, cited, leadLabel === 'In brief' ? 'Behind the summary' : 'Behind the answer');

  // One numbering for the whole page, in reading order: the answer (or In
  // brief) and its scope note, the evidence table, the report sections,
  // then the Out of scope note. The print packet reuses it.
  const raw = run.briefing.citations;
  const tableIds = groups.flatMap((gr) => gr.cards.flatMap((r) => r.parts ?? [r])).map((c) => citationOf(c, raw)?.id ?? '');
  const citationsById = numberByAppearance(raw, [
    ...citedIn([...answerParas, ...scope0]),
    ...tableIds,
    ...citedIn(body0.flatMap((s) => s.paras)),
    ...citedIn(outOfScope0)
  ]);
  const citations: Citation[] = Object.values(citationsById).sort((a, b) => a.n - b.n);
  const sorted = (paras: ClaimPart[][]) => paras.map((p) => sortMarks(p, citationsById));
  const answer = sorted(answerParas);
  const scope = sorted(scope0);
  const body = body0.map((s) => ({ ...s, paras: sorted(s.paras) }));
  const outOfScope = sorted(outOfScope0);
  const narration = (c: Card) => pebbleManifest.byId[c.id.replace(/^pebble-/, '')]?.narration.short ?? null;
  const findings = new Map(cards.map((c) => [c.id, findingOf(c, narration(c))]));

  const models = meta ? snapshotModels(metaCard?.models ?? []) : metaCard?.models ?? [];
  const modelId = g?.model ?? null;
  // The model id is printed once: in the models list when it has a row
  // for it, else in the snapshot stamp.
  const modelListed = !!modelId && models.some((m) => m.repo === modelId);
  const shownText = [
    ...answer, ...scope, ...body.flatMap((s) => s.paras), ...outParas
  ].map(text).join(' ') + ' ' + [...findings.values()].map((x) => (x ? `${x.first} ${x.rest}` : '')).join(' ');

  return {
    kind,
    question,
    place: run.resolvedPlace ?? queryText,
    leadLabel,
    hasAnswer,
    leadWord,
    /** "Yes." keeps its full stop; a count is set bare; a refusal leads
     *  with its first sentence. */
    lead: refusal ? refusal.sentence : leadWord && /^[A-Z]/.test(leadWord) ? `${leadWord}.` : leadWord,
    /** The lead is a sentence, not a word or a figure. */
    leadIsSentence: !!refusal,
    answer,
    /** The first answer paragraph is the key sentence; the rest support it. */
    keyed: !!keyed,
    scope,
    body,
    outOfScope,
    /** A cannot-answer line cites nothing, so the backend's "answer is the
     *  cited text word for word" reason is left off. */
    checks: checks
      ? g?.answer_lead === 'cannot_answer'
        ? text(checks).replace(/; no entailment check needed[^.;]*/, '')
        : text(checks)
      : null,
    citations,
    /** The page's citations, numbered by first appearance. */
    citationsById,
    /** Doc ids the answer cites, in reading order. */
    cited,
    cards,
    findings,
    evidenceGroups: groups,
    absent,
    /** Sources behind the cards that were not run for this question. */
    notRun: [...new Set(absent.filter((c) => c.absent === 'Not run').map((c) => c.source))],
    metaCard,
    models,
    modelId,
    lists: sourceLists(run),
    /** The mode line without the model id, which the method block prints
     *  once. A refusal checked no claims, so it has none. */
    modeLine: sentence(g && !run.refused ? modeLine({ ...g, model: undefined }) : null),
    dropped: g?.dropped_claims ?? [],
    unanswered: !!question && !!f && !run.stopped && !hasAnswer && g?.tier !== 'llm',
    generated: meta ? formatGeneratedAt(meta.generatedAt) : null,
    commit: meta?.commit ?? null,
    stamp: meta && !modelListed ? meta.stamp : null,
    /** Live runs without a models list still name the model once. */
    modelLine: !meta && modelId && !modelListed ? modelId : null,
    terms: termsIn(shownText, cards.length > 0, cards.some((c) => c.tier === 'synthetic')),
    runFacts: runFacts(run),
    /** NYC-only resident resources are offered only on NYC runs. */
    nyc: (f?.deployment ?? deployment.current?.name) === 'nyc'
  };
}

export type BriefingModel = ReturnType<typeof briefingModel>;

const evidenceCard = ({ id, source, experimental, title, tier, vintage, citeId, docId, scalars, headline, variant, parts }: EvidenceRow): EvidenceCard =>
  ({ id, source, experimental, title, tier, vintage, citeId, docId, scalars, headline, variant, ...(parts && { parts: parts.map(evidenceCard) }) });

/** Build the print snapshot from a finished run: the live route calls it
 *  when the stream ends, the gallery when a reader presses Print
 *  (`origin: 'gallery'`, so live readings print dated to the snapshot).
 *  It carries the report as the briefing page sets it, so the print route
 *  needs no RunState. */
export function snapshotFromRun(
  run: RunState,
  queryId: string,
  queryText: string,
  generatedAt: string = new Date().toISOString(),
  origin: 'gallery' | 'live' = 'live',
): PrintSnapshot {
  const m = briefingModel(run, queryText);
  const g = run.finalResult?.grounding;
  return {
    queryId,
    queryText,
    origin,
    intent: run.plan?.intent ?? null,
    specialists: run.plan?.specialists?.length ?? 0,
    blocks: run.briefing.blocks,
    citations: m.citationsById,
    generatedAt,
    resolvedPlace: run.resolvedPlace,
    question: m.question,
    mode: run.refused ? null : modeLine(g),
    unanswered: m.unanswered,
    consulted: m.lists.consulted?.map(({ title, failed }) => ({ title, failed })),
    noData: m.lists.noData,
    notChecked: m.lists.notChecked,
    kind: m.kind,
    lead: m.lead,
    leadLabel: m.leadLabel,
    answer: m.answer,
    keyed: m.keyed,
    scope: m.scope,
    body: m.body,
    outOfScope: m.outOfScope,
    checks: m.checks,
    cited: m.cited,
    evidence: {
      groups: m.evidenceGroups.map((gr) => ({ ...gr, cards: gr.cards.map(evidenceCard) })),
      findings: Object.fromEntries(m.findings),
      notRun: m.notRun,
    },
  };
}
