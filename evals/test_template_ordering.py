"""Regression tests: HTE template safety messages must precede any fallible plot call.

`templates/python/hte.md` and `templates/r/hte.md` ship two safety messages (the
variable-importance caveat, the policy-tree deployment disclaimer) as literal code the
skill copies verbatim -- `skills/causal-hte/SKILL.md` calls them "part of the code
pattern, not optional narration". If a plotting call sits between the anchor computation
and the message, a plot crash (feature-name/dimension mismatches are a known failure
mode) means the message never prints -- the exact "sometimes missing" defect this pattern
exists to prevent, just triggered by a crash instead of a logic gap. This locks the fix:
each message immediately follows its anchor call and precedes every plot call in the
same section.

Run: python3 -m pytest evals/test_template_ordering.py   (from repo root)
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PYTHON_HTE = _REPO_ROOT / "templates" / "python" / "hte.md"
_R_HTE = _REPO_ROOT / "templates" / "r" / "hte.md"


def _code_block_after(text: str, heading: str) -> str:
    """The body of the first fenced code block that follows `heading` in `text`."""
    heading_idx = text.index(heading)
    fence_start = text.index("```", heading_idx)
    body_start = text.index("\n", fence_start) + 1
    fence_end = text.index("```", body_start)
    return text[body_start:fence_end]


def _index_of(code: str, needle: str) -> int:
    idx = code.find(needle)
    assert idx != -1, f"expected to find {needle!r} in:\n{code}"
    return idx


def _assert_immediately_follows(code: str, anchor: str, message: str) -> None:
    """The message's first line must be the next non-blank, non-comment line after the
    anchor's line -- not merely somewhere later. A later-but-not-adjacent placement (e.g.
    an intervening `names(x) <- y` assignment) is itself a fallible statement that could
    sit between the anchor and the safety message, recreating the crash-before-message
    bug with a different culprit than a plot call.
    """
    anchor_idx = _index_of(code, anchor)
    anchor_line_end = code.find("\n", anchor_idx)
    message_idx = _index_of(code, message)
    message_line_start = code.rfind("\n", 0, message_idx) + 1
    between = code[anchor_line_end:message_line_start]
    offending = [ln for ln in between.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    assert not offending, (
        f"non-comment code between {anchor!r} and {message!r}: {offending}")


def test_python_variable_importance_caveat_immediately_follows_extraction():
    code = _code_block_after(_PYTHON_HTE.read_text(), "### Variable importance:")
    _assert_immediately_follows(code, "feature_importances_", "Important caveat")
    caveat = _index_of(code, "Important caveat")
    plot = _index_of(code, "plt.barh")
    assert caveat < plot, (caveat, plot)


def test_python_policy_tree_disclaimer_immediately_follows_prediction():
    code = _code_block_after(_PYTHON_HTE.read_text(), "### Step 4b: Policy tree (opt-in)")
    _assert_immediately_follows(code, "pt.predict(", "exploratory targeting rule")
    disclaimer = _index_of(code, "exploratory targeting rule")
    summary = _index_of(code, "Policy tree treats")
    plot = _index_of(code, "plot_tree(")
    assert disclaimer < summary < plot, (disclaimer, summary, plot)


def test_r_variable_importance_caveat_immediately_follows_extraction():
    code = _code_block_after(_R_HTE.read_text(), "### Variable importance:")
    _assert_immediately_follows(code, "variable_importance(", "Important caveat")
    caveat = _index_of(code, "Important caveat")
    plot = _index_of(code, "barplot(")
    assert caveat < plot, (caveat, plot)


def test_r_policy_tree_disclaimer_immediately_follows_prediction():
    code = _code_block_after(_R_HTE.read_text(), "### Step 4b: Policy tree (opt-in)")
    _assert_immediately_follows(code, "predict(pt, X)", "exploratory targeting rule")
    disclaimer = _index_of(code, "exploratory targeting rule")
    summary = _index_of(code, "Policy tree treats")
    plot = _index_of(code, "plot(pt)")
    assert disclaimer < summary < plot, (disclaimer, summary, plot)
