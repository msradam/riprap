<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { EXAMPLES } from '$lib/samples';
  import { STATIC_SITE, QUICKSTART_URL } from '$lib/staticSite';

  /** Landing top: kind line, title, one deck sentence, the query box and
   *  one runnable example per kind of input. The static site has no
   *  backend, so the gallery replaces the query box there. */

  let q = $state('');
  let input: HTMLInputElement | undefined;
  // Set by an empty submit, cleared by the next keystroke. The button stays
  // enabled and the input has no `required`, so the browser shows no bubble.
  let empty = $state(false);

  // "Edit query" from a briefing arrives as /?q=<query>. Attachments run
  // on the client only, which matters because the landing is prerendered.
  // It also keeps the node for the empty-submit focus.
  function prefill(node: HTMLInputElement) {
    input = node;
    const v = new URLSearchParams(window.location.search).get('q');
    if (v) {
      q = v;
      node.focus();
    }
  }

  function briefHref(v: string) {
    return resolve('/(app)/q/[queryId]', { queryId: encodeURIComponent(v) });
  }

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const v = q.trim();
    if (v) {
      goto(briefHref(v));
    } else {
      empty = true;
      input?.focus();
    }
  }
</script>

<section class="land-hero">
  <p class="land-kind">Riprap, open beta</p>
  <h1>Flood-exposure briefings for New York City</h1>
  <p class="land-deck">
    Riprap turns an address, a community district, or a flood question into a written briefing
    on flood exposure.
  </p>

  {#if STATIC_SITE}
    <p class="land-static">
      <a class="land-button" href="{resolve('/(app)/gallery')}/">Read the precomputed briefings</a>
    </p>
    <p class="land-note">
      This public copy has no backend. <a href={QUICKSTART_URL}>Run locally to ask your own question</a>.
    </p>
  {:else}
    <form class="land-query" role="search" onsubmit={submit}>
      <label for="land-query-input">Address, community district, or flood question</label>
      <div class="land-query-row">
        <input
          id="land-query-input"
          type="text"
          {@attach prefill}
          bind:value={q}
          oninput={() => (empty = false)}
          aria-describedby={empty ? 'land-query-hint' : undefined}
          placeholder="Address, QN12, or a question"
          autocomplete="off"
          enterkeyhint="search"
        />
        <button type="submit" class="land-button">Brief this place</button>
      </div>
      <!-- Always in the DOM so screen readers announce the message when it appears. -->
      <p id="land-query-hint" class="land-query-hint" role="status">{#if empty}Type an address, a community district such as QN12, or a question.{/if}</p>
    </form>

    <p class="land-try-head" id="land-try">Or try one of these:</p>
    <ul class="land-try" aria-labelledby="land-try">
      {#each EXAMPLES as ex (ex.kind)}
        <li><span class="land-try-kind">{ex.kind}</span> <a href={briefHref(ex.q)}>{ex.q}</a></li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .land-hero {
    max-width: 800px;
    padding: 48px 0 0;
  }
  .land-kind {
    margin: 0 0 12px;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  h1 {
    margin: 0;
    font-size: 56px;
    font-weight: 700;
    line-height: 1.05;
    letter-spacing: -0.02em;
    text-wrap: balance;
  }
  .land-deck {
    margin: 20px 0 0;
    max-width: 58ch;
    font-size: 20px;
    line-height: 1.5;
    color: var(--ink-secondary);
    text-wrap: pretty;
  }
  a {
    color: var(--riprap-text-link);
    text-underline-offset: 0.2em;
  }
  a:focus-visible,
  input:focus-visible,
  button:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }

  .land-query {
    margin-top: 32px;
    max-width: 720px;
  }
  label {
    display: block;
    margin-bottom: 8px;
    font-size: 17px;
    font-weight: 600;
  }
  .land-query-row {
    display: flex;
    gap: 8px;
  }
  /* Small in ink: a prompt, not an error, so no red. */
  .land-query-hint {
    margin: 0;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink);
  }
  .land-query-hint:not(:empty) {
    margin-top: 8px;
  }
  input {
    flex: 1;
    min-width: 0;
    height: 56px;
    padding: 0 16px;
    border: 1px solid var(--ink-secondary);
    border-radius: 0;
    background: var(--riprap-white);
    font: inherit;
    font-size: 19px;
    color: var(--ink);
  }
  input::placeholder {
    color: var(--ink-tertiary);
  }
  input:focus-visible {
    outline-offset: 0;
  }
  .land-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 56px;
    padding: 0 24px;
    border: 0;
    background: var(--ink);
    color: var(--paper);
    font: inherit;
    font-size: 17px;
    font-weight: 600;
    white-space: nowrap;
    text-decoration: none;
    cursor: pointer;
  }
  .land-button:hover {
    background: #000;
  }

  .land-try-head {
    margin: 20px 0 4px;
    font-size: 14px;
    color: var(--ink-secondary);
  }
  .land-try {
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 17px;
  }
  .land-try li {
    padding: 2px 0;
  }
  .land-try-kind {
    display: inline-block;
    min-width: 5.5em;
    color: var(--ink-secondary);
  }
  .land-try a,
  .land-note a {
    display: inline-block;
    min-height: 24px;
  }
  .land-static {
    margin: 32px 0 12px;
  }
  .land-note {
    margin: 0;
    font-size: 14px;
    color: var(--ink-secondary);
  }

  @media (max-width: 640px) {
    .land-hero {
      padding-top: 24px;
    }
    h1 {
      font-size: 36px;
      line-height: 1.1;
    }
    .land-deck {
      font-size: 18px;
    }
    .land-query-row {
      flex-direction: column;
    }
    input {
      flex: none;
    }
    .land-try li {
      display: flex;
      flex-direction: column;
    }
  }
</style>
