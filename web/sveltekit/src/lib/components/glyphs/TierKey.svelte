<script lang="ts">
  /** Compact key for the four evidence-tier marks the briefing, the
   *  citations and the print packet draw inline. The meanings are the
   *  TIER_META descriptions (the same text as the TierGlyph tooltips). */
  import TierGlyph from './TierGlyph.svelte';
  import { TIER_META, type Tier } from '$lib/types/tier';

  const TIERS: Tier[] = ['empirical', 'modeled', 'proxy', 'synthetic'];
  // The key names the tiers in one word each; TIER_META's synthetic
  // label is "Synthetic prior".
  const WORD: Record<Tier, string> = {
    empirical: 'Empirical',
    modeled: 'Modeled',
    proxy: 'Proxy',
    synthetic: 'Synthetic'
  };
</script>

<ul class="tier-key" aria-label="Evidence tier key">
  {#each TIERS as tier (tier)}
    <li>
      <span class="tier-key-mark" aria-hidden="true"><TierGlyph {tier} size={10} color="var(--tier-{tier})" /></span>
      <span><strong>{WORD[tier]}</strong>: {TIER_META[tier].desc.toLowerCase()}</span>
    </li>
  {/each}
</ul>

<style>
  .tier-key {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2px 16px;
    font-size: 12px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .tier-key li {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }
  .tier-key strong {
    font-weight: 600;
    color: var(--ink);
  }
  .tier-key-mark {
    flex: none;
  }
  @media (max-width: 480px) {
    .tier-key { grid-template-columns: 1fr; }
  }
</style>
