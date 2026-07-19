"""Fast, dependency-free unit tests for eval scorer harness changes.
Run: python3 evals/test_scorer.py   (from repo root)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scorer  # noqa: E402
from scorer import (  # noqa: E402
    JudgeError,
    _execute_code,
    _judge_l1,
    _judge_l2,
    _judge_l4,
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
    assert out["guard_passed"] is True
    assert out["diagnostic_coverage"] == 1.0  # backward-compat: prose 'parallel trends' matches


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


def test_l2_rubric_appended_after_flags_and_severity():
    exp = {"must_flag": ["overlap"], "severity": "fatal"}
    rubric = ["Q1?", "Q2?"]
    out, seen = _with_fake_judge([True, True, True, False],
                                 lambda: _judge_l2("resp", exp, rubric=rubric))
    assert seen["num_questions"] == 4, seen
    assert out["violation_detected"] is True   # index 0 still the flag answer
    assert out["rubric_coverage"] == 0.5, out  # 1 of 2 rubric questions passed


def test_l2_clean_case_with_rubric():
    exp = {}  # no must_flag -> clean branch (question 0 = false-alarm check)
    rubric = ["Q1?", "Q2?", "Q3?"]
    out, seen = _with_fake_judge([False, True, True, False],
                                 lambda: _judge_l2("resp", exp, rubric=rubric))
    assert seen["num_questions"] == 4, seen
    assert out["violation_detected"] is True   # no false alarm
    assert abs(out["rubric_coverage"] - 2 / 3) < 1e-9, out


def test_l2_case_level_rubric_revived_via_score_response():
    # report_* cases carry rubric at the top level of the case, not under expected.
    case = {"layer": 2, "name": "t", "expected": {},
            "rubric": ["Does it include all sections?"]}
    out, seen = _with_fake_judge([False, True],
                                 lambda: score_response(case, "resp"))
    assert seen["num_questions"] == 2, seen
    assert out["rubric_coverage"] == 1.0, out


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
                        {"layer": 3, "language": "python", "name": "t"})
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
    """Run fn() with scorer.subprocess.run returning each reply in turn."""
    calls = {"n": 0}
    real = scorer.subprocess.run

    def fake(*args, **kwargs):
        i = min(calls["n"], len(replies) - 1)
        calls["n"] += 1
        reply = replies[i]
        if isinstance(reply, BaseException):
            raise reply
        return reply

    scorer.subprocess.run = fake
    try:
        return fn(), calls
    finally:
        scorer.subprocess.run = real


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
