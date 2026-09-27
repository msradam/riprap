"""The five answer error classes, on the refactor 2 failures (q05, q10,
q12, q16, q18, q19) and on answers that should pass."""

from riprap.core.burr.answer_checks import check_answer, check_claim, words_to_digits

IDA = "USGS surveyed 2 Hurricane Ida high-water mark(s) within 800 m of this address; the highest observed water elevation was 48.2 ft."
ALERTS = "There are 3 active NWS alerts at this point: Coastal Flood Warning (Severe), High Surf Advisory (Minor), and Rip Current Statement (Moderate)."
OBS = "The latest METAR observation at JFK Airport (7.8 km away) reports a temperature of 15.0°C."
SLR = "NPCC4 (2024) projects 0.38 m of sea-level rise at the Battery by 2050."
DEP50 = "This address is outside the modeled flooding in the NYC DEP stormwater scenario (2.13 in/hr, 2050 SLR)."
MTA = ("8 MTA subway entrances within 800 m of this address: 0 inside the 2012 Sandy inundation extent "
       "and 8 inside the DEP extreme stormwater scenario (2080 sea-level rise).")
NYCHA = ("5 NYCHA developments within 2000 m of this address: 3 inside the 2012 Sandy inundation extent "
         "and 2 inside the DEP extreme stormwater scenario (2080 sea-level rise).")


def classes(hits):
    return {c for c, _ in hits}


def test_q12_absence_contradicted_by_evidence():
    text = "No active flood alerts or precipitation observations indicate heavy rain near 90-01 183rd Street."
    assert "absence" in classes(check_claim(text, ["nws_alerts", "nws_obs"], {"nws_alerts": ALERTS, "nws_obs": OBS}))
    assert not check_claim("This address is not inside the Sandy footprint.", ["sandy_inundation"],
                           {"sandy_inundation": "This address sits outside the 2012 Sandy footprint."})


def test_q19_overgeneralised_quantifier():
    text = "The NYCHA developments near 560 Grand Street, Manhattan, are mapped within the 2012 Hurricane Sandy inundation extent."
    assert "universal" in classes(check_claim(text, ["nycha_development_exposure"], {"nycha_development_exposure": NYCHA}))
    ok = "3 of the 5 NYCHA developments near 560 Grand Street are inside the 2012 Sandy inundation extent."
    assert not check_claim(ok, ["nycha_development_exposure"], {"nycha_development_exposure": NYCHA})


def test_q18_all_inside_is_not_overgeneralised():
    text = "The subway entrances near 90-01 183rd Street are inside the DEP extreme stormwater scenario with 2080 sea-level rise."
    assert "universal" not in classes(check_claim(text, ["mta_entrance_exposure"], {"mta_entrance_exposure": MTA}))


def test_q10_warning_stated_as_observation():
    text = "There is a Coastal Flood Warning active near 80 Pioneer Street, indicating flooding is currently occurring."
    assert "inference" in classes(check_claim(text, ["nws_alerts"], {"nws_alerts": ALERTS}))


def test_q16_inference_joining_two_sources():
    text = ("NPCC4 projects 0.38 meters of sea-level rise at the Battery by 2050, which means the address "
            "is outside the flooding area under the DEP stormwater scenario.")
    assert "inference" in classes(check_claim(text, ["npcc4_slr", "dep_moderate_2050"],
                                              {"npcc4_slr": SLR, "dep_moderate_2050": DEP50}))


def test_q18_and_q05_dropped_count():
    q18 = "Are the subway entrances near 90-01 183rd Street, Queens in a flood scenario?"
    ans = ["The subway entrances near 90-01 183rd Street are inside the DEP extreme scenario with 2080 sea-level rise."]
    assert classes(check_answer(ans, q18, {"mta_entrance_exposure": MTA})) == {"dropped_count"}
    assert not check_answer(["Eight subway entrances are inside it."], q18, {"mta_entrance_exposure": MTA})
    q05 = "Has the block around 90-01 183rd Street, Queens flooded since Hurricane Ida?"
    ans05 = ["The block had a Hurricane Ida high-water mark within 800 meters, with the highest elevation at 48.2 feet."]
    assert classes(check_answer(ans05, q05, {"ida_hwm": IDA})) == {"dropped_count"}
    assert not check_answer([], q05, {"ida_hwm": IDA})  # the cannot-answer line is honest


def test_q05_elevation_without_datum():
    text = "The highest observed water elevation was 48.2 feet."
    assert "datum" in classes(check_claim(text, ["ida_hwm"], {"ida_hwm": IDA}))
    assert not check_claim("The highest water elevation was 48.2 ft NAVD88.", ["ida_hwm"], {"ida_hwm": IDA})


def test_number_words():
    assert words_to_digits("Four schools and two hospitals") == "4 schools and 2 hospitals"


def test_rain_question_wants_the_precipitation_not_the_temperature():
    q = "Is it raining near the address right now?"
    dry = {"nws_obs": "Latest METAR at JFK (7.8 km away): 15.0°C, no recent precipitation."}
    assert not check_answer(["No recent precipitation was reported at JFK."], q, dry)
    wet = {"nws_obs": "Latest METAR at JFK (7.8 km away): 15.0°C, 8.4 mm precip in the last hour."}
    assert check_answer(["It is 15.0°C at JFK."], q, wet)
    assert not check_answer(["JFK reported 8.4 mm of rain in the last hour."], q, wet)


def test_a_count_is_matched_exactly_not_through_unit_conversion():
    q = "Has the block around 90-01 183rd Street flooded since Hurricane Ida?"
    doc = {"ida_hwm": "USGS surveyed 2 Hurricane Ida high-water mark(s) within 800 m; the highest stood 0.76 ft above ground."}
    ans = ["The block had a Hurricane Ida high-water mark, the highest standing 0.76 ft above ground."]
    assert classes(check_answer(ans, q, doc)) == {"dropped_count"}


def test_no_states_a_count_of_zero():
    doc = {"doh_hospital_exposure": "0 hospitals within 3000 m of this address: 0 inside the 2012 Sandy inundation extent and 0 inside the DEP extreme stormwater scenario."}
    assert not check_answer(["No hospitals are mapped within 3000 meters."], "Are any hospitals nearby flooded?", doc)
