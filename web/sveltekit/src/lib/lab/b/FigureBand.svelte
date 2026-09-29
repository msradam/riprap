<script lang="ts">
  import { shortDate, type Band } from './figures';

  /** A break-out band of two or three numbers from the evidence cards. */
  let { band }: { band: Band } = $props();

  const sourceLine = (source: string, vintage: string) =>
    vintage === 'live' ? `${source}, live reading` : `${source}, data as of ${shortDate(vintage)}`;
  let shared = $derived(new Set(band.figures.map((f) => f.source + f.vintage)).size === 1);
</script>

<figure class="band">
  {#if band.title}<figcaption class="band-title">{band.title}</figcaption>{/if}
  <dl class="band-list" style:--n={band.figures.length}>
    {#each band.figures as f, i (i)}
      <div class="band-item">
        <dt>
          {f.label}
          {#if !shared}<span class="band-source">{sourceLine(f.source, f.vintage)}</span>{/if}
        </dt>
        <dd>{f.value}{#if f.unit}<span class="band-unit">&nbsp;{f.unit}</span>{/if}</dd>
      </div>
    {/each}
  </dl>
  {#if shared}<p class="band-source">{sourceLine(band.figures[0].source, band.figures[0].vintage)}</p>{/if}
</figure>

<style>
  .band {
    max-width: 1040px;
    margin: 64px auto;
    padding: 0;
  }
  .band-title {
    max-width: 640px;
    margin: 0 0 16px;
    font-size: 17px;
    font-weight: 600;
    line-height: 1.35;
  }
  .band-list {
    display: grid;
    grid-template-columns: repeat(var(--n), minmax(0, 1fr));
    gap: 24px 40px;
    margin: 0;
  }
  /* The number reads first; the label follows it and names it. */
  .band-item {
    display: flex;
    flex-direction: column-reverse;
    justify-content: flex-end;
    gap: 6px;
  }
  dd {
    margin: 0;
    font-size: 48px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
    color: var(--ink);
  }
  .band-unit {
    font-size: 20px;
    font-weight: 600;
    letter-spacing: 0;
  }
  dt {
    font-size: 16px;
    line-height: 1.4;
    color: var(--ink);
  }
  .band-source {
    display: block;
    margin: 4px 0 0;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  p.band-source {
    margin-top: 16px;
  }
  @media (max-width: 640px) {
    .band {
      margin: 48px auto;
    }
    .band-list {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 24px 20px;
    }
    dd {
      font-size: 40px;
    }
  }
</style>
