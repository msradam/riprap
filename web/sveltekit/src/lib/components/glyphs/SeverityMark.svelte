<script lang="ts">
  /**
   * docs/design/handoff/RIPRAP-MAPPING.md — severity axis, separate from
   * evidence tier: "how bad" vs "how directly known". A filled-step
   * triangle (deliberately a different shape + hue family from
   * EvidenceMark's square) so the two axes never collapse into one.
   *
   * app/score.py's `tier` field runs 1 (High exposure) .. 4 (Limited
   * exposure) — i.e. NUMERICALLY INVERTED from alarm level — while the
   * --riprap-sev-* token ramp goes gray(1) -> amber(2/3) -> red(4), i.e.
   * increasing alarm with increasing number. This component takes the
   * raw score.py tier and does the inversion (visualStep = 5 - scoreTier)
   * so callers just pass score.py's output through unchanged. tier 0
   * ("No flagged exposure") renders nothing.
   */
  interface Props {
    /** Raw app/score.py composite().tier: 0 (no exposure) .. 4 (limited) .. 1 (high). */
    scoreTier: 0 | 1 | 2 | 3 | 4;
    size?: number;
    title?: string;
  }

  let { scoreTier, size = 12, title }: Props = $props();

  let visualStep = $derived(scoreTier === 0 ? 0 : 5 - scoreTier);
  let colorVar = $derived(`var(--riprap-sev-${visualStep})`);
  let clipId = $derived(`rp-tri-${scoreTier}-${size}`);

  // Equilateral-ish triangle, apex up, inset half a stroke so the
  // outline doesn't clip at the viewBox edge.
  let inset = $derived(size * 0.06);
  let trianglePoints = $derived(
    `${size / 2},${inset} ${size - inset},${size - inset} ${inset},${size - inset}`
  );
  let stroke = $derived(Math.max(1, Math.round(size / 10)));
</script>

{#if visualStep > 0}
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
    <defs>
      <clipPath id={clipId}>
        <polygon points={trianglePoints} />
      </clipPath>
    </defs>
    <polygon points={trianglePoints} fill="none" stroke={colorVar} stroke-width={stroke} stroke-linejoin="round" />
    <g clip-path="url(#{clipId})">
      <rect
        x="0"
        y={size - (size * visualStep) / 4}
        width={size}
        height={size}
        fill={colorVar}
      />
    </g>
  </svg>
{/if}
