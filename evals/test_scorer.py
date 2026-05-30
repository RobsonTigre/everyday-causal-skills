"""Fast, dependency-free unit tests for eval scorer harness changes.
Run: python3 evals/test_scorer.py   (from repo root)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scorer import _score_layer3, _execute_code  # noqa: E402


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
