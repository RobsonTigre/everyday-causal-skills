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


def run_recipe(recipe_path: str, fixture_path: str, language: str,
               requires: list = None, timeout: int = 180) -> dict:
    """Run a reference recipe with `df` preloaded from the fixture; capture stdout."""
    py = os.environ.get("EVAL_PYTHON", "python3")
    rsc = os.environ.get("EVAL_RSCRIPT", "Rscript")
    interp = py if language == "python" else rsc

    for mod in (requires or []):
        if language == "python":
            chk = subprocess.run([py, "-c", f"import {mod}"], capture_output=True, text=True)
        else:
            chk = subprocess.run([rsc, "-e", f"library({mod})"], capture_output=True, text=True)
        if chk.returncode != 0:
            return {"ran": False, "error": f"package '{mod}' not importable under {interp}",
                    "stdout": ""}

    with open(recipe_path) as f:
        code = f.read()
    if language == "python":
        preamble = ("import matplotlib\nmatplotlib.use('Agg')\nimport pandas as pd\n"
                    f"df = pd.read_csv({fixture_path!r})\n")
        suffix = ".py"
    else:
        _r_path = fixture_path.replace("\\", "\\\\").replace("'", "\\'")
        preamble = f"options(warn=1)\ndf <- read.csv('{_r_path}')\n"
        suffix = ".R"

    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as tf:
            tf.write(preamble + code)
            tmp = tf.name
        proc = subprocess.run([interp, tmp], capture_output=True, text=True, timeout=timeout)
        return {"ran": proc.returncode == 0,
                "error": None if proc.returncode == 0 else (proc.stderr or "")[-2000:],
                "stdout": proc.stdout or ""}
    except subprocess.TimeoutExpired:
        return {"ran": False, "error": f"timeout after {timeout}s", "stdout": ""}
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def load_spec(path: str) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


def _read(repo_root: str, rel: str) -> str:
    p = os.path.join(repo_root, rel)
    if not os.path.exists(p):
        return ""
    with open(p) as fh:
        return fh.read()


def _default_template_paths(method: str) -> dict:
    return {"python": f"templates/python/{method}.md", "r": f"templates/r/{method}.md"}


def run_method(spec: dict, repo_root: str = ".", baseline: dict = None) -> dict:
    """Run one method's parity check; return verdict + details."""
    baseline = baseline or {}
    method = spec["method"]
    fixture = os.path.join(repo_root, spec["fixture"])
    ref, req = spec["reference"], spec.get("requires", {}) or {}

    r_res = run_recipe(os.path.join(repo_root, ref["r"]), fixture, "r", req.get("r"))
    py_res = run_recipe(os.path.join(repo_root, ref["python"]), fixture, "python", req.get("python"))

    exec_failures = []
    if not r_res["ran"]:
        exec_failures.append(f"R recipe failed: {r_res['error']}")
    if not py_res["ran"]:
        exec_failures.append(f"Python recipe failed: {py_res['error']}")

    comparisons = compare_estimands(parse_estimands(r_res["stdout"]),
                                    parse_estimands(py_res["stdout"]),
                                    spec.get("estimands", []))

    caps = spec.get("capability_assertions", {}) or {}
    tpl_paths = spec.get("template_paths") or _default_template_paths(method)
    assertion_failures = []
    for lang, terms in (caps.get("template_must_use") or {}).items():
        for term, ok in assert_contains(extract_code(_read(repo_root, tpl_paths[lang])), terms).items():
            if not ok:
                assertion_failures.append(f"{lang} template missing canonical '{term}'")
    for lang, terms in (caps.get("template_must_mention") or {}).items():
        paths = ([tpl_paths["python"], tpl_paths["r"]] if lang == "both" else [tpl_paths[lang]])
        texts = [_read(repo_root, p) for p in paths]
        for term in terms:
            if not all(assert_contains(t, [term])[term] for t in texts):
                assertion_failures.append(f"{lang} template missing mention '{term}'")
    reg_pkgs = caps.get("registry_currency") or []
    if reg_pkgs:
        reg = _read(repo_root, "references/method-registry.md")
        for pkg, ok in assert_contains(reg, reg_pkgs).items():
            if not ok:
                assertion_failures.append(f"method-registry missing current package '{pkg}'")

    all_fail = assertion_failures + exec_failures
    verdict = classify(comparisons, all_fail, in_baseline=(method in baseline))
    return {"method": method, "verdict": verdict, "comparisons": comparisons,
            "assertion_failures": all_fail,
            "baseline_id": baseline.get(method, {}).get("backlog_id")}


def select_spec_paths(specs_dir: str, methods: set = None) -> list:
    if not os.path.isdir(specs_dir):
        return []
    paths = []
    for fn in sorted(os.listdir(specs_dir)):
        if not fn.endswith(".yaml"):
            continue
        method = fn[:-5]
        if methods is None or method in methods:
            paths.append(os.path.join(specs_dir, fn))
    return paths


def summarize_exit_code(results: list) -> int:
    return 1 if any(r["verdict"] == "FAIL" for r in results) else 0


def _git_changed_paths(repo_root: str) -> list:
    out = subprocess.run(["git", "-C", repo_root, "diff", "--name-only", "HEAD"],
                         capture_output=True, text=True)
    staged = subprocess.run(["git", "-C", repo_root, "diff", "--name-only", "--cached"],
                            capture_output=True, text=True)
    return [p for p in (out.stdout + staged.stdout).splitlines() if p.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description="R<->Python parity gate")
    ap.add_argument("--method", action="append", default=[], help="method name (repeatable)")
    ap.add_argument("--all", action="store_true", help="run every spec")
    ap.add_argument("--changed", action="store_true", help="only methods touched vs HEAD")
    ap.add_argument("--repo-root", default=".")
    args = ap.parse_args(argv)

    root = args.repo_root
    specs_dir = os.path.join(root, "evals/parity/specs")
    baseline = load_baseline(os.path.join(root, "evals/parity/baseline.yaml"))

    methods = None
    if args.method:
        methods = set(args.method)
    elif args.changed:
        methods = changed_methods(_git_changed_paths(root))
        if not methods:
            print("parity: no method-affecting changes detected — nothing to check.")
            return 0
    elif not args.all:
        ap.error("specify --all, --changed, or --method M")

    results = []
    for sp in select_spec_paths(specs_dir, methods):
        res = run_method(load_spec(sp), repo_root=root, baseline=baseline)
        results.append(res)
        flag = {"PASS": "ok", "KNOWN_DISPARITY": "known", "FAIL": "FAIL"}[res["verdict"]]
        print(f"[{flag:>5}] {res['method']}")
        for f in res["assertion_failures"]:
            print(f"          - {f}")
        for c in res["comparisons"]:
            if not c["agree"]:
                print(f"          - estimand {c['name']}: {c['reason']} (R={c['r']} Py={c['python']})")
    if not results:
        print("parity: no specs found for the selection.")
    code = summarize_exit_code(results)
    print(f"\nparity: {sum(r['verdict']=='PASS' for r in results)} pass, "
          f"{sum(r['verdict']=='KNOWN_DISPARITY' for r in results)} known, "
          f"{sum(r['verdict']=='FAIL' for r in results)} FAIL -> exit {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())
