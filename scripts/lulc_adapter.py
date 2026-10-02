"""Experimental: the owner's TerraMind land-cover adapter, kept for comparison.

The app's land-cover layer was made with this adapter until 2026-10-02; it is
now made by the NYC land-cover model (app/eo/cover.py), which beat it on the
city's own 2021 map (docs/MODELS.md). This module is used only by the
comparison scripts (scripts/eval_cover.py --run-adapter, scripts/check_tim.py).
Needs the `eo` extra.

The model is the owner's LoRA adapter `lulc_nyc` from
`msradam/TerraMind-NYC-Adapters` on IBM and ESA's TerraMind 1.0 base. The
adapter and its decoder are safetensors at a pinned commit; the base is
the only file its publisher offers, a PyTorch checkpoint, read with
`weights_only=True` (tensors only, no code).

Three things differ from the model card, each checked against ESA
WorldCover 2021 on one box of Manhattan, Brooklyn and Queens
(docs/MODELS.md has the numbers):

  * the classes are the ones the training script wrote
    (experiments/05_terramind_nyc_finetune/data/slice_and_label_nyc.py at
    git tag v0.7.0): the card lists them in another order and names a
    "building" class the labels never had;
  * the Sentinel-1 and elevation inputs carry nothing. Training fed radar
    on the wrong scale and an empty elevation channel, and zeros in both
    give the same map as real data, so only Sentinel-2 is read;
  * the thinking-in-modalities adapter (`tim_nyc`), with its generation
    weights loaded from the base checkpoint (scripts/check_tim.py), scores
    no better than this one, so it is not used.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass

from app.eo.cover import (  # noqa: F401 - TerraMind's Sentinel-2 bands and statistics
    S2_BANDS,
    S2_MEAN,
    S2_STD,
)


@dataclass(frozen=True)
class _Adapter:
    repo: str
    revision: str


MODEL = _Adapter("msradam/TerraMind-NYC-Adapters", "984341631d10db4fb699f76cd5d5bc7d8b3690b3")
BASE_REPO, BASE_FILE = "ibm-esa-geospatial/TerraMind-1.0-base", "TerraMind_v1_base.pt"
BASE_REVISION = "fb96c70d0a5f68dcc44030b89cbfd8ec3fb0c67a"
ADAPTER = "lulc_nyc"
# 0 water and wetland, 1 built-up (paved or roofed), 2 trees and shrubs,
# 3 grass and crops, 4 bare ground and other.
CLASSES = ("water", "built", "trees", "grass", "bare")
CHIP, TIMESTEPS = 224, 4  # trained on one scene repeated four times
# TerraMind's pretraining statistics for radar (dB) and elevation (m); zeros are fed for both.
S1_MEAN, S1_STD = [-10.93, -17.329], [4.391, 4.459]
DEM_MEAN, DEM_STD = 670.665, 951.272

_MODEL = None
_INIT_LOCK = threading.Lock()


def load_model():
    """TerraMind base with the NYC land-cover adapter merged in, once."""
    global _MODEL
    with _INIT_LOCK:
        if _MODEL is None:
            import torch
            from huggingface_hub import hf_hub_download
            from safetensors.torch import load_file
            from terratorch.tasks import SemanticSegmentationTask

            from app.eo.prithvi import device

            task = SemanticSegmentationTask(
                model_factory="EncoderDecoderFactory",
                model_args={
                    "backbone": "terramind_v1_base", "backbone_pretrained": False,
                    "backbone_modalities": ["S2L2A", "S1RTC", "DEM"], "backbone_use_temporal": True,
                    "backbone_temporal_pooling": "concat", "backbone_temporal_n_timestamps": TIMESTEPS,
                    "necks": [{"name": "SelectIndices", "indices": [2, 5, 8, 11]},
                              {"name": "ReshapeTokensToImage", "remove_cls_token": False},
                              {"name": "LearnedInterpolateToPyramidal"}],
                    "decoder": "UNetDecoder", "decoder_channels": [512, 256, 128, 64],
                    "head_dropout": 0.1, "num_classes": len(CLASSES),
                },
                loss="ce", ignore_index=-1,
            )
            net = task.model
            base = torch.load(hf_hub_download(BASE_REPO, BASE_FILE, revision=BASE_REVISION),
                              map_location="cpu", weights_only=True)
            net.encoder.load_state_dict({f"encoder.{k}": v for k, v in base.items()}, strict=False)

            def adapter_file(name: str) -> str:
                return hf_hub_download(MODEL.repo, f"{ADAPTER}/{name}", revision=MODEL.revision)

            net.load_state_dict(load_file(adapter_file("decoder_head.safetensors")), strict=False)
            # Merge the LoRA update (scale * B @ A) into the attention weights it adapts.
            with open(adapter_file("adapter_config.json")) as f:
                cfg = json.load(f)
            scale = cfg["lora_alpha"] / cfg["r"]
            pairs: dict[str, dict[str, torch.Tensor]] = {}
            for key, value in load_file(adapter_file("adapter_model.safetensors")).items():
                m = re.match(r"(.+)\.lora_([AB])\.default\.weight$", key)
                if m:
                    pairs.setdefault(m.group(1), {})[m.group(2)] = value
            state = net.state_dict()
            merged = 0
            for layer, ab in pairs.items():
                if f"{layer}.weight" in state and {"A", "B"} <= ab.keys():
                    state[f"{layer}.weight"] += scale * (ab["B"].float() @ ab["A"].float())
                    merged += 1
            if merged != len(pairs) or not merged:
                raise RuntimeError(f"{MODEL.repo}: {merged} of {len(pairs)} LoRA layers matched the base model")
            net.load_state_dict(state)
            _MODEL = net.eval().to(device())
    return _MODEL


def classify(s2, batch: int = 8):
    """(12, H, W) Sentinel-2 digital numbers -> (H, W) uint8 class index
    (see CLASSES); 255 where the scene has no data. The radar and
    elevation channels the architecture expects are zeros."""
    import numpy as np
    import torch

    from app.eo.prithvi import device

    net, dev = load_model(), device()
    _, h, w = s2.shape
    ph, pw = -h % CHIP, -w % CHIP
    mean, std = (np.array(v, "float32").reshape(-1, 1, 1) for v in (S2_MEAN, S2_STD))
    x2 = np.pad((s2.astype("float32") - mean) / std, ((0, 0), (0, ph), (0, pw)))
    # What a zero input is after normalisation, for the two unused channels.
    blank = {"S1RTC": [-m / d for m, d in zip(S1_MEAN, S1_STD, strict=True)], "DEM": [-DEM_MEAN / DEM_STD]}
    seen = np.pad(s2[1:4].sum(0) > 0, ((0, ph), (0, pw)))
    out = np.full((h + ph, w + pw), 255, dtype="uint8")
    corners = [(i, j) for i in range(0, h + ph, CHIP) for j in range(0, w + pw, CHIP) if seen[i:i + CHIP, j:j + CHIP].any()]
    with torch.no_grad():
        for k in range(0, len(corners), batch):
            group = corners[k:k + batch]
            c = np.stack([x2[:, i:i + CHIP, j:j + CHIP] for i, j in group])
            # (B, C, T, H, W): the scene repeated four times, as in training.
            inputs = {"S2L2A": torch.from_numpy(np.repeat(c[:, :, None], TIMESTEPS, axis=2)).to(dev)}
            for name, values in blank.items():
                inputs[name] = torch.tensor(values, dtype=torch.float32, device=dev).view(1, -1, 1, 1, 1).expand(
                    len(group), -1, TIMESTEPS, CHIP, CHIP)
            pred = net(inputs).output.argmax(1).cpu().numpy()
            for (i, j), p in zip(group, pred, strict=True):
                out[i:i + CHIP, j:j + CHIP] = p
    out[~seen] = 255
    return out[:h, :w]
