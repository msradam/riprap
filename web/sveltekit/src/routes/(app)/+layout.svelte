<script lang="ts">
  // Briefing, gallery and print styles. Kept out of the root layout so the
  // landing does not download them as render-blocking CSS.
  import '$lib/styles.css';
  import '$lib/print.css';
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();
</script>

{@render children()}
