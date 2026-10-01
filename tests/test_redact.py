"""311 free text is redacted of emails and phone numbers at fetch time and
never written to the HTTP cache (refactor 6). Synthetic examples only."""

import pytest

from riprap.core.redact import EMAIL, PHONE, redact, redact_text


@pytest.mark.parametrize("text,expected", [
    ("Case closed. Contact jane.doe+311@example.org for details.", f"Case closed. Contact {EMAIL} for details."),
    ("Called resident at (617) 555-0142, no answer", f"Called resident at {PHONE}, no answer"),
    ("cb 617-555-0142 or 617.555.0142", f"cb {PHONE} or {PHONE}"),
    ("call +1 415 555 0199 after 5", f"call {PHONE} after 5"),
    ("resident left number 4155550199 on voicemail", f"resident left number {PHONE} on voicemail"),
])
def test_emails_and_phones_are_removed(text, expected):
    assert redact_text(text) == expected


@pytest.mark.parametrize("text", [
    "101005413921",               # a Boston case id, one token
    "4155550199",                 # a bare id-like token with no surrounding text
    "SR24-01234567",
    "Catch basin cleaned on 2025-06-01 at 10:30",
    "Water main break at 1200 Commonwealth Ave, 3 ft of water",
    "311 service request 24-00123456 closed",
    "point at [-73.9325034109, 40.8134529068] in the polygon",
    "total 4155550199.5 gallons",
])
def test_ids_dates_and_addresses_are_kept(text):
    assert redact_text(text) == text


def test_nested_records_are_redacted():
    rows = {"issues": [{"id": 7, "summary": "Flooded street", "description": "email a@b.co or 212-555-0100",
                        "reporter": {"name": "x", "note": "c@d.io"}}]}
    out = redact(rows)
    assert out["issues"][0]["description"] == f"email {EMAIL} or {PHONE}"
    assert out["issues"][0]["reporter"]["note"] == EMAIL and out["issues"][0]["id"] == 7


def test_personal_fetch_bypasses_the_cache_and_redacts(monkeypatch):
    from riprap.core import http
    from riprap.core.pebbles import _http

    calls = {}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"status_notes": "Spoke with owner, 415-555-0123, jo@example.com"}]

    def fake_get(url, **kw):
        calls.update(kw)
        return R()

    monkeypatch.setattr(http, "get", fake_get)
    out = _http.fetch_url_json("https://example.test/311.json", personal=True)
    assert calls["store"] is False
    assert out == [{"status_notes": f"Spoke with owner, {PHONE}, {EMAIL}"}]


@pytest.mark.parametrize("module", ["riprap.core.pebbles.adapters.socrata_records", "app.context.seeclickfix"])
def test_every_311_adapter_fetches_as_personal(module):
    import importlib
    import inspect

    src = inspect.getsource(importlib.import_module(module))
    assert "personal=True" in src
