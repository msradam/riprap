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


def nyc311_scope() -> str:
    from app.context.nyc311 import KIND, SCOPE

    assert SCOPE.startswith("eleven descriptors") and len(KIND) == 11  # the sentence's own count of them
    return SCOPE


def test_summary_splits_by_kind_and_merges_the_two_street_descriptors():
    assert V["n"] == 6 and V["by_kind"] == {"street flooding": 4, "sewer backup": 2}
    assert f"in the last 3 years (since {V['since']}; {nyc311_scope()}): 4 street flooding, 2 sewer backup. " in V["narrative"]


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
        assert "complaints about flooding and sewer backups filed" in v["narrative"].split(". ")[0]


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
                                             '"Street Flooding (SJ)" and "Flooding on Street" [nyc311_nta].')


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
    assert out["narrative"].startswith("2 NYC 311 complaints about flooding and sewer backups filed in Community District QN12 "
                                       f"(by the record's community board field) in the last 3 years (since {out['since']}; ")
    # The exact query the count was read from travels with it.
    assert out["query_url"].startswith("https://data.cityofnewyork.us/resource/erm2-nwe9.json?%24select=")
    assert "community_board%3D%2712+QUEENS%27" in out["query_url"] and "created_date+%3E%3D" in out["query_url"]
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


def test_no_house_number_or_house_coordinate_is_served(monkeypatch):
    """A dated complaint at a house number is a record about a household
    (one house had fifteen sewer backups listed). Each complaint is served at
    its block, with coordinates rounded to three decimal places (about 100 m);
    the count is unchanged. The briefing value, the 311 tool and route, and
    the gallery bake's strip step all hold to it."""
    import json
    import sys
    from pathlib import Path

    from app.context import nyc311

    rows = [{"unique_key": str(i), "descriptor": "Sewer Backup (Use Comments) (SA)", "created_date": f"2026-05-{i + 1:02d}T10:00:00",
             "incident_address": "90-12 183 STREET", "street_name": "183 STREET", "cross_street_1": "90 AVE",
             "cross_street_2": "91 AVE", "status": "Closed", "latitude": "40.71089296427826", "longitude": "-73.77792504589425"}
            for i in range(15)]
    rows.append({"unique_key": "x", "descriptor": "Catch Basin Clogged", "created_date": "2026-04-01T10:00:00",
                 "incident_address": "90 AVENUE", "street_name": "90 AVENUE", "cross_street_1": "90 AVENUE",
                 "cross_street_2": "184 STREET", "latitude": "40.71125090957996", "longitude": "-73.77708701255543"})

    class Reply:
        def raise_for_status(self): pass
        def json(self): return rows

    monkeypatch.setattr(nyc311.http, "get", lambda *a, **k: Reply())
    v = nyc311.summary_for_point(40.7105, -73.7772)
    tool = nyc311.flood_requests(lat=40.7105, lon=-73.7772)
    assert v["n"] == tool["n"] == 16 and len(v["points"]) == 16  # every record is still counted and shown
    assert v["points"][0] == {"date": "2026-05-01", "descriptor": "Sewer Backup (Use Comments) (SA)",
                              "block": "183 STREET between 90 AVE and 91 AVE", "lat": 40.711, "lon": -73.778}
    assert v["points"][-1]["block"] == "90 AVENUE and 184 STREET"  # an intersection request
    assert v["most_recent"][0] == {"date": "2026-05-01", "descriptor": "Sewer Backup (Use Comments) (SA)",
                                   "block": "183 STREET between 90 AVE and 91 AVE"}
    for served in (v, tool):
        text = json.dumps({k: x for k, x in served.items() if k != "query_url"})
        assert "90-12" not in text and "address" not in text and "40.7108929" not in text, text
    assert "complaints about flooding and sewer backups" in v["narrative"] and "studies of other 311 complaint types" in v["caveat"]
    # Review round 2: the published query link returns no house number and no coordinates either.
    from urllib.parse import unquote_plus

    link = unquote_plus(nyc311.query_url("within_circle(location, 40.71, -73.77, 200)", None, 2000))
    select = link.split("$select=")[1].split("&")[0]
    assert "incident_address" not in select and "latitude" not in select and "longitude" not in select
    assert all(f in select for f in ("created_date", "descriptor", "street_name", "cross_street_1"))

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from build_gallery import HOUSES_STRIPPED, strip_records

    old = {"nyc311": {"n": 1, "points": [{"lat": 40.71089296427826, "lon": -73.77792504589425, "address": "90-12 183 STREET"}],
                      "most_recent": [{"date": "2026-05-24", "address": "90-12 183 STREET"}]},
           "geocode": {"address": "90-01 183 STREET", "bbl": "4099040046", "bin": "4211957"}}
    assert strip_records(old) == {"nyc311": {"n": 1, "points": [{"lat": 40.711, "lon": -73.778}], "most_recent": [{"date": "2026-05-24"}]},
                                  "geocode": {"address": "90-01 183 STREET"}}
    # Every snapshot baked since the rule holds no complaint address (older ones have no mark, until rebuilt).
    gallery = Path(__file__).resolve().parent.parent / "web" / "sveltekit" / "src" / "lib" / "gallery"
    for f in sorted(gallery.glob("*.json")):
        d = json.loads(f.read_text()) if f.name != "index.json" else {}
        for key in ("nyc311", "nyc311_nta"):
            block = ((d.get("final") or {}).get(key) or {}) if d.get(HOUSES_STRIPPED) else {}
            assert not any("address" in row for row in [*(block.get("points") or []), *(block.get("most_recent") or [])]), f.name
