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
