"""The models list names what took part in a briefing: the LLM endpoint
when a question went through one, and nothing otherwise (no other model
runs)."""

from app.models_info import for_briefing, loaded


def test_the_llm_is_listed_with_where_calls_and_latency():
    final = {
        "trace": [{"step": "fema_nfhl", "ok": True, "elapsed_s": 0.5}],
        "plan": {"llm_calls": [{"model": "hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M",
                                "endpoint": "localhost:11434", "duration_s": 10.0}]},
        "grounding": {"llm_calls": [{"model": "hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M",
                                     "endpoint": "localhost:11434", "duration_s": 20.5}]},
    }
    (llm,) = for_briefing(final)
    assert llm["repo"] == "hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M" and llm["how"] == "endpoint"
    assert llm["where"].startswith("Ollama on this machine") and llm["calls"] == 2 and llm["latency_s"] == 30.5


def test_no_models_for_a_briefing_made_without_the_llm():
    assert for_briefing({"trace": [{"step": "fema_nfhl", "ok": True}], "grounding": {"tier": "no_llm"}}) == []


def test_api_models_gives_each_experimental_model_its_tested_result_and_status():
    surge, cover = loaded()["experimental"]
    assert surge["repo"] == "msradam/Granite-TTM-r2-Battery-Surge" and surge["status"].startswith("not in default briefings")
    assert "for the best rule tested that needs no model" in surge["tested"] and "distinct events" in surge["tested"]
    assert cover["name"] == "NYC land-cover model" and "less tree canopy than the city's 2017 map" in cover["tested"]
    assert cover["status"].startswith("in land-cover answers")
