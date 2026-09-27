<script lang="ts">
  import type { Citation } from '$lib/types/claim';
  import { citations } from '$lib/stores/citations.svelte';

  interface Props { c: Citation; }
  let { c }: Props = $props();

  function activate(e: MouseEvent) {
    e.preventDefault();
    citations.active = c.id;
    const el = document.getElementById(`cite-${c.id}`);
    if (!el) return;
    // Focus the entry (tabindex -1) so the next Tab reaches its source
    // link. preventScroll stops the focus jump; one instant scroll then
    // brings the entry into view (a smooth scroll would run far past the
    // 150 ms motion budget).
    el.focus({ preventScroll: true });
    el.scrollIntoView({ block: 'nearest' });
  }
</script>

<a
  href="#cite-{c.id}"
  class="inline-cite"
  data-cite={c.id}
  onclick={activate}
  aria-label="Citation {c.n}: {c.source}, {c.title}"
><sup>[{c.n}]</sup></a>
