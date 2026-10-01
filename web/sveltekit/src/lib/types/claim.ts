import type { Tier } from './tier';

export interface Citation {
  id: string;
  n: number;
  tier: Tier;
  source: string;
  title: string;
  docId: string;
  url: string;
  vintage: string;
  retrieved: string;
  /** 'experimental' layers get a visible badge in the citation list. */
  maturity?: 'production' | 'experimental';
}

export interface ClaimPart {
  text: string;
  tier?: Tier;
  cite?: string;
  bold?: boolean;
  /** An empty part that opens a paragraph from an experimental source:
   *  the badge's label, taken off the sentence ("Experimental" or
   *  "Experimental forecast"). `true` in print snapshots saved before the
   *  label was kept. */
  exp?: string | true;
}

export type BriefingBlock =
  | { kind: 'status'; html: string }
  | { kind: 'head'; n: string; label: string; tier?: Tier; title?: string }
  | { kind: 'prose'; parts: ClaimPart[] };
