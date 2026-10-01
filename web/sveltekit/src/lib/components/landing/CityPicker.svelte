<script lang="ts">
  import { resolve } from '$app/paths';

  /** One sample address per shipped city, as plain links. New York City
   *  is the production deployment; the other three are experimental. */

  const CITIES = [
    { city: 'NYC', address: '189 Atlantic Avenue, Brooklyn, NY', experimental: false },
    { city: 'Chicago', address: '233 S Wacker Dr, Chicago, IL', experimental: true },
    { city: 'Seattle', address: '2100 5th Ave, Seattle, WA', experimental: true },
    { city: 'Albany', address: '25 Erie Blvd, Albany, NY', experimental: true }
  ];

  const href = (addr: string) => resolve('/(app)/q/[queryId]', { queryId: encodeURIComponent(addr) });
</script>

<section class="land-section" aria-labelledby="cities-h">
  <h2 id="cities-h">Cities</h2>
  <p>
    New York City is in production; Chicago, Seattle and Albany are experimental. Each link
    briefs one sample address.
  </p>
  <ul>
    {#each CITIES as c (c.city)}
      <li>
        <a href={href(c.address)}>{c.city}</a>
        <span class="city-addr">({c.experimental ? 'experimental' : 'production'}), {c.address}</span>
      </li>
    {/each}
  </ul>
</section>

<style>
  .land-section {
    margin-top: 64px;
    max-width: 60ch;
  }
  h2 {
    margin: 0 0 8px;
    font-size: 22px;
    font-weight: 600;
    line-height: 1.25;
  }
  p {
    margin: 0 0 12px;
    font-size: 17px;
    line-height: 1.55;
  }
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 17px;
  }
  li {
    padding: 2px 0;
  }
  a {
    display: inline-block;
    min-height: 24px;
    color: var(--riprap-text-link);
    text-underline-offset: 0.2em;
  }
  a:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  .city-addr {
    color: var(--ink-secondary);
  }
  @media (max-width: 640px) {
    .land-section {
      margin-top: 48px;
    }
  }
</style>
