"""Score the NYC land-cover models against the 2021 six-inch land cover map
(experimental, offline; the 2021 map is a local test key and never leaves
outputs/).

Methods, all on the same Sentinel-2 scenes and the same pixels:
  * each model trained by scripts/train_cover.py (TerraMind, UNet, MLP), from
    its saved predictions;
  * the app's current adapter (`lulc_nyc`, scripts/lulc_adapter.py), run here on the
    same scenes (`--run-adapter`, under the GPU lock), its one label per pixel
    counted as a fraction of 1;
  * persistence: the 2017 map itself, as a prediction of 2021.

Everything is compared in five groups every method can express: tree
canopy, grass and shrub, bare soil, water, paved or built over (building,
road, other paved, railroad; the adapter's "built"). Pixels: city land, the
2021 map covering the cell, and a clear view in the scene. Scores are at
30 m (3 by 3 cells averaged, all nine valid), because Sentinel-2 is located to
about one pixel, and on the test squares no model trained on (see
train_cover.py), with all land as a second line.

  * accuracy: mean absolute error and bias of each group's share, and R2;
  * a district's paved share against the 2021 map (community districts,
    test-square pixels), and the same for the adapter on all land beside
    its 7.7 point bias against WorldCover;
  * noise: the two 2021 scenes against each other, district paved share;
  * change: predicted 2017 to 2021 change in paved and canopy share against
    the maps' change, cell by cell, and at sites of DOB new-building permits
    issued 2016 to 2019 against land with no new-building or demolition
    permit within 200 m from 2015 to 2021.

    python3 gpu_lock.py uv run python scripts/eval_cover.py --run-adapter
    uv run python scripts/eval_cover.py

Writes data/experimental/landcover_nyc_eval.json (scores only, no map).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.eo.landcover import GROUPS  # noqa: E402

DATA = ROOT / "outputs" / "terramind_nyc"
MODELS = DATA / "models"
OUT = ROOT / "data" / "experimental" / "landcover_nyc_eval.json"

# 8 label classes -> 5 groups (train_cover.CLASSES order)
FROM8 = [0, 1, 2, 3, 4, 4, 4, 4]
# adapter classes (water, built, trees, grass, bare) -> groups
FROM_ADAPTER = [3, 4, 0, 1, 2]


def to_groups8(frac):
    import numpy as np

    out = np.zeros((5, *frac.shape[1:]), "float32")
    for c, g in enumerate(FROM8):
        out[g] += frac[c]
    return out


def adapter_groups(labels):
    import numpy as np

    out = np.zeros((5, *labels.shape), "float32")
    for c, g in enumerate(FROM_ADAPTER):
        out[g][labels == c] = 1
    out[:, labels == 255] = np.nan
    return out


def block(a, k: int = 3):
    """Mean over k by k cells; (..., H, W) -> (..., H//k, W//k)."""
    h, w = a.shape[-2] // k * k, a.shape[-1] // k * k
    a = a[..., :h, :w]
    return a.reshape(*a.shape[:-2], h // k, k, w // k, k).mean(axis=(-3, -1))


def block_all(m, k: int = 3):
    return block(m.astype("float32"), k) == 1


def scene_paths(year: str) -> list[Path]:
    return sorted(DATA.glob(f"s2_{year}-*.tif"))


def run_adapter() -> None:
    import lulc_adapter as tm
    import numpy as np
    from train_cover import read_scene

    for p in scene_paths("2017") + scene_paths("2021"):
        s2, clear = read_scene(p)
        labels = tm.classify(s2)
        labels[~clear] = 255
        np.save(MODELS / f"adapter_lulc_nyc_{p.stem}.npy", labels)
        print(f"adapter: {p.stem}", flush=True)


def scores(pred, truth, valid) -> dict:
    """Per group: MAE and bias in percentage points, R2, at the cells in `valid`."""
    import numpy as np

    out = {}
    for g, name in enumerate(GROUPS):
        p, t = pred[g][valid], truth[g][valid]
        ss = ((t - t.mean()) ** 2).sum()
        out[name] = {"mae_pts": round(100 * float(np.abs(p - t).mean()), 2),
                     "bias_pts": round(100 * float((p - t).mean()), 2),
                     "r2": round(float(1 - ((p - t) ** 2).sum() / ss), 3) if ss else None}
    out["mean_mae_pts"] = round(float(np.mean([out[n]["mae_pts"] for n in GROUPS])), 2)
    return out


def district_paved(share, valid, zones, min_cells: int = 500) -> dict[str, float]:
    import numpy as np

    codes, raster = zones
    out = {}
    for i, c in enumerate(codes):
        m = (raster == i + 1) & valid
        if m.sum() >= min_cells:
            out[c] = float(np.nanmean(share[m]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-adapter", action="store_true")
    args = ap.parse_args()

    import numpy as np
    import rasterio
    import run_landcover_batch as lb
    from train_cover import read_labels, read_scene, split_map

    from app.eo import prithvi

    MODELS.mkdir(parents=True, exist_ok=True)
    if args.run_adapter:
        run_adapter()
    ref = prithvi.grid(lb.NYC_BBOX)
    land = lb.land_mask(ref)
    split = split_map(ref.shape)
    f17, cov17 = read_labels("2017")
    f21, cov21 = read_labels("2021")
    t17, t21 = to_groups8(f17), to_groups8(f21)
    s21, s17 = scene_paths("2021"), scene_paths("2017")
    clear = {p.stem: read_scene(p)[1] for p in s21 + s17}
    districts = lb.zones(ref, "cdta2020")

    methods: dict[str, dict[str, np.ndarray]] = {}
    for p in sorted(MODELS.glob("*_s2_2021-*.npy")):
        name, scene = p.stem.split("_s2_")[0], "s2_" + p.stem.split("_s2_")[1]
        arr = np.load(p)
        methods.setdefault(name, {})[scene] = (adapter_groups(arr) if name.startswith("adapter")
                                               else to_groups8(arr.astype("float32") / 1000))
    for name in list(methods):
        for p in s17:
            f = MODELS / f"{name}_{p.stem}.npy"
            if f.exists():
                arr = np.load(f)
                methods[name][p.stem] = (adapter_groups(arr) if name.startswith("adapter")
                                         else to_groups8(arr.astype("float32") / 1000))
    methods["persistence_2017_map"] = {p.stem: t17 for p in s21}

    out: dict = {"what": "NYC land-cover models against the 2021 six-inch map (local test key)",
                 "run_date": str(date.today()), "groups": list(GROUPS),
                 "scenes_2021": [p.stem for p in s21], "scenes_2017": [p.stem for p in s17],
                 "scale": "30 m cells (3 by 3 Sentinel-2 pixels), all nine valid", "methods": {}}
    base_valid = land & (cov21 >= 0.95)
    for name, preds in methods.items():
        res: dict = {}
        for scene in [p.stem for p in s21]:
            if scene not in preds:
                continue
            pred = preds[scene]
            valid = base_valid & clear[scene] & ~np.isnan(pred[0])
            vb = block_all(valid)
            pb, tb = block(np.nan_to_num(pred)), block(t21)
            test_b = block_all(split == 2) & vb
            res[scene] = {"test_squares": scores(pb, tb, test_b), "all_land": scores(pb, tb, vb),
                          "cells_test": int(test_b.sum()), "cells_all": int(vb.sum())}
            # District paved share against the 2021 map, at 10 m pixels.
            for where, m in (("test_squares", valid & (split == 2)), ("all_land", valid)):
                ours, theirs = district_paved(pred[4], m, districts), district_paved(t21[4], m, districts)
                d = np.array([100 * (ours[c] - theirs[c]) for c in ours if c in theirs])
                res[scene][f"district_paved_{where}"] = {
                    "n_districts": len(d), "median_bias_pts": round(float(np.median(d)), 1),
                    "median_abs_pts": round(float(np.median(np.abs(d))), 1), "max_abs_pts": round(float(np.abs(d).max()), 1)}
        # Noise between the two 2021 scenes, district paved share, on pixels both saw.
        sc = [p.stem for p in s21 if p.stem in preds]
        if len(sc) >= 2:
            both = land & clear[sc[0]] & clear[sc[1]]
            a, b = district_paved(preds[sc[0]][4], both, districts), district_paved(preds[sc[1]][4], both, districts)
            gaps = np.array([100 * abs(a[c] - b[c]) for c in a if c in b])
            res["noise_two_2021_scenes"] = {"district_paved_median_pts": round(float(np.median(gaps)), 2),
                                            "district_paved_p95_pts": round(float(np.percentile(gaps, 95)), 2)}
        # Change 2017 to 2021, mean of each year's scenes.
        sc17 = [p.stem for p in s17 if p.stem in preds]
        if sc17 and sc and name != "persistence_2017_map":
            def year_mean(scs, preds=preds):
                stack = np.stack([np.where(clear[s][None], preds[s], np.nan) for s in scs])
                return np.nanmean(stack, 0)
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                p17, p21 = year_mean(sc17), year_mean(sc)
            valid = land & (cov17 >= 0.95) & (cov21 >= 0.95) & ~np.isnan(p17[0]) & ~np.isnan(p21[0])
            vb = block_all(valid)
            dp, dt = block(np.nan_to_num(p21 - p17)), block(t21 - t17)
            ch = {}
            for where, m in (("test_squares", vb & block_all(split == 2)), ("all_land", vb)):
                ch[where] = {g: {"r": round(float(np.corrcoef(dp[k][m], dt[k][m])[0, 1]), 3),
                                 "pred_mean_change_pts": round(100 * float(dp[k][m].mean()), 2),
                                 "map_mean_change_pts": round(100 * float(dt[k][m].mean()), 2)}
                             for k, g in ((4, "paved"), (0, "tree_canopy"))}
            res["change_2017_2021"] = ch
            res["dob_sites"] = dob_test(ref, land, valid, split, p17, p21, t17, t21)
        out["methods"][name] = res
        print(name, json.dumps({k: (v["test_squares"]["mean_mae_pts"] if isinstance(v, dict) and "test_squares" in v
                                    else v) for k, v in res.items() if k.startswith("s2_")}), flush=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {OUT}")
    with rasterio.open(ROOT / "data" / "eo" / "landcover_2021.tif") as src:
        out["app_landcover_2021_dates"] = src.tags().get("dates")
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    return 0


def dob_test(ref, land, valid, split, p17, p21, t17, t21) -> dict:
    """Predicted and mapped 2017 to 2021 change in paved share in the 30 m
    around DOB new-building permits issued 2016 to 2019, against random land
    with no NB or DM permit within 200 m in 2015 to 2021."""
    from datetime import datetime

    import numpy as np
    from pyproj import Transformer
    from scipy.ndimage import distance_transform_edt

    rows = json.loads((DATA / "dob_nb_dm_2015_2021.json").read_text())
    t = Transformer.from_crs("EPSG:4326", ref.rio.crs, always_xy=True)
    inv = ~ref.rio.transform()

    def rc(r):
        try:
            x, y = t.transform(float(r["gis_longitude"]), float(r["gis_latitude"]))
        except (KeyError, TypeError, ValueError):
            return None
        c, rr = inv * (x, y)
        return int(rr), int(c)

    any_permit = np.zeros(ref.shape, bool)
    first_nb: dict[str, tuple] = {}
    for r in rows:
        p = rc(r)
        if not p or not (0 <= p[0] < ref.shape[0] and 0 <= p[1] < ref.shape[1]):
            continue
        any_permit[p] = True
        if r["job_type"] == "NB":
            raw = r["issuance_date"]  # the dataset mixes 06/24/2016 and 2016-06-24
            d = datetime.strptime(raw[:10], "%Y-%m-%d" if raw[4] == "-" else "%m/%d/%Y")
            if r["job__"] not in first_nb or d < first_nb[r["job__"]][0]:
                first_nb[r["job__"]] = (d, p)
    sites = {p for d, p in first_nb.values() if 2016 <= d.year <= 2019}
    far = distance_transform_edt(~any_permit) * 10 > 200
    ok = valid.copy()
    ok[:1], ok[-1:], ok[:, :1], ok[:, -1:] = False, False, False, False

    def window_change(a17, a21, pts):
        return np.array([float(np.nanmean(a21[4, r - 1:r + 2, c - 1:c + 2] - a17[4, r - 1:r + 2, c - 1:c + 2]))
                         for r, c in pts])

    rng = np.random.default_rng(0)
    out = {"n_new_building_jobs_2016_2019": len(sites)}
    for where, m in (("test_squares", split == 2), ("all_land", np.ones(ref.shape, bool))):
        s_pts = [p for p in sites if ok[p] and m[p]]
        cand = np.argwhere(ok & far & m & land)
        c_pts = [tuple(x) for x in cand[rng.choice(len(cand), size=min(len(cand), 5 * len(s_pts)), replace=False)]]
        res = {"n_sites": len(s_pts), "n_controls": len(c_pts)}
        for label, a17, a21 in (("model", p17, p21), ("map", t17, t21)):
            s, c = window_change(a17, a21, s_pts), window_change(a17, a21, c_pts)
            # AUC: the chance a site's change exceeds a control's.
            auc = float((s[:, None] > c[None, :]).mean() + 0.5 * (s[:, None] == c[None, :]).mean())
            res[label] = {"sites_mean_paved_change_pts": round(100 * float(np.mean(s)), 2),
                          "controls_mean_paved_change_pts": round(100 * float(np.mean(c)), 2),
                          "auc_sites_vs_controls": round(auc, 3)}
        out[where] = res
    return out


if __name__ == "__main__":
    raise SystemExit(main())
