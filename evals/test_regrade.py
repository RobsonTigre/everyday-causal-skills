"""Offline tests for the judge gate-reproducibility screen. No model calls.

The judge subprocess is stubbed throughout, mirroring `evals/test_scorer.py`.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import regrade  # noqa: E402
import scorer  # noqa: E402


# --- fixtures -------------------------------------------------------------

_CASE = {"layer": 4, "name": "t", "rubric": {
    "pedagogy": [{"id": "explains_why", "question": "Does it explain why?",
                  "required": True},
                 {"id": "is_tailored", "question": "Is it tailored?",
                  "required": True}],
    "safety": [{"id": "warns", "question": "Does it warn?", "required": False}]}}


def _slot_file(d: Path, case: str, slot: int, response: str) -> Path:
    p = d / f"case-{case}-slot{slot}.json"
    p.write_text(json.dumps({
        "runs": 1, "backend": "cli",
        "cases": [{"name": case, "layer": 4, "aggregate": {}, "verdict": "FAIL",
                   "invalid_reasons": [],
                   "run_records": [{"run": 1, "response": response,
                                    "scores": {}, "tokens": {}}]}],
    }))
    return p


def _corpus(d: Path, cases=("alpha",), slots=5, response="a response"):
    for case in cases:
        for slot in range(slots):
            _slot_file(d, case, slot, f"{response} {case} {slot}")
    return d


def _with_fake_judge(answer_sequence, fn):
    """Serve a canned boolean list per judge call."""
    calls = {"n": 0}
    real = scorer._call_judge

    def fake(prompt, num_questions, config=None, debug=False, label=""):
        answers = answer_sequence[calls["n"] % len(answer_sequence)]
        calls["n"] += 1
        return answers[:num_questions]

    scorer._call_judge = fake
    try:
        return fn(), calls
    finally:
        scorer._call_judge = real


# --- cell identity --------------------------------------------------------

def test_cells_are_keyed_by_case_and_question_because_ids_collide():
    """`provide_complete_runnable_code` is declared by both did_pedagogy_clean and
    experiments_pedagogy_messy — 229 distinct ids across 230 questions. Keying by
    bare id merges two different criteria into one row of evidence."""
    assert regrade.cell_key("did_pedagogy_clean", 0, "shared_id") != \
        regrade.cell_key("experiments_pedagogy_messy", 0, "shared_id")
    assert regrade.criterion_key("did_pedagogy_clean", "shared_id") != \
        regrade.criterion_key("experiments_pedagogy_messy", "shared_id")


# --- fail closed ----------------------------------------------------------

def test_a_short_corpus_is_refused_not_quietly_measured():
    """An absent slot file must stop the run. Measuring what happens to be on disk
    turns a missing measurement into a smaller, quieter statistic — which is the
    denominator failure this whole arc exists to prevent."""
    with tempfile.TemporaryDirectory() as t:
        d = _corpus(Path(t))
        (d / "case-alpha-slot3.json").unlink()
        try:
            regrade.validate_corpus(d, {"alpha"}, slots=5)
        except ValueError as e:
            assert "alpha" in str(e) and "3" in str(e), e
        else:
            raise AssertionError("a missing slot must be refused")


def test_an_empty_response_is_refused():
    """A stored slot holding an empty string is not a response; grading it would
    produce a confident answer about nothing."""
    with tempfile.TemporaryDirectory() as t:
        d = _corpus(Path(t))
        _slot_file(d, "alpha", 2, "   ")
        try:
            regrade.validate_corpus(d, {"alpha"}, slots=5)
        except ValueError as e:
            assert "empty" in str(e).lower(), e
        else:
            raise AssertionError("an empty stored response must be refused")


def test_a_complete_corpus_validates_clean():
    """The discriminating half — the check must not refuse everything."""
    with tempfile.TemporaryDirectory() as t:
        d = _corpus(Path(t), cases=("alpha", "beta"))
        assert regrade.validate_corpus(d, {"alpha", "beta"}, slots=5) == 10


# --- gate reconstruction --------------------------------------------------

def test_a_round_reconstructs_the_gate_through_the_production_rule():
    """One round is one judgment of each of a criterion's five stored responses,
    scored by the SAME 4-of-5 rule the release uses. A second copy of that rule
    here would let the screen and the gate disagree about what failing means."""
    answers = {0: True, 1: True, 2: True, 3: True, 4: False}     # 4 of 5
    assert regrade.round_gate_result(answers, floor=0.8) is True
    answers[3] = False                                            # 3 of 5
    assert regrade.round_gate_result(answers, floor=0.8) is False


def test_a_round_missing_an_answer_is_not_scored_over_the_runs_that_have_one():
    """Package F's never-shrink-the-denominator rule. Four answers out of five
    valid responses must not read as 4/4."""
    assert regrade.round_gate_result({0: True, 1: True, 2: True, 3: True},
                                     floor=0.8) is None


# --- labels ---------------------------------------------------------------

def test_a_criterion_whose_gate_result_moves_across_rounds_is_gate_sensitive():
    assert regrade.label([True, True, False, True, True]) == "OBSERVED_GATE_SENSITIVE"
    assert regrade.label([False, False, True, False, False]) == "OBSERVED_GATE_SENSITIVE"


def test_a_criterion_identical_in_every_round_rules_nothing_out():
    """The label has to carry its own limit. Five identical rounds do not exclude
    variance below the detection limit, a stable judge error, or an invalid case —
    so the name says only what was observed, at the K it was observed at."""
    assert regrade.label([False] * 5) == "NO_GATE_CHANGE_OBSERVED_K5"
    assert regrade.label([True] * 5) == "NO_GATE_CHANGE_OBSERVED_K5"


def test_an_incomplete_round_makes_the_criterion_unmeasured():
    """No sound or sensitive verdict is legal until the expected matrix is whole."""
    assert regrade.label([True, True, None, True, True]) == "UNMEASURED"


# --- grading path ---------------------------------------------------------

def test_regrade_once_keys_by_id_through_one_judge_call_per_response():
    """`_judge_l4` grades a whole case rubric in one call, which is why 70 stored
    responses cost 70 calls per round rather than 97."""
    out, calls = _with_fake_judge([[True, False, True]],
                                  lambda: regrade.regrade_once("resp", _CASE, {}))
    assert calls["n"] == 1, calls
    assert out == {"explains_why": True, "is_tailored": False, "warns": True}, out


def test_the_judge_receives_the_release_config_not_its_own_defaults():
    """Hashing a config does not prove it was passed. The two happen to agree today
    — config.release.yaml's judge block is byte-for-byte the scorer's fallback — so
    a silent divergence would be invisible until one of them moved."""
    seen = {}
    real = scorer._judge_l4

    def spy(response, case, config=None, debug=False):
        seen["config"] = config
        return real(response, case, config, debug)

    scorer._judge_l4 = spy
    try:
        cfg = {"judge": {"model": "claude-sonnet-4-20250514", "timeout": 120}}
        _with_fake_judge([[True, True, True]],
                         lambda: regrade.regrade_once("resp", _CASE, cfg))
    finally:
        scorer._judge_l4 = real
    assert seen["config"] == cfg, seen
