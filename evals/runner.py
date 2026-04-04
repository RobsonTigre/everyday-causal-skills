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
import subprocess
from datetime import datetime
from pathlib import Path

import yaml

from scorer import score_response, score_l5


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


def collect_cases(layer: int | None = None, case_name: str | None = None) -> list[str]:
    cases_dir = Path("evals/cases")
    if case_name:
        for layer_dir in cases_dir.iterdir():
            if layer_dir.is_dir():
                f = layer_dir / f"{case_name}.yaml"
                if f.exists():
                    return [str(f)]
        raise FileNotFoundError(f"Case not found: {case_name}")
    if layer is not None:
        d = cases_dir / f"layer{layer}"
        return sorted(str(f) for f in d.glob("*.yaml"))
    return sorted(str(f) for f in cases_dir.rglob("*.yaml"))


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
        except Exception as e:
            results.append({"run": i + 1, "scores": {"correct": False}, "tokens": {"input": 0, "output": 0}, "error": str(e)})
    return results


# --- Backend: Claude Code CLI (`claude -p`) ---

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
        proc = subprocess.run(
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
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0:
            results.append({
                "run": i + 1,
                "response": "",
                "scores": {},
                "tokens": {"input": 0, "output": 0},
                "error": proc.stderr[:500],
            })
            continue

        resp = json.loads(proc.stdout)
        text = resp.get("result", "")
        usage = resp.get("usage", {})
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

    import os
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

            proc1 = subprocess.run(
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
                capture_output=True, text=True, timeout=300,
            )
            import os
            os.unlink(sys_file1.name)

            if proc1.returncode != 0:
                results.append({
                    "run": i + 1,
                    "step1_response": "",
                    "step2_response": "",
                    "response": "",
                    "scores": {},
                    "tokens": {"input": 0, "output": 0},
                    "error": f"Step 1 failed: {proc1.stderr[:500]}",
                })
                continue

            resp1 = json.loads(proc1.stdout)
            step1_text = resp1.get("result", "")
            usage1 = resp1.get("usage", {})

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

            proc2 = subprocess.run(
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
                capture_output=True, text=True, timeout=300,
            )
            os.unlink(sys_file2.name)

            if proc2.returncode != 0:
                results.append({
                    "run": i + 1,
                    "step1_response": step1_text,
                    "step2_response": "",
                    "response": step1_text,
                    "scores": {},
                    "tokens": {
                        "input": usage1.get("input_tokens", 0),
                        "output": usage1.get("output_tokens", 0),
                    },
                    "error": f"Step 2 failed: {proc2.stderr[:500]}",
                })
                continue

            resp2 = json.loads(proc2.stdout)
            step2_text = resp2.get("result", "")
            usage2 = resp2.get("usage", {})

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
        except Exception as e:
            results.append({
                "run": i + 1,
                "step1_response": "",
                "step2_response": "",
                "response": "",
                "scores": {},
                "tokens": {"input": 0, "output": 0},
                "error": str(e),
            })
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
        resp = client.messages.create(
            model=config.get("model", "claude-sonnet-4-20250514"),
            max_tokens=config.get("max_tokens", 4096),
            system=system,
            messages=[{"role": "user", "content": case["user_message"]}],
        )
        text = resp.content[0].text
        scores = score_response(case, text, config, debug=debug)
        results.append({
            "run": i + 1,
            "response": text,
            "scores": scores,
            "tokens": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
        })
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
        except Exception as e:
            results.append({
                "run": i + 1,
                "step1_response": "",
                "step2_response": "",
                "response": "",
                "scores": {},
                "tokens": {"input": 0, "output": 0},
                "error": str(e),
            })
    return results


# --- Aggregation & Reporting ---

def aggregate(runs: list[dict], case: dict) -> dict:
    layer = case["layer"]
    n = len(runs)
    if layer == 0:
        correct = sum(1 for r in runs if r["scores"].get("correct", False))
        return {
            "trigger_accuracy": f"{correct}/{n}",
            "rate": correct / n,
        }
    elif layer == 1:
        correct = sum(1 for r in runs if r["scores"].get("correct_method"))
        fp_counts = sum(len(r["scores"].get("false_positives", [])) for r in runs)
        # For rubric-based cases, use accuracy average; for legacy, use correct/n
        accuracies = [r["scores"].get("accuracy") for r in runs if r["scores"].get("accuracy") is not None]
        if accuracies:
            avg_accuracy = sum(accuracies) / len(accuracies)
            return {
                "accuracy": f"{avg_accuracy:.0%}",
                "false_positive_rate": f"{fp_counts}/{n}",
                "rate": avg_accuracy,
            }
        return {
            "accuracy": f"{correct}/{n}",
            "false_positive_rate": f"{fp_counts}/{n}",
            "completeness": f"{sum(1 for r in runs if r['scores'].get('completeness'))}/{n}",
            "rate": correct / n,
        }
    elif layer == 2:
        detected = sum(1 for r in runs if r["scores"].get("violation_detected"))
        severity_ok = sum(1 for r in runs if r["scores"].get("severity_correct"))
        return {
            "detection_rate": f"{detected}/{n}",
            "severity_accuracy": f"{severity_ok}/{n}",
            "rate": detected / n,
        }
    elif layer == 3:
        ran = sum(1 for r in runs if r["scores"].get("runs_without_error"))
        accurate = sum(1 for r in runs if r["scores"].get("estimation_accurate") is True)
        diag = sum(r["scores"].get("diagnostic_coverage", 0) for r in runs) / n
        return {
            "runs_without_error": f"{ran}/{n}",
            "estimation_accuracy": f"{accurate}/{n}",
            "diagnostic_coverage": f"{diag:.0%}",
            "rate": ran / n,
        }
    elif layer == 4:
        dimensions = ["pedagogy", "safety", "actionable"]
        dim_avgs = {}
        for dim in dimensions:
            vals = [r["scores"].get(dim, 0.0) for r in runs]
            dim_avgs[dim] = sum(vals) / n if n else 0.0
        overall = sum(dim_avgs.values()) / len(dim_avgs) if dim_avgs else 0.0
        return {
            "pedagogy": f"{dim_avgs['pedagogy']:.0%}",
            "safety": f"{dim_avgs['safety']:.0%}",
            "actionable": f"{dim_avgs['actionable']:.0%}",
            "overall": f"{overall:.0%}",
            "rate": overall,
        }
    elif layer == 5:
        handoff_vals = [r["scores"].get("handoff_quality", 0.0) for r in runs]
        avg_handoff = sum(handoff_vals) / n if n else 0.0
        total_passed = sum(r["scores"].get("questions_passed", 0) for r in runs)
        total_questions = sum(r["scores"].get("questions_total", 0) for r in runs)
        return {
            "handoff_quality": f"{avg_handoff:.0%}",
            "questions": f"{total_passed}/{total_questions}",
            "rate": avg_handoff,
        }
    return {}


def save_report(results: dict, config: dict):
    out_dir = Path("evals/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = out_dir / f"{ts}.md"

    lines = [
        f"# Eval Report — {ts}\n",
        f"**Model**: {config.get('model')}\n",
        f"**Backend**: {results['backend']}\n",
        f"**Runs per case**: {results['runs']}\n",
        "## Summary\n",
        "| Case | Layer | Score |",
        "|------|-------|-------|",
    ]
    for cr in results["cases"]:
        c = cr["case"]
        a = cr["aggregate"]
        score = a.get('trigger_accuracy', a.get('accuracy', a.get('detection_rate', a.get('runs_without_error', a.get('overall', a.get('handoff_quality', 'N/A'))))))
        lines.append(f"| {c['name']} | L{c['layer']} | {score} |")

    lines.extend(["\n## Details\n"])
    for cr in results["cases"]:
        c = cr["case"]
        lines.append(f"### {c['name']}\n")
        for run in cr["runs"]:
            lines.append(f"**Run {run['run']}**: {json.dumps(run['scores'])}\n")
            if run.get("response"):
                lines.append(f"<details><summary>Response</summary>\n\n{run['response']}\n\n</details>\n")
            if run.get("error"):
                lines.append(f"**Error**: {run['error']}\n")
        lines.append("---\n")

    path.write_text("\n".join(lines))
    print(f"Report saved: {path}")


def save_history(results: dict, config: dict, notes: str = ""):
    """Append a summary row to HISTORY.md for trend tracking."""
    hist_path = Path("evals/results/HISTORY.md")

    # Compute aggregate pass rates per layer
    layer_stats = {0: {"pass": 0, "total": 0}, 1: {"pass": 0, "total": 0}, 2: {"pass": 0, "total": 0, "sev_pass": 0, "sev_total": 0}, 3: {"pass": 0, "total": 0, "est_pass": 0, "est_total": 0}, 4: {"scores": [], "total": 0}, 5: {"scores": [], "total": 0}}
    thresholds = config.get("thresholds", {})

    for cr in results["cases"]:
        layer = cr["case"]["layer"]
        agg = cr["aggregate"]
        rate = agg.get("rate", 0)
        layer_stats[layer]["total"] += 1

        if layer == 0:
            if rate >= thresholds.get("layer0", {}).get("trigger_accuracy", 0.9):
                layer_stats[layer]["pass"] += 1
        elif layer == 1:
            if rate >= thresholds.get("layer1", {}).get("accuracy", 0.8):
                layer_stats[layer]["pass"] += 1
        elif layer == 2:
            if rate >= thresholds.get("layer2", {}).get("detection_rate", 0.8):
                layer_stats[layer]["pass"] += 1
            # Track severity separately
            sev_str = agg.get("severity_accuracy", "0/0")
            if "/" in str(sev_str):
                sev_n, sev_d = str(sev_str).split("/")
                if int(sev_d) > 0:
                    layer_stats[2]["sev_total"] += 1
                    if int(sev_n) / int(sev_d) >= thresholds.get("layer2", {}).get("severity_accuracy", 0.7):
                        layer_stats[2]["sev_pass"] += 1
        elif layer == 3:
            if rate >= thresholds.get("layer3", {}).get("runs_without_error", 0.9):
                layer_stats[layer]["pass"] += 1
            est_str = agg.get("estimation_accuracy", "0/0")
            if "/" in str(est_str):
                est_n, est_d = str(est_str).split("/")
                if int(est_d) > 0:
                    layer_stats[3]["est_total"] += 1
                    if int(est_n) / int(est_d) >= thresholds.get("layer3", {}).get("estimation_accuracy", 0.8):
                        layer_stats[3]["est_pass"] += 1
        elif layer == 4:
            layer_stats[4]["total"] += 1
            layer_stats[4]["scores"].append(rate)
        elif layer == 5:
            layer_stats[5]["total"] += 1
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

    row = f"| {ts} | {model} | {l0} | {l1} | {l2_det} | {l2_sev} | {l3_run} | {l3_est} | {l4} | {l5} | {notes} |"

    if not hist_path.exists():
        header = """# Eval History

| Date | Model | L0 Trigger | L1 Acc | L2 Detect | L2 Severity | L3 Runs OK | L3 Est Acc | L4 Exp | L5 Wkfl | Notes |
|------|-------|------------|--------|-----------|-------------|------------|------------|--------|---------|-------|
"""
        hist_path.write_text(header + row + "\n")
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
    args = parser.parse_args()

    if args.layer is None and not args.case and not args.all:
        parser.error("Specify --layer, --case, or --all")

    config = load_config(args.config)
    paths = collect_cases(layer=args.layer, case_name=args.case)
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
            print(f"done ({agg.get('accuracy', agg.get('detection_rate', agg.get('runs_without_error', '')))})")
        except Exception as e:
            print(f"ERROR: {e}")
            all_results["cases"].append({
                "case": case,
                "runs": [{"run": i+1, "response": "", "scores": {}, "error": str(e)} for i in range(args.runs)],
                "aggregate": {"rate": 0, "error": str(e)},
            })

    save_report(all_results, config)
    save_history(all_results, config, notes=args.notes)


if __name__ == "__main__":
    main()
