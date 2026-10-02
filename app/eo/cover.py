"""Experimental: NYC land cover fractions from Sentinel-2, for batch jobs
(scripts/run_landcover_batch.py, scripts/train_cover.py).

Not used per request. The app reads the saved outputs (app/eo/landcover.py).
This module builds the land-cover model, loads its trained weights and turns
one Sentinel-2 scene into eight class fractions per 10 m pixel. Needs the
`eo` extra.

The model is trained by scripts/train_cover.py on the city's own 2017 six-inch
land cover map (NYC Open Data), aggregated to the Sentinel-2 grid, and tested
against the 2021 map, which it never saw (scripts/eval_cover.py). Its weights
are not published; the batch job reads them from a local safetensors file,
pinned here by its SHA-256.
"""

from __future__ import annotations

import os
from pathlib import Path

from app import experimental

ROOT = Path(__file__).resolve().parents[2]
CLASSES = ("tree_canopy", "grass_shrub", "bare_soil", "water", "building", "road", "other_paved", "railroad")
PAVED = (4, 5, 6, 7)  # building, road, other paved, railroad: paved or built over
GREEN = (0, 1)
CHIP = 224
TERRAMIND = {  # official repositories, pinned; read with weights_only=True
    "tiny": ("ibm-esa-geospatial/TerraMind-1.0-tiny", "TerraMind_v1_tiny.pt", "2b5ac0a3ed7dd7e922ccfd595b56607f342df343"),
    "small": ("ibm-esa-geospatial/TerraMind-1.0-small", "TerraMind_v1_small.pt",
              "960f7549bfe9d7a08946860042f83badd604c779"),
    "base": ("ibm-esa-geospatial/TerraMind-1.0-base", "TerraMind_v1_base.pt", "fb96c70d0a5f68dcc44030b89cbfd8ec3fb0c67a"),
}
# The model the batch job runs, and the SHA-256 of its trained weights.
ARCH = os.environ.get("RIPRAP_COVER_ARCH", "terramind_base_px")
WEIGHTS = Path(os.environ.get("RIPRAP_COVER_WEIGHTS", ROOT / "outputs" / "terramind_nyc" / "models" / f"{ARCH}.safetensors"))
SHA256 = experimental.MODELS["landcover"].revision  # pinned in app/experimental.py


SQUARE = 200  # pixels: the 2 km squares of the train, validation and test split


def split_map(shape):
    """0 train, 1 validation, 2 test for every pixel of the 10 m grid, by its
    2 km square and a fixed hash (one in five test, one in ten validation).
    The test squares are never trained on."""
    import numpy as np

    r, c = np.indices(shape)
    sq = (r // SQUARE) * 1000 + c // SQUARE
    h = (sq * 2654435761) % 2**32 % 10
    return np.where(h < 2, 2, np.where(h < 3, 1, 0))


def normalise(s2):
    """(12, H, W) Sentinel-2 digital numbers on one scale (scenes before 2022
    lifted by 1000) -> standardised with TerraMind's pretraining statistics."""
    import numpy as np

    from app.eo import terramind as tm

    m, s = (np.array(v, "float32").reshape(-1, 1, 1) for v in (tm.S2_MEAN, tm.S2_STD))
    return (s2 - m) / s


def build(name: str, pretrained: bool = True):
    """An untrained network: `mlp`, `unet`, or `terramind_<size>[_px]`, the
    TerraMind encoder from its pinned checkpoint when `pretrained`."""
    import torch
    from torch import nn

    if name == "mlp":
        return nn.Sequential(nn.Conv2d(12, 128, 1), nn.GELU(), nn.Conv2d(128, 128, 1), nn.GELU(),
                             nn.Conv2d(128, len(CLASSES), 1))
    if name == "unet":
        import segmentation_models_pytorch as smp

        return smp.Unet("resnet18", encoder_weights=None, in_channels=12, classes=len(CLASSES))
    pixel = name.endswith("_px")  # add a per-pixel branch: a ViT token is 16 pixels (160 m) across
    size = name.removeprefix("terramind_").removesuffix("_px")
    from huggingface_hub import hf_hub_download
    from terratorch.models import EncoderDecoderFactory

    repo, file, revision = TERRAMIND[size]
    channels = [256, 128, 64, 32] if size == "tiny" else [512, 256, 128, 64]
    model = EncoderDecoderFactory().build_model(
        task="segmentation", backbone=f"terramind_v1_{size}", backbone_pretrained=False,
        backbone_modalities=["S2L2A"],
        necks=[{"name": "SelectIndices", "indices": [2, 5, 8, 11]},
               {"name": "ReshapeTokensToImage", "remove_cls_token": False},
               {"name": "LearnedInterpolateToPyramidal"}],
        decoder="UNetDecoder", decoder_channels=channels, head_dropout=0.1, num_classes=len(CLASSES))
    if pretrained:
        state = torch.load(hf_hub_download(repo, file, revision=revision), map_location="cpu", weights_only=True)
        own = model.encoder.state_dict()
        take = {k: v for k, v in state.items() if k in own and own[k].shape == v.shape}
        if len(take) < 0.9 * len(own):
            raise RuntimeError(f"{repo}: only {len(take)} of {len(own)} encoder tensors loaded")
        model.encoder.load_state_dict(take, strict=False)

    class Wrap(nn.Module):  # the factory wants a modality dict and returns a ModelOutput
        def __init__(self, m, px):
            super().__init__()
            self.m, self.px = m, px

        def forward(self, x):
            out = self.m({"S2L2A": x}).output
            return out + self.px(x) if self.px is not None else out

    return Wrap(model, build("mlp") if pixel else None)


def load(name: str = ARCH, weights: Path = WEIGHTS, sha256: str = SHA256):
    """The trained model, from its safetensors file; fails if the file's
    hash is not the pinned one."""
    import hashlib

    from safetensors.torch import load_file

    from app.eo.prithvi import device

    if not weights.exists():
        raise FileNotFoundError(f"{weights}: the land-cover weights are local and not published; "
                                "train them with scripts/train_cover.py")
    digest = hashlib.sha256(weights.read_bytes()).hexdigest()
    if sha256 and digest != sha256:
        raise RuntimeError(f"{weights}: SHA-256 {digest}, expected {sha256}")
    net = build(name, pretrained=False)
    net.load_state_dict(load_file(weights), strict=True)
    return net.eval().to(device())


def predict(net, s2n, dev=None, batch: int = 8, stride: int = 192):
    """(8, H, W) class fractions for a normalised scene; softmax averaged
    over overlapping 224 px chips."""
    import numpy as np
    import torch

    from app.eo.prithvi import device

    dev = dev or device()
    _, h, w = s2n.shape
    ph = max(0, CHIP - h) + (-(max(h, CHIP) - CHIP)) % stride
    pw = max(0, CHIP - w) + (-(max(w, CHIP) - CHIP)) % stride
    x = np.pad(s2n, ((0, 0), (0, ph), (0, pw)), mode="reflect")
    H, W = x.shape[1:]
    out, hits = np.zeros((len(CLASSES), H, W), "float32"), np.zeros((H, W), "float32")
    corners = [(i, j) for i in range(0, H - CHIP + 1, stride) for j in range(0, W - CHIP + 1, stride)]
    net.eval()
    with torch.no_grad():
        for k in range(0, len(corners), batch):
            group = corners[k:k + batch]
            xb = torch.from_numpy(np.stack([x[:, i:i + CHIP, j:j + CHIP] for i, j in group])).to(dev)
            p = torch.softmax(net(xb), 1).float().cpu().numpy()
            for (i, j), pi in zip(group, p, strict=True):
                out[:, i:i + CHIP, j:j + CHIP] += pi
                hits[i:i + CHIP, j:j + CHIP] += 1
    return out[:, :h, :w] / np.maximum(hits, 1)[:h, :w]
