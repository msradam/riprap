import type { FinalResult } from '$lib/client/agentStream';

/** A refused query whose statement suggests a district. */
export const REFUSAL_QUERY = 'QN99';
export const REFUSAL = {
  intent: 'not_implemented',
  plan: { intent: 'not_implemented' },
  paragraph: 'Riprap has no community district QN99. Did you mean QN14?',
  citations: {},
  grounding: { tier: 'no_llm', claims: [], dropped_claims: [] }
} as unknown as FinalResult;
