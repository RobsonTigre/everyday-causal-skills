"""Execution regression tests: the R timeseries template's own code, run for real.

Every other guard in this suite is offline by design (`test_shipped_apis.py`,
`test_template_ordering.py`, ...) -- this file is the deliberate exception. It exists
because a hand-written R script that merely proves "R can solve this problem" is not the
same claim as "the template's own code pattern, copied verbatim per
skills/causal-timeseries/SKILL.md's 'exactly, then adapt only variable names' rule, runs
against a real case's data." The R CausalArima block passed raw character dates into
`CausalArima(dates = df$date, ...)` for months without anything ever running that literal
code against a real dataset -- discovered only by extracting and executing the template's
actual text, not a paraphrase of it.

Extracts the literal fenced R blocks from templates/r/timeseries.md, substitutes only the
documented placeholder covariate names and case-specific date literals (the same
adaptations SKILL.md already asks a live model to make -- never a structural change), and
runs the assembled script through scorer._score_layer3 against the real L3 fixture CSVs.

Skipped entirely if Rscript is unavailable, keeping the rest of the offline suite
dependency-free.

Run: python3 -m pytest evals/test_l3_r_templates.py -v   (from repo root)
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorer import _score_layer3  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE = _REPO_ROOT / "templates" / "r" / "timeseries.md"

pytestmark = pytest.mark.skipif(
    shutil.which("Rscript") is None,
    reason="Rscript not available -- these tests execute the real R template")


def _r_blocks(text: str) -> list[str]:
    return re.findall(r"```r\n(.*?)```", text, re.DOTALL)


def _preflight_block() -> str:
    """The 'Prerequisites' fenced block -- the library() calls every downstream block
    depends on (tidyverse's `%>%`, in particular). Always the first `r` block."""
    return _r_blocks(_TEMPLATE.read_text())[0]


def _data_prep_block() -> str:
    """The 'Data Preparation' fenced block -- date conversion + ts_data construction.
    Always the second `r` block, right after the Prerequisites preflight block."""
    return _r_blocks(_TEMPLATE.read_text())[1]


def _block_containing(marker: str) -> str:
    for block in _r_blocks(_TEMPLATE.read_text()):
        if marker in block:
            return block
    raise AssertionError(f"no R block in {_TEMPLATE} contains {marker!r}")


def test_causalarima_template_runs_against_its_own_case_fixture():
    # CausalArima has no covariates, so the ARIMA case's CSV is just date,outcome --
    # the full Data Preparation block's ts_data construction (which selects
    # covariate1/covariate2) would crash on this fixture and isn't needed for this path.
    # Only the date-conversion fix line applies here; extract it literally.
    prep = _data_prep_block()
    date_fix_line = next(ln for ln in prep.splitlines() if "as.Date(df$date)" in ln)
    assert "df$date <- as.Date(df$date)" in date_fix_line, date_fix_line

    arima_block = _block_containing("CausalArima(")
    script = (
        f"{_preflight_block()}\n"
        f"{date_fix_line}\n"
        'intervention_date <- as.Date("2023-03-12")\n'
        f"{arima_block}\n"
        'cat(sprintf("ESTIMATE:%f\\n", mean(ca_fit$causal.effect)))\n'
    )

    case = {"dataset": "evals/data/timeseries_causalarima_l3.csv",
            "language": "r", "requires": ["CausalArima"]}
    expected = {"true_effect": 4.0, "tolerance": 2.5,
                "must_include": ["pre_treatment", "confidence_interval"]}
    result = _score_layer3(
        f"```r\n{script}```\n\nChecked pre treatment fit and report a 95 percent "
        "confidence interval from the bootstrap distribution.",
        expected, case)

    assert result["runs_without_error"] is True, result
    assert result["estimation_accurate"] is True, result


def test_causalimpact_controls_template_runs_against_its_own_case_fixture():
    prep = _data_prep_block()
    # Documented adaptation only: the template's placeholder covariate names for this
    # case's real column names. Same substitution SKILL.md already asks a model to make.
    prep = prep.replace("covariate1, covariate2", "control1, control2")
    prep = prep.replace(
        'intervention_date <- as.Date("2020-01-01")  # Set your intervention date',
        'intervention_date <- as.Date("2022-03-01")')
    prep = prep.replace(
        'pre.period  <- as.Date(c("2018-01-01", "2019-12-31"))',
        'pre.period  <- as.Date(c("2018-01-01", "2022-02-01"))')
    prep = prep.replace(
        'post.period <- as.Date(c("2020-01-01", "2021-12-31"))',
        'post.period <- as.Date(c("2022-03-01", "2024-08-01"))')

    impact_block = _block_containing("CausalImpact(")
    script = (
        f"{_preflight_block()}\n"
        f"{prep}\n"
        f"{impact_block}\n"
        'cat(sprintf("ESTIMATE:%f\\n", impact$summary$AbsEffect[1]))\n'
    )

    case = {"dataset": "evals/data/timeseries_causalimpact_controls_l3.csv",
            "language": "r", "requires": ["CausalImpact", "zoo"]}
    expected = {"true_effect": 5.0, "tolerance": 2.5,
                "must_include": ["pre_treatment", "confidence_interval"]}
    result = _score_layer3(
        f"```r\n{script}```\n\nChecked pre treatment fit and CausalImpact reports a "
        "95 percent confidence interval around the absolute effect.",
        expected, case)

    assert result["runs_without_error"] is True, result
    assert result["estimation_accurate"] is True, result
