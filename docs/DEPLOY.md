---
type: guide
---

# Deployment

Riprap is one CPU process: FastAPI serving the SvelteKit build and the evidence
pipeline. The MCP server is a separate process (`python -m riprap.mcp.server`);
`web/main.py` does not mount it. It needs no GPU and no keys. An LLM is optional and
is always a separate OpenAI-compatible endpoint you point it at.

## 1. Local, no LLM (default)

```bash
git lfs install && git lfs pull      # data/ and the policy PDFs are Git LFS files
uv sync
uv run uvicorn web.main:app --port 7860
```

Open `http://localhost:7860`. Every briefing is the no-LLM evidence briefing
(docs/GROUNDING.md).

## 2. Local, with an LLM

Any OpenAI-compatible endpoint works. With [Ollama](https://ollama.com):

```bash
ollama pull hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M
RIPRAP_LLM_BASE_URL=http://localhost:11434/v1 \
RIPRAP_LLM_MODEL=hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M \
  uv run uvicorn web.main:app --port 7860
```

`RIPRAP_LLM_API_KEY` is sent when set. `RIPRAP_LLM_FALLBACK_BASE_URL`,
`_MODEL` and `_API_KEY` name a second endpoint tried when the first fails.
Settings are read when a request runs, not frozen at import.

This is IBM's own GGUF on Hugging Face, the model the gallery uses. On an
Apple M5 laptop, earlier probes with `granite4:micro` took 19 to 60 s
(`tests/probe_grounding_results.json`) and with `llama3.1:8b` 189 to 325 s,
about 3 to 5.5 minutes (`tests/probe_grounding_results_llama3.1-8b.json`).
A small shared VPS will be several times slower for 8B models.

## 3. Docker

```bash
docker compose up                      # app only, no LLM
docker compose --profile local-llm up  # app plus an Ollama container
```

See the comments in `docker-compose.yml` for pointing the app at the bundled
Ollama. `deploy/Dockerfile` builds the image on its own.

## 4. Optional: a GPU LLM endpoint on Modal

For a faster or larger model than a laptop can serve, run one yourself and
point `RIPRAP_LLM_BASE_URL` at it. The companion repo
[`msradam/riprap-inference`](https://github.com/msradam/riprap-inference) has a
scale-to-zero vLLM app for Granite 4.1 8B (`modal_vllm_app.py`):

```bash
# in msradam/riprap-inference
modal secret create riprap-vllm-secret RIPRAP_VLLM_API_KEY=$(openssl rand -hex 24) --env riprap
modal deploy modal_vllm_app.py --env riprap
```

Then:

```bash
export RIPRAP_LLM_BASE_URL=<the riprap-vllm Modal URL>/v1
export RIPRAP_LLM_MODEL=<the model name vLLM serves>
export RIPRAP_LLM_API_KEY=<the RIPRAP_VLLM_API_KEY value>
```

A cold start there takes one to two minutes, and the GPU bills for its idle
window. A hosted provider serving an open model is usually cheaper for low
traffic. `deploy/modal_app.py` can also host the app itself on Modal as a
CPU-only function.

The per-request ML specialist server in riprap-inference (`modal_app.py`,
LitServe) is not used: TTM, embeddings and NER run in the app process on CPU,
and the earth-observation models run as batch jobs (`scripts/run_eo_batch.py`).
