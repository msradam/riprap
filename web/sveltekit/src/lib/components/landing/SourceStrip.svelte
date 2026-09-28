<script lang="ts">
  /** SourceStrip: trust-signal numbers.
   *
   *  Surfaces the data-source counts inline (31 sources · 1 production
   *  city · 5 experimental) so the "every claim cites a public record"
   *  promise from the deck is visually substantiated. The date is the
   *  last git change to docs/METHODOLOGY.md; update it when that file
   *  changes.
   *
   *  The numbers are defaults, checked against the manifests on
   *  2026-09-28 (31 pebbles: 27 NYC manifests plus 4 federal). They are
   *  props so a different deployment (or an automated pre-build pass
   *  scanning manifests) can drive them dynamically.
   */
  interface Props {
    sources?: number;
    productionCities?: number;
    experimentalCities?: number;
    lastReview?: string;
  }
  let {
    sources = 31,
    productionCities = 1,
    experimentalCities = 5,
    lastReview = '2026-09-26',
  }: Props = $props();
</script>

<div class="source-strip" id="sources" role="region" aria-label="Source counts">
  <span class="source-strip-stat">
    <span class="source-strip-stat-num">{sources}</span>data sources
  </span>
  <span class="source-strip-stat">
    <span class="source-strip-stat-num">{productionCities}</span>city in production
  </span>
  <span class="source-strip-stat">
    <span class="source-strip-stat-num">{experimentalCities}</span>experimental cities
  </span>
  <span class="source-strip-meta">methodology updated · {lastReview}</span>
</div>

<style>
  .source-strip {
    display: flex;
    align-items: baseline;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px dashed var(--rule-soft);
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-tertiary);
    letter-spacing: 0.04em;
  }
  .source-strip-stat {
    font-family: var(--font-sans);
    color: var(--ink);
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0;
  }
  .source-strip-stat-num {
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--accent);
    margin-right: 4px;
  }
  .source-strip-meta { margin-left: auto; }
</style>
