"""Riprap web UI — FastAPI + SSE streaming of the Burr FSM trace.

Run: uvicorn web.main:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
import re
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import (  # noqa: E402
    FileResponse,
    JSONResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.context import floodnet  # noqa: E402
from app.flood_layers import dep_stormwater, sandy_inundation  # noqa: E402
from riprap.core.json_safe import to_json_safe as _to_json_safe  # noqa: E402
from riprap.core.pebbles import load_registry as _load_pebbles  # noqa: E402
from riprap.core.stones import load_stones as _load_stones  # noqa: E402

# Explicit, bounded thread pool for offloading blocking FSM/reconcile work
# from SSE handlers (compare_stream, api_agent_stream). NOT
# `loop.run_in_executor(None, ...)` — that lazily creates asyncio's
# process-wide default executor sized `min(32, os.cpu_count() + 4)`, and
# in a Modal container os.cpu_count() reflects the host's physical cores,
# not the function's actual CPU allocation — so that pool can grow to 32
# threads that then sit alive for the process lifetime, which is what
# Modal's shutdown logging was flagging as "36 background threads still
# running after container exit" (blocking a clean container recycle for
# up to 30s). Bounded to the same width as @modal.concurrent's max_inputs
# in deploy/modal_app.py — never more workers than could ever be
# concurrently needed.
_SSE_EXECUTOR = ThreadPoolExecutor(max_workers=20, thread_name_prefix="riprap-sse")

# Deployment dir (default deployments/nyc; override via RIPRAP_DEPLOYMENT).
# Stones + pebbles load once at import time.
_env_deployment = os.environ.get("RIPRAP_DEPLOYMENT")
_DEPLOYMENT = (
    Path(_env_deployment)
    if _env_deployment
    else Path(__file__).resolve().parent.parent / "deployments" / "nyc"
)
_STONES = _load_stones(_DEPLOYMENT)
_PEBBLES = _load_pebbles(_DEPLOYMENT)

# Pretty-printed Stone metadata the frontend renders as parent-row labels.
# Sourced from deployments/<name>/stones.yaml.
_STONE_META: dict[str, dict] = {
    s.name: {"name": s.name, "tagline": s.tagline, "description": s.description}
    for s in _STONES.all()
}


# Map trace step name -> Stone display name. Every pebble contributes
# (pebble.id -> Stone.name) from the registry; steps not in the map
# (geocode, nta_resolve, select_deployment) open no Stone boundary.
def _stone_display(stone_id: str) -> str:
    return _STONES.get(stone_id).name


_STEP_TO_STONE: dict[str, str] = {
    pebble.id: _stone_display(pebble.stone) for pebble in _PEBBLES.all()
}
# Steps that are not data pebbles. policy_corpus is a manifest pebble but
# runs in the Capstone, after the data Stones.
_STEP_TO_STONE.update(
    {
        "policy_corpus": _stone_display("capstone"),
        "reconcile_claims": _stone_display("capstone"),
        "reconcile_templated": _stone_display("capstone"),
    }
)

ROOT = Path(__file__).resolve().parent
SVELTEKIT_BUILD = ROOT / "sveltekit" / "build"

app = FastAPI(title="Riprap")

# SvelteKit static build (adapter-static), served from / and /q/<query>.
if SVELTEKIT_BUILD.exists():
    app.mount("/_app", StaticFiles(directory=SVELTEKIT_BUILD / "_app"), name="sveltekit_assets")


# Top-level static assets the SvelteKit build emits next to the HTML
# entry points (favicon.svg / favicon.png / robots.txt). These would
# fall through to the SPA fallback and 404 without explicit routes;
# adapter-static expects them under /, not /_app.
def _serve_build_asset(name: str):
    p = SVELTEKIT_BUILD / name
    if not p.exists():
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/favicon.svg", include_in_schema=False)
def _favicon_svg():
    return _serve_build_asset("favicon.svg")


@app.get("/favicon.png", include_in_schema=False)
def _favicon_png():
    return _serve_build_asset("favicon.png")


@app.get("/favicon.ico", include_in_schema=False)
def _favicon_ico():
    # No .ico in the build, but browsers still probe for it. Redirect-
    # by-content to the PNG so the tab gets the dam mark either way.
    return _serve_build_asset("favicon.png")


@app.get("/robots.txt", include_in_schema=False)
def _robots():
    return _serve_build_asset("robots.txt")


import json as _json  # noqa: E402

import geopandas as _gpd  # noqa: E402

_LAYER_CACHE: dict = {}


def _clip_simplify(
    gdf, lat: float, lon: float, radius_m: float = 1500, simplify_ft: float = 8, props_keep=None
):
    """Clip a NYC-wide layer to a small bbox around a point and simplify.

    Uses shapely's clip_by_rect (much faster than gpd.overlay on dense
    polygons) and a pre-bbox-filter via .cx so we never touch geometries
    outside the AOI.
    """
    import shapely.geometry as sg

    pt = _gpd.GeoSeries([sg.Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:2263")[0]
    half = radius_m * 3.281
    minx, miny, maxx, maxy = pt.x - half, pt.y - half, pt.x + half, pt.y + half

    sub = gdf.cx[minx:maxx, miny:maxy]
    if sub.empty:
        return {"type": "FeatureCollection", "features": []}

    clipped = sub.copy()
    clipped["geometry"] = sub.geometry.clip_by_rect(minx, miny, maxx, maxy)
    clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()]
    if clipped.empty:
        return {"type": "FeatureCollection", "features": []}

    clipped["geometry"] = clipped.geometry.simplify(simplify_ft, preserve_topology=True)
    g = clipped.to_crs("EPSG:4326")
    if props_keep is not None:
        g = g[[c for c in g.columns if c in props_keep or c == "geometry"]]
    else:
        g = g[["geometry"]]
    return _json.loads(g.to_json())


@app.on_event("startup")
def _warm_caches():
    """Prime slow loads so the first user query doesn't pay the cold-cost penalty."""
    if os.environ.get("RIPRAP_SKIP_WARM", "").lower() in ("1", "true", "yes"):
        # Scale-to-zero deployments (Modal etc.) want a fast cold start, not an
        # eager multi-minute warm on every wake. Everything below lazy-loads on
        # first use, so skipping the warm only moves the cost to the first query.
        print("[startup] cache warm skipped (RIPRAP_SKIP_WARM)", flush=True)
        return
    print("[startup] warming flood layers...", flush=True)
    sandy_inundation.load()
    for scen in ["dep_extreme_2080", "dep_moderate_2050", "dep_moderate_current"]:
        dep_stormwater.load(scen)
    print("[startup] flood layers ready", flush=True)
    if os.environ.get("RIPRAP_NYCHA_REGISTERS", "0").lower() in ("1", "true", "yes"):
        print("[startup] pre-loading register catalogs...", flush=True)
        try:
            # NYCHA + DOE schools read from pre-built JSON catalogs at
            # data/registers/{nycha,schools}.json — sub-ms per query.
            from app.registers._loader import load_register

            n_nycha = len(load_register("nycha"))
            n_schools = len(load_register("schools"))
            print(
                f"[startup] catalogs ready: nycha={n_nycha} rows, schools={n_schools} rows",
                flush=True,
            )
            # DOH hospitals has no pre-built catalog (~150 entries; we
            # read the GeoJSON directly and sample baked rasters per hit).
            from app.registers import doh_hospitals as _r_hospitals

            _r_hospitals._load_hospitals()
            print("[startup] hospitals geojson loaded", flush=True)
        except Exception as _e:
            print(f"[startup] register warm failed (non-fatal): {_e}", flush=True)
    print("[startup] loading the policy-corpus index...", flush=True)
    # RAG warm loads sentence-transformers, which on some HF Space rebuilds
    # has hit transformers-lazy-import edge cases (CodeCarbonCallback). The
    # Space *must* start even if RAG fails — the FSM still works without
    # RAG citations (specialists deliver their own grounded data, and the
    # rag step in fsm.py already handles `rag=[]` gracefully). Surface the
    # failure loudly in logs but don't kill the app.
    try:
        from app import rag

        rag.warm()
        print("[startup] RAG ready", flush=True)
    except Exception as e:  # noqa: BLE001
        print(
            f"[startup] RAG warm FAILED — continuing without RAG: {type(e).__name__}: {e}",
            flush=True,
        )
        import traceback

        traceback.print_exc()
    # Import the in-process model stacks on the main thread before any
    # worker thread does: transformers' lazy module loader races under
    # concurrent first imports ("Could not import module
    # 'PreTrainedModel'"). Modules whose deps are not installed no-op.
    try:
        from transformers import PreTrainedModel  # noqa: F401
        from tsfm_public import TinyTimeMixerForPrediction  # noqa: F401
    except Exception as e:  # noqa: BLE001
        print(f"[startup] ML pre-import skipped: {e}", flush=True)
    for mod_path in ("app.live.ttm_forecast", "app.live.ttm_battery_surge",
                     "app.live.floodnet_forecast", "app.context.entity_extract"):
        try:
            __import__(mod_path)
        except Exception as e:  # noqa: BLE001
            print(f"[startup] {mod_path} pre-import skipped: {type(e).__name__}: {e}", flush=True)


def _stones_pebbles_for_deployment(deployment_name: str | None):
    """Resolve (stones_registry, pebble_registry) for a deployment name.

    None → the server's boot-time deployment (back-compat). A bare name
    like 'boston' resolves to `deployments/boston/` regardless of which
    deployment the server booted with — this is what makes per-query
    routing reach the UI scaffold.
    """
    from pathlib import Path

    if not deployment_name:
        return _STONES, _PEBBLES
    from riprap.core.pebbles.deployments import deployment_by_name as _dep_by_name  # noqa: PLC0415

    dep = _dep_by_name(deployment_name)
    if dep is None:
        # Try treating as a path / fallback to boot deployment so the UI
        # never gets a 500 from a malformed query param.
        p = Path(deployment_name)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / deployment_name
        if not p.exists():
            return _STONES, _PEBBLES
        stones_root = p
    else:
        stones_root = dep.root
    return _load_stones(stones_root), _load_pebbles(stones_root)


@app.get("/api/pebbles")
def api_pebbles(deployment: str | None = None):
    """Return a deployment's stones + pebbles for evidence-card rendering.

    With per-query routing, the frontend MUST pass `?deployment=<name>`
    once the SSE stream resolves the deployment for a given query —
    otherwise the UI renders the server's boot-time scaffold (which
    e.g. lists NYC pebbles for a Boston run, the exact bug the user
    reported via the screenshot).

    Per-pebble payload is the manifest minus implementation guts (config /
    shaper / trace_summary / spatial.crs) — just the parts the UI needs to
    draw a card and show provenance. Shared with the MCP `list_sources`
    tool via `riprap.core.pebbles.describe`.
    """
    from riprap.core.pebbles.describe import describe_deployment

    stones_reg, pebble_reg = _stones_pebbles_for_deployment(deployment)
    return JSONResponse(describe_deployment(stones_reg, pebble_reg))


@app.get("/api/deployment")
def api_deployment(deployment: str | None = None):
    """Active-deployment descriptor for the UI shell.

    Returns the city + hazard names the chrome renders in the header
    chip + browser title. Pulled from each deployment's `stones.yaml`
    `deployment:` block (with sensible defaults derived from the
    deployment directory name when the block is absent).

    Without `?deployment`, returns the server's boot-time deployment
    (back-compat). With `?deployment=<name>` (e.g. `boston`), returns
    that deployment's descriptor — what the per-query header chip
    consumes once the SSE stream resolves the deployment for a query.
    """
    if not deployment:
        return JSONResponse(
            {
                "name": _DEPLOYMENT.name,
                "city": _STONES.city,
                "hazard": _STONES.hazard,
            }
        )
    stones_reg, _ = _stones_pebbles_for_deployment(deployment)
    return JSONResponse(
        {
            "name": deployment,
            "city": stones_reg.city,
            "hazard": stones_reg.hazard,
        }
    )


@app.post("/api/print")
async def api_print(request: Request) -> Response:
    """Render a completed briefing to PDF.

    Accepts the briefing JSON in the request body (the same shape the
    SSE stream emits as its final `final` event). Returns the PDF as
    `application/pdf` with a sensible filename. The document carries a
    SHA-256 hash on its stamp page that two reviewers comparing the
    same briefing can verify by.

    Requires WeasyPrint's system deps (pango + cairo) on the host:
      macOS:  brew install pango
      Linux:  apt-get install libpango-1.0-0 libpangoft2-1.0-0

    Returns 503 with a structured error body when the deps are missing
    so the UI can surface a helpful "PDF rendering unavailable" toast
    instead of a stack trace.
    """
    from app.print_pdf import PdfRenderFailed, render_briefing_pdf  # noqa: PLC0415

    try:
        payload = await request.json()
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "expected a JSON object body"}, status_code=400)

    # Annotate with active deployment so the cover-page chip reads
    # consistently with the web view, even if the client didn't post it.
    payload.setdefault(
        "deployment",
        {
            "name": _DEPLOYMENT.name,
            "city": _STONES.city,
            "hazard": _STONES.hazard,
        },
    )

    try:
        pdf_bytes = render_briefing_pdf(payload)
    except PdfRenderFailed as e:
        return JSONResponse(
            {"error": "pdf_unavailable", "detail": str(e)},
            status_code=503,
        )

    # Filename: <city>-<slug-of-address>.pdf. Browsers honor
    # Content-Disposition: attachment + the filename hint, while still
    # letting users preview in a new tab.
    addr = payload.get("query") or payload.get("address") or "briefing"
    slug = re.sub(r"[^a-z0-9]+", "-", str(addr).lower()).strip("-")[:60] or "briefing"
    fname = f"riprap-{slug}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{fname}"',
            # Don't cache user-specific renders.
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/backend")
async def api_backend():
    """LLM mode for the UI badge: `no_llm`, or the configured endpoints and
    whether the first one answers. No secrets."""
    import httpx

    from riprap.core import llm

    info = llm.describe()
    info["reachable"] = None
    if info["endpoints"]:
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                r = await client.get(info["endpoints"][0]["base_url"] + "/models")
            info["reachable"] = r.status_code in (200, 401)
        except Exception:
            info["reachable"] = False
    return JSONResponse(info)


@app.get("/")
def index():
    """SvelteKit landing page (the new design-system UI)."""
    sk = SVELTEKIT_BUILD / "index.html"
    if sk.exists():
        return FileResponse(sk)
    return JSONResponse(
        {"error": "sveltekit build not present — run `cd web/sveltekit && npm run build`"},
        status_code=503,
    )


@app.get("/q/sample")
def q_sample_page():
    """Legacy `/q/sample` route — used to serve a prerendered Red Hook
    demo briefing whose citations + numbers were fabricated. That violated
    the Plain Writing Act voice the rest of the surface now commits to,
    so the synthetic page was removed (see commit history). Redirect
    to a real anchor address that runs an actual briefing through the
    normal pipeline; CityPicker on the landing offers the same instant-
    click affordance for each shipped city.
    """
    from fastapi.responses import RedirectResponse  # noqa: PLC0415

    return RedirectResponse(
        url="/q/189%20Atlantic%20Avenue%2C%20Brooklyn%2C%20NY",
        status_code=308,
    )


@app.get("/q/{query_id}")
def q_query_page(query_id: str):  # noqa: ARG001 — captured for the SPA router
    """Live briefing route. Served by the SvelteKit SPA fallback (200.html);
    the client opens an EventSource to /api/agent/stream."""
    sk = SVELTEKIT_BUILD / "200.html"
    if sk.exists():
        return FileResponse(sk)
    return JSONResponse({"error": "sveltekit build not present"}, status_code=503)


@app.get("/print/{query_id}")
def print_page(query_id: str):  # noqa: ARG001 — captured by the SPA router
    """Curated print artifact for a completed briefing. The client
    hydrates from localStorage (key riprap:print:<query_id>) and
    auto-fires window.print() — no backend round-trip."""
    sk = SVELTEKIT_BUILD / "200.html"
    if sk.exists():
        return FileResponse(sk)
    return JSONResponse({"error": "sveltekit build not present"}, status_code=503)


@app.get("/api/register/{asset_class}")
def api_register(asset_class: str):
    """Return a pre-computed asset-class register."""
    if asset_class not in ("schools", "nycha", "mta_entrances"):
        return JSONResponse({"error": f"unknown asset class {asset_class!r}"}, status_code=404)
    f = ROOT.parent / "data" / "registers" / f"{asset_class}.json"
    if not f.exists():
        script = f"scripts/build_{asset_class}_register.py"
        return JSONResponse(
            {"error": f"register not built — run python {script}", "rows": []},
            status_code=503,
        )
    return JSONResponse(
        _json.loads(f.read_text()), headers={"Cache-Control": "public, max-age=300"}
    )


@app.get("/api/agent")
def api_agent(q: str):
    """One briefing as JSON: plan (LLM or regex), run the Burr app for the
    intent, return the full result. Used by MCP clients and scripts."""
    from riprap.core.burr.app import run as burr_run

    return JSONResponse(_to_json_safe(burr_run(q)))


_BATCH_MAX_ADDRESSES = 25


@app.post("/api/agent/batch")
async def api_agent_batch(request: Request) -> JSONResponse:
    """Run a single_address flood-exposure assessment over a list of
    addresses, one request in, one JSON array of briefings out.

    For a civic engineer or NGO checking a portfolio (a block of NYCHA
    buildings, a list of schools) rather than one address at a time —
    the single biggest gap for that audience, since every other route
    takes one query at a time.

    Body: {"addresses": ["123 Main St, Brooklyn", "456 Oak Ave, Queens"]}

    Runs sequentially, not concurrently: each address holds the local
    Ollama reconciler and the RAG/specialist stack, and this is one
    shared instance, not a pool. Capped at _BATCH_MAX_ADDRESSES to
    protect that shared instance from an unbounded request. One
    address's failure doesn't fail the batch — its slot in `results`
    carries an `error` key instead of a briefing.
    """
    try:
        payload = await request.json()
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    addresses = payload.get("addresses") if isinstance(payload, dict) else None
    if not isinstance(addresses, list) or not addresses:
        return JSONResponse(
            {"error": "expected a JSON object with a non-empty 'addresses' list"},
            status_code=400,
        )
    if not all(isinstance(a, str) and a.strip() for a in addresses):
        return JSONResponse({"error": "every address must be a non-empty string"}, status_code=400)
    if len(addresses) > _BATCH_MAX_ADDRESSES:
        return JSONResponse(
            {"error": f"batch size {len(addresses)} exceeds the max of {_BATCH_MAX_ADDRESSES}"},
            status_code=400,
        )

    from riprap.core.burr.app import run as burr_run  # noqa: PLC0415

    results = []
    for addr in addresses:
        try:
            results.append(_to_json_safe(burr_run(addr)))
        except Exception as e:  # noqa: BLE001
            results.append({"query": addr, "error": str(e)})

    return JSONResponse({"results": results, "n": len(results)})


@app.get("/api/agent/stream")
async def api_agent_stream(q: str):
    """SSE: `plan` once the planner finishes, a `step` event per finished
    pebble or pipeline step, then `final` with the full result. The run
    happens on a worker thread; events cross over through a queue."""
    import asyncio
    import queue

    out_q: queue.Queue[dict] = queue.Queue()

    def runner():
        try:
            from riprap.core import llm as core_llm
            from riprap.core.burr.app import energy_summary, iter_steps, plan_for, run_compare

            if core_llm.tier() == "no_llm":
                out_q.put({"kind": "plan_token", "delta": "[heuristic planner, no LLM call]"})
            plan = plan_for(q)
            out_q.put({"kind": "plan", "intent": plan["intent"], "targets": plan.get("targets"),
                       "question": plan.get("question"), "focus": plan.get("focus"),
                       "pebbles": plan.get("pebbles"), "specialists": [],
                       "rationale": plan.get("rationale")})

            def stream(query: str, sub_plan: dict, label: str | None = None) -> dict:
                final: dict = {}
                for ev in iter_steps(query, sub_plan):
                    if ev["kind"] == "final":
                        final = ev
                    elif label and ev["kind"] == "step":
                        out_q.put({**ev, "target_label": label})
                    else:
                        out_q.put(ev)
                final.pop("kind", None)
                return final

            if plan["intent"] == "compare":
                labels = iter(("PLACE A", "PLACE B"))
                final = run_compare(q, plan, runner=lambda qq, pp: stream(qq, pp, next(labels, None)))
            else:
                final = stream(q, plan)
            final["emissions"] = energy_summary(final, plan)
            out_q.put({"kind": "final", **final})
        except Exception as e:
            out_q.put({"kind": "error", "err": str(e)})
        finally:
            out_q.put({"kind": "_done"})

    async def event_stream():
        loop = asyncio.get_event_loop()
        loop.run_in_executor(_SSE_EXECUTOR, runner)
        yield f"event: hello\ndata: {json.dumps({'query': q})}\n\n"

        # Stone-boundary envelope: track current Stone so we can wrap
        # contiguous step events in stone_start / stone_done. step
        # events whose name maps to None (geocode, rag, gliner) flow
        # through without opening a Stone — those are orientation /
        # ancillary, not part of any data-Stone group.
        current_stone: str | None = None
        stone_step_count: dict[str, int] = {}

        def _open(stone: str) -> str:
            stone_step_count[stone] = 0
            payload = {**_STONE_META.get(stone, {"name": stone})}
            return f"event: stone_start\ndata: {json.dumps(payload)}\n\n"

        def _close(stone: str) -> str:
            payload = {
                **_STONE_META.get(stone, {"name": stone}),
                "n_steps": stone_step_count.get(stone, 0),
            }
            return f"event: stone_done\ndata: {json.dumps(payload)}\n\n"

        while True:
            try:
                ev = await asyncio.to_thread(out_q.get, True, 1.0)
            except Exception:
                # No event for 1 s — send an SSE comment so the HF Space
                # proxy doesn't close the idle connection (proxy idle timeout
                # is ~15-20 s; the reconciler's vLLM call can take longer).
                yield ": keepalive\n\n"
                continue
            kind = ev.get("kind")
            if kind == "_done":
                break

            # First reconcile token implies the data-Stones are done
            # and the Capstone has begun, even if the FSM step event
            # for reconcile hasn't fired yet (it fires AFTER the
            # generation finishes). Open Capstone here so the UI
            # shows it lighting up while tokens stream.
            if kind == "token" and current_stone != "Capstone":
                if current_stone is not None:
                    yield _close(current_stone)
                current_stone = "Capstone"
                yield _open(current_stone)

            if kind == "step":
                step_name = ev.get("step") or ""
                # Per-query routing handshake — when the pipeline
                # resolves the deployment, push it to the UI so the
                # header chip + pebble scaffold can pivot off the
                # deployment that actually fanned out, not whatever
                # the server booted with.
                if step_name == "select_deployment":
                    result = ev.get("result") or {}
                    dep_name = result.get("deployment")
                    yield (
                        "event: deployment\n"
                        f"data: {json.dumps({'name': dep_name, 'city': result.get('city'), 'state': result.get('state')})}\n\n"
                    )
                stone = _STEP_TO_STONE.get(step_name)
                if stone is not None:
                    if stone != current_stone:
                        if current_stone is not None:
                            yield _close(current_stone)
                        current_stone = stone
                        yield _open(current_stone)
                    stone_step_count[stone] = stone_step_count.get(stone, 0) + 1

            # `final` arrives after the Capstone has produced its
            # paragraph. Close the Capstone before forwarding final
            # so the trace cleanly reads: ... stone_done(Capstone),
            # final, done.
            if kind == "final" and current_stone is not None:
                yield _close(current_stone)
                current_stone = None

            yield f"event: {kind}\ndata: {json.dumps(ev, default=str)}\n\n"

        # Pipeline ended without a final (error / abort) — close any
        # still-open Stone so the client doesn't render an unbounded
        # parent row.
        if current_stone is not None:
            yield _close(current_stone)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/district/{code}")
def api_district(code: str, no_llm: bool = False):
    """Evidence summary for an NYC community district (QN12, BK15): the
    neighbourhood pipeline over the union of the district's NTAs."""
    from riprap.core.burr.app import district_summary

    return JSONResponse(_to_json_safe(district_summary(code, no_llm=no_llm)))


@app.get("/api/nyc311/flood_requests")
def api_nyc311_flood_requests(lat: float | None = None, lon: float | None = None,
                              radius_m: float = 200, community_district: str | None = None,
                              days: int = 365):
    """Flood-related 311 requests near a point or inside a community district."""
    from app.context.nyc311 import flood_requests

    out = flood_requests(lat=lat, lon=lon, radius_m=radius_m,
                         community_district=community_district, days=days)
    return JSONResponse(out, status_code=400 if "error" in out else 200)


@app.get("/api/agent/plan")
def api_agent_plan(q: str):
    """Just the plan (intent and targets), no execution."""
    from riprap.core.burr.app import plan_for

    return JSONResponse(plan_for(q))


@app.get("/api/layers/nta")
def layer_nta(code: str):
    """Return the NTA polygon for a given NTA code as GeoJSON (EPSG:4326)."""
    from app.areas import nta as nta_mod

    g = nta_mod.load()
    sub = g[g["nta2020"] == code][["nta2020", "ntaname", "boroname", "geometry"]]
    if sub.empty:
        return JSONResponse({"type": "FeatureCollection", "features": []}, status_code=404)
    return JSONResponse(
        _json.loads(sub.to_json()), headers={"Cache-Control": "public, max-age=3600"}
    )


@app.get("/api/layers/sandy_clipped")
def layer_sandy_clipped(code: str):
    """Sandy inundation polygons clipped to an NTA bbox + simplified.
    Used by the agent map for neighborhood / development_check intents."""
    from app.areas import nta as nta_mod
    from app.flood_layers import sandy_inundation

    poly = nta_mod.polygon_for(code)
    if poly is None:
        return JSONResponse({"type": "FeatureCollection", "features": []})
    bounds = poly.bounds
    cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    # bbox half-extent in metres ~ half the polygon span × 111 km/deg
    half_m = max((bounds[2] - bounds[0]), (bounds[3] - bounds[1])) / 2 * 111_000
    return JSONResponse(
        _clip_simplify(sandy_inundation.load(), cy, cx, half_m * 1.2),
        headers={"Cache-Control": "public, max-age=600"},
    )


@app.get("/api/layers/dep_clipped")
def layer_dep_clipped(code: str, scenario: str = "dep_extreme_2080"):
    """DEP scenario polygons clipped to an NTA bbox + simplified."""
    from app.areas import nta as nta_mod
    from app.flood_layers import dep_stormwater

    poly = nta_mod.polygon_for(code)
    if poly is None:
        return JSONResponse({"type": "FeatureCollection", "features": []})
    bounds = poly.bounds
    cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    half_m = max((bounds[2] - bounds[0]), (bounds[3] - bounds[1])) / 2 * 111_000
    return JSONResponse(
        _clip_simplify(
            dep_stormwater.load(scenario), cy, cx, half_m * 1.2, props_keep={"Flooding_Category"}
        ),
        headers={"Cache-Control": "public, max-age=600"},
    )


@app.get("/api/layers/sandy")
def layer_sandy(lat: float, lon: float, r: float = 1500):
    key = ("sandy", round(lat, 4), round(lon, 4), int(r))
    if key not in _LAYER_CACHE:
        _LAYER_CACHE[key] = _clip_simplify(sandy_inundation.load(), lat, lon, r)
    return JSONResponse(_LAYER_CACHE[key], headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/layers/dep_extreme_2080")
def layer_dep_2080(lat: float, lon: float, r: float = 1500):
    key = ("dep2080", round(lat, 4), round(lon, 4), int(r))
    if key not in _LAYER_CACHE:
        _LAYER_CACHE[key] = _clip_simplify(
            dep_stormwater.load("dep_extreme_2080"), lat, lon, r, props_keep={"Flooding_Category"}
        )
    return JSONResponse(_LAYER_CACHE[key], headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/layers/prithvi_water")
def layer_prithvi_water(lat: float, lon: float, r: float = 1500):
    """New surface water after Ida from the Prithvi-EO batch (experimental):
    the new-water pixels of data/eo/ within `r` m of the address, as polygons."""
    key = ("prithvi", round(lat, 4), round(lon, 4), int(r))
    if key not in _LAYER_CACHE:
        from app.flood_layers import prithvi_water as pw

        _LAYER_CACHE[key] = pw.layer_geojson(lat, lon, r)
    return JSONResponse(_LAYER_CACHE[key], headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/layers/ida_hwm")
def layer_ida_hwm(lat: float, lon: float, r: float = 1500):
    """USGS Hurricane Ida 2021 high-water marks within radius_m of (lat, lon).
    Returns GeoJSON FeatureCollection of Point features. No geopandas needed —
    HWMs are already points so haversine filter is sufficient."""
    from app.flood_layers import ida_hwm as _ida

    features = []
    for f in _ida._load():
        flon, flat = f["geometry"]["coordinates"]
        d = _ida._haversine_m(lat, lon, flat, flon)
        if d <= r:
            p = f["properties"]
            features.append(
                {
                    "type": "Feature",
                    "geometry": f["geometry"],
                    "properties": {
                        "hwm_id": p.get("hwm_id"),
                        "site_description": p.get("site_description"),
                        "elev_ft": p.get("elev_ft"),
                        "height_above_gnd_ft": p.get("height_above_gnd"),
                        "hwm_quality": p.get("hwm_quality"),
                        "waterbody": p.get("waterbody"),
                        "distance_m": round(d, 0),
                    },
                }
            )
    return JSONResponse(
        {"type": "FeatureCollection", "features": features},
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/floodnet_near")
def floodnet_near(lat: float, lon: float, r: float = 1000):
    sensors = floodnet.sensors_near(lat, lon, r)
    ids = [s.deployment_id for s in sensors]
    events = floodnet.flood_events_for(ids)
    by_dep: dict = {}
    for e in events:
        by_dep.setdefault(e.deployment_id, []).append(e)

    features = []
    for s in sensors:
        if s.lat is None or s.lon is None:
            continue
        evs = by_dep.get(s.deployment_id, [])
        peak = max((e.max_depth_mm or 0 for e in evs), default=0)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
                "properties": {
                    "deployment_id": s.deployment_id,
                    "name": s.name,
                    "street": s.street,
                    "borough": s.borough,
                    "n_events_3y": len(evs),
                    "peak_depth_mm": peak,
                },
            }
        )
    return JSONResponse({"type": "FeatureCollection", "features": features})
