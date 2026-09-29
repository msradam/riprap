"""311 counts split by complaint kind, and a question about one kind
answered with that kind's count (refactor 5, phase 3). Offline."""

from types import SimpleNamespace

from app.context.nyc311 import Complaint, _summarize, kind_named
from riprap.core.burr import answer_checks as ac
from riprap.core.burr import synthesis as syn
from riprap.core.burr.synthesis import Doc


def _c(desc):
    return Complaint(unique_key="1", descriptor=desc, created_date="2025-06-01", address=None, status=None)


V = _summarize([_c("Street Flooding (SJ)")] * 3 + [_c("Flooding on Street")]
               + [_c("Sewer Backup (Use Comments) (SA)")] * 2, years=3, radius_m=None)
Q = "How many street flooding complaints has Queens CB 12 had?"


def test_summary_splits_by_kind_and_merges_the_two_street_descriptors():
    assert V["n"] == 6 and V["by_kind"] == {"street flooding": 4, "sewer backup": 2}
    assert V["narrative"].endswith("in the last 3 years: 4 street flooding, 2 sewer backup.")


def test_true_zero_says_the_source_answered():
    z = _summarize([], years=5, radius_m=200)
    assert z["n"] == 0 and "answered and none matched" in z["narrative"]


def test_kind_named():
    assert kind_named(Q) == "street flooding"
    assert kind_named("Any sewer back-up calls near here?") == "sewer backup"
    assert kind_named("How many flood complaints near here?") is None


def test_kind_question_uses_that_kind_count():
    docs, values = {"nyc311_nta": V["narrative"]}, {"nyc311_nta": V}
    assert ac.relevant_figure("nyc311_nta", docs, values, Q) == 4
    assert ac.relevant_figure("nyc311_nta", docs, values, "How many 311 flood complaints?") == 6
    assert ac.kind_lead(Q, docs, values) == ('4 street flooding complaints in the last 3 years, counting the 311 descriptors '
                                             '"Street Flooding (SJ)" and "Flooding on Street".')


def test_extractive_count_answer_leads_with_the_kind(monkeypatch):
    monkeypatch.setenv("RIPRAP_ANSWER_MODE", "extractive")
    monkeypatch.setattr(syn, "_documents", lambda state: (
        [Doc("nyc311_nta", "Touchstone", V["narrative"], False)],
        [SimpleNamespace(doc_id="nyc311_nta", pebble_id="nyc311_nta")], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"claims": [], "answer": {"lead": "count", "facts": ["nyc311_nta"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "neighborhood", "plan": {"question": Q}, "nyc311_nta": V})
    assert "**Answer.**\n4 street flooding complaints in the last 3 years, counting the 311 descriptors" in out["paragraph"]
    assert "4 street flooding, 2 sewer backup [nyc311_nta]." in out["paragraph"]
