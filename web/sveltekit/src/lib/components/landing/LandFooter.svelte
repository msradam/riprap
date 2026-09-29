<script lang="ts">
  /** Landing footer: the beta status, the standards Riprap is built to
   *  (commitments, not certification), and the build and credit line. */
  import { APP_VERSION } from '$lib/version';

  const FEEDBACK = 'https://github.com/msradam/riprap-nyc/issues/new/choose';
</script>

<footer class="land-footer">
  <div class="land-footer-inner">
    <p>
      This is open beta. Methodology and source attribution are stable. Per-city coverage is
      expanding. <a href={FEEDBACK} target="_blank" rel="noopener">Send feedback</a>.
    </p>
    <p>
      Built to USWDS, WCAG 2.2 AA, Section 508 and the Plain Writing Act. Open source under
      Apache-2.0.
    </p>
    <p class="land-footer-build">
      Riprap <span class="mono">v{APP_VERSION}</span>. Data from NYC OpenData, FEMA NFHL, USGS and
      NPCC4. Dam mark by Chintuza, Noun Project (CC-BY).
    </p>
  </div>
</footer>

<style>
  .land-footer {
    margin-top: 96px;
    border-top: 1px solid var(--rule-soft);
    background: var(--paper-deep);
  }
  .land-footer-inner {
    max-width: 1040px;
    margin: 0 auto;
    padding: 24px 32px 48px;
  }
  p {
    margin: 0 0 8px;
    max-width: 54ch;
    font-size: 14px;
    line-height: 1.5;
    color: var(--ink-secondary);
  }
  a {
    display: inline-block;
    min-height: 24px;
    color: var(--riprap-text-link);
    text-underline-offset: 0.2em;
  }
  a:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  .mono {
    font-family: var(--font-mono);
    font-size: 13px;
  }
  @media (max-width: 640px) {
    .land-footer {
      margin-top: 48px;
    }
    .land-footer-inner {
      padding: 20px 16px 32px;
    }
  }
</style>
