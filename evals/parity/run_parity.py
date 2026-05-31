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


def extract_code(markdown: str) -> str:
    """Concatenate the contents of fenced code blocks (python/r/R or bare)."""
    blocks = re.findall(r"```(?:python|r|R)?\n(.*?)```", markdown or "", re.DOTALL)
    return "\n".join(blocks)


def assert_contains(text: str, terms: list) -> dict:
    """{term: term-appears-in-text} (case-insensitive substring)."""
    low = (text or "").lower()
    return {t: (t.lower() in low) for t in (terms or [])}


def classify(comparisons: list, assertion_failures: list, in_baseline: bool) -> str:
    """PASS if everything agrees; else KNOWN_DISPARITY when baselined, FAIL when new."""
    failed = any(not c["agree"] for c in comparisons) or bool(assertion_failures)
    if not failed:
        return "PASS"  # passing while baselined => stale baseline entry (still PASS)
    return "KNOWN_DISPARITY" if in_baseline else "FAIL"


def load_baseline(path: str) -> dict:
    """Map method -> baseline entry from baseline.yaml (empty if file/key absent)."""
    if not path or not os.path.exists(path):
        return {}
    with open(path) as fh:
        data = yaml.safe_load(fh) or {}
    return {e["method"]: e for e in (data.get("known_disparities") or [])}


METHODS = ["did", "iv", "rdd", "matching", "sc", "timeseries", "hte",
           "experiments", "dag", "report-figures", "exercises"]

SKILL_TO_METHOD = {
    "causal-did": "did", "causal-iv": "iv", "causal-rdd": "rdd",
    "causal-matching": "matching", "causal-sc": "sc", "causal-timeseries": "timeseries",
    "causal-hte": "hte", "causal-experiments": "experiments", "causal-dag": "dag",
    "causal-report": "report-figures", "causal-exercises": "exercises",
}


def changed_methods(paths: list) -> set:
    """Map changed git paths to affected method names."""
    found = set()
    for raw in paths or []:
        p = raw.strip()
        m = re.search(r'templates/(?:r|python)/([a-z-]+)\.md', p)
        if m and m.group(1) in METHODS:
            found.add(m.group(1))
        m = re.search(r'skills/(causal-[a-z]+)/', p)
        if m and m.group(1) in SKILL_TO_METHOD:
            found.add(SKILL_TO_METHOD[m.group(1)])
        m = re.search(r'evals/parity/(?:reference|specs)/([a-z-]+)', p)
        if m and m.group(1) in METHODS:
            found.add(m.group(1))
    return found
