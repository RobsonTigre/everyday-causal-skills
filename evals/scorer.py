"""
Scorer for everyday-causal-skills eval outputs.
Parses model responses and scores against expected outcomes.

Judge calls use `claude -p` (Max subscription) instead of the Anthropic SDK,
so no API key is needed.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

# Case `dataset:` paths are declared relative to the repo root, but generated code runs
# in a temp cwd, so they are resolved against this.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: `artifact_fixture.source` (D5) must resolve inside this directory -- shared by
#: validate_cases.py and runner.py so the confinement boundary is defined once, not
#: duplicated as a literal that could drift between the two checkers (the same reasoning
#: SEVERITIES below uses).
FIXTURES_ROOT = Path(_REPO_ROOT) / "evals" / "fixtures"


def run_subprocess_grouped(args, timeout, capture_output=True, text=True,
                           cwd=None, term_grace=10.0):
    """Like subprocess.run, but the child is its own process group so a timeout
    can be cleaned up without leaving orphaned grandchildren behind.

    subprocess.run's own timeout handling only ever reaches the direct child —
    it kills it but never exposes the pid, so anything the child spawned
    survives. Here we own the Popen, so on timeout we SIGTERM the whole group,
    give it `term_grace` seconds, SIGKILL if it is still alive, then drain.
    Always raises subprocess.TimeoutExpired on timeout, matching subprocess.run's
    contract so callers need no changes beyond the call site itself.
    """
    proc = subprocess.Popen(
        args, cwd=cwd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=text, start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_group(proc, term_grace)
        raise
    return subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)


def _terminate_group(proc, grace):
    """SIGTERM the process group, wait, SIGKILL if still alive, then drain.

    Draining via communicate() (not just wait()) after the kill mirrors what
    subprocess.run itself does on its own timeout path — wait() alone can
    deadlock if the child left enough buffered output to fill the pipe.
    """
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.communicate(timeout=grace)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass
    proc.communicate()


class JudgeError(RuntimeError):
    """The judge did not produce a valid, complete measurement.

    Raised instead of returning a degraded score. A judge that is rate-limited,
    timing out, or replying off-schema yields no measurement at all — callers
    record the run as invalid so it can be requeued. Silently substituting
    zeros here is what made whole sweeps unusable.

    Carries `reason` so callers can tell a genuine timeout (`judge_timeout`,
    terminal — see `_with_judge_retries`) from a malformed reply
    (`malformed_response`) or a generic failure (`judge_error`, the default).
    """

    def __init__(self, message: str, reason: str = "judge_error"):
        super().__init__(message)
        self.reason = reason


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


def _with_judge_retries(attempt_fn, config: dict | None, label: str):
    """Call attempt_fn(), retrying JudgeError with exponential backoff.

    Rate limiting is transient, so a failed measurement is worth retrying before
    the run is abandoned. Persistent failure raises rather than degrading.

    A genuine timeout is terminal, not retried: repeating the same wait three
    times just burns 3x the time for the same outcome, which is what let a
    single slow judge call stall a whole sweep.
    """
    judge_config = (config or {}).get("judge", {})
    max_attempts = int(judge_config.get("max_attempts", 3))
    backoff = float(judge_config.get("retry_backoff", 5.0))

    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            return attempt_fn()
        except JudgeError as e:
            if e.reason == "judge_timeout":
                raise
            last_err = e
            if attempt < max_attempts and backoff:
                time.sleep(backoff * 2 ** (attempt - 1))
    raise JudgeError(f"{label}: giving up after {max_attempts} attempt(s): {last_err}",
                     reason=last_err.reason if last_err else "judge_error")


def _call_judge_once(prompt: str, num_questions: int, config: dict | None = None,
                     debug: bool = False, label: str = "JUDGE") -> list[bool]:
    """One judge call. Raises JudgeError unless it yields exactly num_questions answers."""
    judge_config = (config or {}).get("judge", {})
    judge_model_raw = judge_config.get("model", "claude-sonnet-4-20250514")
    model = _MODEL_MAP.get(judge_model_raw, judge_model_raw)
    timeout = int(judge_config.get("timeout", 120))

    try:
        proc = run_subprocess_grouped(
            [
                "claude", "-p", prompt,
                "--model", model,
                "--output-format", "json",
                "--json-schema", _JUDGE_SCHEMA,
                "--tools", "",
                "--no-session-persistence",
                "--setting-sources", "local",
            ],
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise JudgeError(f"{label}: claude -p timed out after {timeout}s",
                         reason="judge_timeout") from e

    if proc.returncode != 0:
        raise JudgeError(f"{label}: claude -p exited {proc.returncode}: {proc.stderr[:500]}")

    try:
        resp = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as e:
        raise JudgeError(f"{label}: unparseable claude -p stdout: {proc.stdout[:200]}",
                         reason="malformed_response") from e

    if resp.get("is_error"):
        raise JudgeError(f"{label}: claude -p error: {resp.get('result', 'unknown')}")

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

    # Strict count: a short reply is an incomplete measurement, and an over-long
    # one misaligns per-dimension slices. Neither may be scored.
    if len(answers) != num_questions:
        raise JudgeError(
            f"{label}: expected {num_questions} answers, got {len(answers)}",
            reason="malformed_response")

    return answers


def _call_judge(prompt: str, num_questions: int, config: dict | None = None,
                debug: bool = False, label: str = "JUDGE") -> list[bool]:
    """Call claude -p as a structured-output judge and return one boolean per question.

    Uses the Max subscription (no API key). Raises JudgeError if a valid,
    complete set of answers cannot be obtained within the retry budget.
    """
    return _with_judge_retries(
        lambda: _call_judge_once(prompt, num_questions, config, debug, label),
        config, label)


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
    timeout = int(judge_config.get("l0_timeout", 30))

    def attempt():
        try:
            result = run_subprocess_grouped(
                [
                    "claude", "-p", prompt,
                    "--model", model,
                    "--output-format", "text",
                    "--tools", "",
                    "--no-session-persistence",
                    "--setting-sources", "local",
                ],
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise JudgeError(f"L0 JUDGE: claude -p timed out after {timeout}s",
                             reason="judge_timeout") from e
        if result.returncode != 0:
            raise JudgeError(
                f"L0 JUDGE: claude -p exited {result.returncode}: {result.stderr[:500]}")
        text = result.stdout.strip().upper()
        first = text.split("\n")[0]
        # An empty or off-script reply is no measurement. Reading it as "not
        # triggered" silently PASSES every should_trigger: false case.
        if "YES" not in first and "NO" not in first:
            raise JudgeError(f"L0 JUDGE: no YES/NO in reply: {text[:200]!r}",
                             reason="malformed_response")
        return text, "YES" in first

    answer, triggered = _with_judge_retries(attempt, config, "L0 JUDGE")

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
        # Rubric questions may live under expected.rubric or at case level
        # (the report_* cases carry a top-level rubric).
        rubric = expected.get("rubric") or case.get("rubric") or []
        scores = _score_layer2(response, expected, config, debug, rubric=rubric)
        # response_contract / deferred_rubric (D1): declarative case metadata,
        # not judge output. _judge_l2 only receives `expected` + `rubric`, not
        # the full case, so this is injected here rather than inside it —
        # mirrors what _judge_l4 already does directly, since L4 has `case`
        # in scope. Absent on every case today, so inert until D2 uses it.
        return {**scores, "response_contract": case.get("response_contract"),
                "deferred_rubric": case.get("deferred_rubric") or []}
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

    answers = _call_judge(prompt, len(rubric), config, debug, label="L1 JUDGE")
    accuracy = sum(answers) / len(answers) if answers else 0.0

    return {
        "correct_method": accuracy >= 0.5,
        "rubric_scores": answers,
        "accuracy": accuracy,
        "false_positives": false_positives,
    }


#: The only `severity` values this scorer implements a pattern for. Shared with
#: validate_cases.py so a typo (or a new severity level introduced without wiring a
#: pattern here) is rejected at validation time instead of silently auto-passing --
#: `_check_severity_patterns` treats any unrecognised value as "no severity expected".
SEVERITIES = {"fatal", "serious"}


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


def _judge_l2(response: str, case_expected: dict, config: dict | None = None, debug: bool = False,
              rubric: list | None = None) -> dict:
    """Use LLM judge with binary rubric questions for L2 scoring.

    `rubric` is an optional list of extra judge questions (from expected.rubric
    or the case-level rubric field). Rubric questions are appended AFTER the
    flag/severity questions so existing answer indices are unchanged; their
    pass fraction is returned as `rubric_coverage` (absent when no rubric).
    """
    must_flag = case_expected.get("must_flag", [])
    severity = case_expected.get("severity", "")
    rubric = rubric or []

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
            "manipulation_test": "a density or manipulation test at the cutoff",
            "overlap": "poor overlap or common support between treatment and control groups",
            # Unused by any current case (kept, not dropped — it documents a real
            # concept the map already covers, and removing a mapped-but-idle entry
            # for no functional gain is not worth the churn).
            "positivity": "a positivity violation (some covariate strata have zero probability of treatment)",
            "pre_treatment_fit": "poor pre-treatment fit between the treated unit and its synthetic control",
            "convex_hull": "the treated unit falling outside the convex hull of the donor pool",
            "compliance": "non-compliance, differential compliance, or a gap between treatment assignment and treatment receipt that could bias per-protocol estimates",
            "exclusion": "a concern about the exclusion restriction — the instrument may affect the outcome through channels other than the treatment",
            "post_treatment": "controlling for a post-treatment variable (mediator or collider) that was measured after treatment and could introduce bias",
            "structural_break": "a structural break or regime change in the pre-treatment period that invalidates the counterfactual projection",
            "late_extrapolation": "the problem of scaling a complier-specific (LATE) effect to non-compliers or the full population without justification",
            "audit_carryover": "the upstream audit's non-fatal finding carried forward as a named risk or caveat (without converting it into a numeric adjustment)",
            "missing_financial_inputs": "that required financial or business inputs are missing and must be provided (or explicitly ranged) before a final verdict",
            "collider_bias": "collider bias — conditioning on a variable that is a common effect of two other variables, which opens a spurious association between them",
            "m_bias": "M-bias — conditioning on a pre-treatment variable that is itself a collider between an unmeasured cause of treatment and an unmeasured cause of the outcome, inducing bias rather than removing it",
            "no_backdoor_adjustment": "the absence of a valid backdoor adjustment set (e.g., because a needed confounder is unobserved), requiring an alternative identification strategy such as the front-door criterion",
            "no_heterogeneity": "a lack of meaningful treatment effect heterogeneity (e.g., a null or non-significant BLP/GATES result), which should temper any targeting or personalization recommendation",
            "missing_plan": "that the causal plan (plan.md) is missing from the available artifacts and should be flagged as a gap",
            "missing_audit": "that the validity audit (audit.md) is missing from the available artifacts and should be flagged as a gap",
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

    # Optional rubric questions go LAST so flag/severity answer indices stay stable.
    rubric_start = len(questions)
    questions.extend(rubric)

    numbered = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    prompt = f"""You are evaluating a causal inference assistant's response. Read the response carefully, then answer each question.

<response>
{response}
</response>

Think step by step about each question. For each question, answer true (YES) or false (NO).

Return your answers as a JSON object with an "answers" array of booleans, one per question in order.

Questions:
{numbered}"""

    answers = _call_judge(prompt, len(questions), config, debug, label="JUDGE")

    rubric_answers = answers[rubric_start:] if rubric else []
    rubric_extra = (
        {"rubric_coverage": sum(rubric_answers) / len(rubric_answers)} if rubric else {}
    )

    if rubric_type == "clean":
        false_alarm = answers[0]
        return {
            "violation_detected": not false_alarm,
            "flags_coverage": 1.0 if not false_alarm else 0.0,
            "severity_correct": not false_alarm,
            **rubric_extra,
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
            **rubric_extra,
        }


def _score_layer2(response: str, expected: dict, config: dict | None = None, debug: bool = False,
                  rubric: list | None = None) -> dict:
    """Score assumption checking via LLM judge."""
    return _judge_l2(response, expected, config, debug, rubric=rubric)


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

    # response_contract / deferred_rubric (D1) are declarative case metadata,
    # not judge output — passed through unchanged so aggregate() can surface
    # deferred criteria in the verdict. Absent on every case today (D1 is
    # mechanism only; D2 migrates cases), so this is inert until then.
    #
    # Which dimensions the case actually populates — the gate scores only these,
    # so an absent dimension is skipped rather than counted as a 0.0.
    return {**dim_scores, "overall": overall, "dimensions_present": sorted(dim_ranges),
            "response_contract": case.get("response_contract"),
            "deferred_rubric": case.get("deferred_rubric") or []}


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

    answers = _call_judge(prompt, len(rubric_questions), config, debug, label="L5 JUDGE")

    passed = sum(answers[:len(rubric_questions)])
    total = len(rubric_questions)

    return {
        "handoff_quality": passed / total if total else 0.0,
        "questions_passed": passed,
        "questions_total": total,
    }


def must_include_alternates(term) -> tuple[str, list[str]]:
    """Normalize one `must_include` entry to (canonical_key, [accepted phrasings]).

    A term is either a plain string, or a list of interchangeable phrasings whose
    FIRST element is the canonical key. Alternates exist because the metric matches
    literal substrings: did_basic_2x2 reported a 95% CI six different ways and still
    scored zero for never writing "confidence interval". Keying on the first element
    keeps results comparable across runs no matter which phrasing matched.

    Raises ValueError on shapes the validator is expected to have rejected already.
    """
    if isinstance(term, str):
        if not term.strip():
            raise ValueError("must_include term is empty")
        return term, [term]
    if isinstance(term, (list, tuple)):
        if not term:
            raise ValueError("must_include alternates list is empty")
        if not all(isinstance(a, str) and a.strip() for a in term):
            raise ValueError(
                f"must_include alternates must all be non-empty strings: {term!r}")
        return term[0], list(term)
    raise ValueError(
        f"must_include term must be a string or a list of strings, got {type(term).__name__}")


def _score_layer3(response: str, expected: dict, case: dict) -> dict:
    """Score implementation quality — includes code execution."""
    code_blocks = re.findall(r"```(?:python|r|R)\n(.*?)```", response, re.DOTALL)

    must_include = expected.get("must_include", [])
    resp_lower = response.lower()
    included = {}
    for term in must_include:
        canonical, alternates = must_include_alternates(term)
        included[canonical] = any(
            alt.lower().replace("_", " ") in resp_lower for alt in alternates)

    # Code-scoped guard: match only inside fenced code blocks, not prose.
    code_text = "\n".join(code_blocks).lower()
    must_not_include = expected.get("must_not_include", [])
    must_include_code = expected.get("must_include_code", [])
    must_not_results = {t: (t.lower() in code_text) for t in must_not_include}   # True = violation
    code_presence = {t: (t.lower() in code_text) for t in must_include_code}      # False = missing
    guard_passed = (not any(must_not_results.values())) and all(code_presence.values())

    true_effect = expected.get("true_effect")
    expected_values = expected.get("values") or {}
    is_exercise = (true_effect is None and not expected_values
                   and any("ESTIMATE:" in cb for cb in code_blocks))

    # Nothing-executed must be distinguishable from executed-and-crashed. Leaving this
    # as error=None made a prose-only reply look identical to a failing script, which is
    # exactly how exercise_dgp_iv read as a crash in 4 of 5 runs when in fact no code
    # was ever produced. The default below is overwritten whenever execution happens.
    if not code_blocks:
        _why_not = ("no runnable code block found in the response — expected a "
                    f"{case.get('language', 'python')} block")
    elif is_exercise:
        _why_not = ("no runnable code found — this exercise case needs a code block "
                    "printing an ESTIMATE: line to recover ground truth")
    else:
        _why_not = ("no runnable code was executed — the response has code but the case "
                    "declares neither `dataset` nor `expected.code_runs`, so nothing "
                    "selected it to run (case configuration issue, not a skill failure)")
    exec_result = {"ran": False, "error": _why_not, "estimate": None}

    if is_exercise:
        # Exercise case: find and run the DGP block to extract runtime ground truth
        dgp_block = next((cb for cb in code_blocks if "ESTIMATE:" in cb), None)
        if dgp_block:
            exec_result = _execute_code(
                dgp_block,
                language=case.get("language", "python"),
                requires=case.get("requires"),
            )
    elif code_blocks and (case.get("dataset") or expected.get("code_runs")):
        # Standard L3 case or dataset-free case (e.g., DAG structural code)
        exec_result = _execute_code(
            code_blocks[0],
            language=case.get("language", "python"),
            dataset_path=case.get("dataset"),
            requires=case.get("requires"),
        )

    # Check estimation accuracy if ground truth provided (non-exercise cases only).
    # None means the gate does not apply to this case at all; a case that declares a
    # true effect and then reports no estimate has failed it, not skipped it.
    estimate_ok = None
    if not is_exercise and true_effect is not None:
        if exec_result["estimate"] is None:
            estimate_ok = False
        else:
            tolerance = expected.get("tolerance", 1.0)
            estimate_ok = abs(exec_result["estimate"] - true_effect) <= tolerance

    # Named-value accuracy: expected.values maps KEY -> number or
    # KEY -> {value, tol}. Values are parsed from KEY:<float> lines in the
    # executed output. Feeds the existing estimation_accurate metric ONLY when
    # no true_effect is set — the single-true_effect path is untouched.
    values_results = {}
    if expected_values:
        got = exec_result.get("values") or {}
        default_tol = expected.get("values_tolerance", 1e-6)
        for key, spec in expected_values.items():
            if isinstance(spec, dict):
                want, tol = float(spec["value"]), float(spec.get("tol", default_tol))
            else:
                want, tol = float(spec), default_tol
            have = got.get(key)
            values_results[key] = (have is not None) and (abs(have - want) <= tol)
        if true_effect is None:
            estimate_ok = all(values_results.values())

    return {
        "has_code": len(code_blocks) > 0,
        "runs_without_error": exec_result["ran"],
        "execution_error": exec_result["error"],
        "estimate": exec_result["estimate"],
        "estimation_accurate": estimate_ok,
        "diagnostic_coverage": sum(included.values()) / len(included) if included else 1.0,
        "must_include_results": included,
        "guard_passed": guard_passed,
        "must_not_include_results": must_not_results,
        "must_include_code_results": code_presence,
        "values_results": values_results,
    }


def _execute_code(code: str, language: str = "python", dataset_path: str | None = None,
                  requires: list | None = None) -> dict:
    """Execute generated code in a subprocess and capture results."""
    import tempfile

    result = {"ran": False, "error": None, "estimate": None, "values": {}}

    # Configurable interpreters (default to current behavior).
    py_interp = os.environ.get("EVAL_PYTHON", "python3")
    r_interp = os.environ.get("EVAL_RSCRIPT", "Rscript")

    # Preflight: required packages must import under the chosen interpreter.
    for mod in (requires or []):
        if language == "python":
            chk = subprocess.run([py_interp, "-c", f"import {mod}"],
                                 capture_output=True, text=True)
            interp = py_interp
        else:
            chk = subprocess.run([r_interp, "-e", f"library({mod})"],
                                 capture_output=True, text=True)
            interp = r_interp
        if chk.returncode != 0:
            result["error"] = f"Required package '{mod}' not importable under {interp}"
            return result

    # Prepend dataset loading if dataset provided. Cases declare paths relative to the
    # repo root (`evals/data/...`), but the code runs in a temp cwd, so resolve here.
    if dataset_path:
        abs_dataset = os.path.abspath(os.path.join(_REPO_ROOT, dataset_path))
        if language == "python":
            # Use non-interactive matplotlib backend to prevent plt.show() blocking
            code = f"import matplotlib\nmatplotlib.use('Agg')\nimport pandas as pd\ndf = pd.read_csv({abs_dataset!r})\n" + code
        else:
            code = f'df <- read.csv({abs_dataset!r})\n' + code

    # Suppress R warning escalation — print warnings but don't error
    if language != "python":
        code = 'options(warn = 1)\n' + code

    # Ensure directories for CSV writes exist in temp execution context
    for csv_match in re.findall(r'\.to_csv\(["\'](.+?)["\']\)', code):
        csv_dir = os.path.dirname(csv_match)
        if csv_dir:
            code = f"import os; os.makedirs('{csv_dir}', exist_ok=True)\n" + code
            break  # Only need one makedirs preamble

    suffix = ".py" if language == "python" else ".R"
    cmd = [py_interp] if language == "python" else [r_interp]

    try:
        # Run inside a throwaway directory. Generated code calls savefig("x.png") and
        # to_csv("y.csv") with bare names; inheriting the repo root as cwd littered it
        # with artifacts that then showed up as dirty paths in the sweep fingerprint.
        # The dataset path is resolved to an absolute path above, before the preamble is
        # built, so relative `evals/data/...` declarations survive the cwd change.
        with tempfile.TemporaryDirectory(prefix="eval-exec-") as workdir:
            script = os.path.join(workdir, f"generated{suffix}")
            with open(script, "w") as f:
                f.write(code)
            proc = subprocess.run(
                cmd + [script], capture_output=True, text=True, timeout=180,
                cwd=workdir,
            )
        # Extract estimate from output FIRST
        for line in proc.stdout.split("\n"):
            if line.startswith("ESTIMATE:"):
                try:
                    result["estimate"] = float(line.split(":")[1].strip())
                except ValueError:
                    pass

        # Extract all named KEY:<float> outputs (uppercase keys) for
        # expected.values scoring — same convention as the parity runner.
        for m in re.finditer(
                r'^([A-Z][A-Z0-9_]*)\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$',
                proc.stdout, re.MULTILINE):
            try:
                result["values"][m.group(1)] = float(m.group(2))
            except ValueError:
                pass

        # Success requires a clean exit, full stop. Previously an estimate printed
        # before a crash counted as a successful run and its stderr was thrown away,
        # so a script that died partway through registered as green.
        result["ran"] = proc.returncode == 0

        if proc.returncode != 0:
            stderr = proc.stderr
            # Strip R package loading messages that obscure real errors
            stderr = re.sub(r'── Attaching.*?── Conflicts.*?\n(?:.*?masks.*?\n)*(?:ℹ.*?\n)*', '', stderr, flags=re.DOTALL)
            stderr = stderr.strip()
            detail = stderr[:500] if stderr else "no error message on stderr"
            got = ("" if result["estimate"] is None
                   else f" (an ESTIMATE was printed before the failure: {result['estimate']})")
            result["error"] = f"exit code {proc.returncode}: {detail}{got}"
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
