"""Real production case: neighborhood.py's EXTRA_SYSTEM_PROMPT shows the
desired output shape wrapped in a ``` fence — the model sometimes imitates
the fence itself, most often as a stray trailing ``` with no matching open,
into an otherwise clean, fully-cited briefing. Briefing prose never
legitimately contains a code block, so stripping any bare fence line is
always correct."""
from __future__ import annotations

from app.reconcile import _strip_code_fences


def test_strips_stray_trailing_fence():
    text = "**Status.**\nSomething happened [doc_id].\n\n```"
    assert _strip_code_fences(text) == "**Status.**\nSomething happened [doc_id]."


def test_strips_stray_leading_fence():
    text = "```\n**Status.**\nSomething happened [doc_id]."
    assert _strip_code_fences(text) == "**Status.**\nSomething happened [doc_id]."


def test_strips_language_tagged_fence():
    text = "```markdown\n**Status.**\nSomething happened [doc_id]."
    assert _strip_code_fences(text) == "**Status.**\nSomething happened [doc_id]."


def test_leaves_clean_text_alone():
    text = "**Status.**\nSomething happened [doc_id]."
    assert _strip_code_fences(text) == text


def test_leaves_backticks_that_are_not_a_bare_fence_line():
    """A backtick sequence that isn't alone on its own line (e.g. part
    of prose quoting a raw value) should not be touched — only a line
    that is *only* a fence marker is stripped."""
    text = "The field is labeled `dep_extreme_2080` in the source data [doc_id]."
    assert _strip_code_fences(text) == text
