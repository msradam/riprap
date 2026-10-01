"""NPCC4 sea-level rise projections for New York City (static lookup).

Source: Braneon, C. et al. (2024). NPCC4: New York City climate risk
information 2022, observations and projections. Annals of the New York
Academy of Sciences 1539 (doi:10.1111/nyas.15116), Table 1, "Projections
for sea level rise in New York City for 2030-2150", relative to a
1995-2014 baseline.

The table gives the 10th, 25th, 75th and 90th percentiles and no median.
The middle range (25th to 75th) is what the report itself quotes in its
text, so the sentence quotes it, with the 90th percentile as the high end.

An earlier version of this table (15 in at the median and 29 in at the
90th percentile for the 2050s, on a 2000-2004 baseline, cited to a "Table
3.2") matched no table in the report. It was replaced on 2026-10-01 after
a check against the published paper.
"""

DOC_ID = "npcc4_slr"
CITATION = (
    "Braneon, C. et al. (2024). NPCC4: New York City climate risk information 2022, "
    "observations and projections. Annals of the New York Academy of Sciences 1539, "
    "doi:10.1111/nyas.15116, Table 1. Baseline 1995-2014."
)

# Inches above the 1995-2014 baseline, by percentile, as printed in Table 1.
_TABLE_IN = {
    "2030s": {10: 6, 25: 7, 75: 11, 90: 13},
    "2050s": {10: 12, 25: 14, 75: 19, 90: 23},
    "2080s": {10: 21, 25: 25, 75: 39, 90: 45},
    "2100": {10: 25, 25: 30, 75: 50, 90: 65},
}


def _in_to_m(inches: float) -> float:
    return round(inches * 0.0254, 2)


def get_projections() -> dict:
    """The NPCC4 table as a value, always available (static)."""
    result: dict = {"available": True, "baseline": "1995-2014", "place": "New York City"}
    for period, pcts in _TABLE_IN.items():
        result[period] = {str(pct): {"in": v, "m": _in_to_m(v)} for pct, v in pcts.items()}
    a, b = result["2050s"], result["2100"]
    result["narrative"] = (
        f"NPCC4 (2024) projects sea-level rise in New York City of {a['25']['in']} to {a['75']['in']} in "
        f"({a['25']['m']} to {a['75']['m']} m) by the 2050s and {b['25']['in']} to {b['75']['in']} in "
        f"({b['25']['m']} to {b['75']['m']} m) by 2100, relative to 1995-2014, as its middle range (25th to "
        f"75th percentile); the 90th percentile is {a['90']['in']} in ({a['90']['m']} m) by the 2050s and "
        f"{b['90']['in']} in ({b['90']['m']} m) by 2100."
    )
    return result
