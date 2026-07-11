"""One-shot demo pre-warm on Modal's own scheduler (laptop-independent).

Fires once at 13:53 UTC (09:53 America/New_York, EDT) on the demo date, so the
stack is warm for a 10:00 ET demo without needing a laptop awake or a Claude
session open. Warms the GPU first (so the planner's first call does not hit a
cold vLLM), then fires one throwaway query to pay the frontend lazy-load.

Deploy:  modal deploy modal/demo_prewarm.py --env riprap
Remove:  modal app stop riprap-demo-prewarm --env riprap --yes

Date-gated to DEMO_DATE: on any other day the cron fires but no-ops (~$0). The
main riprap-frontend + riprap-triton apps must be deployed for this to warm them.
"""
from __future__ import annotations

import datetime
import os
import time

import modal

app = modal.App("riprap-demo-prewarm")

_GPU_HEALTHZ = "https://msradam-riprap--riprap-triton-riprap-proxy.modal.run/healthz"
_FRONTEND_STREAM = "https://msradam-riprap--riprap-frontend-web-app.modal.run/api/agent/stream"
DEMO_DATE = datetime.date(2026, 6, 8)
WARM_QUERY = "80 Pioneer Street, Red Hook, Brooklyn"


@app.function(
    image=modal.Image.debian_slim().pip_install("httpx"),
    # 13:53 UTC = 09:53 America/New_York (EDT). Cold warm + frontend lazy-load
    # (~5 min) finishes by ~09:58, warm through a 10:00 ET first query.
    schedule=modal.Cron("53 13 * * *"),
    secrets=[modal.Secret.from_name("riprap-stack")],
    timeout=900,
)
def prewarm() -> None:
    import httpx

    today = datetime.datetime.now(datetime.timezone.utc).date()
    if today != DEMO_DATE:
        print(f"[prewarm] {today} is not the demo day {DEMO_DATE} - skipping", flush=True)
        return

    tok = os.environ["RIPRAP_PROXY_TOKEN"]

    # 1) Warm the GPU first. LLM mode hard-fails if the planner's first call
    #    hits a cold vLLM, so the throwaway query below must run on a warm GPU.
    healthy = False
    for i in range(30):
        try:
            r = httpx.get(_GPU_HEALTHZ, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
            if r.status_code == 200 and r.json().get("vllm") == "ok":
                print(f"[prewarm] GPU healthy after {i + 1} checks: {r.text[:160]}", flush=True)
                healthy = True
                break
        except Exception as e:  # noqa: BLE001
            print(f"[prewarm] healthz {i + 1}: {e}", flush=True)
        time.sleep(8)
    if not healthy:
        print("[prewarm] GPU not confirmed healthy; firing warm query anyway", flush=True)

    # 2) Throwaway query: pays the frontend lazy-load (rasters + embedding model)
    #    so the first audience query is fast.
    try:
        r = httpx.get(_FRONTEND_STREAM, params={"q": WARM_QUERY}, timeout=420)
        ok = "event: final" in r.text
        print(f"[prewarm] frontend warm query http={r.status_code} bytes={len(r.content)} final={ok}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[prewarm] frontend query error: {e}", flush=True)
