export type Tier = 'empirical' | 'modeled' | 'proxy';

/** The tier in reader's words (DESIGN.md: source notes and tables). */
export const TIER_WORDS: Record<Tier, string> = {
  empirical: 'Measured',
  modeled: 'Modeled',
  proxy: 'Proxy'
};
