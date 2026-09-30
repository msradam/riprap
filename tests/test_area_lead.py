"""A community district briefing opens with a cited lead, as an address does."""
from riprap.core.burr.evidence import Evidence
from riprap.core.burr.templated_reconciler import _area_lead

ITEMS = [
    Evidence(pebble_id="sandy_nta", doc_id="sandy_nta", stone_id="cornerstone", maturity="production", manifest=None,
             text="0.8% of this area lies inside the 2012 Hurricane Sandy inundation extent (area 24.7 km²)."),
    Evidence(pebble_id="dep_extreme_2080_nta", doc_id="dep_extreme_2080_nta", stone_id="cornerstone", maturity="production", manifest=None,
             text="DEP Extreme Stormwater (3.66 in/hr, 2080 SLR): 16.4% of this area is modeled to flood from rainfall."),
    Evidence(pebble_id="nyc311_nta", doc_id="nyc311_nta", stone_id="touchstone", maturity="production", manifest=None,
             text="4263 NYC 311 flood-related complaints filed inside this area in the last 3 years."),
]
STATE = {"sandy_nta": {"fraction": 0.0075}, "dep_extreme_2080_nta": {"fraction_any": 0.1638},
         "nyc311_nta": {"n": 4263, "years": 3}}


def test_district_lead_is_cited_and_checked():
    lead = _area_lead(STATE, ITEMS)
    assert lead == ("0.8% of this area lies inside the 2012 Sandy inundation extent [sandy_nta]. "
                    "16.4% is modeled to flood from rainfall in the DEP extreme scenario for 2080 sea-level rise "
                    "[dep_extreme_2080_nta]. 4263 flood-related 311 complaints were filed inside this area in the "
                    "last 3 years [nyc311_nta].")
