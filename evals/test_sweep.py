"""Unit tests for the sweep orchestrator's pure logic (ledger, verdict, resume).
Run: python3 evals/test_sweep.py   (from repo root)

The subprocess and canary layers are deliberately not exercised here — they need
a live `claude` CLI. Everything that decides a verdict is tested offline.
"""
import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sweep  # noqa: E402
from sweep import (  # noqa: E402
    compile_verdict,
    fingerprint_mismatch,
    load_ledger,
    render_verdict_md,
    save_ledger,
)


def _entry(layer, status="done", verdict_agg=None, attempts=1, valid=5, total=5):
    return {
        "path": f"evals/cases/layer{layer}/x.yaml", "layer": layer, "status": status,
        "attempts": attempts, "runs_valid": valid, "runs_total": total,
        "runner_exit": 0, "aggregate": verdict_agg, "verdict": None,
        "invalid_reasons": [], "updated": "2026-07-18T09:00:00",
    }


def _ledger(cases):
    return {
        "sweep_id": "sweep-test", "started": "2026-07-18T08:00:00", "runs_per_case": 5,
        "max_requeues": 2, "thresholds": None,
        "fingerprint": {"commit": "abc123", "branch": "main", "dirty_paths": [],
                        "cases_sha256": "deadbeef", "harness_sha256": "cafe",
                        "case_count": len(cases),
                        "model": "m", "judge_model": "j", "claude_cli": "v1",
                        "python": "3.9"},
        "cases": cases,
    }


_L1_PASS = {"runs_valid": 5, "runs_total": 5, "accuracy": 0.95,
            "false_positives": 0, "rate": 0.95}
_L1_FAIL = {"runs_valid": 5, "runs_total": 5, "accuracy": 0.4,
            "false_positives": 0, "rate": 0.4}
_UNMEASURED = {"runs_valid": 0, "runs_total": 5, "rate": None}


def test_verdict_all_pass():
    v = compile_verdict(_ledger({"a": _entry(1, verdict_agg=_L1_PASS),
                                 "b": _entry(1, verdict_agg=_L1_PASS)}))
    assert v["overall"] == "PASS", v["overall"]
    assert v["totals"] == {"PASS": 2, "FAIL": 0, "UNMEASURED": 0}, v["totals"]


def test_verdict_fail_dominates_unmeasured():
    v = compile_verdict(_ledger({
        "a": _entry(1, verdict_agg=_L1_FAIL),
        "b": _entry(1, status="gave_up", verdict_agg=_UNMEASURED, valid=0),
    }))
    assert v["overall"] == "FAIL", v
    assert v["totals"]["FAIL"] == 1 and v["totals"]["UNMEASURED"] == 1, v["totals"]


def test_verdict_unmeasured_when_no_real_failures():
    v = compile_verdict(_ledger({
        "a": _entry(1, verdict_agg=_L1_PASS),
        "b": _entry(1, status="gave_up", verdict_agg=_UNMEASURED, valid=0),
    }))
    assert v["overall"] == "UNMEASURED", v


def test_gave_up_case_is_unmeasured_never_fail():
    # A case that never measured must not be reported as a skill failure.
    v = compile_verdict(_ledger({"a": _entry(4, status="gave_up",
                                             verdict_agg=None, valid=0)}))
    assert v["cases"]["a"]["verdict"] == "UNMEASURED", v["cases"]["a"]


def test_verdict_rolls_up_per_layer():
    v = compile_verdict(_ledger({
        "a": _entry(0, verdict_agg={"runs_valid": 5, "runs_total": 5,
                                    "trigger_correct": 5, "rate": 1.0}),
        "b": _entry(1, verdict_agg=_L1_FAIL),
        "c": _entry(1, verdict_agg=_L1_PASS),
    }))
    assert v["layers"]["0"] == {"PASS": 1, "FAIL": 0, "UNMEASURED": 0}, v["layers"]
    assert v["layers"]["1"] == {"PASS": 1, "FAIL": 1, "UNMEASURED": 0}, v["layers"]


def test_verdict_markdown_names_failing_cases():
    v = compile_verdict(_ledger({"good": _entry(1, verdict_agg=_L1_PASS),
                                 "bad": _entry(1, verdict_agg=_L1_FAIL)}))
    md = render_verdict_md(v)
    assert "Cases not passing" in md
    assert "| bad |" in md
    assert "FAIL" in md


def test_verdict_markdown_flags_dirty_tree():
    ledger = _ledger({"a": _entry(1, verdict_agg=_L1_PASS)})
    ledger["fingerprint"]["dirty_paths"] = ["evals/scorer.py"]
    md = render_verdict_md(compile_verdict(ledger))
    assert "dirty" in md.lower(), md


# --- Ledger durability and resume safety ---

def test_verdict_reflects_corrected_gate_without_rerunning():
    # A gate fix must be applicable to measurements already collected. Same ledger,
    # different threshold -> different verdict, no models re-run.
    ledger = _ledger({"borderline": _entry(
        1, verdict_agg={"runs_valid": 5, "runs_total": 5, "accuracy": 0.75,
                        "false_positives": 0, "rate": 0.75})})
    assert compile_verdict(ledger)["overall"] == "FAIL"
    ledger["thresholds"] = {"layer1": {"accuracy": 0.7}}
    assert compile_verdict(ledger)["overall"] == "PASS"


def test_ledger_round_trip():
    ledger = _ledger({"a": _entry(1, verdict_agg=_L1_PASS)})
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ledger.json"
        save_ledger(ledger, p)
        assert load_ledger(p) == ledger
        assert not p.with_suffix(".tmp").exists(), "temp file left behind"


def test_resume_rejects_changed_code_or_cases():
    base = _ledger({})["fingerprint"]
    assert fingerprint_mismatch(base, dict(base)) == []
    assert "commit" in fingerprint_mismatch(base, {**base, "commit": "other"})
    assert "cases_sha256" in fingerprint_mismatch(base, {**base, "cases_sha256": "x"})
    assert "judge_model" in fingerprint_mismatch(base, {**base, "judge_model": "z"})
    # Editing scorer.py mid-sweep changes what the numbers mean, even on one commit.
    assert "harness_sha256" in fingerprint_mismatch(base, {**base, "harness_sha256": "x"})


def test_resume_tolerates_dirty_path_changes():
    # Editing an unrelated file mid-sweep should not invalidate a resume.
    base = _ledger({})["fingerprint"]
    other = {**base, "dirty_paths": ["README.md"]}
    assert fingerprint_mismatch(base, other) == []


# --- Requeue selection ---

def test_only_unmeasured_cases_are_pending():
    ledger = _ledger({
        "measured_pass": _entry(1, verdict_agg=_L1_PASS),
        "measured_fail": _entry(1, verdict_agg=_L1_FAIL),
        "not_measured": _entry(1, status="invalid", verdict_agg=_UNMEASURED, valid=0),
    })
    pending = [n for n, c in ledger["cases"].items() if c["status"] != "done"]
    # A real miss is a result; only the unmeasured case is worth re-running.
    assert pending == ["not_measured"], pending


def test_run_one_case_marks_partial_measurement_invalid(tmp=None):
    # 4 of 5 runs valid is not a measurement of the case — it must requeue.
    with tempfile.TemporaryDirectory() as d:
        sweep_dir = Path(d)
        (sweep_dir / "case-x.json").write_text(json.dumps({
            "cases": [{"name": "x", "layer": 1, "verdict": "PASS",
                       "aggregate": {"runs_valid": 4, "runs_total": 5, "rate": 0.9},
                       "invalid_reasons": ["judge_error"]}]}))

        class _Proc:
            returncode, stderr, stdout = 0, "", ""

        real = sweep.subprocess.run
        sweep.subprocess.run = lambda *a, **k: _Proc()
        try:
            patch = sweep.run_one_case("x", 5, "evals/config.yaml", sweep_dir)
        finally:
            sweep.subprocess.run = real
        assert patch["status"] == "invalid", patch
        assert "4 of 5" in patch["error"], patch


# --- Release preconditions (Package C) ---

def _with_git(stub):
    """Swap sweep._git for a stub; returns a restore callable."""
    real = sweep._git
    sweep._git = stub
    return lambda: setattr(sweep, "_git", real)


def _clean_git(*args):
    return "" if args[0] == "status" else "abc123"


def test_release_refuses_dirty_tree():
    restore = _with_git(lambda *a: " M evals/scorer.py\n M skills/causal-dag/SKILL.md"
                        if a[0] == "status" else "abc123")
    os.environ["EVAL_PYTHON"] = "/tmp/py"
    try:
        problems = sweep.release_preconditions({})
    finally:
        restore()
        os.environ.pop("EVAL_PYTHON", None)
    assert any("dirty" in p for p in problems), problems
    assert any("2 path" in p for p in problems), problems


def test_release_refuses_unset_eval_python():
    """scorer.py:673 falls back to bare 'python3'. On this machine that is the 3.9.6
    system interpreter, not the venv holding every declared dependency."""
    restore = _with_git(_clean_git)
    os.environ.pop("EVAL_PYTHON", None)
    try:
        problems = sweep.release_preconditions({})
    finally:
        restore()
    assert any("EVAL_PYTHON" in p for p in problems), problems


#: The interpreter running these tests — NOT a hardcoded .venv path.
#: `.venv` is gitignored, so it does not exist in a fresh `git worktree`, on CI, or on
#: another machine. Pinning to it made these tests pass only in the original checkout,
#: which the frozen-worktree release procedure would have tripped over immediately.
_VENV_PY = sys.executable
_RELEASE_CFG = "evals/config.release.yaml"


def test_release_passes_when_clean_pinned_and_using_the_release_config():
    restore = _with_git(_clean_git)
    os.environ["EVAL_PYTHON"] = _VENV_PY
    try:
        assert sweep.release_preconditions({}, _RELEASE_CFG) == []
    finally:
        restore()
        os.environ.pop("EVAL_PYTHON", None)


def test_release_refuses_the_untracked_local_config():
    """--config defaults to the gitignored config.yaml, so evidence could be measured
    against settings nobody can inspect afterwards."""
    restore = _with_git(_clean_git)
    os.environ["EVAL_PYTHON"] = _VENV_PY
    try:
        problems = sweep.release_preconditions({}, "evals/config.yaml")
    finally:
        restore()
        os.environ.pop("EVAL_PYTHON", None)
    assert any("config.release.yaml" in p for p in problems), problems


def test_eval_python_validation_rejects_a_nonexistent_interpreter():
    real = os.environ.get("EVAL_PYTHON")
    os.environ["EVAL_PYTHON"] = "/nonexistent/python"
    try:
        problems = sweep.validate_eval_python()
    finally:
        os.environ.pop("EVAL_PYTHON", None)
        if real:
            os.environ["EVAL_PYTHON"] = real
    assert any("does not exist" in p for p in problems), problems


def test_eval_python_validation_rejects_an_interpreter_missing_l3_packages():
    """Importability, not metadata. System Python carries a `causalimpact 0.2.6`
    distribution whose import raises (scipy dropped signal.gaussian), while the venv's
    `pycausalimpact` imports *as* `causalimpact` — metadata lies in both directions."""
    real = os.environ.get("EVAL_PYTHON")
    os.environ["EVAL_PYTHON"] = "python3"      # bare system interpreter
    try:
        problems = sweep.validate_eval_python()
    finally:
        os.environ.pop("EVAL_PYTHON", None)
        if real:
            os.environ["EVAL_PYTHON"] = real
    # Either too old, or missing declared imports — both are disqualifying.
    assert problems, "bare python3 must not qualify as the L3 executor"


def test_dependency_probe_resolves_real_import_names():
    """Import names come from each distribution's own metadata, never guessed from the
    distribution name. This repo's signature bug is that mismatch: distribution
    `pycausalimpact` provides module `causalimpact`, and a *different* distribution
    literally named `causalimpact` also exists. Guessing reports healthy packages as
    broken (scikit-learn -> `scikit_learn`) and broken ones as healthy."""
    real = os.environ.get("EVAL_PYTHON")
    os.environ["EVAL_PYTHON"] = _VENV_PY
    try:
        probed = sweep._declared_dependency_versions()["python"]
    finally:
        os.environ.pop("EVAL_PYTHON", None)
        if real:
            os.environ["EVAL_PYTHON"] = real

    if "error" in probed:
        return  # venv unavailable in this environment; nothing to assert
    assert probed["pycausalimpact"]["modules"] == {"causalimpact": True}, \
        probed["pycausalimpact"]
    assert "sklearn" in probed["scikit-learn"]["modules"], probed["scikit-learn"]
    broken = {k: v for k, v in probed.items()
              if isinstance(v, dict) and not v.get("importable")}
    assert not broken, f"declared packages falsely reported unimportable: {broken}"


def test_probe_reports_discoverable_but_unimportable_as_not_importable():
    """`importable` must mean it imports, not that find_spec found something. System
    Python can FIND causalimpact while importing it raises — the exact case the field
    exists to catch, and the one find_spec gets wrong."""
    probe_src = None
    real = os.environ.get("EVAL_PYTHON")
    os.environ["EVAL_PYTHON"] = _VENV_PY
    try:
        # A module that exists on disk but raises on import.
        with tempfile.TemporaryDirectory() as d:
            broken = Path(d) / "brokenmod.py"
            broken.write_text("raise ImportError('deliberately broken')\n")
            probe = (
                "import json, sys, importlib\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "import importlib.util as u\n"
                "found = u.find_spec('brokenmod') is not None\n"
                "try:\n"
                "    importlib.import_module('brokenmod'); imported = True\n"
                "except Exception: imported = False\n"
                "print(json.dumps({'found': found, 'imported': imported}))\n"
            )
            out = subprocess.run([_VENV_PY, "-c", probe, d],
                                 capture_output=True, text=True, timeout=120)
            probe_src = json.loads(out.stdout.strip())
    finally:
        os.environ.pop("EVAL_PYTHON", None)
        if real:
            os.environ["EVAL_PYTHON"] = real

    assert probe_src["found"] is True, "precondition: the module must be discoverable"
    assert probe_src["imported"] is False, "precondition: importing it must fail"
    # The production probe uses import_module, so it classifies this as unimportable.
    assert "importlib.import_module(m)" in inspect.getsource(
        sweep._declared_dependency_versions), \
        "the dependency probe must really import, not just find_spec"


def test_content_digest_follows_the_config_actually_loaded():
    """Hashing config.release.yaml unconditionally meant a run could load config.yaml
    and fingerprint a file it never read."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "evals").mkdir(parents=True)
        a, b = root / "evals" / "cfg_a.yaml", root / "evals" / "cfg_b.yaml"
        a.write_text("model: one\n")
        b.write_text("model: two\n")
        real = sweep.REPO_ROOT
        sweep.REPO_ROOT = root
        try:
            assert sweep._content_digest("evals/cfg_a.yaml") != \
                   sweep._content_digest("evals/cfg_b.yaml")
            assert sweep._content_digest(None) != sweep._content_digest("evals/cfg_a.yaml")
        finally:
            sweep.REPO_ROOT = real


def test_measurement_keys_cover_the_new_provenance():
    """A clean tree is not proof the fingerprint held: committing mid-sweep leaves the
    tree clean and moves the commit. Everything that shapes a measurement must be
    compared, not just the code."""
    for key in ("interpreters", "dependencies", "manifests", "config_path",
                "model_alias_invoked", "content_sha256"):
        assert key in sweep.MEASUREMENT_KEYS, key
    assert "gate_sha256" not in sweep.MEASUREMENT_KEYS, \
        "a corrected gate is what --recompile exists to apply"
    base = _ledger({})["fingerprint"]
    assert "interpreters" in fingerprint_mismatch(
        base, {**base, "interpreters": {"eval_python": "3.9.6"}})


def test_local_sweep_is_unaffected_by_release_preconditions():
    """A dirty tree is the normal debugging mode and must keep working locally —
    the gate applies only when --release-verdict asks for evidence."""
    restore = _with_git(lambda *a: " M x.py" if a[0] == "status" else "abc")
    try:
        assert sweep.release_preconditions({}), "should block a release"
    finally:
        restore()
    # compile_verdict is what a local sweep uses, and it never consults the gate.
    v = compile_verdict(_ledger({"a": _entry(1, verdict_agg=_L1_PASS)}))
    assert v["overall"] == "PASS", v


# --- Fingerprint: measurement vs gate (Package C) ---

def test_gate_digest_changes_with_thresholds_only():
    a = sweep._gate_digest({"thresholds": {"layer1": {"accuracy": 0.8}}})
    b = sweep._gate_digest({"thresholds": {"layer1": {"accuracy": 0.7}}})
    assert a != b, "threshold change must move the gate digest"
    assert a == sweep._gate_digest({"thresholds": {"layer1": {"accuracy": 0.8}}})


def test_gate_digest_covers_the_whole_gate_not_just_its_entry_point():
    """case_gate calls _meets and _threshold but does not define them. Hashing only
    case_gate left the comparison logic and the epsilon outside the digest — changing
    _GATE_EPS provably did not move it, which voids the before/after claim recompile
    stamps."""
    import runner
    baseline = sweep._gate_digest({})

    real_eps = runner._GATE_EPS
    runner._GATE_EPS = 0.5          # would silently reclassify every borderline case
    try:
        assert sweep._gate_digest({}) != baseline, \
            "_GATE_EPS must be part of the gate digest"
    finally:
        runner._GATE_EPS = real_eps

    real_meets = runner._meets
    runner._meets = lambda v, t: True   # a gate that passes everything
    try:
        assert sweep._gate_digest({}) != baseline, \
            "_meets must be part of the gate digest"
    finally:
        runner._meets = real_meets

    assert sweep._gate_digest({}) == baseline, "digest must be stable once restored"


def test_gate_digest_excluded_from_resume_drift():
    """--recompile exists to re-apply a corrected gate to existing measurements, so a
    changed gate must not block resume the way changed measurement inputs do."""
    base = _ledger({})["fingerprint"]
    assert fingerprint_mismatch(base, {**base, "gate_sha256": "different"}) == []


def test_resume_rejects_changed_skill_content():
    """skills/references/templates ARE the system prompt. Editing one mid-sweep changes
    what is being measured, and the commit hash will not move while the tree is dirty."""
    base = _ledger({})["fingerprint"]
    assert "content_sha256" in fingerprint_mismatch(
        base, {**base, "content_sha256": "edited"})


def test_content_digest_is_independent_of_checkout_location():
    """The frozen-worktree release procedure measures identical content at a different
    absolute path. Hashing absolute paths made that produce a different digest, silently
    defeating the very procedure it was meant to support."""
    def _build(root: Path):
        (root / "skills" / "causal-dag").mkdir(parents=True)
        (root / "skills" / "causal-dag" / "SKILL.md").write_text("# same content\n")
        (root / "references").mkdir()
        (root / "references" / "lessons.md").write_text("lesson\n")

    real = sweep.REPO_ROOT
    try:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root_a, root_b = Path(a), Path(b)
            _build(root_a)
            _build(root_b)
            sweep.REPO_ROOT = root_a
            digest_a = sweep._content_digest()
            sweep.REPO_ROOT = root_b
            digest_b = sweep._content_digest()
    finally:
        sweep.REPO_ROOT = real
    assert digest_a == digest_b, "identical content at two roots must digest identically"


def test_gate_digest_covers_the_verdict_rollup():
    """compile_verdict assigns UNMEASURED and owns the overall rollup (any FAIL -> FAIL),
    so it decides verdicts as much as case_gate does. Replacing it wholesale previously
    left the digest byte-identical."""
    baseline = sweep._gate_digest({})
    real = sweep.compile_verdict
    sweep.compile_verdict = lambda ledger: {"overall": "PASS"}
    try:
        assert sweep._gate_digest({}) != baseline, \
            "the rollup rule must be part of the gate digest"
    finally:
        sweep.compile_verdict = real
    assert sweep._gate_digest({}) == baseline


def test_content_digest_notices_an_edited_skill():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "skills" / "causal-dag").mkdir(parents=True)
        skill = root / "skills" / "causal-dag" / "SKILL.md"
        skill.write_text("# original")
        real = sweep.REPO_ROOT
        sweep.REPO_ROOT = root
        try:
            before = sweep._content_digest()
            skill.write_text("# edited")
            after = sweep._content_digest()
        finally:
            sweep.REPO_ROOT = real
        assert before != after, "editing a SKILL.md must move content_sha256"


def test_declared_packages_excludes_the_project_version_string():
    """A loose regex over pyproject picks up `version = "0.3.2"` and records it as a
    package named 0.3.2 — which is what the first implementation did."""
    names = sweep._declared_python_packages()
    assert names, "expected some declared packages"
    assert not any(n[0].isdigit() for n in names), names
    assert not any(n.startswith("everyday-causal-skills") for n in names), names


# --- Non-destructive recompile + release verdict (Package C) ---

def test_release_verdict_writes_both_formats():
    v = compile_verdict(_ledger({"a": _entry(1, verdict_agg=_L1_PASS)}))
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "evals" / "results").mkdir(parents=True)
        real = sweep.REPO_ROOT
        sweep.REPO_ROOT = root
        try:
            sweep._write_release_verdict(v, "0.6.0")  # bare version gets the v
        finally:
            sweep.REPO_ROOT = real
        md = root / "evals" / "results" / "verdict-v0.6.0.md"
        js = root / "evals" / "results" / "verdict-v0.6.0.json"
        assert md.exists() and js.exists(), sorted(p.name for p in (root / "evals" / "results").iterdir())
        assert json.loads(js.read_text())["overall"] == "PASS"


def test_recompile_cannot_produce_a_release_verdict():
    """A recompile re-decides a measurement it did not take, from a ledger under the
    gitignored evals/results/sweep-*/ — an unsigned, editable local file that nothing
    authenticates. Validating its self-reported provenance would prove nothing and would
    still permit lowering a threshold after seeing the outcome (see the local-diagnostic
    test below, which does exactly that). So the flags are mutually exclusive, and the
    refusal must happen before ANY file is written."""
    with tempfile.TemporaryDirectory() as d:
        sweep_dir = Path(d)
        ledger_path = sweep_dir / "ledger.json"
        save_ledger(_ledger({"a": _entry(1, verdict_agg=_L1_PASS)}), ledger_path)

        results = Path(d) / "results"
        results.mkdir()
        real_root, real_argv = sweep.REPO_ROOT, sys.argv
        sweep.REPO_ROOT = Path(d)
        sys.argv = ["sweep.py", "--recompile", str(ledger_path),
                    "--release-verdict", "v9.9.9", "--skip-preflight"]
        try:
            code = sweep.main()
        finally:
            sweep.REPO_ROOT, sys.argv = real_root, real_argv

    assert code != 0, "combining the flags must fail"
    # Neither artifact may exist: not the release verdict, not even a recompiled sibling.
    assert not (results / "verdict-v9.9.9.md").exists()
    assert not (results / "verdict-v9.9.9.json").exists()
    assert not (sweep_dir / "verdict-recompiled-1.json").exists(), \
        "must refuse before writing anything"


def test_recompile_never_overwrites_and_numbers_each_run():
    """Exercises recompile_verdict itself as a LOCAL DIAGNOSTIC. Note this test lowers a
    threshold so a FAIL becomes PASS with no new measurement — which is precisely why a
    recompile may never become release evidence. The original verdict.json must survive,
    and a second recompile must not clobber the first."""
    borderline = _entry(1, verdict_agg={"runs_valid": 5, "runs_total": 5,
                                        "accuracy": 0.75, "false_positives": 0,
                                        "rate": 0.75})
    with tempfile.TemporaryDirectory() as d:
        sweep_dir = Path(d)
        ledger_path = sweep_dir / "ledger.json"
        save_ledger(_ledger({"borderline": borderline}), ledger_path)

        original = sweep_dir / "verdict.json"
        original.write_text('{"overall": "ORIGINAL"}')

        # Default threshold (0.8) fails 0.75.
        v1, md1 = sweep.recompile_verdict(ledger_path, {})
        assert v1["overall"] == "FAIL", v1["overall"]

        # A corrected gate flips it, with no models re-run.
        v2, md2 = sweep.recompile_verdict(ledger_path, {"thresholds": {"layer1": {"accuracy": 0.7}}})
        assert v2["overall"] == "PASS", v2["overall"]
        assert v2["measurement_unchanged"] is True

        assert md1.name == "verdict-recompiled-1.md", md1
        assert md2.name == "verdict-recompiled-2.md", md2
        assert md1.exists() and md2.exists()
        assert json.loads(original.read_text())["overall"] == "ORIGINAL", \
            "recompile must not overwrite the original verdict"
        assert v2["gate_sha256_after"] != v1["gate_sha256_after"], \
            "a changed gate must be visible in the recompiled verdict"
        assert v2["source_ledger_sha256"] == v1["source_ledger_sha256"], \
            "same measurement, so the ledger hash must match"
        assert v1["thresholds_source"] == "ledger", v1["thresholds_source"]
        assert v2["thresholds_source"] == "config", v2["thresholds_source"]


def test_recompile_records_which_thresholds_it_applied():
    """compile_verdict reads ledger['thresholds'], so a config threshold only takes
    effect if recompile substitutes it. Silently ignoring one would stamp a gate hash
    describing a gate that never ran."""
    with tempfile.TemporaryDirectory() as d:
        ledger_path = Path(d) / "ledger.json"
        ledger = _ledger({"a": _entry(1, verdict_agg=_L1_PASS)})
        ledger["thresholds"] = {"layer1": {"accuracy": 0.5}}
        save_ledger(ledger, ledger_path)

        v_ledger, _ = sweep.recompile_verdict(ledger_path, {})
        assert v_ledger["thresholds_applied"] == {"layer1": {"accuracy": 0.5}}

        v_cfg, _ = sweep.recompile_verdict(
            ledger_path, {"thresholds": {"layer1": {"accuracy": 0.99}}})
        assert v_cfg["thresholds_applied"] == {"layer1": {"accuracy": 0.99}}
        assert v_cfg["overall"] == "FAIL", "0.95 accuracy must fail a 0.99 bar"


# --- Validator warnings reach preflight (Package C) ---

def test_warn_tree_is_the_only_implementation():
    """sweep's preflight and validate_cases' main must not grow separate copies —
    that drift is exactly what made save_history disagree with case_gate."""
    from validate_cases import warn_case, warn_tree
    with tempfile.TemporaryDirectory() as d:
        cases = Path(d) / "layer2"
        cases.mkdir(parents=True)
        case = cases / "x.yaml"
        case.write_text(
            "name: x\ndescription: d\nlayer: 2\nskill: causal-dag\n"
            "user_message: u\nbogus_key: 1\nexpected:\n  must_flag: []\n")
        flat = warn_tree(Path(d))
        direct = warn_case(case)
    assert direct, "expected a dead-metadata warning"
    assert len(flat) == len(direct), (flat, direct)
    assert all(str(case) in line for line in flat), flat
    assert any("bogus_key" in line for line in flat), flat


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
