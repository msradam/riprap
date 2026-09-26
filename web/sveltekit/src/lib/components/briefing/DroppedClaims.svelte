<script lang="ts">
  import type { DroppedClaim } from '$lib/client/agentStream';

  /** Claims the model wrote that failed verification against their cited
   *  sources. They are not part of the briefing; listed here, collapsed,
   *  so a reader can see what was removed and why. */
  interface Props { claims?: DroppedClaim[] }
  let { claims = [] }: Props = $props();
</script>

{#if claims.length}
  <details class="dropped-claims">
    <summary>Dropped claims ({claims.length}): written by the model but failed verification, not part of the briefing</summary>
    <ul class="dropped-list">
      {#each claims as c, i (i)}
        <li class="dropped-item">
          <p class="dropped-text">{#if c.place}<span class="dropped-place">{c.place}:</span> {/if}{c.text}</p>
          <p class="dropped-reason">Reason: {c.reason}</p>
        </li>
      {/each}
    </ul>
  </details>
{/if}

<style>
  .dropped-claims {
    border: 1px solid var(--rule-soft);
    background: var(--paper-deep);
    margin: 16px 0;
  }
  .dropped-claims summary {
    padding: 10px 14px;
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink-secondary);
  }
  .dropped-list {
    list-style: none;
    margin: 0;
    padding: 0 14px 12px;
  }
  .dropped-item {
    padding: 8px 0;
    border-top: 1px solid var(--rule-soft);
  }
  .dropped-text {
    margin: 0;
    font-size: 13px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .dropped-place { font-weight: 600; }
  .dropped-reason {
    margin: 4px 0 0;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
  }
</style>
