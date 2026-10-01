"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def _model_path_unless_a_test_says_otherwise(monkeypatch):
    """Tests of the model path script the model's reply, so they run with
    the rules-first switch off whatever RIPRAP_RULES_FIRST says. A test of
    rules-first sets the switch itself."""
    from riprap.core.burr import synthesis

    monkeypatch.setattr(synthesis, "RULES_FIRST", False)
