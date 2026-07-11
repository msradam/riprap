"""Real Apple Silicon power readings for the Mac Mini deployment.

`powermetrics` needs root, so it can't be shelled out to per-call from the
app process. Instead an operator runs it once, continuously, as its own
root process, appending text samples to a log file:

    sudo powermetrics -i 200 --samplers cpu_power,gpu_power,ane_power \
        -o /tmp/riprap-powermetrics.log

Set RIPRAP_POWERMETRICS_LOG to that path and this module tails it from an
unprivileged thread, parsing the "Combined Power (CPU + GPU + ANE)" line
out of each sample block. `read_instant_w()` mirrors `llm._sample_gpu_power_w`
(the NVML proxy reader) closely enough that `llm.py` can bracket a call with
it the same way — real measured watts when the log is fresh, None otherwise
so the caller falls back to the data-sheet estimate.
"""

from __future__ import annotations

import os
import re
import threading
import time

_COMBINED_RE = re.compile(r"Combined Power \(CPU \+ GPU \+ ANE\):\s*(\d+(?:\.\d+)?)\s*mW")
_STALE_S = 5.0

_lock = threading.Lock()
_last_w: float | None = None
_last_seen: float = 0.0
_started = False


def _tail(path: str) -> None:
    global _last_w, _last_seen
    while not os.path.exists(path):
        time.sleep(1.0)
    with open(path, errors="replace") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            m = _COMBINED_RE.search(line)
            if m:
                with _lock:
                    _last_w = float(m.group(1)) / 1000.0
                    _last_seen = time.monotonic()


def _ensure_started() -> None:
    global _started
    if _started:
        return
    path = os.environ.get("RIPRAP_POWERMETRICS_LOG")
    if not path:
        _started = True  # nothing to start; stay a permanent no-op
        return
    threading.Thread(target=_tail, args=(path,), daemon=True, name="powermetrics-tail").start()
    _started = True


def read_instant_w() -> float | None:
    """Latest Combined Power reading in watts, or None if the sampler
    isn't configured, hasn't produced a sample yet, or has gone stale
    (log stopped being written — treat as no measurement rather than
    reporting a frozen number)."""
    _ensure_started()
    with _lock:
        if _last_w is None:
            return None
        if time.monotonic() - _last_seen > _STALE_S:
            return None
        return _last_w


def avg_w(p0: float | None, p1: float | None) -> float | None:
    """Mean of a before/after power-sample bracket around a call; falls
    back to whichever single sample is available, or None if both failed.
    Shared by llm.py and inference.py so both bracket calls the same way."""
    pair = [p for p in (p0, p1) if p is not None]
    if not pair:
        return None
    return sum(pair) / len(pair)
