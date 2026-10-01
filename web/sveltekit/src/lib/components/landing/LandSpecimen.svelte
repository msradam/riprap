<script lang="ts">
  import { MediaQuery } from 'svelte/reactivity';
  import { asset, resolve } from '$app/paths';

  /** A real gallery briefing beside the headline, as a short loop: the
   *  question is typed into a picture of the search box, the search is
   *  sent, and the briefing's screenshot fades in and scrolls. The image
   *  comes from scripts/capture-hero-preview.mjs; the question comes from
   *  the snapshot at build time. */
  export interface Specimen {
    slug: string;
    question: string;
  }
  let { specimen }: { specimen: Specimen } = $props();

  let href = $derived(`${resolve('/(app)/gallery/[slug]', { slug: specimen.slug })}/`);

  // One clock drives the loop: `t` is the unpaused time in ms since the
  // loop began, and the frame below is a pure function of it. The server
  // render is t = 0: an empty box and plain paper. Reduced motion shows
  // the whole picture at once, still.
  const START = 600;
  const HOLD = 500;
  const PRESS = 250;
  // Matches the 13.5s of specimen-scroll below.
  const SCROLL = 13500;
  const FADE = 400;

  // No matchMedia on the server or in some test DOMs: then it is motion.
  const reduce = 'matchMedia' in globalThis ? new MediaQuery('prefers-reduced-motion: reduce') : undefined;
  let t = $state(0);
  let hovered = $state(false);
  let focused = $state(false);
  let paused = $derived(hovered || focused);

  let marks = $derived.by(() => {
    const keys: number[] = [];
    let at = START;
    for (let i = 1; i <= specimen.question.length; i++) {
      keys.push(at);
      // 35 to 70ms a key, varied by position so it reads as a person.
      at += 35 + ((i * 47) % 36);
    }
    const press = at + HOLD;
    const show = press + PRESS;
    const out = show + SCROLL;
    return { keys, press, show, out, end: out + FADE };
  });
  let still = $derived(reduce?.current ?? false);
  let typed = $derived(still ? specimen.question.length : marks.keys.filter((k) => k <= t).length);
  let phase = $derived(
    still ? 'still' : t < marks.press ? 'type' : t < marks.show ? 'press' : t < marks.out ? 'show' : 'out'
  );
  let sent = $derived(phase === 'show' || phase === 'out' || phase === 'still');

  $effect(() => {
    if (still) return;
    let last = performance.now();
    let frame = requestAnimationFrame(function tick(now) {
      // Capped, so a tab in the background does not skip the loop ahead.
      if (!paused) t = (t + Math.min(now - last, 100)) % marks.end;
      last = now;
      frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  });
</script>

<figure class="specimen">
  <a
    class="window"
    class:paused
    {href}
    onpointerenter={() => (hovered = true)}
    onpointerleave={() => (hovered = false)}
    onfocusin={() => (focused = true)}
    onfocusout={() => (focused = false)}
  >
    <span class="visually-hidden">{specimen.question}</span>
    <span class="window-bar" aria-hidden="true">{sent ? `riprap / gallery / ${specimen.slug}` : 'riprap'}</span>
    <!-- A picture of the hero's search row: spans only, nothing focusable. -->
    <span class="search" class:still={phase === 'still'} aria-hidden="true">
      <span class="box">
        <span class="line">
          <span class="typed">{specimen.question.slice(0, typed)}</span>
          <span class="caret" class:solid={typed > 0} class:gone={sent}></span>
          <span class="spacer"></span>
        </span>
      </span>
      <span class="go" class:pressed={phase === 'press'}>Get the briefing</span>
    </span>
    <span class="window-view">
      <!-- The size matches CLIP in scripts/capture-hero-preview.mjs (the 1x file). The window spans the frame below 1100px and is about 455px wide above. -->
      <img
        class:on={phase === 'show' || phase === 'still'}
        class:scroll={phase === 'show' || phase === 'out'}
        src={asset('/landing/hero-briefing.webp')}
        srcset="{asset('/landing/hero-briefing-712.webp')} 712w, {asset('/landing/hero-briefing.webp')} 1424w"
        sizes="(max-width: 640px) calc(100vw - 32px), (max-width: 1099px) calc(100vw - 64px), 455px"
        width="712"
        height="1400"
        decoding="async"
        alt="The Riprap briefing for this question: the answer Yes. over its cited sentences on FloodNet sensor events, Hurricane Ida high-water marks and 311 flood complaints, then a map of those points around the address."
      />
    </span>
  </a>
  <figcaption class="specimen-caption">
    <a class="land-link" {href}>Read the full briefing</a>
  </figcaption>
</figure>

<style>
  .specimen {
    margin: 0;
  }
  .window {
    display: block;
    border: 1px solid var(--rule-soft);
    background: var(--riprap-white);
    color: var(--ink-secondary);
    text-decoration: none;
  }
  .window:focus-visible {
    outline-offset: 3px;
  }
  .window-bar {
    display: block;
    padding: 6px 12px;
    border-bottom: 1px solid var(--rule-soft);
    background: var(--paper-deep);
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* The hero's input and button at about two thirds of their size. */
  .search {
    display: flex;
    gap: 6px;
    padding: 12px;
    border-bottom: 1px solid var(--rule-soft);
  }
  /* Width 0 and flex 1: the long line must not widen the window, which
     on a phone sits in a flex column that would grow to fit it. */
  .box {
    flex: 1;
    width: 0;
    display: flex;
    height: 40px;
    border: 1px solid var(--ink-secondary);
    background: var(--riprap-white);
    color: var(--ink);
    font-size: 15px;
  }
  /* One line, like a real input: once the text is wider than the box the
     spacer shrinks to nothing and flex-end keeps the caret in view, so the
     start of the question slides out to the left under a short fade. The
     fade is on this inner line so the border stays whole. */
  .line {
    flex: 1;
    min-width: 0;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    padding: 0 10px;
    white-space: nowrap;
    overflow: hidden;
    mask-image: linear-gradient(to right, transparent, #000 10px);
  }
  .typed,
  .caret {
    flex: none;
  }
  .spacer {
    flex: 1 1 auto;
  }
  .caret {
    width: 1.5px;
    height: 1.15em;
    margin-left: 1px;
    background: var(--ink);
    animation: caret-blink 1.06s steps(1) infinite;
  }
  /* A caret holds still while keys are going in. */
  .caret.solid {
    animation: none;
  }
  .caret.gone {
    display: none;
  }
  @keyframes caret-blink {
    50% {
      opacity: 0;
    }
  }
  /* Reduced motion: the whole question, wrapped, with nothing clipped. */
  .search.still .box {
    height: auto;
    min-height: 40px;
  }
  .search.still .line {
    padding-block: 8px;
    justify-content: flex-start;
    white-space: normal;
    mask-image: none;
  }
  .search.still .typed {
    flex: 1 1 auto;
    min-width: 0;
    line-height: 1.3;
  }
  .go {
    flex: none;
    display: inline-flex;
    align-items: center;
    height: 40px;
    padding: 0 14px;
    background: var(--ink);
    color: var(--paper);
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
    transition: background 0.1s;
  }
  .go.pressed {
    background: #000;
    text-decoration: underline;
    transform: translateY(1px);
  }

  /* A fixed shape, so the image cannot shift the layout as it loads.
     Size containment lets the scroll end be written as 100cqh. */
  .window-view {
    display: block;
    aspect-ratio: 4 / 5;
    /* Full width on a tablet: no taller than the desktop window. */
    max-height: 600px;
    overflow: hidden;
    container-type: size;
    background: var(--paper);
  }
  /* Hidden, not removed, so the image loads during the typing. */
  img {
    display: block;
    width: 100%;
    height: auto;
    opacity: 0;
    translate: 0 6px;
    transition:
      opacity 0.4s ease-out,
      translate 0.4s ease-out;
  }
  img.on {
    opacity: 1;
    translate: 0 0;
  }
  /* Holds 1.5s at the top, scrolls for 10s, holds 2s at the foot, and
     stays there while it fades out. */
  img.scroll {
    animation: specimen-scroll 13.5s ease-in-out forwards;
  }
  .window.paused img {
    animation-play-state: paused;
  }
  @keyframes specimen-scroll {
    0%,
    11.1% {
      transform: translateY(0);
    }
    85.2%,
    100% {
      transform: translateY(calc(100cqh - 100%));
    }
  }
  @media (prefers-reduced-motion: reduce) {
    img,
    .go {
      transition: none;
    }
    .caret {
      animation: none;
    }
  }

  .specimen-caption {
    margin-top: 16px;
  }

  /* Phone: a shorter window, so the actions stay near the fold. */
  @media (max-width: 480px) {
    .window-view {
      aspect-ratio: auto;
      height: 380px;
    }
  }
</style>
