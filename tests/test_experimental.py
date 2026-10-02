"""The three experimental models: one hedging rule, answers that never
read as a measurement, and no experimental lead on a question about the
past. Offline: no model is loaded and no network is used."""

import json

import pytest

from app import experimental
from app.live import ttm_battery_surge as surge
from riprap.core.burr import rule_answer as ra
from riprap.core.burr import synthesis
from riprap.core.burr.intake import heuristic_plan


@pytest.fixture
def saved_evaluations(tmp_path, monkeypatch):
    (tmp_path / "surge.json").write_text(json.dumps({
        "n_windows": 635, "first": "2025-01-01", "last": "2026-09-27", "mae_cm": 11.5, "baseline_mae_cm": 13.3,
        "n_flood_windows": 23, "n_flood_foreseen": 1}))
    monkeypatch.setattr(experimental, "EVAL_DIR", tmp_path)


def test_every_model_sentence_is_labelled_limited_scored_and_pointed_elsewhere(saved_evaluations):
    s = experimental.hedge("surge", "the water may run 0.2 m above the tide", forecast=True)
    assert s.startswith("Experimental forecast: the water may run 0.2 m above the tide. Limits: ")
    assert "no wind or pressure input" in s
    assert "its mean error was 11.5 cm, against 13.3 cm" in s and "foresaw 1 of the 23 windows" in s
    assert "Rely on the National Weather Service (weather.gov/okx) and Notify NYC" in s
    assert experimental.hedge("surge", "x.").startswith("Experimental: x. Limits:")  # not about the future


def test_a_model_with_no_saved_evaluation_says_so(saved_evaluations):
    assert "it has no saved evaluation" in experimental.hedge("landcover", "x")


def test_models_are_pinned_to_a_commit_or_a_weights_hash():
    # A published model is pinned to a commit; the unpublished land-cover model (no repository) to its weights' SHA-256.
    for m in experimental.MODELS.values():
        assert m.extra in ("ml", "eo")
        if m.repo:
            assert m.repo.startswith("msradam/") and len(m.revision) == 40
        else:
            assert len(m.revision) == 64 and all(c in "0123456789abcdef" for c in m.revision)


def test_every_experimental_nyc_source_reads_one_of_the_three_models():
    from app.models_info import SOURCES
    from riprap.core.pebbles.bridge import get_registry

    marked = {p.id for p in get_registry("nyc").all() if p.manifest.maturity == "experimental"}
    assert marked == set(SOURCES)


STAGES = {"minor": 7.0, "moderate": 8.3, "major": 9.4}


def _forecast(peak_m: float, tide_ft: float):
    residual = [0.05] * 95 + [peak_m]
    tide = {f"2026-10-{d:02d} {h:02d}:00": tide_ft * surge.M_PER_FT for d in range(1, 7) for h in range(24)}
    return surge.summarize("2026-10-01 12:00", residual, tide, STAGES)


def test_surge_sentence_gives_value_unit_window_place_and_the_stage(saved_evaluations):
    v = _forecast(0.21, 5.0)
    n = v["narrative"]
    assert n.startswith("Experimental forecast: the water at The Battery may run up to 0.21 m (0.7 ft) above NOAA's "
                        "predicted tide in the next 96 hours, counted from 2026-10-01 12:00 UTC")
    assert "the highest total would be 5.7 ft above MLLW" in n and "below the gauge's minor flood stage of 7.0 ft" in n
    assert v["flood_category"] is None and not v["notable"]


def test_a_total_at_the_minor_stage_is_named_and_notable(saved_evaluations):
    v = _forecast(0.5, 6.0)
    assert v["flood_category"] == "minor" and v["notable"]
    assert "would reach the gauge's minor flood stage of 7.0 ft" in v["narrative"]
    assert " will " not in v["narrative"]  # never a certainty


def test_without_the_ml_extra_the_source_says_it_is_not_installed(monkeypatch):
    monkeypatch.setattr(surge, "ML_MISSING", True)
    v = surge.fetch()
    assert v["available"] is False and v["installed"] is False
    assert v["narrative"] == ("Experimental: the Battery surge forecast model is not available on this server; it "
                              "needs the optional ml extra (uv sync --extra ml).")


T = {
    "nws_water_forecast": "The National Weather Service forecasts a peak water level of 6.0 ft above MLLW at The Battery.",
    "noaa_tides": "Latest reading at The Battery, NY: 4.1 ft above MLLW.",
    "nws_alerts": "No active NWS flood, coastal or wind alerts at this point.",
    "ttm_battery_surge": "Experimental forecast: the water at The Battery may run up to 0.20 m above the tide.",
    "prithvi_water_nta": "Experimental: a satellite model showed 4,000 m² of new surface water in this area.",
    "dep_moderate_current_nta": "NYC DEP stormwater scenario: 7.2% of this area is modeled to flood from rainfall.",
    "landcover_nta": "Experimental: a satellite land-cover model labels 71.0% of this area as paved or built over.",
    "floodnet": "2 FloodNet community sensors within 600 m have logged 14 above-curb flood events in the last 3 years.",
    "nyc311": "7 NYC 311 flood-related complaints filed within 200 m in the last 5 years.",
    "sandy_inundation": "This address sits within the empirical 2012 Hurricane Sandy inundation footprint.",
    "dep_moderate_current": "This address is outside the modeled flooding in the NYC DEP stormwater scenario.",
    "ida_hwm": "USGS surveyed 2 Hurricane Ida high-water marks within 800 m of this address.",
}
V = {"floodnet": {"n_sensors": 2, "n_flood_events_3y": 14, "n_flood_events_good_3y": 14},
     "nyc311": {"n": 7, "years": 5, "by_year": {"2024": 7}, "by_kind": {}},
     "sandy_inundation": {"inside": True}, "ida_hwm": {"n_within_radius": 2, "nearest_dist_m": 100}}


@pytest.mark.parametrize("question,lead,facts", [
    # A surge question: the Weather Service's forecast, then the model's.
    ("Will the water at the Battery run above the predicted tide in the next four days, and by how much?",
     "facts", ["nws_water_forecast", "noaa_tides", "ttm_battery_surge"]),
    # No official source here answers these: the model's hedged sentence is the answer.
    ("How much of BX02 is paved over and how much is green?", "experimental", ["landcover_nta"]),
    ("Has the land cover in SI03 changed much in the last few years?", "experimental", ["landcover_nta"]),
    ("If this paving trend continues, is runoff likely to rise in QN12?", "experimental", ["landcover_nta"]),
    # What the satellite showed, when the question asks for it: after the surveyed record.
    ("What did satellite imagery show in BK18 after Ida?", "experimental", ["prithvi_water_nta"]),
])
def test_a_question_about_the_future_gets_the_models_hedged_answer(question, lead, facts):
    # A run has the point sources or the area ones, never both.
    area = any(f.endswith("_nta") for f in facts)
    texts = {k: v for k, v in T.items() if k.endswith("_nta") == area or k in ("nws_water_forecast", "noaa_tides")}
    assert ra.answer(question, texts, V) == (lead, facts)


def test_a_land_cover_question_quotes_the_citys_map_before_the_model():
    # The measured record comes first: the city's 2017 map is the source of the sentence, the model follows it,
    # and the lead is the neutral one, not "From an experimental model".
    city = "New York City's 2017 land cover map (6 inch, from LiDAR and aerial imagery) shows that 67.1% of this area is paved."
    area = {**{k: v for k, v in T.items() if k.endswith("_nta")}, "city_landcover_nta": city}
    assert ra.answer("How much of QN12 is paved over and how much is tree canopy?", area, V) == (
        "facts", ["city_landcover_nta", "landcover_nta"])
    # The model's saved maps missing on a server: the map still answers.
    del area["landcover_nta"]
    assert ra.answer("How much tree canopy does QN12 have?", area, V) == ("facts", ["city_landcover_nta"])


def test_water_that_lingers_is_answered_by_the_citys_stormwater_model_not_the_satellite():
    # The satellite model was tested for this and failed (docs/MODELS.md): it is not quoted.
    area = {k: v for k, v in T.items() if k.endswith("_nta")}
    lead, facts = ra.answer("Is Canarsie the kind of place where water sits around for a long time after heavy rain?", area, V)
    assert lead == "facts" and facts == ["dep_moderate_current_nta"]


def test_will_it_flood_is_neither_refused_nor_answered_yes_or_no():
    point = {k: v for k, v in T.items() if not k.endswith("_nta")}
    lead, facts = ra.answer("I live at 30 Waterside Plaza, Manhattan. Will my building flood next week?", point, V)
    assert lead == "no_prediction"
    assert facts == ["nws_alerts", "nws_water_forecast", "dep_moderate_current", "sandy_inundation", "ttm_battery_surge"]
    assert synthesis.LEAD_PHRASES[lead].startswith("Riprap cannot predict whether a particular place floods")
    plan = heuristic_plan("I live at 30 Waterside Plaza, Manhattan. Will my building flood next week?")
    assert plan["intent"] == "single_address" and plan["focus"]["time_frame"] == "future"
    # With no place there is nothing to answer with: still declined.
    assert heuristic_plan("Will it flood next Tuesday?")["intent"] == "out_of_scope"


@pytest.mark.parametrize("question,lead", [
    ("Has the block flooded since Hurricane Ida?", "yes"),
    # What the imagery showed is the model's to say: the surveyed marks come
    # first, and their "Yes." does not stand over the model's sentence.
    ("Did satellite imagery show flooding near here after Ida?", "facts"),
])
def test_a_model_never_sets_the_lead_of_a_question_about_past_flooding(question, lead):
    point = {**{k: v for k, v in T.items() if not k.endswith("_nta")}, "prithvi_water": T["prithvi_water_nta"]}
    got, facts = ra.answer(question, point, V)
    assert got == lead
    models = [f for f in facts if f.startswith(("prithvi", "landcover", "ttm"))]
    assert facts[0] not in models and facts[len(facts) - len(models):] == models
    assert ("prithvi_water" in facts) == ("satellite" in question)


def test_a_right_now_tide_question_adds_the_forecast_after_the_readings():
    lead, facts = ra.answer("Could tonight's high tide reach flood level in lower Manhattan?", T, V)
    assert lead == "facts" and facts[-1] == "ttm_battery_surge" and {"nws_alerts", "nws_water_forecast"} <= set(facts)
    # A right-now question that names no tide does not get it.
    assert "ttm_battery_surge" not in ra.answer("Is it flooding right now at 80 Pioneer Street?", T, V)[1]


def test_experimental_sources_stay_out_of_a_plain_briefing_unless_notable():
    from riprap.core.burr.templated_reconciler import _QUIET_UNLESS

    assert not _QUIET_UNLESS["ttm_battery_surge"]({"notable": False}) and _QUIET_UNLESS["ttm_battery_surge"]({"notable": True})
    assert not _QUIET_UNLESS["prithvi_water"]({"new_water_m2": 0}) and not _QUIET_UNLESS["landcover"]({"built_pct": 80})


def test_without_the_model_the_official_forecast_still_answers_and_the_absence_is_said():
    # A server without the ml extra (the Docker image): the Weather Service's
    # forecast and the gauge answer, not the gauge alone.
    q = "Will the water at the Battery run above the predicted tide in the next four days?"
    official = {k: T[k] for k in ("nws_water_forecast", "noaa_tides")}
    assert ra.time_frame(q) == "future"
    assert ra.answer(q, official, V) == ("facts", ["nws_water_forecast", "noaa_tides"])
    absent = {"ttm_battery_surge": "Experimental: the Battery surge forecast model is not available on this server."}
    assert ra.experimental(q, absent) == ([], ["ttm_battery_surge"])  # synthesis appends this sentence


def test_every_sentence_of_a_hedged_answer_carries_its_citation(saved_evaluations):
    from riprap.core.burr.evidence import cite

    text = cite(experimental.hedge("surge", "the water may run 0.2 m above the tide", forecast=True), "ttm_battery_surge",
                every=True)
    sentences = [s for s in text.split("[ttm_battery_surge]") if s.strip(" .")]
    assert len(sentences) == 3  # the statement, the limits with the accuracy, the pointer
    assert sentences[1].lstrip(". ").startswith("Limits:") and sentences[2].lstrip(". ").startswith("Rely on")


def test_a_percentage_is_a_numeric_claim():
    # "72.8% of this area" has no word boundary after the sign and once went uncited mid-paragraph.
    from riprap.core.burr.evidence import cite

    assert cite("72.8% of this area lies inside. Nothing else.", "sandy_nta") == (
        "72.8% of this area lies inside [sandy_nta]. Nothing else.")
