/**
 * Regression for a real bug found 2026-07-15 evaluating a live briefing:
 * the reconciler emits **bold** markdown around key figures (HAND,
 * elevation, dates — app/reconcile.py's EXTRA_SYSTEM_PROMPT), and nothing
 * ever rendered it — the literal asterisks showed up in the UI
 * ("HAND of **3.81 m**"). parseSentenceParts now splits bold runs into
 * their own ClaimPart with `bold: true` instead of passing `**...**`
 * through as plain text.
 */
import { describe, it, expect } from 'vitest';
import { parseBriefing, splitBriefing } from '$lib/client/parseBriefing';

function proseText(blocks: ReturnType<typeof parseBriefing>['blocks']): string {
  return blocks
    .filter((b) => b.kind === 'prose')
    .flatMap((b) => (b.kind === 'prose' ? b.parts.map((p) => p.text) : []))
    .join('');
}

describe('parseBriefing — bold markdown', () => {
  it('strips ** markers and marks the run as bold, no literal asterisks survive', () => {
    const { blocks } = parseBriefing(
      '**Status.** The HAND is **3.81 m** at this address.'
    );
    const text = proseText(blocks);
    expect(text).not.toContain('*');

    const boldParts = blocks
      .filter((b) => b.kind === 'prose')
      .flatMap((b) => (b.kind === 'prose' ? b.parts : []))
      .filter((p) => p.bold);
    expect(boldParts.map((p) => p.text)).toContain('3.81 m');
  });

  it('bold immediately before a citation keeps the citation attached to the bold run', () => {
    const { blocks, citations } = parseBriefing(
      '**Status.** Hurricane Ida high-water marks were recorded at **138 m** [ida_hwm].'
    );
    const proseBlock = blocks.find((b) => b.kind === 'prose');
    expect(proseBlock?.kind).toBe('prose');
    const boldWithCite = proseBlock?.kind === 'prose'
      ? proseBlock.parts.find((p) => p.bold && p.cite)
      : undefined;
    expect(boldWithCite?.text).toBe('138 m');
    expect(boldWithCite?.cite).toBe('ida_hwm');
    expect(citations.ida_hwm).toBeTruthy();
  });

  it('plain text with no ** markers is unaffected', () => {
    const { blocks } = parseBriefing('**Status.** No emphasis in this sentence at all.');
    const text = proseText(blocks);
    expect(text).toContain('No emphasis in this sentence at all.');
  });
});

describe('parseBriefing: answer section', () => {
  it('recognises **Answer.** as the first section with its citations', () => {
    const { blocks, citations } = parseBriefing(
      'Scope line.\n\n**Answer.**\nIda high-water marks were recorded nearby [ida_hwm].\n\n**Status.** Fine [sandy].'
    );
    const heads = blocks.filter((b) => b.kind === 'head');
    expect(heads.map((h) => (h.kind === 'head' ? [h.n, h.label] : []))).toEqual([
      ['00', 'Answer'],
      ['01', 'Status']
    ]);
    expect(citations.ida_hwm).toBeDefined();
  });

  it('numbers Stone sections from 01 after the Answer', () => {
    const { blocks } = parseBriefing(
      'Scope line.\n\n**Answer.**\nYes [ida_hwm].\n\n**Hazard Reader.**\nZone X [fema_nfhl].\n\n**Out of scope.** Title.'
    );
    const heads = blocks.filter((b) => b.kind === 'head');
    expect(heads.map((h) => (h.kind === 'head' ? h.n : ''))).toEqual(['00', '01', '02']);
  });
});

describe('splitBriefing', () => {
  const text = (bs: ReturnType<typeof parseBriefing>['blocks']) =>
    bs.map((b) => (b.kind === 'head' ? `#${b.label}` : proseText([b]))).join(' | ');

  it('separates the scope preamble, the Answer, the body and Out of scope', () => {
    const { blocks } = parseBriefing(
      'Scope line.\n\n**Answer.**\nYes [ida_hwm].\n\n**Hazard Reader.**\nZone X [fema_nfhl].\n\n' +
        '**Out of scope.** Title.\n\nChecks run: citations.'
    );
    const s = splitBriefing(blocks);
    expect(text(s.scope)).toBe('Scope line.');
    expect(text(s.lead)).toMatch(/^#Answer \| Yes/);
    expect(text(s.body)).toMatch(/^#Hazard Reader \| Zone X/);
    expect(text(s.outOfScope)).toBe('Title. | Checks run: citations.');
  });

  it('keeps everything in the body when there is no preamble or Out of scope', () => {
    const { blocks } = parseBriefing('**Hazard Reader.**\nZone X [fema_nfhl].');
    const s = splitBriefing(blocks);
    expect(s.scope).toEqual([]);
    expect(s.lead).toEqual([]);
    expect(s.outOfScope).toEqual([]);
    expect(s.body).toEqual(blocks);
  });
});
