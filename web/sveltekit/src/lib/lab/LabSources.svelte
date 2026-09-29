<script lang="ts">
  import type { sourceLists } from '$lib/stores/briefingState.svelte';

  /** ResultsView's sources disclosure, same wording, unstyled. */
  interface Props {
    lists: ReturnType<typeof sourceLists>;
    class?: string;
  }
  let { lists, class: className }: Props = $props();

  /** Lists at or under this length open by default. */
  const SHORT_LIST = 8;
  let failedCount = $derived(lists.consulted?.filter((r) => r.failed).length ?? 0);
</script>

<section class={['lab-sources', className]} aria-label="Sources consulted, sources with no data, and sources not checked">
  {#if lists.consulted}
    <details open={lists.consulted.length <= SHORT_LIST}>
      <summary>
        <!-- Older snapshots carry no consulted list, only the failed steps. -->
        {lists.hasConsultedList ? 'Sources consulted' : 'Sources that failed to respond'} ({lists.consulted.length}){#if lists.hasConsultedList && failedCount}, {failedCount} failed to respond{/if}
      </summary>
      <ul>
        {#each lists.consulted as s (s.id)}
          <li class:is-failed={s.failed}>{s.title}{#if s.failed}<strong>: failed to respond</strong>{/if}</li>
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
    <details open={lists.notChecked.length <= SHORT_LIST}>
      <summary>Not checked for this question ({lists.notChecked.length})</summary>
      <ul>
        {#each lists.notChecked as t, i (`${i}-${t}`)}
          <li>{t}</li>
        {/each}
      </ul>
    </details>
  {:else if lists.notChecked}
    <p class="lab-sources-none">
      <strong>Not checked for this question:</strong> none of the sources for this kind of place were skipped.
    </p>
  {/if}
</section>
