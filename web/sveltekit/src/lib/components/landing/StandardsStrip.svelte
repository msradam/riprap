<script lang="ts">
  /** StandardsStrip: the standards the design and implementation are
   *  built to. Worded as commitments, not certification: no check marks,
   *  and a heading that says so. Drop entries that no longer hold; don't
   *  add ones the implementation can't substantiate. */
  const STANDARDS = ['USWDS', 'WCAG 2.2 AA', 'Section 508', 'Plain Writing Act'];
</script>

<section class="standards-strip" aria-labelledby="standards-head">
  <h2 class="standards-head" id="standards-head">Standards we build to</h2>
  <ul class="standards-list">
    {#each STANDARDS as s (s)}
      <li class="badge"><strong>{s}</strong></li>
    {/each}
    <li class="badge"><strong>Open source</strong>&nbsp;· Apache-2.0</li>
  </ul>
</section>

<style>
  .standards-strip {
    margin-top: 28px;
    padding-top: 18px;
    border-top: 1px solid var(--rule-soft);
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.04em;
    color: var(--ink-tertiary);
  }
  .standards-head {
    margin: 0 0 8px;
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-secondary);
  }
  .standards-list {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 14px 4px 0;
    margin-right: 14px;
    border-right: 1px solid var(--rule-soft);
    color: var(--ink-secondary);
  }
  .badge:last-child {
    border-right: none;
    margin-right: 0;
  }
  .badge strong {
    color: var(--ink);
    font-family: var(--font-sans);
    font-weight: 600;
    letter-spacing: 0.02em;
  }
</style>
