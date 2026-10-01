<script lang="ts">
  /**
   * The run ended without a briefing: the place did not resolve, nothing
   * was found, or the backend did not answer. Set where the answer would
   * be, as a plain statement with the next steps as links. Announced with
   * aria-live=assertive.
   */
  import type { ErrorKey } from '$lib/types/states';
  import { deployment } from '$lib/stores/deployment.svelte';
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { SAMPLE_ADDRESS } from '$lib/samples';
  import { briefingState } from '$lib/stores/briefingState.svelte';
  import { QUICKSTART_URL } from '$lib/staticSite';

  interface Action {
    label: string;
    href: string;
  }

  interface Props {
    state: ErrorKey;
  }

  let { state }: Props = $props();

  interface Spec {
    kind: string;
    headline: string;
    body: string;
    actions: Action[];
  }

  // The query as typed; empty outside the live route.
  let query = $derived(page.params.queryId ?? '');
  // A borough code and district number, typed with or without a space.
  let looksLikeDistrict = $derived(/^\s*(MN|BX|BK|QN|SI)\s*\d{1,2}\s*$/i.test(query));

  // The routed deployment decides whether the geocoder hint may name
  // an NYC community district; under a Chicago chip it would mislead.
  let depName = $derived(deployment.current?.name);
  let cityName = $derived(deployment.current?.city ?? '');
  let isUnknown = $derived(!depName || depName === 'unknown' || depName === '__none__' || depName === 'federal');

  let sample = $derived<Action>({ label: 'Use a sample query', href: resolve('/(app)/q/[queryId]', { queryId: encodeURIComponent(SAMPLE_ADDRESS) }) });
  // The landing reads ?q= into its search box and focuses it.
  let edit = $derived<Action>({ label: 'Edit query', href: query ? `${resolve('/')}?q=${encodeURIComponent(query)}` : resolve('/') });
  let retry = $derived<Action>({ label: 'Try again', href: page.url.pathname });

  const SPECS = $derived<Record<ErrorKey, Spec>>({
    geocoder: {
      kind: 'Address not resolved',
      headline: isUnknown
        ? 'We could not match that to a place Riprap covers.'
        : `We could not match that to a place Riprap covers in ${cityName}.`,
      // Community districts are New York City codes; name them only
      // when the run is in NYC or no city resolved at all.
      body: isUnknown || depName === 'nyc'
        ? 'Try a full street address, or a community district such as QN12.'
        : 'Try a full street address.',
      actions: [sample, edit]
    },
    'all-silent': {
      kind: 'Outside evidence coverage',
      headline: 'No source returned evidence for this point.',
      body:
        `The address resolved, but every flood source came back empty. This is rare and usually means parkland, water, or a point with no civic data nearby. Try a street address nearby, or a neighborhood name.`,
      actions: [edit, sample]
    },
    grounding: {
      kind: 'Grounding failure',
      headline: 'No written claim passed verification against its cited sources.',
      body:
        'The model wrote claims, but each one failed the check against its cited sources, so no briefing prose is shown. The evidence itself comes straight from the sources and is not affected.',
      actions: [retry, edit]
    },
    backend: {
      kind: 'Backend error',
      headline: 'Riprap hit an error building this briefing.',
      body: 'The backend stopped before the briefing was written. The error it reported is below.',
      actions: [retry, edit]
    },
    // The public static copy: the links are in the body, so no actions.
    'no-backend': {
      kind: 'No backend',
      headline: 'This public copy has no backend.',
      body: '',
      actions: []
    }
  });

  let spec = $derived(SPECS[state]);
</script>

<section class="error-card error-card-{state}" role="alert" aria-live="assertive" aria-labelledby="error-card-h">
  <p class="error-card-kind">{spec.kind}</p>
  <h2 id="error-card-h" class="error-card-headline">{spec.headline}</h2>
  {#if spec.body}<p class="error-card-body">{spec.body}</p>{/if}
  {#if state === 'no-backend'}
    <p class="error-card-body">
      Browse the <a href="{resolve('/(app)/gallery')}/">gallery</a>, or run Riprap locally:
      <a href={QUICKSTART_URL}>README Quickstart</a>.
    </p>
  {:else if state === 'backend' && briefingState.errorMessage}
    <details class="error-card-detail">
      <summary>Error text</summary>
      <pre>{briefingState.errorMessage}</pre>
    </details>
  {/if}
  {#if state === 'geocoder' && looksLikeDistrict && (isUnknown || depName === 'nyc')}
    <p class="error-card-body">
      Check the borough code and district number, for example QN12, or read the precomputed
      <a href="{resolve('/(app)/gallery/[slug]', { slug: 'qn12-complaints' })}/">QN12 briefing in the gallery</a>.
    </p>
  {/if}
  <!-- A full load: each action starts a new run or restarts this one. -->
  <ul class="error-card-actions">
    {#each spec.actions as a (a.label)}
      <li><a class="error-card-action" href={a.href} data-sveltekit-reload>{a.label}</a></li>
    {/each}
  </ul>
</section>

<style>
  .error-card {
    max-width: 680px;
    margin-top: 16px;
    color: var(--ink);
  }
  .error-card-kind {
    margin: 0 0 4px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  /* One h2 style on every page: Headline. */
  .error-card-headline {
    margin: 0 0 8px;
    max-width: 30ch;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
    text-wrap: balance;
  }
  .error-card-body {
    margin: 0 0 8px;
    max-width: 54ch;
    font-size: 17px;
    line-height: 1.55;
  }
  .error-card a {
    color: var(--riprap-text-link);
  }
  .error-card-detail {
    max-width: 54ch;
    margin: 8px 0;
    font-size: 14px;
    line-height: 1.45;
  }
  .error-card-detail summary {
    min-height: 24px;
    cursor: pointer;
  }
  .error-card-detail pre {
    margin: 4px 0 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--ink-secondary);
  }
  .error-card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 24px;
    margin: 16px 0 0;
    padding: 0;
    list-style: none;
    font-size: 17px;
  }
  .error-card-action {
    display: inline-block;
    min-height: 24px;
    font-weight: 600;
    text-underline-offset: 3px;
  }
  .error-card a:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
</style>
