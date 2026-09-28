<script lang="ts">
  /** Labelled tier mark. The drawing is EvidenceMark's (DESIGN.md: a square
   *  whose fill is solid, hatched, hollow or stippled), so every tier mark
   *  in the app has one shape vocabulary. */
  import type { Tier } from '$lib/types/tier';
  import EvidenceMark from './EvidenceMark.svelte';

  interface Props {
    tier: Tier;
    size?: number;
    color?: string;
    title?: string;
  }

  let { tier, size = 12, color = 'currentColor', title }: Props = $props();

  const TIER_DESC: Record<Tier, string> = {
    empirical: 'Empirical: directly measured or observed',
    modeled: 'Modeled: scenario-based prediction',
    proxy: 'Proxy: indirect indicator',
    synthetic: 'Synthetic prior: generated, not observed'
  };
</script>

<EvidenceMark {tier} {size} {color} title={title ?? TIER_DESC[tier]} />
