<script lang="ts">
  import { MediaQuery } from 'svelte/reactivity';
  import { resolve } from '$app/paths';

  /** A real gallery briefing beside the headline, as a short loop: the
   *  question is typed into a picture of the search box, the search is
   *  sent, and the briefing's answer fades in and scrolls. The question
   *  and the answer are the snapshot's own text, read at build time, so a
   *  gallery rebuild changes them and nothing here can go stale. No map
   *  and no sensor points are drawn. */
  export interface Specimen {
    slug: string;
    question: string;
    /** "Yes.", "No." or "Partly." when the answer opens with one. */
    lead: string | null;
    /** The answer's sentences, one paragraph per source. */
    paras: string[];
    /** The day the snapshot was saved, YYYY-MM-DD. */
    date: string;
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
  // The loop runs for longer than five seconds beside other content, so it
  // has a control that stops it (WCAG 2.2.2); hover only holds it.
  let stopped = $state(false);
  let paused = $derived(stopped || hovered);

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
  <!-- Not a link: the answer is text to read. The caption links to the page. -->
  <div
    class="window"
    class:paused
    role="group"
    aria-label="A saved briefing"
    onpointerenter={() => (hovered = true)}
    onpointerleave={() => (hovered = false)}
  >
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
    <div class="window-view" class:still={phase === 'still'}>
      <div class="sheet" class:on={phase === 'show' || phase === 'still'} class:scroll={phase === 'show' || phase === 'out'}>
        <p class="sheet-q">{specimen.question}</p>
        {#if specimen.lead}<p class="sheet-lead">{specimen.lead}</p>{/if}
        {#each specimen.paras as p (p)}<p>{p}</p>{/each}
        <p class="sheet-note">
          Saved briefing of <time class="data" datetime={specimen.date}>{specimen.date}</time>. Each sentence has its
          source and date on the full page.
        </p>
      </div>
    </div>
  </div>
  <figcaption class="specimen-caption">
    <a class="land-link" {href}>Read the full briefing</a>
    {#if !still}
      <button type="button" class="specimen-pause" onclick={() => (stopped = !stopped)}>
        {stopped ? 'Play the preview' : 'Pause the preview'}
      </button>
    {/if}
  </figcaption>
</figure>

<style>
  .specimen {
    margin: 0;
  }
  .window {
    border: 1px solid var(--rule-soft);
    background: var(--riprap-white);
    color: var(--ink-secondary);
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

  /* A fixed shape, whatever the length of the answer. Size containment
     lets the scroll end be written as 100cqh. */
  .window-view {
    display: block;
    aspect-ratio: 4 / 5;
    /* Full width on a tablet: no taller than the desktop window. */
    max-height: 600px;
    overflow: hidden;
    container-type: size;
    background: var(--paper);
  }
  /* Reduced motion: nothing scrolls, so the window grows to show it all. */
  .window-view.still {
    aspect-ratio: auto;
    height: auto;
    max-height: none;
    container-type: normal;
  }
  /* The answer as the briefing page sets it: the question, the lead word
     large, then one paragraph per source. */
  .sheet {
    padding: 16px;
    color: var(--ink);
    font-size: 15px;
    line-height: 1.5;
    opacity: 0;
    translate: 0 6px;
    transition:
      opacity 0.4s ease-out,
      translate 0.4s ease-out;
  }
  .sheet.on {
    opacity: 1;
    translate: 0 0;
  }
  .sheet p {
    margin: 0 0 12px;
  }
  .sheet .sheet-q {
    font-size: 17px;
    font-weight: 600;
    line-height: 1.3;
  }
  .sheet .sheet-lead {
    margin-bottom: 8px;
    font-size: 40px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
  }
  .sheet .sheet-note {
    margin-bottom: 0;
    font-size: 13px;
    color: var(--ink-secondary);
  }
  /* Holds 1.5s at the top, scrolls for 10s, holds 2s at the foot, and
     stays there while it fades out. */
  .sheet.scroll {
    animation: specimen-scroll 13.5s ease-in-out forwards;
  }
  .window.paused .sheet {
    animation-play-state: paused;
  }
  @keyframes specimen-scroll {
    0%,
    11.1% {
      transform: translateY(0);
    }
    85.2%,
    100% {
      /* An answer shorter than the window stays where it is. */
      transform: translateY(min(0px, calc(100cqh - 100%)));
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .sheet,
    .go {
      transition: none;
    }
    .caret {
      animation: none;
    }
  }

  .specimen-caption {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 24px;
    margin-top: 16px;
  }
  /* A text button in the link colour, at least 24px tall (2.5.8). */
  .specimen-pause {
    min-height: 24px;
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    font-size: 14px;
    color: var(--riprap-text-link);
    text-decoration: underline;
    text-underline-offset: 0.2em;
    cursor: pointer;
  }
  .specimen-pause:hover {
    text-decoration-thickness: 2px;
  }

  /* Phone: a shorter window, so the actions stay near the fold. */
  @media (max-width: 480px) {
    .window-view {
      aspect-ratio: auto;
      height: 380px;
    }
  }
</style>
