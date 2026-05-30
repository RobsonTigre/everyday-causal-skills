"""Dependency-free unit tests for the R<->Python parity runner.
Run: python3 evals/parity/test_run_parity.py   (from repo root)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_parity import (parse_estimands, compare_estimands,  # noqa: E402
                        extract_code, assert_contains)


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
