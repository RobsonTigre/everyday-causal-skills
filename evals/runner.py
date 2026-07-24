"""
Eval runner for everyday-causal-skills.

Supports two backends:
  --backend cli   (default) Uses `claude -p` — bills to your Claude Code subscription
  --backend api   Uses Anthropic SDK — requires ANTHROPIC_API_KEY, bills per token
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

from scorer import (FIXTURES_ROOT, JudgeError, l2_rubric, score_response, score_l5,
                    run_subprocess_grouped, reject_symlinks)


# Mirrors evals/config.yaml, which is untracked (local config by design).
# case_gate() is the single place the release contract is expressed:
# docs/contribution-checklist.md — "All layers must meet thresholds in evals/config.yaml."
DEFAULT_THRESHOLDS = {
    "layer0": {"trigger_accuracy": 0.9},
    "layer1": {"accuracy": 0.8},
    "layer2": {"detection_rate": 0.8, "severity_accuracy": 0.7,
               "rubric_required_rate": 0.8},
    "layer3": {"runs_without_error": 0.9, "estimation_accuracy": 0.8,
               "guard_pass_rate": 1.0},
    "layer4": {"pedagogy": 0.7, "safety": 0.7, "actionable": 0.7},
    "layer5": {"handoff_quality": 0.7},
}


def _threshold(thresholds: dict | None, layer: int, key: str):
    layer_key = f"layer{layer}"
    supplied = (thresholds or {}).get(layer_key, {})
    if key in supplied:
        return supplied[key]
    return DEFAULT_THRESHOLDS[layer_key][key]


# Aggregates are means of per-run fractions, so a case that scored exactly the bar can
# land on 0.7999999999999999 and fail a >= 0.8 gate. Observed live: small_sample_panel
# failed on this while single_treated_unit passed at an identical-looking 0.80. No real
# quality difference is smaller than this epsilon, so it can only fix false failures.
_GATE_EPS = 1e-9


def _meets(value: float, threshold: float) -> bool:
    """`value >= threshold`, immune to float representation noise."""
    return value >= threshold - _GATE_EPS


def case_gate(case: dict, agg: dict, thresholds: dict | None = None) -> str:
    """PASS / FAIL / UNMEASURED for one case, per the config.yaml contract.

    A metric that does not apply to a case (no ground truth, an unpopulated L4
    dimension) is skipped, never counted as a miss. No valid runs means the case
    was not measured — that is not a failure, it is a requeue.

    Takes the whole case, not a layer number: since Package F the L2 gate depends
    on which rubric criteria the case declares required, and D9 shipped precisely
    because a caller handed the aggregation path a stripped `{"layer": n}` dict and
    the fallback engaged in silence. Every caller must now supply the real case.
    """
    layer = case["layer"]
    rate = agg.get("rate")
    if rate is None:
        return "UNMEASURED"

    def t(key):
        return _threshold(thresholds, layer, key)

    if layer == 0:
        return "PASS" if _meets(rate, t("trigger_accuracy")) else "FAIL"
    if layer == 1:
        ok = _meets(rate, t("accuracy")) and agg.get("false_positives", 0) == 0
        return "PASS" if ok else "FAIL"
    if layer == 2:
        valid = agg["runs_valid"]
        sev = agg.get("severity_ok", 0) / valid if valid else 0.0
        ok = _meets(rate, t("detection_rate")) and _meets(sev, t("severity_accuracy"))
        # Package F: detection, severity and every required criterion are
        # independently mandatory. Nothing here averages across criteria.
        criteria = agg.get("rubric_criteria")
        required = [e["id"] for e in l2_rubric(case)
                    if isinstance(e, dict) and e.get("required") is True and e.get("id")]
        if criteria and not l2_rubric(case):
            raise ValueError(
                "aggregate carries rubric_criteria but the case declares no rubric — "
                "the caller passed a stripped case dict, so every required criterion "
                "would be silently dropped")
        if required:
            if not criteria:
                return "UNMEASURED"   # pre-F ledger: no per-question answers on file
            for cid in required:
                # Derived from the counts, never the stored rate — see criterion_status.
                status, crate = criterion_status(criteria.get(cid), valid)
                if status != "ok":
                    return "UNMEASURED"   # absent, partly answered, or self-contradicting
                if not _meets(crate, t("rubric_required_rate")):
                    ok = False
        return "PASS" if ok else "FAIL"
    if layer == 3:
        valid = agg["runs_valid"]
        ok = _meets(rate, t("runs_without_error"))
        applicable = agg.get("est_applicable", 0)
        if applicable:
            ok = ok and _meets(agg["est_ok"] / applicable, t("estimation_accuracy"))
        # diagnostic_coverage is REPORTED, NOT GATED. It is a literal substring match
        # (scorer.py:566) with demonstrated false negatives: did_basic_2x2 scored 0.33
        # while clustering its SEs six times and reporting a 95% CI — it simply never
        # wrote the exact phrases. must_include alternates were built to cure that, but
        # only 2 of 21 L3 cases use them and neither of the two cases that demonstrated
        # the problem does. A wording matcher must not decide a release.
        guard = agg.get("guard_ok", valid) / valid if valid else 0.0
        ok = ok and _meets(guard, t("guard_pass_rate"))
        return "PASS" if ok else "FAIL"
    if layer == 4:
        for dim in ("pedagogy", "safety", "actionable"):
            score = agg.get(dim)
            if score is not None and not _meets(score, t(dim)):
                return "FAIL"
        return "PASS"
    if layer == 5:
        return "PASS" if _meets(rate, t("handoff_quality")) else "FAIL"
    return "FAIL"


def load_config(path: str = "evals/config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_skill(name: str) -> str:
    path = Path(f"skills/{name}/SKILL.md")
    if not path.exists():
        raise FileNotFoundError(f"Skill not found: {path}")
    return path.read_text()


def load_references(refs: list[str]) -> str:
    parts = []
    for ref in refs:
        p = Path(ref)
        if p.exists():
            parts.append(f"## {p.name}\n\n{p.read_text()}")
    return "\n\n---\n\n".join(parts)


def load_case(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def inject_schema(case: dict) -> dict:
    """Inject dataset schema into user_message if dataset exists."""
    import pandas as pd
    dataset = case.get("dataset")
    if not dataset or not Path(dataset).exists():
        return case
    case = dict(case)  # shallow copy to avoid mutating original
    df = pd.read_csv(dataset)
    schema = (
        f"\n\nHere's a sample of the data:\n```\n{df.head().to_string()}\n```"
        f"\n\nColumn types:\n```\n{df.dtypes.to_string()}\n```"
    )
    case["user_message"] = case["user_message"].rstrip() + schema
    return case


def collect_cases(layer: int | None = None, case_name: str | None = None,
                  cases_dir: Path | None = None) -> list[str]:
    """Resolve case paths, refusing to run while any case name is ambiguous.

    Case names key `--case`, ledgers, and verdicts, so a name appearing in two
    layers silently shadows one of them. That is checked on every invocation,
    not just when --case is used.
    """
    cases_dir = Path(cases_dir) if cases_dir else Path("evals/cases")

    by_name: dict[str, list[str]] = {}
    for f in sorted(cases_dir.rglob("*.yaml")):
        by_name.setdefault(f.stem, []).append(str(f))
    dupes = {n: p for n, p in by_name.items() if len(p) > 1}
    if dupes:
        detail = "; ".join(f"{n}: {', '.join(paths)}" for n, paths in sorted(dupes.items()))
        raise ValueError(f"duplicate case name(s) across layers — {detail}")

    if case_name:
        if case_name not in by_name:
            raise FileNotFoundError(f"Case not found: {case_name}")
        return by_name[case_name]
    if layer is not None:
        d = cases_dir / f"layer{layer}"
        return sorted(str(f) for f in d.glob("*.yaml"))
    return sorted(str(f) for f in cases_dir.rglob("*.yaml"))


class SkillError(RuntimeError):
    """A `claude -p` skill call produced no usable response.

    Carries `reason` so the run can be tagged `skill_error` (the call failed) or
    `empty_response` (it succeeded but said nothing).
    """

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def invoke_skill_cli(args: list[str], config: dict | None = None, timeout: int = 450,
                     label: str = "skill", cwd: str | None = None) -> tuple[str, dict]:
    """Run one skill call, retrying transient failures. Returns (text, usage).

    Rate limiting shows up as a nonzero exit with empty stderr. Without a retry
    here, one blip discards the whole run and forces the sweep to re-run all five
    — the failure mode that left ~40 cases unmeasured in July.

    A genuine timeout is terminal, not retried: repeating the same wait three
    times just burns 3x the time for the same outcome — the failure mode that
    stalled the auditor cases and left the v0.6.0 sweep at 176 UNMEASURED.
    `config["skill"]["timeout"]` overrides the `timeout` param so the release
    timeout policy can be pinned and fingerprinted, not just hard-coded here.
    """
    skill_cfg = (config or {}).get("skill", {})
    max_attempts = int(skill_cfg.get("max_attempts", 3))
    backoff = float(skill_cfg.get("retry_backoff", 10.0))
    timeout = int(skill_cfg.get("timeout", timeout))

    last: SkillError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            proc = run_subprocess_grouped(args, timeout=timeout, cwd=cwd)
            if proc.returncode != 0:
                raise SkillError(
                    "skill_error",
                    f"{label}: claude -p exited {proc.returncode}: {proc.stderr[:500]}")
            try:
                resp = json.loads(proc.stdout)
            except (json.JSONDecodeError, TypeError) as e:
                raise SkillError(
                    "skill_error",
                    f"{label}: unparseable claude -p stdout: {proc.stdout[:200]}") from e
            text = resp.get("result", "")
            if resp.get("is_error") or not text.strip():
                raise SkillError(
                    "empty_response",
                    f"{label}: claude -p returned no usable text: {str(resp.get('result'))[:200]}")
            return text, resp.get("usage", {})
        except subprocess.TimeoutExpired as e:
            raise SkillError(
                "skill_timeout", f"{label}: claude -p timed out after {timeout}s") from e
        except SkillError as e:
            last = e
        if attempt < max_attempts and backoff:
            time.sleep(backoff * 2 ** (attempt - 1))

    raise SkillError(last.reason if last else "skill_error",
                     f"{label}: giving up after {max_attempts} attempt(s): {last}")


def _invalid_run(index: int, reason: str, error: str, tokens: dict | None = None,
                 **extra) -> dict:
    """A run that produced no usable measurement.

    Aggregation skips these, so they can never masquerade as a zero score. The
    error text is always non-empty — an empty stderr previously produced a
    failed run that looked indistinguishable from a clean one.
    """
    record = {
        "run": index + 1,
        "scores": {},
        "invalid": reason,
        "error": error or f"{reason} (no detail reported)",
        "tokens": tokens or {"input": 0, "output": 0},
        "response": extra.pop("response", ""),
    }
    record.update(extra)
    return record


# --- L0: Trigger Tests ---

def run_case_l0(case: dict, config: dict, runs: int, debug: bool = False) -> list[dict]:
    """Run L0 trigger test. Asks judge if description would trigger for user message."""
    skill_name = case["skill"]
    skill_path = Path(f"skills/{skill_name}/SKILL.md")

    # Extract description from frontmatter
    with open(skill_path) as f:
        content = f.read()
    parts = content.split("---", 2)
    fm = yaml.safe_load(parts[1])
    description = fm.get("description", "")
    case["description_text"] = description

    results = []
    for i in range(runs):
        try:
            scores = score_response(case, "", config, debug)
            results.append({"run": i + 1, "scores": scores, "tokens": {"input": 0, "output": 0}})
        except JudgeError as e:
            results.append(_invalid_run(i, e.reason, str(e)))
        except Exception as e:
            results.append(_invalid_run(i, "run_error", str(e)))
    return results


# --- Backend: Claude Code CLI (`claude -p`) ---

_SANDBOX_LINK_DIRS = ("templates", "references")


def _link_plugin_dirs(workdir: str) -> None:
    """Every method skill's SKILL.md instructs the model to Read live, relative-path
    files under `templates/` ("Generate complete analysis code. Read the appropriate
    template from templates/r/X.md...") and `references/` (assumption checklists,
    method registry) — these are NOT pre-loaded into the system prompt the way a
    case's own `references:` list is (that's a *different* mechanism: load_references()
    bakes case-declared refs into the system prompt as text; SKILL.md's own "Read
    references/lessons.md" etc. is a live tool call the model makes itself). Confirmed
    by direct probe: pointing `claude -p` at an empty cwd and asking it to Read
    `templates/python/dag.md` returns "does not exist" — the model then silently
    improvises code instead of copying the template, with no visible error anywhere
    in its response. Symlinked (not copied) so a plugin edit is reflected immediately
    and this costs one syscall per case-run. Deliberately excludes `docs/` (the
    artifact fixture needs an isolated home there, not a live view of the real
    gitignored docs/) and `evals/` (would let a case Glob its own answer key).
    """
    for name in _SANDBOX_LINK_DIRS:
        src = Path(name).resolve()
        if src.is_dir():
            os.symlink(src, Path(workdir) / name)


def _provision_artifact_fixture(case: dict, workdir: str) -> None:
    """D5: `input_mode: artifact` cases declare `artifact_fixture: {source, dest}` — a
    checked-in fixture tree under `evals/fixtures/` and the relative path inside the
    sandbox where the skill should discover it, matching what the case's narrative
    claims (e.g. `docs/causal-plans/2026-03-15-loyalty-program`). Copied fresh into
    each run's temp workspace so Read/Glob/Grep find it exactly where the story says
    it lives, without ever touching the real repo tree or leaking across runs.
    """
    if case.get("input_mode") != "artifact":
        return
    fixture = case.get("artifact_fixture")
    if not fixture:
        return
    import shutil
    source_str = fixture["source"]
    if not isinstance(source_str, str) or ".." in Path(source_str).parts:
        raise ValueError(f"artifact_fixture.source must not contain '..': {source_str!r}")
    # Unlike `dest`, an absolute `source` is not itself unsafe -- there is no
    # Path(workdir)/source join for it to defeat. What matters is where it resolves to,
    # so containment is the authoritative check, not path style.
    source = Path(source_str).resolve()
    if not source.is_relative_to(FIXTURES_ROOT):
        raise ValueError(f"artifact_fixture.source escapes evals/fixtures/: {source_str!r}")
    try:
        reject_symlinks(source)
    except ValueError as e:
        raise ValueError(f"artifact_fixture.source {e}") from None
    dest_str = fixture["dest"]
    if not isinstance(dest_str, str) or Path(dest_str).is_absolute() or ".." in Path(dest_str).parts:
        raise ValueError(f"artifact_fixture.dest must be a relative path with no '..': {dest_str!r}")
    workdir_resolved = Path(workdir).resolve()
    dest = Path(workdir) / dest_str
    if not dest.resolve().is_relative_to(workdir_resolved):
        raise ValueError(f"artifact_fixture.dest escapes the sandbox workdir: {dest_str!r}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)


def run_case_cli(case: dict, config: dict, runs: int, debug: bool = False) -> list[dict]:
    """Run eval case via `claude -p` — bills to Claude Code subscription."""
    import tempfile

    skill_content = load_skill(case["skill"])
    refs = case.get("references", [])
    ref_content = load_references(refs)
    system = f"{skill_content}\n\n{ref_content}" if ref_content else skill_content

    model_map = {
        "claude-sonnet-4-20250514": "sonnet",
        "claude-opus-4-20250514": "opus",
        "claude-haiku-4-5-20251001": "haiku",
    }
    model = model_map.get(config.get("model", ""), config.get("model", "sonnet"))

    # Write system prompt to temp file to avoid CLI arg length limits
    sys_file = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    sys_file.write(system)
    sys_file.close()

    results = []
    for i in range(runs):
        text = ""
        try:
            with tempfile.TemporaryDirectory(prefix="eval-case-") as workdir:
                _link_plugin_dirs(workdir)
                _provision_artifact_fixture(case, workdir)
                text, usage = invoke_skill_cli(
                    [
                        "claude", "-p", case["user_message"],
                        "--system-prompt-file", sys_file.name,
                        "--model", model,
                        "--output-format", "json",
                        "--tools", "Read,Glob,Grep",
                        "--dangerously-skip-permissions",
                        "--no-session-persistence",
                        "--setting-sources", "local",
                    ],
                    config, label=case["name"], cwd=workdir)

            scores = score_response(case, text, config, debug=debug)
            results.append({
                "run": i + 1,
                "response": text,
                "scores": scores,
                "tokens": {
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                },
            })
        except SkillError as e:
            results.append(_invalid_run(i, e.reason, str(e)))
        except JudgeError as e:
            # The skill answered; only the measurement failed. Keep the response.
            results.append(_invalid_run(i, e.reason, str(e), response=text))
        except Exception as e:
            results.append(_invalid_run(i, "run_error", str(e), response=text))

    os.unlink(sys_file.name)
    return results


def run_case_l5_cli(case: dict, config: dict, runs: int, debug: bool = False) -> list[dict]:
    """Run L5 (workflow handoff) eval via `claude -p` — two sequential skill steps."""
    import tempfile

    steps = case["steps"]
    model_map = {
        "claude-sonnet-4-20250514": "sonnet",
        "claude-opus-4-20250514": "opus",
        "claude-haiku-4-5-20251001": "haiku",
    }
    model = model_map.get(config.get("model", ""), config.get("model", "sonnet"))

    results = []
    for i in range(runs):
        try:
            # --- Step 1 ---
            step1 = steps[0]
            skill1 = load_skill(step1["skill"])
            refs1 = step1.get("references", case.get("references", []))
            ref1_content = load_references(refs1)
            system1 = f"{skill1}\n\n{ref1_content}" if ref1_content else skill1

            sys_file1 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
            sys_file1.write(system1)
            sys_file1.close()

            try:
                step1_text, usage1 = invoke_skill_cli(
                    [
                        "claude", "-p", step1["scenario"],
                        "--system-prompt-file", sys_file1.name,
                        "--model", model,
                        "--output-format", "json",
                        "--tools", "Read,Glob,Grep",
                        "--dangerously-skip-permissions",
                        "--no-session-persistence",
                        "--setting-sources", "local",
                    ],
                    config, label=f"{case['name']} step 1")
            finally:
                os.unlink(sys_file1.name)

            # --- Step 2 ---
            step2 = steps[1]
            skill2 = load_skill(step2["skill"])
            refs2 = step2.get("references", case.get("references", []))
            ref2_content = load_references(refs2)
            system2 = f"{skill2}\n\n{ref2_content}" if ref2_content else skill2

            step2_scenario = step2.get("scenario", "")
            if step2.get("input_from") == "step_1":
                step2_message = f"{step1_text}\n\n{step2_scenario}".strip()
            else:
                step2_message = step2_scenario

            sys_file2 = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
            sys_file2.write(system2)
            sys_file2.close()

            try:
                step2_text, usage2 = invoke_skill_cli(
                    [
                        "claude", "-p", step2_message,
                        "--system-prompt-file", sys_file2.name,
                        "--model", model,
                        "--output-format", "json",
                        "--tools", "Read,Glob,Grep",
                        "--dangerously-skip-permissions",
                        "--no-session-persistence",
                        "--setting-sources", "local",
                    ],
                    config, label=f"{case['name']} step 2")
            except SkillError as e:
                # Step 1's real response is worth keeping for triage.
                results.append(_invalid_run(
                    i, e.reason, str(e),
                    tokens={"input": usage1.get("input_tokens", 0),
                            "output": usage1.get("output_tokens", 0)},
                    response=step1_text, step1_response=step1_text, step2_response=""))
                continue
            finally:
                os.unlink(sys_file2.name)

            scores = score_l5(step1_text, step2_text, case, config, debug=debug)
            results.append({
                "run": i + 1,
                "step1_response": step1_text,
                "step2_response": step2_text,
                "response": f"--- Step 1 ---\n{step1_text}\n\n--- Step 2 ---\n{step2_text}",
                "scores": scores,
                "tokens": {
                    "input": usage1.get("input_tokens", 0) + usage2.get("input_tokens", 0),
                    "output": usage1.get("output_tokens", 0) + usage2.get("output_tokens", 0),
                },
            })
        except SkillError as e:
            results.append(_invalid_run(i, e.reason, str(e),
                                        step1_response="", step2_response=""))
        except JudgeError as e:
            results.append(_invalid_run(i, e.reason, str(e),
                                        step1_response="", step2_response=""))
        except Exception as e:
            results.append(_invalid_run(i, "run_error", str(e),
                                        step1_response="", step2_response=""))
    return results


# --- Backend: Anthropic API SDK ---

def run_case_api(client, case: dict, config: dict, runs: int, debug: bool = False) -> list[dict]:
    """Run eval case via Anthropic SDK — requires ANTHROPIC_API_KEY."""
    skill_content = load_skill(case["skill"])
    refs = case.get("references", [])
    ref_content = load_references(refs)
    system = f"{skill_content}\n\n{ref_content}" if ref_content else skill_content

    results = []
    for i in range(runs):
        text = ""
        try:
            resp = client.messages.create(
                model=config.get("model", "claude-sonnet-4-20250514"),
                max_tokens=config.get("max_tokens", 4096),
                system=system,
                messages=[{"role": "user", "content": case["user_message"]}],
            )
            text = resp.content[0].text
            if not text.strip():
                results.append(_invalid_run(i, "empty_response", "API returned empty text"))
                continue
            scores = score_response(case, text, config, debug=debug)
            results.append({
                "run": i + 1,
                "response": text,
                "scores": scores,
                "tokens": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
            })
        except JudgeError as e:
            results.append(_invalid_run(i, e.reason, str(e), response=text))
        except Exception as e:
            results.append(_invalid_run(i, "run_error", str(e), response=text))
    return results


def run_case_l5_api(client, case: dict, config: dict, runs: int, debug: bool = False) -> list[dict]:
    """Run L5 (workflow handoff) eval via Anthropic SDK — two sequential skill steps."""
    steps = case["steps"]

    results = []
    for i in range(runs):
        try:
            # --- Step 1 ---
            step1 = steps[0]
            skill1 = load_skill(step1["skill"])
            refs1 = step1.get("references", case.get("references", []))
            ref1_content = load_references(refs1)
            system1 = f"{skill1}\n\n{ref1_content}" if ref1_content else skill1

            resp1 = client.messages.create(
                model=config.get("model", "claude-sonnet-4-20250514"),
                max_tokens=config.get("max_tokens", 4096),
                system=system1,
                messages=[{"role": "user", "content": step1["scenario"]}],
            )
            step1_text = resp1.content[0].text

            # --- Step 2 ---
            step2 = steps[1]
            skill2 = load_skill(step2["skill"])
            refs2 = step2.get("references", case.get("references", []))
            ref2_content = load_references(refs2)
            system2 = f"{skill2}\n\n{ref2_content}" if ref2_content else skill2

            step2_scenario = step2.get("scenario", "")
            if step2.get("input_from") == "step_1":
                step2_message = f"{step1_text}\n\n{step2_scenario}".strip()
            else:
                step2_message = step2_scenario

            resp2 = client.messages.create(
                model=config.get("model", "claude-sonnet-4-20250514"),
                max_tokens=config.get("max_tokens", 4096),
                system=system2,
                messages=[{"role": "user", "content": step2_message}],
            )
            step2_text = resp2.content[0].text

            scores = score_l5(step1_text, step2_text, case, config, debug=debug)
            results.append({
                "run": i + 1,
                "step1_response": step1_text,
                "step2_response": step2_text,
                "response": f"--- Step 1 ---\n{step1_text}\n\n--- Step 2 ---\n{step2_text}",
                "scores": scores,
                "tokens": {
                    "input": resp1.usage.input_tokens + resp2.usage.input_tokens,
                    "output": resp1.usage.output_tokens + resp2.usage.output_tokens,
                },
            })
        except JudgeError as e:
            results.append(_invalid_run(i, e.reason, str(e),
                                        step1_response="", step2_response=""))
        except Exception as e:
            results.append(_invalid_run(i, "run_error", str(e),
                                        step1_response="", step2_response=""))
    return results


# --- Aggregation & Reporting ---

def criterion_status(crit: dict | None, runs_valid: int) -> tuple[str, float | None]:
    """Is one stored criterion block trustworthy and complete? -> (status, rate).

    `("ok", rate)` and, otherwise, `("missing"|"partial"|"inconsistent", None)`.

    The rate is DERIVED from the counts and the stored `rate` is never read. A
    ledger is data, not testimony: `_rubric_criteria` cannot write a complete-looking
    rate over an incomplete answer set today, but that invariant lived only in the
    writer, and the one shape that must never reach the gate is exactly the one a
    foreign or hand-edited ledger would carry. Deriving here costs a division and
    makes the writer's correctness irrelevant to the gate's.

    The full invariant, since a partial check is no check:
    `0 <= passed <= answered == crit["valid"] == runs_valid`, each an honest int.
    `type(v) is int`, not isinstance: bools are ints in Python, so `passed: true`
    would otherwise be read as 1.

    One helper, not three: the gate, the UNMEASURED reason and the verdict table all
    have to agree on what "complete" means. Three copies would drift, and drift here
    means a criterion the gate refused to grade rendered as a clean pass rate.
    """
    if not isinstance(crit, dict):
        return "missing", None

    passed, answered, cvalid = crit.get("passed"), crit.get("answered"), crit.get("valid")
    if any(type(v) is not int for v in (passed, answered, cvalid)):
        return "inconsistent", None
    if cvalid != runs_valid or runs_valid <= 0:
        return "inconsistent", None
    if not 0 <= passed <= answered <= cvalid:
        return "inconsistent", None
    if answered != cvalid:
        return "partial", None
    return "ok", passed / cvalid


def _rubric_criteria(valid: list[dict], case: dict) -> dict | None:
    """Per-criterion L2 rubric results, or None when this is pre-F data.

    The denominator is every valid run, never the subset that happens to carry an
    answer. A required criterion answered in 4 of 5 valid runs reports
    `rate: None`, not 4/4 — otherwise a measurement gap reads as a perfect score
    and clears the gate. `answered` is kept alongside so the verdict can say which
    of the two it was.

    Returns None when no valid run carries `rubric_answers` at all: that is a
    ledger written before Package F, and the gate must call it UNMEASURED rather
    than infer anything from the old collapsed mean.
    """
    declared = [e for e in l2_rubric(case) if isinstance(e, dict) and e.get("id")]
    if not declared:
        return None
    if not any("rubric_answers" in r["scores"] for r in valid):
        return None

    n = len(valid)
    out = {}
    for entry in declared:
        cid = entry["id"]
        answers = [r["scores"]["rubric_answers"][cid] for r in valid
                   if cid in (r["scores"].get("rubric_answers") or {})]
        passed = sum(1 for a in answers if a)
        out[cid] = {
            "question": entry.get("question", ""),
            "required": entry.get("required") is True,
            "passed": passed,
            "answered": len(answers),
            "valid": n,
            "rate": passed / n if len(answers) == n else None,
        }
    return out


def aggregate(runs: list[dict], case: dict) -> dict:
    """Summarise a case's runs. Values are typed — counts are ints, rates are
    floats or None. Markdown formatting happens at render time, so nothing here
    has to be parsed back out of a string.
    """
    layer = case["layer"]
    total = len(runs)
    valid = [r for r in runs if not r.get("invalid")]
    n = len(valid)
    base = {"runs_valid": n, "runs_total": total}

    if n == 0:
        # No measurement at all — UNMEASURED, distinct from a measured zero.
        return {**base, "rate": None}

    if layer == 0:
        correct = sum(1 for r in valid if r["scores"].get("correct", False))
        return {**base, "trigger_correct": correct, "rate": correct / n}

    elif layer == 1:
        fp_counts = sum(len(r["scores"].get("false_positives", [])) for r in valid)
        accuracies = [r["scores"]["accuracy"] for r in valid
                      if r["scores"].get("accuracy") is not None]
        if accuracies:
            rate = sum(accuracies) / len(accuracies)
        else:  # legacy keyword-scored cases
            rate = sum(1 for r in valid if r["scores"].get("correct_method")) / n
        return {**base, "accuracy": rate, "false_positives": fp_counts, "rate": rate}

    elif layer == 2:
        # D9: `violation_detected` is `any(flag_answers)` -- a case declaring 3 flags
        # would pass detection on a single hit. `flags_coverage` (fraction of declared
        # flags actually caught) is computed per-run by the scorer but was never rolled
        # into the gate. Multi-flag cases now require full coverage per run; single-flag
        # cases are unaffected (flags_coverage and violation_detected agree when there's
        # only one flag to hit).
        must_flag = (case.get("expected") or {}).get("must_flag") or []
        if len(must_flag) > 1:
            detected = sum(1 for r in valid if r["scores"].get("flags_coverage") == 1.0)
        else:
            detected = sum(1 for r in valid if r["scores"].get("violation_detected"))
        severity_ok = sum(1 for r in valid if r["scores"].get("severity_correct"))
        out = {**base, "detected": detected, "severity_ok": severity_ok,
               "rate": detected / n}
        # Rubric coverage (informational): only present for rubric-bearing cases.
        # Kept after Package F both for backward comparability and because its
        # presence *without* `rubric_criteria` is how a pre-F ledger identifies
        # itself to the gate.
        rubric_vals = [r["scores"]["rubric_coverage"] for r in valid
                       if r["scores"].get("rubric_coverage") is not None]
        if rubric_vals:
            out["rubric_coverage"] = sum(rubric_vals) / len(rubric_vals)
        criteria = _rubric_criteria(valid, case)
        if criteria is not None:
            out["rubric_criteria"] = criteria
        # response_contract / deferred_rubric (D1): same propagation as L4's
        # branch above — static case metadata, same on every run, surfaced in
        # the verdict without affecting `rate`/detection at all.
        out["response_contract"] = next(
            (r["scores"].get("response_contract") for r in valid
             if r["scores"].get("response_contract")), None)
        out["deferred_rubric"] = next(
            (r["scores"].get("deferred_rubric") for r in valid
             if r["scores"].get("deferred_rubric")), [])
        return out

    elif layer == 3:
        ran = sum(1 for r in valid if r["scores"].get("runs_without_error"))
        # Only runs that could be judged against ground truth count toward
        # estimation accuracy; a case with none is not held to that gate.
        applicable = [r for r in valid if r["scores"].get("estimation_accurate") is not None]
        est_ok = sum(1 for r in applicable if r["scores"]["estimation_accurate"] is True)
        diag = sum(r["scores"].get("diagnostic_coverage", 0) for r in valid) / n
        guard = sum(1 for r in valid if r["scores"].get("guard_passed", True))
        return {**base, "ran": ran, "est_ok": est_ok, "est_applicable": len(applicable),
                "diagnostic_coverage": diag, "guard_ok": guard, "rate": ran / n}

    elif layer == 4:
        present = set()
        for r in valid:
            present.update(r["scores"].get("dimensions_present") or [])
        if not present:
            # D9: old-ledger compatibility. Runs recorded before `dimensions_present`
            # existed carry no per-run marker. The previous fallback ("assume all
            # three") forced every dimension a case never populated into a hard 0.0
            # average via scores.get(dim, 0.0) below -- exactly what this guards
            # against. Use the case's own declared rubric dimensions instead: still
            # works with zero per-run markers (--recompile stays supported), but
            # reflects what this case actually grades instead of guessing.
            rubric = case.get("rubric") or {}
            present = {d for d in ("pedagogy", "safety", "actionable") if rubric.get(d)}
            if not present:  # case has no rubric on file either -- last-resort guess
                present = {"pedagogy", "safety", "actionable"}
        dim_avgs = {}
        for dim in ("pedagogy", "safety", "actionable"):
            if dim in present:
                dim_avgs[dim] = sum(r["scores"].get(dim, 0.0) for r in valid) / n
            else:
                dim_avgs[dim] = None  # not populated by this case — skipped, not zero
        scored = [v for v in dim_avgs.values() if v is not None]
        overall = sum(scored) / len(scored) if scored else 0.0
        # response_contract / deferred_rubric (D1): static case metadata, same
        # on every run — take it from whichever run reported it. Deferred
        # criteria are surfaced in the verdict; they never entered dim_avgs
        # above, so they cost no judge calls and cannot affect the score.
        contract = next((r["scores"].get("response_contract") for r in valid
                         if r["scores"].get("response_contract")), None)
        deferred = next((r["scores"].get("deferred_rubric") for r in valid
                         if r["scores"].get("deferred_rubric")), [])
        return {**base, **dim_avgs, "overall": overall, "rate": overall,
                "response_contract": contract, "deferred_rubric": deferred}

    elif layer == 5:
        handoff = sum(r["scores"].get("handoff_quality", 0.0) for r in valid) / n
        return {
            **base,
            "handoff_quality": handoff,
            "questions_passed": sum(r["scores"].get("questions_passed", 0) for r in valid),
            "questions_total": sum(r["scores"].get("questions_total", 0) for r in valid),
            "rate": handoff,
        }
    return base


def format_score(layer: int, agg: dict) -> str:
    """Human-readable headline metric for reports. Rendering only."""
    if agg.get("rate") is None:
        return "UNMEASURED"
    if layer == 0:
        return f"{agg['trigger_correct']}/{agg['runs_valid']}"
    if layer == 1:
        return f"{agg['accuracy']:.0%}"
    if layer == 2:
        return f"{agg['detected']}/{agg['runs_valid']}"
    if layer == 3:
        return f"{agg['ran']}/{agg['runs_valid']}"
    if layer == 4:
        return f"{agg['overall']:.0%}"
    if layer == 5:
        return f"{agg['handoff_quality']:.0%}"
    return "N/A"


def report_path(out_dir: Path, label: str) -> Path:
    """Collision-proof report filename.

    A second-granular timestamp alone let concurrent invocations clobber each
    other's reports, so the label and PID go in too.
    """
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", label).strip("-") or "run"
    return out_dir / f"{ts}_{safe}_pid{os.getpid()}.md"


def save_report(results: dict, config: dict, label: str = "run"):
    out_dir = Path("evals/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = report_path(out_dir, label)

    lines = [
        f"# Eval Report — {path.stem}\n",
        f"**Model**: {config.get('model')}\n",
        f"**Backend**: {results['backend']}\n",
        f"**Runs per case**: {results['runs']}\n",
        "## Summary\n",
        "| Case | Layer | Score | Valid runs | Verdict |",
        "|------|-------|-------|------------|---------|",
    ]
    for cr in results["cases"]:
        c = cr["case"]
        a = cr["aggregate"]
        layer = c["layer"]
        valid = f"{a.get('runs_valid', 0)}/{a.get('runs_total', 0)}"
        lines.append(
            f"| {c['name']} | L{layer} | {format_score(layer, a)} | {valid} "
            f"| {case_gate(c, a, config.get('thresholds'))} |")

    lines.extend(["\n## Details\n"])
    for cr in results["cases"]:
        c = cr["case"]
        lines.append(f"### {c['name']}\n")
        for run in cr["runs"]:
            if run.get("invalid"):
                lines.append(f"**Run {run['run']}**: INVALID ({run['invalid']})\n")
            else:
                lines.append(f"**Run {run['run']}**: {json.dumps(run['scores'])}\n")
            if run.get("response"):
                lines.append(f"<details><summary>Response</summary>\n\n{run['response']}\n\n</details>\n")
            if run.get("error"):
                lines.append(f"**Error**: {run['error']}\n")
        lines.append("---\n")

    path.write_text("\n".join(lines))
    print(f"Report saved: {path}")


def release_token(version: str) -> str:
    """The one string that marks a row as a version's release evidence."""
    return f"[release:{version}]"


def save_history(results: dict, config: dict, notes: str = "",
                 hist_path: Path | None = None, release_version: str | None = None):
    """Append a summary row to HISTORY.md for trend tracking.

    Unmeasured cases are excluded from both numerator and denominator — they are
    a gap in the measurement, not a failure of the skill.

    With `release_version`, the row is keyed by an exact `[release:vX.Y.Z]` token
    and *replaces* any existing row carrying that token: a re-run release sweep
    for the same unpublished version is a correction, not a second opinion, and
    two rows claiming to be the evidence for one version is worse than either.
    The match is on the exact token only — historical rows say things like
    "v0.1.0 release" in free text, and a looser match would eat them.
    """
    hist_path = Path(hist_path) if hist_path else Path("evals/results/HISTORY.md")

    # Compute aggregate pass rates per layer
    layer_stats = {0: {"pass": 0, "total": 0}, 1: {"pass": 0, "total": 0}, 2: {"pass": 0, "total": 0, "sev_pass": 0, "sev_total": 0}, 3: {"pass": 0, "total": 0, "est_pass": 0, "est_total": 0}, 4: {"scores": [], "total": 0}, 5: {"scores": [], "total": 0}}
    thresholds = config.get("thresholds", {})

    def thr(layer, key):
        return _threshold(thresholds, layer, key)

    for cr in results["cases"]:
        layer = cr["case"]["layer"]
        agg = cr["aggregate"]
        rate = agg.get("rate")
        if rate is None:
            continue  # unmeasured: contributes to neither column
        # The pass column is the release verdict, so it must be case_gate() and not a
        # second, drifting copy of it. The old inline logic ignored L1 false positives
        # and L3 guard/diagnostic gates, so HISTORY could report a case as passing that
        # the gate failed. The supplementary columns below are separate metrics, not
        # gates, and stay broken out.
        gate = case_gate(cr["case"], agg, thresholds) if layer in (0, 1, 2, 3) else None
        if gate == "UNMEASURED":
            # Same rule as `rate is None` above, and the same treatment: the whole case
            # sits out every column. Until Package F the gate could only withhold a
            # verdict when there was no rate at all, so that check covered this. The
            # rubric gate can now withhold one with a rate present — required criteria
            # answered in only some runs — and the reason a case is unmeasured must not
            # change whether it counts.
            continue
        layer_stats[layer]["total"] += 1
        if gate == "PASS":
            layer_stats[layer]["pass"] += 1

        valid = agg.get("runs_valid", 0) or 1

        if layer == 2:
            layer_stats[2]["sev_total"] += 1
            if _meets(agg.get("severity_ok", 0) / valid, thr(2, "severity_accuracy")):
                layer_stats[2]["sev_pass"] += 1
        elif layer == 3:
            applicable = agg.get("est_applicable", 0)
            if applicable:  # cases without ground truth sit out this column
                layer_stats[3]["est_total"] += 1
                if _meets(agg["est_ok"] / applicable, thr(3, "estimation_accuracy")):
                    layer_stats[3]["est_pass"] += 1
        elif layer == 4:
            layer_stats[4]["scores"].append(rate)
        elif layer == 5:
            layer_stats[5]["scores"].append(rate)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    model = config.get("model", "unknown")

    def frac(d, key_p="pass", key_t="total"):
        return f"{d[key_p]}/{d[key_t]}" if d[key_t] > 0 else "—"

    def avg_pct(scores):
        if not scores:
            return "—"
        return f"{sum(scores) / len(scores):.0%}"

    l0 = frac(layer_stats[0])
    l1 = frac(layer_stats[1])
    l2_det = frac(layer_stats[2])
    l2_sev = frac(layer_stats[2], "sev_pass", "sev_total")
    l3_run = frac(layer_stats[3])
    l3_est = frac(layer_stats[3], "est_pass", "est_total")
    l4 = avg_pct(layer_stats[4]["scores"])
    l5 = avg_pct(layer_stats[5]["scores"])

    if release_version:
        token = release_token(release_version)
        notes = f"{token} {notes}".strip()
    row = f"| {ts} | {model} | {l0} | {l1} | {l2_det} | {l2_sev} | {l3_run} | {l3_est} | {l4} | {l5} | {notes} |"

    if not hist_path.exists():
        header = """# Eval History

| Date | Model | L0 Trigger | L1 Acc | L2 Detect | L2 Severity | L3 Runs OK | L3 Est Acc | L4 Exp | L5 Wkfl | Notes |
|------|-------|------------|--------|-----------|-------------|------------|------------|--------|---------|-------|
"""
        hist_path.write_text(header + row + "\n")
    elif release_version:
        token = release_token(release_version)
        lines = hist_path.read_text().splitlines()
        replaced = False
        for i, line in enumerate(lines):
            if token in line:
                lines[i] = row
                replaced = True
                break
        if not replaced:
            lines.append(row)
        hist_path.write_text("\n".join(lines) + "\n")
    else:
        with open(hist_path, "a") as f:
            f.write(row + "\n")

    print(f"History updated: {hist_path}")


def main():
    parser = argparse.ArgumentParser(description="everyday-causal-skills eval runner")
    parser.add_argument("--layer", type=int, choices=[0, 1, 2, 3, 4, 5])
    parser.add_argument("--case", type=str)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--config", default="evals/config.yaml")
    parser.add_argument("--backend", choices=["cli", "api"], default="cli",
                        help="cli = claude -p (subscription), api = Anthropic SDK (API key)")
    parser.add_argument("--notes", type=str, default="",
                        help="Annotation for this run in HISTORY.md")
    parser.add_argument("--debug-judge", action="store_true",
                        help="Print LLM judge reasoning for L2 cases")
    parser.add_argument("--json-out", type=str, default="",
                        help="Write typed results as JSON (machine-readable channel)")
    parser.add_argument("--no-history", action="store_true",
                        help="Skip the HISTORY.md row (sweeps write one consolidated row)")
    args = parser.parse_args()

    if args.layer is None and not args.case and not args.all:
        parser.error("Specify --layer, --case, or --all")

    config = load_config(args.config)
    paths = collect_cases(layer=args.layer, case_name=args.case)
    label = args.case or (f"L{args.layer}" if args.layer is not None else "all")
    print(f"Running {len(paths)} case(s), {args.runs} run(s) each [backend={args.backend}]...\n")

    client = None
    if args.backend == "api":
        import anthropic
        client = anthropic.Anthropic()

    all_results = {"runs": args.runs, "backend": args.backend, "cases": []}
    for p in paths:
        case = load_case(p)
        case = inject_schema(case)
        print(f"  {case['name']}...", end=" ", flush=True)
        try:
            if case.get("layer") == 0:
                runs = run_case_l0(case, config, args.runs, debug=args.debug_judge)
            elif case.get("layer") == 5:
                if args.backend == "cli":
                    runs = run_case_l5_cli(case, config, args.runs, debug=args.debug_judge)
                else:
                    runs = run_case_l5_api(client, case, config, args.runs, debug=args.debug_judge)
            elif args.backend == "cli":
                runs = run_case_cli(case, config, args.runs, debug=args.debug_judge)
            else:
                runs = run_case_api(client, case, config, args.runs, debug=args.debug_judge)
            agg = aggregate(runs, case)
            all_results["cases"].append({"case": case, "runs": runs, "aggregate": agg})
            verdict = case_gate(case, agg, config.get("thresholds"))
            print(f"{verdict} ({format_score(case['layer'], agg)}, "
                  f"{agg['runs_valid']}/{agg['runs_total']} valid)")
        except Exception as e:
            print(f"ERROR: {e}")
            runs = [_invalid_run(i, "run_error", str(e)) for i in range(args.runs)]
            all_results["cases"].append({
                "case": case,
                "runs": runs,
                "aggregate": aggregate(runs, case),
            })

    save_report(all_results, config, label=label)
    if not args.no_history:
        save_history(all_results, config, notes=args.notes)

    if args.json_out:
        out = {
            "runs": all_results["runs"],
            "backend": all_results["backend"],
            "cases": [
                {
                    "name": cr["case"]["name"],
                    "layer": cr["case"]["layer"],
                    "aggregate": cr["aggregate"],
                    "verdict": case_gate(cr["case"], cr["aggregate"],
                                         config.get("thresholds")),
                    "invalid_reasons": sorted({r["invalid"] for r in cr["runs"]
                                               if r.get("invalid")}),
                    # Raw per-run records, additive: lets a caller that ran
                    # --runs 1 (sweep.py's run-slot checkpointing) recover the
                    # single measurement instead of only its aggregate.
                    "run_records": cr["runs"],
                }
                for cr in all_results["cases"]
            ],
        }
        Path(args.json_out).write_text(json.dumps(out, indent=2))
        print(f"JSON results: {args.json_out}")

    # Exit 2 signals "not measured" so a sweep can requeue instead of recording
    # a verdict it cannot trust.
    if any(cr["aggregate"].get("rate") is None for cr in all_results["cases"]):
        sys.exit(2)


if __name__ == "__main__":
    main()
