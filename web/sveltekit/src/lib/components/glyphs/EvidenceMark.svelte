<script lang="ts">
  /**
   * docs/design/handoff/RIPRAP-MAPPING.md, evidence tier axis.
   * A square whose FILL carries directness: solid (empirical), hatched
   * (modeled), hollow (proxy), stippled (synthetic). Hue reinforces but
   * is never the sole carrier, so the tier survives grayscale and print
   * (WCAG 1.4.1), verified by docs/design/handoff/gates/grayscale-gate.mjs.
   *
   * The only tier drawing in the app: TierGlyph wraps it with a label.
   */
  import type { Tier } from '$lib/types/tier';

  interface Props {
    tier: Tier;
    size?: number;
    /** Defaults to the tier's `--riprap-tier-*` token. */
    color?: string;
    /** Decorative by default (aria-hidden). Pair with visible tier text
     *  or pass a title for an accessible name. */
    title?: string;
  }

  let { tier, size = 12, color, title }: Props = $props();

  // Per-instance pattern ids: a shared id resolves to the first pattern in
  // the document, which may carry another colour or sit in a hidden subtree.
  const uid = $props.id();
  let fill = $derived(color ?? `var(--riprap-tier-${tier})`);
  let patternId = $derived(`rp-tier-${uid}`);
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
  {#if title}<title>{title}</title>{/if}
  {#if tier === 'empirical'}
    <rect x="0" y="0" width={size} height={size} fill={fill} />
  {:else if tier === 'modeled'}
    <defs>
      <pattern id={patternId} width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="3" stroke={fill} stroke-width="1.5" />
      </pattern>
    </defs>
    <rect
      x={stroke / 2} y={stroke / 2}
      width={size - stroke} height={size - stroke}
      fill="url(#{patternId})" stroke={fill} stroke-width={stroke}
    />
  {:else if tier === 'proxy'}
    <rect
      x={stroke / 2} y={stroke / 2}
      width={size - stroke} height={size - stroke}
      fill="none" stroke={fill} stroke-width={stroke}
    />
  {:else}
    <defs>
      <pattern id={patternId} width="3" height="3" patternUnits="userSpaceOnUse">
        <circle cx="1.5" cy="1.5" r="0.75" fill={fill} />
      </pattern>
    </defs>
    <rect
      x={stroke / 2} y={stroke / 2}
      width={size - stroke} height={size - stroke}
      fill="url(#{patternId})" stroke={fill} stroke-width={stroke}
    />
  {/if}
</svg>
