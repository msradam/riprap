from __future__ import annotations

import pytest

from app.spatial import _check_not_lfs_pointer


def test_lfs_pointer_raises_actionable_error(tmp_path):
    pointer = tmp_path / "sandy_inundation.geojson"
    pointer.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:2d5b899acc144a422ca340eabe100c91c5fe110e2b13e62216e61fdc07b00200\n"
        "size 91392952\n"
    )
    with pytest.raises(RuntimeError, match="git lfs pull"):
        _check_not_lfs_pointer(pointer)


def test_real_small_file_does_not_raise(tmp_path):
    real = tmp_path / "small.geojson"
    real.write_text('{"type": "FeatureCollection", "features": []}')
    _check_not_lfs_pointer(real)  # should not raise


def test_missing_file_does_not_raise(tmp_path):
    _check_not_lfs_pointer(tmp_path / "does_not_exist.geojson")
