<!--
  Placeholder while the evidence is gathered after the place resolved:
  the shape of the report that will replace it (the lead, the answer
  lines, the source notes beside them, then the evidence rows). The
  status line above it carries the words, so this is hidden from
  assistive technology.
-->
<div class="skeleton-brief" aria-hidden="true">
  <div class="sk-answer">
    <span class="sk sk-lead"></span>
    <span class="sk" style:width="94%"></span>
    <span class="sk" style:width="88%"></span>
    <span class="sk" style:width="62%"></span>
  </div>
  <div class="sk-rail">
    {#each [70, 84, 58] as w (w)}
      <span class="sk sk-small" style:width="{w}%"></span>
      <span class="sk sk-small" style:width="{w - 22}%"></span>
    {/each}
  </div>
  <div class="sk-rows">
    {#each [92, 80, 86, 74] as w (w)}
      <span class="sk sk-small" style:width="{w}%"></span>
    {/each}
  </div>
</div>

<style>
  .skeleton-brief {
    display: grid;
    grid-template-columns: minmax(0, 680px) 280px;
    column-gap: 56px;
    row-gap: 40px;
    margin-top: 24px;
  }
  .sk-answer,
  .sk-rail,
  .sk-rows {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .sk-rail {
    gap: 6px;
    padding-top: 10px;
  }
  .sk-rows {
    grid-column: 1 / -1;
    gap: 20px;
  }
  .sk {
    display: block;
    height: 16px;
    background: var(--paper-deep);
    animation: sk-fade 1.6s ease-in-out infinite;
  }
  .sk-lead {
    width: 3.2em;
    height: 56px;
    margin-bottom: 8px;
    font-size: 44px;
  }
  .sk-small {
    height: 12px;
  }
  .sk-rail .sk-small:nth-child(2n) {
    margin-bottom: 10px;
  }
  @keyframes sk-fade {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.55; }
  }
  @media (prefers-reduced-motion: reduce) {
    .sk { animation: none; }
  }
  @media (max-width: 1099px) {
    .skeleton-brief {
      grid-template-columns: minmax(0, 1fr);
      max-width: 680px;
      row-gap: 24px;
    }
  }
</style>
