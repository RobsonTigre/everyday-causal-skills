"""Offline tests for the CLI credential dependency and how it is recorded.

Run: .venv/bin/python -m pytest evals/test_backends.py

NOTHING here contacts Anthropic. The `claude` subprocess is faked at
`run_subprocess_grouped` and at `subprocess.run`, so every assertion is about what the
harness *would* send and how it handles what comes back. A test that needed a real call
would be a test that cannot run in CI, and would quietly stop running.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner  # noqa: E402
import scorer  # noqa: E402
import sweep  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

_CFG = {"backend": "cli", "judge": {"max_attempts": 1, "retry_backoff": 0},
        "skill": {"max_attempts": 1, "retry_backoff": 0}}

_L1_CASE = {"layer": 1, "skill": "causal-planner", "name": "t",
            "user_message": "hi", "expected": {}}


# --- Fakes -------------------------------------------------------------------

class _Proc:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def _cli_reply(text=None, answers=None):
    """Shape a `claude -p --output-format json` reply."""
    result = json.dumps({"answers": answers}) if answers is not None else text
    return _Proc(json.dumps({"result": result,
                             "usage": {"input_tokens": 1, "output_tokens": 2}}))


@contextmanager
def _fake_cli(replies):
    """Serve scripted subprocess replies to both scorer and runner."""
    calls = []

    def fake(args, *a, **k):
        calls.append(args)
        item = replies[min(len(calls) - 1, len(replies) - 1)]
        if isinstance(item, BaseException):
            raise item
        return item

    real_s, real_r = scorer.run_subprocess_grouped, runner.run_subprocess_grouped
    scorer.run_subprocess_grouped = fake
    runner.run_subprocess_grouped = fake
    try:
        yield calls
    finally:
        scorer.run_subprocess_grouped = real_s
        runner.run_subprocess_grouped = real_r


@contextmanager
def _no_case_validation():
    rv, rw = sweep.validate_tree, sweep.warn_tree
    sweep.validate_tree = lambda *a, **k: []
    sweep.warn_tree = lambda *a, **k: []
    try:
        yield
    finally:
        sweep.validate_tree, sweep.warn_tree = rv, rw


# --- Backend resolution ------------------------------------------------------

def test_absent_backend_resolves_to_the_one_that_exists():
    # One backend, so nothing to guess wrong — an absent key is not an error.
    assert scorer.resolve_backend({}) == "cli"
    assert scorer.resolve_backend(None) == "cli"
    assert scorer.resolve_backend({"backend": "cli"}) == "cli"


def test_an_unimplemented_backend_is_refused_not_quietly_served_by_the_cli():
    # The failure this guards: someone writes `backend: api`, expects API billing, and
    # silently gets CLI calls on their subscription instead.
    with pytest.raises(scorer.BackendError) as e:
        scorer.resolve_backend({"backend": "api"})
    msg = str(e.value)
    assert "does not implement" in msg
    assert "deliberately not built" in msg


def test_release_config_declares_its_backend():
    cfg = yaml.safe_load((REPO / "evals" / "config.release.yaml").read_text())
    assert cfg["backend"] == "cli"
    assert scorer.resolve_backend(cfg) == "cli"


def test_release_config_carries_no_dead_keys():
    # max_tokens was only ever read by the half-built API path. With that path gone it
    # reads as a live setting while nothing consumes it — the dead-metadata problem
    # this config's own comments describe.
    cfg = yaml.safe_load((REPO / "evals" / "config.release.yaml").read_text())
    assert "max_tokens" not in cfg
    sources = "".join((REPO / "evals" / f).read_text()
                      for f in ("runner.py", "scorer.py", "sweep.py"))
    for key in cfg:
        if key in ("thresholds", "reporting_only"):
            continue
        assert f'"{key}"' in sources, f"config declares {key!r} but no code reads it"


# --- Dispatch ----------------------------------------------------------------

def test_candidate_calls_shell_out_to_claude_p():
    with _fake_cli([_cli_reply("an answer"), _cli_reply(answers=[True])]) as calls:
        out = runner.run_case_cli(dict(_L1_CASE, expected={"rubric": ["q?"]}), _CFG, 1)
    argv = calls[0]
    assert argv[0] == "claude" and argv[1] == "-p"
    assert "--system-prompt-file" in argv
    assert out[0]["response"] == "an answer"


def test_judge_calls_shell_out_with_a_json_schema():
    with _fake_cli([_cli_reply(answers=[True, False])]) as calls:
        assert scorer._call_judge("p", 2, _CFG) == [True, False]
    assert calls[0][0] == "claude"
    assert "--json-schema" in calls[0]


def test_l0_judge_shells_out_too():
    with _fake_cli([_Proc("YES\n")]) as calls:
        out = scorer._score_layer0("desc", "msg", {"should_trigger": True}, _CFG)
    assert out["triggered"] is True and out["correct"] is True
    assert calls[0][0] == "claude"


def test_no_run_record_invents_a_served_model():
    # The CLI does not report which model answered. Recording one would be a
    # provenance claim the harness cannot support.
    with _fake_cli([_cli_reply("an answer"), _cli_reply(answers=[True])]):
        out = runner.run_case_cli(dict(_L1_CASE, expected={"rubric": ["q?"]}), _CFG, 1)
    blob = json.dumps(out)
    assert "served_model" not in blob


# --- Preflight: the credential is named, not guessed --------------------------

def test_missing_executable_is_caught_before_anything_is_dispatched():
    import shutil
    real = shutil.which
    shutil.which = lambda name, *a, **k: None
    try:
        problems = sweep.backend_availability("cli")
    finally:
        shutil.which = real
    assert len(problems) == 1
    assert "`claude` executable is not on PATH" in problems[0]
    assert "authenticated Claude CLI account" in problems[0]


def test_a_logged_out_cli_explains_itself_instead_of_echoing_an_exit_code():
    # The reported symptom: `claude -p exited 1` said nothing about what was wrong.
    real = subprocess.run
    subprocess.run = lambda *a, **k: _Proc("", returncode=1, stderr="")
    try:
        with pytest.raises(RuntimeError) as e:
            sweep.canary_skill(_CFG)
    finally:
        subprocess.run = real
    msg = str(e.value)
    assert "authenticated Claude CLI account" in msg
    assert "logged-out CLI looks like" in msg
    assert "Log in outside this harness" in msg


def test_probes_never_leave_stdin_open_for_a_login_prompt():
    seen = {}
    real = subprocess.run

    def spy(*a, **k):
        seen.update(k)
        return _Proc("ok\n")

    subprocess.run = spy
    try:
        sweep.canary_skill(_CFG)
    finally:
        subprocess.run = real
    assert seen.get("stdin") == subprocess.DEVNULL


def test_static_preflight_runs_even_though_canaries_can_be_skipped():
    # --skip-preflight is a debug flag, not an authorization: it must not disable a
    # free correctness check.
    import shutil
    real = shutil.which
    shutil.which = lambda name, *a, **k: None
    try:
        with _no_case_validation():
            with pytest.raises(RuntimeError) as e:
                sweep.preflight_static(_CFG, "cli")
    finally:
        shutil.which = real
    assert "not on PATH" in str(e.value)


def test_static_preflight_makes_no_model_call():
    with _no_case_validation():
        with _fake_cli([AssertionError("static preflight must not call a model")]):
            sweep.preflight_static(_CFG, "cli")


# --- Preflight failure is zero measurements, not a verdict -------------------

def test_preflight_failure_is_zero_measurements_and_writes_no_verdict():
    import shutil
    argv, real_root = sys.argv, sweep.REPO_ROOT
    real_dep, real_exec = sweep._declared_dependency_versions, sweep._executor_versions
    real_which = shutil.which
    with tempfile.TemporaryDirectory() as d:
        try:
            sweep.REPO_ROOT = Path(d)
            sweep._declared_dependency_versions = lambda: {}
            sweep._executor_versions = lambda: {}
            shutil.which = lambda name, *a, **k: None   # no `claude` on PATH
            sys.argv = ["sweep.py", "--runs", "1", "--cases", "ab_test_large_sample"]
            buf = StringIO()
            with _no_case_validation():
                with redirect_stdout(buf):
                    code = sweep.main()
            out = buf.getvalue()
        finally:
            sys.argv, sweep.REPO_ROOT = argv, real_root
            sweep._declared_dependency_versions = real_dep
            sweep._executor_versions = real_exec
            shutil.which = real_which

        assert code == 3, out
        assert "0 cases were measured" in out
        assert "NOT a FAIL and NOT a PASS" in out
        assert "authenticated Claude CLI account" in out
        assert "no model was called" in out
        # Nothing that could later be mistaken for a result.
        assert not list(Path(d).rglob("verdict*.json")), out
        assert not list(Path(d).rglob("verdict*.md")), out
        # The ledger exists so the sweep can be resumed, every case still pending.
        ledgers = list(Path(d).rglob("ledger.json"))
        assert len(ledgers) == 1
        ledger = json.loads(ledgers[0].read_text())
        assert ledger["backend"] == "cli"
        assert all(c["status"] == "pending" for c in ledger["cases"].values())


def test_sweep_refuses_an_unimplemented_backend_before_writing_anything():
    argv = sys.argv
    try:
        sys.argv = ["sweep.py", "--runs", "1"]
        real = runner.load_config
        runner.load_config = lambda path: {"backend": "api"}
        buf = StringIO()
        try:
            with redirect_stdout(buf):
                code = sweep.main()
        finally:
            runner.load_config = real
    finally:
        sys.argv = argv
    assert code == 3
    assert "does not implement" in buf.getvalue()


def test_runner_exits_3_not_2_on_an_unusable_invocation():
    # runner.py already spends exit 2 on "this case was not measured, requeue it".
    # An unusable invocation must not share that code, or a caller retries it forever.
    # The config below asks for a backend that does not exist, so the process exits
    # during resolution and never reaches a dispatch — this test makes no model call.
    with tempfile.TemporaryDirectory() as d:
        cfg = Path(d) / "bad-backend.yaml"
        cfg.write_text("backend: api\nmodel: claude-sonnet-4-20250514\n")
        proc = subprocess.run(
            [sys.executable, "evals/runner.py", "--case", "ab_test_large_sample",
             "--config", str(cfg)],
            cwd=REPO, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 3, (proc.returncode, proc.stderr)
    assert "does not implement" in proc.stderr


# --- The dependency is recorded with the measurement -------------------------

_FP_CACHE = {}


def _fp(backend="cli"):
    """A real fingerprint, built once.

    Cached because build_fingerprint shells out to the interpreter and Rscript to
    record dependency versions — correct for a sweep, far too slow to repeat across a
    dozen assertions. Callers get a copy and treat it as read-only.
    """
    if backend not in _FP_CACHE:
        _FP_CACHE[backend] = sweep.build_fingerprint(
            {"model": "claude-sonnet-4-20250514",
             "judge": {"model": "claude-sonnet-4-20250514"}},
            [], "evals/config.release.yaml", backend)
    return dict(_FP_CACHE[backend])


def test_fingerprint_names_the_backend_and_the_cli_build():
    fp = _fp()
    assert fp["backend"] == "cli"
    assert fp["model"] == "claude-sonnet-4-20250514"
    assert fp["judge_model"] == "claude-sonnet-4-20250514"
    assert fp["claude_cli"] not in (None, "", "unknown")


def test_new_ledger_records_the_backend_at_both_levels():
    ledger = sweep.new_ledger("s", [], 1, {"backend": "cli"}, 0,
                              "evals/config.release.yaml", "cli")
    assert ledger["backend"] == "cli"
    assert ledger["fingerprint"]["backend"] == "cli"


@pytest.mark.parametrize("key,changed", [
    ("backend", "something-else"),
    ("claude_cli", "9.9.9"),
    ("model", "claude-opus-4-20250514"),
    ("judge_model", "claude-opus-4-20250514"),
])
def test_resume_is_blocked_by_backend_model_and_cli_version_drift(key, changed):
    base = _fp()
    assert key in sweep.fingerprint_mismatch(base, {**base, key: changed})


def test_a_pre_backend_ledger_is_readable_but_not_resumable():
    # Old ledgers stay diagnostic artifacts: --recompile still reads them and the
    # verdict still renders. They are just not material to extend.
    old = {k: v for k, v in _fp().items() if k != "backend"}
    assert "backend" in sweep.fingerprint_mismatch(old, _fp())

    verdict = {"sweep_id": "s", "started": "t", "compiled": "t", "runs_per_case": 5,
               "fingerprint": old, "overall": "PASS",
               "totals": {"PASS": 0, "FAIL": 0, "UNMEASURED": 0},
               "layers": {}, "cases": {}}
    assert "unrecorded (pre-backend ledger)" in sweep.render_verdict_md(verdict)


def test_verdict_names_the_backend_and_the_cli_build():
    verdict = {"sweep_id": "s", "started": "t", "compiled": "t", "runs_per_case": 5,
               "fingerprint": _fp(), "overall": "PASS",
               "totals": {"PASS": 0, "FAIL": 0, "UNMEASURED": 0},
               "layers": {}, "cases": {}}
    md = sweep.render_verdict_md(verdict)
    assert "**Backend**: cli" in md


def test_resume_refuses_a_ledger_measured_on_another_backend():
    argv = sys.argv
    with tempfile.TemporaryDirectory() as d:
        ledger_path = Path(d) / "ledger.json"
        ledger_path.write_text(json.dumps({
            "sweep_id": "s", "backend": None, "runs_per_case": 1, "max_requeues": 0,
            "thresholds": None, "fingerprint": {k: v for k, v in _fp().items()
                                                if k != "backend"},
            "cases": {"x": {"path": "evals/cases/layer1/x.yaml", "layer": 1,
                            "status": "pending", "attempts": 0,
                            "slots": [{"status": "pending", "result": None}]}}}))
        try:
            sys.argv = ["sweep.py", "--resume", str(ledger_path)]
            real = runner.load_config
            runner.load_config = lambda path: {"backend": "cli"}
            buf = StringIO()
            try:
                with redirect_stdout(buf):
                    code = sweep.main()
            finally:
                runner.load_config = real
        finally:
            sys.argv = argv
    out = buf.getvalue()
    assert code == 3, out
    assert "measured on backend None" in out and "resolves to 'cli'" in out
    assert "Start a fresh sweep" in out


def test_release_history_row_reports_the_backend_that_measured_it():
    captured = {}
    real = runner.save_history
    runner.save_history = lambda results, cfg, **k: captured.update(results)
    try:
        sweep._write_release_history(
            {"sweep_id": "s", "runs_per_case": 5, "backend": "cli", "cases": {},
             "fingerprint": {"commit": "abc"}},
            {"overall": "PASS"}, "v9.9.9", {})
    finally:
        runner.save_history = real
    assert captured["backend"] == "cli"


# --- Credentials never reach persisted artifacts -----------------------------

_SENTINEL = "sk-ant-api03-THISISNOTAREALKEYJUSTASENTINEL"


def test_auth_output_in_stderr_never_reaches_a_persisted_run_record():
    # A failing `claude -p` has its stderr spliced into the run record, and that
    # record is written verbatim into slot JSON, the ledger and the verdict.
    failing = _Proc("", returncode=1, stderr=f"auth failed for {_SENTINEL}")
    with _fake_cli([failing]):
        out = runner.run_case_cli(dict(_L1_CASE), _CFG, 1)
    blob = json.dumps(out)
    assert _SENTINEL not in blob, blob
    assert "sk-ant-***" in blob          # redacted, not deleted
    assert "auth failed" in blob         # the diagnosis survives


def test_a_redacted_error_survives_into_a_ledger_without_the_secret():
    failing = _Proc("", returncode=1, stderr=f"auth failed for {_SENTINEL}")
    with _fake_cli([failing]):
        runs = runner.run_case_cli(dict(_L1_CASE), _CFG, 1)
    agg = runner.aggregate(runs, dict(_L1_CASE))
    with tempfile.TemporaryDirectory() as d:
        ledger_path = Path(d) / "ledger.json"
        sweep.save_ledger({"sweep_id": "s", "backend": "cli", "cases": {"t": {
            "path": "evals/cases/layer1/t.yaml", "layer": 1, "status": "invalid",
            "attempts": 1, "aggregate": agg, "verdict": None,
            "invalid_reasons": [r["invalid"] for r in runs],
            "error": runs[0]["error"],
            "slots": [{"status": "pending", "result": None}]}}}, ledger_path)
        assert _SENTINEL not in ledger_path.read_text()


def test_redaction_catches_a_key_from_any_source_not_just_the_env():
    out = scorer.redact_secrets("boom sk-ant-api03-ABCDEFGHIJ end")
    assert "sk-ant-api03-ABCDEFGHIJ" not in out
    assert "sk-ant-***" in out

    old = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["ANTHROPIC_API_KEY"] = "some-other-shaped-token-value"
    try:
        assert "some-other-shaped-token-value" not in scorer.redact_secrets(
            "leaked some-other-shaped-token-value here")
    finally:
        if old is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = old


# --- Documentation must not resurrect the stale claims -----------------------

def test_no_source_file_claims_a_subscription_covers_the_api():
    # The three claims this repair deleted. `Max subscription` is matched only when it
    # is NOT part of "Claude Pro/Max subscription" — naming the tier while saying API
    # billing is separate is accurate; the point is to stop the inaccurate claim
    # coming back, not to ban the words.
    stale = [
        re.compile(r"(?<!Pro/)Max subscription"),
        re.compile(r"no API key (is )?needed"),
        re.compile(r"bills to your Claude Code subscription"),
    ]
    checked = [REPO / "evals" / p for p in
               ("scorer.py", "runner.py", "sweep.py", "README.md",
                "config.release.yaml")]
    for path in checked:
        text = path.read_text()
        for claim in stale:
            hit = claim.search(text)
            assert hit is None, f"{path.name} still claims {hit.group(0)!r}"


def test_no_source_file_still_advertises_an_api_backend():
    # The half-built path is gone; nothing should imply it is selectable.
    for name in ("runner.py", "sweep.py", "scorer.py"):
        text = (REPO / "evals" / name).read_text()
        assert "--backend api" not in text, name
        assert "anthropic.Anthropic(" not in text, name


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
