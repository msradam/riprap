<script lang="ts">
  import { resolve } from '$app/paths';

  /** Who Riprap is for: four readers, each with a gallery example (the
   *  last points to the developer section). */
  const galleryHref = (slug: string) => `${resolve('/(app)/gallery/[slug]', { slug })}/`;
  const READERS = [
    {
      title: 'Reporters and data desks',
      body: "Quote a block's flood record with its source and date, on deadline.",
      link: 'See a sourced yes',
      href: galleryHref('hollis-since-ida')
    },
    {
      title: 'Community boards and council offices',
      body: "Take a district's 311 counts, flood map shares and exposed sites to the meeting on one printable page.",
      link: 'See QN12',
      href: galleryHref('qn12')
    },
    {
      title: 'Resilience analysts and planners',
      body: 'See which schools, subway entrances, public housing and hospitals sit inside the Sandy extent or a city stormwater scenario, in any of the 59 districts.',
      link: 'See BK06 public housing',
      href: galleryHref('bk06-nycha')
    },
    {
      title: 'Researchers and civic technologists',
      body: 'Pull the same cited evidence into a notebook, a pipeline or an AI agent.',
      link: 'For developers',
      href: '#developers'
    }
  ];
</script>

<section class="land-section" aria-labelledby="for-h">
  <div class="land-frame">
    <h2 id="for-h" class="land-h2">Made for people who have to cite it</h2>
    <ul class="land-cards is-four">
      {#each READERS as r (r.title)}
        <li class="land-card">
          <h3>{r.title}</h3>
          <p>{r.body}</p>
          <p class="land-card-link"><a class="land-link" href={r.href}>{r.link}</a></p>
        </li>
      {/each}
    </ul>
  </div>
</section>
