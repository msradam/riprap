"""Optional: serve the Riprap app from Modal as a scale-to-zero CPU app.

This is not the default path. The app runs anywhere with `uv sync` and
needs no GPU: see the README quickstart. Modal is one place to host it.

    modal deploy deploy/modal_app.py --env riprap

Without LLM settings the app serves the no-LLM evidence briefing. To turn
on LLM synthesis, point it at any OpenAI-compatible endpoint (a hosted
provider, or a vLLM server such as msradam/riprap-inference's
modal_vllm_app.py, described in docs/DEPLOY.md): set RIPRAP_LLM_BASE_URL
and RIPRAP_LLM_MODEL below, and attach the endpoint's key as the Modal
secret `riprap-llm-secret` (key RIPRAP_LLM_API_KEY).
"""
from __future__ import annotations

import os
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parent.parent

FRONTEND_ENV = {
    "RIPRAP_DEPLOYMENT": "deployments/nyc",
    "PYTHONUNBUFFERED": "1",
    # LLM synthesis is opt-in; leave both empty for the no-LLM briefing.
    "RIPRAP_LLM_BASE_URL": os.environ.get("RIPRAP_LLM_BASE_URL", ""),
    "RIPRAP_LLM_MODEL": os.environ.get("RIPRAP_LLM_MODEL", ""),
}


def _image() -> modal.Image:
    return (
        modal.Image.debian_slim(python_version="3.12")
        # Mirrors deploy/Dockerfile: the geo wheels bundle GDAL, GEOS and PROJ;
        # rasterio still links the system libexpat.
        .apt_install("curl", "ca-certificates", "libexpat1")
        .pip_install_from_pyproject(str(REPO / "pyproject.toml"))
        .env(FRONTEND_ENV)
        .workdir("/app")
        # Runtime code + fixtures. The pebble framework resolves
        # `deployments/<name>/manifests` relative to the repo root (cwd),
        # so deployments/ (with the policy corpus) + data/ must be present. `riprap/`
        # is the post-refactor core package web.main imports from.
        .add_local_dir(str(REPO / "riprap"), "/app/riprap")
        .add_local_dir(str(REPO / "app"), "/app/app")
        .add_local_dir(str(REPO / "deployments"), "/app/deployments")
        .add_local_dir(str(REPO / "data"), "/app/data")
        .add_local_file(str(REPO / "web" / "__init__.py"), "/app/web/__init__.py")
        .add_local_file(str(REPO / "web" / "main.py"), "/app/web/main.py")
        .add_local_dir(
            str(REPO / "web" / "sveltekit" / "build"),
            "/app/web/sveltekit/build",
        )
    )


app = modal.App("riprap-frontend")


@app.function(
    image=_image(),
    secrets=[modal.Secret.from_name("riprap-llm-secret", required_keys=["RIPRAP_LLM_API_KEY"])]
    if FRONTEND_ENV["RIPRAP_LLM_BASE_URL"] else [],
    cpu=2.0,
    # The lazy-loaded geo files (citywide DEM, Sandy/DEP layers) and the
    # in-process embedding and TTM models need a few GB under concurrent
    # first loads.
    memory=8192,
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
