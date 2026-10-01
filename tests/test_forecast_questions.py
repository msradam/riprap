"""Forecast questions reach the Lodestone: they plan with focus time_frame
future and a point intent, run the Weather Service's water-level forecast
and every projection, and their answers never lead with yes or no (a
forecast is not an observation)."""

from types import SimpleNamespace

from riprap.core.burr import synthesis as syn
from riprap.core.burr.intake import forecast_question, heuristic_plan
from riprap.core.burr.stones import floor_for, select_pebbles
from riprap.core.burr.synthesis import Doc
from riprap.core.pebbles.bridge import get_registry

Q = "What do the forecasts show for flooding near 80 Pioneer Street, Brooklyn?"
NYC = get_registry("nyc")


def test_forecast_questions_are_detected_and_named_days_are_not():
    assert forecast_question(Q)
    assert forecast_question("What sea-level rise is projected near 200 Water Street by 2050?")
    assert not forecast_question("Will 200 Water Street, Manhattan flood next Tuesday?")  # refused elsewhere
    assert not forecast_question("Is there flooding near 80 Pioneer Street right now?")


def test_forecast_question_plans_as_a_point_question_with_future_focus():
    p = heuristic_plan(Q)
    assert p["intent"] == "single_address" and p["focus"]["time_frame"] == "future"
    assert heuristic_plan("Will 200 Water Street, Manhattan flood next Tuesday?")["intent"] == "out_of_scope"


def test_llm_plan_saying_live_now_is_corrected(monkeypatch):
    from riprap.core.burr import app

    fake = SimpleNamespace(intent="live_now", targets=[{"type": "address", "text": "80 Pioneer Street, Brooklyn"}],
                           rationale="r", question=Q, focus={"hazard": "flood", "time_frame": "now", "assets": []},
                           pebbles=["nws_alerts"], catalog=[m.id for m in NYC.all()])
    monkeypatch.setattr(app, "_tier", lambda: "llm")
    monkeypatch.setattr("app.planner.plan", lambda q, ledger=None: fake)
    plan = app.plan_for(Q)
    assert plan["intent"] == "single_address" and plan["focus"]["time_frame"] == "future"


def test_future_floor_runs_every_forecast():
    plan = {"intent": "single_address", "question": Q, "pebbles": ["nws_alerts"],
            "catalog": [m.id for m in NYC.all()], "focus": {"time_frame": "future", "assets": []}}
    chosen = set(select_pebbles(plan, NYC))
    assert {"nws_water_forecast", "npcc4_slr", "dep_moderate_2050", "dep_extreme_2080"} <= chosen
    assert "nws_water_forecast" in floor_for(plan)


def test_forecast_answer_quotes_the_weather_service_and_has_no_yes(monkeypatch):
    surge = ("The National Weather Service forecasts a peak water level of 8.5 ft above MLLW at The Battery on "
             "2026-10-01 16:00 UTC (forecast issued 2026-09-30 07:44 UTC), which reaches the gauge's moderate "
             "flood stage of 8.3 ft.")
    docs = [Doc("nws_water_forecast", "Projector", surge, False)]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"answer": {"lead": "yes", "facts": ["nws_water_forecast"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "single_address", "plan": {"question": Q, "focus": {"time_frame": "future"}}})
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    assert answer.startswith("From the sources consulted: The National Weather Service forecasts")
    assert "moderate flood stage of 8.3 ft" in answer and "Yes." not in answer


def test_forecast_facts_are_the_forecasts_not_the_flood_zone(monkeypatch):
    docs = [Doc("fema_nfhl", "Hazard Reader", "This address sits in FEMA flood zone AE.", False),
            Doc("npcc4_slr", "Projector", "NPCC4 projects 0.38 m of sea-level rise by the 2050s.", False),
            Doc("nws_water_forecast", "Projector", "The National Weather Service forecasts a peak of 6.0 ft.", False)]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"answer": {"lead": "cannot_answer", "facts": []}}  # the model declines; the forecasts answer anyway
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "single_address", "plan": {"question": Q, "focus": {"time_frame": "future"}}})
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    # The Weather Service's forecast for the coming days leads; the projection for the decades follows.
    assert answer.index("[nws_water_forecast]") < answer.index("[npcc4_slr]") and "fema_nfhl" not in answer


def test_a_scenario_question_keeps_the_model_facts(monkeypatch):
    docs = [Doc("dep_moderate_2050", "Hazard Reader", "The DEP 2050 scenario models deep and contiguous flooding (1 ft or more) here.",
                False),
            Doc("nws_water_forecast", "Projector", "The National Weather Service forecasts a peak of 6.0 ft.", False)]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"answer": {"lead": "yes", "facts": ["dep_moderate_2050"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    q = "What does the 2050 stormwater scenario show at 400 Carroll Street, Brooklyn?"
    out = syn.synthesize({"intent": "single_address", "plan": {"question": q, "focus": {"time_frame": "future"}}})
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    assert answer.startswith("From the sources consulted: The DEP 2050 scenario") and "nws_water_forecast" not in answer


def test_weather_service_forecast_names_the_stage_it_reaches(monkeypatch):
    """The peak of the forecast still ahead, and the flood stage it reaches
    by the gauge's own stages. Offline: the two API calls are stubbed."""
    from app.context import nws_water

    gauge = {"flood": {"categories": {"minor": {"stage": 7.0}, "moderate": {"stage": 8.3}, "major": {"stage": 9.4},
                                      "action": {"stage": 7.0}}}}
    fc = {"issuedTime": "2026-09-30T07:44:00Z",
          "data": [{"validTime": "2000-01-01T00:00:00Z", "primary": 12.0},   # already past: not the peak
                   {"validTime": "2999-01-01T10:00:00Z", "primary": 6.1},
                   {"validTime": "2999-01-01T16:00:00Z", "primary": 8.5},
                   {"validTime": "2999-01-02T04:00:00Z", "primary": -999}]}
    monkeypatch.setattr(nws_water, "_json", lambda path: fc if path.endswith("forecast") else gauge)
    v = nws_water.summary_for_point(40.7074, -74.0048)
    assert v["gauge_id"] == "BATN6" and v["forecast_peak_ft_mllw"] == 8.5 and v["flood_category"] == "moderate"
    assert v["narrative"] == ("The National Weather Service forecasts a peak water level of 8.5 ft above MLLW at The "
                              "Battery on 2999-01-01 16:00 UTC (forecast issued 2026-09-30 07:44 UTC), which reaches "
                              "the gauge's moderate flood stage of 8.3 ft.")
    fc["data"][2]["primary"] = 6.5
    assert nws_water.summary_for_point(40.7074, -74.0048)["narrative"].endswith(
        "below the gauge's minor flood stage of 7.0 ft.")
    fc["data"] = fc["data"][:1]
    assert nws_water.summary_for_point(40.7074, -74.0048) is None  # no forecast ahead: silence, not a stale peak
