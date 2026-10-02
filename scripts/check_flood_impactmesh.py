"""Check that Riprap feeds TerraMind-base-Flood the way it was trained, on
ImpactMesh-Flood's own validation samples (experimental, one-off).

scripts/run_flood_ida.py builds the inputs for Ida itself: band order,
Sentinel-1 in dB, the DEM repeated over the four dates, and the ImpactMesh v0
normalisation. If that pipeline is right, the model should find the flood
water that Copernicus EMS mapped in ImpactMesh's validation patches. This
script reads the released patches (zarr, the files the model was trained
from), runs the same normalisation and model as run_flood_ida.py, and scores
the model's flood class against the masks (v1 masks: 0 no water, 1 permanent
water, 2 flood water, -1 ignore). Validation patches may come from training
events (the dataset was split by patch), so this is a check of the pipeline,
not a skill score.

    # the validation split (6.4 GB): val/{S2L2A,S1RTC,DEM,MASK}.tar and split/impactmesh_flood_val.txt
    # from the dataset repository, untarred into outputs/impactmesh/data/
    python3 gpu_lock.py uv run --with zarr==2.18.0 --with numcodecs==0.15.1 python scripts/check_flood_impactmesh.py

Writes data/experimental/flood_terramind_impactmesh_check.json.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

DATA = ROOT / "outputs" / "impactmesh" / "data"
SPLIT = ROOT / "outputs" / "impactmesh" / "split" / "impactmesh_flood_val.txt"
OUT = ROOT / "data" / "experimental" / "flood_terramind_impactmesh_check.json"
N = 300


def main() -> int:
    import numpy as np
    import rasterio
    import run_flood_ida as fl
    import torch
    import zarr

    from app.eo.prithvi import device

    t0 = time.time()
    ids = [s.strip() for s in SPLIT.read_text().splitlines() if s.strip()]
    rng = np.random.default_rng(0)
    pick = sorted(rng.choice(len(ids), size=min(N, len(ids)), replace=False))
    dev = device()
    net = fl.load_model().to(dev)
    norm = {m: (np.array(fl.MEAN[m], "float32").reshape(-1, 1, 1, 1), np.array(fl.STD[m], "float32").reshape(-1, 1, 1, 1))
            for m in fl.MEAN}
    cm = np.zeros((3, 2), np.int64)  # mask class (no water, permanent, flood) by predicted class
    per_patch = []
    for k in pick:
        pid = ids[k]
        s2 = zarr.open_consolidated(str(DATA / "S2L2A" / f"{pid}_S2L2A.zarr.zip"), mode="r")["bands"][...]
        s1 = zarr.open_consolidated(str(DATA / "S1RTC" / f"{pid}_S1RTC.zarr.zip"), mode="r")["bands"][...]
        with rasterio.open(DATA / "DEM" / f"{pid}_DEM.tif") as src:
            dem = src.read(1)
        with rasterio.open(DATA / "MASK" / f"{pid}_annotation_flood.tif") as src:
            mask = src.read(1)
        x = {}
        for name, a in (("S2L2A", s2), ("S1RTC", s1), ("DEM", np.repeat(dem[None, None], 4, 0))):
            a = a.astype("float32").transpose(1, 0, 2, 3)  # (C, T, H, W)
            a = np.nan_to_num(np.where(a == -9999, np.nan, a), nan=0.0)  # the dataset's nodata handling
            m, sd = norm[name]
            x[name] = torch.from_numpy((a - m) / sd)[None].to(dev)
        with torch.no_grad():
            pred = net(x).output.argmax(1)[0].cpu().numpy()
        ok = mask >= 0
        np.add.at(cm, (mask[ok].astype(int), pred[ok]), 1)
        per_patch.append({"id": pid, "flood_px": int((mask == 2).sum()), "pred_px": int((pred == 1).sum()),
                          "hit_px": int(((mask == 2) & (pred == 1)).sum())})
    tp, fp, fn = cm[2, 1], cm[0, 1] + cm[1, 1], cm[2, 0]
    iou = tp / max(tp + fp + fn, 1)
    out = {"what": __doc__.split("\n\n")[0], "run_date": str(date.today()), "model": f"{fl.REPO}@{fl.REVISION}",
           "dataset": "ibm-esa-geospatial/ImpactMesh-Flood (CC BY 4.0), validation split",
           "n_patches": len(pick), "seed": 0,
           "confusion_mask_by_pred": {"no_water": cm[0].tolist(), "permanent_water": cm[1].tolist(),
                                      "flood_water": cm[2].tolist()},
           "flood_iou": round(float(iou), 3),
           "flood_recall": round(float(tp / max(tp + fn, 1)), 3),
           "flood_precision": round(float(tp / max(tp + fp, 1)), 3),
           "permanent_water_called_flood_pct": round(100 * float(cm[1, 1] / max(cm[1].sum(), 1)), 1),
           "no_water_called_flood_pct": round(100 * float(cm[0, 1] / max(cm[0].sum(), 1)), 2),
           "patches_with_flood": sum(p["flood_px"] > 0 for p in per_patch),
           "seconds": round(time.time() - t0)}
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
