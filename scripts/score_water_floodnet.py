"""One fair test of the satellite water layer: floods a satellite can see
(experimental, one-off).

Hurricane Ida drained before any satellite passed, so missing it says little
about the layer. FloodNet street sensors log flood events with start and end
times, so for every Sentinel-1 and Sentinel-2 pass over the city this script
asks which sensors were under water at that instant (a "positive moment"),
and then whether a model's water lies near them more often than near the same
sensors on dry passes of the same orbit and season ("negative moments").

Step 1 (no model): the table of moments. Pre-registered rule: fewer than 10
positive moments on fewer than 3 distinct dates, after the clear-sky filter,
is "too few moments to tell" and nothing else runs.

Step 2: two models on a 2.56 km box around each sensor.
  * Prithvi NYC Pluvial (app/eo/prithvi.py), Sentinel-2 moments only: new
    water as scripts/run_eo_batch.py computes it (water in the event scene,
    not water in a dry reference scene, both clear).
  * TerraMind-base-Flood, loaded and normalised by scripts/run_flood_ida.py:
    four dates of Sentinel-2 L2A, Sentinel-1 RTC in dB and the Copernicus
    DEM. The event image of the moment's own satellite is the pass at the
    moment; the other satellite's is its nearest pass, which is hours or days
    off. The other three dates are dry passes of the same orbit. The +1000
    offset of Sentinel-2 processing baseline 04.00 and later is removed, as
    ImpactMesh's own values have it removed.
A hit is model water within 100 m of the sensor (50 and 250 m also reported),
on land (inside a neighbourhood tabulation area) that the Sentinel-2 scene
classification of the dry "just before" scene does not call water.

Step 3: Microsoft AI for Good's precomputed Sentinel-1 flood detections
(Hugging Face dataset ai-for-good-lab/ai4g-flood-dataset, MIT, October 2014
to September 2024), scored the same way at the Sentinel-1 moments they cover.

    uv run python scripts/score_water_floodnet.py            # step 1
    uv run python scripts/score_water_floodnet.py --inputs   # pick negatives and scenes, fetch them
    python3 gpu_lock.py uv run python scripts/score_water_floodnet.py --models

Every stage rewrites two files. The full result, with every moment, its
sensor, event times and depth, goes to outputs/water_coastal/ (git-ignored):
FloodNet's Data Access License Agreement forbids reposting the data in part
or in its entirety, so those rows are never committed. The aggregate result
(counts, rates and the verdict, with no per-event or per-sensor record) goes
to data/experimental/water_coastal_floodnet_summary.json. FloodNet data is
CC BY-NC-SA 4.0: FloodNet (New York University and The City University of
New York); Mydlarz et al. (2024), https://doi.org/10.1029/2023WR036806.
FloodNet responses, scene lists, scenes and model outputs are cached under
outputs/water_coastal/ too and never fetched twice; delete that folder to
start over.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
import threading
import time
from bisect import bisect_right
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_eo_batch as eo  # noqa: E402
import run_flood_ida as flood  # noqa: E402

from app.context import floodnet  # noqa: E402
from app.eo import prithvi  # noqa: E402

CACHE = ROOT / "outputs" / "water_coastal"
RAW = CACHE / "water_coastal_floodnet.json"  # per-event rows: git-ignored, never committed
OUT = ROOT / "data" / "experimental" / "water_coastal_floodnet_summary.json"
SINCE = "2020-10-01"  # the first sensor was deployed on 2020-10-05
S1, S2 = "sentinel-1-rtc", "sentinel-2-l2a"
PX, RADII, SEED, NEGATIVES = 256, (50, 100, 250), 20261002, 5  # SEED is quoted in METHOD
DAY = timedelta(days=1)
RULE = ("Fewer than 10 positive moments on fewer than 3 distinct dates across both satellites, after the clear-sky "
        "filter, is 'too few moments to tell'. Otherwise a model shows skill when, at 100 m, it has at least 5 hits "
        "on at least 2 distinct dates, a hit rate at least twice the false-alarm rate, and a one-sided Fisher exact "
        "p below 0.05. The verdict is 'skill' when either model shows it.")
METHOD = {
    "positive": "a FloodNet event labelled flood spans the pass time, at a sensor in good working order that was "
                "deployed, inside the scene's footprint and reporting within 15 minutes; for Sentinel-2 the scene "
                "classification at the sensor is clear",
    "negative": "five passes per positive of the same sensor, satellite and relative orbit, with no flood event within "
                "three hours, a reading of zero within 15 minutes and (Sentinel-2) a clear view; within 45 days of the "
                "positive's day of the year where there are enough; seeded random order",
    "hit": "model water within the radius of the sensor on a 10 m grid, on land (inside a neighbourhood tabulation "
           "area) that the scene classification of the dry Sentinel-2 scene just before does not call water",
    "box": "2.56 km square of 10 m pixels around the sensor; gaps at tile and slice edges filled from the same pass",
    "radar": "8 HH and HV scenes are left out; Sentinel-1 RTC passes only",
    "seed": 20261002,
}
ITEMS: dict[str, dict] = {}  # STAC item dicts by id
PASS: dict[str, list[str]] = {}  # an item, then the other tiles or slices of its pass


def gql(query: str, variables: dict | None = None) -> dict:
    """A FloodNet query, answered from the cache when it has been asked
    before; a second's pause before every request that goes out."""
    import httpx

    f = CACHE / "floodnet" / (hashlib.sha256(json.dumps([query, variables], sort_keys=True).encode()).hexdigest()[:16]
                              + ".json")
    if f.exists():
        return json.loads(f.read_text())["data"]
    time.sleep(1)
    r = httpx.post(floodnet.URL, json={"query": query, "variables": variables or {}}, timeout=120)
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise RuntimeError(f"FloodNet GraphQL error: {j['errors']}")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"query": query, "variables": variables, "data": j["data"]}))
    return j["data"]


def utc(s: str) -> datetime:
    """FloodNet and STAC times as naive UTC."""
    return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)


def sensors() -> dict[str, dict]:
    """Sensors whose status in FloodNet's API is good (`floodnet.is_good`), with a location."""
    rows = gql("{ deployments(limit: 5000) { deployment_id name sensor_address_street sensor_address_borough "
               "sensor_address_neighborhood sensor_status date_deployed date_down deploy_type mounted_over location "
               "nearest_tidal_id } }")["deployments"]
    out = {}
    for r in rows:
        lat, lon = floodnet._parse_location(r["location"])
        if floodnet.is_good(r["sensor_status"]) and lat is not None and r["date_deployed"]:
            out[r["deployment_id"]] = {**r, "lat": lat, "lon": lon}
    return out


def flood_events() -> dict[str, list[tuple[datetime, datetime, int | None]]]:
    """Every event FloodNet labels "flood" (the label the app reads), by
    sensor, sorted by start. Events with no end time, or stamped in the
    future (a sensor clock fault), are left out."""
    by: dict[str, list] = {}
    off, now = 0, datetime.now(UTC).replace(tzinfo=None)
    while True:
        page = gql("query P($off: Int!) { sensor_events(where:{label:{_eq:\"flood\"}}, order_by:{id: asc}, "
                   "limit: 5000, offset: $off) { id deployment_id start_time end_time max_depth_proc_mm } }",
                   {"off": off})["sensor_events"]
        for e in page:
            if e["end_time"] and utc(e["start_time"]) < now:
                by.setdefault(e["deployment_id"], []).append((utc(e["start_time"]), utc(e["end_time"]),
                                                              e["max_depth_proc_mm"]))
        off += 5000
        if len(page) < 5000:
            break
    for v in by.values():
        v.sort(key=lambda e: e[0])
    return by


def passes(collection: str) -> list[dict]:
    """Every item of a Planetary Computer collection over the city since the
    first sensor, as STAC dicts, oldest first (the least cloudy tile of a
    pass first). Eight radar scenes are HH and HV, which neither model
    reads; they are left out."""
    from pystac_client import Client

    f = CACHE / f"stac_items_{collection}.json"
    if not f.exists():
        items = Client.open(prithvi.STAC_URL).search(collections=[collection], bbox=eo.NYC_BBOX,
                                                     datetime=f"{SINCE}/{date.today()}").items()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps([i.to_dict() for i in items]))
    out = sorted((i for i in json.loads(f.read_text()) if collection != S1 or "vv" in i["assets"]),
                 key=lambda i: (i["properties"]["datetime"], i["properties"].get("eo:cloud_cover") or 0))
    by_pass: dict[tuple, list[str]] = {}
    for i in out:
        p = i["properties"]
        ITEMS[i["id"]] = i
        by_pass.setdefault((p["platform"].lower(), p["datetime"][:10], p["sat:relative_orbit"]), []).append(i["id"])
    PASS.update({i: [i] + [j for j in ids if j != i] for ids in by_pass.values() for i in ids})
    return out


def moments(sens: dict, events: dict, collection: str) -> dict[str, list[dict]]:
    """By sensor, one row per pass, oldest first: the sensor was deployed and
    the scene's footprint contains it. `flooded` says a flood event spans the
    pass time, `dry` that none comes within three hours of it. Items of one
    pass (same platform, day and orbit) count once."""
    import numpy as np
    import shapely
    from shapely.geometry import shape

    ids = list(sens)
    xs, ys = np.array([sens[k]["lon"] for k in ids]), np.array([sens[k]["lat"] for k in ids])
    up = [(utc(s["date_deployed"]), utc(s["date_down"]) if s["date_down"] else datetime.max) for s in sens.values()]
    starts = {k: [e[0] for e in events.get(k, ())] for k in ids}
    seen, out = set(), {k: [] for k in ids}
    for it in passes(collection):
        p = it["properties"]
        t = utc(p["datetime"])
        for n in np.flatnonzero(shapely.contains_xy(shape(it["geometry"]), xs, ys)):
            k, key = ids[n], (n, p["platform"].lower(), p["datetime"][:10], p["sat:relative_orbit"])
            if key in seen or not up[n][0] <= t < up[n][1]:
                continue
            seen.add(key)
            ev = events.get(k, [])
            i = bisect_right(starts[k], t) - 1
            wet = i >= 0 and ev[i][1] >= t
            out[k].append({"sensor": k, "collection": collection, "item": it["id"], "time": p["datetime"],
                           "orbit": p["sat:relative_orbit"], "cloud": p.get("eo:cloud_cover"), "flooded": bool(wet),
                           "dry": not any(a - DAY / 8 <= t <= b + DAY / 8 for a, b, _ in ev[max(i, 0):i + 2]),
                           **({"event_start": str(ev[i][0]), "event_end": str(ev[i][1]), "event_max_depth_mm": ev[i][2]}
                              if wet else {})})
    return out


def depth_at(sensor: str, t: datetime) -> dict:
    """The sensor's own reading nearest the pass, within 15 minutes: proof it
    was reporting, and the depth at that instant."""
    rows = gql("query D($id: String!, $a: timestamptz!, $b: timestamptz!) { depth_data(where:{deployment_id:{_eq:$id}, "
               "time:{_gte:$a, _lte:$b}}, order_by:{time: asc}) { time depth_proc_mm depth_filt_mm } }",
               {"id": sensor, "a": f"{t - timedelta(minutes=15)}+00:00", "b": f"{t + timedelta(minutes=15)}+00:00"})["depth_data"]
    if not rows:
        return {"reporting": False, "depth_mm": None}
    r = min(rows, key=lambda r: abs(datetime.fromisoformat(r["time"]).replace(tzinfo=None) - t))
    return {"reporting": True, "depth_mm": r["depth_proc_mm"], "depth_time": r["time"]}


@cache
def place(lat: float, lon: float):
    """The 2.56 km grid around a sensor, every pixel's distance from it in
    metres, and the land mask."""
    import numpy as np
    from pyproj import Transformer

    dlat, dlon = 1300 / 111_320, 1300 / 84_400  # metres per degree at 40.7 N
    ref = prithvi.grid([lon - dlon, lat - dlat, lon + dlon, lat + dlat]).isel(y=slice(0, PX), x=slice(0, PX))
    assert ref.shape == (PX, PX)
    x, y = Transformer.from_crs("EPSG:4326", ref.rio.crs, always_xy=True).transform(lon, lat)
    return ref, np.hypot(ref.x.values[None, :] - x, ref.y.values[:, None] - y), eo.land_mask(ref)


def signed(item_id: str):
    """A cached STAC item with asset URLs signed for reading."""
    import planetary_computer as pc
    import pystac

    return pc.sign(pystac.Item.from_dict(ITEMS[item_id]))


def cached(s: dict, name: str, read):
    """An array read once per sensor and kept under outputs/."""
    import numpy as np

    f = CACHE / "scenes" / s["deployment_id"] / f"{name}.npy"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(f".{threading.get_ident()}.tmp.npy")
        np.save(tmp, read())
        tmp.replace(f)
    return np.load(f)


def mosaic(s: dict, i: str, one):
    """`one(s, item)` on the sensor's grid; where the box runs past the edge
    of the item, the gap is filled from the other tiles or slices of the
    same pass (0 is no data in every array read here)."""
    import numpy as np
    from shapely.geometry import box, shape

    out = one(s, i)
    area = box(*place(s["lat"], s["lon"])[0].rio.transform_bounds("EPSG:4326"))
    for j in PASS[i][1:]:
        if out.reshape(-1, PX, PX).any(0).all():
            break
        if shape(ITEMS[j]["geometry"]).intersects(area):
            out = np.where(out == 0, one(s, j), out)
    return out


def scl(s: dict, i: str):
    """The Sentinel-2 scene classification on the sensor's grid."""
    return mosaic(s, i, lambda s, j: cached(
        s, f"{j}.scl", lambda: prithvi.read_band(signed(j), "SCL", place(s["lat"], s["lon"])[0], "nearest")))


def clear(s: dict, i: str):
    """`prithvi.clear_mask` from the cached classification."""
    import numpy as np

    a = scl(s, i)
    return (a > 0) & ~np.isin(a, prithvi.SCL_UNCLEAR)


def clear_view(s: dict, i: str) -> dict:
    """Is the view clear at the sensor, and what share of the 250 m around it is."""
    c, dist = clear(s, i), place(s["lat"], s["lon"])[1]
    return {"clear": bool(c.flat[dist.argmin()]), "clear_share_250m": round(float(c[dist <= 250].mean()), 2)}


def s2_dn(s: dict, i: str):
    """The 12 bands TerraMind reads, as run_flood_ida reads them (digital
    numbers, nearest neighbour), with the +1000 offset of baseline 04.00 and
    later removed; 0 stays no data."""
    import numpy as np

    def one(s, j):
        dn = cached(s, f"{j}.dn", lambda: np.stack([prithvi.read_band(signed(j), b, place(s["lat"], s["lon"])[0], "nearest")
                                                    for b in flood.S2_BANDS])).astype("float32")
        return np.where(dn > 0, dn - offset(j), 0)

    return mosaic(s, i, one)


def offset(i: str) -> int:
    from types import SimpleNamespace

    return prithvi.boa_offset(SimpleNamespace(properties=ITEMS[i]["properties"]))


def s2_reflectance(s: dict, i: str):
    """The six bands the Prithvi layer reads, as it reads them."""
    return mosaic(s, i, lambda s, j: cached(s, f"{j}.refl", lambda: prithvi.read_bands(signed(j), place(s["lat"], s["lon"])[0])))


def s1_db(s: dict, i: str):
    """VV and VH in dB as run_flood_ida reads them."""
    import numpy as np

    def read(j):
        lin = np.stack([prithvi.read_band(signed(j), b, place(s["lat"], s["lon"])[0], "bilinear") for b in ("vv", "vh")])
        return np.where(lin > 0, 10 * np.log10(np.clip(lin, 1e-6, None)), 0).astype("float32")

    return mosaic(s, i, lambda s, j: cached(s, f"{j}.s1", lambda: read(j)))


def dem(s: dict):
    """Copernicus DEM GLO-30 on the sensor's grid, as run_flood_ida reads it."""
    import numpy as np
    import planetary_computer as pc
    from pystac_client import Client

    def read():
        ref = place(s["lat"], s["lon"])[0]
        out = np.zeros(ref.shape, "float32")
        for it in Client.open(prithvi.STAC_URL, modifier=pc.sign_inplace).search(
                collections=["cop-dem-glo-30"], bbox=list(ref.rio.transform_bounds("EPSG:4326"))).items():
            out = np.where(out == 0, prithvi.read_band(it, "data", ref, "bilinear").astype("float32"), out)
        return out

    return cached(s, "dem", read)


def table():
    sens = sensors()
    events = flood_events()
    return sens, events, {c: moments(sens, events, c) for c in (S1, S2)}


def step1(sens, events, rows) -> dict:
    n_events = sum(len(events.get(k, ())) for k in sens)
    out = {"what": "FloodNet flood events held against every Sentinel-1 and Sentinel-2 pass over New York City",
           "run_date": str(date.today()), "rule": RULE, "method": METHOD,
           "n_sensors": len(sens), "n_sensors_with_flood_events": sum(k in events for k in sens),
           "n_flood_events": n_events,
           "date_range": [min(s["date_deployed"] for s in sens.values())[:10], str(date.today())], "satellites": {}}
    positives = []
    for name, coll in (("sentinel-1", S1), ("sentinel-2", S2)):
        ms = [m for v in rows[coll].values() for m in v]
        pos = [dict(m) for m in ms if m["flooded"]]
        out["satellites"][name] = {"collection": coll, "n_items": len(passes(coll)),
                                   "n_passes": len({(m["time"][:10], m["orbit"]) for m in ms}),
                                   "n_moments": len(ms), "n_positive_before_checks": len(pos)}
        positives += pos
    for m in positives:
        s = sens[m["sensor"]]
        m.update(name=s["name"], neighbourhood=s["sensor_address_neighborhood"], borough=s["sensor_address_borough"],
                 deploy_type=s["deploy_type"], lat=s["lat"], lon=s["lon"], **depth_at(m["sensor"], utc(m["time"])))
        if m["collection"] == S2:
            m.update(clear_view(s, m["item"]))
        # A positive counts when the sensor was reporting at the pass and, for Sentinel-2, the view of it was clear.
        m["counted"] = bool(m["reporting"] and m.get("clear", True))
    good = [m for m in positives if m["counted"]]
    for name, coll in (("sentinel-1", S1), ("sentinel-2", S2)):
        mine = [m for m in positives if m["collection"] == coll]
        out["satellites"][name].update(n_positive_reporting=sum(m["reporting"] for m in mine),
                                       n_positive=sum(m["counted"] for m in mine))
    out.update(n_positive=len(good), n_positive_dates=len({m["time"][:10] for m in good}),
               positive_dates=dict(sorted(Counter(m["time"][:10] for m in good).items())),
               n_positive_sensors=len({m["sensor"] for m in good}),
               positive_neighbourhoods=dict(Counter(m["neighbourhood"] for m in good).most_common()),
               positive_depths_mm=sorted(m["depth_mm"] for m in good if m["depth_mm"] is not None),
               positive_moments=sorted(positives, key=lambda m: (m["time"], m["sensor"])))
    out["step1_passes"] = not (out["n_positive"] < 10 and out["n_positive_dates"] < 3)
    return out


def negatives(sens, rows, positives) -> list[dict]:
    """For each positive, five passes of the same sensor, satellite and
    orbit on which it was dry, reporting a depth of zero and (Sentinel-2) in
    clear view; within 45 days of the positive's day of the year when there
    are enough, drawn in a seeded random order."""
    rng, used, out = random.Random(SEED), set(), []
    for m in positives:
        s, doy = sens[m["sensor"]], utc(m["time"]).timetuple().tm_yday
        cands = [r for r in rows[m["collection"]][m["sensor"]] if r["dry"] and r["orbit"] == m["orbit"]]
        rng.shuffle(cands)
        season = {r["item"]: min(d := abs(utc(r["time"]).timetuple().tm_yday - doy), 365 - d) <= 45 for r in cands}
        got = 0
        for r in sorted(cands, key=lambda r: not season[r["item"]]):
            if got == NEGATIVES:
                break
            if (m["sensor"], r["item"]) in used or (r["collection"] == S2 and not clear_view(s, r["item"])["clear"]):
                continue
            d = depth_at(m["sensor"], utc(r["time"]))
            if d["reporting"] and not d["depth_mm"]:
                used.add((m["sensor"], r["item"]))
                out.append({**r, **d, "negative_of": m["time"], "same_season": season[r["item"]]})
                got += 1
    return out


def scenes(s: dict, rows: dict, m: dict) -> dict:
    """A moment's four scenes per satellite, in ImpactMesh's order (a month
    before, just before, the event, after). The event scene of the moment's
    own satellite is the moment's; the other satellite's is its nearest
    usable pass. The rest are passes of the event scene's orbit with the
    sensor dry, and for Sentinel-2 a clear view of it and of 90% of the
    250 m around it. None where no such pass exists."""
    def usable(r):
        if r["collection"] == S1:
            return True
        v = clear_view(s, r["item"])
        return v["clear"] and v["clear_share_250m"] >= 0.9

    t, out = utc(m["time"]), {}
    for coll in (S1, S2):
        mine = rows[coll][m["sensor"]]
        event = m if coll == m["collection"] else next(
            (r for r in sorted(mine, key=lambda r: abs(utc(r["time"]) - t)) if usable(r)), None)
        if event is None:
            out[coll] = [None] * 4
            continue
        te = utc(event["time"])
        same = [r for r in mine if r["orbit"] == event["orbit"] and r["dry"]]
        just = next((r for r in reversed(same) if utc(r["time"]) < te - DAY / 2 and usable(r)), None)
        month = just and next((r for r in reversed(same)
                               if utc(r["time"]) < min(te - 20 * DAY, utc(just["time"])) and usable(r)), None)
        after = next((r for r in same if utc(r["time"]) > te + DAY / 2 and usable(r)), None)
        out[coll] = [r and r["item"] for r in (month, just, event, after)]
        out[f"{coll}_event_hours_from_moment"] = round((te - t).total_seconds() / 3600, 1)
        out[f"{coll}_event_flooded"] = event["flooded"]
    return out


def plan(sens, rows, step) -> list[dict]:
    """Positives, their negatives and every moment's scenes, with every scene fetched into the cache."""
    f = CACHE / "plan.json"
    if f.exists():
        ms = json.loads(f.read_text())
    else:
        pos = [{k: m[k] for k in ("sensor", "collection", "item", "time", "orbit", "flooded", "depth_mm")}
               for m in step["positive_moments"] if m["counted"]]
        for m in pos:
            place(sens[m["sensor"]]["lat"], sens[m["sensor"]]["lon"])  # here, not in the threads below
        ms = pos + negatives(sens, rows, pos)
        with ThreadPoolExecutor(8) as pool:
            for m, sc in zip(ms, pool.map(lambda m: scenes(sens[m["sensor"]], rows, m), ms), strict=True):
                m.update(sc)
        f.write_text(json.dumps(ms, indent=1))
    jobs = []
    for m in ms:
        s = sens[m["sensor"]]
        if m["collection"] == S2 and m[S2][1]:
            jobs += [(s2_reflectance, s, i) for i in m[S2][1:3]]
        if None not in m[S1] + m[S2]:
            jobs += [(s2_dn, s, i) for i in m[S2]] + [(s1_db, s, i) for i in m[S1]] + [(dem, s)]
    for m in ms:
        place(sens[m["sensor"]]["lat"], sens[m["sensor"]]["lon"])
    with ThreadPoolExecutor(8) as pool:
        for n, _ in enumerate(pool.map(lambda j: j[0](*j[1:]), jobs)):
            if n % 200 == 0:
                print(f"  scene {n} of {len(jobs)}", flush=True)
    return ms


def ground(s: dict, m: dict):
    """Where a hit can count: land (inside a neighbourhood tabulation area)
    that the scene classification of the moment's dry "just before"
    Sentinel-2 scene does not call water (class 6)."""
    return place(s["lat"], s["lon"])[2] & (scl(s, m[S2][1]) != 6)


def run_models(sens, ms) -> dict:
    """Both models at every moment: the count of model water pixels within
    each radius, on land that is not permanent water."""
    import numpy as np

    f = CACHE / "step2.json"
    if f.exists():
        return json.loads(f.read_text())
    seconds = {}
    for m in ms:
        s = sens[m["sensor"]]
        dist = place(s["lat"], s["lon"])[1]
        if m[S2][1]:
            m["not_ground_share"] = {f"{r}m": round(float(1 - ground(s, m)[dist <= r].mean()), 2) for r in RADII}

    def near(m, water, observed):
        s = sens[m["sensor"]]
        dist = place(s["lat"], s["lon"])[1]
        return {"seen": bool(observed.flat[dist.argmin()]),
                **{f"px_{r}m": int((water & observed & ground(s, m))[dist <= r].sum()) for r in RADII}}

    t0 = time.time()
    net = flood.load_model()
    for m in ms:
        if None in m[S1] + m[S2]:
            continue
        s = sens[m["sensor"]]
        s2, s1 = np.stack([s2_dn(s, i) for i in m[S2]]), np.stack([s1_db(s, i) for i in m[S1]])
        prob = flood.predict(net, s2, s1, dem(s))
        own = s2[2].any(0) if m["collection"] == S2 else s1[2, 0] != 0  # data in the moment's own event image
        dist, land = place(s["lat"], s["lon"])[1:]
        m["terramind"] = {**near(m, prob >= 0.5, own), "max_prob_100m": round(float(prob[dist <= 100].max()), 3),
                          "flood_px_in_box": int((prob >= 0.5).sum()),
                          "s1_filled": round(float((s1[:, 0] != 0).mean()), 3), "s2_filled": round(float(s2.any(1).mean()), 3),
                          "s1_event_db_median_on_land": [round(float(np.median(s1[2, b][land & (s1[2, b] != 0)])), 1) for b in (0, 1)],
                          "s2_offset_removed": [offset(i) for i in m[S2]]}
    del net
    seconds["terramind"] = round(time.time() - t0)
    t0 = time.time()
    for m in ms:
        if m["collection"] != S2 or not m[S2][1]:
            continue
        s = sens[m["sensor"]]
        pre_id, post_id = m[S2][1:3]
        post, pre = s2_reflectance(s, post_id), s2_reflectance(s, pre_id)
        # run_eo_batch.run_event: observed where both scenes have data and a clear view; new water is water after, not before.
        valid = (post.sum(0) > 0) & (pre.sum(0) > 0) & clear(s, post_id) & clear(s, pre_id)
        after, before = prithvi.water_mask(post) == 1, prithvi.water_mask(pre) == 1
        open_water = (scl(s, post_id) == 6) & valid  # what the scene classification calls water, to check the model sees water at all
        m["prithvi"] = {**near(m, after & ~before, valid), "water_px_in_box": int(after.sum()),
                        "scl_water_px": int(open_water.sum()), "scl_water_px_found": int((after & open_water).sum())}
    seconds["prithvi"] = round(time.time() - t0)
    out = {"moments": ms, "model_seconds": seconds}
    f.write_text(json.dumps(out, indent=1))
    return out


AI4G = {"dataset": "ai-for-good-lab/ai4g-flood-dataset", "revision": "d594d7a72f9719abff2df375dd3734a912b80595",
        "file": "N39/N39W075/N39W075-post-processing.parquet", "licence": "MIT (dataset card)",
        "sha256": "6b62266edd349aaccf091c417d4b0884f0d2095702beb566da6b9664200af6e7",
        "covers": "October 2014 to September 2024; this tile's last detection is dated 2024-09-27"}


def ai4g(sens, ms) -> dict:
    """Step 3: Microsoft AI for Good's precomputed Sentinel-1 flood
    detections (20 m points, one row per detection with its scene's name),
    scored at the Sentinel-1 moments the dataset covers. A detection counts
    when it lies on the same ground as the other models' hits; `px` is the
    count within the radius plus the 80 m buffer the dataset card
    recommends, `raw_px` within the radius alone. The dataset lists
    detections only, so a pass with none is taken as observed and empty."""
    import numpy as np
    import pandas as pd
    import rasterio
    from huggingface_hub import hf_hub_download
    from pyproj import Transformer

    path = hf_hub_download(AI4G["dataset"], AI4G["file"], repo_type="dataset", revision=AI4G["revision"],
                           local_dir=CACHE / "ai4g")
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == AI4G["sha256"]
    df = pd.read_parquet(path, columns=["lat", "lon", "filename"])
    last, named = "2024-09-27", set(df.filename)
    for m in ms:
        if m["collection"] != S1 or m["time"][:10] > last or not m[S2][1]:
            continue
        s = sens[m["sensor"]]
        ref, dist, _ = place(s["lat"], s["lon"])
        names = [i.removesuffix("_rtc") + "-20m" for i in PASS[m["item"]]]
        d = df[df.filename.isin(names)]
        x, y = Transformer.from_crs("EPSG:4326", ref.rio.crs, always_xy=True).transform(d.lon.values, d.lat.values)
        rows, cols = rasterio.transform.rowcol(ref.rio.transform(), x, y)
        inside = (rows >= 0) & (rows < PX) & (cols >= 0) & (cols < PX)
        det = np.zeros((PX, PX), bool)
        det[rows[inside], cols[inside]] = True
        det &= ground(s, m)
        m["ai4g"] = {"seen": True, "scene_has_detections_in_tile": any(n in named for n in names),
                     **{f"px_{r}m": int(det[dist <= r + 80].sum()) for r in RADII},
                     **{f"raw_px_{r}m": int(det[dist <= r].sum()) for r in RADII}}
    return {**AI4G, **score(ms, "ai4g")}


def score(ms: list[dict], model: str) -> dict:
    """Hit rate at positives, false-alarm rate at negatives and a one-sided
    Fisher exact p at each radius, over the moments the model observed."""
    from scipy.stats import fisher_exact

    seen = [m for m in ms if m.get(model, {}).get("seen")]
    pos, neg = [m for m in seen if m["flooded"]], [m for m in seen if not m["flooded"]]
    out: dict = {"n_positive": len(pos), "n_negative": len(neg)}
    for r in RADII:
        hit, fa = [m for m in pos if m[model][f"px_{r}m"]], [m for m in neg if m[model][f"px_{r}m"]]
        out[f"{r}m"] = {"hits": len(hit), "hit_dates": sorted({m["time"][:10] for m in hit}),
                        "hit_sensors": sorted({m["sensor"] for m in hit}), "false_alarms": len(fa),
                        "hit_rate": round(len(hit) / max(len(pos), 1), 3),
                        "false_alarm_rate": round(len(fa) / max(len(neg), 1), 3),
                        "fisher_p": round(float(fisher_exact([[len(hit), len(pos) - len(hit)], [len(fa), len(neg) - len(fa)]],
                                                             alternative="greater")[1]), 4)}
    r = out["100m"]
    out["shows_skill"] = bool(r["hits"] >= 5 and len(r["hit_dates"]) >= 2 and r["fisher_p"] < 0.05
                              and r["hits"] * max(len(neg), 1) >= 2 * r["false_alarms"] * max(len(pos), 1))
    return out


# Keys that hold a FloodNet record: one row per moment, or a value per sensor or per event.
_RECORDS = ("positive_moments", "moments", "not_ground_share_by_sensor", "positive_depths_mm")


def aggregate(out: dict) -> dict:
    """The result without FloodNet records: counts, rates, dates and the
    verdict. Sensor ids become a count."""
    def strip(v):
        if not isinstance(v, dict):
            return v
        return {("n_hit_sensors" if k == "hit_sensors" else k): (len(x) if k == "hit_sensors" else strip(x))
                for k, x in v.items() if k not in _RECORDS}

    return {**strip(out), "floodnet_licence": f"{floodnet.ATTRIBUTION}, {floodnet.LICENSE}, {floodnet.LICENSE_URL}",
            "run_at": out.get("run_at") or out.get("run_date")}


def _check() -> None:
    """The skill rule on made-up moments: 6 hits of 10 on two dates against
    2 false alarms of 50 is skill; the same hits on one date are not."""
    def m(wet, px, day):
        return {"flooded": wet, "time": f"2024-01-{day:02d}", "sensor": "s",
                "x": {"seen": True, **{f"px_{r}m": int(px) for r in RADII}}}

    ms = [m(True, k < 6, 1 + k % 2) for k in range(10)] + [m(False, k < 2, 3) for k in range(50)]
    assert score(ms, "x")["shows_skill"] and score(ms, "x")["100m"]["hits"] == 6
    assert not score([{**a, "time": "2024-01-01"} for a in ms], "x")["shows_skill"]
    agg = aggregate({"moments": ms, "x": score(ms, "x"), "positive_depths_mm": [60]})
    assert "sensor" not in json.dumps(agg).replace("n_hit_sensors", "") and agg["x"]["100m"]["n_hit_sensors"] == 1


def main() -> int:
    _check()
    sens, events, rows = table()
    out = step1(sens, events, rows)
    if not out["step1_passes"]:
        out["verdict"] = "too few moments to tell"
    elif "--inputs" in sys.argv or "--models" in sys.argv or (CACHE / "step2.json").exists():
        ms = plan(sens, rows, out)
        out["n_negative"] = sum(not m["flooded"] for m in ms)
        if "--models" in sys.argv or (CACHE / "step2.json").exists():
            done = run_models(sens, ms)
            ms = done["moments"]
            out.update(model_seconds=done["model_seconds"], ai4g_flood=ai4g(sens, ms),
                       prithvi=score(ms, "prithvi"), terramind=score(ms, "terramind"),
                       terramind_sentinel1_moments=score([m for m in ms if m["collection"] == S1], "terramind"),
                       terramind_sentinel2_moments=score([m for m in ms if m["collection"] == S2], "terramind"))
            # Per sensor: the share of each radius that can never be a hit (off the land mask, or water in the dry scene).
            out["not_ground_share_by_sensor"] = {
                k: {f"{r}m": max(m["not_ground_share"][f"{r}m"] for m in ms if m["sensor"] == k and "not_ground_share" in m)
                    for r in RADII} for k in sorted({m["sensor"] for m in ms if "not_ground_share" in m})}
            gaps = {c: sorted(abs(m[f"{c}_event_hours_from_moment"]) for m in ms if "terramind" in m and m["collection"] != c)
                    for c in (S1, S2)}
            out["terramind_other_satellite_event_image_hours_from_moment_median"] = {c: g[len(g) // 2] for c, g in gaps.items()}
            out["models"] = {"prithvi": {"repo": prithvi.REPO, "revision": prithvi.REVISION, "file": prithvi.WEIGHTS},
                             "terramind": {"repo": flood.REPO, "revision": flood.REVISION, "file": flood.FILE,
                                           "sha256": flood.SHA256, "threshold": "flood probability 0.5"}}
            found = [(m["prithvi"]["scl_water_px_found"], m["prithvi"]["scl_water_px"]) for m in ms if "prithvi" in m]
            out["prithvi_finds_open_water_pct"] = round(100 * sum(a for a, _ in found) / max(sum(b for _, b in found), 1), 1)
            out["verdict"] = ("skill: keep as a coastal and tidal layer"
                              if out["prithvi"]["shows_skill"] or out["terramind"]["shows_skill"] else "no skill")
        out["moments"] = ms
    out["run_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")  # the time stamp FloodNet's licence asks for
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(out, indent=1) + "\n")
    OUT.write_text(json.dumps(aggregate(out), indent=1) + "\n")
    print(json.dumps(aggregate(out), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
