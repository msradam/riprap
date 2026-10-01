"""The models panel lists what took part in a briefing (refactor 8)."""

from app.models_info import for_briefing


def test_models_that_ran_are_listed_with_where_and_latency():
    final = {
        "trace": [{"step": "policy_corpus", "ok": True, "elapsed_s": 1.4, "result": {"n": 1}},
                  {"step": "fema_nfhl", "ok": True, "elapsed_s": 0.5}],
        "policy_corpus": {"rag_hits": []},
        "plan": {"llm_calls": [{"model": "hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M",
                                "endpoint": "localhost:11434", "duration_s": 10.0}]},
        "grounding": {"llm_calls": [{"model": "hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M",
                                     "endpoint": "localhost:11434", "duration_s": 20.5}]},
    }
    rows = for_briefing(final)
    assert [r["repo"] for r in rows] == ["ibm-granite/granite-embedding-278m-multilingual",
                                          "flair/ner-english-ontonotes-fast",
                                          "hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M"]
    emb, _, llm = rows
    assert emb["where"] == "CPU" and emb["how"] == "loaded" and emb["latency_s"] == 1.4
    assert llm["where"].startswith("Ollama on this machine") and llm["calls"] == 2 and llm["latency_s"] == 30.5


def test_no_models_for_a_no_llm_briefing_without_model_pebbles():
    assert for_briefing({"trace": [{"step": "fema_nfhl", "ok": True}], "grounding": {"tier": "no_llm"}}) == []
