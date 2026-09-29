/**
 * The view model behind a briefing page. Built from a RunState, so the
 * live route (streaming) and the gallery (a replayed `final`) render the
 * same way. Gallery pages add their snapshot meta; live runs have none.
 */
import { looksLikeQuestion, type RunState } from '$lib/client/runState.svelte';
import { splitBriefing } from '$lib/client/parseBriefing';
import { modeLine } from '$lib/client/cardAdapter';
import { formatGeneratedAt } from '$lib/client/gallery';
import { citedIn, findingOf, termsIn } from '$lib/client/briefingText';
import { sourceLists } from '$lib/stores/briefingState.svelte';
import { pebbleManifest } from '$lib/stores/pebbleManifest.svelte';
import { deployment } from '$lib/stores/deployment.svelte';
import { STONE_META, STONE_ORDER, type Card, type StoneTrace } from '$lib/types/card';
import type { BriefingBlock, Citation, ClaimPart } from '$lib/types/claim';

export type Kind = 'question' | 'address' | 'district';
export type Section = { label: string; paras: ClaimPart[][] };
export type SnapshotMeta = { generatedAt: string; commit: string; stamp: string | null };
export type EvidenceGroup = { key: string; name: string; role: string | null; cards: Card[] };

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

/** "Yes." comes off the first answer part and is set large on its own. A
 *  count is set large too, but its sentence stays whole below it. */
export function splitLead(parts: ClaimPart[]): { word: string | null; parts: ClaimPart[] } {
  const [first, ...rest] = parts;
  if (!first) return { word: null, parts };
  const yes = LEAD_RE.exec(first.text);
  if (yes) return { word: yes[1], parts: [{ ...first, text: first.text.slice(yes[0].length) }, ...rest] };
  return { word: COUNT_RE.exec(first.text)?.[1] ?? null, parts };
}

/** The first found cards cite what the answer cites (in the answer's
 *  order); the rest follow grouped by Stone. Absent and meta cards are not
 *  evidence and are left out by the caller. */
export function evidenceGroups(cards: Card[], cited: string[], firstLabel = 'Behind the answer'): EvidenceGroup[] {
  const rank = (c: Card) => {
    const i = cited.indexOf(c.docId);
    const j = c.citeId ? cited.indexOf(c.citeId) : -1;
    return i < 0 ? j : j < 0 ? i : Math.min(i, j);
  };
  const behind = cards.filter((c) => rank(c) >= 0).sort((a, b) => rank(a) - rank(b));
  const rest = cards.filter((c) => rank(c) < 0);
  const groups: EvidenceGroup[] = behind.length
    ? [{ key: 'answer', name: firstLabel, role: null, cards: behind }]
    : [];
  for (const key of STONE_ORDER) {
    const inStone = rest.filter((c) => c.stone === key);
    if (inStone.length) groups.push({ key, name: STONE_META[key].name, role: STONE_META[key].role, cards: inStone });
  }
  return groups;
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
    count('not_invoked') && `${count('not_invoked')} were not run`
  ].filter(Boolean);
  const facts = [
    `${d.stones.length} Stones, ${all.length} registered source functions: ${parts.join(', ')}.`
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

export function briefingModel(run: RunState, queryText: string, meta?: SnapshotMeta) {
  const f = run.finalResult;
  const g = f?.grounding;
  const blocks = run.briefing.blocks;
  const split = splitBriefing(blocks);
  const question = run.plan?.question || g?.question || (looksLikeQuestion(queryText) ? queryText : '') || null;
  const isDistrict = !!f?.area_boundary || DISTRICT_RE.test(queryText.trim());
  const kind: Kind = question ? 'question' : isDistrict ? 'district' : 'address';

  const lead = sections(split.lead)[0];
  const leadParas = lead?.paras ?? [];
  const hasAnswer = blocks.some((b) => b.kind === 'head' && b.label === 'Answer');
  const first = splitLead(leadParas[0] ?? []);
  const answer = leadParas.length ? [first.parts, ...leadParas.slice(1)] : [];
  const leadWord = first.word;

  // "Checks run: ..." closes the Out of scope note; it is its own line here.
  const outParas = sections(split.outOfScope).flatMap((s) => s.paras);
  const checks = outParas.find((p) => text(p).startsWith('Checks run'));
  const outOfScope = outParas.filter((p) => p !== checks);
  const scope = sections(split.scope).flatMap((s) => s.paras);
  const body = sections(split.body);

  const citations: Citation[] = Object.values(run.briefing.citations).sort((a, b) => a.n - b.n);
  const cited = citedIn(answer);
  const allCards: Card[] = run.findingsData.cards;
  const cards = allCards.filter((c) => !c.absent && c.variant !== 'meta');
  const absent = allCards.filter((c) => c.absent);
  const metaCard = allCards.find((c) => c.variant === 'meta') ?? null;
  const leadLabel = lead?.label || (question ? 'Answer' : 'In brief');
  const groups = evidenceGroups(cards, cited, leadLabel === 'In brief' ? 'Behind the summary' : 'Behind the answer');
  const narration = (c: Card) => pebbleManifest.byId[c.id.replace(/^pebble-/, '')]?.narration.short ?? null;
  const findings = new Map(cards.map((c) => [c.id, findingOf(c, narration(c))]));

  const models = metaCard?.models ?? [];
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
    /** "Yes." keeps its full stop; a count is set bare. */
    lead: leadWord && /^[A-Z]/.test(leadWord) ? `${leadWord}.` : leadWord,
    answer,
    scope,
    body,
    outOfScope,
    checks: checks ? text(checks) : null,
    citations,
    citationsById: run.briefing.citations,
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
    /** The mode line without the model id, which the method block prints once. */
    modeLine: sentence(g ? modeLine({ ...g, model: undefined }) : null),
    dropped: g?.dropped_claims ?? [],
    unanswered: !!question && !!f && !run.stopped && !hasAnswer && g?.tier !== 'llm',
    generated: meta ? formatGeneratedAt(meta.generatedAt) : null,
    commit: meta?.commit ?? null,
    stamp: meta && !modelListed ? meta.stamp : null,
    /** Live runs without a models list still name the model once. */
    modelLine: !meta && modelId && !modelListed ? modelId : null,
    terms: termsIn(shownText, cards.length > 0),
    runFacts: runFacts(run),
    /** NYC-only resident resources are offered only on NYC runs. */
    nyc: (f?.deployment ?? deployment.current?.name) === 'nyc'
  };
}

export type BriefingModel = ReturnType<typeof briefingModel>;
