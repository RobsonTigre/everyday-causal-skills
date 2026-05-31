"""Dependency-free unit tests for the R<->Python parity runner.
Run: python3 evals/parity/test_run_parity.py   (from repo root)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_parity import (parse_estimands, compare_estimands,  # noqa: E402
                        extract_code, assert_contains, classify, changed_methods,
                        run_recipe)


def test_parse_basic():
    out = parse_estimands("noise\nATT:5.06\nSE: 0.30\nCI_LO:-1.2e-3\ntrailing")
    assert out == {"ATT": 5.06, "SE": 0.30, "CI_LO": -0.0012}, out


def test_parse_ignores_nonmatching():
    out = parse_estimands("ATT is 5\nestimate: 3\nATT:5.0\n")
    assert out == {"ATT": 5.0}, out


def test_compare_agree_abs():
    cmp = compare_estimands({"ATT": 5.00}, {"ATT": 5.10},
                            [{"name": "ATT", "tol_abs": 0.5}])
    assert cmp[0]["agree"] is True, cmp


def test_compare_disagree():
    cmp = compare_estimands({"ATT": 5.0}, {"ATT": 9.0},
                            [{"name": "ATT", "tol_abs": 0.5, "tol_rel": 0.05}])
    assert cmp[0]["agree"] is False, cmp


def test_compare_missing_side():
    cmp = compare_estimands({"ATT": 5.0}, {}, [{"name": "ATT", "tol_abs": 0.5}])
    assert cmp[0]["agree"] is False
    assert "missing" in cmp[0]["reason"].lower()


def test_compare_rel_tolerance():
    cmp = compare_estimands({"F": 100.0}, {"F": 104.0},
                            [{"name": "F", "tol_rel": 0.05}])
    assert cmp[0]["agree"] is True, cmp


def test_extract_code_only_fences():
    md = "prose CallawaySantAnna\n```python\nimport x\ncs = CallawaySantAnna()\n```\nmore prose"
    code = extract_code(md)
    assert "CallawaySantAnna()" in code
    assert "more prose" not in code


def test_assert_contains_present():
    res = assert_contains("from diff_diff import CallawaySantAnna", ["CallawaySantAnna"])
    assert res == {"CallawaySantAnna": True}, res


def test_assert_contains_absent():
    res = assert_contains("from linearmodels.panel import PanelOLS", ["CallawaySantAnna"])
    assert res == {"CallawaySantAnna": False}, res


def test_assert_contains_case_insensitive():
    res = assert_contains("uses ATT_GT here", ["att_gt"])
    assert res == {"att_gt": True}, res


def test_classify_pass():
    cmps = [{"name": "ATT", "agree": True}]
    assert classify(cmps, [], in_baseline=False) == "PASS"


def test_classify_new_failure():
    cmps = [{"name": "ATT", "agree": False}]
    assert classify(cmps, [], in_baseline=False) == "FAIL"


def test_classify_known_disparity():
    cmps = [{"name": "ATT", "agree": False}]
    assert classify(cmps, [], in_baseline=True) == "KNOWN_DISPARITY"


def test_classify_assertion_failure_is_fail():
    cmps = [{"name": "ATT", "agree": True}]
    assert classify(cmps, ["python template missing 'CallawaySantAnna'"], in_baseline=False) == "FAIL"


def test_classify_known_passes_now_is_pass():
    # A baseline-listed method that now agrees should report PASS (stale baseline).
    cmps = [{"name": "ATT", "agree": True}]
    assert classify(cmps, [], in_baseline=True) == "PASS"


def test_changed_template():
    assert changed_methods(["templates/python/iv.md"]) == {"iv"}


def test_changed_skill_dir():
    assert changed_methods(["skills/causal-rdd/SKILL.md"]) == {"rdd"}


def test_changed_report_hyphen():
    assert changed_methods(["templates/r/report-figures.md"]) == {"report-figures"}


def test_changed_parity_files():
    got = changed_methods(["evals/parity/reference/sc.py", "evals/parity/specs/hte.yaml"])
    assert got == {"sc", "hte"}, got


def test_changed_ignores_unrelated():
    assert changed_methods(["README.md", "evals/scorer.py"]) == set()


import tempfile as _tf  # noqa: E402


def _write(tmp, name, content):
    p = os.path.join(tmp, name)
    with open(p, "w") as f:
        f.write(content)
    return p


def test_run_recipe_python_reads_df_and_prints():
    with _tf.TemporaryDirectory() as tmp:
        csv = _write(tmp, "f.csv", "a,b\n1,2\n3,4\n")
        rec = _write(tmp, "r.py", "print(f'SUM:{df[\"a\"].sum()}')\n")
        out = run_recipe(rec, csv, "python")
        assert out["ran"] is True, out
        assert parse_estimands(out["stdout"]) == {"SUM": 4.0}, out


def test_run_recipe_missing_requires():
    with _tf.TemporaryDirectory() as tmp:
        csv = _write(tmp, "f.csv", "a\n1\n")
        rec = _write(tmp, "r.py", "print('X:1')\n")
        out = run_recipe(rec, csv, "python", requires=["no_such_pkg_zzz"])
        assert out["ran"] is False
        assert "not importable" in out["error"]


def test_run_recipe_python_error_captured():
    with _tf.TemporaryDirectory() as tmp:
        csv = _write(tmp, "f.csv", "a\n1\n")
        rec = _write(tmp, "r.py", "raise ValueError('boom')\n")
        out = run_recipe(rec, csv, "python")
        assert out["ran"] is False
        assert "boom" in (out["error"] or "")


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1; print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run_all()
