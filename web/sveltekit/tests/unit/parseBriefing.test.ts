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
import { parseBriefing } from '$lib/client/parseBriefing';

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
