"""Forecast questions reach the Lodestone (refactor 8): they plan with focus
time_frame future and a point intent, run every forecast and projection,
and their answers keep the experimental labels and never lead with yes/no."""

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
    assert {"ttm_battery_surge", "floodnet_forecast", "ttm_311_forecast", "npcc4_slr",
            "dep_moderate_2050", "dep_extreme_2080"} <= chosen
    assert "ttm_battery_surge" in floor_for(plan)


def test_forecast_answer_keeps_labels_and_has_no_yes(monkeypatch):
    surge = ("a TTM model fine-tuned on Battery gauge history, with no wind or pressure input, forecasts a peak "
             "surge residual of 0.46 m at The Battery about 4 h ahead. Use NOAA ETSS or the Stevens Flood "
             "Advisory System for storm decisions.")
    docs = [Doc("ttm_battery_surge", "Projector", surge, True)]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"answer": {"lead": "yes", "facts": ["ttm_battery_surge"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "single_address", "plan": {"question": Q, "focus": {"time_frame": "future"}}})
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    assert answer.startswith("From the sources consulted: Experimental: a TTM model")
    assert "Use NOAA ETSS or the Stevens Flood Advisory System" in answer and "Yes." not in answer


def test_forecast_facts_are_the_forecasts_not_the_flood_zone(monkeypatch):
    docs = [Doc("fema_nfhl", "Hazard Reader", "This address sits in FEMA flood zone AE.", False),
            Doc("npcc4_slr", "Projector", "NPCC4 projects 0.38 m of sea-level rise by the 2050s.", False),
            Doc("ttm_battery_surge", "Projector", "a TTM model forecasts a peak surge residual of 0.41 m.", True)]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"answer": {"lead": "cannot_answer", "facts": []}}  # the model declines; the forecasts answer anyway
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "single_address", "plan": {"question": Q, "focus": {"time_frame": "future"}}})
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    # The experimental surge forecast comes after the NPCC4 projection.
    assert answer.index("[npcc4_slr]") < answer.index("[ttm_battery_surge]") and "fema_nfhl" not in answer


def test_a_scenario_question_keeps_the_model_facts(monkeypatch):
    docs = [Doc("dep_moderate_2050", "Hazard Reader", "The DEP 2050 scenario models deep and contiguous flooding (1 ft or more) here.",
                False),
            Doc("ttm_battery_surge", "Projector", "a TTM model forecasts a peak surge residual of 0.41 m.", True)]
    monkeypatch.setattr(syn, "_documents", lambda state: (docs, [], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"answer": {"lead": "yes", "facts": ["dep_moderate_2050"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    q = "What does the 2050 stormwater scenario show at 400 Carroll Street, Brooklyn?"
    out = syn.synthesize({"intent": "single_address", "plan": {"question": q, "focus": {"time_frame": "future"}}})
    answer = out["paragraph"].split("**Answer.**\n")[1].split("\n\n")[0]
    assert answer.startswith("From the sources consulted: The DEP 2050 scenario") and "ttm_battery_surge" not in answer
