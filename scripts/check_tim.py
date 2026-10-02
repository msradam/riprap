"""Re-test the thinking-in-modalities adapter (`tim_nyc`) with TerraMind's
generation weights loaded (experimental, one-off).

The first check of `tim_nyc` (2026-10-01, docs/MODELS.md) built TerraTorch's
`terramind_v1_base_tim` with `backbone_pretrained=False` and loaded the base
checkpoint into the encoder only. The TiM sampler, which generates the land
cover tokens the encoder then reads, is a second encoder and decoder
(`sampler.model.*`); it stayed at random initialisation. The pinned base
checkpoint holds those weights, and TerraTorch's own `checkpoint_filter_fn_tim`
copies them in. This script runs three models on the same box, date and key:

  * `lulc_nyc` as the app runs it (scripts/lulc_adapter.py);
  * `tim_nyc` with a random sampler, as first checked;
  * `tim_nyc` with the sampler loaded from the pinned base checkpoint,
    over three generation seeds (TiM samples its land cover tokens).

Key: ESA WorldCover 2021 (the adapters' label source), on the box and the
first clear 2021 date the first check used. Inputs follow the app: Sentinel-2
on one scale (scenes before 2022 lifted by 1000), zeros for radar and
elevation.

    python3 gpu_lock.py uv run python scripts/check_tim.py

Writes data/experimental/tim_check.json.
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

BBOX = [-74.03, 40.60, -73.84, 40.80]  # the first check's box: lower Manhattan, Brooklyn, western Queens
OUT = ROOT / "data" / "experimental" / "tim_check.json"


def build_tim(load_sampler: bool):
    """`tim_nyc` on the TerraMind base: encoder from the pinned checkpoint,
    the sampler too when `load_sampler`, then the adapter's decoder and LoRA."""
    import lulc_adapter as tm
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file
    from terratorch.models.backbones.terramind.model.terramind_register import (
        checkpoint_filter_fn_tim,
    )
    from terratorch.tasks import SemanticSegmentationTask

    task = SemanticSegmentationTask(model_factory="EncoderDecoderFactory", model_args={
        "backbone": "terramind_v1_base_tim", "backbone_pretrained": False, "backbone_tim_modalities": ["LULC"],
        "backbone_modalities": ["S2L2A", "S1RTC", "DEM"], "backbone_use_temporal": True,
        "backbone_temporal_pooling": "concat", "backbone_temporal_n_timestamps": tm.TIMESTEPS,
        "necks": [{"name": "SelectIndices", "indices": [2, 5, 8, 11]},
                  {"name": "ReshapeTokensToImage", "remove_cls_token": False},
                  {"name": "LearnedInterpolateToPyramidal"}],
        "decoder": "UNetDecoder", "decoder_channels": [512, 256, 128, 64], "head_dropout": 0.1,
        "num_classes": len(tm.CLASSES)}, loss="ce", ignore_index=-1)
    net = task.model
    tim = net.encoder.encoder  # TerraMindTiM inside TerraTorch's temporal wrapper
    base = torch.load(hf_hub_download(tm.BASE_REPO, tm.BASE_FILE, revision=tm.BASE_REVISION),
                      map_location="cpu", weights_only=True)
    if load_sampler:
        before = {k: v.clone() for k, v in tim.state_dict().items() if k.startswith("sampler.model.")}
        tim.load_state_dict(checkpoint_filter_fn_tim(base, tim), strict=True)  # raises if the sampler is incomplete
        after = tim.state_dict()
        changed = sum(not torch.equal(before[k], after[k]) for k in before)
        loaded = {"sampler_tensors": len(before), "sampler_tensors_changed": changed}
    else:  # as first checked: the encoder only
        missing, _ = net.encoder.load_state_dict({f"encoder.{k}": v for k, v in base.items()}, strict=False)
        loaded = {"sampler_tensors_random": sum(k.startswith("encoder.sampler.model.") for k in missing)}

    def adapter_file(name: str) -> str:
        return hf_hub_download(tm.MODEL.repo, f"tim_nyc/{name}", revision=tm.MODEL.revision)

    _, unexpected = net.load_state_dict(load_file(adapter_file("decoder_head.safetensors")), strict=False)
    if unexpected:
        raise RuntimeError(f"decoder head: {len(unexpected)} unexpected keys")
    cfg = json.loads(Path(adapter_file("adapter_config.json")).read_text())
    scale = cfg["lora_alpha"] / cfg["r"]
    pairs: dict[str, dict] = {}
    for key, value in load_file(adapter_file("adapter_model.safetensors")).items():
        m = re.match(r"(.+)\.lora_([AB])\.default\.weight$", key)
        if m:
            pairs.setdefault(m.group(1), {})[m.group(2)] = value
    state = net.state_dict()
    merged = [layer for layer, ab in pairs.items() if f"{layer}.weight" in state and {"A", "B"} <= ab.keys()]
    for layer in merged:
        ab = pairs[layer]
        state[f"{layer}.weight"] += scale * (ab["B"].float() @ ab["A"].float())
    net.load_state_dict(state)
    loaded["lora_layers"], loaded["lora_layers_merged"] = len(pairs), len(merged)
    loaded["lora_layers_unmatched"] = sorted({".".join(k.split(".")[:4]) for k in pairs if k not in merged})
    return net, loaded


def score(pred, truth, clear, n: int) -> dict:
    import numpy as np

    ok = clear & (truth != 255) & (pred != 255)
    cm = np.zeros((n, n), int)
    np.add.at(cm, (truth[ok], pred[ok]), 1)
    iou = [cm[c, c] / max(cm[c].sum() + cm[:, c].sum() - cm[c, c], 1) for c in range(n)]
    return {"agreement": round(float(np.trace(cm) / cm.sum()), 4), "miou": round(float(np.mean(iou)), 4),
            "iou": [round(float(v), 3) for v in iou],
            "pred_share": [round(float(cm[:, c].sum() / cm.sum()), 3) for c in range(n)],
            "truth_share": [round(float(cm[c].sum() / cm.sum()), 3) for c in range(n)], "pixels": int(cm.sum())}


def main() -> int:
    import lulc_adapter as tm
    import run_landcover_batch as lb
    import torch

    from app.eo import prithvi

    t0 = time.time()
    ref = prithvi.grid(BBOX)
    day, items = next((d, it) for d, it in lb.scene_dates(2021, lb.NYC_BBOX) if d not in ("2021-09-02", "2021-09-07"))
    s2, clear = lb.read_s2(items, ref, lift_old=True)
    truth = lb.worldcover(BBOX, ref)
    print(f"{day}: inputs read in {time.time() - t0:.0f} s, {clear.mean():.1%} clear", flush=True)
    out = {"what": __doc__.split("\n\n")[0], "run_date": str(date.today()), "bbox": BBOX, "date": day,
           "scenes": [i.id for i in items], "key": "ESA WorldCover 2021, collapsed to the adapters' five classes",
           "classes": list(tm.CLASSES), "base": f"{tm.BASE_REPO}@{tm.BASE_REVISION}",
           "adapters": f"{tm.MODEL.repo}@{tm.MODEL.revision}", "runs": []}

    def run(name: str, net, loaded: dict, seed: int | None = None) -> None:
        t = time.time()
        if seed is not None:
            random.seed(seed)
            torch.manual_seed(seed)
        tm._MODEL = net.eval().to(prithvi.device())
        pred = tm.classify(s2)
        r = {"model": name, "seed": seed, **loaded, **score(pred, truth, clear, len(tm.CLASSES)),
             "seconds": round(time.time() - t)}
        out["runs"].append(r)
        print(json.dumps({k: r[k] for k in ("model", "seed", "agreement", "miou", "iou", "seconds")}), flush=True)

    tm._MODEL = None
    run("lulc_nyc", tm.load_model(), {})
    net, loaded = build_tim(load_sampler=False)
    run("tim_nyc, random sampler (as first checked)", net, loaded, seed=0)
    net, loaded = build_tim(load_sampler=True)
    for seed in (0, 1, 2):
        run("tim_nyc, sampler from the base checkpoint", net, loaded, seed=seed)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {OUT} in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
