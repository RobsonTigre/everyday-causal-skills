"""Tests for the repository governance audit.

These exercise the pure parsing and classification functions against fixed
input. Nothing here shells out to git, so the suite stays deterministic
regardless of what the working tree happens to look like when it runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repo_doctor import (  # noqa: E402
    added_history_rows,
    nonstandard_refs,
    parse_refs,
)

FOR_EACH_REF = """\
refs/heads/main 40cb9c1aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
refs/remotes/origin/main 373d587bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
refs/rescue/history-2026-04-06 4a963aeccccccccccccccccccccccccccccccccc
refs/tags/v0.5.0 21301a8ddddddddddddddddddddddddddddddddd
"""


class TestParseRefs:
    def test_splits_name_and_sha(self):
        refs = parse_refs(FOR_EACH_REF)
        assert len(refs) == 4
        assert refs[0] == (
            "refs/heads/main",
            "40cb9c1aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

    def test_ignores_blank_and_malformed_lines(self):
        assert parse_refs("\n\nnot-a-ref-line\n") == []

    def test_empty_input(self):
        assert parse_refs("") == []


class TestNonstandardRefs:
    def test_flags_the_rescue_namespace(self):
        """The exact ref that hid for six weeks must be caught."""
        flagged = nonstandard_refs(parse_refs(FOR_EACH_REF))
        assert [name for name, _ in flagged] == ["refs/rescue/history-2026-04-06"]

    def test_accepts_heads_tags_and_remotes(self):
        standard = parse_refs(
            "refs/heads/main abc1234\n"
            "refs/tags/v1.0.0 def5678\n"
            "refs/remotes/origin/main 9abcdef\n"
        )
        assert nonstandard_refs(standard) == []

    def test_flags_any_invented_namespace(self):
        for ns in ("refs/wip/thing", "refs/backup/x", "refs/notes/commits"):
            assert nonstandard_refs([(ns, "abc1234")]) == [(ns, "abc1234")]

    def test_does_not_match_on_substring(self):
        """A branch merely named 'rescue' is standard and must not be flagged."""
        assert nonstandard_refs([("refs/heads/rescue", "abc1234")]) == []


class TestAddedHistoryRows:
    DIFF = """\
diff --git a/evals/results/HISTORY.md b/evals/results/HISTORY.md
--- a/evals/results/HISTORY.md
+++ b/evals/results/HISTORY.md
@@ -23,3 +23,5 @@
 | 2026-04-05 23:28 | claude-sonnet-4-20250514 | x |
+| 2026-04-06 08:52 | claude-sonnet-4-20250514 | x |
+| 2026-04-06 08:53 | claude-sonnet-4-20250514 | x |
-| 2026-04-05 22:00 | claude-sonnet-4-20250514 | x |
"""

    def test_counts_only_added_rows(self):
        rows = added_history_rows(self.DIFF)
        assert len(rows) == 2
        assert all(r.startswith("| 2026-04-06") for r in rows)

    def test_ignores_removed_and_context_rows(self):
        assert "2026-04-05" not in "".join(added_history_rows(self.DIFF))

    def test_ignores_diff_header_plus_lines(self):
        """'+++ b/path' starts with '+' but is not a ledger row."""
        assert added_history_rows("+++ b/evals/results/HISTORY.md\n") == []

    def test_ignores_added_prose(self):
        assert added_history_rows("+Some added paragraph of text\n") == []

    def test_clean_diff_yields_nothing(self):
        assert added_history_rows("") == []
