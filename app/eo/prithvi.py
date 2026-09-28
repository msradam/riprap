"""Prithvi-EO 2.0 water segmentation for batch jobs (scripts/run_eo_batch.py).

Not used per request. The app reads the precomputed outputs; this module
only loads the model and turns a Sentinel-2 L2A window into a water mask.
Needs the `eo` extra (terratorch, STAC and xarray libraries).

The default model is `msradam/Prithvi-EO-2.0-NYC-Pluvial` with a fallback
to the IBM-NASA Sen1Floods11 base. Neither has a flood-detection score on
held-out events; outputs are experimental.
"""

from __future__ import annotations

import logging
import os
import threading

log = logging.getLogger("riprap.eo.prithvi")

REPO = os.environ.get("RIPRAP_PRITHVI_REPO", "msradam/Prithvi-EO-2.0-NYC-Pluvial")
BASE_REPO = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11"
BANDS = ["B02", "B03", "B04", "B8A", "B11", "B12"]
IMG_SIZE = 512  # Sen1Floods11 training crop
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

_MODEL = None
_RUN_MODEL = None
_INIT_LOCK = threading.Lock()


def load_model():
    """Load Prithvi-EO 2.0 once into RAM.

    The v2 NYC Pluvial fine-tune (`msradam/Prithvi-EO-2.0-NYC-Pluvial`)
    is **architecturally distinct** from the IBM-NASA Sen1Floods11
    base: v2 ships a `UNetDecoder` + 2-class head, the base ships a
    UperNet with PSP / FPN. The model has to be built from each
    repo's own config.yaml — there's no key-mapping shim that bridges
    them.

    Strategy:

      1. If the active REPO != BASE_REPO, try to build from the v2
         yaml + v2 ckpt. The v2 yaml's data: paths point at the
         training droplet's filesystem (`/root/terramind_nyc/...`)
         which doesn't exist locally; that's fine — the
         GenericNonGeoSegmentationDataModule constructor only
         records the paths, splits aren't read until `setup()`.
      2. On any v2 failure (yaml not present, datamodule constructor
         strict, weights mismatch), fall back to the base yaml + base
         ckpt. The base path is the proven pre-C5 behaviour.

    The shared `inference.run_model` helper is only published by the
    IBM-NASA base repo; we always pull it from there.
    """
    global _MODEL, _RUN_MODEL
    if _MODEL is not None:
        return _MODEL, _RUN_MODEL
    with _INIT_LOCK:
        if _MODEL is not None:  # double-check inside the lock
            return _MODEL, _RUN_MODEL
        import importlib.util

        from huggingface_hub import hf_hub_download
        from terratorch.cli_tools import LightningInferenceModel
        log.info("prithvi: loading model from %s", REPO)

        # Inference helper only lives in the IBM-NASA base repo.
        inference_py = hf_hub_download(BASE_REPO, "inference.py")

        m = None
        # ---- v2 path: yaml + ckpt from the published repo ----------
        if REPO != BASE_REPO:
            try:
                # The v2 repo publishes `prithvi_nyc_phase14.yaml` and
                # `prithvi_nyc_pluvial_v2.ckpt`. Be tolerant of small
                # naming drift (best_val_loss.ckpt etc.) by probing.
                v2_yaml = None
                for name in ("prithvi_nyc_phase14.yaml",
                              "config.yaml", "phase14.yaml",
                              "prithvi_nyc_v2.yaml"):
                    try:
                        v2_yaml = hf_hub_download(REPO, name)
                        break
                    except Exception:
                        continue
                v2_ckpt = None
                for name in ("prithvi_nyc_pluvial_v2.ckpt",
                              "best_val_loss.ckpt", "model.ckpt",
                              "last.ckpt"):
                    try:
                        v2_ckpt = hf_hub_download(REPO, name)
                        break
                    except Exception:
                        continue
                if v2_yaml and v2_ckpt:
                    log.info("prithvi: building v2 model from "
                             "yaml=%s ckpt=%s", v2_yaml, v2_ckpt)
                    m = LightningInferenceModel.from_config(v2_yaml, v2_ckpt)
                    # prithvi_nyc_phase14.yaml uses GenericNonGeoSegmentationDataModule
                    # which omits test_transform (→ None) and uses terratorch Normalize
                    # for aug (only handles 4D/5D). IBM inference.py:run_model() calls
                    # both on a 3D dict. Patch both to match the IBM base contract:
                    # ToTensorV2 for test_transform; Kornia AugmentationSequential
                    # (accepts dict input, adds batch dim) for aug.
                    if getattr(getattr(m, 'datamodule', None),
                               'test_transform', None) is None:
                        import albumentations as A
                        import torch as _torch
                        from albumentations.pytorch import ToTensorV2
                        m.datamodule.test_transform = A.Compose([ToTensorV2()])
                        _old = m.datamodule.aug

                        # IBM's inference.py:188 calls
                        # `datamodule.aug({'image': tensor})['image']`.
                        # kornia's AugmentationSequential doesn't accept
                        # dict input cleanly and tripped the
                        # `'list' object has no attribute 'view'`
                        # error on the L4 deploy. Use a hand-rolled
                        # dict-aware normalizer instead — same math,
                        # fewer moving parts, no kornia version skew.
                        class _DictNormalize:
                            def __init__(self, mean, std):
                                self.mean = _torch.as_tensor(mean).view(-1, 1, 1).float()
                                self.std = _torch.as_tensor(std).view(-1, 1, 1).float()

                            def __call__(self, sample):
                                if isinstance(sample, dict):
                                    img = sample["image"]
                                    mean = self.mean.to(img.device)
                                    std = self.std.to(img.device)
                                    return {**sample, "image": (img - mean) / std}
                                mean = self.mean.to(sample.device)
                                std = self.std.to(sample.device)
                                return (sample - mean) / std

                        # `_old.means` / `_old.stds` come from the
                        # yaml as Python lists — calling `.view()` on
                        # them is what tripped the original
                        # `'list' object has no attribute 'view'`.
                        # _DictNormalize handles the conversion via
                        # torch.as_tensor internally; just pass the
                        # raw values whatever their type.
                        m.datamodule.aug = _DictNormalize(_old.means, _old.stds)
                        log.info("prithvi: patched v2 datamodule transforms "
                                 "for IBM inference.py compat (dict-aware Normalize)")
                else:
                    log.warning("prithvi: v2 yaml/ckpt not "
                                "discoverable in %s; falling back to base",
                                REPO)
            except Exception as e:
                log.warning("prithvi: v2 build failed (%s); "
                             "falling back to base", e)
                m = None

        # ---- base path: proven IBM-NASA Sen1Floods11 fine-tune -----
        if m is None:
            base_config = hf_hub_download(BASE_REPO, "config.yaml")
            base_ckpt = hf_hub_download(
                BASE_REPO, "Prithvi-EO-V2-300M-TL-Sen1Floods11.pt")
            m = LightningInferenceModel.from_config(base_config, base_ckpt)

        m.model.eval()

        spec = importlib.util.spec_from_file_location("_prithvi_inference",
                                                       inference_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODEL = m
        _RUN_MODEL = mod.run_model
        return _MODEL, _RUN_MODEL


def search_scenes(bbox: list[float], start: str, end: str, max_cloud: float = 30.0) -> list:
    """Sentinel-2 L2A items over `bbox` between two ISO datetimes, least
    cloudy first."""
    import planetary_computer as pc
    from pystac_client import Client

    client = Client.open(STAC_URL, modifier=pc.sign_inplace)
    items = client.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=f"{start}/{end}",
                          query={"eo:cloud_cover": {"lt": max_cloud}}, max_items=50).items()
    return sorted(items, key=lambda it: it.properties.get("eo:cloud_cover", 100))


def grid(bbox: list[float], crs: str = "EPSG:32618", res: float = 10.0):
    """An empty 10 m grid covering `bbox` (lon/lat) in `crs`, as a
    DataArray to pass to read_bands(match=...). NYC is in UTM zone 18N."""
    import numpy as np
    import rioxarray  # noqa: F401
    import xarray as xr
    from pyproj import Transformer
    from rasterio.transform import from_origin

    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    xs, ys = t.transform([bbox[0], bbox[2], bbox[0], bbox[2]], [bbox[1], bbox[1], bbox[3], bbox[3]])
    x0, y1 = min(xs), max(ys)
    w, h = int((max(xs) - x0) / res), int((y1 - min(ys)) / res)
    da = xr.DataArray(np.zeros((h, w), "float32"), dims=("y", "x"),
                      coords={"y": y1 - res / 2 - res * np.arange(h), "x": x0 + res / 2 + res * np.arange(w)})
    return da.rio.write_crs(crs).rio.write_transform(from_origin(x0, y1, res, res))


def read_bands(item, bbox: list[float], match=None):
    """The six model bands over `bbox` as a (6, H, W) float32 reflectance
    array plus the reference DataArray (grid, transform, CRS). Pass
    `match` (a previous reference) to read onto the same grid."""
    import numpy as np
    import rioxarray  # noqa: F401
    import xarray as xr

    ref = match
    arrs = []
    for band in BANDS:
        da = rioxarray.open_rasterio(item.assets[band].href, masked=False).squeeze(drop=True)
        da = da.rio.clip_box(*bbox, crs="EPSG:4326")
        if ref is None:
            ref = da
        elif da.shape != ref.shape or da.rio.crs != ref.rio.crs:
            da = da.rio.reproject_match(ref)
        arrs.append(da.astype("float32"))
    img = xr.concat(arrs, dim="band", join="override").values
    if img.mean() > 1:
        img = img / 10000.0
    return np.nan_to_num(img.astype("float32")), ref


# Sentinel-2 L2A scene classification (SCL) classes that are not a clear
# view of the ground: saturated or defective, cloud shadow, cloud (medium
# and high probability), thin cirrus. Unclassified (7) is kept.
SCL_UNCLEAR = (1, 3, 8, 9, 10)


def clear_mask(item, bbox: list[float], match):
    """(H, W) bool, True where the scene's SCL layer shows a clear view,
    read onto the `match` grid (nearest neighbour, SCL is 20 m)."""
    import numpy as np
    import rioxarray  # noqa: F401
    from rasterio.enums import Resampling

    da = rioxarray.open_rasterio(item.assets["SCL"].href, masked=False).squeeze(drop=True)
    da = da.rio.clip_box(*bbox, crs="EPSG:4326").rio.reproject_match(match, resampling=Resampling.nearest)
    scl = da.values
    return (scl > 0) & ~np.isin(scl, SCL_UNCLEAR)


def water_mask(img):
    """(6, H, W) reflectance -> (H, W) uint8 mask, 1 = water. Runs the
    model on 512 px windows (zero-padded at the edges), in eval mode."""
    import numpy as np
    import torch

    model, _ = load_model()
    net, aug = model.model, model.datamodule.aug
    _, h, w = img.shape
    ph, pw = -h % IMG_SIZE, -w % IMG_SIZE
    x = torch.from_numpy(np.pad(img, ((0, 0), (0, ph), (0, pw))))
    x = aug(x) if not isinstance(aug(x), dict) else aug({"image": x})["image"]
    out = np.zeros((h + ph, w + pw), dtype="uint8")
    with torch.no_grad():
        for i in range(0, h + ph, IMG_SIZE):
            for j in range(0, w + pw, IMG_SIZE):
                win = x[:, i:i + IMG_SIZE, j:j + IMG_SIZE][None, :, None]  # (1, C, T=1, H, W)
                logits = net(win).output
                out[i:i + IMG_SIZE, j:j + IMG_SIZE] = logits.argmax(1)[0].cpu().numpy()
    return out[:h, :w]
