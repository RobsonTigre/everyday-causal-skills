"""Model-free R<->Python parity runner + gate for the causal-skills plugin.

Runs dedicated reference recipes (reference/<method>.{R,py}) on a shared fixture,
compares declared estimands within tolerance, and runs static capability
assertions against the templates and method-registry. See
docs/superpowers/specs/2026-05-30-rpy-parity-machine-design.md.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_ESTIMAND_RE = re.compile(
    r'^([A-Z][A-Z0-9_]*)\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$', re.MULTILINE)


def parse_estimands(stdout: str) -> dict:
    """Extract KEY:<float> lines (uppercase keys) from recipe stdout."""
    out = {}
    for m in _ESTIMAND_RE.finditer(stdout or ""):
        try:
            out[m.group(1)] = float(m.group(2))
        except ValueError:  # pragma: no cover
            continue
    return out


def compare_estimands(r_vals: dict, py_vals: dict, estimands: list) -> list:
    """Compare each declared estimand. agree if within tol_abs OR tol_rel."""
    results = []
    for e in estimands or []:
        name = e["name"]
        r, py = r_vals.get(name), py_vals.get(name)
        if r is None or py is None:
            results.append({"name": name, "r": r, "python": py, "agree": False,
                            "reason": "missing in " + ("R" if r is None else "Python")})
            continue
        adiff = abs(r - py)
        scale = max(abs(r), abs(py))
        oks = []
        if e.get("tol_abs") is not None:
            oks.append(adiff <= e["tol_abs"])
        if e.get("tol_rel") is not None:
            oks.append(adiff <= e["tol_rel"] * scale)
        agree = any(oks) if oks else (adiff == 0.0)
        results.append({"name": name, "r": r, "python": py, "adiff": adiff,
                        "agree": agree,
                        "reason": "" if agree else f"|delta|={adiff:.6g} exceeds tolerance"})
    return results
