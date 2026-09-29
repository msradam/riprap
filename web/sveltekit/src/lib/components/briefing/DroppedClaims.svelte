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
    margin: 12px 0 0;
    max-width: 54ch;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .dropped-claims summary {
    min-height: 24px;
    cursor: pointer;
    font-weight: 600;
    color: var(--ink);
  }
  .dropped-list {
    list-style: none;
    margin: 0;
    padding: 0 0 0 16px;
  }
  .dropped-item {
    padding: 8px 0;
  }
  .dropped-text,
  .dropped-reason {
    margin: 0;
  }
  .dropped-place { font-weight: 600; }
</style>
