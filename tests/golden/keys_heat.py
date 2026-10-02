"""Independent answer keys for the heat briefing.

A second opinion on every fact the heat briefing states, each computed by a
route the app does not take. Nothing here imports riprap or app, and nothing
reads the app's baked heat files (the one exception is the list of Landsat
image ids and the selection rule in data/heat/surface_temp.json, which is
what the surface key checks). Written to be short and obvious, not fast.

What each key reads, and the tolerance the runner applies to it:

heat_surface, heat_surface_district
    Landsat Collection 2 Level 2 surface temperature (lwir11) and QA_PIXEL,
    read from Microsoft Planetary Computer for the image ids the app lists.
    Native 30 m pixels whose centres are within 150 m of the point (or inside
    the district outline) and inside an NTA polygon, minus the mean of every
    clear pixel inside the NTA polygons, per image, for the images where at
    least half of the place's pixels are clear. The app works on 90 m cells,
    each weighted by its share inside the circle, so the tolerance is per
    entry: the largest change the nine possible alignments of such a grid
    make to the same number (land pixels only), plus CITY_TOL_F for the city
    mean and 0.1 for two roundings. The image count is right anywhere between
    "all of the place clear" and "any of it clear"; the dates are exact.
landsat_selection
    The app's keep or skip decision for every listed image, recomputed from
    the item's tier and scene cloud cover and the share of NTA pixels clear.
hvi, hvi_district
    EHDP indicators 2411 (NTA 2020) and 2191 (CDTA 2020), ids resolved by
    name through the portal's geography/GeoLookup.csv. Exact. Green space is
    recounted from the 2017 land cover raster over the NTA polygon (2 points);
    air conditioning has no NTA publication outside the file the app bakes, so
    it is only bounded: equal to one of the borough's 2017 survey area figures
    in indicator 2185, or between the lowest and highest of them.
heat_visits
    EHDP indicator 2443 by community district, id resolved by borough name
    and "(CDn)" through GeoLookup.csv. Exact, including suppression.
heat_station
    NCEI daily summaries TMAX for Central Park, LaGuardia and JFK, days
    counted here, each year's highest reading and the all-time record over
    everything NCEI holds for the station. Exact (a date is right if it is
    any day that reached the high). Nearest station by haversine to NCEI's
    coordinates; the distance within 0.2 km.
nws_heat_forecast
    api.weather.gov points, forecast and raw grid, fetched fresh. Highs exact,
    highest apparent temperature within 1 F, unscored when the issue times of
    the two fetches differ.
city_landcover, city_landcover_district
    NYC Land Cover 2017 (he6d-2qns) read from the publisher's zip at the
    native 6 inch pixels inside 500 m (1.5 points, the app counts 30 m cells),
    and at every 8th pixel inside a district outline (0.5 points).
vegetative_cover_2143
    The Health portal's own 2017 vegetative cover by community district, an
    outside figure for the district green share (3 points, not the same
    outline: a community district against its NTA approximation).
cool_features
    NYC Parks Spray Showers (ckaz-6gaa) and Pools (y5rm-wagw) from the live
    Socrata API, haversine 800 m. Exact.
npcc4_table
    Table 4 of Braneon et al. 2024 parsed from the pdftotext sample. Exact.

Every response is cached under outputs/golden_heat_cache/ and requests to one
host are a second apart.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from functools import cache, lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "outputs" / "golden_heat_cache"
UA = "Mozilla/5.0 (compatible; Riprap golden keys; +https://github.com/msradam/riprap)"
_last_call: dict[str, float] = {}


def _fetch(url: str, params: dict | None = None, stamp: str = "", body: dict | None = None, timeout: int = 120) -> bytes:
    """GET (or POST a JSON body) once and keep the bytes. `stamp` is part of
    the cache name: '' for files that do not change, today's date for live
    tables, a timestamp for forecasts (kept for the record, never reused)."""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    CACHE.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha1((url + json.dumps(body or "") + stamp).encode()).hexdigest()[:20]
    f = CACHE / (name + ".bin")
    if f.exists():
        return f.read_bytes()
    host = urllib.parse.urlsplit(url).netloc
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"User-Agent": UA, "Accept": "application/geo+json, application/json, */*",
                                          "Content-Type": "application/json"})
    for attempt in range(5):
        wait = 1.0 - (time.time() - _last_call.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429 or attempt == 4:
                raise
        except (urllib.error.URLError, ConnectionResetError, TimeoutError):
            if attempt == 4:
                raise
        time.sleep(3 * 2 ** attempt)
    f.write_bytes(data)
    with open(CACHE / "index.tsv", "a") as ix:
        ix.write(f"{name}\t{stamp}\t{url}\n")
    return data


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000.0 * math.asin(math.sqrt(a))


# NYC Planning's 2020 neighborhood tabulation areas: the one geography file shared with the app.
BORO = {"MN": "Manhattan", "BX": "Bronx", "BK": "Brooklyn", "QN": "Queens", "SI": "Staten Island"}


@lru_cache(maxsize=1)
def _ntas():
    import geopandas as gpd

    return gpd.read_file(ROOT / "data" / "nyc_ntas_2020.geojson")


def nta_at(lat: float, lon: float) -> dict | None:
    from shapely.geometry import Point

    g = _ntas()
    hit = g.iloc[g.sindex.query(Point(lon, lat), predicate="within")]
    return None if hit.empty else hit.iloc[0][["nta2020", "ntaname", "ntatype", "cdta2020", "boroname"]].to_dict()


def district_outline(code: str):
    g = _ntas()
    return g[g["cdta2020"] == code.upper()].union_all()


# ---------------------------------------------------------------- EHDP (NYC Health Department)
_EHDP = "https://raw.githubusercontent.com/nychealth/EHDP-data/production/"


@lru_cache(maxsize=1)
def _geolookup() -> list[dict]:
    text = _fetch(_EHDP + "geography/GeoLookup.csv").decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


@cache
def _indicator(indicator_id: int) -> list[dict]:
    """One indicator file, turned from parallel arrays into rows."""
    d = json.loads(_fetch(_EHDP + f"indicators/data/{indicator_id}.json"))
    return [dict(zip(d, vals, strict=True)) for vals in zip(*d.values(), strict=True)]


@lru_cache(maxsize=1)
def _period_ids() -> dict[str, set[int]]:
    """Period label to ids. A label can have two ids ("2018-22" is 312 and 362), so this is a set."""
    out: dict[str, set[int]] = {}
    for t in json.loads(_fetch(_EHDP + "indicators/metadata/TimePeriods.json")):
        out.setdefault(t["TimePeriod"], set()).add(t["TimePeriodID"])
    return out


def _geo_id(geo_type: str, borough: str, name: str | None = None, cd: int | None = None) -> str | None:
    """The portal's id for a place, found by borough name and place name (or
    the "(CD 5)" at the end of a district's name). Never built by arithmetic:
    the portal numbers boroughs alphabetically for GeoType Borough, by city
    borough code for CD, and by county FIPS for CDTA2020 and NTA2020."""
    hits = [r for r in _geolookup() if r["GeoType"] == geo_type and r["Borough"] == borough
            and (name is None or r["Name"] == name)
            and (cd is None or re.search(rf"\(CD ?{cd}\)$", r["Name"]))]
    return hits[0]["GeoID"] if len(hits) == 1 else None


def _value(indicator_id: int, measure: int, geo_type: str, geo_id: str, period: str | None = None) -> dict | None:
    rows = [r for r in _indicator(indicator_id) if r["MeasureID"] == measure and r["GeoType"] == geo_type
            and str(r["GeoID"]) == str(geo_id) and (period is None or r["TimePeriodID"] in _period_ids()[period])]
    return rows[0] if len(rows) == 1 else None


def _split(code: str) -> tuple[str, int]:
    return BORO[code[:2].upper()], int(code[2:])


def hvi(lat: float, lon: float) -> dict:
    """Heat Vulnerability Index of the NTA containing the point (indicator 2411, measure 1288)."""
    a = nta_at(lat, lon)
    if a is None:
        return {"hvi": None, "area": None, "area_code": None, "why": "the point is in no tabulation area"}
    gid = _geo_id("NTA2020", a["boroname"], name=a["ntaname"])
    row = _value(2411, 1288, "NTA2020", gid) if gid else None
    return {"hvi": row["Value"] if row else None, "area": a["ntaname"], "area_code": a["nta2020"],
            "ntatype": a["ntatype"], "geo_id": gid,
            "why": None if row else "the portal publishes no index for this tabulation area"}


def hvi_district(code: str) -> dict:
    """Index of the district (indicator 2191, CDTA 2020) and of each of its NTAs (2411)."""
    borough, n = _split(code)
    gid = _geo_id("CDTA2020", borough, cd=n)
    row = _value(2191, 822, "CDTA2020", gid) if gid else None
    g = _ntas()
    hoods = {}
    for name in sorted(g[g["cdta2020"] == code.upper()]["ntaname"]):
        nid = _geo_id("NTA2020", borough, name=name)
        r = _value(2411, 1288, "NTA2020", nid) if nid else None
        if r:
            hoods[name] = r["Value"]
    return {"hvi": row["Value"] if row else None, "geo_id": gid, "neighbourhoods": hoods}


def hvi_ac_values(borough: str) -> list[float]:
    """Percent of households with air conditioning in 2017, by survey area of
    one borough (indicator 2185, measure 781, GeoType Subboro). The index's
    NTA figure is one of these (152 of 198 NTAs) or a blend of several, so
    the check is a bound: no other publication of the NTA figure exists."""
    ids = {r["GeoID"] for r in _geolookup() if r["GeoType"] == "Subboro" and r["Borough"] == borough}
    return sorted(r["Value"] for r in _indicator(2185) if r["MeasureID"] == 781 and r["GeoType"] == "Subboro"
                  and r["TimePeriodID"] in _period_ids()["2017"] and str(r["GeoID"]) in ids and r["Value"] is not None)


def heat_visits(code: str) -> dict | None:
    """Heat stress emergency department visits 2018-22 for one community
    district (indicator 2443: 1403 number, 1405 average annual age-adjusted rate)."""
    try:
        borough, n = _split(code)
    except (KeyError, ValueError):
        return None
    gid = _geo_id("CD", borough, cd=n)
    if gid is None:
        return None  # a park, airport or other joint interest area: no community district
    num, rate = _value(2443, 1403, "CD", gid, "2018-22"), _value(2443, 1405, "CD", gid, "2018-22")
    city = _value(2443, 1405, "Citywide", _geo_id("Citywide", ""), "2018-22")
    return {"district": code.upper(), "geo_id": gid, "n": num["Value"], "suppressed": num["Value"] is None,
            "note": num["Note"] or None, "age_adjusted_rate": rate["Value"],
            "citywide_age_adjusted_rate": city["Value"]}


def heat_visits_at(lat: float, lon: float) -> dict | None:
    a = nta_at(lat, lon)
    return heat_visits(a["cdta2020"]) if a else None


def vegetative_cover_2143(code: str) -> float | None:
    """The portal's own vegetative cover percent for a community district, 2017 (indicator 2143, measure 690)."""
    borough, n = _split(code)
    gid = _geo_id("CD", borough, cd=n)
    row = _value(2143, 690, "CD", gid, "2017") if gid else None
    return row["Value"] if row else None


# ---------------------------------------------------------------- NCEI daily summaries
STATIONS = {"USW00094728": "Central Park", "USW00014732": "LaGuardia", "USW00094789": "JFK"}


def _ncei(station: str, start: str, end: str, stamp: str) -> list[dict]:
    return json.loads(_fetch("https://www.ncei.noaa.gov/access/services/data/v1", {
        "dataset": "daily-summaries", "stations": station, "dataTypes": "TMAX", "startDate": start,
        "endDate": end, "units": "standard", "format": "json", "includeStationLocation": "1"},
        stamp=stamp, timeout=3000))


@cache
def _tmax_before_1991(station: str) -> dict[str, float]:
    """The rest of the station's record, for its all-time high. Slow: tens of minutes the first time."""
    return {r["DATE"]: float(r["TMAX"]) for r in _ncei(station, "1869-01-01", "1990-12-31", "")
            if r.get("TMAX") not in (None, "")}


@cache
def _tmax(station: str) -> tuple[dict[str, float], float, float]:
    """Every daily maximum since 1991 at one station, and where NCEI says it is."""
    today = date.today()
    # NCEI takes minutes for 35 years: the closed years are fetched once, this year once a day.
    rows = (_ncei(station, "1991-01-01", f"{today.year - 1}-12-31", "")
            + _ncei(station, f"{today.year}-01-01", str(today), str(today)))
    days = {r["DATE"]: float(r["TMAX"]) for r in rows if r.get("TMAX") not in (None, "")}
    return days, float(rows[0]["LATITUDE"]), float(rows[0]["LONGITUDE"])


def heat_station(lat: float, lon: float, record: bool = True) -> dict:
    """Days at or above 90 F at the nearest of the three stations, counted from NCEI's daily maxima."""
    dist = {s: haversine_m(lat, lon, *_tmax(s)[1:]) for s in STATIONS}
    order = sorted(dist, key=dist.get)
    sid = order[0]
    days = _tmax(sid)[0]
    year = date.today().year
    by_year = {str(y): 0 for y in range(1991, year + 1)}
    n_days = dict.fromkeys(by_year, 0)
    for d, t in days.items():
        n_days[d[:4]] += 1
        by_year[d[:4]] += t >= 90
    tops: dict[str, float] = {}
    for d, t in days.items():
        tops[d[:4]] = max(t, tops.get(d[:4], t))
    max_by_year = {y: [round(t), sorted(d for d, v in days.items() if d[:4] == y and v == t)] for y, t in tops.items()}
    this = {d: t for d, t in days.items() if d.startswith(str(year))}
    top = max(this.values()) if this else None
    normal = sum(by_year[str(y)] for y in range(1991, 2021)) / 30
    whole = {**_tmax_before_1991(sid), **days} if record else {}
    high = max(whole.values(), default=None)
    all_time = {"record_f": round(high), "record_dates": sorted(d for d, t in whole.items() if t == high),
                "record_since": min(whole)[:4]} if whole else {}
    return {"station": STATIONS[sid], "station_id": sid, "distance_km": round(dist[sid] / 1000, 1),
            "runner_up": STATIONS[order[1]], "runner_up_km": round(dist[order[1]] / 1000, 1),
            "days_ge_90": by_year[str(year)], "days_ge_90_last_year": by_year[str(year - 1)],
            "normal_days_ge_90": round(normal), "normal_exact": round(normal, 2), "by_year": by_year,
            "max_f": round(top) if top is not None else None,
            "max_dates": sorted(d for d, t in this.items() if t == top), "max_by_year": max_by_year, **all_time,
            "through": max(days), "days_missing": {y: (366 if int(y) % 4 == 0 else 365) - n
                                                   for y, n in n_days.items() if int(y) < year
                                                   and n != (366 if int(y) % 4 == 0 else 365)}}


# ---------------------------------------------------------------- NWS forecast
_NY = ZoneInfo("America/New_York")


def _c_to_f(c: float) -> float:
    return c * 9 / 5 + 32


def nws_heat_forecast(lat: float, lon: float) -> dict:
    """Daytime highs from the text forecast and the highest apparent temperature in the raw grid, fetched now."""
    now = datetime.now(UTC)
    stamp = now.isoformat(timespec="seconds")
    p = json.loads(_fetch(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"))["properties"]
    fc = json.loads(_fetch(p["forecast"], stamp=stamp))["properties"]
    grid = json.loads(_fetch(p["forecastGridData"], stamp=stamp))["properties"]
    highs = [{"day": q["name"], "date": q["startTime"][:10], "high_f": q["temperature"]}
             for q in fc["periods"] if q["isDaytime"]]
    apparent = []
    for v in grid["apparentTemperature"]["values"]:
        start, dur = v["validTime"].split("/")
        m = re.fullmatch(r"P(?:(\d+)D)?(?:T(\d+)H)?", dur)
        end = datetime.fromisoformat(start) + timedelta(days=int(m.group(1) or 0), hours=int(m.group(2) or 0))
        if v["value"] is not None and end > now:
            apparent.append((_c_to_f(v["value"]), start))
    top = max(apparent) if apparent else (None, None)

    def eastern(t: str) -> str:
        return datetime.fromisoformat(t).astimezone(_NY).strftime("%Y-%m-%d %H:%M")

    return {"grid": f"{p['gridX']},{p['gridY']}", "office": p["gridId"], "highs": highs,
            "max_high_f": max(h["high_f"] for h in highs) if highs else None,
            "max_apparent_f": round(top[0], 1) if top[0] is not None else None, "max_apparent_at": top[1],
            "issued": eastern(fc["updateTime"]), "grid_issued": eastern(grid["updateTime"]), "fetched": stamp}


# ---------------------------------------------------------------- NYC Parks spray showers and pools
def _socrata(dataset: str) -> list[dict]:
    return json.loads(_fetch(f"https://data.cityofnewyork.us/resource/{dataset}.json", {"$limit": 50000},
                             stamp=str(date.today())))


def _site(r: dict) -> str:
    return (r.get("sitename") or r.get("propname") or "").strip().casefold()


def _cool(near_point, near_shape) -> dict:
    showers = [r for r in _socrata("ckaz-6gaa") if r.get("point") and near_point(*r["point"]["coordinates"])]
    from shapely.geometry import shape

    pools = []
    for r in _socrata("y5rm-wagw"):
        if r.get("polygon"):
            c = shape(r["polygon"]).centroid
            if near_shape(c.x, c.y):
                pools.append(r)
    return {"n_spray_shower_sites": len({_site(r) for r in showers}),
            "n_spray_shower_rows": len(showers), "n_spray_shower_properties": len({r.get("propid") for r in showers}),
            "spray_shower_sites": sorted({_site(r) for r in showers}),
            "n_outdoor_pools": sum(r.get("location") == "Outdoor" for r in pools),
            "n_indoor_pools": sum(r.get("location") == "Indoor" for r in pools),
            "pools": sorted(r.get("name", "") for r in pools)}


def cool_features(lat: float, lon: float, radius_m: int = 800) -> dict:
    """Distinct spray shower site names and pools (polygon centroid) within the radius, haversine."""
    def near(x, y):
        return haversine_m(lat, lon, y, x) <= radius_m
    return _cool(near, near)


def cool_features_district(code: str) -> dict:
    import shapely

    outline = district_outline(code)

    def inside(x, y):
        return bool(shapely.contains_xy(outline, x, y))
    return _cool(inside, inside)


# ---------------------------------------------------------------- NPCC4 Table 4
def npcc4_table() -> dict:
    """Table 4 of Braneon et al. 2024 as pdftotext printed it: period, row, then baseline, 10th, 25th, 75th, 90th."""
    text = (ROOT / "research_notes/fable/climate/samples/npcc4_braneon2024_table4.txt").read_text()
    names = {"Days at or above 90": "days_ge_90", "Days at or above 95": "days_ge_95", "Number of heat waves": "heat_waves"}
    out: dict = {}
    period = None
    for line in text.splitlines():
        m = re.match(r"\s*(20\d0s)", line)
        if m:
            period = m.group(1)
        for label, key in names.items():
            if period and line.strip().startswith(label):
                # The row label carries its own number (90, 95) and a degree mark: the five values are the last five.
                nums = [float(x) if "." in x else int(x) for x in re.findall(r"\d+(?:\.\d+)?", line)][-5:]
                out.setdefault(period, {})[key] = dict(zip(("baseline", "10", "25", "75", "90"), nums, strict=True))
    return out


# ---------------------------------------------------------------- Landsat surface temperature
_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
CITY_TOL_F = 0.4  # the most a different land mask moved any image's city mean (0.38); see landsat_city_mean_variants()


def landsat_lists() -> dict:
    """The image ids the app kept and skipped, and its stated rule: all this key reads of the app's bake."""
    d = json.loads((ROOT / "data" / "heat" / "surface_temp.json").read_text())
    return {"kept": [i["id"] for i in d["images"]], "skipped": [i["id"] for i in d["skipped"]], "rule": d["rule"]}


@lru_cache(maxsize=1)
def _grid() -> tuple[float, float, int, int]:
    """One 30 m UTM 18N grid over the city, on Landsat's own pixel lattice
    (edges at 15 m past a multiple of 30): left, top, width, height."""
    x0, y0, x1, y1 = _ntas().to_crs(32618).total_bounds
    left = math.floor((x0 - 15) / 30) * 30 + 15 - 300
    top = math.ceil((y1 - 15) / 30) * 30 + 15 + 300
    return left, top, math.ceil((x1 + 300 - left) / 30), math.ceil((top - y0 + 300) / 30)


def _item(item_id: str) -> dict:
    return json.loads(_fetch(f"{_STAC}/collections/landsat-c2-l2/items/{item_id}"))


@lru_cache(maxsize=64)
def _scene(item_id: str):
    """lwir11 and qa_pixel over the city grid as uint16 arrays, read by window
    from the signed cloud-optimised files and kept as one .npz per image."""
    import numpy as np

    f = CACHE / f"landsat_{item_id}.npz"
    if f.exists():
        z = np.load(f)
        return z["st"], z["qa"]
    import planetary_computer
    import rasterio
    from rasterio.windows import Window

    left, top, w, h = _grid()
    assets = _item(item_id)["assets"]
    out = {}
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_USERAGENT=UA, GDAL_HTTP_MAX_RETRY=4):
        for name, asset, fill in (("st", "lwir11", 0), ("qa", "qa_pixel", 1)):
            with rasterio.open(planetary_computer.sign(assets[asset]["href"])) as ds:
                assert ds.crs.to_epsg() == 32618 and ds.res == (30.0, 30.0), (item_id, ds.crs, ds.res)
                col, row = (left - ds.transform.c) / 30, (ds.transform.f - top) / 30
                assert col == int(col) and row == int(row), (item_id, col, row)
                out[name] = ds.read(1, window=Window(int(col), int(row), w, h), boundless=True, fill_value=fill)
            time.sleep(1)
    np.savez_compressed(f, **out)
    return out["st"], out["qa"]


@lru_cache(maxsize=1)
def _nta_index():
    """For each 30 m pixel, the NTA polygon its centre is in (row number plus 1), or 0."""
    from affine import Affine
    from rasterio.features import rasterize

    left, top, w, h = _grid()
    g = _ntas().to_crs(32618)
    return rasterize(((geom, i + 1) for i, geom in enumerate(g.geometry)), out_shape=(h, w),
                     transform=Affine(30, 0, left, 0, -30, top), fill=0, dtype="uint16")


def _scene_f(item_id: str):
    """Degrees F per pixel, and which pixels are clear (QA_PIXEL bits 0 to 4 unset) and hold a temperature."""
    st, qa = _scene(item_id)
    return (st * 0.00341802 + 149.0 - 273.15) * 1.8 + 32, ((qa & 0b11111) == 0) & (st > 0)


@lru_cache(maxsize=64)
def _city_mean_f(item_id: str) -> float:
    f, ok = _scene_f(item_id)
    return float(f[(_nta_index() > 0) & ok].mean())


def _when(item_id: str) -> str:
    d = item_id.split("_")[3]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _surface(place) -> dict:
    """Place mean minus city land mean in each kept image where at least half
    of the place is clear (a mean of less is not a mean of the place: in a
    street canyon Landsat flags building shadow as cloud shadow). `place` is
    a weight per pixel: true or false for the key, a share of a 90 m cell for
    the tolerance. Also how many images pass with all of it clear and with any."""
    import numpy as np

    rr, cc = np.flatnonzero(place.any(axis=1)), np.flatnonzero(place.any(axis=0))
    if not len(rr):
        return {"n_images": 0, "n_images_all_clear": 0, "n_images_any_clear": 0}
    box = (slice(rr[0], rr[-1] + 1), slice(cc[0], cc[-1] + 1))
    w = place[box].astype("float64")
    total = float(w.sum())
    rows, n_all, n_any = [], 0, 0
    for item_id in sorted(landsat_lists()["kept"], key=_when):
        f, ok = _scene_f(item_id)
        wk = w * ok[box]
        n = float(wk.sum())
        n_all += n >= total - 1e-9
        n_any += n > 0
        if n > 0 and 2 * n >= total:
            rows.append((_when(item_id), float((f[box] * wk).sum() / n), _city_mean_f(item_id), n))
    if not rows:
        return {"n_images": 0, "n_images_all_clear": n_all, "n_images_any_clear": n_any}
    diffs = [h - c for _, h, c, _ in rows]
    return {"n_images": len(rows), "n_images_all_clear": n_all, "n_images_any_clear": n_any,
            "first": rows[0][0], "last": rows[-1][0],
            "mean_diff_f": sum(diffs) / len(diffs), "min_diff_f": min(diffs), "max_diff_f": max(diffs),
            "latest_surface_f": rows[-1][1], "latest_city_mean_f": rows[-1][2],
            "warmer_in_every_image": min(diffs) > 0, "cooler_in_every_image": max(diffs) < 0,
            "n_pixels": round(total, 1), "min_clear_pixels": round(min(r[3] for r in rows), 1)}


_SURFACE_FIELDS = ("mean_diff_f", "min_diff_f", "max_diff_f", "latest_surface_f")


def _with_tolerance(native_mask, cell_masks) -> dict:
    """The native 30 m answer, and for each number the largest change any of
    the nine alignments of a 90 m grid makes to it: what the app's cell
    geometry can account for, worked out without the app's answer."""
    out = _surface(native_mask)
    if not out["n_images"]:
        return out
    alt = [_surface(m) for m in cell_masks]
    alt = [a for a in alt if a["n_images"]]
    out["geometry_f"] = {k: round(max((abs(a[k] - out[k]) for a in alt), default=0.0), 2) for k in _SURFACE_FIELDS}
    for k in (*_SURFACE_FIELDS, "latest_city_mean_f"):
        out[k] = round(out[k], 2)
    return out


def _pixel_centres():
    import numpy as np

    left, top, w, h = _grid()
    return left + 30 * (np.arange(w) + 0.5), top - 30 * (np.arange(h) + 0.5)


def _cell_centres(a: int, b: int):
    """Centre of the 90 m cell each pixel belongs to, for a 90 m grid shifted by a and b pixels."""
    import numpy as np

    left, top, w, h = _grid()
    return (left + 90 * ((np.arange(w) - a) // 3) + 30 * a + 45,
            top - 90 * ((np.arange(h) - b) // 3) - 30 * b - 45)


def _share(cx, cy, size_m: float, x: float, y: float, radius_m: float):
    """For each pixel, the share of the square of side size_m centred at
    (cx, cy) that lies inside the circle, from 81 points per square. With the
    centres of 90 m cells this is the weight the app says it gives a cell."""
    import numpy as np

    cols = np.flatnonzero(np.abs(cx - x) <= radius_m + size_m)
    rows = np.flatnonzero(np.abs(cy - y) <= radius_m + size_m)
    off = ((np.arange(9) + 0.5) / 9 - 0.5) * size_m
    dx, dy = cx[cols][:, None] + off - x, cy[rows][:, None] + off - y
    out = np.zeros((len(cy), len(cx)))
    out[np.ix_(rows, cols)] = ((dy[:, None, :, None] ** 2 + dx[None, :, None, :] ** 2) <= radius_m ** 2).mean(axis=(2, 3))
    return out


def heat_surface(lat: float, lon: float, radius_m: float = 150) -> dict:
    """Surface temperature of the ground within 150 m against the city's land
    mean, per image, at 30 m, land pixels only (the sentence says "ground").
    `half_pixel_south_east_f` is a diagnosis, not a key: the same circle moved
    15 m east and 15 m south, where surface_shift_fit() found the app's raster
    to sit on 2026-10-02."""
    from pyproj import Transformer

    x, y = Transformer.from_crs(4326, 32618, always_xy=True).transform(lon, lat)
    land = _nta_index() > 0
    xs, ys = _pixel_centres()
    out = _with_tolerance((((xs[None, :] - x) ** 2 + (ys[:, None] - y) ** 2) <= radius_m ** 2) & land,
                          [_share(*_cell_centres(a, b), 90, x, y, radius_m) * land for a in range(3) for b in range(3)])
    moved = _surface(_share(xs, ys, 30, x + 15, y - 15, radius_m) * land)
    out["half_pixel_south_east_f"] = {k: round(moved[k], 2) for k in _SURFACE_FIELDS} if moved["n_images"] else {}
    return out


def surface_shift_fit(app: list[dict], reach_m: int = 30, step_m: int = 5) -> list[tuple]:
    """A diagnosis, not a key: is the app's surface raster where Landsat's
    is? `app` is the app's heat_surface values with lat and lon, one per
    address. For each shift (east, north) of the 150 m circle, land pixels
    weighted by their share inside it, the mean absolute difference from the
    app's four numbers over all addresses, best first. A raster in register
    has its best fit at (0, 0)."""
    from pyproj import Transformer

    tr = Transformer.from_crs(4326, 32618, always_xy=True)
    xs, ys = _pixel_centres()
    land = _nta_index() > 0
    out = []
    for dx in range(-reach_m, reach_m + 1, step_m):
        for dy in range(-reach_m, reach_m + 1, step_m):
            errs = []
            for v in app:
                x, y = tr.transform(v["lon"], v["lat"])
                r = _surface(_share(xs, ys, 30, x + dx, y + dy, 150) * land)
                errs += [abs(r[k] - v[k]) for k in _SURFACE_FIELDS if r["n_images"] and v.get(k) is not None]
            out.append((round(sum(errs) / len(errs), 3), dx, dy))
    return sorted(out)


def heat_surface_district(code: str) -> dict:
    """The same over a district: every 30 m pixel whose centre is inside the union of its NTAs."""
    import numpy as np
    import shapely.ops
    from pyproj import Transformer

    g = _ntas()
    ids = [i + 1 for i in np.flatnonzero((g["cdta2020"] == code.upper()).to_numpy())]
    native = np.isin(_nta_index(), ids)
    outline = shapely.ops.transform(Transformer.from_crs(4326, 32618, always_xy=True).transform, district_outline(code))
    rows, cols = np.flatnonzero(native.any(axis=1)), np.flatnonzero(native.any(axis=0))
    r0, r1, c0, c1 = max(rows[0] - 3, 0), rows[-1] + 4, max(cols[0] - 3, 0), cols[-1] + 4
    land = _nta_index() > 0
    masks = []
    for a in range(3):
        for b in range(3):
            xs, ys = _cell_centres(a, b)
            m = np.zeros_like(native)
            xx, yy = np.meshgrid(xs[c0:c1], ys[r0:r1])
            m[r0:r1, c0:c1] = shapely.contains_xy(outline, xx, yy)
            masks.append(m & land)
    return _with_tolerance(native, masks)


def landsat_selection() -> list[dict]:
    """The rule applied here to every image the app lists: tier T1, scene
    cloud cover at most 20%, 1 June to 10 September, and at least 95% of the
    pixels inside NTA polygons clear."""
    lists = landsat_lists()
    land = _nta_index() > 0
    out = []
    for item_id in lists["kept"] + lists["skipped"]:
        p = _item(item_id)["properties"]
        _, qa = _scene(item_id)
        clear = round(100 * float(((qa & 0b11111) == 0)[land].mean()), 1)
        day = p["datetime"][5:10]
        keep = (p["landsat:collection_category"] == "T1" and p["eo:cloud_cover"] <= 20
                and "06-01" <= day <= "09-10" and clear >= 95.0)
        out.append({"id": item_id, "tier": p["landsat:collection_category"], "scene_cloud_pct": p["eo:cloud_cover"],
                    "clear_land_pct": clear, "key_keeps": keep, "app_keeps": item_id in lists["kept"]})
    return out


def landsat_candidates() -> list[dict]:
    """Every Landsat 8 or 9 image over the middle of the city in the rule's
    months, 2023 to 2026, from a STAC search: the list the app chose from."""
    out = []
    for year in (2023, 2024, 2025, 2026):
        d = json.loads(_fetch(f"{_STAC}/search", body={
            "collections": ["landsat-c2-l2"], "intersects": {"type": "Point", "coordinates": [-73.94, 40.70]},
            "datetime": f"{year}-06-01T00:00:00Z/{year}-09-10T23:59:59Z", "limit": 250,
            "query": {"platform": {"in": ["landsat-8", "landsat-9"]}}}))
        out += [{"id": f["id"], "scene_cloud_pct": f["properties"]["eo:cloud_cover"],
                 "tier": f["properties"]["landsat:collection_category"]} for f in d["features"]]
    return out


def landsat_city_mean_variants() -> dict:
    """How far the choice of land mask moves an image's city mean: the mean
    over NTA pixels, the same without pixels Landsat flags as water, and the
    same over 90 m cells that lie wholly inside an NTA polygon."""
    import numpy as np

    idx = _nta_index() > 0
    h3, w3 = idx.shape[0] // 3 * 3, idx.shape[1] // 3 * 3
    whole = idx[:h3, :w3].reshape(h3 // 3, 3, w3 // 3, 3).all(axis=(1, 3)).repeat(3, 0).repeat(3, 1)
    whole = np.pad(whole, ((0, idx.shape[0] - h3), (0, idx.shape[1] - w3)))
    out = {}
    for item_id in landsat_lists()["kept"]:
        f, ok = _scene_f(item_id)
        _, qa = _scene(item_id)
        out[_when(item_id)] = {"nta_pixels": round(float(f[idx & ok].mean()), 2),
                               "no_water_flag": round(float(f[idx & ok & ((qa & 0x80) == 0)].mean()), 2),
                               "whole_90m_cells": round(float(f[whole & ok].mean()), 2)}
    return out


# ---------------------------------------------------------------- NYC Land Cover 2017 (6 inch)
_LC = "/vsizip/" + str(ROOT / "outputs/terramind_nyc/raw/Land_Cover_2017.zip") + "/Land_Cover/NYC_2017_LiDAR_LandCover.img"
_FT = 0.3048006096  # metres in a US survey foot, the unit of EPSG:2263


def _shares(counts) -> dict:
    """Shares of the classified ground: 1 tree canopy, 2 grass or shrubs, 3 bare soil, 4 water, 5 to 8 paved or built."""
    c = [int(x) for x in counts] + [0] * 9
    n = sum(c[1:9])

    def pct(k):
        return round(100 * k / n, 2) if n else None

    return {"built_pct": pct(sum(c[5:9])), "green_pct": pct(c[1] + c[2]), "tree_canopy_pct": pct(c[1]),
            "water_pct": pct(c[4]), "bare_pct": pct(c[3]), "n_pixels": n, "n_unclassified": c[0],
            "green_pct_of_land": round(100 * (c[1] + c[2]) / (n - c[4]), 2) if n - c[4] else None}


def _cached(name: str, compute) -> dict:
    f = CACHE / name
    if f.exists():
        return json.loads(f.read_text())
    out = compute()
    f.write_text(json.dumps(out))
    return out


def city_landcover(lat: float, lon: float, radius_m: int = 500) -> dict:
    """Every 6 inch pixel whose centre is within the radius, counted by class."""
    def compute():
        import numpy as np
        import rasterio
        from pyproj import Transformer
        from rasterio.windows import Window

        x, y = Transformer.from_crs(4326, 2263, always_xy=True).transform(lon, lat)
        r = radius_m / _FT
        with rasterio.open(_LC) as ds:
            t = ds.transform
            # Clipped to the raster: at the city's edge (Tottenville) the circle runs past it, over New Jersey.
            c0, c1 = max(int((x - r - t.c) / t.a), 0), min(int((x + r - t.c) / t.a) + 1, ds.width)
            r0, r1 = max(int((t.f - y - r) / -t.e), 0), min(int((t.f - y + r) / -t.e) + 1, ds.height)
            # Never boundless: that path reads through a VRT in an order that seeks backwards,
            # and a backward seek in a zipped 97 GB file starts the inflate again from byte 0.
            a = ds.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))
        xs = (t.c + (np.arange(c0, c1) + 0.5) * t.a - x).astype("float32")
        ys = (t.f + (np.arange(r0, r1) + 0.5) * t.e - y).astype("float32")
        inside = (xs[None, :] ** 2 + ys[:, None] ** 2) <= r * r
        return _shares(np.bincount(a[inside], minlength=9))
    return _cached(f"landcover_{lat:.6f}_{lon:.6f}_{radius_m}.json", compute)


def landcover_polygon(name: str, geom, step: int = 8) -> dict:
    """Every `step`th pixel (each way) whose centre is inside a WGS84 polygon."""
    def compute():
        import numpy as np
        import rasterio
        import shapely.ops
        from affine import Affine
        from pyproj import Transformer
        from rasterio.features import rasterize
        from rasterio.windows import Window

        g = shapely.ops.transform(Transformer.from_crs(4326, 2263, always_xy=True).transform, geom)
        x0, y0, x1, y1 = g.bounds
        counts = np.zeros(9, dtype="int64")
        with rasterio.open(_LC) as ds:
            t = ds.transform
            c0, r0 = int((x0 - t.c) / t.a) // step * step, int((t.f - y1) / -t.e) // step * step
            nc, nr = int((x1 - t.c) / t.a) // step + 1 - c0 // step, int((t.f - y0) / -t.e) // step + 1 - r0 // step
            # A grid of step-sized cells whose centres are the centres of the sampled native pixels.
            coarse = Affine(t.a * step, 0, t.c + (c0 + 0.5) * t.a - t.a * step / 2,
                            0, t.e * step, t.f + (r0 + 0.5) * t.e - t.e * step / 2)
            inside = rasterize([(g, 1)], out_shape=(nr, nc), transform=coarse, fill=0, dtype="uint8").astype(bool)
            strip = 128  # sampled rows per read: 1024 native rows
            for k in range(0, nr, strip):
                rows = min(strip, nr - k)
                a = ds.read(1, window=Window(c0, r0 + k * step, nc * step, rows * step))
                counts += np.bincount(a[::step, ::step][inside[k:k + rows]], minlength=9)[:9]
        return _shares(counts)
    return _cached(f"landcover_{name}_step{step}.json", compute)


def city_landcover_district(code: str) -> dict:
    return landcover_polygon(code.upper(), district_outline(code))


def nta_landcover(nta2020: str) -> dict:
    """Land cover of one NTA polygon: the outside check on the index's green space figure."""
    g = _ntas()
    return landcover_polygon(nta2020, g[g["nta2020"] == nta2020].geometry.iloc[0])


# ---------------------------------------------------------------- everything for one place
def all_heat_keys(lat: float, lon: float, record: bool = True) -> dict:
    """Every key for one point, in one dict."""
    a = nta_at(lat, lon)
    forecast = nws_heat_forecast(lat, lon)  # first: it is compared with a fetch the app made seconds ago
    return {"nta": a, "nws_heat_forecast": forecast, "heat_surface": heat_surface(lat, lon), "hvi": hvi(lat, lon),
            "hvi_ac_values": hvi_ac_values(a["boroname"]) if a else [],
            "nta_landcover": nta_landcover(a["nta2020"]) if a else None,
            "heat_visits": heat_visits_at(lat, lon), "heat_station": heat_station(lat, lon, record),
            "city_landcover": city_landcover(lat, lon),
            "cool_features": cool_features(lat, lon), "npcc4": npcc4_table()}


def all_heat_district_keys(code: str) -> dict:
    """Every key for one community district ('QN12'), in one dict."""
    c = district_outline(code).representative_point()
    return {"heat_surface": heat_surface_district(code), "hvi": hvi_district(code), "heat_visits": heat_visits(code),
            "city_landcover": city_landcover_district(code), "vegetative_cover_2143": vegetative_cover_2143(code),
            "cool_features": cool_features_district(code), "npcc4": npcc4_table(),
            "centre": {"lat": c.y, "lon": c.x}}


def _selfcheck() -> None:
    """The traps this file exists to step around, as asserts: python keys_heat.py check"""
    assert _geo_id("Borough", "Bronx", name="Bronx") == "1"  # alphabetical
    assert _geo_id("CD", "Manhattan", cd=1) == "101" and _geo_id("CD", "Manhattan", cd=11) == "111"  # city borough code
    assert _geo_id("CDTA2020", "Manhattan", cd=5) == "6105"  # county FIPS
    assert _geo_id("NTA2020", "Bronx", name="Kingsbridge-Marble Hill") == "50802"
    assert heat_visits("MN05")["suppressed"] and heat_visits("MN05")["n"] is None and heat_visits("MN64") is None
    assert len(_period_ids()["2018-22"]) == 2  # if the portal drops the duplicate label this says so
    t = npcc4_table()
    assert t["2050s"]["days_ge_90"] == {"baseline": 17, "10": 32, "25": 38, "75": 62, "90": 69}, t["2050s"]
    assert t["2080s"]["days_ge_95"]["90"] == 73 and t["2050s"]["heat_waves"]["75"] == 8
    assert abs(haversine_m(40.7, -74.0, 40.7, -73.99) - 843) < 1
    print("ok")


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["check"]:
        _selfcheck()
    elif len(sys.argv) == 2:
        print(json.dumps(all_heat_district_keys(sys.argv[1]), indent=1, default=str))
    else:
        print(json.dumps(all_heat_keys(float(sys.argv[1]), float(sys.argv[2])), indent=1, default=str))
