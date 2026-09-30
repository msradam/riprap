<script lang="ts">
  import type { StoneMember } from '$lib/types/card';
  import EvidenceMark from '$lib/components/glyphs/EvidenceMark.svelte';
  import Self from './ProvenanceTrace.svelte';

  /** Indented specialist tree. Each row: status pip, mono id, name, note.
   *  Recursive via self-import (svelte:self is deprecated in Svelte 5). */
  let { members, depth = 0 }: { members: StoneMember[]; depth?: number } = $props();

  /** v0.4.5 status pip — five distinct shapes per V0.4.5_SPEC.md §1.
   *
   *    fired             ● solid square (tier-colored)
   *    silent_by_design  ○ open circle (neutral)
   *    warned            ▲ solid triangle (warn ochre)
   *    errored           ■ solid filled (red)
   *    not_invoked       □ hollow gray square
   */
  function pip(status: StoneMember['status']): string {
    return ({
      fired: '●',
      silent_by_design: '○',
      warned: '▲',
      errored: '■',
      not_invoked: '□',
    } as const)[status];
  }
  function pipColorVar(m: StoneMember): string {
    if (m.status === 'warned') return 'var(--accent-warn)';
    if (m.status === 'errored') return 'var(--accent-alert)';
    if (m.status === 'silent_by_design') return 'var(--ink-tertiary)';
    if (m.status === 'not_invoked') return 'var(--ink-tertiary)';
    if (m.tier) return `var(--tier-${m.tier})`;
    return 'var(--ink)';
  }
</script>

<ul class="prov-tree" style="--depth: {depth};">
  {#each members as m (m.id)}
    <li class="prov-row prov-status-{m.status}">
      <span class="prov-pip" style="color: {pipColorVar(m)};" aria-hidden="true">{pip(m.status)}</span>
      <span class="prov-id">{m.id}</span>
      {#if m.tier}
        <span class="prov-tier">
          <EvidenceMark tier={m.tier} size={9} color={`var(--tier-${m.tier})`} />
        </span>
      {/if}
      <span class="prov-name">{m.name}</span>
      {#if m.note}<span class="prov-note">{m.note}</span>{/if}
      {#if m.ms != null}<span class="prov-ms">{m.ms < 1000 ? `${m.ms}ms` : `${(m.ms / 1000).toFixed(1)}s`}</span>{/if}
    </li>
    {#if m.children?.length}
      <li class="prov-children">
        <Self members={m.children} depth={depth + 1} />
      </li>
    {/if}
  {/each}
</ul>

<style>
  .prov-tree {
    list-style: none;
    margin: 0;
    padding: 0;
    padding-left: calc(var(--depth, 0) * 16px);
  }
  .prov-row {
    /* Flex, not a fixed grid: rows carry four to six cells (tier and note
       are optional). */
    display: flex;
    flex-wrap: wrap;
    overflow-wrap: anywhere;
    column-gap: var(--s-2);
    row-gap: 2px;
    align-items: baseline;
    padding: 3px 0;
    font-size: 14px;
    line-height: 1.45;
  }
  .prov-row > * { min-width: 0; }
  .prov-pip {
    flex: 0 0 14px;
    text-align: center;
    font-size: 14px;
    line-height: 1;
  }
  .prov-id,
  .prov-ms {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .prov-tier {
    display: inline-flex;
    align-items: center;
  }
  .prov-name {
    color: var(--ink);
  }
  .prov-note {
    color: var(--ink-secondary);
  }
  .prov-ms {
    margin-left: auto;
  }
  .prov-status-silent_by_design .prov-name,
  .prov-status-not_invoked .prov-name {
    color: var(--ink-secondary);
  }
  .prov-status-warned .prov-name { color: var(--accent-warn); }
  .prov-status-errored .prov-name { color: var(--accent-alert); }
  .prov-children { padding: 0; }
</style>
