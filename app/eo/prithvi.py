"""Sentinel scene helpers for the batch jobs, and the Prithvi-EO 2.0 water
model they were first written for.

The satellite water layer was retired from the app on 2026-10-02: on
Hurricane Ida and again on coastal and tidal floods that FloodNet sensors
recorded at the moment of a satellite pass, it found flooding no more often
than chance (docs/MODELS.md). Nothing here runs per request. The scene
helpers (`grid`, `read_band`, `clear_mask`, `search_scenes`) are used by the
land-cover and surface-temperature batch jobs; `load_model` and `water_mask`
are kept for the scripts that ran those tests (scripts/run_eo_batch.py,
scripts/score_water_floodnet.py). Needs the `eo` extra.

The model is the owner's fine-tune `msradam/Prithvi-EO-2.0-NYC-Pluvial`
of NASA and IBM's Prithvi-EO 2.0 (300M, Sen1Floods11), loaded from its
safetensors file at a pinned commit. Its training labels were the base
model's own output for Hurricane Ida, so it has no flood-detection score
against surveyed flooding; see docs/MODELS.md.
"""

from __future__ import annotations

import logging
import threading

log = logging.getLogger("riprap.eo.prithvi")

# The owner's fine-tune, pinned by commit (it was experimental.MODELS["water"] while the layer was in the app).
REPO, REVISION = "msradam/Prithvi-EO-2.0-NYC-Pluvial", "25ce564199d8cfa8fefd5ac0e80e2d911b65ea60"
WEIGHTS = "Prithvi_EO_2.0_NYC_Pluvial.safetensors"
BANDS = ["B02", "B03", "B04", "B8A", "B11", "B12"]
# Per-band mean and standard deviation of reflectance (0 to 1) the model was
# trained with (prithvi_nyc_phase14.yaml in the model repository).
MEANS = [0.107, 0.107, 0.115, 0.265, 0.235, 0.155]
STDS = [0.082, 0.075, 0.085, 0.115, 0.110, 0.100]
CHIP = 224  # the fine-tune's training chip
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

_MODEL = None
_INIT_LOCK = threading.Lock()


def device() -> str:
    import torch

    return "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"


def load_model():
    """The fine-tune, built from its training config and loaded once."""
    global _MODEL
    with _INIT_LOCK:
        if _MODEL is None:
            from huggingface_hub import hf_hub_download
            from safetensors.torch import load_file
            from terratorch.tasks import SemanticSegmentationTask

            task = SemanticSegmentationTask(
                model_factory="EncoderDecoderFactory",
                model_args={
                    "backbone": "prithvi_eo_v2_300_tl", "backbone_pretrained": False,
                    "backbone_bands": ["BLUE", "GREEN", "RED", "NARROW_NIR", "SWIR_1", "SWIR_2"],
                    "necks": [{"name": "SelectIndices", "indices": [5, 11, 17, 23]},
                              {"name": "ReshapeTokensToImage", "remove_cls_token": True},
                              {"name": "LearnedInterpolateToPyramidal"}],
                    "decoder": "UNetDecoder", "decoder_channels": [512, 256, 128, 64],
                    "head_dropout": 0.1, "num_classes": 2,
                },
                loss="dice", ignore_index=-1,
            )
            state = load_file(hf_hub_download(REPO, WEIGHTS, revision=REVISION))
            missing, unexpected = task.model.load_state_dict(
                {k.removeprefix("model."): v for k, v in state.items() if k.startswith("model.")}, strict=False)
            if missing or unexpected:
                raise RuntimeError(f"{REPO}: weights do not fit the model ({len(missing)} missing, "
                                   f"{len(unexpected)} unexpected keys)")
            _MODEL = task.model.eval().to(device())
    return _MODEL


def search_scenes(bbox: list[float], start: str, end: str, max_cloud: float = 30.0) -> list:
    """Sentinel-2 L2A items over `bbox` between two ISO datetimes, least
    cloudy first."""
    import planetary_computer as pc
    from pystac_client import Client

    client = Client.open(STAC_URL, modifier=pc.sign_inplace)
    items = client.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=f"{start}/{end}",
                          query={"eo:cloud_cover": {"lt": max_cloud}}, max_items=200).items()
    return sorted(items, key=lambda it: it.properties.get("eo:cloud_cover", 100))


def grid(bbox: list[float], crs: str = "EPSG:32618", res: float = 10.0):
    """An empty 10 m grid covering `bbox` (lon/lat) in `crs`, snapped to
    the Sentinel-2 pixel grid, as a DataArray to pass to
    read_bands(match=...). NYC is in UTM zone 18N."""
    import numpy as np
    import rioxarray  # noqa: F401
    import xarray as xr
    from pyproj import Transformer
    from rasterio.transform import from_origin

    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    xs, ys = t.transform([bbox[0], bbox[2], bbox[0], bbox[2]], [bbox[1], bbox[1], bbox[3], bbox[3]])
    x0, y1 = res * round(min(xs) / res), res * round(max(ys) / res)
    w, h = int((max(xs) - x0) / res), int((y1 - min(ys)) / res)
    da = xr.DataArray(np.zeros((h, w), "float32"), dims=("y", "x"),
                      coords={"y": y1 - res / 2 - res * np.arange(h), "x": x0 + res / 2 + res * np.arange(w)})
    return da.rio.write_crs(crs).rio.write_transform(from_origin(x0, y1, res, res))


def boa_offset(item) -> int:
    """Sentinel-2 products from processing baseline 04.00 (January 2022)
    add 1000 to every digital number; older ones do not."""
    try:
        return 1000 if float(item.properties.get("s2:processing_baseline", 0)) >= 4.0 else 0
    except (TypeError, ValueError):
        return 0


def read_band(item, band: str, match, resampling: str = "bilinear"):
    """One asset of a scene on the `match` grid, as a 2-D array of digital
    numbers (0 where the scene has no data)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT

    h, w = match.shape
    with rasterio.open(item.assets[band].href) as src, WarpedVRT(
            src, crs=match.rio.crs, transform=match.rio.transform(), width=w, height=h,
            resampling=Resampling[resampling]) as vrt:
        return vrt.read(1)


def read_bands(item, match):
    """The six model bands of a scene on the `match` grid as a (6, H, W)
    float32 reflectance array (0 to 1; 0 where the scene has no data)."""
    import numpy as np

    off = boa_offset(item)
    out = np.zeros((len(BANDS), *match.shape), dtype="float32")
    for i, band in enumerate(BANDS):
        dn = read_band(item, band, match).astype("float32")
        out[i] = np.where(dn > 0, np.clip(dn - off, 0, None) / 10000.0, 0)
    return out


# Sentinel-2 L2A scene classification (SCL) classes that are not a clear
# view of the ground: saturated or defective, cloud shadow, cloud (medium
# and high probability), thin cirrus. Unclassified (7) is kept.
SCL_UNCLEAR = (1, 3, 8, 9, 10)


def clear_mask(item, match):
    """(H, W) bool, True where the scene's SCL layer shows a clear view,
    read onto the `match` grid (nearest neighbour, SCL is 20 m)."""
    import numpy as np

    scl = read_band(item, "SCL", match, resampling="nearest")
    return (scl > 0) & ~np.isin(scl, SCL_UNCLEAR)


def water_mask(img, batch: int = 16):
    """(6, H, W) reflectance -> (H, W) uint8 mask, 1 = water. Runs the
    model on 224 px chips (zero-padded at the edges), in eval mode."""
    import numpy as np
    import torch

    net, dev = load_model(), device()
    _, h, w = img.shape
    ph, pw = -h % CHIP, -w % CHIP
    mean = np.array(MEANS, "float32")[:, None, None]
    std = np.array(STDS, "float32")[:, None, None]
    x = np.pad((img - mean) / std, ((0, 0), (0, ph), (0, pw)))
    out = np.zeros((h + ph, w + pw), dtype="uint8")
    corners = [(i, j) for i in range(0, h + ph, CHIP) for j in range(0, w + pw, CHIP)
               if img[:, i:i + CHIP, j:j + CHIP].any()]  # skip chips with no data at all
    with torch.no_grad():
        for k in range(0, len(corners), batch):
            group = corners[k:k + batch]
            chips = np.stack([x[:, i:i + CHIP, j:j + CHIP] for i, j in group])[:, :, None]  # (B, C, T=1, H, W)
            pred = net(torch.from_numpy(chips).to(dev)).output.argmax(1).cpu().numpy()
            for (i, j), p in zip(group, pred, strict=True):
                out[i:i + CHIP, j:j + CHIP] = p
    return out[:h, :w]
