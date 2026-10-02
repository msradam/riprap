"""Train a NYC land-cover model on Sentinel-2 against the city's own 2017
six-inch land cover (experimental, offline).

Each 10 m pixel gets the fraction of its area in eight classes (tree canopy,
grass and shrub, bare soil, water, building, road, other paved, railroad),
learned from the 2017 map aggregated to the Sentinel-2 grid
(scripts/prepare_landcover_labels.py). Three models share one data split,
one loss and one training loop, so the foundation model has to earn its cost:

  * `terramind_tiny|small|base`: IBM and ESA's TerraMind 1.0 encoder, from its
    pinned checkpoint (read with `weights_only=True`), Sentinel-2 L2A only,
    with a UNet decoder, all weights trained; with `_px` (for example
    `terramind_small_px`) the per-pixel network below is added to its output,
    since a ViT token is 16 pixels across and its decoder never sees one
    pixel's spectrum;
  * `unet`: a small UNet with no pretraining;
  * `mlp`: a per-pixel network on the twelve bands (1x1 convolutions), the
    simple baseline.

Split: the city is cut into 2 km squares; one in five (by a fixed hash) is a
test square never seen in training and one in ten a validation square.
Training reads only training squares, on land, where the label covers the
pixel and the scene's classification layer shows a clear view.

Loss: cross-entropy against the fractions (a soft label). Every model keeps
the weights that scored best on the validation squares (checked every
--eval-every steps), and a pretrained encoder trains at a tenth of the
decoder's learning rate. Trained weights are
saved as safetensors under outputs/terramind_nyc/models/ (git-ignored). The
2021 map is never read here.

    python3 gpu_lock.py uv run python scripts/train_cover.py --model terramind_base_px --steps 3000   # the shipped model
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.eo.cover import (  # noqa: E402, F401 - shared with the batch
    CHIP,
    CLASSES,
    build,
    normalise,
    predict,
    split_map,
)

DATA = ROOT / "outputs" / "terramind_nyc"
TRAIN_DATES = ("2017",)  # label year; the scene files are found by prefix


def scenes(year: str) -> list[Path]:
    return sorted(DATA.glob(f"s2_{year}-*.tif"))


def read_scene(path: Path):
    """(12, H, W) float32 digital numbers on one scale, (H, W) clear mask."""
    import rasterio

    with rasterio.open(path) as src:  # bands 1 to 12 are B01 to B12, band 13 the clear view
        s2 = src.read(list(range(1, 13))).astype("float32")
        clear = src.read(13).astype(bool)
    return s2, clear & (s2[1] > 0)


def read_labels(year: str):
    """(8, H, W) class fractions and (H, W) labelled share."""
    import rasterio

    with rasterio.open(DATA / f"labels_{year}_10m.tif") as src:
        a = src.read().astype("float32")
    return a[:8], a[8]






def soft_ce(logits, target, weight):
    import torch

    loss = -(target * torch.log_softmax(logits, 1)).sum(1)
    return (loss * weight).sum() / weight.sum().clamp(min=1)




def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model", required=True, help="mlp, unet, terramind_tiny, terramind_small or terramind_base")
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--encoder-lr-scale", type=float, default=0.1,
                    help="learning rate of a pretrained TerraMind encoder, as a share of --lr")
    ap.add_argument("--eval-every", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="")
    ap.add_argument("--no-predict", action="store_true", help="a timing run: no validation, no saved maps")
    args = ap.parse_args()

    import numpy as np
    import run_landcover_batch as lb
    import torch
    from safetensors.torch import save_file

    from app.eo import prithvi

    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    dev = prithvi.device()
    ref = prithvi.grid(lb.NYC_BBOX)
    land = lb.land_mask(ref)
    split = split_map(ref.shape)
    frac, labelled = read_labels("2017")
    train_scenes = []
    for p in scenes("2017"):
        s2, clear = read_scene(p)
        train_scenes.append((p.stem, normalise(s2), clear))
    ok = land & (labelled >= 0.95)
    weight_by_scene = [(ok & c).astype("float32") for _, _, c in train_scenes]
    print(f"{args.model}: {len(train_scenes)} scenes {[n for n, _, _ in train_scenes]}; "
          f"train pixels {int((ok & (split == 0)).sum())}, val {int((ok & (split == 1)).sum())}, "
          f"test {int((ok & (split == 2)).sum())}", flush=True)

    # Chip corners whose centre is a training square with labelled land.
    h, w = ref.shape
    cand = [(i, j) for i in range(0, h - CHIP, 32) for j in range(0, w - CHIP, 32)
            if (ok & (split == 0))[i:i + CHIP, j:j + CHIP].mean() > 0.3]
    print(f"{len(cand)} candidate chips", flush=True)

    net = build(args.model).to(dev)
    n_params = sum(p.numel() for p in net.parameters())
    # A pretrained encoder learns more slowly than the new decoder, or it forgets what it brought.
    enc = [p for n, p in net.named_parameters() if n.startswith("m.encoder.")]
    rest = [p for n, p in net.named_parameters() if not n.startswith("m.encoder.")]
    groups = [{"params": rest, "lr": args.lr}] + ([{"params": enc, "lr": args.lr * args.encoder_lr_scale}] if enc else [])
    opt = torch.optim.AdamW(groups, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[g["lr"] for g in groups], total_steps=args.steps,
                                                pct_start=0.05)
    best, best_state = float("inf"), None
    train_only = (split == 0).astype("float32")
    log = {"model": args.model, "params": n_params, "steps": args.steps, "batch": args.batch, "lr": args.lr,
           "encoder_lr": args.lr * args.encoder_lr_scale if enc else None,
           "seed": args.seed, "scenes": [n for n, _, _ in train_scenes], "val": []}
    t0 = time.time()
    for step in range(1, args.steps + 1):
        net.train()
        xs, ys, ws = [], [], []
        for _ in range(args.batch):
            k = rng.integers(len(train_scenes))
            i, j = cand[rng.integers(len(cand))]
            sl = (slice(i, i + CHIP), slice(j, j + CHIP))
            x, y = train_scenes[k][1][:, sl[0], sl[1]], frac[:, sl[0], sl[1]]
            wgt = weight_by_scene[k][sl] * train_only[sl]
            rot, flip = rng.integers(4), rng.integers(2)
            x, y, wgt = (np.rot90(a, rot, axes=(-2, -1)) for a in (x, y, wgt))
            if flip:
                x, y, wgt = (a[..., ::-1] for a in (x, y, wgt))
            xs.append(x.copy())
            ys.append(y.copy())
            ws.append(wgt.copy())
        xb, yb, wb = (torch.from_numpy(np.stack(a)).to(dev) for a in (xs, ys, ws))
        loss = soft_ce(net(xb), yb, wb)
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
        if step % 50 == 0:
            print(f"step {step} loss {loss.item():.4f} {time.time() - t0:.0f} s", flush=True)
        if not args.no_predict and (step % args.eval_every == 0 or step == args.steps):
            name, s2n, clear = train_scenes[0]
            pred = predict(net, s2n, dev)
            m = ok & clear & (split == 1)
            mae = np.abs(pred[:, m] - frac[:, m]).mean(1)
            log["val"].append({"step": step, "seconds": round(time.time() - t0), "loss": round(loss.item(), 4),
                               "val_mae_by_class": dict(zip(CLASSES, np.round(mae, 4).tolist(), strict=True)),
                               "val_mae_mean": round(float(mae.mean()), 4)})
            print(json.dumps(log["val"][-1]), flush=True)
            if mae.mean() < best:  # keep the weights that did best on the validation squares
                best = float(mae.mean())
                best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
                log["best_step"] = step
    log["train_seconds"] = round(time.time() - t0)
    if best_state is not None:
        net.load_state_dict(best_state)
    if args.no_predict:
        print(f"{args.model}: {n_params / 1e6:.1f}M parameters, {log['train_seconds'] / args.steps:.2f} s a step")
        return 0
    out = DATA / "models"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{args.model}{args.tag}"
    save_file({k: v.detach().cpu().contiguous() for k, v in net.state_dict().items()}, out / f"{stem}.safetensors")
    (out / f"{stem}.json").write_text(json.dumps(log, indent=1))
    # Predict every saved scene (2017 and 2021) for the evaluation script.
    for p in sorted(DATA.glob("s2_*.tif")):
        s2, _ = read_scene(p)
        pred = predict(net, normalise(s2), dev)
        np.save(out / f"{stem}_{p.stem}.npy", (pred * 1000).round().astype("uint16"))
        print(f"predicted {p.stem}", flush=True)
    print(f"done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
