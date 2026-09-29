<script lang="ts">
  import type { Component, ComponentProps } from 'svelte';
  import type RipMapComponent from './RipMap.svelte';

  /** Holds the map's place with a same-size frame and loads MapLibre and
   *  deck.gl (about 1.6 MB of script) only once `ready` is true (the live
   *  route passes false until the briefing text has rendered) and the
   *  frame comes within 200px of the viewport. `address` may be missing
   *  while the place is still being geocoded; the frame still reserves the
   *  space so nothing below it moves when the map arrives. */
  type MapProps = ComponentProps<typeof RipMapComponent>;
  type Props = Omit<MapProps, 'address'> & {
    address?: MapProps['address'] | null;
    ready?: boolean;
  };

  let { address, ready = true, ...rest }: Props = $props();

  let RipMap = $state.raw<Component<MapProps> | null>(null);
  let failed = $state(false);

  function loadWhenNear(node: HTMLElement) {
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        import('./RipMap.svelte').then(
          (m) => (RipMap = m.default),
          () => (failed = true)
        );
      },
      { rootMargin: '200px 0px' }
    );
    io.observe(node);
    return () => io.disconnect();
  }
</script>

{#if RipMap && address}
  <RipMap {address} {...rest} />
{:else}
  <div class="map-frame map-placeholder" {@attach ready && loadWhenNear}>
    <p>{failed ? 'The map could not load.' : 'Loading map…'}</p>
  </div>
{/if}

<style>
  .map-placeholder {
    display: grid;
    place-items: center;
    aspect-ratio: 8 / 5.6;
  }
  .map-placeholder p {
    margin: 0;
    font-size: 14px;
    color: var(--ink-secondary);
  }
</style>
