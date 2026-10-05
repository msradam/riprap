"""The one HTTP client every data adapter uses.

  * timeouts: 5 s to connect, 20 s to read, unless a call asks for more;
  * caching: hishel stores successful responses in a local SQLite file and
    serves them for `ttl_s` seconds (default 600, 10 minutes, for live
    sources) whatever the upstream cache headers say; POST bodies are part
    of the key, so GraphQL queries cache per query. A 200 the caller finds
    to be a failure (an empty body, an error object) is dropped with
    `forget`, so it is not served again for the rest of its TTL;
  * retries: stamina retries transport errors, 429 and 5xx with backoff
    and jitter, 3 attempts within 30 s. 4xx responses are returned to the
    caller, which decides what they mean.

RIPRAP_HTTP_CACHE sets the cache file (default ~/.cache/riprap/http.sqlite);
RIPRAP_HTTP_CACHE_TTL_S the default TTL; RIPRAP_HTTP_CACHE=off disables it.
"""

from __future__ import annotations

import functools
import hashlib
import os
import sqlite3
from pathlib import Path

import hishel
import httpx
import stamina
from hishel.httpx import SyncCacheTransport

# A product token and nothing that names a person: no repository URL (it carries the owner's handle), no
# email. The Weather Service asks for "a string that is unique to your application", and OSM's Nominatim
# policy for an identifying application name; a product name meets both.
USER_AGENT = "Riprap/0.9 (civic flood-evidence tool)"
DEFAULT_TTL_S = float(os.environ.get("RIPRAP_HTTP_CACHE_TTL_S", "600"))
TIMEOUT = httpx.Timeout(20.0, connect=5.0)


class _OkOnly(hishel.BaseFilter[hishel.Response]):
    def needs_body(self) -> bool:
        return False

    def apply(self, item: hishel.Response, body: bytes | None) -> bool:
        return item.status_code == 200


_STORAGE: list = []  # the cache storage of client(), for forget()


@functools.cache
def client() -> httpx.Client:
    setting = os.environ.get("RIPRAP_HTTP_CACHE", "")
    transport: httpx.BaseTransport = httpx.HTTPTransport()
    if setting.lower() != "off":
        path = Path(setting or Path.home() / ".cache" / "riprap" / "http.sqlite")
        path.parent.mkdir(parents=True, exist_ok=True)
        # The Stones fan-out calls this client from many threads.
        conn = sqlite3.connect(path, check_same_thread=False)
        storage = hishel.SyncSqliteStorage(connection=conn, default_ttl=DEFAULT_TTL_S)
        policy = hishel.FilterPolicy(response_filters=[_OkOnly()])
        policy.use_body_key = True
        transport = SyncCacheTransport(transport, storage=storage, policy=policy)
        _STORAGE[:] = [storage]
    return httpx.Client(transport=transport, timeout=TIMEOUT, follow_redirects=True,
                        headers={"User-Agent": USER_AGENT})


@functools.cache
def uncached_client() -> httpx.Client:
    """For responses that may hold personal data (311 free text): never
    written to the cache file."""
    return httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


@stamina.retry(on=_retryable, attempts=3, timeout=30.0)
def request(method: str, url: str, *, ttl_s: float | None = None, store: bool = True,
            **kwargs) -> httpx.Response:
    """Send a request through the shared client. `ttl_s` overrides the
    cache lifetime for this call (0 disables caching for it). With
    store=False the response never touches the cache file."""
    if not store:
        resp = uncached_client().request(method, url, **kwargs)
        if resp.status_code == 429 or resp.status_code >= 500:
            resp.raise_for_status()
        return resp
    extensions = dict(kwargs.pop("extensions", None) or {})
    extensions["hishel_ttl"] = DEFAULT_TTL_S if ttl_s is None else ttl_s
    if ttl_s == 0:
        extensions["hishel_ttl"] = 0.001
    resp = client().request(method, url, extensions=extensions, **kwargs)
    if resp.status_code == 429 or resp.status_code >= 500:
        resp.raise_for_status()
    return resp


def forget(resp: httpx.Response) -> None:
    """Drop a response from the cache. For a caller that finds an HTTP 200
    to be a failure: FEMA's map service answers some failures with 200 and
    an empty body, which was then served from the cache for a day."""
    if not _STORAGE:
        return
    req = resp.request
    # The key hishel files an entry under with use_body_key: the hash of the request body.
    for entry in _STORAGE[0].get_entries(hashlib.sha256(req.content).hexdigest()):
        if str(entry.request.url) == str(req.url) and entry.request.method == req.method:
            _STORAGE[0].remove_entry(entry.id)


def get(url: str, **kwargs) -> httpx.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> httpx.Response:
    return request("POST", url, **kwargs)
