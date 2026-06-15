"""Guard test: the pyproject `parity` extra must declare every Python package
the parity recipes actually require. Prevents the parity environment from
silently drifting out of sync with the recipes — the gap that let synthetic
control and RDD pass as hollow greens when their packages were absent.

Run: python3 evals/parity/test_parity_deps.py   (from repo root)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_parity import load_spec, select_spec_paths  # noqa: E402

# import-name -> pip-name, mirroring references/preflight.md. Identity for the rest.
IMPORT_TO_PIP = {
    "scpi_pkg": "scpi-pkg",
    "diff_diff": "diff-diff",
    "sklearn": "scikit-learn",
}

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SPECS_DIR = os.path.join(_REPO_ROOT, "evals", "parity", "specs")
_PYPROJECT = os.path.join(_REPO_ROOT, "pyproject.toml")


def _pip_name(mod):
    return IMPORT_TO_PIP.get(mod, mod).lower()


def _declared_parity_packages():
    text = open(_PYPROJECT).read()
    m = re.search(r"(?ms)^\s*parity\s*=\s*\[(.*?)\]", text)
    assert m, "pyproject.toml has no [project.optional-dependencies] `parity` array"
    names = re.findall(r'"([^"]+)"', m.group(1))
    return {re.split(r"[<>=!~;\s]", n, 1)[0].strip().lower() for n in names}


def _required_python_packages():
    req = set()
    for path in select_spec_paths(_SPECS_DIR, None):
        spec = load_spec(path)
        for mod in (spec.get("requires", {}) or {}).get("python", []) or []:
            req.add(_pip_name(mod))
    return req


def test_parity_extra_covers_all_recipe_requires():
    declared = _declared_parity_packages()
    required = _required_python_packages()
    missing = sorted(required - declared)
    assert not missing, (
        "pyproject [parity] extra is missing recipe Python deps: "
        f"{missing}. Add them so `pip install -e \".[parity]\"` reproduces a "
        "complete parity environment."
    )


if __name__ == "__main__":  # direct-run convenience, matches sibling test file
    test_parity_extra_covers_all_recipe_requires()
    print("ok")
