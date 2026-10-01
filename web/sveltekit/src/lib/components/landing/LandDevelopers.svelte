<script lang="ts">
  import { QUICKSTART_URL } from '$lib/staticSite';

  /** For developers and AI agents: the HTTP and MCP routes to the same
   *  evidence, and the README quickstart's commands. */
  const TOOLS = [
    'get_evidence',
    'get_district_summary',
    'get_briefing',
    'nyc311_flood_requests',
    'plan_query',
    'list_sources',
    'get_citation'
  ];
  const CODE = `# Get the code and its data (needs uv and Git LFS)
git clone https://github.com/msradam/riprap && cd riprap
git lfs install && git lfs pull

# Start the server: no GPU, no API keys
uv run uvicorn web.main:app --port 7860

# A district briefing as JSON
curl -s "http://localhost:7860/api/agent?q=QN12"

# The same evidence for an AI agent, over MCP
uv run riprap-mcp`;
</script>

<section class="land-section land-band" id="developers" aria-labelledby="dev-h">
  <div class="land-frame dev-grid">
    <div>
      <h2 id="dev-h" class="land-h2">For developers and AI agents</h2>
      <p class="dev-body">
        Every briefing is also data. Over HTTP you get the full result as JSON with its trace. Over
        MCP, seven tools return each finding with its figures, its source URL and the date of its
        data, plus the list of sources that did not answer. No language model is needed.
      </p>
      <p class="dev-tools-head" id="dev-tools">The MCP tools</p>
      <ul class="dev-tools" aria-labelledby="dev-tools">
        {#each TOOLS as t (t)}<li>{t}</li>{/each}
      </ul>
      <ul class="land-actions">
        <li><a class="land-button" href={QUICKSTART_URL}>Read the quickstart</a></li>
        <li><a class="land-button is-secondary" href="https://github.com/msradam/riprap">View the code on GitHub</a></li>
      </ul>
    </div>
    <figure class="dev-figure">
      <figcaption class="land-small">Commands to run Riprap and query it</figcaption>
      <!-- tabindex: the block scrolls sideways on a phone, so a keyboard user can scroll it (WCAG 2.1.1). -->
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <pre class="dev-code" tabindex="0"><code>{CODE}</code></pre>
    </figure>
  </div>
</section>

<style>
  .dev-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 48px;
    align-items: start;
  }
  .dev-body {
    margin: 0;
    max-width: 64ch;
    font-size: 17px;
    line-height: 1.55;
  }
  .dev-tools-head {
    margin: 24px 0 8px;
    font-size: 14px;
    line-height: 1.45;
    color: var(--ink-secondary);
  }
  .dev-tools {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 16px;
    margin: 0;
    padding: 0;
    list-style: none;
    font-family: var(--font-mono);
    font-size: 14px;
    line-height: 1.6;
  }
  .dev-figure {
    margin: 0;
    min-width: 0;
  }
  .dev-figure figcaption {
    margin-bottom: 8px;
  }
  /* The one dark band: Paper on Ink, Overpass Mono 14px. */
  .dev-code {
    margin: 0;
    padding: 24px;
    overflow-x: auto;
    background: var(--ink);
    color: var(--paper);
    font-family: var(--font-mono);
    font-size: 14px;
    line-height: 1.6;
  }
  /* The ring sits outside the block, on the band, so it takes Federal Blue
     as everywhere else (a Paper ring vanished against Sunken Paper). */
  .dev-code:focus-visible {
    outline: 3px solid var(--riprap-focus);
    outline-offset: 2px;
  }
  @media (max-width: 1099px) {
    .dev-grid {
      grid-template-columns: minmax(0, 1fr);
      gap: 32px;
    }
  }
  @media (max-width: 640px) {
    .dev-code {
      padding: 16px;
    }
  }
</style>
