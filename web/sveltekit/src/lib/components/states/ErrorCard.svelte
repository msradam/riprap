<script lang="ts">
  /**
   * v0.4.2 §12 — four canonical error states, each in polite-redirect
   * register. Same tone as cold-start: explanatory, helpful, never
   * alarming. The card announces via aria-live=assertive; first action
   * receives focus (caller wires `bind:focusEl` if needed).
   */
  import type { Tier } from '$lib/types/tier';
  import type { ErrorKey } from '$lib/types/states';
  import TierGlyph from '$lib/components/glyphs/TierGlyph.svelte';
  import { deployment } from '$lib/stores/deployment.svelte';
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { SAMPLE_ADDRESS } from '$lib/samples';

  interface Action {
    label: string;
    onClick?: () => void;
    href?: string;
  }

  interface Props {
    state: ErrorKey;
    actions?: Action[];
    /** Override headline / body for context-specific messages. */
    eyebrowOverride?: string;
    headlineOverride?: string;
    bodyOverride?: string;
  }

  let {
    state,
    actions,
    eyebrowOverride,
    headlineOverride,
    bodyOverride
  }: Props = $props();

  interface Spec {
    eyebrow: string;
    headline: string;
    body: string;
    tier: Tier;
    defaultActions: (string | Action)[];
  }

  // The query as typed; empty outside the live route.
  let query = $derived(page.params.queryId ?? '');
  // A borough code and district number, typed with or without a space.
  let looksLikeDistrict = $derived(/^\s*(MN|BX|BK|QN|SI)\s*\d{1,2}\s*$/i.test(query));

  // The routed deployment decides whether the geocoder hint may name
  // an NYC community district; under a Boston chip it would mislead.
  let depName = $derived(deployment.current?.name);
  let cityName = $derived(deployment.current?.city ?? '');
  let isUnknown = $derived(!depName || depName === 'unknown' || depName === '__none__');

  const SPECS = $derived<Record<ErrorKey, Spec>>({
    geocoder: {
      eyebrow: 'Address not resolved',
      headline: isUnknown
        ? 'We could not match that to a place Riprap covers.'
        : `We could not match that to a place Riprap covers in ${cityName}.`,
      // Community districts are New York City codes; name them only
      // when the run is in NYC or no city resolved at all.
      body: isUnknown || depName === 'nyc'
        ? 'Try a full street address, or a community district such as QN 12.'
        : 'Try a full street address.',
      tier: 'proxy',
      defaultActions: [
        { label: 'Use a sample query', href: resolve('/q/[queryId]', { queryId: encodeURIComponent(SAMPLE_ADDRESS) }) },
        // The landing reads ?q= into its search box and focuses it.
        { label: 'Edit query', href: query ? `${resolve('/')}?q=${encodeURIComponent(query)}` : resolve('/') }
      ]
    },
    'all-silent': {
      eyebrow: 'Outside evidence coverage',
      headline: 'No specialists found evidence at this point.',
      body:
        `The address resolved, but every flood-evidence specialist returned silent. This is rare and usually means parkland, water, or a point with no nearby civic data. Try a nearby street address or expand to neighborhood-mode.`,
      tier: 'proxy',
      defaultActions: ['Try nearby address', 'Switch to neighborhood-mode']
    },
    grounding: {
      eyebrow: 'Grounding failure',
      headline: 'No written claim passed verification against its cited sources.',
      body:
        'The model wrote claims, but each one failed the check against its cited sources, so no briefing prose is shown. The underlying evidence is fine: the evidence cards below come straight from the sources.',
      tier: 'modeled',
      defaultActions: ['Download evidence (JSON)', 'Contact support', 'Try again']
    },
    backend: {
      eyebrow: 'Backend unavailable',
      headline: 'Inference backend did not respond.',
      body:
        "The configured inference backend didn't respond within the routing budget. This usually clears within a few minutes during a deploy window.",
      tier: 'proxy',
      defaultActions: ['Retry now', 'Switch backend']
    }
  });

  let spec = $derived(SPECS[state]);
  let resolvedActions = $derived<Action[]>(
    actions ?? spec.defaultActions.map((a) => (typeof a === 'string' ? { label: a } : a))
  );
</script>

<article class="error-card error-card-{state}" role="alert" aria-live="assertive">
  <header class="error-card-head">
    <TierGlyph tier={spec.tier} size={11} color="var(--tier-{spec.tier})" />
    <span class="error-card-eyebrow">{eyebrowOverride ?? spec.eyebrow}</span>
  </header>
  <h3 class="error-card-headline">{headlineOverride ?? spec.headline}</h3>
  <p class="error-card-body">{bodyOverride ?? spec.body}</p>
  {#if state === 'geocoder' && looksLikeDistrict && !bodyOverride && (isUnknown || depName === 'nyc')}
    <p class="error-card-body">
      Write a district code with a space, for example QN 12, or read the precomputed
      <a href="{resolve('/gallery/[slug]', { slug: 'qn12-complaints' })}/">QN 12 briefing in the gallery</a>.
    </p>
  {/if}
  <div class="error-card-actions">
    {#each resolvedActions as a, i (i)}
      {#if a.href}
        <a class="error-card-action" class:is-primary={i === 0} href={a.href}>{a.label}</a>
      {:else}
        <button
          type="button"
          class="error-card-action"
          class:is-primary={i === 0}
          onclick={a.onClick}
        >{a.label}</button>
      {/if}
    {/each}
  </div>
  <footer class="error-card-foot">
    <span class="section-label">Trust signals · still on</span>
    <span class="error-card-foot-copy">All foundation models Apache-2.0 · No commercial APIs at runtime</span>
  </footer>
</article>
