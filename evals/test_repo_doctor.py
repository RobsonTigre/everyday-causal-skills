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
    stale_results,
    stale_results_note,
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


class TestStaleResults:
    """T1.4 — a stored sweep is evidence about the commit that produced it, nothing else.

    On 2026-08-04 the 2026-08-03 L4 sweep (measured at 3bf5738) was mined as current
    evidence. By then 24 of its 37 case files, 7 skill files and both scorer.py and
    runner.py had changed. Nothing in the repo said so.
    """

    HEAD = "935e525aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    OLD = "3bf5738bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    def test_a_sweep_measured_at_head_is_current(self):
        assert stale_results([("sweep-x", self.HEAD)], self.HEAD) == []

    def test_a_sweep_measured_at_an_older_commit_is_stale(self):
        stale = stale_results([("sweep-2026-08-03", self.OLD)], self.HEAD)
        assert len(stale) == 1
        assert stale[0][0] == "sweep-2026-08-03"

    def test_it_reports_both_commits_so_the_gap_is_checkable(self):
        """Naming only 'stale' makes a reader take it on trust. Name both SHAs."""
        _, detail = stale_results([("sweep-2026-08-03", self.OLD)], self.HEAD)[0]
        assert self.OLD[:7] in detail, detail
        assert self.HEAD[:7] in detail, detail

    def test_a_sweep_with_no_recorded_commit_is_stale(self):
        """A pre-fingerprint ledger cannot prove it describes anything. Not current."""
        assert stale_results([("sweep-ancient", "")], self.HEAD) != []

    def test_it_reports_every_stale_sweep_not_just_the_first(self):
        stale = stale_results(
            [("a", self.OLD), ("b", self.HEAD), ("c", self.OLD)], self.HEAD
        )
        assert [name for name, _ in stale] == ["a", "c"]

    def test_no_results_on_disk_is_not_a_finding(self):
        assert stale_results([], self.HEAD) == []


class TestStaleResultsNote:
    """Every stored sweep predates HEAD the moment anything is committed, so a note
    per sweep is 21 lines of noise that buries the other findings. One line, or none.
    """

    STALE = [("a", "detail a"), ("b", "detail b")]

    def test_nothing_stored_produces_no_note(self):
        assert stale_results_note([], total=0) == []

    def test_everything_current_produces_no_note(self):
        assert stale_results_note([], total=3) == []

    def test_it_emits_exactly_one_line(self):
        assert len(stale_results_note(self.STALE, total=5)) == 1

    def test_the_line_carries_the_count_and_the_total(self):
        line = stale_results_note(self.STALE, total=5)[0]
        assert "2" in line and "5" in line, line

    def test_it_names_the_newest_stale_result_so_there_is_a_thread_to_pull(self):
        """The most recent stale sweep is the one someone is about to cite."""
        line = stale_results_note(self.STALE, total=5)[0]
        assert "b" in line, line
