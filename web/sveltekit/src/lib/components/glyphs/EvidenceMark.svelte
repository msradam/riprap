<script lang="ts">
  /**
   * docs/design/handoff/RIPRAP-MAPPING.md, evidence tier axis.
   * A square whose FILL carries directness: solid (empirical), hatched
   * (modeled), hollow (proxy). Hue reinforces but
   * is never the sole carrier, so the tier survives grayscale and print
   * (WCAG 1.4.1), verified by docs/design/handoff/gates/grayscale-gate.mjs.
   *
   * The only tier drawing in the app.
   */
  import type { Tier } from '$lib/types/tier';

  interface Props {
    tier: Tier;
    size?: number;
    /** Defaults to currentColor, so a wrapper sets the hue. */
    color?: string;
    /** Accessible name; defaults to the tier's description. Pass an
     *  empty string for a decorative mark (aria-hidden). */
    title?: string;
  }

  // The modeled tier holds scenario maps, mapped zones, forecasts and an
  // index: "scenario-based prediction" called a scenario a prediction, and
  // fitted none of the others. A proxy here is mostly reports people filed.
  const TIER_DESC: Record<Tier, string> = {
    empirical: 'Empirical: directly measured or observed',
    modeled:
      'Modeled: from a model, not a measurement. The row says which kind: a simulated scenario (not a forecast), a mapped zone, a forecast, or an index (a rank from a statistical model)',
    proxy: 'Proxy: an indirect indicator, such as reports people filed with 311; not a measurement of flooding'
  };

  let { tier, size = 12, color = 'currentColor', title = TIER_DESC[tier] }: Props = $props();

  // Per-instance pattern ids: a shared id resolves to the first pattern in
  // the document, which may carry another colour or sit in a hidden subtree.
  const uid = $props.id();
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
    <rect x="0" y="0" width={size} height={size} fill={color} />
  {:else if tier === 'modeled'}
    <defs>
      <pattern id={patternId} width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="3" stroke={color} stroke-width="1.5" />
      </pattern>
    </defs>
    <rect
      x={stroke / 2} y={stroke / 2}
      width={size - stroke} height={size - stroke}
      fill="url(#{patternId})" stroke={color} stroke-width={stroke}
    />
  {:else}
    <rect
      x={stroke / 2} y={stroke / 2}
      width={size - stroke} height={size - stroke}
      fill="none" stroke={color} stroke-width={stroke}
    />
  {/if}
</svg>
