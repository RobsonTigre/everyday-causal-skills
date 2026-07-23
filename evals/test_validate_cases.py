"""Unit tests for the case-schema validator.
Run: python3 evals/test_validate_cases.py   (from repo root)
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_cases import validate_case, validate_tree, warn_case  # noqa: E402

L4_GOOD = """
name: good_l4
description: fine
layer: 4
skill: causal-did
user_message: hello
rubric:
  pedagogy:
    - "Q1?"
  safety:
    - "Q2?"
"""

L4_FLAT_RUBRIC = """
name: bad_l4
description: rubric in the wrong place
layer: 4
skill: causal-did
user_message: hello
expected:
  rubric:
    - "Q1?"
"""

L5_GOOD = """
name: good_l5
description: fine
layer: 5
steps:
  - skill: causal-planner
    scenario: do a thing
  - skill: causal-did
    input_from: step_1
    scenario: continue
rubric:
  - "Q1?"
"""

L5_NO_STEPS = """
name: bad_l5
description: single-skill shape
layer: 5
skill: causal-report
user_message: hello
rubric:
  - "Q1?"
"""


def _write(tmp, layer_dir, filename, text):
    d = Path(tmp) / layer_dir
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(text)
    return p


def test_valid_l4_passes():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "good_l4.yaml", L4_GOOD)
        assert validate_case(p) == [], validate_case(p)


def test_l4_flat_rubric_under_expected_is_caught():
    # This exact shape scored a silent 0.0 on every run for months.
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "bad_l4.yaml", L4_FLAT_RUBRIC)
        errs = validate_case(p)
        assert any("expected.rubric" in e for e in errs), errs


def test_valid_l5_passes():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer5", "good_l5.yaml", L5_GOOD)
        assert validate_case(p) == [], validate_case(p)


def test_l5_without_steps_is_caught():
    # runner.py indexes case["steps"] — this shape KeyErrors on every run.
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer5", "bad_l5.yaml", L5_NO_STEPS)
        errs = validate_case(p)
        assert any("steps" in e for e in errs), errs


def test_name_must_match_filename():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "renamed.yaml", L4_GOOD)
        errs = validate_case(p)
        assert any("does not match filename" in e for e in errs), errs


def test_layer_must_match_directory():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer3", "good_l4.yaml", L4_GOOD)
        errs = validate_case(p)
        assert any("lives in layer3" in e for e in errs), errs


def test_missing_reference_path_is_caught():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "good_l4.yaml",
                   L4_GOOD + "references:\n  - references/nope_does_not_exist.md\n")
        errs = validate_case(p)
        assert any("reference not found" in e for e in errs), errs


def test_duplicate_names_reported_on_both_paths():
    with tempfile.TemporaryDirectory() as t:
        _write(t, "layer4", "good_l4.yaml", L4_GOOD)
        _write(t, "layer5", "good_l4.yaml", L4_GOOD)
        problems = validate_tree(Path(t))
        assert len(problems) == 2, problems
        assert all(any("duplicate case name" in e for e in errs)
                   for errs in problems.values()), problems


def test_real_case_tree_is_valid():
    problems = validate_tree()
    assert problems == {}, problems


# --- Dead-metadata detection -------------------------------------------------

def _warn(text: str, name: str = "probe") -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"{name}.yaml"
        p.write_text(text)
        return warn_case(p)


def test_unknown_expected_key_is_flagged_as_dead_metadata():
    # Ten L2 cases carried a `must_not_miss` list nothing had ever read. A warning
    # list that only knows a hardcoded pair cannot catch that; the schema can.
    warnings = _warn("""
name: probe
description: fine
layer: 2
skill: causal-did
user_message: hello
expected:
  must_flag: [overlap]
  must_not_miss: [overlap]
""")
    assert any("must_not_miss" in w and "dead metadata" in w for w in warnings), warnings


def test_unknown_top_level_key_is_flagged():
    warnings = _warn("""
name: probe
description: fine
layer: 2
skill: causal-did
user_message: hello
invented_key: [something]
expected:
  must_flag: []
""")
    assert any("invented_key" in w for w in warnings), warnings


def test_dataset_is_allowed_at_every_layer():
    # runner.py injects the dataset schema into user_message regardless of layer, so
    # `dataset` is consumed everywhere. Flagging it would have condemned 24 live cases.
    for layer, extra in ((2, "expected:\n  must_flag: []"),
                         (4, "rubric:\n  pedagogy:\n    - \"Q?\"")):
        warnings = _warn(f"""
name: probe
description: fine
layer: {layer}
skill: causal-did
user_message: hello
dataset: evals/data/did_clean.csv
{extra}
""")
        assert not any("dataset" in w for w in warnings), (layer, warnings)


def test_l3_keys_are_not_allowed_at_l2():
    warnings = _warn("""
name: probe
description: fine
layer: 2
skill: causal-did
user_message: hello
expected:
  must_flag: []
  true_effect: 1.0
""")
    assert any("true_effect" in w for w in warnings), warnings


def test_clean_case_produces_no_warnings():
    assert _warn(L4_GOOD, name="good_l4") == []


# --- Grading contract (D1): response_contract / input_mode / deferred_rubric ---

def test_grading_contract_fields_are_legal_and_not_dead_metadata():
    # A case using all three fields with legal values must be both valid and
    # warning-free — the whole point of D1 is that they are real schema, not
    # unread metadata.
    text = """
name: probe
description: fine
layer: 4
skill: causal-did
user_message: hello
response_contract: first_turn
input_mode: inline
deferred_rubric:
  - "Was the adjustment set correctly justified?"
rubric:
  pedagogy:
    - "Q1?"
"""
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", text)
        assert validate_case(p) == [], validate_case(p)
    assert _warn(text, name="probe") == []


def test_illegal_response_contract_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:", "response_contract: sometimes\nrubric:"))
        errs = validate_case(p)
        assert any("response_contract" in e for e in errs), errs


def test_illegal_input_mode_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:", "input_mode: telepathy\nrubric:"))
        errs = validate_case(p)
        assert any("input_mode" in e for e in errs), errs


def test_illegal_severity_is_an_error():
    # D9: `_check_severity_patterns` (scorer.py) treats any value outside
    # scorer.SEVERITIES as "no severity expected" and auto-passes -- a typo here
    # would silently never be checked, at any threshold, on any run, forever.
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer2", "probe.yaml", """
name: probe
description: fine
layer: 2
skill: causal-did
user_message: hello
expected:
  must_flag: [overlap]
  severity: ftal
""")
        errs = validate_case(p)
        assert any("severity" in e for e in errs), errs


def test_legal_severity_values_are_valid():
    for severity in ("fatal", "serious", ""):
        with tempfile.TemporaryDirectory() as t:
            p = _write(t, "layer2", "probe.yaml", f"""
name: probe
description: fine
layer: 2
skill: causal-did
user_message: hello
expected:
  must_flag: [overlap]
  severity: {severity!r}
""")
            assert validate_case(p) == [], (severity, validate_case(p))


def test_empty_deferred_rubric_is_an_error():
    # Absent is legitimate (most first_turn cases defer nothing); present-but-
    # empty is a pointless, likely-accidental declaration.
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:", "deferred_rubric: []\nrubric:"))
        errs = validate_case(p)
        assert any("deferred_rubric" in e for e in errs), errs


def test_deferred_rubric_non_string_entry_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:", "deferred_rubric: [1, 2]\nrubric:"))
        errs = validate_case(p)
        assert any("deferred_rubric" in e for e in errs), errs


# --- Dataset contract (D4): dataset_contract / columns+n_rows vs. the real fixture ---

def test_dataset_contract_matching_fixture_is_valid():
    with tempfile.TemporaryDirectory() as t:
        csv_path = Path(t) / "probe.csv"
        csv_path.write_text("a,b,c\n1,2,3\n4,5,6\n")
        p = _write(t, "layer4", "good_l4.yaml", L4_GOOD.replace(
            "rubric:",
            f"dataset: {csv_path}\ndataset_contract:\n  columns: [a, b, c]\n  n_rows: 2\nrubric:"))
        assert validate_case(p) == [], validate_case(p)


def test_dataset_contract_wrong_columns_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        csv_path = Path(t) / "probe.csv"
        csv_path.write_text("a,b,c\n1,2,3\n")
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            f"dataset: {csv_path}\ndataset_contract:\n  columns: [x, y, z]\n  n_rows: 1\nrubric:"))
        errs = validate_case(p)
        assert any("dataset_contract.columns" in e for e in errs), errs


def test_dataset_contract_wrong_row_count_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        csv_path = Path(t) / "probe.csv"
        csv_path.write_text("a,b\n1,2\n3,4\n")
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            f"dataset: {csv_path}\ndataset_contract:\n  columns: [a, b]\n  n_rows: 999\nrubric:"))
        errs = validate_case(p)
        assert any("dataset_contract.n_rows" in e for e in errs), errs


def test_dataset_contract_without_dataset_field_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:", "dataset_contract:\n  columns: [a, b]\n  n_rows: 1\nrubric:"))
        errs = validate_case(p)
        assert any("dataset_contract requires a dataset" in e for e in errs), errs


def test_dataset_contract_empty_columns_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        csv_path = Path(t) / "probe.csv"
        csv_path.write_text("a,b\n1,2\n")
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            f"dataset: {csv_path}\ndataset_contract:\n  columns: []\n  n_rows: 1\nrubric:"))
        errs = validate_case(p)
        assert any("dataset_contract.columns must be" in e for e in errs), errs


# --- Artifact fixture (D5): input_mode: artifact / artifact_fixture: {source, dest} ---

def test_artifact_fixture_with_real_source_is_valid():
    with tempfile.TemporaryDirectory() as t:
        fixture_dir = Path(t) / "fixture"
        fixture_dir.mkdir()
        (fixture_dir / "plan.md").write_text("hi")
        p = _write(t, "layer4", "good_l4.yaml", L4_GOOD.replace(
            "rubric:",
            f"input_mode: artifact\nartifact_fixture:\n  source: {fixture_dir}\n"
            f"  dest: docs/causal-plans/probe\nrubric:"))
        assert validate_case(p) == [], validate_case(p)


def test_artifact_input_mode_without_fixture_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:", "input_mode: artifact\nrubric:"))
        errs = validate_case(p)
        assert any("requires an artifact_fixture" in e for e in errs), errs


def test_artifact_fixture_without_artifact_input_mode_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        fixture_dir = Path(t) / "fixture"
        fixture_dir.mkdir()
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            f"input_mode: inline\nartifact_fixture:\n  source: {fixture_dir}\n"
            f"  dest: docs/causal-plans/probe\nrubric:"))
        errs = validate_case(p)
        assert any("only meaningful with input_mode: artifact" in e for e in errs), errs


def test_artifact_fixture_missing_source_directory_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            "input_mode: artifact\nartifact_fixture:\n"
            "  source: evals/fixtures/does-not-exist\n"
            "  dest: docs/causal-plans/probe\nrubric:"))
        errs = validate_case(p)
        assert any("not found or not a directory" in e for e in errs), errs


def test_artifact_fixture_dest_escaping_sandbox_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        fixture_dir = Path(t) / "fixture"
        fixture_dir.mkdir()
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            f"input_mode: artifact\nartifact_fixture:\n  source: {fixture_dir}\n"
            f"  dest: ../../etc\nrubric:"))
        errs = validate_case(p)
        assert any("must be a relative path with no '..'" in e for e in errs), errs


def test_d2_migration_is_confined_to_the_approved_checkpoint_table():
    # D1 landed the mechanism with zero cases using it (superseded test:
    # test_real_case_tree_declares_no_grading_contract_fields_yet asserted exactly
    # that). D2, checkpoint-approved 2026-07-22 against the plan's rev. 3 table
    # (lines 741-783), migrates exactly these 22 cases onto response_contract — no
    # more, no fewer. `report_full_artifacts` / `report_partial_artifacts` needed
    # D5's fixture provisioning first (now done), so every approved case must be
    # migrated with the approved value.
    import yaml
    approved = {
        "dag_clean_confounder": "final_output",
        "dag_frontdoor": "final_output",
        "dag_collider_bias": "first_turn",
        "dag_mbias": "first_turn",
        "dag_pedagogy_clean": "first_turn",
        "dag_pedagogy_messy": "first_turn",
        "hte_pedagogy_clean": "final_output",
        "hte_pedagogy_messy": "final_output",
        "hte_no_heterogeneity": "first_turn",
        "hte_poor_subgroup_overlap": "first_turn",
        "hte_post_treatment_modifier": "first_turn",
        "report_full_artifacts": "final_output",
        "report_no_artifacts": "first_turn",
        "report_partial_artifacts": "final_output",
        "report_figures_fallback": "final_output",
        "report_figures_success": "final_output",
        "report_standalone": "final_output",
        "report_tone_academic": "final_output",
        "report_tone_business": "final_output",
        "report_tone_hybrid": "final_output",
        "planner_pedagogy_ambiguous": "first_turn",
        "planner_pedagogy_clear": "first_turn",
    }
    cases_dir = Path("evals/cases")
    found = {}
    for path in sorted(cases_dir.rglob("*.yaml")):
        case = yaml.safe_load(path.read_text()) or {}
        name = case.get("name")
        contract = case.get("response_contract")
        if contract is not None:
            found[name] = contract
        elif name in approved:
            raise AssertionError(f"{name} is approved for D2 but declares no response_contract")

    d3_names = {
        "dag_interview_guard", "planner_interview_guard",
        "hte_interview_guard", "report_interview_guard",
    }
    for name, contract in found.items():
        assert name in approved or name in d3_names, (
            f"{name} declares response_contract but is not in the approved D2 table "
            "or the D3 interview-guard set")
        if name in approved:
            assert contract == approved[name], (name, contract, approved[name])


def test_d3_interview_guards_are_exactly_four_first_turn_skill_specific_cases():
    # D3: one interview-regression guard per skill (dag, planner, hte, report), each
    # graded on that skill's own interview contract, not a shared rubric — a universal
    # "did it ask a question" check would manufacture a false measurement (plan lines
    # 785-793). All four are first_turn: the point is to catch a regression that makes
    # the skill stop interviewing, which only shows up in what turn one does.
    import yaml
    expected = {
        "dag_interview_guard": "causal-dag",
        "planner_interview_guard": "causal-planner",
        "hte_interview_guard": "causal-hte",
        "report_interview_guard": "causal-report",
    }
    cases_dir = Path("evals/cases")
    found = {}
    for path in sorted(cases_dir.rglob("*.yaml")):
        case = yaml.safe_load(path.read_text()) or {}
        name = case.get("name")
        if name in expected:
            found[name] = case

    assert set(found) == set(expected), (set(found), set(expected))
    for name, skill in expected.items():
        case = found[name]
        assert case.get("skill") == skill, (name, case.get("skill"), skill)
        assert case.get("response_contract") == "first_turn", (name, case.get("response_contract"))
        assert case.get("layer") == 4, (name, case.get("layer"))
        rubric = case.get("rubric") or {}
        # Skill-specific: no two guards may share a rubric line verbatim.
        all_qs = [q for dim in rubric.values() for q in dim]
        assert all_qs, f"{name} has no rubric questions"
    seen_questions = {}
    for name in expected:
        for q in [q for dim in found[name].get("rubric", {}).values() for q in dim]:
            assert q not in seen_questions, (
                f"{name} shares a rubric line with {seen_questions.get(q)}: {q!r}")
            seen_questions[q] = name


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run_all()
