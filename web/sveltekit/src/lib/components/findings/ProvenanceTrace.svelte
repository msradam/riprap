<script lang="ts">
  import type { StoneMember } from '$lib/types/card';
  import EvidenceMark from '$lib/components/glyphs/EvidenceMark.svelte';

  /** A Stone's specialists, one row each: status pip, mono id, name, note. */
  let { members }: { members: StoneMember[] } = $props();

  /** v0.4.5 status pip, one shape per status (V0.4.5_SPEC.md §1).
   *
   *    fired             ● solid square (tier-colored)
   *    silent_by_design  ○ open circle (neutral)
   *    errored           ■ solid filled (red)
   *    not_invoked       □ hollow gray square
   */
  function pip(status: StoneMember['status']): string {
    return ({
      fired: '●',
      silent_by_design: '○',
      errored: '■',
      not_invoked: '□',
    } as const)[status];
  }
  function pipColorVar(m: StoneMember): string {
    if (m.status === 'errored') return 'var(--accent-alert)';
    if (m.status === 'silent_by_design') return 'var(--ink-tertiary)';
    if (m.status === 'not_invoked') return 'var(--ink-tertiary)';
    if (m.tier) return `var(--tier-${m.tier})`;
    return 'var(--ink)';
  }
</script>

<ul class="prov-tree">
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
  {/each}
</ul>

<style>
  .prov-tree {
    list-style: none;
    margin: 0;
    padding: 0;
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
  .prov-status-errored .prov-name { color: var(--accent-alert); }
</style>
