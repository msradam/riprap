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
STATE = {"sandy_nta": {"fraction": 0.0075},
         "dep_extreme_2080_nta": {"fraction_any": 0.1638, "fraction_class": {"1": 0.1, "2": 0.0638}},
         "nyc311_nta": {"n": 4263, "years": 3}}


def test_district_lead_is_cited_and_checked():
    lead = _area_lead(STATE, ITEMS)
    # The same three sentences, the reported record first: for an inland
    # district the Sandy share is the smallest number and it used to lead.
    assert lead == ("4263 flood-related 311 complaints were filed inside this area in the last 3 years [nyc311_nta]. "
                    "16.4% is modeled to flood from rainfall in the DEP extreme scenario for 2080 sea-level rise "
                    "[dep_extreme_2080_nta]. 0.8% of this area lies inside the 2012 Sandy inundation extent "
                    "[sandy_nta].")


def test_coastal_district_lead_states_the_rainfall_share_not_the_tide():
    """QN14's DEP value: 2.2% rainfall (classes 1 and 2), 43.1% future high
    tide (class 3). The lead quotes the rainfall share the sentence states,
    so the verifier keeps it."""
    state = {"dep_extreme_2080_nta": {"fraction_any": 0.4527,
                                      "fraction_class": {"1": 0.0121, "2": 0.01, "3": 0.4306}}}
    text = ("DEP Extreme Stormwater (3.66 in/hr, 2080 SLR): 2.2% of this area is modeled to flood from rainfall, "
            "1.2% as nuisance flooding and 1.0% as deep and contiguous flooding; 43.1% is in the future high tide "
            "area (the 2080 sea-level rise scenario).")
    items = [Evidence(pebble_id="dep_extreme_2080_nta", doc_id="dep_extreme_2080_nta", stone_id="cornerstone",
                      maturity="production", manifest=None, text=text)]
    assert _area_lead(state, items) == ("2.2% is modeled to flood from rainfall in the DEP extreme scenario for "
                                        "2080 sea-level rise [dep_extreme_2080_nta].")
