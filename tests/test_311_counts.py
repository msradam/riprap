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
    assert "in the last 3 years: 4 street flooding, 2 sewer backup. " in V["narrative"]


def test_every_count_carries_the_under_reporting_caveat():
    """A complaint count is a count of reports. The caveat is one sentence,
    in the sentence a reader sees and in the value a program reads (JSON,
    MCP), for a count of zero as for any other."""
    from app.context import nyc311
    from riprap.core.compliance.predicates import _sentences

    assert len(_sentences(nyc311.CAVEAT)) == 1
    assert "a low count can mean under-reporting and not the absence of flooding" in nyc311.CAVEAT
    # Both references were read on 2026-10-05: arxiv.org/abs/1710.02452 and doi.org/10.1214/24-AOAS2003.
    assert "Kontokosta, Hong and Korsberg, arXiv:1710.02452" in nyc311.CAVEAT
    assert "Boxer, Hong, Kontokosta and Neill, Annals of Applied Statistics 19(2), 2025" in nyc311.CAVEAT
    zero = _summarize([], years=5, radius_m=200)
    for v in (V, zero):
        assert v["caveat"] == nyc311.CAVEAT and v["narrative"].endswith(nyc311.CAVEAT)
        assert "complaints filed" in v["narrative"].split(". ")[0]


def test_the_requests_tool_carries_the_caveat(monkeypatch):
    from app.context import nyc311

    monkeypatch.setattr(nyc311, "_complaints_where", lambda clause, since, limit: [_c("Street Flooding (SJ)")])
    assert nyc311.flood_requests(community_district="QN12")["caveat"] == nyc311.CAVEAT


def test_a_neighbourhood_is_counted_with_its_exact_outline(monkeypatch):
    """Socrata is asked for the outline's bounding box and the rows are
    tested against the outline itself. A simplified outline in the query
    undercounted (Red Hook's area: 483 against 515)."""
    from shapely.geometry import Polygon

    from app.context import nyc311

    # An L: the notch at the top right is inside the bounding box and outside the outline.
    outline = Polygon([(-74.0, 40.0), (-73.0, 40.0), (-73.0, 40.5), (-73.5, 40.5), (-73.5, 41.0), (-74.0, 41.0)])
    seen = {}

    def fake(clause, since, limit):
        seen["clause"] = clause

        def at(key, lat, lon):
            return Complaint(key, "Street Flooding (SJ)", "2025-06-01", None, None, lat=lat, lon=lon)
        return [at("in the foot", 40.25, -73.25), at("in the stem", 40.75, -73.75),
                at("in the notch", 40.75, -73.25), Complaint("no point", "Backup", "2025-06-01", None, None)]

    monkeypatch.setattr(nyc311, "_complaints_where", fake)
    got = nyc311.complaints_in_polygon(outline)
    assert seen["clause"] == "within_box(location, 41.0, -74.0, 40.0, -73.0)"
    assert [c.unique_key for c in got] == ["in the foot", "in the stem"]


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
    monkeypatch.setattr(syn, "_documents", lambda state: (
        [Doc("nyc311_nta", "Touchstone", V["narrative"], False)],
        [SimpleNamespace(doc_id="nyc311_nta", pebble_id="nyc311_nta")], None))
    monkeypatch.setattr(syn.evidence, "citations", lambda items: {})
    reply = {"claims": [], "answer": {"lead": "count", "facts": ["nyc311_nta"]}}
    monkeypatch.setattr(syn.llm, "chat_json", lambda *a, **k: (reply, "scripted"))
    out = syn.synthesize({"intent": "neighborhood", "plan": {"question": Q}, "nyc311_nta": V})
    assert "**Answer.**\n4 street flooding complaints in the last 3 years, counting the 311 descriptors" in out["paragraph"]
    assert "4 street flooding, 2 sewer backup [nyc311_nta]." in out["paragraph"]


def test_district_counts_by_community_board_and_says_so(monkeypatch):
    """A community district is counted by the record's community_board
    field, not the NTA-union outline, and the sentence names the field."""
    from types import SimpleNamespace

    from app.areas import nta_evidence
    from app.context import nyc311

    seen = {}

    def fake(clause, since, limit):
        seen["clause"] = clause
        return [_c("Street Flooding (SJ)")] * 2

    monkeypatch.setattr(nyc311, "_complaints_where", fake)
    q = SimpleNamespace(extras={"area_code": "QN12"})
    out = nta_evidence.complaints(None, query=q, years=3)
    assert seen["clause"] == "community_board='12 QUEENS'"
    assert out["n"] == 2 and out["where"] == "in Community District QN12 (by the record's community board field)"
    assert out["narrative"].startswith("2 NYC 311 flood-related complaints filed in Community District QN12 "
                                       "(by the record's community board field) in the last 3 years")
    # An NTA code is not a district: the polygon path is unchanged.
    called = {}
    monkeypatch.setattr(nyc311, "summary_for_polygon", lambda polygon, years: called.setdefault("polygon", years))
    nta_evidence.complaints("poly", query=SimpleNamespace(extras={"area_code": "QN0201"}), years=3)
    assert called == {"polygon": 3}


def test_renamed_descriptors_count_as_the_same_kinds():
    """NYC renamed the descriptors in 2026 ("Backup" for "Sewer Backup (Use
    Comments) (SA)"); both names count, as one kind."""
    v = _summarize([_c("Sewer Backup (Use Comments) (SA)"), _c("Backup"), _c("Catch Basin Clogged"),
                    _c("Manhole Overflow"), _c("Flooding on Highway")], years=5, radius_m=200)
    assert v["n"] == 5
    assert v["by_kind"] == {"sewer backup": 2, "catch basin": 1, "manhole overflow": 1, "highway flooding": 1}


def test_a_request_logged_under_both_names_counts_once():
    def at(desc, minute, address="90-01 183 STREET"):
        return Complaint(unique_key=desc + str(minute), descriptor=desc, address=address, status=None,
                         created_date=f"2023-09-29T10:{minute:02d}:00.000")

    cs = [at("Street Flooding (SJ)", 0), at("Flooding on Street", 2),            # the same request twice
          at("Flooding on Street", 40),                                          # a later one, same address
          at("Flooding on Street", 2, address="1 OTHER STREET"),                 # another address
          at("Backup", 1)]                                                       # another kind
    v = _summarize(cs, years=5, radius_m=200)
    assert v["n"] == 4 and v["by_kind"] == {"street flooding": 3, "sewer backup": 1}
