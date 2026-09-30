"""The four register summaries are one table-driven query
(app.registers.exposure). Each returned dict must stay identical, keys
and values, to what the hand-written modules returned, because the card
adapter, the manifests' trace_summary blocks,
answer_checks._register_counts and the gallery JSON read it. The
fixtures were captured from those modules at six points before the
collapse; a change here is a change the frontend sees."""
import json
from pathlib import Path

import pytest

from app.registers import exposure

FIXTURES = Path(__file__).parent / "fixtures" / "registers"
POINTS = [(40.711001, -73.777712), (40.677, -74.0105), (40.5757, -73.986),
          (40.707431, -74.00476), (40.8296, -73.9262), (40.6436, -74.0781)]


def _canon(v: dict) -> str:
    return json.dumps(v, sort_keys=True, default=str)


@pytest.mark.parametrize("asset_class", ["mta_entrances", "doh_hospitals", "doe_schools", "nycha"])
def test_summary_matches_the_snapshot(asset_class):
    want = json.loads((FIXTURES / f"{asset_class}.json").read_text())
    for lat, lon in POINTS:
        assert _canon(exposure.summary_for_point(lat, lon, asset_class)) == _canon(want[f"{lat},{lon}"]), (asset_class, lat, lon)
