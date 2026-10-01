"""Riprap web UI — FastAPI + SSE streaming of the Burr FSM trace.

Run: uvicorn web.main:app --reload --port 8000
"""

from __future__ import annotations

import functools
import json
import os
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore")

from fastapi import FastAPI, Query, Request  # noqa: E402
from fastapi.responses import (  # noqa: E402
    FileResponse,
    JSONResponse,
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

ROOT = Path(__file__).resolve().parent
SVELTEKIT_BUILD = ROOT / "sveltekit" / "build"

app = FastAPI(title="Riprap")

import geopandas as _gpd  # noqa: E402


@functools.lru_cache(maxsize=256)
def _layer(kind: str, lat: float, lon: float, r: int) -> dict:
    """Clipped map layers keyed by rounded position; the routes below
    round before calling so nearby requests share an entry."""
    if kind == "sandy":
        return _clip_simplify(sandy_inundation.load(), lat, lon, r)
    if kind == "dep2080":
        return _clip_simplify(
            dep_stormwater.load("dep_extreme_2080"), lat, lon, r, props_keep={"Flooding_Category"}
        )
    raise ValueError(f"unknown layer {kind!r}")


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
    return json.loads(g.to_json())


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
    if os.environ.get("RIPRAP_WARM", "").lower() in ("1", "true", "yes"):
        # Ping the LLM now, so the first question of a demo is not the cold one.
        from app.models_info import warm

        print(f"[startup] warm (seconds, -1 = skipped): {warm()}", flush=True)


def _stones_pebbles_for_deployment(deployment_name: str | None):
    """(stones registry, pebble registry) for a deployment name, or None
    for a name that is not a shipped deployment. No name means the
    server's boot-time deployment; a name such as 'chicago' resolves to
    `deployments/chicago/` whichever deployment the server booted with."""
    if not deployment_name:
        return _STONES, _PEBBLES
    from riprap.core.pebbles.deployments import deployment_by_name as _dep_by_name  # noqa: PLC0415

    dep = _dep_by_name(deployment_name)
    return (_load_stones(dep.root), _load_pebbles(dep.root)) if dep else None


def _unknown_deployment(name: str) -> JSONResponse:
    from riprap.core.pebbles.deployments import discover_deployments  # noqa: PLC0415

    return JSONResponse({"error": f"unknown deployment {name!r}",
                         "known": sorted(d.name for d in discover_deployments())}, status_code=404)


@app.get("/api/pebbles")
def api_pebbles(deployment: str | None = None):
    """Return a deployment's stones + pebbles for evidence-card rendering.

    With per-query routing, the frontend MUST pass `?deployment=<name>`
    once the SSE stream resolves the deployment for a given query.
    Otherwise the UI renders the server's boot-time scaffold, which
    lists NYC pebbles for a Chicago run.

    Per-pebble payload is the manifest minus implementation guts (config /
    shaper / trace_summary / spatial.crs) — just the parts the UI needs to
    draw a card and show provenance. Shared with the MCP `list_sources`
    tool via `riprap.core.pebbles.describe`.
    """
    from riprap.core.pebbles.describe import describe_deployment

    found = _stones_pebbles_for_deployment(deployment)
    if found is None:
        return _unknown_deployment(deployment)
    return JSONResponse(describe_deployment(*found))


@app.get("/api/deployment")
def api_deployment(deployment: str | None = None):
    """Active-deployment descriptor for the UI shell.

    Returns the city + hazard names the chrome renders in the header
    chip + browser title. Pulled from each deployment's `stones.yaml`
    `deployment:` block (with sensible defaults derived from the
    deployment directory name when the block is absent).

    Without `?deployment`, returns the server's boot-time deployment
    (back-compat). With `?deployment=<name>` (e.g. `chicago`), returns
    that deployment's descriptor, which the per-query header chip
    reads once the SSE stream resolves the deployment for a query.
    """
    if not deployment:
        return JSONResponse(
            {
                "name": _DEPLOYMENT.name,
                "city": _STONES.city,
                "hazard": _STONES.hazard,
                "experimental": _STONES.experimental,
            }
        )
    found = _stones_pebbles_for_deployment(deployment)
    if found is None:
        return _unknown_deployment(deployment)
    stones_reg, _ = found
    return JSONResponse(
        {
            "name": deployment,
            "city": stones_reg.city,
            "hazard": stones_reg.hazard,
            "experimental": stones_reg.experimental,
        }
    )


@app.get("/api/models")
def api_models():
    """The experimental models this server can use and the LLM endpoint
    configured. Each briefing's own list is the `models` field of its
    result."""
    from app.models_info import loaded

    return loaded()


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
    """The baked register for a class: every public school or NYCHA
    development inside the Sandy zone or a DEP scenario, with its flags,
    and those outside the Sandy outline but within 50 m of it
    (`near_sandy_edge`), which are named in a briefing and not counted as
    exposed."""
    if asset_class not in ("schools", "nycha"):
        return JSONResponse({"error": f"unknown asset class {asset_class!r}"}, status_code=404)
    f = ROOT.parent / "data" / "registers" / f"{asset_class}.json"
    if not f.exists():
        script = f"scripts/build_register.py {asset_class}"
        return JSONResponse(
            {"error": f"register not built — run python {script}", "rows": []},
            status_code=503,
        )
    return JSONResponse(
        json.loads(f.read_text()), headers={"Cache-Control": "public, max-age=300"}
    )


@app.get("/api/agent")
def api_agent(q: str = Query(min_length=1)):
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

    Runs sequentially, not concurrently: every address uses the same
    upstream data APIs and, when one is configured, the same LLM
    endpoint. Capped at _BATCH_MAX_ADDRESSES so one request cannot hold
    them without bound. One address's failure doesn't fail the batch:
    its slot in `results` carries an `error` key instead of a briefing.
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
            from riprap.core.burr.app import energy_summary, iter_steps, plan_for, run_compare

            plan = plan_for(q)
            out_q.put({"kind": "plan", "intent": plan["intent"], "targets": plan.get("targets"),
                       "question": plan.get("question"), "focus": plan.get("focus"),
                       "pebbles": plan.get("pebbles"), "rationale": plan.get("rationale")})

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

        while True:
            try:
                ev = await asyncio.to_thread(out_q.get, True, 1.0)
            except Exception:
                # No event for a second: an SSE comment keeps an idle
                # connection open through a proxy while a source or the LLM is slow.
                yield ": keepalive\n\n"
                continue
            kind = ev.get("kind")
            if kind == "_done":
                break
            if kind == "step" and ev.get("step") == "select_deployment":
                # The deployment the query routed to, so the header chip and the
                # source scaffold show that city and not the server's default.
                result = ev.get("result") or {}
                yield ("event: deployment\n"
                       f"data: {json.dumps({'name': result.get('deployment'), 'city': result.get('city'), 'state': result.get('state')})}\n\n")
            yield f"event: {kind}\ndata: {json.dumps(ev, default=str)}\n\n"
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
    from riprap.core.burr.place import parse_district

    found, refusal = parse_district(code)
    if not found:
        return JSONResponse({"error": refusal or f"{code!r} is not a community district code such as QN12"},
                            status_code=404)
    return JSONResponse(_to_json_safe(district_summary(found, no_llm=no_llm)))


@app.get("/api/nyc311/flood_requests")
def api_nyc311_flood_requests(lat: float | None = None, lon: float | None = None,
                              radius_m: float = 200, community_district: str | None = None,
                              days: int = 365):
    """Flood-related 311 requests near a point or inside a community district."""
    from app.context.nyc311 import flood_requests

    out = flood_requests(lat=lat, lon=lon, radius_m=radius_m,
                         community_district=community_district, days=days)
    return JSONResponse(out, status_code=400 if "error" in out else 200)


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
    layer = _layer("sandy", round(lat, 4), round(lon, 4), int(r))
    return JSONResponse(layer, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/layers/dep_extreme_2080")
def layer_dep_2080(lat: float, lon: float, r: float = 1500):
    layer = _layer("dep2080", round(lat, 4), round(lon, 4), int(r))
    return JSONResponse(layer, headers={"Cache-Control": "public, max-age=3600"})


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


# The SvelteKit build (adapter-static): index.html at /, the prerendered
# gallery at /gallery/<slug>/, /_app assets, favicons, robots.txt and
# 404.html for anything else. Mounted last so every API route above wins;
# /q/* and /print/* above serve the 200.html SPA fallback.
if SVELTEKIT_BUILD.exists():
    app.mount("/", StaticFiles(directory=SVELTEKIT_BUILD, html=True), name="site")
