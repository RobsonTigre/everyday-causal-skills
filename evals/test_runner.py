"""Fast, dependency-free unit tests for the eval runner.
Run: python3 evals/test_runner.py   (from repo root)

Everything here is offline — no `claude -p`, no network.
"""
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner  # noqa: E402
from runner import (  # noqa: E402
    DEFAULT_THRESHOLDS, aggregate, case_gate, collect_cases, report_path)


import json  # noqa: E402

# A skill call is one `claude -p` invocation; these fakes stand in for it.
_SKILL_CFG = {"skill": {"max_attempts": 3, "retry_backoff": 0},
              "judge": {"max_attempts": 1, "retry_backoff": 0}}
_L3_CASE = {"layer": 3, "skill": "causal-did", "name": "t",
            "user_message": "hi", "expected": {}}


class _P:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def _ok(text="```python\nprint(1)\n```"):
    return _P(json.dumps({"result": text, "usage": {"input_tokens": 1, "output_tokens": 2}}))


def _with_fake_cli(replies, fn):
    """Replace runner.subprocess.run, serving each reply in turn."""
    calls = {"n": 0}
    real = runner.subprocess.run

    def fake(*a, **k):
        i = min(calls["n"], len(replies) - 1)
        calls["n"] += 1
        return replies[i]

    runner.subprocess.run = fake
    try:
        return fn(), calls
    finally:
        runner.subprocess.run = real


def test_skill_call_retries_transient_failure():
    # One rate-limited blip must not cost the run — retry, then score normally.
    out, calls = _with_fake_cli(
        [_P("", returncode=1, stderr=""), _ok()],
        lambda: runner.run_case_cli(dict(_L3_CASE), _SKILL_CFG, 1))
    assert calls["n"] == 2, calls
    assert len(out) == 1 and not out[0].get("invalid"), out


def test_skill_call_gives_up_after_max_attempts():
    out, calls = _with_fake_cli(
        [_P("", returncode=1, stderr="")],
        lambda: runner.run_case_cli(dict(_L3_CASE), _SKILL_CFG, 1))
    assert calls["n"] == 3, calls
    assert out[0]["invalid"] == "skill_error", out
    assert out[0]["error"], out


def test_skill_empty_response_retries_then_marks_invalid():
    out, calls = _with_fake_cli(
        [_P(json.dumps({"result": "  ", "usage": {}}))],
        lambda: runner.run_case_cli(dict(_L3_CASE), _SKILL_CFG, 1))
    assert calls["n"] == 3, calls
    assert out[0]["invalid"] == "empty_response", out


def test_skill_retry_actually_sleeps_between_attempts():
    # Guards the backoff path itself: with a non-zero backoff the retry must call
    # time.sleep, not blow up on a missing import the zero-backoff tests never hit.
    slept = []
    real_sleep = runner.time.sleep
    runner.time.sleep = lambda s: slept.append(s)
    try:
        cfg = {"skill": {"max_attempts": 3, "retry_backoff": 2}}
        _with_fake_cli([_P("", returncode=1)],
                       lambda: runner.run_case_cli(dict(_L3_CASE), cfg, 1))
    finally:
        runner.time.sleep = real_sleep
    assert slept == [2, 4], slept  # exponential, and no sleep after the last try


def test_skill_unparseable_stdout_retries_then_marks_invalid():
    out, calls = _with_fake_cli(
        [_P("not json")],
        lambda: runner.run_case_cli(dict(_L3_CASE), _SKILL_CFG, 1))
    assert calls["n"] == 3, calls
    assert out[0]["invalid"] == "skill_error", out


def _runs(layer, scores_list, invalid_after=0):
    """Build run records: one per scores dict, plus `invalid_after` invalid runs."""
    out = [{"run": i + 1, "scores": s, "tokens": {"input": 0, "output": 0}}
           for i, s in enumerate(scores_list)]
    for j in range(invalid_after):
        out.append(runner._invalid_run(len(out), "judge_error", "judge down"))
    return out


# --- Invalid runs must never be scored ---

def test_aggregate_excludes_invalid_runs():
    runs = _runs(1, [{"accuracy": 1.0}, {"accuracy": 1.0}, {"accuracy": 0.4}],
                 invalid_after=2)
    agg = aggregate(runs, {"layer": 1})
    assert agg["runs_valid"] == 3, agg
    assert agg["runs_total"] == 5, agg
    assert abs(agg["rate"] - (1.0 + 1.0 + 0.4) / 3) < 1e-9, agg


def test_aggregate_zero_valid_is_unmeasured():
    runs = _runs(1, [], invalid_after=5)
    agg = aggregate(runs, {"layer": 1})
    assert agg["rate"] is None, agg
    assert agg["runs_valid"] == 0 and agg["runs_total"] == 5, agg
    assert case_gate(1, agg) == "UNMEASURED", agg


def test_unmeasured_is_never_a_fail_on_any_layer():
    for layer in range(6):
        agg = aggregate(_runs(layer, [], invalid_after=3), {"layer": layer})
        assert case_gate(layer, agg) == "UNMEASURED", (layer, agg)


def test_invalid_run_always_carries_a_nonempty_error():
    # Empty stderr used to produce an error-marked run with no error text.
    r = runner._invalid_run(0, "skill_error", "")
    assert r["invalid"] == "skill_error"
    assert r["error"], r


# --- Typed aggregates: no "3/5" or "n/a" strings in machine output ---

def test_aggregate_values_are_typed_not_strings():
    runs = _runs(3, [{"runs_without_error": True, "estimation_accurate": True,
                      "diagnostic_coverage": 1.0, "guard_passed": True}])
    agg = aggregate(runs, {"layer": 3})
    for key, val in agg.items():
        assert not isinstance(val, str), (key, val)


# --- L3 estimation: applicable-only denominator ---

def test_l3_est_na_when_no_ground_truth():
    # DAG structural cases have no true_effect -> estimation_accurate is None.
    runs = _runs(3, [{"runs_without_error": True, "estimation_accurate": None,
                      "diagnostic_coverage": 1.0, "guard_passed": True}] * 5)
    agg = aggregate(runs, {"layer": 3})
    assert agg["est_applicable"] == 0, agg
    assert case_gate(3, agg) == "PASS", agg  # must not fail an inapplicable gate


def test_l3_est_denominator_counts_applicable_only():
    scores = [
        {"runs_without_error": True, "estimation_accurate": True,
         "diagnostic_coverage": 1.0, "guard_passed": True},
        {"runs_without_error": True, "estimation_accurate": None,
         "diagnostic_coverage": 1.0, "guard_passed": True},
        {"runs_without_error": True, "estimation_accurate": False,
         "diagnostic_coverage": 1.0, "guard_passed": True},
    ]
    agg = aggregate(_runs(3, scores), {"layer": 3})
    assert agg["est_applicable"] == 2 and agg["est_ok"] == 1, agg
    assert case_gate(3, agg) == "FAIL", agg  # 1/2 = 0.5 < 0.8


def test_l3_missing_estimate_with_ground_truth_is_a_failure_not_a_skip():
    # A case declaring true_effect whose code never prints ESTIMATE: has failed the
    # estimation gate. Treating it as "inapplicable" would let it pass on runtime alone.
    from scorer import _score_layer3
    resp = "```python\nprint('no estimate here')\n```"
    out = _score_layer3(resp, {"true_effect": 4.0, "tolerance": 2.5, "code_runs": True},
                        {"layer": 3, "language": "python", "name": "t"})
    assert out["estimate"] is None, out
    assert out["estimation_accurate"] is False, out

    agg = aggregate(_runs(3, [{"runs_without_error": True, "estimation_accurate": False,
                               "diagnostic_coverage": 1.0, "guard_passed": True}] * 5),
                    {"layer": 3})
    assert agg["est_applicable"] == 5, agg
    assert case_gate(3, agg) == "FAIL", agg


def test_l3_gate_enforces_guards_but_not_diagnostic_coverage():
    base = {"runs_without_error": True, "estimation_accurate": True,
            "diagnostic_coverage": 1.0, "guard_passed": True}
    assert case_gate(3, aggregate(_runs(3, [base] * 5), {"layer": 3})) == "PASS"

    # diagnostic_coverage is REPORTED, NOT GATED. It is a literal substring match
    # (scorer.py:566) with demonstrated false negatives: did_basic_2x2 scored 0.33 while
    # clustering its SEs six times and reporting a 95% CI, having never written the exact
    # phrases. `must_include` alternates were built to cure that, but only 2 of 21 L3
    # cases use them and neither of the two cases that demonstrated the problem does. A
    # wording matcher must not be able to fail a release on its own.
    zero_diag = aggregate(_runs(3, [{**base, "diagnostic_coverage": 0.0}] * 5),
                          {"layer": 3})
    assert case_gate(3, zero_diag) == "PASS", zero_diag
    # …but it is still computed and reported, so the signal is not lost.
    assert zero_diag["diagnostic_coverage"] == 0.0, zero_diag

    bad_guard = aggregate(_runs(3, [{**base, "guard_passed": False}] * 5), {"layer": 3})
    assert case_gate(3, bad_guard) == "FAIL", bad_guard  # guard_pass_rate must be 1.0


def test_diagnostic_coverage_is_absent_from_every_gating_threshold_block():
    """An inert key inside a thresholds block reads as a gate on review. That is the
    dead-metadata problem section 3 removed from cases; it must not return via config."""
    import yaml
    assert "diagnostic_coverage" not in DEFAULT_THRESHOLDS["layer3"], DEFAULT_THRESHOLDS
    release = yaml.safe_load(
        (Path(__file__).resolve().parent / "config.release.yaml").read_text())
    assert "diagnostic_coverage" not in release["thresholds"]["layer3"], release
    # Still declared somewhere explicit, so dropping the gate is a decision, not a loss.
    assert "diagnostic_coverage" in release["reporting_only"]["layer3"], release


# --- Gate contract per layer (config.yaml is the source of truth) ---

def test_l0_gate():
    agg = aggregate(_runs(0, [{"correct": True}] * 5), {"layer": 0})
    assert case_gate(0, agg) == "PASS"
    agg = aggregate(_runs(0, [{"correct": True}] * 4 + [{"correct": False}]), {"layer": 0})
    assert case_gate(0, agg) == "FAIL"  # 0.8 < 0.9


def test_l1_gate_fails_on_forbidden_method_even_with_perfect_rubric():
    clean = aggregate(_runs(1, [{"accuracy": 1.0, "false_positives": []}] * 5), {"layer": 1})
    assert case_gate(1, clean) == "PASS", clean

    fp = aggregate(_runs(1, [{"accuracy": 1.0, "false_positives": ["RDD"]}] * 5), {"layer": 1})
    assert fp["false_positives"] == 5, fp
    assert case_gate(1, fp) == "FAIL", fp


def test_l2_gate_enforces_severity():
    good = aggregate(_runs(2, [{"violation_detected": True, "severity_correct": True}] * 5),
                     {"layer": 2})
    assert case_gate(2, good) == "PASS"
    # Detection perfect, severity 2/5 = 0.4 < 0.7 -> FAIL
    mixed = [{"violation_detected": True, "severity_correct": i < 2} for i in range(5)]
    agg = aggregate(_runs(2, mixed), {"layer": 2})
    assert case_gate(2, agg) == "FAIL", agg


def test_l4_gate_requires_every_populated_dimension():
    dims = ["pedagogy", "safety", "actionable"]
    strong = {"pedagogy": 0.9, "safety": 0.9, "actionable": 0.9, "dimensions_present": dims}
    assert case_gate(4, aggregate(_runs(4, [strong] * 5), {"layer": 4})) == "PASS"

    # Average is 0.77 (passes an average>=0.7 rule) but pedagogy 0.4 must fail.
    lopsided = {"pedagogy": 0.4, "safety": 1.0, "actionable": 0.9,
                "dimensions_present": dims}
    agg = aggregate(_runs(4, [lopsided] * 5), {"layer": 4})
    assert agg["overall"] > 0.7, agg
    assert case_gate(4, agg) == "FAIL", agg


def test_l4_absent_dimension_is_skipped_not_zeroed():
    # A case that only populates pedagogy must not fail on empty safety/actionable.
    only_ped = {"pedagogy": 0.9, "safety": 0.0, "actionable": 0.0,
                "dimensions_present": ["pedagogy"]}
    agg = aggregate(_runs(4, [only_ped] * 5), {"layer": 4})
    assert agg["safety"] is None, agg
    assert case_gate(4, agg) == "PASS", agg


def test_l5_gate():
    good = aggregate(_runs(5, [{"handoff_quality": 0.8, "questions_passed": 4,
                                "questions_total": 5}] * 5), {"layer": 5})
    assert case_gate(5, good) == "PASS"
    weak = aggregate(_runs(5, [{"handoff_quality": 0.6, "questions_passed": 3,
                                "questions_total": 5}] * 5), {"layer": 5})
    assert case_gate(5, weak) == "FAIL"


def test_gate_is_not_decided_by_floating_point_noise():
    # Averaging per-run fractions yields values like 0.7999999999999999 for a case that
    # scored exactly 0.8. Observed live: small_sample_panel failed on this while
    # single_treated_unit passed with an identical-looking 0.80.
    noisy = {"runs_valid": 5, "runs_total": 5, "accuracy": 0.7999999999999999,
             "false_positives": 0, "rate": 0.7999999999999999}
    assert case_gate(1, noisy) == "PASS", noisy

    # A case genuinely below the bar must still fail.
    real_miss = {**noisy, "accuracy": 0.79, "rate": 0.79}
    assert case_gate(1, real_miss) == "FAIL", real_miss


def test_case_gate_respects_supplied_thresholds():
    agg = aggregate(_runs(1, [{"accuracy": 0.75, "false_positives": []}] * 5), {"layer": 1})
    assert case_gate(1, agg) == "FAIL"
    assert case_gate(1, agg, {"layer1": {"accuracy": 0.7}}) == "PASS"


# --- Duplicate case names (shadowing bug) ---

def test_collect_cases_raises_on_duplicate_name():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for layer in ("layer2", "layer3"):
            (root / layer).mkdir()
            (root / layer / "dup_case.yaml").write_text("name: dup_case\n")
        try:
            collect_cases(cases_dir=root)
        except ValueError as e:
            assert "dup_case" in str(e), e
            return
        raise AssertionError("expected ValueError for duplicate case name")


def test_real_case_tree_has_no_duplicate_names():
    collect_cases()  # raises if the repo still carries a shadowed case


def test_collect_cases_by_name_finds_unique_case():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "layer1").mkdir()
        (root / "layer1" / "solo.yaml").write_text("name: solo\n")
        got = collect_cases(case_name="solo", cases_dir=root)
        assert got == [str(root / "layer1" / "solo.yaml")], got


# --- Report filename collisions ---

def test_report_filename_is_unique_per_process_and_label():
    with tempfile.TemporaryDirectory() as d:
        a = report_path(Path(d), "layer3")
        b = report_path(Path(d), "roi_values_r")
        assert a != b
        assert str(os.getpid()) in a.name, a.name
        assert re.match(r"\d{4}-\d{2}-\d{2}_\d{6}_.+_pid\d+\.md$", a.name), a.name


def test_report_label_is_sanitized():
    with tempfile.TemporaryDirectory() as d:
        p = report_path(Path(d), "weird/../label name")
        assert "/" not in p.name and " " not in p.name, p.name


# --- HISTORY must survive unmeasured + inapplicable-estimation cases ---

def test_save_history_handles_unmeasured_and_inapplicable_est():
    cases = [
        {"case": {"name": "ok", "layer": 3},
         "aggregate": aggregate(_runs(3, [{"runs_without_error": True,
                                           "estimation_accurate": None,
                                           "diagnostic_coverage": 1.0,
                                           "guard_passed": True}] * 5), {"layer": 3})},
        {"case": {"name": "dead", "layer": 3},
         "aggregate": aggregate(_runs(3, [], invalid_after=5), {"layer": 3})},
    ]
    results = {"runs": 5, "backend": "cli", "cases": cases}
    with tempfile.TemporaryDirectory() as d:
        hist = Path(d) / "HISTORY.md"
        runner.save_history(results, {"model": "test"}, notes="unit", hist_path=hist)
        text = hist.read_text()
    # One measured L3 case passes runtime; the unmeasured one is excluded entirely,
    # and the inapplicable estimation column renders as a dash, not 0/1.
    assert "| 1/1 |" in text, text
    assert "int(" not in text
    row = [ln for ln in text.splitlines() if ln.startswith("| 20")][0]
    assert row.count("—") >= 1, row


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
