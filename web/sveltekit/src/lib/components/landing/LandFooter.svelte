<script lang="ts">
  /** Landing-page footer. Tier legend + a build line. The in-app
   *  AppFooter has more detail; this one is intentionally tighter so
   *  the landing page closes cleanly.
   *
   *  Tier icons are EvidenceMark — was a third, bespoke swatch
   *  implementation (.lm-sw-*, hand-rolled circle/dash/stripe CSS,
   *  including a raw #6B6B6B hex) independent of both TierGlyph
   *  (app-wide) and EvidenceMark (report content), so this legend's
   *  proxy dot didn't match either the report body's or the map
   *  legend's proxy mark. One mark family now. */
  import EvidenceMark from '$lib/components/glyphs/EvidenceMark.svelte';
  import type { Tier } from '$lib/types/tier';

  const TIERS: Tier[] = ['empirical', 'modeled', 'proxy', 'synthetic'];
</script>

<footer class="land-footer">
  <span class="land-footer-tiers">
    {#each TIERS as tier (tier)}
      <span class="land-footer-tier"><EvidenceMark {tier} size={9} />{tier}</span>
    {/each}
  </span>
  <span class="land-footer-build">Riprap v0.4.6 · NYC OpenData · FEMA NFHL · USGS · NPCC4 · Dam mark by Chintuza, Noun Project (CC-BY)</span>
</footer>

<style>
  .land-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    padding: 16px 32px;
    border-top: 1px solid var(--rule-soft);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    letter-spacing: 0.02em;
  }
  .land-footer-tiers {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  .land-footer-tier {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    text-transform: capitalize;
  }
</style>
