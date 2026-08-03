"""Structural contract for the outcome-only SC direct-mode fixture."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "causal-sc" / "SKILL.md"


def _direct_section() -> str:
    raw = SKILL.read_text()
    return raw.split("**Fully specified direct mode**", maxsplit=1)[1].split(
        "**Determine variant**", maxsplit=1
    )[0]


def test_sc_direct_mode_precedence_keeps_known_fatal_override():
    direct = " ".join(_direct_section().split())

    for phrase in (
        "takes precedence over Stage 3's template-adherence rule",
        "missing-package pause",
        "fixture-specific `Synth` path",
        "fatal verdict wins over direct mode",
        "do not calculate or interpret an effect",
    ):
        assert phrase in direct


def test_sc_outcome_only_fixture_uses_literal_synth_inputs():
    direct = _direct_section()

    for pattern in (
        'required_columns <- c("unit", "time", "outcome", "treated", "post")',
        "treated_id <- 1L",
        "intervention <- 21L",
        "donor_ids <- 2:10",
        "special.predictors = outcome_history",
        'dependent = "outcome"',
        'unit.variable = "unit"',
        'time.variable = "time"',
        "time.optimize.ssr = pre_periods",
    ):
        assert pattern in direct

    assert "never invent\n`predictor1` or `predictor2`" in direct
    runnable = direct.split("```r", maxsplit=1)[1].split("```", maxsplit=1)[0]
    assert "predictor1" not in runnable
    assert "predictor2" not in runnable


def test_sc_fixture_code_orders_diagnostics_before_effect_and_inference():
    direct = _direct_section()
    runnable = direct.split("```r", maxsplit=1)[1].split("```", maxsplit=1)[0]

    for pattern in (
        "outside_hull <-",
        "pre_rmspe = sqrt",
        "print(weights)",
        "if (!fit_ok)",
        "positive_donors <-",
        "loo <- lapply",
        "placebos <- lapply",
        "placebo_ratios <-",
        "pseudo_p <-",
        "do not claim diagnostics passed or interpret the effect",
    ):
        assert pattern in direct

    assert runnable.index("if (!fit_ok)") < runnable.index("effect <-")
    assert runnable.index("loo <- lapply") < runnable.index("effect <-")
    assert runnable.index("effect <-") < runnable.index("placebos <- lapply")
    assert "no effect or placebo rank was estimated" in runnable
