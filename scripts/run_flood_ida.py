"""Put IBM and ESA's official TerraMind-base-Flood through the Ida test the
Prithvi water layer was judged by (experimental, one-off).

The model is `ibm-esa-geospatial/TerraMind-base-Flood`, fine-tuned on
ImpactMesh-Flood (Copernicus EMS flood maps with Sentinel-1 RTC, Sentinel-2
L2A and the Copernicus DEM over four dates: a month before, just before, the
event and after). It reads all three and labels each 10 m pixel flood or not.
The checkpoint is a PyTorch file, read with `weights_only=True`; its pickle
holds only tensors and an OrderedDict.

Inputs over the city, on the 10 m grid the Prithvi layer uses:
  * Sentinel-2 L2A, every tile of one date: 2021-08-13 (a month before),
    2021-08-25 (just before), 2021-09-02 (the Prithvi layer's post scene, the
    first clear pass after the rain of 1 September), 2021-09-07 (after);
  * Sentinel-1 RTC, relative orbit 33 (the one that covers the whole city):
    2021-07-26, 2021-08-19, 2021-09-12, 2021-09-24. Planetary Computer has no
    pass of it between 19 August and 12 September, so the radar's event image
    is 11 days after the rain (orbit 106 passed on 5 September but covers 4%
    of the city). Backscatter in dB, as ImpactMesh's statistics are;
  * Copernicus DEM GLO-30, the same for every date.
Normalised with the ImpactMesh-Flood statistics of the code release that
matches the checkpoint (IBM/ImpactMesh at 6c76a0a, 2026-02-27; the current
code has new statistics for a three-class v1 dataset). The released
checkpoint has two classes; ImpactMesh v0 masks were flood or not.

Scoring (scripts/run_eo_batch.py `ida_marks_score`): the 153 USGS
high-water marks, water within 500 m, and the chance rate (the share of the
observed land within 500 m of the model's flood pixels), on exactly the land
the Prithvi layer's Ida raster observed. A second line scores all the city's
land, since radar sees through cloud.

    uv run python scripts/run_flood_ida.py --inputs-only   # fetch and cache the scenes
    python3 gpu_lock.py uv run python scripts/run_flood_ida.py
    uv run python scripts/run_flood_ida.py --rescore        # rescore the saved probabilities

Writes data/experimental/flood_terramind_ida.json and, under outputs/flood_ida/
(git-ignored), the inputs and the flood raster.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

REPO, REVISION = "ibm-esa-geospatial/TerraMind-base-Flood", "1e4b2429d17234922f8d92beb0d725af4db85c08"
FILE, SHA256 = "TerraMind_v1_base_ImpactMesh_flood.pt", "22627584c2db618c2f6ddb64b411a95762a893becb25104e3f66bfebecaa71e9"
S2_DATES = ["2021-08-13", "2021-08-25", "2021-09-02", "2021-09-07"]
S1_DATES = ["2021-07-26", "2021-08-19", "2021-09-12", "2021-09-24"]
S1_ORBIT = 33  # orbit 106 covers 4% of the city
S2_BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B11", "B12"]
# ImpactMesh-Flood statistics at IBM/ImpactMesh 6c76a0a (impactmesh_datamodule.py).
MEAN = {"S2L2A": [1223.128, 1251.355, 1423.443, 1408.984, 1786.818, 2448.316, 2685.642, 2745.795, 2817.936,
                  3194.081, 1964.659, 1399.317], "S1RTC": [-9.98, -15.968], "DEM": [141.786]}
STD = {"S2L2A": [2358.709, 2227.598, 2082.363, 2068.519, 2086.682, 2003.085, 2019.494, 2060.309, 2014.732,
                 2992.644, 1414.951, 1218.357], "S1RTC": [4.24, 4.105], "DEM": [189.363]}
CROP, STRIDE = 256, 208  # the checkpoint's tiled inference parameters
CACHE = ROOT / "outputs" / "flood_ida"
OUT = ROOT / "data" / "experimental" / "flood_terramind_ida.json"


def load_model():
    import torch
    from huggingface_hub import hf_hub_download
    from terratorch.tasks import SemanticSegmentationTask

    path = hf_hub_download(REPO, FILE, revision=REVISION)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != SHA256:
        raise RuntimeError(f"{FILE}: SHA-256 {digest}, expected {SHA256}")
    task = SemanticSegmentationTask(model_factory="EncoderDecoderFactory", model_args={
        "backbone": "terramind_v1_base", "backbone_pretrained": False,
        "backbone_modalities": ["S2L2A", "S1RTC", "DEM"], "backbone_use_temporal": True,
        "backbone_temporal_pooling": "concat", "backbone_temporal_n_timestamps": 4,
        "necks": [{"name": "SelectIndices", "indices": [2, 5, 8, 11]},
                  {"name": "ReshapeTokensToImage", "remove_cls_token": False},
                  {"name": "LearnedInterpolateToPyramidal"}],
        "decoder": "UNetDecoder", "decoder_channels": [512, 256, 128, 64], "head_dropout": 0.1,
        "num_classes": 2}, loss="dice", ignore_index=-1)
    state = torch.load(path, map_location="cpu", weights_only=True)["state_dict"]
    task.load_state_dict(state, strict=True)  # every tensor of the checkpoint, nothing left random
    return task.model.eval()


def read_inputs(ref):
    """(S2 (4, 12, H, W) DN, S2 clear masks (4, H, W), S1 (4, 2, H, W) dB, DEM (H, W) m, scene ids)."""
    import numpy as np
    import planetary_computer as pc
    from pystac_client import Client

    from app.eo import prithvi

    cache = CACHE / f"inputs_s1_orbit{S1_ORBIT}.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        return z["s2"], z["clear"], z["s1"], z["dem"], json.loads(str(z["scenes"]))
    old = sorted(CACHE.glob("inputs_s1_orbit*.npz"))  # the optical scenes and DEM do not depend on the orbit
    client = Client.open(prithvi.STAC_URL, modifier=pc.sign_inplace)
    bbox = [-74.26, 40.49, -73.69, 40.92]
    h, w = ref.shape
    s2 = np.zeros((4, len(S2_BANDS), h, w), "uint16")
    clear = np.zeros((4, h, w), bool)
    s1 = np.zeros((4, 2, h, w), "float32")
    scenes: dict = {"S2L2A": [], "S1RTC": [], "DEM": []}
    for t, day in enumerate(S2_DATES if not old else []):
        items = list(client.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=day).items())
        scenes["S2L2A"].append([i.id for i in items])
        for it in sorted(items, key=lambda i: i.properties.get("eo:cloud_cover", 100)):
            for b, band in enumerate(S2_BANDS):
                dn = prithvi.read_band(it, band, ref, resampling="nearest")
                s2[t, b] = np.where((s2[t, b] == 0) & (dn > 0), dn, s2[t, b])
            clear[t] |= prithvi.clear_mask(it, ref)
        print(f"S2 {day}: {len(items)} items, {clear[t].mean():.1%} clear", flush=True)
    for t, day in enumerate(S1_DATES):
        items = [i for i in client.search(collections=["sentinel-1-rtc"], bbox=bbox, datetime=day).items()
                 if i.properties.get("sat:relative_orbit") == S1_ORBIT]
        scenes["S1RTC"].append([i.id for i in items])
        for it in items:
            for b, band in enumerate(("vv", "vh")):
                lin = prithvi.read_band(it, band, ref, resampling="bilinear").astype("float32")
                db = np.where(lin > 0, 10 * np.log10(np.clip(lin, 1e-6, None)), 0)
                s1[t, b] = np.where((s1[t, b] == 0) & (db != 0), db, s1[t, b])
        print(f"S1 {day}: {len(items)} items, {(s1[t, 0] != 0).mean():.1%} filled", flush=True)
    if old:
        z = np.load(old[0], allow_pickle=False)
        s2, clear, dem = z["s2"], z["clear"], z["dem"]
        prev = json.loads(str(z["scenes"]))
        scenes["S2L2A"], scenes["DEM"] = prev["S2L2A"], prev["DEM"]
        np.savez_compressed(cache, s2=s2, clear=clear, s1=s1, dem=dem, scenes=json.dumps(scenes))
        return s2, clear, s1, dem, scenes
    dem = np.zeros((h, w), "float32")
    for it in client.search(collections=["cop-dem-glo-30"], bbox=bbox).items():
        scenes["DEM"].append(it.id)
        tile = prithvi.read_band(it, "data", ref, resampling="bilinear").astype("float32")
        dem = np.where(dem == 0, tile, dem)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, s2=s2, clear=clear, s1=s1, dem=dem, scenes=json.dumps(scenes))
    return s2, clear, s1, dem, scenes


def predict(net, s2, s1, dem, batch: int = 8):
    """Flood probability on the grid: 256 px crops every 208 px, softmax
    averaged where crops overlap."""
    import numpy as np
    import torch

    from app.eo.prithvi import device

    dev = device()
    net = net.to(dev)
    norm = {}
    for name, arr in (("S2L2A", s2.astype("float32")), ("S1RTC", s1), ("DEM", np.repeat(dem[None, None], 4, 0))):
        m, sd = (np.array(v, "float32").reshape(1, -1, 1, 1) for v in (MEAN[name], STD[name]))
        norm[name] = ((arr - m) / sd).transpose(1, 0, 2, 3)  # (C, T, H, W)
    _, _, h, w = norm["S2L2A"].shape
    ph, pw = max(CROP - h, (-(h - CROP)) % STRIDE), max(CROP - w, (-(w - CROP)) % STRIDE)
    for name in norm:
        norm[name] = np.pad(norm[name], ((0, 0), (0, 0), (0, ph), (0, pw)), mode="reflect")
    H, W = h + ph, w + pw
    prob, hits = np.zeros((H, W), "float32"), np.zeros((H, W), "float32")
    corners = [(i, j) for i in range(0, H - CROP + 1, STRIDE) for j in range(0, W - CROP + 1, STRIDE)]
    with torch.no_grad():
        for k in range(0, len(corners), batch):
            group = corners[k:k + batch]
            x = {n: torch.from_numpy(np.stack([a[:, :, i:i + CROP, j:j + CROP] for i, j in group])).to(dev)
                 for n, a in norm.items()}
            p = torch.softmax(net(x).output, 1)[:, 1].cpu().numpy()
            for (i, j), pi in zip(group, p, strict=True):
                prob[i:i + CROP, j:j + CROP] += pi
                hits[i:i + CROP, j:j + CROP] += 1
            if k % (batch * 25) == 0:
                print(f"  {k + len(group)} of {len(corners)} crops", flush=True)
    return (prob / np.maximum(hits, 1))[:h, :w]


def sweep(prob, seen, transform, crs) -> list[dict]:
    """The Ida score at lower flood thresholds, with the binomial chance of
    as many hits or more if marks fell at random (marks cluster, so this
    overstates the evidence), and the number of separate places the hits
    are at (marks within 1 km of each other are one place)."""
    import geopandas as gpd
    import numpy as np
    import rasterio
    import run_eo_batch as eo
    from scipy.ndimage import distance_transform_edt
    from scipy.stats import binom

    marks = gpd.read_file(ROOT / "data" / "ida_2021_hwms_ny.geojson").to_crs(crs)
    rows, cols = rasterio.transform.rowcol(transform, marks.geometry.x.values, marks.geometry.y.values)
    out = []
    for th in (0.5, 0.3, 0.1, 0.05):
        a = np.where(prob >= th, 1, 0).astype("uint8")
        a[~seen] = 255
        r = eo.ida_marks_score(a, transform, crs)
        near = distance_transform_edt(a != 1) * transform.a <= 500
        hit = [(x, y) for x, y, rr, cc in zip(marks.geometry.x, marks.geometry.y, rows, cols, strict=True)
               if 0 <= rr < a.shape[0] and 0 <= cc < a.shape[1] and seen[rr, cc] and near[rr, cc]]
        places: list[list] = []
        for x, y in hit:
            for p in places:
                if any(np.hypot(x - u, y - v) < 1000 for u, v in p):
                    p.append((x, y))
                    break
            else:
                places.append([(x, y)])
        out.append({"threshold": th, **r, "places_hit": len(places),
                    "binomial_p_at_least_this_many": round(float(binom.sf(r["n_marks_with_water"] - 1, r["n_marks"],
                                                                          r["chance_share"])), 3)})
    return out


def main() -> int:
    import numpy as np
    import rasterio
    import run_eo_batch as eo

    from app.eo import prithvi

    t0 = time.time()
    ref = prithvi.grid(eo.NYC_BBOX)
    s2, clear, s1, dem, scenes = read_inputs(ref)
    print(f"inputs ready in {time.time() - t0:.0f} s", flush=True)
    if "--inputs-only" in sys.argv:  # fetch the scenes without holding the GPU lock
        return 0
    saved = CACHE / "flood_prob.npy"
    if "--rescore" in sys.argv and saved.exists():  # score the saved probabilities again, no model run
        prob = np.load(saved).astype("float32")
    else:
        prob = predict(load_model(), s2, s1, dem)
    flood = prob >= 0.5
    land = eo.land_mask(ref)
    with rasterio.open(ROOT / "data" / "eo" / "prithvi_new_water_2021-09-01.tif") as src:
        prithvi_seen = src.read(1) != 255
        transform, crs = src.transform, src.crs
    assert prithvi_seen.shape == ref.shape and transform == ref.rio.transform()
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(CACHE / "flood_prob.npy", prob.astype("float16"))

    def raster(seen):
        a = np.where(flood, 1, 0).astype("uint8")
        a[~seen] = 255
        return a

    event_s2 = s2[2, 1] > 0
    same_land = raster(prithvi_seen)
    all_land = raster(land & event_s2 & (s1[2, 0] != 0))
    water_outside_land = ~land & event_s2
    out = {
        "what": "TerraMind-base-Flood (official, ImpactMesh) on Hurricane Ida, scored as the Prithvi layer is",
        "run_date": str(date.today()), "model": REPO, "revision": REVISION, "file": FILE, "sha256": SHA256,
        "licence": "Apache-2.0 (model card and repository metadata)",
        "s2_dates": S2_DATES, "s1_dates": S1_DATES, "s1_relative_orbit": S1_ORBIT, "scenes": scenes,
        "normalisation": "ImpactMesh-Flood v0 statistics, IBM/ImpactMesh 6c76a0a",
        "threshold": "flood probability 0.5 (argmax of two classes)",
        "same_land_as_prithvi": eo.ida_marks_score(same_land, transform, crs),
        "all_land_with_radar_and_optical": eo.ida_marks_score(all_land, transform, crs),
        "threshold_sweep": sweep(prob, prithvi_seen, transform, crs),
        "flood_share_of_land_seen_pct": round(100 * float(flood[prithvi_seen].mean()), 2),
        "flood_share_of_open_water_outside_land_pct": round(100 * float(flood[water_outside_land].mean()), 2),
        "event_s2_clear_on_land_pct": round(100 * float(clear[2][land].mean()), 1),
        "prithvi_for_comparison": {k: json.loads((ROOT / "data" / "experimental" / "water.json").read_text())[k]
                                   for k in ("n_marks", "n_marks_with_water", "marks_pct", "chance_pct")},
        "seconds": round(time.time() - t0),
    }
    with rasterio.open(CACHE / "terramind_flood_2021-09-01.tif", "w", driver="GTiff", dtype="uint8", count=1,
                       height=ref.shape[0], width=ref.shape[1], crs=crs, transform=transform, compress="deflate",
                       nodata=255) as dst:
        dst.write(all_land, 1)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "scenes"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
