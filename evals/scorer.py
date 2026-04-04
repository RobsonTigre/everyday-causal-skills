"""
Scorer for everyday-causal-skills eval outputs.
Parses model responses and scores against expected outcomes.

Judge calls use `claude -p` (Max subscription) instead of the Anthropic SDK,
so no API key is needed.
"""
from __future__ import annotations

import json
import re
import subprocess


_MODEL_MAP = {
    "claude-sonnet-4-20250514": "sonnet",
    "claude-opus-4-20250514": "opus",
    "claude-haiku-4-5-20251001": "haiku",
}

_JUDGE_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {"type": "boolean"},
        }
    },
    "required": ["answers"],
})


def _call_judge(prompt: str, num_questions: int, config: dict | None = None,
                debug: bool = False, label: str = "JUDGE") -> list[bool]:
    """Call claude -p as a structured-output judge and return a list of booleans.

    Uses the Max subscription (no API key). Returns one boolean per question,
    padded with False if the judge returns fewer answers than expected.
    """
    judge_config = (config or {}).get("judge", {})
    judge_model_raw = judge_config.get("model", "claude-sonnet-4-20250514")
    model = _MODEL_MAP.get(judge_model_raw, judge_model_raw)

    proc = subprocess.run(
        [
            "claude", "-p", prompt,
            "--model", model,
            "--output-format", "json",
            "--json-schema", _JUDGE_SCHEMA,
            "--tools", "",
            "--no-session-persistence",
            "--setting-sources", "local",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if proc.returncode != 0:
        raise RuntimeError(f"claude -p exited {proc.returncode}: {proc.stderr[:500]}")

    resp = json.loads(proc.stdout)

    if resp.get("is_error"):
        raise RuntimeError(f"claude -p error: {resp.get('result', 'unknown')}")

    if debug:
        print(f"\n    [{label} REASONING]\n{resp.get('result', '')}\n    [/{label} REASONING]")

    # With --json-schema, result contains JSON matching the schema
    result_text = resp.get("result", "")
    try:
        structured = json.loads(result_text)
        answers = [bool(a) for a in structured.get("answers", [])]
    except (json.JSONDecodeError, TypeError):
        # Fallback: try structured_output field or parse YES/NO from text
        structured_output = resp.get("structured_output")
        if structured_output and "answers" in structured_output:
            answers = [bool(a) for a in structured_output["answers"]]
        else:
            answers = []
            for line in result_text.split("\n"):
                upper = line.strip().upper()
                cleaned = upper.split(".")[-1].strip() if "." in upper else upper
                if "YES" in cleaned:
                    answers.append(True)
                elif "NO" in cleaned:
                    answers.append(False)

    # Pad with False if fewer answers than expected
    while len(answers) < num_questions:
        answers.append(False)

    return answers


def _score_layer0(description: str, user_message: str, expected: dict,
                  config: dict | None = None, debug: bool = False) -> dict:
    """Score L0 trigger test: would Claude load this skill for this user message?"""
    prompt = f"""You are Claude's skill-loading system. Given a skill description and a user message, decide if this skill should be loaded.

Skill description: {description}

User message: {user_message}

Would you load this skill for this user message? Answer with exactly YES or NO, nothing else."""

    judge_config = (config or {}).get("judge", {})
    judge_model_raw = judge_config.get("model", "claude-sonnet-4-20250514")
    model = _MODEL_MAP.get(judge_model_raw, judge_model_raw)
    result = subprocess.run(
        [
            "claude", "-p", prompt,
            "--model", model,
            "--output-format", "text",
            "--tools", "",
            "--no-session-persistence",
            "--setting-sources", "local",
        ],
        capture_output=True, text=True, timeout=30
    )
    answer = result.stdout.strip().upper()
    triggered = "YES" in answer.split("\n")[0]

    should_trigger = expected.get("should_trigger", True)
    correct = triggered == should_trigger

    if debug:
        print(f"  L0 judge: {answer} | expected: {'YES' if should_trigger else 'NO'} | {'PASS' if correct else 'FAIL'}")

    return {
        "triggered": triggered,
        "should_trigger": should_trigger,
        "correct": correct,
    }


def score_response(case: dict, response: str, config: dict | None = None, debug: bool = False) -> dict:
    """Score a response against expected outcomes based on layer."""
    layer = case["layer"]
    expected = case.get("expected", {})

    if layer == 0:
        return _score_layer0(
            case.get("description_text", ""),
            case.get("user_message", ""),
            expected, config, debug
        )
    elif layer == 1:
        return _score_layer1(response, expected, config, debug)
    elif layer == 2:
        return _score_layer2(response, expected, config, debug)
    elif layer == 3:
        return _score_layer3(response, expected, case)
    elif layer == 4:
        return _judge_l4(response, case, config, debug)
    return {}


def _score_layer1(response: str, expected: dict, config: dict | None = None, debug: bool = False) -> dict:
    """Score method selection — uses LLM judge if rubric provided, else keyword matching."""
    rubric = expected.get("rubric")

    if rubric:
        return _judge_l1(response, expected, config, debug)

    # Legacy keyword-based scoring (for cases not yet migrated to rubric)
    text = response.lower()
    target = expected.get("method", "").lower()
    primary_match = target in text

    alternative_methods = expected.get("alternative_methods", [])
    alternative_discussed = [m for m in alternative_methods if m.lower() in text]
    correct = primary_match or any(m.lower() in text for m in alternative_methods)

    must_ask = expected.get("must_ask", [])
    asked = {q: q.lower() in text for q in must_ask}

    must_not = expected.get("must_not_recommend", [])
    false_positives = [m for m in must_not if _method_recommended(m.lower(), text)]

    must_warn = expected.get("must_warn", [])
    warnings_found = {w: w.lower() in text for w in must_warn}
    warnings_coverage = sum(warnings_found.values()) / len(warnings_found) if warnings_found else 1.0
    trap_detected = warnings_coverage >= 0.5 if must_warn else None

    result = {
        "correct_method": correct,
        "primary_method": primary_match,
        "alternative_discussed": alternative_discussed,
        "asked_coverage": sum(asked.values()) / len(asked) if asked else 1.0,
        "false_positives": false_positives,
        "completeness": all(asked.values()) if asked else True,
        "warnings_coverage": warnings_coverage,
    }
    if must_warn:
        result["trap_detected"] = trap_detected
    return result


def _judge_l1(response: str, expected: dict, config: dict | None = None, debug: bool = False) -> dict:
    """Use LLM judge with rubric questions for L1 (method selection) scoring."""
    rubric = expected.get("rubric", [])
    must_not = expected.get("must_not_recommend", [])

    # Check false positives via keyword (hard negative — no semantic ambiguity)
    text = response.lower()
    false_positives = [m for m in must_not if _method_recommended(m.lower(), text)]

    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(rubric))
    prompt = f"""You are evaluating a causal inference planner's response. Read the response carefully, then answer each question.

<response>
{response}
</response>

Think step by step about each question. For each question, answer true (YES) or false (NO).

Return your answers as a JSON object with an "answers" array of booleans, one per question in order.

Questions:
{numbered}"""

    try:
        answers = _call_judge(prompt, len(rubric), config, debug, label="L1 JUDGE")
        accuracy = sum(answers) / len(answers) if answers else 0.0

        return {
            "correct_method": accuracy >= 0.5,
            "rubric_scores": answers,
            "accuracy": accuracy,
            "false_positives": false_positives,
        }
    except Exception as e:
        print(f"\n    [L1 judge error: {e}]", end="")
        return {
            "correct_method": False,
            "rubric_scores": [],
            "accuracy": 0.0,
            "false_positives": false_positives,
            "error": str(e),
        }


def _check_severity_patterns(response: str, expected_severity: str) -> bool:
    """Pattern-match for canonical severity phrases from the severity contract."""
    text = response.lower()
    if expected_severity == "fatal":
        patterns = [
            r"\*\*fatal:",
            r"\*\*conditional fatal:",
            r"should not proceed",
            r"results.*not trustworthy",
            r"cannot be trusted",
            r"invalidat",
        ]
    elif expected_severity == "serious":
        patterns = [
            r"\*\*serious:",
            r"must prominently acknowledge",
            r"must acknowledge this limitation",
        ]
    else:
        return True  # No severity expected = automatic pass
    return any(re.search(p, text) for p in patterns)


def _judge_l2(response: str, case_expected: dict, config: dict | None = None, debug: bool = False) -> dict:
    """Use LLM judge with binary rubric questions for L2 scoring."""
    must_flag = case_expected.get("must_flag", [])
    severity = case_expected.get("severity", "")

    # Clean cases with no expected flags
    if not must_flag:
        questions = [
            "Does this response raise any alarm or flag any assumption violation that would block the analysis from proceeding? Answer YES or NO."
        ]
        rubric_type = "clean"
    else:
        questions = []
        flag_descriptions = {
            "parallel_trends": "a violation of the parallel trends assumption (pre-treatment trends diverging)",
            "relevance": "a concern about instrument relevance or weakness (e.g., weak first stage, low F-statistic)",
            "weak_instrument": "a weak instrument problem that would make IV estimates unreliable",
            "manipulation": "manipulation or bunching at the cutoff that would invalidate the RDD",
            "no_manipulation": "a density or manipulation test at the cutoff",
            "overlap": "poor overlap or common support between treatment and control groups",
            "positivity": "a positivity violation (some covariate strata have zero probability of treatment)",
            "pre_treatment_fit": "poor pre-treatment fit between the treated unit and its synthetic control",
            "convex_hull": "the treated unit falling outside the convex hull of the donor pool",
            "compliance": "non-compliance, differential compliance, or a gap between treatment assignment and treatment receipt that could bias per-protocol estimates",
            "exclusion": "a concern about the exclusion restriction — the instrument may affect the outcome through channels other than the treatment",
            "post_treatment": "controlling for a post-treatment variable (mediator or collider) that was measured after treatment and could introduce bias",
            "structural_break": "a structural break or regime change in the pre-treatment period that invalidates the counterfactual projection",
        }
        for flag in must_flag:
            desc = flag_descriptions.get(flag, flag.replace("_", " "))
            questions.append(
                f"Does this response flag or discuss {desc}? Answer YES or NO."
            )
        if severity:
            severity_q = {
                "fatal": "Does this response communicate that at least one identified issue is severe enough to invalidate the analysis or make results untrustworthy — through any of: (a) explicitly saying the analysis should not proceed, (b) labeling an issue as 'fatal' or using a stop indicator, (c) stating that estimates are 'unreliable', 'biased', or 'cannot be trusted', or (d) recommending the user abandon the current approach in favor of an alternative method? Answer YES or NO.",
                "serious": "Does this response communicate that at least one identified issue requires substantive methodological changes before results can be interpreted — through any of: (a) labeling an issue as 'serious' or using a warning indicator, (b) recommending alternative estimation strategies, (c) stating that results may be biased or need adjustments, or (d) conditioning the validity of results on passing a diagnostic test? Answer YES or NO.",
            }
            questions.append(severity_q.get(severity, f"Does this response convey {severity}-level concern? Answer YES or NO."))
        rubric_type = "violation"

    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    prompt = f"""You are evaluating a causal inference assistant's response. Read the response carefully, then answer each question.

<response>
{response}
</response>

Think step by step about each question. For each question, answer true (YES) or false (NO).

Return your answers as a JSON object with an "answers" array of booleans, one per question in order.

Questions:
{numbered}"""

    try:
        answers = _call_judge(prompt, len(questions), config, debug, label="JUDGE")

        if rubric_type == "clean":
            false_alarm = answers[0]
            return {
                "violation_detected": not false_alarm,
                "flags_coverage": 1.0 if not false_alarm else 0.0,
                "severity_correct": not false_alarm,
            }
        else:
            flag_answers = answers[:len(must_flag)]
            # Two-pass severity: pattern match first, then judge fallback
            pattern_pass = _check_severity_patterns(response, severity) if severity else True
            judge_answer = answers[len(must_flag)] if severity else True
            severity_answer = pattern_pass or judge_answer
            return {
                "violation_detected": any(flag_answers),
                "flags_coverage": sum(flag_answers) / len(flag_answers) if flag_answers else 1.0,
                "severity_correct": severity_answer,
            }
    except Exception as e:
        # Fallback to string matching if CLI unavailable
        print(f"\n    [judge fallback: {e}]", end="")
        return _score_layer2_string(response, case_expected)


def _score_layer2_string(response: str, expected: dict) -> dict:
    """Score assumption checking via string matching (fallback)."""
    text = response.lower()
    must_flag = expected.get("must_flag", [])
    flagged = {v: v.lower().replace("_", " ") in text for v in must_flag}
    expected_severity = expected.get("severity", "").lower()
    severity_ok = _check_severity_patterns(response, expected_severity) if expected_severity else True
    return {
        "violation_detected": any(flagged.values()) if flagged else True,
        "flags_coverage": sum(flagged.values()) / len(flagged) if flagged else 1.0,
        "severity_correct": severity_ok,
    }


def _score_layer2(response: str, expected: dict, config: dict | None = None, debug: bool = False) -> dict:
    """Score assumption checking — uses LLM judge, falls back to string matching."""
    return _judge_l2(response, expected, config, debug)


def _judge_l4(response: str, case: dict, config: dict | None = None, debug: bool = False) -> dict:
    """Use LLM judge with per-dimension rubric questions for L4 (experience quality) scoring."""
    rubric = case.get("rubric", {})
    dimensions = ["pedagogy", "safety", "actionable"]

    # Collect all questions and track which dimension each belongs to
    questions: list[str] = []
    dim_ranges: dict[str, tuple[int, int]] = {}
    for dim in dimensions:
        dim_questions = rubric.get(dim, [])
        if dim_questions:
            start = len(questions)
            questions.extend(dim_questions)
            dim_ranges[dim] = (start, len(questions))

    if not questions:
        return {
            "pedagogy": 0.0, "safety": 0.0, "actionable": 0.0, "overall": 0.0,
            "error": "No rubric questions found",
        }

    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    prompt = f"""You are evaluating a causal inference assistant's response for experience quality. Read the response carefully, then answer each question.

<response>
{response}
</response>

Think step by step about each question. For each question, answer true (YES) or false (NO).

Return your answers as a JSON object with an "answers" array of booleans, one per question in order.

Questions:
{numbered}"""

    try:
        answers = _call_judge(prompt, len(questions), config, debug, label="L4 JUDGE")

        dim_scores: dict[str, float] = {}
        for dim in dimensions:
            if dim in dim_ranges:
                start, end = dim_ranges[dim]
                dim_answers = answers[start:end]
                dim_scores[dim] = sum(dim_answers) / len(dim_answers)
            else:
                dim_scores[dim] = 0.0

        active = [s for dim, s in dim_scores.items() if dim in dim_ranges]
        overall = sum(active) / len(active) if active else 0.0

        return {**dim_scores, "overall": overall}
    except Exception as e:
        print(f"\n    [L4 judge error: {e}]", end="")
        return {
            "pedagogy": 0.0, "safety": 0.0, "actionable": 0.0, "overall": 0.0,
            "error": str(e),
        }


def score_l5(step1_response: str, step2_response: str, case: dict,
             config: dict | None = None, debug: bool = False) -> dict:
    """Score workflow handoff quality between two skill steps (L5).

    Unlike other scorers, this is not dispatched by score_response since it
    takes two responses (one per skill step).
    """
    rubric_questions = case.get("rubric", [])
    if not rubric_questions:
        return {"handoff_quality": 0.0, "questions_passed": 0, "questions_total": 0,
                "error": "No rubric questions found"}

    steps = case.get("steps", [{}, {}])
    skill1 = steps[0].get("skill", "step-1 skill")
    skill2 = steps[1].get("skill", "step-2 skill")

    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(rubric_questions))
    prompt = f"""You are evaluating the handoff quality between two causal inference skills in a workflow. The first skill ({skill1}) produced a response, and the second skill ({skill2}) consumed it and produced its own response. Read both responses carefully, then answer each question.

<step1_skill>{skill1}</step1_skill>
<step1_response>
{step1_response}
</step1_response>

<step2_skill>{skill2}</step2_skill>
<step2_response>
{step2_response}
</step2_response>

Think step by step about each question. For each question, answer true (YES) or false (NO).

Return your answers as a JSON object with an "answers" array of booleans, one per question in order.

Questions:
{numbered}"""

    try:
        answers = _call_judge(prompt, len(rubric_questions), config, debug, label="L5 JUDGE")

        passed = sum(answers[:len(rubric_questions)])
        total = len(rubric_questions)

        return {
            "handoff_quality": passed / total if total else 0.0,
            "questions_passed": passed,
            "questions_total": total,
        }
    except Exception as e:
        print(f"\n    [L5 judge error: {e}]", end="")
        return {
            "handoff_quality": 0.0,
            "questions_passed": 0,
            "questions_total": len(rubric_questions),
            "error": str(e),
        }


def _score_layer3(response: str, expected: dict, case: dict) -> dict:
    """Score implementation quality — includes code execution."""
    code_blocks = re.findall(r"```(?:python|r|R)\n(.*?)```", response, re.DOTALL)

    must_include = expected.get("must_include", [])
    included = {c: c.lower().replace("_", " ") in response.lower() for c in must_include}

    true_effect = expected.get("true_effect")
    is_exercise = true_effect is None and any("ESTIMATE:" in cb for cb in code_blocks)

    exec_result = {"ran": False, "error": None, "estimate": None}

    if is_exercise:
        # Exercise case: find and run the DGP block to extract runtime ground truth
        dgp_block = next((cb for cb in code_blocks if "ESTIMATE:" in cb), None)
        if dgp_block:
            exec_result = _execute_code(
                dgp_block,
                language=case.get("language", "python"),
            )
            # DGP's ESTIMATE: output IS the ground truth — record it but don't grade accuracy
            # (there's no student analysis code to compare against)
    elif code_blocks and case.get("dataset"):
        # Standard L3 case: run first code block against provided dataset
        exec_result = _execute_code(
            code_blocks[0],
            language=case.get("language", "python"),
            dataset_path=case.get("dataset"),
        )

    # Check estimation accuracy if ground truth provided (non-exercise cases only)
    estimate_ok = None
    if not is_exercise and exec_result["estimate"] is not None and true_effect is not None:
        tolerance = expected.get("tolerance", 1.0)
        estimate_ok = abs(exec_result["estimate"] - true_effect) <= tolerance

    return {
        "has_code": len(code_blocks) > 0,
        "runs_without_error": exec_result["ran"],
        "execution_error": exec_result["error"],
        "estimate": exec_result["estimate"],
        "estimation_accurate": estimate_ok,
        "diagnostic_coverage": sum(included.values()) / len(included) if included else 1.0,
        "must_include_results": included,
    }


def _execute_code(code: str, language: str = "python", dataset_path: str | None = None) -> dict:
    """Execute generated code in a subprocess and capture results."""
    import tempfile

    result = {"ran": False, "error": None, "estimate": None}

    # Prepend dataset loading if dataset provided
    if dataset_path:
        if language == "python":
            # Use non-interactive matplotlib backend to prevent plt.show() blocking
            code = f"import matplotlib\nmatplotlib.use('Agg')\nimport pandas as pd\ndf = pd.read_csv('{dataset_path}')\n" + code
        else:
            code = f'df <- read.csv("{dataset_path}")\n' + code

    # Suppress R warning escalation — print warnings but don't error
    if language != "python":
        code = 'options(warn = 1)\n' + code

    # Ensure directories for CSV writes exist in temp execution context
    import os as _os
    for csv_match in re.findall(r'\.to_csv\(["\'](.+?)["\']\)', code):
        csv_dir = _os.path.dirname(csv_match)
        if csv_dir:
            code = f"import os; os.makedirs('{csv_dir}', exist_ok=True)\n" + code
            break  # Only need one makedirs preamble

    suffix = ".py" if language == "python" else ".R"
    cmd = ["python3"] if language == "python" else ["Rscript"]

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(code)
            f.flush()
            proc = subprocess.run(
                cmd + [f.name], capture_output=True, text=True, timeout=180
            )
        # Extract estimate from output FIRST
        for line in proc.stdout.split("\n"):
            if line.startswith("ESTIMATE:"):
                try:
                    result["estimate"] = float(line.split(":")[1].strip())
                except ValueError:
                    pass

        # Success = clean exit OR produced an estimate despite warnings
        result["ran"] = proc.returncode == 0 or result["estimate"] is not None

        if proc.returncode != 0 and result["estimate"] is None:
            stderr = proc.stderr
            # Strip R package loading messages that obscure real errors
            stderr = re.sub(r'── Attaching.*?── Conflicts.*?\n(?:.*?masks.*?\n)*(?:ℹ.*?\n)*', '', stderr, flags=re.DOTALL)
            stderr = stderr.strip()
            result["error"] = stderr[:500] if stderr else "Non-zero exit code with no error message"
        else:
            result["error"] = None
    except subprocess.TimeoutExpired:
        result["error"] = "Execution timed out (180s)"
    except Exception as e:
        result["error"] = str(e)

    return result


def _method_recommended(method: str, text: str) -> bool:
    """Check if a method appears to be recommended (not just mentioned)."""
    recommend_patterns = [
        f"recommend {method}",
        f"suggest {method}",
        f"use {method}",
        f"{method} would work",
        f"{method} is appropriate",
    ]
    return any(p in text for p in recommend_patterns)
