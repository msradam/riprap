"""The models list names what took part in a briefing: the LLM endpoint
when a question went through one, and nothing otherwise (no other model
runs)."""

from app.models_info import for_briefing


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
