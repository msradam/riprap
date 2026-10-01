<script lang="ts">
  import { resolve } from '$app/paths';
  import { STATIC_SITE } from '$lib/staticSite';

  /** Build it with us: four ways in, then the contact routes that exist
   *  today (issues and the author address in CITATION.cff). The city
   *  names always show; their sample links run a live briefing, so the
   *  static site leaves them out. */
  const REPO = 'https://github.com/msradam/riprap';
  const DOCS = `${REPO}/blob/main/docs`;
  const EMAIL = 'mailto:msrahmanadam@gmail.com?subject=Riprap';

  const CITIES = [
    { city: 'NYC', address: '189 Atlantic Avenue, Brooklyn, NY' },
    { city: 'Chicago', address: '233 S Wacker Dr, Chicago, IL' },
    { city: 'Seattle', address: '2100 5th Ave, Seattle, WA' },
    { city: 'Albany', address: '25 Erie Blvd, Albany, NY' }
  ];
  const briefHref = (addr: string) => resolve('/(app)/q/[queryId]', { queryId: encodeURIComponent(addr) });

  const WAYS = [
    {
      title: 'Run a pilot',
      body: 'A newsroom data desk, a council office, a community board or a studio course can run its own copy. Tell us what you would ask it.',
      link: 'Email the author',
      href: EMAIL
    },
    {
      title: 'Bring your city',
      body: 'A city with a Socrata open-data portal needs only manifests. Chicago, Seattle and Albany run today as experimental ports, and New York City (NYC) is in production.',
      link: 'How to port a city',
      href: `${DOCS}/PORT-YOUR-CITY.md`,
      cities: true
    },
    {
      title: 'Bring your data',
      body: 'Add your own sites, such as a list of firehouses, to every briefing with one YAML manifest and no fork.',
      link: 'Bring your own data',
      href: `${DOCS}/byod.md`
    },
    {
      title: 'Improve a model',
      body: "Each model has a backtest and a baseline. When a test reruns, the briefing's accuracy sentence updates from its results.",
      link: 'Read the backtests',
      href: `${DOCS}/MODELS.md`
    }
  ];
</script>

<section class="land-section" aria-labelledby="collab-h">
  <div class="land-frame">
    <h2 id="collab-h" class="land-h2">Build it with us</h2>
    <p class="land-intro">
      Riprap is open source under Apache-2.0, on open data and open models. Bring a city, a dataset, a
      model or a class.
    </p>
    <ul class="land-cards">
      {#each WAYS as w (w.title)}
        <li class="land-card">
          <h3>{w.title}</h3>
          <p>{w.body}</p>
          {#if 'cities' in w && !STATIC_SITE}
            <p class="land-small collab-cities">
              Try a sample address:
              {#each CITIES as c, i (c.city)}<a class="land-link" href={briefHref(c.address)}>{c.city}</a
                >{i < CITIES.length - 1 ? ', ' : ''}{/each}
            </p>
          {/if}
          <p class="land-card-link"><a class="land-link" href={w.href}>{w.link}</a></p>
        </li>
      {/each}
    </ul>
    <ul class="land-actions">
      <li><a class="land-button" href="{REPO}/issues/new/choose">Open an issue</a></li>
      <li><a class="land-button is-secondary" href={REPO}>Read the code</a></li>
      <li><a class="land-button is-secondary" href={EMAIL}>Email the author</a></li>
    </ul>
  </div>
</section>

<style>
  .land-card .collab-cities {
    font-size: 14px;
  }
</style>
