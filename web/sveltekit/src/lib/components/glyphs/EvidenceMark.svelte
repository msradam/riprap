<script lang="ts">
  /**
   * docs/design/handoff/RIPRAP-MAPPING.md — evidence tier axis.
   * A square whose FILL carries directness: solid (empirical) / hatched
   * (modeled) / hollow (proxy) / stippled (synthetic). Hue reinforces but
   * is never the sole carrier, so the tier survives grayscale and print
   * (WCAG 1.4.1) — verified by docs/design/handoff/gates/grayscale-gate.mjs.
   *
   * Distinct from the existing glyphs/TierGlyph.svelte (square/square/
   * circle/hatched-square, `--tier-*` tokens, used app-wide). EvidenceMark
   * is the report-content variant: all four tiers share one shape (square)
   * so only the fill pattern changes, and it reads `--riprap-tier-*`.
   */
  import type { Tier } from '$lib/types/tier';
  import { TIER_META } from '$lib/types/tier';

  interface Props {
    tier: Tier;
    size?: number;
    /** Decorative by default (aria-hidden) — pair with visible tier text
     *  (EMP/MOD/PRX/SYN) or an accessible name at the call site. */
    title?: string;
  }

  let { tier, size = 12, title }: Props = $props();

  let colorVar = $derived(`var(--riprap-tier-${tier})`);
  let patternId = $derived(`rp-hatch-${tier}-${size}`);
  let dotsId = $derived(`rp-dots-${tier}-${size}`);
  let stroke = $derived(Math.max(1, Math.round(size / 8)));
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 {size} {size}"
  aria-hidden={title ? undefined : 'true'}
  role={title ? 'img' : undefined}
  aria-label={title}
  style="flex: none; display: inline-block; vertical-align: -0.12em;"
>
  {#if title}<title>{title ?? TIER_META[tier].desc}</title>{/if}
  {#if tier === 'empirical'}
    <rect x="0" y="0" width={size} height={size} fill={colorVar} />
  {:else if tier === 'modeled'}
    <defs>
      <pattern id={patternId} width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="3" stroke={colorVar} stroke-width="1.5" />
      </pattern>
    </defs>
    <rect
      x={stroke / 2} y={stroke / 2}
      width={size - stroke} height={size - stroke}
      fill="url(#{patternId})" stroke={colorVar} stroke-width={stroke}
    />
  {:else if tier === 'proxy'}
    <rect
      x={stroke / 2} y={stroke / 2}
      width={size - stroke} height={size - stroke}
      fill="none" stroke={colorVar} stroke-width={stroke}
    />
  {:else}
    <defs>
      <pattern id={dotsId} width="3" height="3" patternUnits="userSpaceOnUse">
        <circle cx="1.5" cy="1.5" r="0.75" fill={colorVar} />
      </pattern>
    </defs>
    <rect
      x={stroke / 2} y={stroke / 2}
      width={size - stroke} height={size - stroke}
      fill="url(#{dotsId})" stroke={colorVar} stroke-width={stroke}
    />
  {/if}
</svg>
