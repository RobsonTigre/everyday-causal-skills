"""Sweep orchestrator for the eval suite.

Runs every case in its own runner subprocess, so a killed sweep loses at most
one in-flight case and can resume from its ledger. Before each wave it checks
that the judge and the skill path are actually healthy — the 2026-07-15 sweep
was corrupted by rate limiting that silently degraded scores rather than
failing, and roughly forty cases never got a trustworthy measurement.

Cases that fail to measure are requeued; cases that measure and miss their
threshold are not (that is a real result, not weather).

Run: python3 evals/sweep.py --runs 5
Exit: 0 all pass · 1 real failures · 2 unmeasured remain · 3 preflight failed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import runner  # noqa: E402
import scorer  # noqa: E402
from validate_cases import validate_tree, warn_tree  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
# Per-slot timeout: one runner.py invocation now covers a single run (slot
# checkpointing — see run_case_slots), not all `runs_per_case` sequentially, so
# the old whole-case budget is generous headroom for one run.
SLOT_TIMEOUT = 5400  # generous: L3 cases execute generated code


# --- Fingerprint: what this measurement is a measurement OF ---

def _git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                              text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _claude_version() -> str:
    try:
        return subprocess.run(["claude", "--version"], capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


# Content the model actually sees. skills/references/templates ARE the system prompt;
# evals/data is pasted into user_message by runner.inject_schema; evals/fixtures is read
# off disk by the artifact cases. None of this was hashed before, so a skill edit
# mid-sweep changed what was being measured without moving any recorded hash.
_CONTENT_TREES: tuple[tuple[str, str], ...] = (
    ("skills", "*.md"),
    ("references", "*.md"),
    ("templates", "*.md"),
    ("evals/data", "*.csv"),
    ("evals/fixtures", "*"),
)

_HARNESS_FILES = ("scorer.py", "runner.py", "validate_cases.py", "sweep.py")

_MANIFEST_PATHS = (
    ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json",
    "plugin.json", "gemini-extension.json",
)


def _hash_paths(paths) -> str:
    """Hash file contents keyed by REPO-RELATIVE POSIX path.

    Relative, not absolute: the same content checked out in a worktree, or on another
    machine, must produce the same digest. Hashing absolute paths silently defeated the
    frozen-worktree release procedure, which exists precisely to measure identical content
    somewhere else.
    """
    h = hashlib.sha256()
    entries = []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            continue
        try:
            key = path.resolve().relative_to(Path(REPO_ROOT).resolve()).as_posix()
        except ValueError:  # outside the repo — fall back to the name alone
            key = path.name
        entries.append((key, path))
    for key, path in sorted(entries):
        h.update(key.encode())  # keyed by path, so a rename is a change
        h.update(path.read_bytes())
    return h.hexdigest()


def _content_digest(config_path: str | Path | None = None) -> str:
    """Hash the content the model sees, plus the config ACTUALLY LOADED.

    Hashing config.release.yaml unconditionally was wrong: --config defaults to the
    gitignored config.yaml, so a run could load one config and fingerprint another.
    """
    files: list[Path] = []
    for rel, glob in _CONTENT_TREES:
        root = REPO_ROOT / rel
        if root.exists():
            files.extend(p for p in root.rglob(glob) if p.is_file())
    extra = [REPO_ROOT / "pyproject.toml"]
    if config_path:
        p = Path(config_path)
        extra.append(p if p.is_absolute() else REPO_ROOT / p)
    files.extend(p for p in extra if p.exists())
    return _hash_paths(files)


def _manifest_contents() -> dict:
    """Stored, not just hashed — a verdict should be readable without a checkout."""
    out = {}
    for rel in _MANIFEST_PATHS:
        path = REPO_ROOT / rel
        out[rel] = json.loads(path.read_text()) if path.exists() else None
    return out


def _l2_gate_contract(case_paths) -> list:
    """Which L2 criteria are required — normalized, so only policy moves the hash.

    Sorted by id and reduced to `(id, required)`: rewording a question or reordering
    the rubric is a measurement change (`cases_sha256` carries it), while adding,
    renaming or demoting a criterion changes what PASS means and belongs in the gate.
    """
    out = []
    for p in sorted(str(x) for x in case_paths):
        try:
            case = yaml.safe_load(Path(p).read_text()) or {}
        except Exception:  # noqa: BLE001 — an unreadable case is the validator's job
            out.append([Path(p).stem, "unreadable"])
            continue
        if case.get("layer") != 2:
            continue
        entries = sorted((e.get("id"), e.get("required") is True)
                         for e in runner.l2_rubric(case) if isinstance(e, dict))
        if entries:
            out.append([Path(p).stem, entries])
    return out


def _gate_digest(config: dict, case_paths=()) -> str:
    """Everything that decides PASS/FAIL, separate from what was measured.

    Split out so --recompile can prove it changed only the decision rule and not
    the measurement it is re-deciding.

    Package F put two more inputs behind the gate: `l2_rubric`, which resolves which
    criteria exist, and each L2 case's `required` flags. Both are hashed elsewhere —
    in `harness_sha256` and `cases_sha256` — but those are MEASUREMENT keys, and
    `recompile_verdict` never rebuilds the fingerprint. Left out here, gutting the
    accessor or demoting a criterion would leave this digest byte-identical while the
    gate genuinely changed, which is the same way `_GATE_EPS` once invalidated the
    before/after claim --recompile stamps.
    """
    import inspect
    h = hashlib.sha256()
    h.update(json.dumps(config.get("thresholds") or runner.DEFAULT_THRESHOLDS,
                        sort_keys=True).encode())
    h.update(json.dumps(runner.DEFAULT_THRESHOLDS, sort_keys=True).encode())
    h.update(json.dumps(_l2_gate_contract(case_paths), sort_keys=True).encode())

    # The whole gate, not just its entry point. case_gate calls _meets and _threshold but
    # does not define them, so hashing case_gate alone left the comparison logic and the
    # epsilon outside the digest — changing _GATE_EPS provably did not move it, which
    # silently invalidated the before/after claim --recompile stamps.
    # compile_verdict is included because it decides verdicts too: it assigns UNMEASURED
    # and owns the whole rollup (any FAIL -> FAIL; else any UNMEASURED -> UNMEASURED).
    # Replacing it wholesale previously left this digest byte-identical.
    # `runner.l2_rubric`, not `scorer.l2_rubric`: they are the same object today, but
    # case_gate resolves the name in runner's namespace, and hashing the other binding
    # would miss a rebinding of the one the gate actually calls. `_load_ledger_case` is
    # here because compile_verdict depends on it for the contract, exactly as case_gate
    # depends on _meets.
    for fn in (runner.case_gate, runner._meets, runner._threshold,
               runner.l2_rubric, runner.criterion_status,
               _load_ledger_case, compile_verdict):
        try:
            h.update(inspect.getsource(fn).encode())
        except (OSError, TypeError):  # source unavailable (frozen/zipped)
            h.update(f"{fn.__name__}:source-unavailable".encode())
    h.update(repr(runner._GATE_EPS).encode())
    return h.hexdigest()


def _eval_python() -> str:
    """The interpreter that actually runs generated L3 code.

    Must mirror scorer.py:673 exactly, default included — recording or probing a
    different interpreter than the one that ran the code is the bug this exists to fix.
    """
    return os.environ.get("EVAL_PYTHON", "python3")


def _executor_versions() -> dict:
    """The interpreters that ran generated L3 code — NOT this orchestrator.

    scorer.py shells out via EVAL_PYTHON, so sys.version describes the wrong process.
    The 2026-07-18 sweep recorded 3.9.6 while the documented environment was 3.12.13.
    """
    out = {"orchestrator_python": sys.version.split()[0]}
    eval_python = _eval_python()
    out["eval_python_path"] = str(eval_python)
    out["eval_python_pinned"] = bool(os.environ.get("EVAL_PYTHON"))
    try:
        proc = subprocess.run([str(eval_python), "-c",
                               "import sys;print('.'.join(map(str,sys.version_info[:3])))"],
                              capture_output=True, text=True, timeout=30)
        out["eval_python"] = proc.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        out["eval_python"] = "unknown"
    try:
        proc = subprocess.run(["Rscript", "--version"], capture_output=True,
                              text=True, timeout=30)
        out["rscript"] = (proc.stdout or proc.stderr).strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        out["rscript"] = "unknown"
    return out


def _declared_python_packages() -> list[str]:
    """Distribution names from pyproject's dependency arrays only.

    Scoped deliberately: a loose regex over the whole file picks up the project's own
    `version = "0.3.2"` string and records it as a package.
    """
    path = REPO_ROOT / "pyproject.toml"
    if not path.exists():
        return []
    names: set[str] = set()
    try:
        import tomllib
        data = tomllib.loads(path.read_text())
        arrays = [data.get("project", {}).get("dependencies", [])]
        arrays += list(data.get("project", {})
                       .get("optional-dependencies", {}).values())
    except Exception:  # noqa: BLE001 — tomllib is 3.11+; fall back to the arrays by regex
        text = path.read_text()
        arrays = [re.findall(r'"([^"]+)"', block) for block in
                  re.findall(r"(?ms)^\s*(?:dependencies|[a-z]+)\s*=\s*\[(.*?)^\]", text)]
    for arr in arrays:
        for spec in arr:
            base = re.split(r"[<>=!~;\s\[]", spec, 1)[0].strip()
            if base and not base.lower().startswith("everyday-causal-skills"):
                names.add(base)
    return sorted(names)


def _declared_dependency_versions() -> dict:
    """Versions of the DECLARED dependencies only.

    Not a full `pip freeze` / `installed.packages()`: hashing every locally installed
    package would make two identical release environments look different over things
    the eval never touches.
    """
    out: dict = {"python": {}, "r": {}}
    # Probe through EVAL_PYTHON, NOT in-process. The orchestrator is 3.12.13 while the
    # executor defaults to bare "python3" (3.9.6 here), so an in-process importlib call
    # reported packages the interpreter running L3 code does not have.
    # Import names are resolved from each distribution's own top_level.txt, never guessed
    # from the distribution name. This repo's signature bug is exactly that mismatch:
    # distribution `pycausalimpact` provides module `causalimpact`, and a different
    # distribution literally named `causalimpact` also exists. Guessing reports a healthy
    # package as broken and vice versa.
    probe = (
        "import json, sys, importlib\n"
        "from importlib.metadata import distribution, version, PackageNotFoundError\n"
        "names = json.loads(sys.argv[1])\n"
        "out = {}\n"
        "for n in names:\n"
        "    try: dist = version(n)\n"
        "    except PackageNotFoundError: dist = 'not-installed'\n"
        "    mods = []\n"
        "    try:\n"
        "        d = distribution(n)\n"
        "        top = d.read_text('top_level.txt') or ''\n"
        "        mods = [m.strip() for m in top.split() if m.strip()]\n"
        "        if not mods:\n"
        "            seen = []\n"
        "            for f in (d.files or []):\n"
        "                parts = str(f).split('/')\n"
        "                head = parts[0]\n"
        "                if head.endswith(('.dist-info', '.data', '.egg-info')): continue\n"
        "                if head.startswith(('_', '.')) or head == '__pycache__': continue\n"
        "                cand = head[:-3] if head.endswith('.py') else head\n"
        "                if len(parts) > 1 or head.endswith('.py'):\n"
        "                    if cand not in seen: seen.append(cand)\n"
        "            mods = seen\n"
        "    except Exception: pass\n"
        "    if not mods: mods = [n.replace('-', '_')]\n"
        # Really import. find_spec only proves discoverability, and the case that matters
        # is exactly the one it gets wrong: system Python can FIND causalimpact while
        # importing it raises (scipy dropped signal.gaussian).
        "    ok = {}\n"
        "    for m in mods:\n"
        "        try:\n"
        "            importlib.import_module(m); ok[m] = True\n"
        "        except Exception: ok[m] = False\n"
        "    out[n] = {'dist': dist, 'modules': ok,\n"
        "              'importable': bool(ok) and all(ok.values())}\n"
        "print(json.dumps(out))\n"
    )
    try:
        proc = subprocess.run(
            [_eval_python(), "-c", probe, json.dumps(_declared_python_packages())],
            capture_output=True, text=True, timeout=300)
        out["python"] = json.loads(proc.stdout.strip())
    except Exception as exc:  # noqa: BLE001
        out["python"] = {"error": f"unavailable: {type(exc).__name__}"}

    r_pkgs = sorted({pkg for path in (REPO_ROOT / "evals" / "cases").rglob("*.yaml")
                     for pkg in _r_requires(path)})
    if r_pkgs:
        expr = ("cat(paste(sapply(c(%s), function(p) "
                "tryCatch(paste0(p,'=',as.character(packageVersion(p))), "
                "error=function(e) paste0(p,'=missing'))), collapse='\\n'))"
                % ",".join(f"'{p}'" for p in r_pkgs))
        try:
            proc = subprocess.run(["Rscript", "-e", expr], capture_output=True,
                                  text=True, timeout=120)
            for line in proc.stdout.strip().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    out["r"][k] = v
        except Exception:  # noqa: BLE001
            out["r"] = {"error": "unavailable"}
    return out


def _r_requires(case_path: Path) -> list[str]:
    try:
        case = yaml.safe_load(case_path.read_text()) or {}
    except Exception:  # noqa: BLE001
        return []
    if str(case.get("language", "")).lower() != "r":
        return []
    return [str(p) for p in (case.get("requires") or [])]


def build_fingerprint(config: dict, case_paths: list[str],
                      config_path: str | None = None) -> dict:
    """Identify the exact code and config a verdict describes.

    A verdict is only evidence for the tree it was measured against, so resume
    refuses to mix results from different trees.
    """
    h = hashlib.sha256()
    for p in sorted(case_paths):
        h.update(Path(p).read_bytes())

    # The scoring code is part of what a verdict measures. Editing scorer.py
    # mid-sweep silently changes the meaning of results already collected, and
    # the commit hash won't move while the tree is dirty.
    harness = hashlib.sha256()
    for name in _HARNESS_FILES:
        harness.update((Path(__file__).parent / name).read_bytes())

    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty_paths": [ln[3:] for ln in _git("status", "--porcelain").splitlines()],
        "cases_sha256": h.hexdigest(),
        "harness_sha256": harness.hexdigest(),
        "content_sha256": _content_digest(config_path),
        "gate_sha256": _gate_digest(config, case_paths),
        "config_path": str(config_path) if config_path else None,
        "case_count": len(case_paths),
        # Requested vs invoked. What actually served the request is recorded by the
        # runner where it is observable; a "resolved" ID written into the input config
        # would prove nothing.
        "model": config.get("model", "unknown"),
        "model_alias_invoked": scorer._MODEL_MAP.get(config.get("model", ""), "sonnet"),
        "judge_model": config.get("judge", {}).get("model", "unknown"),
        "claude_cli": _claude_version(),
        "manifests": _manifest_contents(),
        "interpreters": _executor_versions(),
        "dependencies": _declared_dependency_versions(),
        "python": sys.version.split()[0],
    }


#: Everything that has to hold constant for two results to describe the same measurement.
#: `gate_sha256` is deliberately absent — a corrected gate is exactly what --recompile
#: exists to re-apply to measurements already collected.
MEASUREMENT_KEYS = (
    "commit", "cases_sha256", "harness_sha256", "content_sha256", "config_path",
    "model", "model_alias_invoked", "judge_model", "claude_cli", "manifests",
    "interpreters", "dependencies",
)


def fingerprint_mismatch(a: dict, b: dict) -> list[str]:
    """Differences that make two runs non-comparable (dirty paths excluded)."""
    return [k for k in MEASUREMENT_KEYS if a.get(k) != b.get(k)]


# --- Ledger ---

def save_ledger(ledger: dict, path: Path) -> None:
    """Atomic write — a sweep killed mid-write must not lose its ledger."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2))
    os.replace(tmp, path)


def load_ledger(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def _is_v1_ledger(ledger: dict) -> bool:
    """A ledger from before run-slot checkpointing has no per-slot state, so
    it cannot be resumed under the new harness — only a fresh sweep can."""
    return any("slots" not in c for c in ledger["cases"].values())


def _reset_abandoned_slots(ledger: dict) -> int:
    """A case left `running` on disk means the sweep died mid-wave for it —
    it is not actually still running after a restart. Its still-`pending`
    slots (never rewritten mid-wave; only run_case_slots's returned patch is
    ever applied, by the coordinator, once a whole case's slots finish) are
    already exactly what a resume should retry — this only needs to fix the
    case-level status so the pending-case filter picks it back up. Returns
    the number of cases touched."""
    touched = 0
    for case in ledger["cases"].values():
        if case["status"] == "running":
            case["status"] = "pending"
            touched += 1
    return touched


def new_ledger(sweep_id: str, case_paths: list[str], runs: int, config: dict,
               max_requeues: int, config_path: str | None = None) -> dict:
    cases = {}
    for p in case_paths:
        rel = str(Path(p).relative_to(REPO_ROOT)) if Path(p).is_absolute() else p
        layer = int(Path(p).parent.name[len("layer"):])
        cases[Path(p).stem] = {
            "path": rel, "layer": layer, "status": "pending", "attempts": 0,
            "runs_valid": None, "runs_total": None,
            "aggregate": None, "verdict": None, "invalid_reasons": [],
            "updated": None,
            "slots": [{"status": "pending", "result": None} for _ in range(runs)],
        }
    return {
        "sweep_id": sweep_id,
        "started": datetime.now().isoformat(timespec="seconds"),
        "runs_per_case": runs,
        "max_requeues": max_requeues,
        "thresholds": config.get("thresholds") or runner.DEFAULT_THRESHOLDS,
        "fingerprint": build_fingerprint(config, case_paths, config_path),
        "cases": cases,
    }


# --- Health canaries ---

def canary_judge(config: dict) -> None:
    """The judge must answer two questions with known answers, correctly."""
    answers = scorer._call_judge(
        "Answer each question.\n\nQuestions:\n"
        "1. Is 2 + 2 equal to 4?\n"
        "2. Is 2 + 2 equal to 5?",
        2, config, label="CANARY")
    if answers != [True, False]:
        raise RuntimeError(f"judge canary returned {answers}, expected [True, False]")


def canary_skill(config: dict) -> None:
    """The plain skill path must return non-empty text on exit 0."""
    proc = subprocess.run(
        ["claude", "-p", "Reply with exactly: OK",
         "--model", scorer._MODEL_MAP.get(config.get("model", ""), "sonnet"),
         "--output-format", "text", "--tools", "",
         "--no-session-persistence", "--setting-sources", "local"],
        capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"skill canary exited {proc.returncode}: {proc.stderr[:300]}")
    if not proc.stdout.strip():
        raise RuntimeError("skill canary returned empty stdout")


RELEASE_CONFIG = "evals/config.release.yaml"
_MIN_EVAL_PYTHON = (3, 10)  # pycausalarima requires >= 3.10


def _l3_python_requires() -> list[str]:
    """Import names declared by `requires:` on Python-executed L3 cases."""
    req: set[str] = set()
    layer3 = REPO_ROOT / "evals" / "cases" / "layer3"
    for path in sorted(layer3.glob("*.yaml")):
        try:
            case = yaml.safe_load(path.read_text()) or {}
        except Exception:  # noqa: BLE001
            continue
        if str(case.get("language", "python")).lower() != "python":
            continue
        req.update(str(m) for m in (case.get("requires") or []))
    return sorted(req)


def validate_eval_python() -> list[str]:
    """The executor must exist, be recent enough, and IMPORT every declared L3 package.

    Importability, not distribution presence: system Python carries a `causalimpact
    0.2.6` distribution whose import raises (scipy removed `signal.gaussian`), while the
    venv's `pycausalimpact` imports *as* `causalimpact`. Metadata lies in both directions,
    so a metadata-only check would call a broken interpreter healthy.
    """
    interp = _eval_python()
    problems: list[str] = []
    probe = (
        "import json, sys, importlib\n"
        "names = json.loads(sys.argv[1])\n"
        "res = {'version': list(sys.version_info[:3]), 'imports': {}}\n"
        "for n in names:\n"
        "    try:\n"
        "        importlib.import_module(n); res['imports'][n] = 'ok'\n"
        "    except Exception as e:\n"
        "        res['imports'][n] = f'{type(e).__name__}: {e}'[:120]\n"
        "print(json.dumps(res))\n"
    )
    required = _l3_python_requires()
    try:
        proc = subprocess.run([interp, "-c", probe, json.dumps(required)],
                              capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        return [f"EVAL_PYTHON={interp!r} does not exist or is not executable"]
    except Exception as exc:  # noqa: BLE001
        return [f"EVAL_PYTHON={interp!r} could not be probed: {exc}"]

    if proc.returncode != 0 or not proc.stdout.strip():
        return [f"EVAL_PYTHON={interp!r} failed to run: {proc.stderr.strip()[:200]}"]

    res = json.loads(proc.stdout.strip())
    version = tuple(res["version"])
    if version < _MIN_EVAL_PYTHON:
        problems.append(
            f"EVAL_PYTHON={interp!r} is Python {'.'.join(map(str, version))}; "
            f"L3 needs >= {'.'.join(map(str, _MIN_EVAL_PYTHON))}")
    broken = {n: why for n, why in res["imports"].items() if why != "ok"}
    if broken:
        detail = "; ".join(f"{n} ({why})" for n, why in sorted(broken.items()))
        problems.append(
            f"EVAL_PYTHON={interp!r} cannot import {len(broken)} declared L3 "
            f"package(s): {detail}")
    return problems


def release_preconditions(config: dict, config_path: str | None = None) -> list[str]:
    """Conditions a *release* verdict must meet. Local diagnostic sweeps ignore these.

    Things a verdict cannot honestly describe otherwise:

    1. A dirty tree. The commit hash does not move while files are uncommitted, so a
       verdict would name a commit that is not what ran. Recorded before, never enforced —
       sweep-2026-07-18_151814 produced a verdict with 45 dirty paths.
    2. An untracked config. --config defaults to the gitignored config.yaml, so evidence
       could be measured against settings nobody can inspect afterwards.
    3. An executor that cannot actually run L3 code (see validate_eval_python).
    """
    problems = []
    dirty = [ln[3:] for ln in _git("status", "--porcelain").splitlines()]
    if dirty:
        shown = ", ".join(sorted(dirty)[:5])
        problems.append(
            f"working tree is dirty ({len(dirty)} path(s): {shown}"
            f"{'…' if len(dirty) > 5 else ''}) — a release verdict must describe a commit")

    if config_path is not None:
        resolved = Path(config_path)
        resolved = resolved if resolved.is_absolute() else REPO_ROOT / resolved
        if resolved != (REPO_ROOT / RELEASE_CONFIG):
            problems.append(
                f"--config is {config_path!r}; a release verdict must be measured against "
                f"the tracked {RELEASE_CONFIG} so the settings are inspectable afterwards")

    if not os.environ.get("EVAL_PYTHON"):
        problems.append(
            "EVAL_PYTHON is not set — scorer.py falls back to bare 'python3'. Set it to the "
            "interpreter that has the declared dependencies (see evals/README.md)")
    problems.extend(validate_eval_python())
    return problems


def preflight(config: dict, attempts: int = 3, wait: float = 60.0,
              strict_warnings: bool = False) -> None:
    """Refuse to burn a measurement window on a degraded environment."""
    problems = validate_tree()
    if problems:
        raise RuntimeError(
            f"{len(problems)} case(s) fail schema validation; run evals/validate_cases.py")

    # Dead metadata was previously surfaced only by running validate_cases.py by hand,
    # so a release verdict could be built over cases carrying keys nothing reads.
    warnings = warn_tree()
    if warnings:
        if strict_warnings:
            raise RuntimeError(
                f"{len(warnings)} case warning(s) block a release verdict:\n  "
                + "\n  ".join(warnings[:10]))
        print(f"  {len(warnings)} case warning(s) (non-blocking):")
        for w in warnings[:5]:
            print(f"    {w}")

    last = None
    for attempt in range(1, attempts + 1):
        try:
            canary_judge(config)
            canary_skill(config)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  canary attempt {attempt}/{attempts} failed: {e}")
            if attempt < attempts and wait:
                time.sleep(wait)
    raise RuntimeError(f"preflight failed after {attempts} attempts: {last}")


# --- Case execution: run-slot checkpointing ---
#
# Each case keeps `runs` independently checkpointed slots. A single slot that
# times out or crashes no longer discards the other, already-valid slots — the
# failure mode that left 176 of 180 cases UNMEASURED. An accepted slot
# ("status": "done") is never re-run; a requeue wave only re-attempts the
# slots still missing.

def run_one_slot(name: str, slot_index: int, config_path: str, sweep_dir: Path) -> dict | None:
    """Run exactly one measurement for a case in its own runner process.

    Returns the raw run record (valid or invalid — either is a real
    measurement) or None if nothing was measured at all (crash, timeout, no
    output), which means this slot must be retried.
    """
    out_json = sweep_dir / f"case-{name}-slot{slot_index}.json"
    cmd = [sys.executable, "evals/runner.py", "--case", name,
           "--runs", "1", "--config", config_path,
           "--json-out", str(out_json), "--no-history"]
    try:
        proc = scorer.run_subprocess_grouped(cmd, timeout=SLOT_TIMEOUT, cwd=REPO_ROOT)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        return None

    # Exit 2 means runner.py measured the run and it was invalid (e.g. the
    # skill call failed after its own retries) — that is still a real
    # measurement, not a crash, so it must not be silently discarded.
    if exit_code not in (0, 2) or not out_json.exists():
        return None

    data = json.loads(out_json.read_text())
    cases = data.get("cases") or []
    records = cases[0].get("run_records") if cases else None
    return records[0] if records else None


def _load_ledger_case(name: str, case_entry: dict) -> dict:
    """Load the case a ledger entry points at, asserting the two agree.

    D9: aggregation and gating both read the case contract (`expected.must_flag`,
    the L2 rubric, the L4 dimensions). Handing either a stripped stand-in silently
    reverts to a weaker rule, so the real file is loaded — and checked against the
    ledger, since a mismatched path would substitute one case's contract for
    another's just as quietly.
    """
    case = runner.load_case(str(REPO_ROOT / case_entry["path"]))
    if Path(case_entry["path"]).stem != name or case["layer"] != case_entry["layer"]:
        raise ValueError(
            f"ledger/case mismatch for {name!r}: case_entry declares path="
            f"{case_entry['path']!r} layer={case_entry['layer']!r}, but the file "
            f"there is named {Path(case_entry['path']).stem!r} with layer="
            f"{case.get('layer')!r}"
        )
    return case


def _unmeasured_reason(case: dict, agg: dict) -> str | None:
    """Why an L2 case with required criteria came back UNMEASURED.

    A verdict that just says UNMEASURED sends the reader back to the ledger to
    work out whether the data is old or the run is incomplete; those need
    different fixes (recompile vs. rerun), so the verdict says which.

    Classified through `runner.criterion_status`, the same helper the gate uses.
    Deciding here from the stored `rate` instead would leave a criterion the gate
    rejected on its counts with no reason printed at all — UNMEASURED and silent.
    """
    required = [e["id"] for e in runner.l2_rubric(case)
                if isinstance(e, dict) and e.get("required") is True and e.get("id")]
    if not required:
        return None
    criteria = agg.get("rubric_criteria")
    if not criteria:
        return ("ledger predates the per-criterion rubric gate — no per-question "
                "answers on file; rerun this case, do not recompile")

    runs_valid = agg.get("runs_valid") or 0
    buckets: dict[str, list[str]] = {}
    for cid in required:
        status, _ = runner.criterion_status(criteria.get(cid), runs_valid)
        if status != "ok":
            buckets.setdefault(status, []).append(cid)

    parts = []
    if buckets.get("missing"):
        parts.append("no answer block at all: " + ", ".join(sorted(buckets["missing"])))
    if buckets.get("partial"):
        # Split by whether anyone answered: nothing at all points at the judge or the
        # rubric wiring, a partial count at specific runs.
        never = sorted(c for c in buckets["partial"]
                       if not (criteria.get(c) or {}).get("answered"))
        some = sorted(c for c in buckets["partial"] if c not in never)
        if never:
            parts.append("never answered in any valid run: " + ", ".join(never))
        for cid in some:
            crit = criteria[cid]
            parts.append(f"{cid} answered in only {crit.get('answered')} of "
                         f"{runs_valid} valid runs")
    if buckets.get("inconsistent"):
        parts.append(
            "counts contradict themselves (untrustworthy ledger, rerun — do not "
            "recompile): " + ", ".join(sorted(buckets["inconsistent"])))
    return "; ".join(parts) if parts else None


def run_case_slots(name: str, case_entry: dict, config_path: str, sweep_dir: Path,
                   runs: int, thresholds: dict | None) -> dict:
    """Run only a case's not-yet-accepted slots. Pure: reads `case_entry` but
    never mutates it or the shared ledger — the caller applies the returned
    patch. Returns a ledger entry patch (status, slots, and — once every slot
    is accepted — aggregate/verdict/invalid_reasons)."""
    slots = [dict(s) for s in (case_entry.get("slots") or
                               [{"status": "pending", "result": None} for _ in range(runs)])]

    for i, slot in enumerate(slots):
        if slot["status"] == "done":
            continue
        result = run_one_slot(name, i, config_path, sweep_dir)
        # A slot is accepted only once it produces a VALID measurement — the
        # same invariant the old whole-case design enforced (runs_valid ==
        # runs_total before "measured"). Exit 2 (measured, but invalid — e.g.
        # a skill_timeout that survived its own retry budget) is real
        # information, not a crash, so keep its reason for diagnosis, but it
        # must not be mistaken for an accepted slot: a case with 4 valid runs
        # and 1 timeout is not a trustworthy 4/5 PASS, it is still missing a
        # measurement and must be retried next wave.
        if result is not None and not result.get("invalid"):
            slot["status"] = "done"
            slot["result"] = result
        else:
            slot["status"] = "pending"  # still missing — next requeue wave retries it
            slot["last_error"] = result.get("invalid") if result else None

    accepted = [s["result"] for s in slots if s["status"] == "done"]
    if len(accepted) != len(slots):
        pending_reasons = sorted({s["last_error"] for s in slots
                                  if s["status"] != "done" and s.get("last_error")})
        return {
            "status": "invalid", "slots": slots,
            "invalid_reasons": pending_reasons,
            "error": f"only {len(accepted)} of {len(slots)} runs measured",
        }

    case = _load_ledger_case(name, case_entry)
    agg = runner.aggregate(accepted, case)
    return {
        "status": "done", "slots": slots, "aggregate": agg,
        "verdict": runner.case_gate(case, agg, thresholds),
        "invalid_reasons": sorted({r["invalid"] for r in accepted if r.get("invalid")}),
        "runs_valid": agg.get("runs_valid"), "runs_total": agg.get("runs_total"),
        "error": None,
    }


def run_wave(ledger: dict, names: list[str], config_path: str, sweep_dir: Path,
             ledger_path: Path, workers: int, release: bool = False) -> bool:
    """Run one wave. Returns True if release fail-fast stopped it early.

    Dispatch is incremental — at most `workers` cases are ever in flight, and
    a new one is only submitted right before it starts, re-checking the
    fail-fast flag each time. Submitting everything upfront (the previous
    design) let the pool's own internal queue hand a worker its next case
    before the coordinator had processed the FAIL that should have stopped
    it — "no further cases will be started" was only usually true. This
    makes it true by construction: nothing is ever queued past the point the
    coordinator has seen the FAIL.
    """
    runs = ledger["runs_per_case"]
    thresholds = ledger["thresholds"]
    done = {"n": 0}
    total = len(names)
    stop = {"flag": False}

    # Coordinator marks intent before dispatch, so a crash mid-wave leaves an
    # accurate "running" marker on disk for the next resume to reset.
    for name in names:
        ledger["cases"][name]["status"] = "running"
    save_ledger(ledger, ledger_path)

    def work(name):
        # Pure worker: no ledger mutation, no save_ledger — coordinator-only
        # writes, so concurrent cases can never race on the shared ledger dict
        # or its on-disk file.
        case_entry = ledger["cases"][name]
        return name, run_case_slots(name, case_entry, config_path, sweep_dir, runs, thresholds)

    remaining = list(names)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        in_flight: dict = {}

        def submit_next():
            while remaining and len(in_flight) < workers:
                if release and stop["flag"]:
                    return  # fail-fast: nothing new gets queued once it's set
                name = remaining.pop(0)
                in_flight[pool.submit(work, name)] = name

        submit_next()
        while in_flight:
            finished, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in finished:
                in_flight.pop(future)
                name, patch = future.result()
                ledger["cases"][name]["attempts"] += 1
                patch["updated"] = datetime.now().isoformat(timespec="seconds")
                ledger["cases"][name].update(patch)
                save_ledger(ledger, ledger_path)
                done["n"] += 1
                entry = ledger["cases"][name]
                flag = entry["verdict"] if entry["status"] == "done" else "UNMEASURED"
                print(f"  [{done['n']}/{total}] {name}: {flag}"
                      + (f" ({entry['error']})" if entry.get("error") else ""))
                if (release and not stop["flag"]
                        and entry["status"] == "done" and entry.get("verdict") == "FAIL"):
                    stop["flag"] = True
                    print(f"  release fail-fast: {name} measured FAIL — no further "
                          f"cases will be submitted (diagnostic sweeps are unaffected)")
            submit_next()

    return stop["flag"]


# --- Verdict ---

def compile_verdict(ledger: dict) -> dict:
    """Apply the gate to every case and roll up per layer.

    Each entry's case file is loaded and handed to the gate, because since
    Package F the L2 contract lives in the case (which criteria are required),
    not in the stored aggregate. A `--recompile` against a pre-F ledger therefore
    reports UNMEASURED for those cases instead of quietly grading them under the
    old rule — the same failure mode D9 fixed on the aggregation path.
    """
    thresholds = ledger.get("thresholds")
    per_case, layers = {}, {}
    for name, entry in sorted(ledger["cases"].items()):
        layer = entry["layer"]
        legacy_reason = None
        if entry["status"] == "done" and entry.get("aggregate"):
            case = _load_ledger_case(name, entry)
            verdict = runner.case_gate(case, entry["aggregate"], thresholds)
            if verdict == "UNMEASURED":
                legacy_reason = _unmeasured_reason(case, entry["aggregate"])
        else:
            verdict = "UNMEASURED"
        per_case[name] = {
            "layer": layer, "verdict": verdict, "attempts": entry["attempts"],
            "runs_valid": entry.get("runs_valid"), "runs_total": entry.get("runs_total"),
            "aggregate": entry.get("aggregate"),
            "invalid_reasons": entry.get("invalid_reasons", []),
            "error": entry.get("error"),
            "unmeasured_reason": legacy_reason,
        }
        bucket = layers.setdefault(layer, {"PASS": 0, "FAIL": 0, "UNMEASURED": 0})
        bucket[verdict] += 1

    totals = {"PASS": 0, "FAIL": 0, "UNMEASURED": 0}
    for bucket in layers.values():
        for k in totals:
            totals[k] += bucket[k]

    if totals["FAIL"]:
        overall = "FAIL"
    elif totals["UNMEASURED"]:
        overall = "UNMEASURED"
    else:
        overall = "PASS"

    return {
        "sweep_id": ledger["sweep_id"],
        "started": ledger["started"],
        "compiled": datetime.now().isoformat(timespec="seconds"),
        "runs_per_case": ledger["runs_per_case"],
        "fingerprint": ledger["fingerprint"],
        "overall": overall,
        "totals": totals,
        "layers": {str(k): v for k, v in sorted(layers.items())},
        "cases": per_case,
    }


def render_verdict_md(verdict: dict) -> str:
    fp = verdict["fingerprint"]
    lines = [
        f"# Eval sweep verdict — {verdict['overall']}",
        "",
        f"**Sweep**: {verdict['sweep_id']} · started {verdict['started']} · "
        f"compiled {verdict['compiled']}",
        f"**Runs per case**: {verdict['runs_per_case']}",
        f"**Commit**: `{fp['commit']}` ({fp['branch']})"
        + ("  ⚠️ working tree dirty" if fp["dirty_paths"] else ""),
        f"**Model**: {fp['model']}"
        + (f" (invoked as `{fp['model_alias_invoked']}`)" if fp.get("model_alias_invoked") else "")
        + f" · judge {fp['judge_model']} · {fp['claude_cli']}",
        f"**Cases**: {fp['case_count']} (sha256 `{fp['cases_sha256'][:16]}…`)",
    ]
    if fp.get("content_sha256"):
        lines.append(
            f"**Content** (skills/references/templates/data/fixtures): "
            f"`{fp['content_sha256'][:16]}…` · **gate** `{(fp.get('gate_sha256') or '')[:16]}…`")
    interp = fp.get("interpreters") or {}
    if interp:
        lines.append(
            f"**Interpreters**: L3 code ran under Python {interp.get('eval_python','?')} "
            f"(`{interp.get('eval_python_path','?')}`) · orchestrator "
            f"{interp.get('orchestrator_python','?')} · {interp.get('rscript','?')}")
    manifests = fp.get("manifests") or {}
    if manifests:
        versions = sorted({
            (m.get("version") or (m.get("plugins") or [{}])[0].get("version"))
            for m in manifests.values() if m})
        lines.append(f"**Plugin version**: {', '.join(v for v in versions if v)} "
                     f"({len(manifests)} manifests)")
    if verdict.get("recompiled_from"):
        lines.append(
            f"**Recompiled** from `{verdict['recompiled_from']}` — no models were run. "
            f"Thresholds from *{verdict.get('thresholds_source')}*; gate "
            f"`{(verdict.get('gate_sha256_before') or 'n/a')[:12]}` → "
            f"`{(verdict.get('gate_sha256_after') or 'n/a')[:12]}`")
    lines += [
        "",
        f"**Totals**: {verdict['totals']['PASS']} PASS · "
        f"{verdict['totals']['FAIL']} FAIL · "
        f"{verdict['totals']['UNMEASURED']} UNMEASURED",
        "",
        "| Layer | PASS | FAIL | UNMEASURED |",
        "|-------|------|------|------------|",
    ]
    for layer, bucket in verdict["layers"].items():
        lines.append(f"| L{layer} | {bucket['PASS']} | {bucket['FAIL']} "
                     f"| {bucket['UNMEASURED']} |")

    problems = {n: c for n, c in verdict["cases"].items() if c["verdict"] != "PASS"}
    if problems:
        lines += ["", "## Cases not passing", "",
                  "| Case | Layer | Verdict | Valid runs | Attempts | Detail |",
                  "|------|-------|---------|------------|----------|--------|"]
        for name, c in sorted(problems.items(), key=lambda kv: (kv[1]["verdict"], kv[0])):
            valid = f"{c['runs_valid']}/{c['runs_total']}" if c["runs_valid"] is not None else "—"
            detail = c.get("error") or ", ".join(c.get("invalid_reasons") or []) or ""
            lines.append(f"| {name} | L{c['layer']} | {c['verdict']} | {valid} "
                         f"| {c['attempts']} | {detail} |")
    else:
        lines += ["", "Every case passed its layer gate with a full set of valid runs."]

    lines += ["", "## All cases", "",
              "| Case | Layer | Verdict | Valid runs |",
              "|------|-------|---------|------------|"]
    for name, c in sorted(verdict["cases"].items(), key=lambda kv: (kv[1]["layer"], kv[0])):
        valid = f"{c['runs_valid']}/{c['runs_total']}" if c["runs_valid"] is not None else "—"
        lines.append(f"| {name} | L{c['layer']} | {c['verdict']} | {valid} |")

    # Package F: per-criterion L2 rubric results. The JSON stays the machine-readable
    # source; this table is what makes a FAIL diagnosable without opening it — which
    # criterion missed, at what rate, and whether it was gating at all.
    rubric_cases = {name: (c.get("aggregate") or {}).get("rubric_criteria")
                    for name, c in verdict["cases"].items()}
    rubric_cases = {name: crit for name, crit in rubric_cases.items() if crit}
    if rubric_cases:
        lines += ["", "## L2 rubric criteria", "",
                  "| Case | Criterion | Status | Rate | Question |",
                  "|------|-----------|--------|------|----------|"]
        for name in sorted(rubric_cases):
            runs_valid = ((verdict["cases"][name].get("aggregate") or {})
                          .get("runs_valid") or 0)
            for cid, crit in sorted(rubric_cases[name].items()):
                status = "required" if crit.get("required") else "informational"
                # Classified by the gate's own helper, not by reading `rate`: a block
                # the gate rejected must never print as a bare `4/5`, which is what
                # trusting a stored rate over contradictory counts would produce.
                state, crate = runner.criterion_status(crit, runs_valid)
                if state == "ok":
                    rate = f"{crit.get('passed', 0)}/{crit.get('valid', 0)}"
                elif state == "partial":
                    # "nobody answered" and "answered in only some runs" are both gaps,
                    # and reporting either as a rate over the runs that answered would
                    # hide it.
                    # "4 of 5", not "4/5": the slash form is the pass rate one column
                    # over, and a gap must not be mistakable for a score.
                    rate = f"— ({crit.get('answered', 0)} of {runs_valid} runs answered)"
                else:
                    rate = (f"— ({state}: passed {crit.get('passed')}, answered "
                            f"{crit.get('answered')}, valid {crit.get('valid')}, "
                            f"{runs_valid} valid runs)")
                lines.append(f"| {name} | {cid} | {status} | {rate} "
                             f"| {crit.get('question', '')} |")

    unmeasured = {name: c["unmeasured_reason"] for name, c in verdict["cases"].items()
                  if c.get("unmeasured_reason")}
    if unmeasured:
        lines += ["", "### Why these are UNMEASURED", ""]
        lines.extend(f"- **{name}**: {reason}" for name, reason in sorted(unmeasured.items()))

    # D1: rubric criteria a case's triage moved out of grading because they
    # cannot be reached in one turn (response_contract: first_turn). Reported
    # here so they stay visible as a migration list — never scored, never
    # judged, never counted toward the verdict above.
    deferred = {name: (c.get("aggregate") or {}).get("deferred_rubric")
               for name, c in verdict["cases"].items()}
    deferred = {name: d for name, d in deferred.items() if d}
    if deferred:
        lines += ["", "## Deferred criteria (reported, not graded)", ""]
        for name in sorted(deferred):
            lines.append(f"- **{name}**:")
            lines.extend(f"  - {q}" for q in deferred[name])

    return "\n".join(lines) + "\n"


def recompile_verdict(ledger_path: Path, config: dict) -> tuple[dict, Path]:
    """Re-derive a verdict from an existing ledger. Runs no models.

    Gate logic lives in code, so a corrected gate can be re-applied to measurements
    already collected. Writes a NUMBERED SIBLING and never touches the original: the
    first verdict is the record of what the gate said at the time, and a recompile is
    a new opinion about the same measurement. Both have to survive for the change to
    be auditable, which the previous in-place overwrite made impossible.
    """
    ledger_path = Path(ledger_path)
    ledger = load_ledger(ledger_path)
    sweep_dir = ledger_path.parent
    source_sha = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    gate_before = ledger.get("fingerprint", {}).get("gate_sha256")

    # compile_verdict reads ledger["thresholds"], which the sweep snapshotted at start.
    # A threshold correction is a gate correction, so recompiling must apply it — but
    # only when the caller actually supplies one, and it is recorded either way. Without
    # this the stamped gate hash would describe a gate that was never applied.
    ledger = dict(ledger)
    if config.get("thresholds"):
        ledger["thresholds"] = config["thresholds"]
        thresholds_source = "config"
    else:
        thresholds_source = "ledger"

    verdict = compile_verdict(ledger)

    verdict["recompiled_from"] = str(ledger_path)
    verdict["source_ledger_sha256"] = source_sha
    verdict["thresholds_source"] = thresholds_source
    verdict["thresholds_applied"] = ledger.get("thresholds") or runner.DEFAULT_THRESHOLDS
    verdict["gate_sha256_before"] = gate_before
    # The contract as APPLIED: the same case files compile_verdict just loaded, so the
    # stamped hash describes the gate that actually ran, not the one the sweep recorded.
    verdict["gate_sha256_after"] = _gate_digest(
        {"thresholds": ledger.get("thresholds")},
        [REPO_ROOT / e["path"] for e in ledger["cases"].values() if e.get("path")])
    verdict["measurement_unchanged"] = True  # no models were run

    # Check BOTH extensions: an orphan .md (from an interrupted write) would otherwise
    # be silently overwritten by the next recompile.
    n = 1
    while ((sweep_dir / f"verdict-recompiled-{n}.json").exists()
           or (sweep_dir / f"verdict-recompiled-{n}.md").exists()):
        n += 1
    (sweep_dir / f"verdict-recompiled-{n}.json").write_text(json.dumps(verdict, indent=2))
    out_md = sweep_dir / f"verdict-recompiled-{n}.md"
    out_md.write_text(render_verdict_md(verdict))
    return verdict, out_md


def _write_release_history(ledger: dict, verdict: dict, version: str, config: dict,
                           hist_path: Path | None = None) -> None:
    """One consolidated HISTORY row for a green release sweep.

    Until now no sweep ever wrote one: every slot runs `runner.py --no-history`
    (each slot is one run of one case, not a result), and the release writer
    emitted only verdict.md/json. The row is reconstructed from the ledger here,
    once, after the verdict is known.

    Only a PASS is recorded. A row for a sweep that failed its gate would read
    later as evidence the version was measured and fine. Each case is loaded from
    disk rather than stubbed, because `save_history` re-applies `case_gate` for
    its pass column and a stripped case would let that column disagree with the
    verdict — the drift D9 already had to fix once.
    """
    if verdict["overall"] != "PASS":
        return
    if not version.startswith("v"):
        version = f"v{version}"

    cases = []
    for name, entry in sorted(ledger["cases"].items()):
        agg = entry.get("aggregate")
        if agg:
            cases.append({"case": _load_ledger_case(name, entry), "aggregate": agg})

    fp = ledger.get("fingerprint") or {}
    results = {"runs": ledger.get("runs_per_case"), "backend": "cli", "cases": cases}
    cfg = {"model": fp.get("model") or config.get("model") or "unknown",
           "thresholds": ledger.get("thresholds") or config.get("thresholds") or {}}
    notes = f"sweep {ledger['sweep_id']} · RC {fp.get('commit', 'unknown')}"
    runner.save_history(results, cfg, notes=notes, hist_path=hist_path,
                        release_version=version)


def _write_release_verdict(verdict: dict, version: str) -> Path:
    """Write the committable verdict at repo level.

    .gitignore un-ignores evals/results/verdict-v*.md and verdict-v*.json; everything
    inside sweep-*/ stays local evidence.
    """
    if not version.startswith("v"):
        version = f"v{version}"
    out_dir = REPO_ROOT / "evals" / "results"
    md, js = out_dir / f"verdict-{version}.md", out_dir / f"verdict-{version}.json"
    js.write_text(json.dumps(verdict, indent=2))
    md.write_text(render_verdict_md(verdict))
    print(f"Release verdict: {md}")
    print(f"                 {js}")
    return md


# --- Entry point ---

def select_cases(args) -> list[str]:
    if args.cases:
        spec = args.cases
        names = (Path(spec[1:]).read_text().split() if spec.startswith("@")
                 else [n.strip() for n in spec.split(",") if n.strip()])
        paths = []
        for n in names:
            paths.extend(runner.collect_cases(case_name=n))
        return paths
    return runner.collect_cases(layer=args.only_layer)


def main() -> int:
    parser = argparse.ArgumentParser(description="everyday-causal-skills eval sweep")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--config", default="evals/config.yaml")
    parser.add_argument("--cases", type=str, default="",
                        help="comma-separated case names, or @file with one per line")
    parser.add_argument("--only-layer", type=int, choices=[0, 1, 2, 3, 4, 5])
    parser.add_argument("--resume", type=str, default="",
                        help="path to a ledger.json from an interrupted sweep")
    parser.add_argument("--max-requeues", type=int, default=2)
    parser.add_argument("--workers", type=int, default=3,
                        help="concurrent cases; keep modest to avoid rate limiting")
    parser.add_argument("--skip-preflight", action="store_true",
                        help="skip canaries (for offline testing only)")
    parser.add_argument("--recompile", type=str, default="",
                        help="LOCAL DIAGNOSTIC ONLY: re-derive a verdict from an existing "
                             "ledger without running anything. Cannot produce a release "
                             "verdict — see --release-verdict")
    parser.add_argument("--release-verdict", type=str, default="",
                        help="vX.Y.Z — write the committable verdict to "
                             "evals/results/verdict-vX.Y.Z.{md,json} and enforce "
                             "release preconditions (clean tree, EVAL_PYTHON set, "
                             "zero case warnings)")
    parser.add_argument("--notes", type=str, default="")
    args = parser.parse_args()

    release = args.release_verdict

    # Checked before ANY file is written, and before the config is even loaded.
    #
    # A recompile re-decides a measurement it did not take, from a ledger that lives under
    # the gitignored evals/results/sweep-*/ — an unsigned, editable local file whose hash is
    # computed only when it is handed over. Validating its self-reported provenance would
    # authenticate nothing, and would still permit lowering a threshold after seeing an
    # outcome. Release criteria are frozen before measurement, so a release verdict comes
    # only from a fresh sweep or a resume whose full fingerprint matches.
    if args.recompile and release:
        print("--recompile cannot produce a release verdict.")
        print("  A recompile re-decides an existing measurement, and its source ledger is "
              "an ignored, editable local file that nothing authenticates.")
        print("  Recompile is a local diagnostic. If a gate defect turns up after "
              "measurement, fix it and re-run the release sweep from a frozen worktree.")
        return 2

    config = runner.load_config(args.config)

    if release:
        blockers = release_preconditions(config, args.config)
        if blockers:
            print("Refusing to build a release verdict:")
            for b in blockers:
                print(f"  - {b}")
            return 3

    if args.recompile:
        verdict, out_md = recompile_verdict(Path(args.recompile), config)
        t = verdict["totals"]
        changed = verdict["gate_sha256_before"] != verdict["gate_sha256_after"]
        print(f"Recompiled {verdict['sweep_id']}: {verdict['overall']} — "
              f"{t['PASS']} PASS · {t['FAIL']} FAIL · {t['UNMEASURED']} UNMEASURED")
        print(f"  gate changed: {changed} · measurement re-run: no")
        print(f"Verdict: {out_md} (original untouched)")
        return 0 if verdict["overall"] == "PASS" else (1 if t["FAIL"] else 2)

    if args.resume:
        ledger_path = Path(args.resume)
        ledger = load_ledger(ledger_path)
        sweep_dir = ledger_path.parent
        if _is_v1_ledger(ledger):
            print("Refusing to resume: this ledger predates run-slot checkpointing "
                  "(no per-slot state) and cannot be safely resumed under the new "
                  "harness. Start a fresh sweep instead.")
            return 3
        current = build_fingerprint(config, [str(REPO_ROOT / c["path"])
                                             for c in ledger["cases"].values()],
                                    args.config)
        drift = fingerprint_mismatch(ledger["fingerprint"], current)
        if drift:
            print(f"Refusing to resume: {', '.join(drift)} changed since this sweep started.")
            print("A verdict must describe one tree. Start a fresh sweep instead.")
            return 3
        reset = _reset_abandoned_slots(ledger)
        if reset:
            print(f"Resuming: {reset} case(s) had a slot still marked running when "
                  f"the sweep stopped — reset to pending for this attempt.")
            save_ledger(ledger, ledger_path)
        print(f"Resuming {ledger['sweep_id']} from {ledger_path}")
    else:
        case_paths = select_cases(args)
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        sweep_id = f"sweep-{ts}_pid{os.getpid()}"
        sweep_dir = REPO_ROOT / "evals" / "results" / sweep_id
        sweep_dir.mkdir(parents=True, exist_ok=True)
        ledger = new_ledger(sweep_id, case_paths, args.runs, config,
                            args.max_requeues, args.config)
        ledger_path = sweep_dir / "ledger.json"
        save_ledger(ledger, ledger_path)
        print(f"Sweep {sweep_id}: {len(case_paths)} case(s) × {args.runs} run(s)")
        print(f"Ledger: {ledger_path}")

    if not args.skip_preflight:
        print("Preflight…")
        try:
            preflight(config, strict_warnings=bool(release))
        except Exception as e:  # noqa: BLE001
            print(f"PREFLIGHT FAILED: {e}")
            print(f"Nothing was measured. Resume with --resume {ledger_path}")
            return 3
        print("  judge and skill path healthy")

    pending = [n for n, c in ledger["cases"].items() if c["status"] != "done"]
    wave = 0
    while pending and wave <= ledger["max_requeues"]:
        if wave:
            print(f"\nRequeue wave {wave}: {len(pending)} case(s) that did not measure")
            if not args.skip_preflight:
                try:
                    preflight(config)
                except Exception as e:  # noqa: BLE001
                    print(f"PREFLIGHT FAILED before requeue: {e}")
                    break
        else:
            print(f"\nWave 0: {len(pending)} case(s), {args.workers} at a time")
        fail_fast = run_wave(ledger, sorted(pending), args.config, sweep_dir, ledger_path,
                             args.workers, release=bool(release))
        pending = [n for n, c in ledger["cases"].items() if c["status"] != "done"]
        wave += 1
        if fail_fast:
            print("\nRelease fail-fast: a case already measured FAIL, so the rest of "
                  "the sweep would only spend budget proving nothing new — stopping. "
                  "Diagnostic sweeps (no --release-verdict) are unaffected.")
            break

    for name in pending:  # exhausted requeues
        ledger["cases"][name]["status"] = "gave_up"
    save_ledger(ledger, ledger_path)

    # Re-check immediately before compiling. A clean tree is NOT sufficient: committing
    # mid-sweep leaves the tree clean and moves the commit hash, so the only honest check
    # is rebuilding the whole fingerprint and comparing it to what the ledger recorded.
    if release:
        blockers = release_preconditions(config, args.config)
        current = build_fingerprint(config,
                                    [str(REPO_ROOT / c["path"])
                                     for c in ledger["cases"].values()],
                                    args.config)
        drift = fingerprint_mismatch(ledger["fingerprint"], current)
        if blockers or drift:
            print("\nRefusing to compile a release verdict:")
            for b in blockers:
                print(f"  - {b}")
            if drift:
                print(f"  - the tree changed mid-sweep: {', '.join(drift)}")
            # Deliberately NOT offering --recompile: it re-decides an existing
            # measurement, and these runs were collected across changing inputs. There is
            # no verdict to salvage, only a measurement to discard.
            print(f"\nThese measurements span more than one tree and cannot become "
                  f"evidence. Raw results remain in {ledger_path} for diagnosis; "
                  f"re-measure from a clean checkout.")
            return 3

    verdict = compile_verdict(ledger)
    (sweep_dir / "verdict.json").write_text(json.dumps(verdict, indent=2))
    (sweep_dir / "verdict.md").write_text(render_verdict_md(verdict))

    t = verdict["totals"]
    print(f"\n{verdict['overall']} — {t['PASS']} PASS · {t['FAIL']} FAIL · "
          f"{t['UNMEASURED']} UNMEASURED")
    print(f"Verdict: {sweep_dir / 'verdict.md'}")
    if release:
        _write_release_verdict(verdict, release)
        _write_release_history(ledger, verdict, release, config)

    if verdict["overall"] == "PASS":
        return 0
    return 1 if t["FAIL"] else 2


if __name__ == "__main__":
    sys.exit(main())
