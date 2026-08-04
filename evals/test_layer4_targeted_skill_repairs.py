"""Structural pins for the seven targeted Layer-4 skill repairs."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def _skill(name: str) -> str:
    return " ".join((SKILLS / name / "SKILL.md").read_text().split())


def _section(name: str, start: str, end: str) -> str:
    raw = (SKILLS / name / "SKILL.md").read_text()
    section = raw.split(start, maxsplit=1)[1].split(end, maxsplit=1)[0]
    return " ".join(section.split())


def test_exercises_separates_iv_strength_validity_and_late():
    text = _skill("causal-exercises")
    for phrase in (
        "treat Step 1 as complete",
        "narrow exception to the normal instruction to conceal",
        "emit the complete runnable generator inline",
        "the generator was not executed",
        "no dataset path exists",
        "relevance/strength and validity as separate questions",
        "robust F statistic",
        "define the compliers in the scenario",
        "effect for those compliers",
    ):
        assert phrase in text


def test_exercises_complete_without_generator_keeps_dgp_hidden():
    raw = (SKILLS / "causal-exercises" / "SKILL.md").read_text()
    complete_branch = raw.split(
        "If difficulty, method, and language are already supplied", maxsplit=1
    )[1].split(
        "When the user explicitly requests the runnable generator", maxsplit=1
    )[0]
    normalized = " ".join(complete_branch.split())

    assert "provide the scenario and precise student deliverable" in normalized
    assert "keep `dgp.[R|py]`, the solution, and the true effect hidden" in normalized
    assert "do not claim that a dataset was created or saved" in normalized
    assert "do not cite a dataset path" in normalized
    assert "generate and save" not in normalized.lower()
    assert "I've generated the dataset at" not in normalized
    assert "docs/causal-exercises/" not in normalized
    assert "runnable data-generation program" not in normalized
    assert "emit the complete runnable generator inline" not in normalized


def test_exercises_generator_fallback_is_honest_without_write_or_execution_tools():
    branch = _section(
        "causal-exercises",
        "When the user explicitly requests the runnable generator",
        "- **Basic**:",
    )
    step3 = _section(
        "causal-exercises",
        "### Step 3: Create and Save Data",
        "### Step 4: Progressive Hints",
    )

    assert "If Bash or Write is unavailable" in branch
    assert "generator was not executed" in branch
    assert "dataset was not saved" in branch
    assert "no dataset path exists" in branch
    assert "Precedence over Step 3" in branch
    assert "complete-exercise and explicit-generator branches" in branch
    assert "supersede Step 3's execution, save, and path-announcement instructions" in branch
    assert "only after a DGP actually runs and its files are actually written" in branch
    assert "Run the DGP code (using Bash tool)" in step3
    assert "I've generated the dataset at [path]" in step3


def test_planner_first_turn_is_one_question_and_actionable():
    first_question = _section(
        "causal-planner",
        "Follow-up questions should refine the recommendation",
        "**First-turn minimum deliverable**",
    )
    first_deliverable = _section(
        "causal-planner",
        "**First-turn minimum deliverable**",
        "### Phase 1: Setting & Objective (P1-P2)",
    )
    mandatory_checks = _section(
        "causal-planner",
        "**Prior exposure check (ask on every case)**",
        "### Phase 2: Assignment Mechanism (P3)",
    )
    for phrase in (
        "exactly one follow-up question in the first response",
        "exact-one rule governs the first response",
        "mandatory over the full interview",
        "defer it to a later turn",
        "permission to ask a second first-turn question",
    ):
        assert phrase in first_question

    for phrase in (
        "name the provisional downstream `/causal-*` skill",
        "conditional primary recommendation",
        "hardest identifying assumption",
        "single discriminating data check",
    ):
        assert phrase in first_deliverable

    assert "ask on every case" in mandatory_checks
    assert "External events check (ask on every case)" in mandatory_checks


def test_matching_fully_specified_direct_mode_has_pedagogy():
    direct = _section(
        "causal-matching",
        "**Fully specified direct mode**",
        "**Canonical runnable block**",
    )
    stage2 = _section(
        "causal-matching",
        "## Stage 2: Assumptions",
        "## Stage 3: Implementation",
    )
    stage3 = _section(
        "causal-matching",
        "## Stage 3: Implementation",
        "## Stage 4: Falsification / Robustness",
    )
    for phrase in (
        "Direct mode overrides only interactive pauses",
        "known fatal violation takes precedence over direct mode",
        "guarded runnable block replaces the later instruction to wait",
        "narrow precedence rule",
        "supersedes the Stage 2 wait clause",
        "Stage 3 prohibition on restructuring",
        "Permit only that minimal reordering and guard wrapper",
        "does not authorize a claim that any code or diagnostic was executed",
        "Put the testable gates first in the runnable code",
        "stop before effect estimation",
        "observed balance cannot test CIA",
        "does not mean any diagnostic has run",
        "absolute SMD below 0.10",
        "conditional independence (CIA)",
        "hidden-bias sensitivity analysis",
        "PSM is transparent",
        "consistent if either the propensity model or the outcome model is correctly specified",
        "not protected when both models are misspecified",
        "still requires exchangeability",
    ):
        assert phrase in direct

    assert "require the user to report the diagnostic result first" in stage2
    assert "Do not restructure the code" in stage3
    assert direct.index("Put the testable gates first") < direct.index(
        "Only after those checks pass may the code estimate the treatment effect"
    )
    assert "protects against misspecifying either" not in direct


def test_rdd_direct_mode_places_bandwidth_and_donut_guidance_early():
    direct = _section(
        "causal-rdd",
        "**Fully specified direct mode**",
        "**Suspected manipulation — first response**",
    )
    manipulation = _section(
        "causal-rdd",
        "**Suspected manipulation — first response**",
        "**Canonical runnable block**",
    )
    stage2 = _section(
        "causal-rdd",
        "## Stage 2: Assumptions",
        "## Stage 3: Implementation",
    )
    stage3 = _section(
        "causal-rdd",
        "## Stage 3: Implementation",
        "## Stage 4: Falsification / Robustness",
    )
    for phrase in (
        "Direct mode overrides only interactive pauses",
        "known fatal violation takes precedence over direct mode",
        "guarded runnable block replaces the later instruction to wait",
        "narrow precedence rule",
        "supersedes the Stage 2 wait clause",
        "Stage 3 prohibition on restructuring",
        "Permit only that minimal reordering and guard wrapper",
        "does not authorize a claim that any code or diagnostic was executed",
        "suspected-manipulation first-response branch",
        "Put `rddensity` and predetermined-covariate continuity checks before",
        "stop before effect estimation",
        "substantive, untestable requirements",
        "does not mean it ran",
        "narrower window compares more similar units",
    ):
        assert phrase in direct

    for phrase in (
        "Suspected manipulation — first response",
        "manipulation mechanism is credibly confined",
        "not salvageable by a donut",
        "conditional donut-hole sensitivity code",
        "wins even when the user asks for the complete response now",
        "do not let direct mode bypass the unresolved manipulation gate",
    ):
        assert phrase in f"Suspected manipulation — first response {manipulation}"

    assert direct.index("Put `rddensity`") < direct.index(
        "Only if those checks pass may the code calculate the main effect"
    )
    assert "require the user to report the diagnostic result first" in stage2
    assert "Do not restructure the code" in stage3


def test_report_one_go_mode_preserves_no_fabrication_boundary():
    direct = _section(
        "causal-report",
        "### Direct one-go report mode",
        "### Language preference:",
    )
    figures = _section(
        "causal-report",
        "For each figure:",
        "**Figure naming convention**",
    )
    for phrase in (
        "Draft all nine sections in one response",
        "takes precedence over the Stage 1 interview",
        "Unavailable from supplied materials",
        "do not call this a full regression table",
        "full estimation code was not provided",
    ):
        assert phrase in direct

    assert "complete bounded report, not invented evidence" in direct
    assert "Never manufacture placeholder code" in direct
    assert "parallel-trends figure and the event-study figure" in figures
    assert "Do not claim that a PNG exists" in figures


def test_sc_fully_specified_direct_mode_has_required_diagnostics():
    text = _section(
        "causal-sc",
        "**Fully specified direct mode**",
        "**Determine variant**",
    )
    for phrase in (
        "Direct mode overrides only interactive pauses",
        "known fatal violation takes precedence over direct mode",
        "guarded runnable block replaces the later instruction to wait",
        "Start the runnable code with donor eligibility and data-coverage checks",
        "stop before effect estimation",
        "substantive assumptions",
        "does not mean any diagnostic has run",
        "enough pre-treatment outcomes to construct outcome-based predictors",
        "code to calculate pre-treatment RMSPE and explain what the measure means",
        "concentrated on one or two donors",
        "donor-pool inclusion is a substantive researcher decision",
        "include in-space placebo code",
    ):
        assert phrase in text

    assert text.index("Start the runnable code") < text.index(
        "Only if those gates pass may the code calculate the post-treatment gap"
    )


def test_timeseries_direct_modes_and_tail_area_interpretation():
    direct = _section(
        "causal-timeseries",
        "**Fully specified direct mode**",
        "**Determine variant**",
    )
    stage2 = _section(
        "causal-timeseries",
        "## Stage 2: Assumptions",
        "## Stage 3: Implementation",
    )
    stage3 = _section(
        "causal-timeseries",
        "## Stage 3: Implementation",
        "## Stage 4: Falsification / Robustness",
    )
    text = _skill("causal-timeseries")
    for phrase in (
        "Direct mode overrides only interactive pauses",
        "known fatal violation",
        "takes precedence over direct mode",
        "guarded runnable block replaces the later instruction to wait",
        "narrow precedence rule",
        "supersedes the Stage 2 wait clause",
        "Stage 3 prohibition on restructuring",
        "Permit only that minimal reordering and guard wrapper",
        "does not authorize a claim that any code or diagnostic was executed",
        "Start the runnable code with structural-break and stationarity checks",
        "stop before effect estimation",
        "substantive assumptions",
        "does not mean any diagnostic has run",
        "CausalArima versus CausalImpact",
        "only a descriptive supplement",
        "pre-period holdout MAPE",
    ):
        assert phrase in direct

    assert direct.index("Start the runnable code") < direct.index(
        "Only if those diagnostics pass may the code fit the final counterfactual model"
    )
    assert "require the user to report the diagnostic result first" in stage2
    assert "Do not restructure the code" in stage3

    for phrase in (
        "posterior tail-area probability",
        "neither the probability that the intervention 'caused a real effect' "
        "nor a frequentist p-value",
    ):
        assert phrase in text
