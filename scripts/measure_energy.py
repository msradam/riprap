"""Measure whole-machine energy per briefing on an Apple Silicon Mac, no sudo.

    uv run python scripts/measure_energy.py --base http://127.0.0.1:7862 \
        --queries tests/golden/seen.json --idle-s 180

The SMC publishes PowerTelemetryData in ioreg: an accumulator of system
power-in samples (mW) and a sample count. The mean power over an interval
is the accumulator delta over the count delta, so the energy over the
interval is that mean times the wall time. The block refreshes about once
a minute, so an interval shorter than a few minutes has coarse resolution;
the script prints the sample counts so the reader can judge it.

It records an idle window first, then runs the queries one after another
against the server, and prints Wh per briefing gross (everything the
machine drew) and net of idle. Both are whole-machine figures: close other
work before running it.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request

_ACC = re.compile(r'"AccumulatedSystemPowerIn"=(\d+)')
_CNT = re.compile(r'"SystemPowerInAccumulatorCount"=(\d+)')


def telemetry() -> tuple[int, int]:
    """(accumulated mW samples, sample count) from the SMC."""
    out = subprocess.run(["ioreg", "-rn", "AppleSmartBattery"], capture_output=True, text=True,
                         check=True).stdout
    acc, cnt = _ACC.search(out), _CNT.search(out)
    if not acc or not cnt:
        raise SystemExit("no PowerTelemetryData in ioreg: not an Apple Silicon Mac laptop?")
    return int(acc.group(1)), int(cnt.group(1))


def _next_publish(count: int) -> tuple[int, int]:
    """Block until the SMC publishes a batch past `count`."""
    while True:
        a, c = telemetry()
        if c != count:
            return a, c
        time.sleep(1)


def window(label: str, work) -> dict:
    """Run `work()` inside a window aligned to the accumulator's batches.
    The SMC samples once a second and publishes about sixty samples at a
    time, so the window opens on a publish, and closes on the first publish
    that covers the whole run plus one more batch; the sample count is the
    clock, so the energy is exact over those samples."""
    a0, c0 = _next_publish(telemetry()[1])
    t0 = time.time()
    n = work()
    ran = time.time() - t0
    a1, c1 = telemetry()
    while c1 - c0 < ran + 60:
        a1, c1 = _next_publish(c1)
    seconds = c1 - c0
    mean_w = (a1 - a0) / seconds / 1000
    return {"label": label, "seconds": seconds, "ran_s": round(ran, 1), "n": n,
            "mean_w": round(mean_w, 2), "wh": round(mean_w * seconds / 3600, 3)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:7862")
    ap.add_argument("--queries", default="tests/golden/seen.json")
    ap.add_argument("--kinds", default="question,address")
    ap.add_argument("--idle-s", type=int, default=180)
    ap.add_argument("--repeat", type=int, default=1, help="run the query list this many times")
    a = ap.parse_args()
    queries = [e["query"] for e in json.load(open(a.queries)) if e["kind"] in a.kinds.split(",")] * a.repeat

    idle = window("idle", lambda: (time.sleep(a.idle_s), 0)[1])
    print(f"  idle {idle['mean_w']} W over {idle['seconds']} s", flush=True)

    def run_all() -> int:
        for q in queries:
            url = a.base + "/api/agent?" + urllib.parse.urlencode({"q": q})
            with urllib.request.urlopen(url, timeout=900) as r:
                d = json.load(r)
            em = d.get("emissions") or {}
            print(f"  {q[:60]:60} {d.get('intent'):16} calls {em.get('n_calls')} "
                  f"tokens {(em.get('tokens') or {}).get('total')}", flush=True)
        return len(queries)

    run = window("briefings", run_all)
    # Net of idle: the machine's idle draw over the same seconds, taken off.
    net_wh = (run["mean_w"] - idle["mean_w"]) * run["seconds"] / 3600
    print(json.dumps({"idle": idle, "briefings": run,
                      "per_briefing": {"wall_s": round(run["ran_s"] / run["n"], 1),
                                       "wh_gross": round(run["wh"] / run["n"], 3),
                                       "wh_net_of_idle": round(net_wh / run["n"], 3)},
                      "method": "SMC PowerTelemetryData accumulator read with ioreg (no sudo), whole "
                                "machine, windows aligned to the SMC's one-minute batches; the idle "
                                "window's mean power over the same seconds is taken off for the net figure"},
                     indent=1))


if __name__ == "__main__":
    main()
