"""A canary on the 311 dataset's own vocabulary. NYC renamed its flood
descriptors in July 2026 and Riprap undercounted until someone looked;
this fails when a flood-like descriptor under the sewer complaint types is
one Riprap does not count. Skipped when NYC Open Data cannot be reached."""

import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.context.nyc311 import COMPLAINT_TYPES, KIND, URL

FLOOD_LIKE = re.compile(r"flood|backup|catch basin clogged|manhole overflow", re.IGNORECASE)


def test_every_live_flood_descriptor_is_counted():
    since = (datetime.now(UTC) - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00")
    types = " OR ".join(f"complaint_type='{t}'" for t in COMPLAINT_TYPES)
    try:
        r = httpx.get(URL, timeout=30, params={"$select": "descriptor, count(*) AS n", "$group": "descriptor",
                                               "$where": f"({types}) AND created_date >= '{since}'"})
        r.raise_for_status()
    except httpx.HTTPError as e:
        pytest.skip(f"NYC Open Data did not answer: {e!r}")
    live = {row["descriptor"]: int(row["n"]) for row in r.json() if row.get("descriptor")}
    assert live, "the sewer complaint types returned no rows in 90 days: has the complaint type been renamed?"
    unknown = {d: n for d, n in live.items() if FLOOD_LIKE.search(d) and d not in KIND}
    assert not unknown, f"flood-like 311 descriptors Riprap does not count: {unknown}"
    assert any(d in KIND for d in live), "none of the counted descriptors appeared in 90 days"
