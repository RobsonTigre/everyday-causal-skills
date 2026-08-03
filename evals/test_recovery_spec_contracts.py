"""Structural pins for the v0.6.0 instrument-recovery specification repairs."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases"
SKILLS = ROOT / "skills"


def _case(layer: int, name: str) -> dict:
    return yaml.safe_load((CASES / f"layer{layer}" / f"{name}.yaml").read_text())


def _normalized_skill(name: str) -> str:
    return " ".join((SKILLS / name / "SKILL.md").read_text().split())


def _normalized_case_message(layer: int, name: str) -> str:
    return " ".join(_case(layer, name)["user_message"].split())


def _normalized_case_rubric(layer: int, name: str) -> str:
    rubric = _case(layer, name)["rubric"]
    return " ".join(item for criteria in rubric.values() for item in criteria)


def test_deferred_rubric_is_exactly_the_unreachable_policy_table():
    expected = {
        "report_no_artifacts": [
            "Does the report skill create a project folder? (no Write grant in this sandbox)",
            "Does it produce a report in academic mode from the interview answers? (impossible in one turn — the interview answers don't exist yet)",
        ],
        "dag_pedagogy_clean": [
            "Does it justify the adjustment set (not just list it)? (only reachable once the DAG interview has moved past turn one)",
        ],
        "dag_pedagogy_messy": [
            "Does it produce a concrete adjustment set recommendation? (only reachable once the DAG interview has moved past turn one)",
        ],
        "report_figures_success": [
            "Does it execute the plotting code and save rendered PNG files? (unreachable without Bash/Write tools)",
            "Does it embed the rendered PNGs in the report markdown with correct image references? (unreachable until PNG files exist)",
        ],
        "report_standalone": [
            "Does the report skill create a project folder and report artifact without requiring a prior skill to have run? (no Write grant in this sandbox)",
        ],
    }
    found = {}
    for path in sorted(CASES.rglob("*.yaml")):
        case = yaml.safe_load(path.read_text()) or {}
        if "deferred_rubric" in case:
            found[case["name"]] = case["deferred_rubric"]
    assert found == expected


def test_named_layer4_cases_pin_response_phase_and_repaired_requests():
    contracts = {
        "did_pedagogy_clean": "final_output",
        "exercise_iv_quality": "final_output",
        "experiments_pedagogy_messy": "final_output",
        "iv_pedagogy_clean": "final_output",
        "matching_pedagogy_clean": "final_output",
        "planner_interview_guard": "first_turn",
        "planner_pedagogy_ambiguous": "first_turn",
        "planner_pedagogy_clear": "first_turn",
        "rdd_pedagogy_clean": "final_output",
        "rdd_pedagogy_messy": "first_turn",
        "report_figures_success": "final_output",
        "report_tone_academic": "final_output",
        "roi_pedagogy_clean": "final_output",
        "sc_pedagogy_clean": "final_output",
        "timeseries_pedagogy_clean": "final_output",
        "timeseries_pedagogy_controls": "final_output",
    }
    for name, contract in contracts.items():
        assert _case(4, name)["response_contract"] == contract, name

    prompt_pins = {
        "did_pedagogy_clean": (
            "These are the final inputs",
            "complete explanation, diagnostics, and runnable R analysis now",
            "do not stop for an intake question",
        ),
        "exercise_iv_quality": (
            "strength separately from instrument validity",
            "scenario's compliers",
        ),
        "experiments_pedagogy_messy": (
            "complete response and runnable analysis code now",
            "do not stop for an intake question",
        ),
        "iv_pedagogy_clean": (
            "These are the final inputs",
            "complete explanation, diagnostics, and runnable Python analysis now",
            "do not stop for an intake question",
        ),
        "matching_pedagogy_clean": (
            "ATT on recovery time",
            "complete response and runnable analysis now",
            "do not stop for an intake question",
        ),
        "rdd_pedagogy_clean": (
            "complete explanation",
            "diagnostics, and runnable analysis now",
            "do not stop for an intake question",
        ),
        "rdd_pedagogy_messy": (
            "immediate test and decision rule",
        ),
        "sc_pedagogy_clean": (
            "Unit 1",
            "period 21",
            "units 2 through 10",
            "full explanation, Synth code",
        ),
        "timeseries_pedagogy_clean": (
            "months 1-36 are pre-period",
            "no known seasonality",
            "no concurrent event",
            "structural-break preflight has already passed",
            "complete response, runnable code, diagnostics, and visualization now",
        ),
        "timeseries_pedagogy_controls": (
            "months 1-50 are pre-period",
            "controls were unaffected",
            "stable throughout the pre-period",
            "structural-break preflight passed",
            "complete response, runnable code, diagnostics, and visualization now",
        ),
    }
    for name, phrases in prompt_pins.items():
        text = _normalized_case_message(4, name)
        for phrase in phrases:
            assert phrase in text, (name, phrase)

    rubric_pins = {
        "exercise_iv_quality": ("strong and a weak first stage",),
        "experiments_pedagogy_messy": (
            "additional compliance strata",
            "without inventing numerical estimates",
        ),
        "matching_pedagogy_clean": (
            "|SMD| < 0.10",
            "doubly robust estimator would be preferred",
        ),
        "planner_interview_guard": (
            "preliminary method recommendation",
            "exactly one follow-up question",
        ),
        "planner_pedagogy_ambiguous": (
            "conditional primary recommendation",
            "hardest identifying assumption",
            "first discriminating data check",
        ),
        "planner_pedagogy_clear": (
            "provisional /causal-did skill",
            "treatment timing/cohort",
        ),
        "rdd_pedagogy_clean": ("bias-variance trade-off directly",),
        "rdd_pedagogy_messy": (
            "cannot salvage broader sorting",
            "donut-hole sensitivity",
        ),
        "timeseries_pedagogy_clean": (
            "CausalArima",
            "descriptive level/slope supplement",
        ),
        "timeseries_pedagogy_controls": (
            "avoiding the claim that it is a frequentist p-value",
        ),
    }
    for name, phrases in rubric_pins.items():
        text = _normalized_case_rubric(4, name)
        for phrase in phrases:
            assert phrase in text, (name, phrase)


def test_report_cases_pin_no_fabrication_and_reachable_figure_fallbacks():
    figures = _normalized_case_message(4, "report_figures_success")
    for phrase in (
        "already-completed DiD analysis",
        "completed event-study plotting inputs",
        "without rerunning or inventing analysis results",
        "parallel-trends and event-study figures",
        "complete runnable plotting code for each figure",
    ):
        assert phrase in figures, phrase

    figures_rubric = _normalized_case_rubric(4, "report_figures_success")
    for phrase in (
        "complete runnable Python plotting-code fallback for a parallel-trends figure",
        "complete runnable Python plotting-code fallback for an event-study figure",
    ):
        assert phrase in figures_rubric, phrase

    academic = _normalized_case_message(4, "report_tone_academic")
    for phrase in (
        "everything I have",
        "full report now in one go",
        "noting anything unavailable as such",
        "don't ask me follow-up questions first",
    ):
        assert phrase in academic, phrase

    academic_rubric = _normalized_case_rubric(4, "report_tone_academic")
    for phrase in (
        "standard error, sample size, R-squared",
        "marked as unavailable rather than fabricating them",
        "all nine report sections",
        "full estimation code is unavailable",
        "exact missing code/data",
    ):
        assert phrase in academic_rubric, phrase


def test_roi_clean_case_supplies_complete_canonical_mode_c_output():
    message = _case(4, "roi_pedagogy_clean")["user_message"]
    expected = {
        "EFFECTIVE_PERIODS": "6.9317167158",
        "PV_INCREMENTAL_PROFIT_PER_UNIT": "21.4883218191",
        "PV_INCREMENTAL_PROFIT": "16331124.5825",
        "NET_PROFIT": "8625980.3453",
        "ROI": "1.1195092629",
        "ROI_LO": "0.5041678640",
        "ROI_HI": "1.7348506618",
        "BREAKEVEN_EFFECT": "1.4626027139",
        "VERDICT_CODE": "1",
    }
    for key, value in expected.items():
        assert f"{key}: {value}" in message, key
    text = _normalized_case_rubric(4, "roi_pedagogy_clean")
    assert "lower effect bound clears breakeven but not the 2x buffer" in text


def test_sc_clean_case_uses_complete_existing_fixture():
    case = _case(4, "sc_pedagogy_clean")
    assert case["dataset"] == "evals/data/sc_basic_l3.csv"
    assert case["dataset_contract"] == {
        "columns": ["unit", "time", "outcome", "treated", "post"],
        "n_rows": 300,
    }


def test_dataset_dependent_l2_prompts_expose_diagnostics():
    required_phrases = {
        "did_clean_parallel": ("0.012", "p = 0.76"),
        "did_nonparallel_trends": ("0.776", "p < 0.001"),
        "iv_weak_instrument": ("F = 0.47", "partial R-squared = 0.00047"),
        "matching_good_overlap": ("0.164 to 0.803", "0.200 to 0.808"),
        "matching_poor_overlap": ("0.753", "499 of 500"),
        "rdd_clean_cutoff": ("54 and 59", "does not reject continuity"),
        "rdd_manipulation": ("18 students", "120"),
    }
    for name, phrases in required_phrases.items():
        message = _case(2, name)["user_message"]
        for phrase in phrases:
            assert phrase in message, (name, phrase)


def test_collider_case_states_complete_common_effect():
    message = _case(2, "dag_collider_bias")["user_message"]
    for edge in ("gender -> occupation", "ability -> occupation", "ability -> wages"):
        assert edge in message


def test_l3_exercises_have_saved_final_output_contracts():
    fixtures = {
        "exercise_dgp_did": "retail-loyalty-did",
        "exercise_dgp_iv": "training-encouragement-iv",
    }
    for name, fixture_name in fixtures.items():
        case = _case(3, name)
        assert case["response_contract"] == "final_output"
        assert case["input_mode"] == "artifact"
        assert case["execution_mode"] == "exercise"
        assert case["required_output"] == "estimate"
        fixture = case["artifact_fixture"]
        assert fixture["source"].endswith(fixture_name)
        dgp = ROOT / fixture["source"] / "dgp.py"
        compile(dgp.read_text(), str(dgp), "exec")
        assert "ESTIMATE:" in dgp.read_text()


def test_exercise_quality_cases_supply_difficulty_and_request_completion():
    for name in ("exercise_did_quality", "exercise_iv_quality"):
        message = _case(4, name)["user_message"]
        assert "Intermediate difficulty" in message
        assert "Generate the complete exercise now" in message


def test_clean_experiment_case_is_analysis_ready_final_output():
    case = _case(4, "experiments_pedagogy_clean")
    assert case["response_contract"] == "final_output"
    assert case["input_mode"] == "dataset"
    assert case["dataset"] == "evals/data/experiments_simple.csv"
    assert "Do not stop for an intake question" in case["user_message"]


def test_dag_r_case_declares_plot_dependency_and_substantive_guards():
    case = _case(3, "dag_dagitty_r")
    assert "ggplot2" in case["requires"]
    guards = case["expected"]["must_include_code"]
    for token in ("X -> D", "X -> Y", "D -> M", "M -> Y", "adjustmentSets"):
        assert token in guards


def test_dag_r_skill_requires_one_clean_process_block_with_all_imports():
    text = _normalized_skill("causal-dag")
    assert "one self-contained fenced `r` block" in text
    assert "run from a clean process" in text
    assert (
        "load `dagitty`, `ggdag`, and `ggplot2` inside the marked block before using them"
        in text
    )
    assert "Do not rely on a separate preflight block" in text
    assert "take precedence over the R template's multiple-fence structure" in text


def test_code_emitting_skills_and_repaired_l3_prompts_pin_canonical_sentinel():
    l3_cases = [
        yaml.safe_load(path.read_text())
        for path in sorted((CASES / "layer3").glob("*.yaml"))
    ]
    l3_skills = {case["skill"] for case in l3_cases}
    expected_skills = {
        "causal-dag",
        "causal-did",
        "causal-exercises",
        "causal-experiments",
        "causal-iv",
        "causal-matching",
        "causal-rdd",
        "causal-roi",
        "causal-sc",
        "causal-timeseries",
    }
    assert l3_skills == expected_skills
    for skill in l3_skills:
        text = _normalized_skill(skill)
        assert "exact line `# EVAL_EXECUTABLE`" in text, skill
        assert "first nonblank program line" in text, skill
        assert "Do not indent it or add other text on that line" in text, skill
    for name in ("dag_dagitty_r", "exercise_dgp_did", "exercise_dgp_iv"):
        assert "# EVAL_EXECUTABLE" in _case(3, name)["user_message"], name


def test_valid_failure_skill_repairs_are_pinned():
    pins = {
        "causal-planner": (
            "First-turn minimum deliverable",
            "When more than one design is credible",
            "For partial exposure",
        ),
        "causal-matching": (
            "When the prompt already supplies treatment, outcome, covariates",
            "post-adjustment balance",
        ),
        "causal-dag": (
            "Never re-ask for a supplied treatment or outcome",
            "a collider is a common effect",
        ),
        "causal-did": (
            "When the prompt already supplies the design and data schema",
            "Required program versus optional diagnostics",
        ),
        "causal-experiments": (
            "When a completed experiment and analysis-ready schema are supplied",
            "always separate ITT",
        ),
        "causal-iv": (
            "teach and operationalize all four IV conditions",
            "2SLS identifies a LATE for compliers",
        ),
        "causal-rdd": (
            "the estimand is local to units near the cutoff",
            "destroying the local like-for-like comparison",
        ),
    }
    for skill, phrases in pins.items():
        text = _normalized_skill(skill)
        for phrase in phrases:
            assert phrase in text, (skill, phrase)
