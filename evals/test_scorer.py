"""Fast, dependency-free unit tests for eval scorer harness changes.
Run: python3 evals/test_scorer.py   (from repo root)
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scorer  # noqa: E402
from scorer import (  # noqa: E402
    JudgeError,
    _execute_code,
    _judge_l1,
    _judge_l2,
    _judge_l4,
    _select_l3_program,
    _score_layer3,
    score_l5,
    score_response,
)


def _case(language="python"):
    return {"layer": 3, "language": language, "name": "t"}


def test_must_not_include_prose_does_not_trip():
    resp = "You could use CallawaySantAnna here.\n```python\nimport pandas as pd\nprint('hi')\n```"
    out = _score_layer3(resp, {"must_not_include": ["CallawaySantAnna"]}, _case())
    assert out["guard_passed"] is True, out


def test_must_not_include_code_trips():
    resp = "```python\nfrom diff_diff import CallawaySantAnna\n```"
    out = _score_layer3(resp, {"must_not_include": ["CallawaySantAnna"]}, _case())
    assert out["guard_passed"] is False, out


def test_must_include_code_present_passes():
    resp = "```python\nfrom diff_diff import CallawaySantAnna\ncs = CallawaySantAnna()\n```"
    out = _score_layer3(resp, {"must_include_code": ["CallawaySantAnna"]}, _case())
    assert out["guard_passed"] is True, out


def test_must_include_code_absent_fails():
    resp = "```python\nfrom linearmodels.panel import PanelOLS\n```"
    out = _score_layer3(resp, {"must_include_code": ["CallawaySantAnna"]}, _case())
    assert out["guard_passed"] is False, out


def test_no_guard_fields_defaults_true():
    resp = "We discuss parallel trends.\n```python\nprint('hi')\n```"
    out = _score_layer3(resp, {"must_include": ["parallel_trends"]}, _case())
    assert out["guard_passed"] is None
    assert out["guard_applicable"] is False
    assert out["diagnostic_coverage"] == 1.0  # backward-compat: prose 'parallel trends' matches


def test_l3_selects_marked_program_after_preflight():
    response = (
        "```python\nimport os\nprint('preflight')\n```\n"
        "```python\n# EVAL_EXECUTABLE\nprint('ESTIMATE:2.0')\n```")
    selected = _select_l3_program(response, "python")
    assert selected["selection"] == "sentinel", selected
    assert selected["program"] == "# EVAL_EXECUTABLE\nprint('ESTIMATE:2.0')\n"


def test_l3_sentinel_must_be_exact_first_nonblank_program_line():
    accepted = _select_l3_program(
        "```python\n\n# EVAL_EXECUTABLE\nprint(1)\n```", "python")
    assert accepted["selection"] == "sentinel", accepted
    assert accepted["program"] == "\n# EVAL_EXECUTABLE\nprint(1)\n"

    for body in (
        " # EVAL_EXECUTABLE\nprint(1)\n",
        "# EVAL_EXECUTABLE  \nprint(1)\n",
        "# eval_executable\nprint(1)\n",
        "# setup\n# EVAL_EXECUTABLE\nprint(1)\n",
    ):
        selected = _select_l3_program(f"```python\n{body}```", "python")
        assert selected["selection"] == "single_fallback", (body, selected)


def test_l3_noncanonical_sentinel_does_not_disambiguate_candidates():
    response = (
        "```python\n # EVAL_EXECUTABLE\nprint(1)\n```\n"
        "```python\nprint(2)\n```")
    selected = _select_l3_program(response, "python")
    assert selected["selection"] == "ambiguous", selected
    assert selected["program"] is None


def test_l3_mixed_languages_only_considers_declared_language():
    response = (
        "```r\n# EVAL_EXECUTABLE\nstop('illustration only')\n```\n"
        "```python\nprint('ESTIMATE:2.0')\n```")
    selected = _select_l3_program(response, "python")
    assert selected["selection"] == "single_fallback", selected
    assert "stop(" not in selected["program"]


def test_l3_multiple_unmarked_candidates_are_ambiguous():
    response = "```python\nprint(1)\n```\n```python\nprint(2)\n```"
    out = _score_layer3(response, {"code_runs": True}, _case())
    assert out["has_code"] is False, out
    assert out["program_selection"] == "ambiguous", out
    assert out["runs_without_error"] is False, out


def test_l3_guards_only_selected_program_bytes():
    response = (
        "```python\nCallawaySantAnna()\n```\n"
        "```python\n# EVAL_EXECUTABLE\nprint('ok')\n```")
    out = _score_layer3(
        response, {"code_runs": True, "must_not_include": ["CallawaySantAnna"]},
        _case())
    assert out["guard_applicable"] is True, out
    assert out["guard_passed"] is True, out


def test_exercise_requires_explicit_estimate_output():
    response = "```python\n# EVAL_EXECUTABLE\nprint('finished')\n```"
    case = {**_case(), "execution_mode": "exercise", "required_output": "estimate"}
    out = _score_layer3(response, {}, case)
    assert out["runs_without_error"] is False, out
    assert out["required_output_ok"] is False, out
    assert "ESTIMATE" in out["execution_error"], out


def test_requires_missing_package_errors():
    out = _execute_code("print('ESTIMATE:1.0')", language="python",
                        requires=["no_such_module_xyz_123"])
    assert out["ran"] is False
    assert "not importable" in (out["error"] or "")


def test_requires_present_package_runs():
    out = _execute_code("print('ESTIMATE:2.0')", language="python", requires=["os"])
    assert out["ran"] is True
    assert out["estimate"] == 2.0


def test_crash_after_printing_estimate_is_not_a_clean_run():
    # A script that prints an estimate and then dies is not a successful run. Counting
    # it as one — and discarding its stderr — let broken analyses register as green.
    out = _execute_code(
        "print('ESTIMATE:3.0')\nraise SystemExit(1)", language="python")
    assert out["ran"] is False, out
    assert out["error"], "stderr must be retained on any nonzero exit"


def test_stderr_retained_even_when_estimate_present():
    out = _execute_code(
        "import sys\nprint('ESTIMATE:3.0')\n"
        "sys.stderr.write('BOOM_MARKER\\n')\nsys.exit(2)", language="python")
    assert out["ran"] is False, out
    assert "BOOM_MARKER" in (out["error"] or ""), out


def test_generated_code_does_not_write_into_the_repo():
    # Generated plotting code calls savefig() with bare filenames. With no cwd set, the
    # subprocess inherited the repo root and littered it with PNGs and CSVs.
    marker = "eval_cwd_probe_marker.txt"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(repo_root, marker)
    assert not os.path.exists(target), "stale probe file from an earlier run"
    out = _execute_code(
        f"open({marker!r}, 'w').write('x')\nprint('ESTIMATE:1.0')", language="python")
    try:
        assert out["ran"] is True, out
        assert not os.path.exists(target), (
            f"generated code wrote {marker} into the repo root; it must run in a temp cwd")
    finally:
        if os.path.exists(target):
            os.remove(target)


def test_relative_dataset_path_still_loads_from_temp_cwd():
    # Cases declare `dataset: evals/data/...` relative to the repo root, so running in a
    # temp cwd must resolve the path first or every dataset case breaks.
    out = _execute_code(
        "print(f'ESTIMATE:{len(df.columns)}.0')",
        language="python", dataset_path="evals/data/iv_strong.csv")
    assert out["ran"] is True, out
    assert out["estimate"] == 4.0, out  # id, draft_number, served, earnings


# --- must_include alternates ---

def test_must_include_accepts_a_plain_string():
    out = _score_layer3(
        "We tested parallel trends before estimating.",
        {"must_include": ["parallel_trends"], "code_runs": False},
        {"layer": 3, "language": "python", "name": "t"})
    assert out["must_include_results"] == {"parallel_trends": True}, out


def test_must_include_alternates_match_any_phrasing():
    # diagnostic_coverage scored word choice, not substance: did_basic_2x2 reported a
    # 95% CI six ways and still scored 0 because it never wrote "confidence interval".
    case = {"layer": 3, "language": "python", "name": "t"}
    expected = {"must_include": [["confidence_interval", "95% CI", "confidence bound"]],
                "code_runs": False}

    for phrasing in ("we report a 95% CI", "the confidence interval is wide",
                     "a confidence bound of 0.3"):
        out = _score_layer3(phrasing, expected, case)
        assert out["must_include_results"] == {"confidence_interval": True}, phrasing

    miss = _score_layer3("no such notion here", expected, case)
    assert miss["must_include_results"] == {"confidence_interval": False}, miss


def test_must_include_alternates_key_on_the_first_element():
    # The canonical key must be stable regardless of which alternate matched, so
    # results stay comparable across runs and across ledger entries.
    out = _score_layer3(
        "reported a 95% CI",
        {"must_include": [["confidence_interval", "95% CI"]], "code_runs": False},
        {"layer": 3, "language": "python", "name": "t"})
    assert list(out["must_include_results"]) == ["confidence_interval"], out


def test_diagnostic_coverage_counts_alternates_as_covered():
    out = _score_layer3(
        "clustered SEs and a 95% CI",
        {"must_include": [["confidence_interval", "95% CI"], ["clustered", "cluster-robust"]],
         "code_runs": False},
        {"layer": 3, "language": "python", "name": "t"})
    assert out["diagnostic_coverage"] == 1.0, out


# --- L3 expected.values (named KEY:value outputs) ---

def test_execute_code_collects_named_values():
    out = _execute_code("print('ROI:2.5')\nprint('BREAKEVEN_EFFECT:0.6667')\nprint('noise: 1')",
                        language="python")
    assert out["values"] == {"ROI": 2.5, "BREAKEVEN_EFFECT": 0.6667}, out


def _values_resp(roi="2.5", be="0.6667"):
    return (f"```python\nprint('ROI:{roi}')\nprint('BREAKEVEN_EFFECT:{be}')\n```")


def test_values_all_match_sets_estimation_accurate():
    exp = {"code_runs": True, "values": {"ROI": 2.5, "BREAKEVEN_EFFECT": {"value": 0.667, "tol": 0.001}}}
    out = _score_layer3(_values_resp(), exp, _case())
    assert out["estimation_accurate"] is True, out
    assert out["values_results"] == {"ROI": True, "BREAKEVEN_EFFECT": True}, out


def test_values_mismatch_fails():
    exp = {"code_runs": True, "values": {"ROI": 9.9}}
    out = _score_layer3(_values_resp(), exp, _case())
    assert out["estimation_accurate"] is False, out
    assert out["values_results"] == {"ROI": False}, out


def test_values_missing_key_fails():
    exp = {"code_runs": True, "values": {"NO_SUCH_KEY": 1.0}}
    out = _score_layer3(_values_resp(), exp, _case())
    assert out["estimation_accurate"] is False, out


def test_values_default_tolerance_is_tight():
    # default values_tolerance = 1e-6: a 1e-3 miss must fail without per-key tol
    exp = {"code_runs": True, "values": {"ROI": 2.501}}
    out = _score_layer3(_values_resp(), exp, _case())
    assert out["estimation_accurate"] is False, out
    exp2 = {"code_runs": True, "values": {"ROI": 2.501}, "values_tolerance": 0.01}
    out2 = _score_layer3(_values_resp(), exp2, _case())
    assert out2["estimation_accurate"] is True, out2


def test_true_effect_path_untouched_by_values_machinery():
    # Classic path: true_effect + ESTIMATE line — values dict absent.
    resp = "```python\nprint('ESTIMATE:5.0')\n```"
    exp = {"true_effect": 5.0, "tolerance": 0.5, "code_runs": True}
    out = _score_layer3(resp, exp, _case())
    assert out["estimation_accurate"] is True, out
    assert out["values_results"] == {}, out


# --- L2 rubric support (judge monkeypatched; no LLM calls) ---

def _with_fake_judge(answers, fn):
    """Run fn() with scorer._call_judge replaced; capture the question count."""
    seen = {}
    real = scorer._call_judge

    def fake(prompt, num_questions, config=None, debug=False, label=""):
        seen["num_questions"] = num_questions
        seen["prompt"] = prompt
        return answers[:num_questions]

    scorer._call_judge = fake
    try:
        return fn(), seen
    finally:
        scorer._call_judge = real


def test_l2_no_rubric_is_unchanged():
    exp = {"must_flag": ["overlap"], "severity": "fatal"}
    out, seen = _with_fake_judge([True, True],
                                 lambda: _judge_l2("resp", exp))
    assert seen["num_questions"] == 2, seen  # 1 flag + 1 severity, exactly as before
    assert "rubric_coverage" not in out, out
    assert out["violation_detected"] is True


def _rubric(*pairs):
    """Package F object-form rubric: [{id, question, required}, ...]."""
    return [{"id": i, "question": q, "required": r} for i, q, r in pairs]


def test_l2_rubric_appended_after_flags_and_severity():
    exp = {"must_flag": ["overlap"], "severity": "fatal"}
    rubric = _rubric(("first_q", "Q1?", True), ("second_q", "Q2?", True))
    out, seen = _with_fake_judge([True, True, True, False],
                                 lambda: _judge_l2("resp", exp, rubric=rubric))
    assert seen["num_questions"] == 4, seen
    assert out["violation_detected"] is True   # index 0 still the flag answer
    assert out["flag_answers"] == {"overlap": True}, out
    assert out["rubric_coverage"] == 0.5, out  # 1 of 2 rubric questions passed
    # The point of Package F: which criterion passed, not just how many.
    assert out["rubric_answers"] == {"first_q": True, "second_q": False}, out


def test_l2_clean_case_with_rubric():
    exp = {}  # no must_flag -> clean branch (question 0 = false-alarm check)
    rubric = _rubric(("q_one", "Q1?", True), ("q_two", "Q2?", True),
                     ("q_three", "Q3?", False))
    out, seen = _with_fake_judge([False, True, True, False],
                                 lambda: _judge_l2("resp", exp, rubric=rubric))
    assert seen["num_questions"] == 4, seen
    assert out["violation_detected"] is True   # no false alarm
    assert abs(out["rubric_coverage"] - 2 / 3) < 1e-9, out
    # The clean branch is exactly where 11 shipped rubric questions were computed
    # and then dropped before any gate could see them.
    assert out["rubric_answers"] == {"q_one": True, "q_two": True, "q_three": False}, out


def test_l2_rubric_question_text_reaches_the_judge():
    exp = {"must_flag": ["overlap"]}
    rubric = _rubric(("only_q", "Is the tone right?", True))
    _, seen = _with_fake_judge([True, True],
                               lambda: _judge_l2("resp", exp, rubric=rubric))
    assert "Is the tone right?" in seen["prompt"], seen["prompt"]
    assert "only_q" not in seen["prompt"], "ids are keys, not judge-facing text"


def test_l2_case_level_rubric_revived_via_score_response():
    # report_* cases carry rubric at the top level of the case, not under expected.
    case = {"layer": 2, "name": "t", "expected": {},
            "rubric": _rubric(("all_sections", "Does it include all sections?", True))}
    out, seen = _with_fake_judge([False, True],
                                 lambda: score_response(case, "resp"))
    assert seen["num_questions"] == 2, seen
    assert out["rubric_coverage"] == 1.0, out
    assert out["rubric_answers"] == {"all_sections": True}, out


def test_l2_legacy_string_rubric_scores_coverage_but_yields_no_ids():
    """The validator rejects string rubrics at L2, so this cannot reach a real sweep.

    If one ever did, the right failure is a missing answer — which the gate turns
    into UNMEASURED — not an exception thrown after the model calls are already
    spent, and not a silent pass.
    """
    exp = {"must_flag": ["overlap"]}
    out, _ = _with_fake_judge([True, True],
                              lambda: _judge_l2("resp", exp, rubric=["Q1?"]))
    assert out["rubric_coverage"] == 1.0, out
    assert out["rubric_answers"] == {}, out


# --- "Nothing executed" must be distinguishable from "code ran and crashed" ---

def test_no_runnable_code_reports_why_not():
    # An exercise-style case whose response explains the effect in prose instead of
    # printing it: nothing executes. Recording ran=False with error=None makes that
    # indistinguishable from code that ran and crashed — the same silent-failure
    # family as the judge padding bug.
    resp = "The true effect was 4.2, as the DGP shows.\n```python\nimport pandas as pd\n```"
    out = _score_layer3(resp, {"true_effect": None, "tolerance": None},
                        {"layer": 3, "language": "python", "name": "t"})
    assert out["runs_without_error"] is False, out
    assert out["execution_error"], "no-code-executed must carry an explanation"
    assert "no runnable code" in out["execution_error"].lower(), out


def test_code_that_actually_runs_is_unaffected():
    resp = "```python\nprint('ESTIMATE:4.0')\n```"
    out = _score_layer3(resp, {"true_effect": None, "tolerance": None},
                        {"layer": 3, "language": "python", "name": "t",
                         "execution_mode": "exercise", "required_output": "estimate"})
    assert out["runs_without_error"] is True, out
    assert out["execution_error"] is None, out


# --- Judge integrity: raise, never pad (defect: fake all-zero scores under load) ---

_NO_RETRY = {"judge": {"max_attempts": 1, "retry_backoff": 0}}


class _FakeProc:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _judge_stdout(answers):
    """Shape a `claude -p --output-format json` reply carrying an answers array."""
    return json.dumps({"result": json.dumps({"answers": answers})})


def _with_fake_subprocess(replies, fn):
    """Run fn() with scorer.run_subprocess_grouped returning each reply in turn."""
    calls = {"n": 0}
    real = scorer.run_subprocess_grouped

    def fake(*args, **kwargs):
        i = min(calls["n"], len(replies) - 1)
        calls["n"] += 1
        reply = replies[i]
        if isinstance(reply, BaseException):
            raise reply
        return reply

    scorer.run_subprocess_grouped = fake
    try:
        return fn(), calls
    finally:
        scorer.run_subprocess_grouped = real


def _expect_judge_error(fn, what):
    try:
        fn()
    except JudgeError:
        return
    raise AssertionError(f"expected JudgeError for {what}")


def test_judge_raises_on_short_output():
    # 1 answer for 3 questions must raise, NOT pad to [True, False, False].
    reply = _FakeProc(_judge_stdout([True]))
    _expect_judge_error(
        lambda: _with_fake_subprocess(
            [reply], lambda: scorer._call_judge("p", 3, _NO_RETRY)),
        "short judge output")


def test_judge_raises_on_overlong_output():
    reply = _FakeProc(_judge_stdout([True] * 5))
    _expect_judge_error(
        lambda: _with_fake_subprocess(
            [reply], lambda: scorer._call_judge("p", 3, _NO_RETRY)),
        "over-length judge output")


def test_judge_raises_on_unparseable_stdout():
    reply = _FakeProc("not json at all")
    _expect_judge_error(
        lambda: _with_fake_subprocess(
            [reply], lambda: scorer._call_judge("p", 2, _NO_RETRY)),
        "unparseable stdout")


# --- run_subprocess_grouped: process-group cleanup on timeout ---

def test_run_subprocess_grouped_starts_new_session_and_returns_completed_process():
    captured = {}

    class _FakePopen:
        def __init__(self, args, **kwargs):
            captured["kwargs"] = kwargs
            self.pid = 1

        def communicate(self, timeout=None):
            self.returncode = 0
            return ("out", "")

    real = scorer.subprocess.Popen
    scorer.subprocess.Popen = _FakePopen
    try:
        result = scorer.run_subprocess_grouped(["echo", "hi"], timeout=5)
    finally:
        scorer.subprocess.Popen = real
    assert captured["kwargs"].get("start_new_session") is True, captured
    assert result.returncode == 0 and result.stdout == "out", result


def test_run_subprocess_grouped_sigterms_group_then_drains_on_timeout():
    # A child that exits cleanly on SIGTERM must not also be SIGKILLed.
    signals = []

    class _FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 4242
            self._calls = 0

        def communicate(self, timeout=None):
            self._calls += 1
            if self._calls == 1:
                raise subprocess.TimeoutExpired(cmd="x", timeout=timeout)
            self.returncode = -15  # terminated by SIGTERM
            return ("", "")

    real_popen, real_killpg = scorer.subprocess.Popen, scorer.os.killpg
    scorer.subprocess.Popen = _FakePopen
    scorer.os.killpg = lambda pid, sig: signals.append((pid, sig))
    try:
        try:
            scorer.run_subprocess_grouped(["sleep", "100"], timeout=1, term_grace=0.01)
            raise AssertionError("expected TimeoutExpired")
        except subprocess.TimeoutExpired:
            pass
    finally:
        scorer.subprocess.Popen = real_popen
        scorer.os.killpg = real_killpg
    assert signals == [(4242, scorer.signal.SIGTERM)], signals


def test_run_subprocess_grouped_sigkills_group_if_term_grace_exceeded():
    # A child unresponsive to SIGTERM must be force-killed, not left running.
    signals = []

    class _FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 4242
            self._calls = 0

        def communicate(self, timeout=None):
            self._calls += 1
            if self._calls <= 2:
                raise subprocess.TimeoutExpired(cmd="x", timeout=timeout)
            self.returncode = -9  # terminated by SIGKILL
            return ("", "")

    real_popen, real_killpg = scorer.subprocess.Popen, scorer.os.killpg
    scorer.subprocess.Popen = _FakePopen
    scorer.os.killpg = lambda pid, sig: signals.append((pid, sig))
    try:
        try:
            scorer.run_subprocess_grouped(["sleep", "100"], timeout=1, term_grace=0.01)
            raise AssertionError("expected TimeoutExpired")
        except subprocess.TimeoutExpired:
            pass
    finally:
        scorer.subprocess.Popen = real_popen
        scorer.os.killpg = real_killpg
    assert signals == [(4242, scorer.signal.SIGTERM), (4242, scorer.signal.SIGKILL)], signals


def test_judge_timeout_is_config_driven():
    # config.judge.timeout must reach run_subprocess_grouped's timeout kwarg.
    captured = {}
    real = scorer.run_subprocess_grouped

    def fake(*a, **k):
        captured["timeout"] = k.get("timeout")
        return _FakeProc(_judge_stdout([True, True]))

    scorer.run_subprocess_grouped = fake
    try:
        cfg = {"judge": {"max_attempts": 1, "retry_backoff": 0, "timeout": 777}}
        scorer._call_judge_once("p", 2, cfg)
    finally:
        scorer.run_subprocess_grouped = real
    assert captured["timeout"] == 777, captured


def test_judge_timeout_is_terminal_not_retried():
    # A genuine judge timeout must not be retried three times — same failure
    # mode as the skill side, just on the measurement call instead of the
    # skill call.
    cfg = {"judge": {"max_attempts": 3, "retry_backoff": 0}}
    reply = subprocess.TimeoutExpired(cmd="claude", timeout=1)
    out, calls = _with_fake_subprocess(
        [reply, _FakeProc(_judge_stdout([True]))],
        lambda: _expect_judge_error(
            lambda: scorer._call_judge("p", 1, cfg), "judge timeout"))
    assert calls["n"] == 1, calls


def test_judge_timeout_reason_is_typed():
    reply = subprocess.TimeoutExpired(cmd="claude", timeout=1)
    try:
        _with_fake_subprocess([reply], lambda: scorer._call_judge("p", 1, _NO_RETRY))
        raise AssertionError("expected JudgeError")
    except JudgeError as e:
        assert e.reason == "judge_timeout", e.reason


def test_judge_wrong_answer_count_reason_is_malformed():
    reply = _FakeProc(_judge_stdout([True]))
    try:
        _with_fake_subprocess(
            [reply], lambda: scorer._call_judge("p", 3, _NO_RETRY))
        raise AssertionError("expected JudgeError")
    except JudgeError as e:
        assert e.reason == "malformed_response", e.reason


def test_judge_generic_error_reason_stays_default():
    # Non-timeout, non-malformed failures (e.g. nonzero exit) keep the
    # existing generic "judge_error" reason — no behavior change there.
    reply = _FakeProc("", returncode=1, stderr="boom")
    try:
        _with_fake_subprocess([reply], lambda: scorer._call_judge("p", 1, _NO_RETRY))
        raise AssertionError("expected JudgeError")
    except JudgeError as e:
        assert e.reason == "judge_error", e.reason


def test_l0_judge_timeout_is_config_driven_and_terminal():
    captured = {"n": 0}
    real = scorer.run_subprocess_grouped

    def fake(*a, **k):
        captured["n"] += 1
        captured["timeout"] = k.get("timeout")
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

    scorer.run_subprocess_grouped = fake
    try:
        cfg = {"judge": {"max_attempts": 3, "retry_backoff": 0, "l0_timeout": 15}}
        try:
            scorer._score_layer0("desc", "msg", {}, cfg)
            raise AssertionError("expected JudgeError")
        except JudgeError as e:
            assert e.reason == "judge_timeout", e.reason
    finally:
        scorer.run_subprocess_grouped = real
    assert captured["n"] == 1, captured  # terminal, not retried
    assert captured["timeout"] == 15, captured


def test_judge_raises_on_nonzero_exit():
    reply = _FakeProc("", returncode=1, stderr="rate limited")
    _expect_judge_error(
        lambda: _with_fake_subprocess(
            [reply], lambda: scorer._call_judge("p", 2, _NO_RETRY)),
        "nonzero exit")


def test_judge_raises_on_is_error():
    reply = _FakeProc(json.dumps({"is_error": True, "result": "overloaded"}))
    _expect_judge_error(
        lambda: _with_fake_subprocess(
            [reply], lambda: scorer._call_judge("p", 2, _NO_RETRY)),
        "is_error response")


def test_judge_exact_count_passes():
    reply = _FakeProc(_judge_stdout([True, False, True]))
    out, _ = _with_fake_subprocess(
        [reply], lambda: scorer._call_judge("p", 3, _NO_RETRY))
    assert out == [True, False, True], out


def test_judge_retries_then_succeeds():
    cfg = {"judge": {"max_attempts": 3, "retry_backoff": 0}}
    replies = [_FakeProc("garbage"), _FakeProc(_judge_stdout([True, True]))]
    out, calls = _with_fake_subprocess(
        replies, lambda: scorer._call_judge("p", 2, cfg))
    assert out == [True, True], out
    assert calls["n"] == 2, calls


def test_judge_gives_up_after_max_attempts():
    cfg = {"judge": {"max_attempts": 3, "retry_backoff": 0}}
    seen = {"n": 0}
    real = scorer._call_judge_once

    def counting(*a, **k):
        seen["n"] += 1
        raise JudgeError("boom")

    scorer._call_judge_once = counting
    try:
        _expect_judge_error(lambda: scorer._call_judge("p", 2, cfg), "always-failing judge")
    finally:
        scorer._call_judge_once = real
    assert seen["n"] == 3, seen


def test_judge_timeout_raises_judge_error():
    exc = scorer.subprocess.TimeoutExpired(cmd="claude", timeout=120)
    _expect_judge_error(
        lambda: _with_fake_subprocess(
            [exc], lambda: scorer._call_judge("p", 2, _NO_RETRY)),
        "subprocess timeout")


# --- Judge errors must propagate, not become zeros ---

def _with_raising_judge(fn):
    real = scorer._call_judge

    def boom(*a, **k):
        raise JudgeError("judge down")

    scorer._call_judge = boom
    try:
        return fn()
    finally:
        scorer._call_judge = real


def test_l1_propagates_judge_error():
    exp = {"rubric": ["Q1?", "Q2?"]}
    _expect_judge_error(
        lambda: _with_raising_judge(lambda: _judge_l1("resp", exp)), "L1")


def test_l2_propagates_judge_error_no_string_fallback():
    exp = {"must_flag": ["overlap"], "severity": "fatal"}
    _expect_judge_error(
        lambda: _with_raising_judge(lambda: _judge_l2("resp", exp)), "L2")


def test_l4_propagates_judge_error():
    case = {"rubric": {"pedagogy": ["Q1?"], "safety": ["Q2?"]}}
    _expect_judge_error(
        lambda: _with_raising_judge(lambda: _judge_l4("resp", case)), "L4")


# --- Grading contract (D1): response_contract / deferred_rubric passthrough ---

def test_judge_l4_absent_grading_contract_defaults_safely():
    # Synthetic/legacy callers may still omit the field; preserve a safe fallback.
    case = {"rubric": {"pedagogy": ["Q1?"], "safety": ["Q2?"]}}
    out, seen = _with_fake_judge([True, True], lambda: _judge_l4("resp", case))
    assert out["question_answers"] == {
        "pedagogy": [True], "safety": [True]}, out
    assert out["response_contract"] is None, out
    assert out["deferred_rubric"] == [], out
    assert out["overall"] == 1.0, out  # unaffected by the new keys
    assert "Explicitly deferred—not graded:\nNone." in seen["prompt"]
    assert seen["num_questions"] == 2, seen


def test_judge_l4_passes_through_response_contract_and_deferred_rubric():
    case = {"rubric": {"pedagogy": ["Q1?"]},
            "response_contract": "first_turn",
            "deferred_rubric": ["Was the adjustment set justified?"]}
    out, _ = _with_fake_judge([True], lambda: _judge_l4("resp", case))
    assert out["response_contract"] == "first_turn", out
    assert out["deferred_rubric"] == ["Was the adjustment set justified?"], out
    # Deferred criteria never enter the graded dimensions or cost a question.
    assert out["overall"] == 1.0, out


def test_judge_l4_prompt_operationalizes_each_response_phase():
    first_deferred = "Was the final balance plot rendered?"
    first = {
        "rubric": {"pedagogy": ["Q1?"]},
        "response_contract": "first_turn",
        "deferred_rubric": [first_deferred],
    }
    _, first_seen = _with_fake_judge(
        [True], lambda: _judge_l4("resp", first))
    first_prompt = " ".join(first_seen["prompt"].split())
    for phrase in (
        "Response contract: first_turn",
        "immediate first reply",
        "diagnostic action reachable now",
        "appropriate next question",
        "Do not require a completed downstream analysis",
    ):
        assert phrase in first_prompt, phrase
    assert f"Explicitly deferred—not graded:\n- {first_deferred}" in first_seen["prompt"]
    assert first_seen["num_questions"] == 1, first_seen
    assert first_seen["prompt"].rsplit("Questions:\n", 1)[1] == "1. Q1?"

    final_deferred = "Was the rendered PNG embedded?"
    final = {
        "rubric": {"pedagogy": ["Q1?"]},
        "response_contract": "final_output",
        "deferred_rubric": [final_deferred],
    }
    _, final_seen = _with_fake_judge(
        [True], lambda: _judge_l4("resp", final))
    final_prompt = " ".join(final_seen["prompt"].split())
    for phrase in (
        "Response contract: final_output",
        "completed one-response deliverable",
        "Promises to provide required analysis",
        "deferred_rubric",
        "do not reward fabricated results",
    ):
        assert phrase in final_prompt, phrase
    assert f"Explicitly deferred—not graded:\n- {final_deferred}" in final_seen["prompt"]
    assert final_seen["num_questions"] == 1, final_seen
    assert final_seen["prompt"].rsplit("Questions:\n", 1)[1] == "1. Q1?"


def test_l5_propagates_judge_error():
    case = {"rubric": ["Q1?"], "steps": [{"skill": "a"}, {"skill": "b"}]}
    _expect_judge_error(
        lambda: _with_raising_judge(lambda: score_l5("s1", "s2", case)), "L5")


# --- L0 strictness (empty stdout used to fake-PASS negative cases) ---

def test_l0_raises_on_empty_stdout():
    _expect_judge_error(
        lambda: _with_fake_subprocess(
            [_FakeProc("")],
            lambda: score_response(
                {"layer": 0, "description_text": "d", "user_message": "m",
                 "expected": {"should_trigger": False}}, "", _NO_RETRY)),
        "empty L0 stdout")


def test_l0_raises_on_nonzero_exit():
    _expect_judge_error(
        lambda: _with_fake_subprocess(
            [_FakeProc("YES", returncode=1)],
            lambda: score_response(
                {"layer": 0, "description_text": "d", "user_message": "m",
                 "expected": {"should_trigger": True}}, "", _NO_RETRY)),
        "nonzero L0 exit")


def test_l0_scores_normally_on_valid_answer():
    for stdout, should_trigger, correct in [("YES", True, True), ("NO", True, False),
                                            ("NO", False, True), ("YES", False, False)]:
        case = {"layer": 0, "description_text": "d", "user_message": "m",
                "expected": {"should_trigger": should_trigger}}
        out, _ = _with_fake_subprocess(
            [_FakeProc(stdout)], lambda: score_response(case, "", _NO_RETRY))
        assert out["correct"] is correct, (stdout, should_trigger, out)


# --- L1 forbidden-method enforcement (config defines layer1.false_positive_rate) ---

def test_l1_reports_false_positives_on_rubric_path():
    exp = {"rubric": ["Q1?", "Q2?"], "must_not_recommend": ["RDD"]}
    resp = "This is panel data, so I recommend RDD for the cutoff."
    out, _ = _with_fake_judge([True, True], lambda: _judge_l1(resp, exp))
    assert out["false_positives"] == ["RDD"], out
    assert out["accuracy"] == 1.0, out  # rubric is perfect; the gate catches the FP


def test_l1_no_false_positive_when_method_not_recommended():
    exp = {"rubric": ["Q1?"], "must_not_recommend": ["RDD"]}
    resp = "RDD would not apply here; use DiD instead."
    out, _ = _with_fake_judge([True], lambda: _judge_l1(resp, exp))
    assert out["false_positives"] == [], out


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run_all()
