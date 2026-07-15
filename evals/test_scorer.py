"""Fast, dependency-free unit tests for eval scorer harness changes.
Run: python3 evals/test_scorer.py   (from repo root)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scorer  # noqa: E402
from scorer import _score_layer3, _execute_code, _judge_l2, score_response  # noqa: E402


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
