<script lang="ts">
  import type { Card } from '$lib/types/card';
  let { card }: { card: Card } = $props();
</script>

<div class="body body-scalars">
  <div class="row">
    {#each card.scalars ?? [] as s (s.label)}
      <div class="cell">
        <div class="value" style="color: var(--tier-{card.tier});">{s.value}</div>
        <div class="label">{s.label}</div>
      </div>
    {/each}
  </div>
  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-scalars { padding: var(--s-3) var(--s-4) var(--s-3); }
  :global(.fc.is-compact) .body-scalars { padding: var(--s-2) var(--s-3); }
  .row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
    gap: var(--s-3);
  }
  .cell { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .value {
    font-family: var(--font-serif);
    font-style: italic;
    font-size: 22px;
    font-weight: 500;
    line-height: 1.1;
  }
  .label {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-tertiary);
    letter-spacing: 0.02em;
    /* Readable labels with units ("Temperature (°C)"): no forced
       lowercase, and words break only when one cannot fit. */
    overflow-wrap: break-word;
  }
  .body-sub {
    margin-top: var(--s-3);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
