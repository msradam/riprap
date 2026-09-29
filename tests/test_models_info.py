"""The models panel lists what took part in a briefing (refactor 8)."""

from app.models_info import for_briefing


def test_models_that_ran_are_listed_with_where_and_latency():
    final = {
        "trace": [{"step": "ttm_battery_surge", "ok": True, "elapsed_s": 1.4, "result": {"n": 1}},
                  {"step": "ttm_311_forecast", "ok": True, "result": {"skipped": "not selected for this question"}},
                  {"step": "prithvi_water", "ok": True, "elapsed_s": 0.2, "result": {}},
                  {"step": "fema_nfhl", "ok": True, "elapsed_s": 0.5}],
        "ttm_battery_surge": {"peak": 0.4},
        "prithvi_water": {"rain_date": "2021-09-01",
                          "post_scene": "S2A_MSIL2A_20210902T154911_R054_T18TWL_20210903T050849;"
                                        "S2A_MSIL2A_20210902T154911_R054_T18TXL_20210903T042643",
                          "pre_scene": "S2A_MSIL2A_20210813T154911_R054_T18TWL_20210814T063950",
                          "batch_run": "2026-09-28"},
        "plan": {"llm_calls": [{"model": "hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M",
                                "endpoint": "localhost:11434", "duration_s": 10.0}]},
        "grounding": {"llm_calls": [{"model": "hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M",
                                     "endpoint": "localhost:11434", "duration_s": 20.5}]},
    }
    rows = for_briefing(final)
    assert [r["repo"] for r in rows] == ["msradam/Granite-TTM-r2-Battery-Surge", "msradam/Prithvi-EO-2.0-NYC-Pluvial",
                                          "hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M"]
    ttm, eo, llm = rows
    assert ttm["where"] == "CPU" and ttm["how"] == "loaded" and ttm["latency_s"] == 1.4
    assert eo["how"] == "precomputed" and eo["detail"] == ("batch output for the 2021-09-01 event: Sentinel-2 scenes "
                                                           "of 2021-09-02 vs 2021-08-13, tiles 18TWL, 18TXL; batch run 2026-09-28")
    assert llm["where"].startswith("Ollama on this machine") and llm["calls"] == 2 and llm["latency_s"] == 30.5


def test_no_models_for_a_no_llm_briefing_without_model_pebbles():
    assert for_briefing({"trace": [{"step": "fema_nfhl", "ok": True}], "grounding": {"tier": "no_llm"}}) == []
