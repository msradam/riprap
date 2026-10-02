"""A small probe on TESSERA embeddings, as a cheap rival to fine-tuning
TerraMind for NYC land cover (experimental, offline).

TESSERA v1 (University of Cambridge, github.com/ucam-eo/tessera; embeddings
CC0, code MIT) gives one 128-number vector per 10 m pixel per year, made from
a year of Sentinel-1 and Sentinel-2. The embeddings were fetched with the
`geotessera` client and resampled to Riprap's grid (outputs/tessera/, see
the JSON beside each file). A two-layer network maps a pixel's vector to the
eight class fractions, trained on the 2017 vectors against the 2017 map with
the split, labels and loss of scripts/train_cover.py, and applied to the 2021
vectors. A year has one vector, so the prediction is saved under each of the
year's scene names, which lets scripts/eval_cover.py score it on the same
pixels as the other models.

    python3 gpu_lock.py uv run python scripts/train_tessera_probe.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

EMB = ROOT / "outputs" / "tessera"
NAME = "tessera_probe"


def main() -> int:
    import numpy as np
    import run_landcover_batch as lb
    import torch
    from safetensors.torch import save_file
    from torch import nn
    from train_cover import CLASSES, DATA, read_labels, scenes, soft_ce, split_map

    from app.eo import prithvi

    t0 = time.time()
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    dev = prithvi.device()
    ref = prithvi.grid(lb.NYC_BBOX)
    meta = json.loads((EMB / "tessera_2017_10m.json").read_text())
    assert list(meta["transform"])[:6] == list(ref.rio.transform())[:6], "embeddings are not on the grid"
    land, split = lb.land_mask(ref), split_map(ref.shape)
    frac, labelled = read_labels("2017")
    e17 = np.load(EMB / "tessera_2017_10m.npy", mmap_mode="r")
    ok = land & (labelled >= 0.95) & (split == 0)
    idx = np.flatnonzero(ok.ravel())
    idx = np.sort(rng.choice(idx, size=min(len(idx), 2_000_000), replace=False))
    flat = e17.reshape(128, -1)
    x = np.asarray(flat[:, idx], dtype="float32").T
    y = frac.reshape(8, -1)[:, idx].T
    keep = np.isfinite(x).all(1)
    x, y = x[keep], y[keep]
    mu, sd = x.mean(0), x.std(0) + 1e-6
    x = (x - mu) / sd
    print(f"{len(x)} training pixels in {time.time() - t0:.0f} s", flush=True)
    net = nn.Sequential(nn.Linear(128, 256), nn.GELU(), nn.Linear(256, 256), nn.GELU(), nn.Linear(256, len(CLASSES))).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=0.01)
    xt, yt = torch.from_numpy(x).to(dev), torch.from_numpy(y).to(dev)
    steps, batch = 6000, 4096
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=steps, pct_start=0.05)
    for step in range(1, steps + 1):
        b = torch.randint(0, len(xt), (batch,), device=dev)
        loss = soft_ce(net(xt[b])[:, :, None, None], yt[b][:, :, None, None], torch.ones(batch, 1, 1, device=dev))
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
        if step % 1000 == 0:
            print(f"step {step} loss {loss.item():.4f}", flush=True)
    out = DATA / "models"
    save_file({k: v.detach().cpu().contiguous() for k, v in net.state_dict().items()} |
              {"input_mean": torch.from_numpy(mu), "input_std": torch.from_numpy(sd)}, out / f"{NAME}.safetensors")
    net.eval()
    for year in ("2017", "2021"):
        e = np.load(EMB / f"tessera_{year}_10m.npy", mmap_mode="r").reshape(128, -1)
        pred = np.zeros((8, e.shape[1]), "uint16")
        bad = np.zeros(e.shape[1], bool)
        with torch.no_grad():
            for s in range(0, e.shape[1], 500_000):
                chunk = (np.asarray(e[:, s:s + 500_000], dtype="float32").T - mu) / sd
                nan = ~np.isfinite(chunk).all(1)
                p = torch.softmax(net(torch.from_numpy(np.nan_to_num(chunk)).to(dev)), 1).cpu().numpy()
                pred[:, s:s + 500_000] = (p.T * 1000).round().astype("uint16")
                bad[s:s + 500_000] = nan
        # No embedding (TESSERA's water mask): predict all water, as its own mask says.
        pred[:, bad] = 0
        pred[3, bad] = 1000
        pred = pred.reshape(8, *ref.shape)
        for p in scenes(year):
            np.save(out / f"{NAME}_{p.stem}.npy", pred)
        print(f"predicted {year} ({bad.reshape(ref.shape)[land].mean():.2%} of land without an embedding)", flush=True)
    (out / f"{NAME}.json").write_text(json.dumps({"model": NAME, "train_pixels": len(x), "steps": steps,
                                                  "batch": batch, "seconds": round(time.time() - t0)}, indent=1))
    print(f"done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
