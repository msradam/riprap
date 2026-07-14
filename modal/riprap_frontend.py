"""Riprap frontend (CPU app tier) on Modal.

Serves the FastAPI backend + SvelteKit static UI as a scale-to-zero web
endpoint. Pairs with the `riprap-triton` GPU app (Triton + vLLM) in the same
Modal environment; point RIPRAP_LLM_BASE_URL / RIPRAP_ML_BASE_URL at that
app's proxy URL to enable full LLM + specialist inference.

Deploy (into the `riprap` environment):

    modal deploy modal/riprap_frontend.py --env riprap

The Phase-1 default is the templated (no-LLM) reconciler tier, so the app
serves real, citation-grounded briefings with no GPU backend at all. To wire
the inference layer, set RIPRAP_RECONCILER_TIER=llm and the two base URLs +
RIPRAP_LLM_API_KEY (the proxy bearer token) and redeploy.
"""

from __future__ import annotations

from pathlib import Path

import modal

REPO = Path(__file__).resolve().parent.parent

# Build-time config. `.env()` is a build step, so it must precede the
# add_local_* mounts per Modal's image ordering rules.
# Proxy URL of the GPU inference app in the same Modal environment.
# riprap-inference (LitServe) replaces riprap-triton (NVIDIA Triton) —
# same vLLM, same 5 specialists, same client-facing /v1/* contract, but
# no Triton base image / KFServing translation layer. See
# msradam/riprap-triton's modal/riprap_modal_litserve.py + litserve_proto/.
_INFERENCE_URL = "https://msradam-riprap--riprap-inference-riprap-proxy.modal.run"

FRONTEND_ENV = {
    # Full LLM tier — Granite 4.1 reconciliation via the riprap-triton GPU app.
    "RIPRAP_RECONCILER_TIER": "llm",
    "RIPRAP_DEPLOYMENT": "deployments/nyc",
    # LLM: Granite 4.1 8B served by vLLM behind the proxy (/v1 OpenAI-compat).
    "RIPRAP_LLM_PRIMARY": "vllm",
    "RIPRAP_LLM_BASE_URL": f"{_INFERENCE_URL}/v1",
    "RIPRAP_LLM_VLLM_8B_NAME": "granite4.1:8b",
    # app/llm.py defaults RIPRAP_LLM_FALLBACK to "ollama" whenever
    # primary=vllm — a sane default for local dev, but there's no Ollama
    # in this container. A transient vLLM error (cold GPU, a genuine 500)
    # was masked by litellm's automatic failover attempt, which then
    # failed with "Ollama_chatException - Connection refused" — a
    # confusing, unrelated error that hid the real one and made every
    # downstream specialist read as "unavailable" instead of surfacing
    # the actual vLLM failure. No fallback to hide behind here.
    "RIPRAP_LLM_FALLBACK": "",
    # mellea_validator.py's 350-token default was sized for the old RunPod
    # deployment's max_model_len=2352, where every completion token had to
    # be clawed back from the input budget. The Modal GPU app's vLLM now
    # runs max_model_len=8192, with ample room, and the growing pebble set
    # (federal fema_nfhl/usgs_gauges auto-merged into every deployment
    # 2026-07-10) produces 4-section briefings that run past 350 tokens
    # and get cut off mid-sentence. 700 comfortably fits Status + Empirical
    # + Modeled + Policy + the closing scope disclaimer — confirmed against
    # the strict/streaming path (/api/agent/stream, what the SvelteKit UI
    # and `make query` actually hit): complete, uncut briefings across all
    # 6 cities. litellm_params.stream_timeout and RIPRAP_TOKEN_TIMEOUT_S
    # were widened alongside this and are harmless headroom, but weren't
    # the actual fix — see RIPRAP_RECONCILE_NUM_PREDICT below for the real
    # second cap this session found.
    "RIPRAP_MELLEA_NUM_PREDICT": "700",
    "RIPRAP_TOKEN_TIMEOUT_S": "90",
    # riprap.core.burr.app.run() — the non-strict path the plain `/api/agent`
    # route and the MCP get_briefing tool call directly, bypassing
    # mellea_validator entirely — hits its OWN hardcoded 400-token cap in
    # app/reconcile.py, sized for local Ollama. Same symptom (mid-sentence
    # cutoff), different code path; this is the one an MCP client on Modal
    # would actually hit.
    "RIPRAP_RECONCILE_NUM_PREDICT": "900",
    # Specialist ML models (Prithvi / TerraMind / TTM / embed) over the proxy.
    "RIPRAP_ML_BACKEND": "remote",
    "RIPRAP_ML_BASE_URL": _INFERENCE_URL,
    "RIPRAP_HEAVY_SPECIALISTS": "1",
    # TerraMind/eo_chip/Prithvi-live all disabled for this demo deploy: all
    # three hit the same real external dependency — Microsoft's Planetary
    # Computer STAC API for recent Sentinel-2/1 scenes — which is
    # consistently slow/timing out from Modal's network (eo_chip_cache's
    # own 75s hard timeout; prithvi_live has no such cap and one real
    # query took 271s total because of it, pystac_client.exceptions.
    # APIError: "The request exceeded the maximum allowed time"). Not a
    # bug in this app — the rest of the briefing completes cleanly in
    # ~40-90s on its own. Re-enable once STAC/COG latency from Modal is
    # investigated separately (possibly needs a shorter per-search
    # timeout + graceful skip in app/flood_layers/prithvi_live.py, same
    # pattern eo_chip_cache.py already uses).
    "RIPRAP_TERRAMIND_ENABLE": "0",
    "RIPRAP_EO_CHIP_ENABLE": "0",
    "RIPRAP_PRITHVI_LIVE_ENABLE": "0",
    # Scale-to-zero: skip the eager boot warm; everything lazy-loads on first
    # query, keeping the cold start within Modal's startup window.
    "RIPRAP_SKIP_WARM": "1",
    "RIPRAP_SKIP_LLM_WARM": "1",
    "PYTHONUNBUFFERED": "1",
    # RIPRAP_LLM_API_KEY / RIPRAP_ML_API_KEY are injected from the
    # riprap-stack secret (the proxy bearer token), attached to the function.
}


def _image() -> modal.Image:
    return (
        modal.Image.debian_slim(python_version="3.12")
        # Geo libs for geopandas / rasterio / fiona / pyproj, mirroring
        # Dockerfile.app. curl is for healthchecks.
        .apt_install(
            "curl",
            "ca-certificates",
            "gdal-bin",
            "libgdal-dev",
            "libgeos-dev",
            "libproj-dev",
        )
        .pip_install_from_requirements(str(REPO / "requirements.txt"))
        .env(FRONTEND_ENV)
        .workdir("/app")
        # Runtime code + fixtures. The pebble framework resolves
        # `deployments/<name>/manifests` relative to the repo root (cwd),
        # so deployments/ + data/ + corpus/ must all be present. `riprap/`
        # is the post-refactor core package web.main imports from.
        .add_local_dir(str(REPO / "riprap"), "/app/riprap")
        .add_local_dir(str(REPO / "app"), "/app/app")
        .add_local_dir(str(REPO / "deployments"), "/app/deployments")
        .add_local_dir(str(REPO / "data"), "/app/data")
        .add_local_dir(str(REPO / "corpus"), "/app/corpus")
        .add_local_dir(str(REPO / "scripts"), "/app/scripts")
        .add_local_file(str(REPO / "web" / "__init__.py"), "/app/web/__init__.py")
        .add_local_file(str(REPO / "web" / "main.py"), "/app/web/main.py")
        .add_local_dir(str(REPO / "web" / "static"), "/app/web/static")
        .add_local_dir(
            str(REPO / "web" / "sveltekit" / "build"),
            "/app/web/sveltekit/build",
        )
    )


app = modal.App("riprap-frontend")


@app.function(
    image=_image(),
    # Proxy bearer token: injected as RIPRAP_LLM_API_KEY / RIPRAP_ML_API_KEY.
    secrets=[modal.Secret.from_name("riprap-stack")],
    cpu=2.0,
    # 16 GB: the lazy-loaded geo files (citywide DEM GeoTIFF, Sandy/DEP GDB),
    # the RAG embedding model, and per-query rasterio/fiona opens blow past
    # 4 GB under concurrent first-loads, which fails those probes ("DEM
    # unavailable", "NPCC4 table missing", etc.) and serves half-empty cards.
    memory=16384,
    scaledown_window=300,
    timeout=600,
    # One container for the demo profile: a single warmed container handles the
    # low query volume and never cold-spawns siblings, which is what thrashed
    # the cards mid-demo (a burst of queries each hit a fresh cold container).
    max_containers=1,
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def web_app():
    import os
    import sys

    os.chdir("/app")
    sys.path.insert(0, "/app")
    from web.main import app as fastapi_app  # noqa: PLC0415

    return fastapi_app
