"""Claim verifier: hand-written good and bad claims against fixed docs.
No LLM, no network."""
from __future__ import annotations

from riprap.core.burr.synthesis import Doc, _render, claims_schema, number_supported, verify

DOCS = [
    Doc("nyc311", "Live observer",
        "22 NYC 311 flood-related complaints filed within 200 m of this location in the last 5 years.",
        False),
    Doc("ida_hwm", "Hazard reader",
        "Nearest USGS-surveyed mark: Carroll St. and Nevins St. (1417 m away).", False),
    Doc("microtopo", "Hazard reader",
        "Elevation 16.89 m; HAND 16.76 m above nearest drainage; TWI 7.1.", False),
    Doc("experimental_layer", "Hazard reader",
        "Experimental: 0 water polygons within 500 m of this address, nearest 5870.5 m away.", True),
]


def claim(text, doc_ids, numbers=(), section="Hazard reader"):
    return {"section": section, "text": text, "doc_ids": list(doc_ids), "numbers": list(numbers)}


def test_exact_numbers_pass():
    kept, dropped = verify([claim("22 flood complaints were filed within 200 m in 5 years.",
                                  ["nyc311"], ["22", "200", "5"], "Live observer")], DOCS)
    assert len(kept) == 1 and not dropped


def test_rounding_and_unit_conversion_pass():
    kept, dropped = verify([
        claim("The nearest Ida high-water mark is about 1.4 km away.", ["ida_hwm"], ["1.4"]),
        claim("The ground sits about 55 ft above sea level.", ["microtopo"], ["55"]),
        claim("The nearest mapped water is roughly 5,870 m away.", ["experimental_layer"], ["5,870"]),
    ], DOCS)
    assert len(kept) == 3, dropped


def test_invented_number_is_dropped():
    kept, dropped = verify([claim("34 flood complaints were filed nearby.", ["nyc311"], ["34"],
                                  "Live observer")], DOCS)
    assert not kept
    assert "34" in dropped[0]["reason"]


def test_identifiers_and_dates_in_numbers_field_are_tokenized():
    docs = [Doc("fema_nfhl", "Hazard reader",
                "Zone X, per NFHL FIRM panel 3604970203F, effective 2007, read 2026-09-26T18:50.", False)]
    kept, dropped = verify([claim("Zone X, FIRM panel 3604970203F, effective 2007.", ["fema_nfhl"],
                                  ["3604970203F", "2007", "2026-09-26T18:50"])], docs)
    assert kept and not dropped


def test_number_only_in_text_is_still_checked():
    # The model left `numbers` empty but the sentence states a number.
    kept, dropped = verify([claim("Elevation is 21 m.", ["microtopo"], [])], DOCS)
    assert not kept and "21" in dropped[0]["reason"]


def test_number_must_come_from_a_cited_doc():
    # 22 is real, but it is in nyc311, not in the cited microtopo doc.
    kept, dropped = verify([claim("22 complaints were filed.", ["microtopo"], ["22"])], DOCS)
    assert not kept


def test_unknown_doc_id_is_dropped():
    kept, dropped = verify([claim("Sandy flooded this block.", ["sandy_inundation"])], DOCS)
    assert not kept and "not provided" in dropped[0]["reason"]


def test_missing_citation_and_placeholder_are_dropped():
    kept, dropped = verify([
        claim("Flooding is common here.", []),
        claim("Elevation is <value> m.", ["microtopo"]),
    ], DOCS)
    assert not kept
    assert dropped[0]["reason"] == "no citation"
    assert "placeholder" in dropped[1]["reason"]


def test_unknown_section_is_dropped():
    kept, dropped = verify([claim("TWI is 7.1.", ["microtopo"], ["7.1"], section="Status")], DOCS)
    assert not kept and "section" in dropped[0]["reason"]


def test_citation_brackets_in_text_are_stripped_before_checking():
    kept, _ = verify([claim("TWI is 7.1 [microtopo].", ["microtopo"], ["7.1"])], DOCS)
    assert kept[0]["text"] == "TWI is 7.1."


def test_number_supported_tolerance_is_bounded():
    assert number_supported("16.9", [16.89])
    assert not number_supported("16.95", [16.89])
    assert not number_supported("17.5", [16.89])


def test_render_labels_experimental_and_fills_empty_sections():
    kept = [claim("No water polygons were detected within 500 m.", ["experimental_layer"], ["500"])]
    text = _render(kept, DOCS, ["Hazard reader", "Live observer"])
    assert "Experimental: No water polygons" in text
    assert "[experimental_layer]." in text
    # Refactor 8: a section the model left empty shows its sources' own cited
    # sentences, never "no grounded evidence" over a section that has evidence.
    live = [d for d in DOCS if d.section == "Live observer"]
    assert "No grounded evidence" not in text
    assert all(f"[{d.doc_id}]" in text.split("**Live observer.**\n")[1] for d in live)


def test_schema_restricts_doc_ids_to_the_documents_passed():
    schema = claims_schema(["ida_hwm", "nyc311"], ["Hazard reader"])
    item = schema["properties"]["claims"]["items"]["properties"]
    assert item["doc_ids"]["items"]["enum"] == ["ida_hwm", "nyc311"]
    assert item["section"]["enum"] == ["Hazard reader"]
