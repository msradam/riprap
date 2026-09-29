<script lang="ts">
  import type { Card } from '$lib/types/card';
  let { card }: { card: Card } = $props();
</script>

<div class="body body-meta">
  <dl class="meta-list">
    {#each card.metaRows ?? [] as r, i (i)}
      <div class="meta-row">
        <dt>{r.k}</dt>
        <dd>{r.v}</dd>
      </div>
    {/each}
  </dl>
  {#if card.models?.length}
    <div class="models">
      <div class="models-head">Models in this briefing</div>
      <ul class="models-list">
        {#each card.models as m, i (i)}
          <li class="model">
            <span class="model-name">{m.name}</span>
            {#if m.href}
              <a class="model-repo" href={m.href} target="_blank" rel="noopener noreferrer">{m.repo}</a>
            {:else}
              <span class="model-repo">{m.repo}</span>
            {/if}
            <span class="model-meta">{m.where} · {m.how}{#if m.latency} · {m.latency}{/if}</span>
            {#if m.detail}<span class="model-detail">{m.detail}</span>{/if}
          </li>
        {/each}
      </ul>
    </div>
  {/if}
  {#if card.sub}<div class="body-sub">{card.sub}</div>{/if}
</div>

<style>
  .body-meta { padding: var(--s-2) var(--s-4) var(--s-3); }
  :global(.fc.is-compact) .body-meta { padding: var(--s-2) var(--s-3); }
  .meta-list {
    margin: 0;
    display: grid;
    grid-template-columns: 1fr;
    gap: 4px;
  }
  .meta-row {
    display: grid;
    grid-template-columns: minmax(110px, max-content) 1fr;
    gap: var(--s-3);
    padding: 3px 0;
    border-bottom: 1px solid var(--rule-soft);
    align-items: baseline;
  }
  .meta-row:last-child { border-bottom: 0; }
  dt {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    text-transform: lowercase;
    letter-spacing: 0.04em;
  }
  dd {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--ink);
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .models { margin-top: var(--s-2); }
  .models-head {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    text-transform: lowercase;
    letter-spacing: 0.04em;
  }
  .models-list { list-style: none; margin: 4px 0 0; padding: 0; }
  .model {
    display: flex;
    flex-direction: column;
    gap: 1px;
    padding: 3px 0;
    border-bottom: 1px solid var(--rule-soft);
  }
  .model:last-child { border-bottom: 0; }
  .model-name { font-family: var(--font-sans); font-size: 12px; color: var(--ink); }
  .model > * { min-width: 0; overflow-wrap: anywhere; }
  .model-repo {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink);
  }
  .model-meta, .model-detail {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
  }
  .model-detail { font-size: 10px; line-height: 1.4; }
  .body-sub {
    margin-top: var(--s-2);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-tertiary);
    line-height: 1.5;
  }
</style>
