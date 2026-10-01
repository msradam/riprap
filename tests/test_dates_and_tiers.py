"""Dates and tiers say what the data says (gallery critique, P2): the FEMA
citation is dated by its FIRM panel, the DEM label matches the raster's
resolution. Offline."""

from pathlib import Path

from riprap.core.pebbles import load_registry
from riprap.core.pebbles.vintage import citation

ROOT = Path(__file__).resolve().parent.parent
FEDERAL = load_registry(ROOT / "deployments" / "federal")
NYC = load_registry(ROOT / "deployments" / "nyc")


def test_fema_citation_vintage_is_the_firm_effective_date():
    m = FEDERAL.get("fema_nfhl").manifest
    c = citation(m, value={"fld_zone": "X", "effective_year": 2007, "effective_date": "2007-09-05"})
    assert c["vintage"] == c["date_modified"] == "2007-09-05"
    assert c["retrieved_at"] not in (None, "2007-09-05")  # the read time stays the retrieval date
    # Without an effective date the citation keeps the manifest's vintage.
    assert citation(m, value={"fld_zone": "X", "effective_date": None})["date_modified"] != "2007-09-05"


def test_fema_value_carries_the_effective_date(monkeypatch):
    from app.context import fema_nfhl

    def query(layer, lat, lon, fields, ttl):
        if layer == fema_nfhl._ZONE_LAYER:
            return [{"attributes": {"FLD_ZONE": "X", "SFHA_TF": "F"}}]
        return [{"attributes": {"FIRM_PAN": "3604970234F", "EFF_DATE": 1188964800000}}]  # 2007-09-05 04:00 UTC

    monkeypatch.setattr(fema_nfhl, "_point_query", query)
    v = fema_nfhl.summary_for_point(40.71, -73.78)
    assert v["effective_date"] == "2007-09-05" and v["effective_year"] == 2007


def test_briefing_citation_for_fema_uses_the_value():
    from riprap.core.burr import evidence

    state = {"fema_nfhl": {"fld_zone": "X", "effective_year": 2007, "effective_date": "2007-09-05",
                           "narrative": "This address sits in FEMA flood zone X, per NFHL FIRM panel 3604970234F, "
                                        "effective 2007."}}
    stones, registry = evidence.load("federal")
    cites = evidence.citations(evidence.collect(state, stones, registry))
    assert cites["fema_nfhl"]["vintage"] == "2007-09-05"


def test_dem_label_states_no_resolution_the_raster_does_not_have():
    from app.context import microtopo

    labels = [microtopo.CITATION, NYC.get("microtopo").manifest.provenance.source_name,
              NYC.get("microtopo").manifest.provenance.citation,
              NYC.get("microtopo_nta").manifest.provenance.source_name]
    assert all("30 m" not in s and s.startswith("USGS 3DEP DEM") for s in labels)


def test_zone_x_subtype_is_read_out():
    from app.context.fema_nfhl import zone_reading

    assert zone_reading("0.2 PCT ANNUAL CHANCE FLOOD HAZARD") == "the 0.2% annual chance, or 500-year, floodplain"
    assert zone_reading("AREA OF MINIMAL FLOOD HAZARD") == "an area of minimal flood hazard"
    assert zone_reading(None) is None and zone_reading("  ") is None
