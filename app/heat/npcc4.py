"""NPCC4 extreme heat projections for New York City (static lookup).

Source: Braneon, C. et al. (2024). NPCC4: New York City climate risk
information 2022, observations and projections. Annals of the New York
Academy of Sciences 1539 (doi:10.1111/nyas.15116), Table 4, "Projections
for extreme heat and extreme precipitation events in NYC for 2030-2100".
Baseline 1981-2010. The table was read from the paper on 2026-10-02 (the
text is saved in tests/fixtures/npcc4_table4.txt, and a test pins every
figure here to it).

The table gives the 10th, 25th, 75th and 90th percentiles and no median;
the sentence quotes the middle range (25th to 75th) with the 90th beside it,
as the sea-level sentence does. One table stands for the whole city: the
projections are for Central Park's record, not for a neighbourhood.
"""

CITATION = ("Braneon, C. et al. (2024). NPCC4: New York City climate risk information 2022, observations and "
            "projections. Annals of the New York Academy of Sciences 1539, doi:10.1111/nyas.15116, Table 4. "
            "Baseline 1981-2010.")
BASELINE = {"days_ge_90": 17, "days_ge_95": 4, "heat_waves": 2}
# Per year, by percentile, as printed in Table 4.
TABLE = {
    "2030s": {"days_ge_90": {10: 27, 25: 27, 75: 46, 90: 54}, "days_ge_95": {10: 8, 25: 8, 75: 17, 90: 27},
              "heat_waves": {10: 3, 25: 3, 75: 6, 90: 7}},
    "2050s": {"days_ge_90": {10: 32, 25: 38, 75: 62, 90: 69}, "days_ge_95": {10: 10, 25: 14, 75: 32, 90: 35},
              "heat_waves": {10: 4, 25: 5, 75: 8, 90: 9}},
    "2080s": {"days_ge_90": {10: 46, 25: 46, 75: 85, 90: 108}, "days_ge_95": {10: 17, 25: 17, 75: 54, 90: 73},
              "heat_waves": {10: 6, 25: 6, 75: 9, 90: 10}},
}


def get_projections() -> dict:
    """The NPCC4 table as a value, always available (static)."""
    out: dict = {"available": True, "baseline_period": "1981-2010", "baseline": BASELINE, "place": "New York City",
                 **{decade: {k: {str(p): v for p, v in pcts.items()} for k, pcts in rows.items()}
                    for decade, rows in TABLE.items()}}
    a, b = TABLE["2050s"], TABLE["2080s"]
    out["narrative"] = (
        f"NPCC4 (2024) projects {a['days_ge_90'][25]} to {a['days_ge_90'][75]} days a year at or above 90°F in New York "
        f"City by the 2050s and {b['days_ge_90'][25]} to {b['days_ge_90'][75]} by the 2080s, as its middle range (25th "
        f"to 75th percentile), against {BASELINE['days_ge_90']} a year in 1981-2010; the 90th percentile is "
        f"{a['days_ge_90'][90]} days by the 2050s and {b['days_ge_90'][90]} by the 2080s. Days at or above 95°F go "
        f"from {BASELINE['days_ge_95']} a year to {a['days_ge_95'][25]} to {a['days_ge_95'][75]} by the 2050s and "
        f"{b['days_ge_95'][25]} to {b['days_ge_95'][75]} by the 2080s, and heat waves from {BASELINE['heat_waves']} a "
        f"year to {a['heat_waves'][25]} to {a['heat_waves'][75]} and then {b['heat_waves'][25]} to "
        f"{b['heat_waves'][75]}. The ranges pool 16 climate models and two emissions scenarios (SSP2-4.5 and "
        "SSP5-8.5), and are for the city as a whole, not for a neighbourhood.")
    return out


def get_projections_area(polygon) -> dict:  # noqa: ARG001 - one projection for the whole city
    return get_projections()
