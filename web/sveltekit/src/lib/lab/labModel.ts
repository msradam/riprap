/**
 * Design pass 2, Part A lab only (deleted in Part C). One view model for
 * the three direction prototypes, built from a gallery entry's RunState so
 * every direction renders the same real data.
 */
import type { RunState } from '$lib/client/runState.svelte';
import type { GalleryEntry } from '$lib/client/gallery';
import { formatGeneratedAt, llmStamp } from '$lib/client/gallery';
import { splitBriefing, citedDocIds } from '$lib/client/parseBriefing';
import { modeLine } from '$lib/client/cardAdapter';
import { sourceLists } from '$lib/stores/briefingState.svelte';
import type { BriefingBlock, Citation, ClaimPart } from '$lib/types/claim';
import type { Card } from '$lib/types/card';

export type Kind = 'question' | 'address' | 'district';
export type Section = { label: string; n: string; paras: ClaimPart[][] };

const LEAD_RE = /^(Yes|No|Partly|Not clear|Unclear)\.\s*/;
const COUNT_RE = /^([\d,]+(?:\.\d+)?%?)\s+/;

function sections(blocks: BriefingBlock[]): Section[] {
  const out: Section[] = [];
  for (const b of blocks) {
    if (b.kind === 'head') out.push({ label: b.label, n: b.n, paras: [] });
    else if (b.kind === 'prose') {
      if (!out.length) out.push({ label: '', n: '', paras: [] });
      out[out.length - 1].paras.push(b.parts);
    }
  }
  return out.filter((s) => s.paras.length);
}

const text = (parts: ClaimPart[]) => parts.map((p) => p.text).join('');

/** Split "Yes." or a leading count off the first answer part. */
function splitLead(parts: ClaimPart[]): { word: string | null; parts: ClaimPart[] } {
  const [first, ...rest] = parts;
  if (!first) return { word: null, parts };
  const yes = LEAD_RE.exec(first.text);
  if (yes) return { word: yes[1], parts: [{ ...first, text: first.text.slice(yes[0].length) }, ...rest] };
  // A count stays in its sentence; the directions may also set it large.
  return { word: COUNT_RE.exec(first.text)?.[1] ?? null, parts };
}

/** District when the entry has an area boundary or a district code
 *  ("QN12") for an address; else question or address. */
export function kindOf(entry: GalleryEntry): Kind {
  if (entry.final.area_boundary || /^[A-Z]{2}\s?\d{1,2}$/.test(entry.address)) return 'district';
  return entry.question ? 'question' : 'address';
}

export function labModel(run: RunState, entry: GalleryEntry) {
  const final = entry.final;
  const g = final.grounding;
  const blocks = run.briefing.blocks;
  const split = splitBriefing(blocks);
  const lead = sections(split.lead)[0];
  const leadParas = lead?.paras ?? [];
  const question = entry.question ?? null;
  const kind = kindOf(entry);

  // "Checks run: ..." closes the Out of scope note; it is its own line here.
  const outParas = sections(split.outOfScope).flatMap((s) => s.paras);
  const checks = outParas.find((p) => text(p).startsWith('Checks run'));
  const outOfScope = outParas.filter((p) => p !== checks);

  const first = splitLead(leadParas[0] ?? []);
  const citations: Citation[] = Object.values(run.briefing.citations).sort((a, b) => a.n - b.n);
  const cited = citedDocIds(blocks);
  const cards: Card[] = run.findingsData.cards;
  const lists = sourceLists(run);

  return {
    kind,
    question,
    place: run.resolvedPlace ?? entry.address,
    address: entry.address,
    neighborhood: entry.neighborhood,
    leadLabel: lead?.label ?? null,
    /** "Yes", "No", "533": the short answer when the lead starts with one. */
    leadWord: first.word,
    /** The answer paragraphs with the lead word removed from the first. */
    answer: leadParas.length ? [first.parts, ...leadParas.slice(1)] : [],
    scope: sections(split.scope).flatMap((s) => s.paras),
    body: sections(split.body),
    outOfScope,
    checks: checks ? text(checks) : null,
    citations,
    citationsById: run.briefing.citations,
    cited,
    cards: cards.filter((c) => !c.absent && c.variant !== 'meta'),
    absent: cards.filter((c) => c.absent),
    metaCard: cards.find((c) => c.variant === 'meta') ?? null,
    lists,
    modeLine: modeLine(g),
    dropped: g?.dropped_claims ?? [],
    generated: formatGeneratedAt(entry.generated_at),
    commit: entry.riprap_commit,
    stamp: llmStamp(entry)
  };
}

export type LabModel = ReturnType<typeof labModel>;

/** One landing row per gallery entry. `lead` is the first sentence of
 *  the Answer or In brief section, citation markers removed. */
export type Story = {
  slug: string;
  neighborhood: string;
  address: string;
  question: string | null;
  mode: string;
  generated_at: string;
  kind: Kind;
  lead: string;
};
export const DIRECTIONS = ['a', 'b', 'c'] as const;
export type Direction = (typeof DIRECTIONS)[number];
