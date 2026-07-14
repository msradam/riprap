<script lang="ts">
  /**
   * v0.4.2 §15 — Register card for the four register specialists
   * (subway entrances, NYCHA developments, schools, hospitals).
   *
   * Headline = numeric count + asset type + radius.
   * Body = 3–5 row table with per-row joined metadata.
   * Row glyph = AssetPin + most-empirical TierGlyph stacked.
   * Tap row to expand a per-field provenance grid.
   */
  import type { RegisterData } from '$lib/types/states';
  import TierBadge from '$lib/components/glyphs/TierBadge.svelte';
  import AssetPin from '$lib/components/glyphs/AssetPin.svelte';
  import EvidenceMark from '$lib/components/glyphs/EvidenceMark.svelte';

  interface Props { data: RegisterData; }
  let { data }: Props = $props();

  let openRow = $state<number | null>(null);

  function toggle(i: number) {
    openRow = openRow === i ? null : i;
  }
</script>

<article class="register-card" aria-label="{data.type} register">
  <header class="register-card-head">
    <div class="register-card-source">
      <EvidenceMark tier="empirical" size={11} />
      <span class="register-card-source-label">{data.sourceLabel ?? 'MTA · USGS · FEMA · NYC OEM · NYC DEP'}</span>
    </div>
    <span class="register-card-vintage">v. {data.vintage ?? '2026-04'} · joined</span>
  </header>
  <h4 class="register-card-title">
    <span class="register-card-count">{data.count}</span>
    <span class="register-card-type">{data.type} within {data.radius}</span>
  </h4>
  <table class="register-table">
    <caption class="visually-hidden">
      {data.count} {data.type} within {data.radius}, joined against FEMA, Sandy 2012, and DEP-modeled flood exposure
    </caption>
    <thead>
      <tr>
        <th scope="col"><span class="visually-hidden">evidence tier</span></th>
        <th scope="col">asset</th><th scope="col">elev.</th><th scope="col">ADA</th>
        <th scope="col">FEMA</th><th scope="col">Sandy 2012</th><th scope="col">DEP modeled</th>
      </tr>
    </thead>
    <tbody>
      {#each data.rows as r, i (i)}
        <tr
          class="register-row"
          class:is-open={openRow === i}
          onclick={() => toggle(i)}
        >
          <td class="register-row-glyph">
            <AssetPin kind={r.asset} size={10} />
            <EvidenceMark tier={r.primaryTier} size={9} />
          </td>
          <td class="register-row-name">{r.name}</td>
          <td class="register-num">{r.elev}</td>
          <td class={r.ada ? 'register-yes' : 'register-no'}>{r.ada ? '✓' : '—'}</td>
          <td>{r.fema}</td>
          <td>{r.sandy}</td>
          <td>{r.dep}</td>
        </tr>
        {#if openRow === i}
          <tr class="register-detail">
            <td colspan="7">
              <div class="register-detail-grid">
                <div><span class="section-label">Position</span><p>Empirical · MTA station entrance dataset, lat/lon survey-grade</p></div>
                <div><span class="section-label">Elevation</span><p>Modeled · NYC DEM 1 ft · joined at entrance centroid</p></div>
                <div><span class="section-label">Sandy 2012</span><p>Empirical · NYC OEM Sandy Inundation Zone, polygon test</p></div>
                <div><span class="section-label">DEP scenario</span><p>Modeled · Stormwater Flood Map moderate (2.13 in/hr)</p></div>
              </div>
            </td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
  <footer class="register-card-foot">
    <span class="register-foot-note">
      Row glyph reflects most-empirical tier across joined fields. Tap row for per-field provenance.
    </span>
    <TierBadge tier="empirical" compact />
  </footer>
</article>
