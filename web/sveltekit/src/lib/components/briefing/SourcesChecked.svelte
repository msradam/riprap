<script lang="ts">
  import type { sourceLists } from '$lib/stores/briefingState.svelte';

  /** What was checked: sources consulted (failures flagged), sources that
   *  ran but returned no data, and sources not checked for the question. */
  interface Props {
    lists: ReturnType<typeof sourceLists>;
  }
  let { lists }: Props = $props();

  /** Lists at or under this length open by default. */
  const SHORT_LIST = 8;
  let failedCount = $derived(lists.consulted?.filter((r) => r.failed).length ?? 0);
</script>

<div class="sources-checked" role="group" aria-label="Sources consulted, sources with no data, and sources not checked">
  {#if lists.consulted}
    <details open={lists.consulted.length <= SHORT_LIST}>
      <summary>
        <!-- Older snapshots carry no consulted list, only the failed steps. -->
        {lists.hasConsultedList ? 'Sources consulted' : 'Sources that failed to respond'} ({lists.consulted.length}){#if lists.hasConsultedList && failedCount}, {failedCount} failed to respond{/if}
      </summary>
      <ul>
        {#each lists.consulted as s (s.id)}
          <li>{s.title}{#if s.failed}<strong>: failed to respond</strong>{/if}</li>
        {/each}
      </ul>
    </details>
  {/if}
  {#if lists.noData.length}
    <details open={lists.noData.length <= SHORT_LIST}>
      <summary>Ran but returned no data ({lists.noData.length})</summary>
      <ul>
        {#each lists.noData as t, i (`${i}-${t}`)}
          <li>{t}</li>
        {/each}
      </ul>
    </details>
  {/if}
  {#if lists.notChecked?.length}
    <details id="not-checked" open={lists.notChecked.length <= SHORT_LIST}>
      <summary>Not checked for this question ({lists.notChecked.length})</summary>
      <ul>
        {#each lists.notChecked as t, i (`${i}-${t}`)}
          <li>{t}</li>
        {/each}
      </ul>
    </details>
  {:else if lists.notChecked}
    <p>
      <strong>Not checked for this question:</strong> none of the sources for this kind of place were skipped.
    </p>
  {/if}
</div>

<style>
  .sources-checked {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr));
    gap: 8px 32px;
    align-items: start;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  details,
  p {
    margin: 0;
    min-width: 0;
  }
  /* The evidence table's footer links here; clear the sticky header. */
  details {
    scroll-margin-top: var(--scroll-offset, 72px);
  }
  summary {
    min-height: 24px;
    cursor: pointer;
    font-weight: 600;
    color: var(--ink);
  }
  ul {
    margin: 4px 0 0;
    padding-left: 18px;
  }
  li + li {
    margin-top: 2px;
  }
  strong {
    font-weight: 600;
    color: var(--ink);
  }
</style>
