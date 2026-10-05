<script lang="ts">
  import type { BriefingModel } from '$lib/client/briefingModel';
  import type { StoneTrace } from '$lib/types/card';
  import { STONE_META } from '$lib/types/card';
  import ProvenanceTrace from '$lib/components/findings/ProvenanceTrace.svelte';

  /** How this briefing was made, recorded once at the end and closed by
   *  default: the checks, the mode line, the models, the snapshot, the run
   *  facts and the trace per Stone. */
  interface Props {
    model: BriefingModel;
    stones: StoneTrace[];
    open?: boolean;
  }
  let { model, stones, open = $bindable(false) }: Props = $props();
</script>

<details id="how-made" class="how-made" bind:open>
  <summary>How this briefing was made</summary>
  <div class="how-made-body">
    {#if model.checks}<p>{model.checks}</p>{/if}
    {#if model.modeLine}<p>{model.modeLine}</p>{/if}
    {#if model.generated}
      <p>
        Precomputed snapshot, generated <span class="data">{model.generated}</span> from Riprap commit
        <span class="data">{model.commit}</span>. Live readings (tides, alerts, sensors) are as of that time.{#if model.stamp}{` ${model.stamp}.`}{/if}
      </p>
    {/if}
    {#if model.modelLine}<p>Language model: <span class="data">{model.modelLine}</span>.</p>{/if}
    {#each model.runFacts as fact (fact)}
      <p>{fact}</p>
    {/each}

    {#if model.models.length}
      <h3>Models in this briefing</h3>
      <ul class="how-made-models">
        {#each model.models as m, i (i)}
          <li>
            <span class="how-made-model">{m.name}</span>,
            {#if m.href}<a class="data" href={m.href} target="_blank" rel="noopener noreferrer">{m.repo}</a>{:else}<span class="data">{m.repo}</span>{/if}.
            {m.where}; {m.how}{#if m.latency}, <span class="data">{m.latency}</span>{/if}.
          </li>
        {/each}
      </ul>
    {/if}

    {#if stones.some((s) => s.members.length)}
      <h3>What each source returned</h3>
      {#each stones.filter((s) => s.members.length) as s (s.key)}
        <details class="how-made-stone">
          <summary>{STONE_META[s.key].role} ({STONE_META[s.key].name}, {s.members.length} source function{s.members.length === 1 ? '' : 's'})</summary>
          <ProvenanceTrace members={s.members} />
        </details>
      {/each}
    {/if}
  </div>
</details>

<style>
  .how-made {
    margin-top: 24px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
    /* The briefing sets the offset per width; the phone header is taller. */
    scroll-margin-top: var(--scroll-offset, 80px);
  }
  summary {
    min-height: 24px;
    cursor: pointer;
    font-weight: 600;
    color: var(--ink);
  }
  .how-made-body {
    max-width: 54ch;
    padding: 8px 0 0 16px;
  }
  p {
    margin: 0 0 8px;
  }
  h3 {
    margin: 16px 0 4px;
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
  }
  .how-made-models {
    margin: 0;
    padding-left: 18px;
    overflow-wrap: anywhere;
  }
  .how-made-models li + li {
    margin-top: 4px;
  }
  .how-made-model {
    color: var(--ink);
  }
  .how-made-models a {
    color: var(--riprap-text-link);
  }
  .how-made-stone {
    margin-top: 4px;
  }
  .how-made-stone summary {
    font-weight: 400;
  }
</style>
