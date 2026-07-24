"""Unit tests for the case-schema validator.
Run: python3 evals/test_validate_cases.py   (from repo root)
"""
import os
import sys
import tempfile
from pathlib import Path

import yaml

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
    # source must resolve under evals/fixtures/ (confinement) -- a real fixture lives
    # there, so the probe dir does too rather than at system temp.
    with tempfile.TemporaryDirectory() as t, \
            tempfile.TemporaryDirectory(dir="evals/fixtures") as fixture_dir:
        Path(fixture_dir, "plan.md").write_text("hi")
        rel_source = os.path.relpath(fixture_dir)
        p = _write(t, "layer4", "good_l4.yaml", L4_GOOD.replace(
            "rubric:",
            f"input_mode: artifact\nartifact_fixture:\n  source: {rel_source}\n"
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


def test_artifact_fixture_source_outside_fixtures_root_is_an_error():
    # The concrete threat: a source that's a real, existing, readable directory --
    # just not under evals/fixtures/. Before this check, is_dir() alone would have
    # accepted it and shutil.copytree would copy it wholesale into the sandbox. An
    # absolute path to a real directory outside evals/fixtures/ is exactly this case --
    # unlike dest, an absolute source isn't rejected on style; containment decides it.
    with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as outside:
        Path(outside, "plan.md").write_text("hi")
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            f"input_mode: artifact\nartifact_fixture:\n  source: {outside}\n"
            f"  dest: docs/causal-plans/probe\nrubric:"))
        errs = validate_case(p)
        assert any("must be under evals/fixtures/" in e for e in errs), errs

    # Same containment failure, reached via a relative (not absolute) path this time.
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            "input_mode: artifact\nartifact_fixture:\n"
            "  source: evals/data\n"
            "  dest: docs/causal-plans/probe\nrubric:"))
        errs = validate_case(p)
        assert any("must be under evals/fixtures/" in e for e in errs), errs


def test_artifact_fixture_dotdot_source_is_an_error():
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            "input_mode: artifact\nartifact_fixture:\n"
            "  source: ../../etc\n"
            "  dest: docs/causal-plans/probe\nrubric:"))
        errs = validate_case(p)
        assert any("source must not contain '..'" in e for e in errs), errs


def test_artifact_fixture_absolute_source_inside_fixtures_root_is_valid():
    # Unlike dest, an absolute source is fine as long as it resolves inside
    # evals/fixtures/ -- containment is the authoritative check, not path style.
    with tempfile.TemporaryDirectory() as t, \
            tempfile.TemporaryDirectory(dir="evals/fixtures") as fixture_dir:
        assert Path(fixture_dir).is_absolute(), fixture_dir
        Path(fixture_dir, "plan.md").write_text("hi")
        p = _write(t, "layer4", "good_l4.yaml", L4_GOOD.replace(
            "rubric:",
            f"input_mode: artifact\nartifact_fixture:\n  source: {fixture_dir}\n"
            f"  dest: docs/causal-plans/probe\nrubric:"))
        assert validate_case(p) == [], validate_case(p)


def test_artifact_fixture_symlinked_file_inside_confined_source_is_an_error():
    # Confining the source ROOT isn't enough: shutil.copytree's default symlinks=False
    # dereferences symlinks during copy, so a symlink inside an otherwise-confined
    # fixture can pull in file content from anywhere on disk. Verified manually with a
    # symlink to /etc/hosts; using a synthetic file here so the test is portable.
    with tempfile.TemporaryDirectory() as t, \
            tempfile.TemporaryDirectory(dir="evals/fixtures") as fixture_dir, \
            tempfile.TemporaryDirectory() as outside:
        Path(fixture_dir, "plan.md").write_text("legit content")
        secret = Path(outside, "secret.txt")
        secret.write_text("should never leak")
        os.symlink(secret, Path(fixture_dir, "evil_link"))
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            f"input_mode: artifact\nartifact_fixture:\n  source: {fixture_dir}\n"
            f"  dest: docs/causal-plans/probe\nrubric:"))
        errs = validate_case(p)
        assert any("symlink" in e for e in errs), errs


def test_artifact_fixture_symlinked_dir_inside_confined_source_is_an_error():
    with tempfile.TemporaryDirectory() as t, \
            tempfile.TemporaryDirectory(dir="evals/fixtures") as fixture_dir, \
            tempfile.TemporaryDirectory() as outside:
        Path(fixture_dir, "plan.md").write_text("legit content")
        Path(outside, "secret.txt").write_text("should never leak")
        os.symlink(outside, Path(fixture_dir, "evil_dir"))
        p = _write(t, "layer4", "probe.yaml", L4_GOOD.replace(
            "rubric:",
            f"input_mode: artifact\nartifact_fixture:\n  source: {fixture_dir}\n"
            f"  dest: docs/causal-plans/probe\nrubric:"))
        errs = validate_case(p)
        assert any("symlink" in e for e in errs), errs


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


# --- Package F: L2 rubric entries are objects, and only at layer 2 ---

L2_HEAD = """
name: {name}
description: fine
layer: 2
skill: causal-dag
user_message: hello
expected:
  must_flag: []
"""


def _l2(body: str, name: str = "good_l2") -> str:
    return L2_HEAD.format(name=name) + body


L2_GOOD = _l2("""
rubric:
  - id: first_criterion
    question: "Q1?"
    required: true
  - id: second_criterion
    question: "Q2?"
    required: false
""")


def _errs(text, name="good_l2.yaml"):
    with tempfile.TemporaryDirectory() as t:
        p = _write(t, "layer2", name, text)
        return validate_case(p)


def test_l2_object_rubric_passes():
    assert _errs(L2_GOOD) == [], _errs(L2_GOOD)


def test_l2_string_rubric_is_rejected():
    # The pre-F shape. Accepting it silently would leave the criterion unmeasurable:
    # no id means no per-question answer, and the gate can never see it.
    errs = _errs(_l2('rubric:\n  - "Q1?"\n'))
    assert any("mapping" in e for e in errs), errs


def test_l2_duplicate_ids_rejected():
    errs = _errs(_l2("""
rubric:
  - id: same_id
    question: "Q1?"
    required: true
  - id: same_id
    question: "Q2?"
    required: true
"""))
    assert any("duplicate" in e for e in errs), errs


def test_l2_non_snake_case_id_rejected():
    for bad in ("CamelCase", "has spaces", "9leading_digit", "trailing_"):
        errs = _errs(_l2(f"""
rubric:
  - id: "{bad}"
    question: "Q1?"
    required: true
"""))
        assert any("snake_case" in e for e in errs), (bad, errs)


def test_l2_empty_question_rejected():
    errs = _errs(_l2("""
rubric:
  - id: ok_id
    question: "   "
    required: true
"""))
    assert any("question" in e for e in errs), errs


def test_l2_non_boolean_required_rejected():
    # "yes" and 1 are both truthy — a case meaning "required" would silently get a
    # non-bool that later compares unequal to True.
    for bad in ('"yes"', "1"):
        errs = _errs(_l2(f"""
rubric:
  - id: ok_id
    question: "Q1?"
    required: {bad}
"""))
        assert any("required" in e for e in errs), (bad, errs)


def test_l2_missing_and_unknown_fields_rejected():
    missing = _errs(_l2("""
rubric:
  - id: ok_id
    question: "Q1?"
"""))
    assert any("required" in e for e in missing), missing

    unknown = _errs(_l2("""
rubric:
  - id: ok_id
    question: "Q1?"
    required: true
    weight: 2
"""))
    assert any("unknown" in e for e in unknown), unknown


def test_l2_rubric_declared_in_both_locations_rejected():
    # Both locations are individually legal and both are in use (5 cases top-level,
    # 3 under expected). Declaring both is not: scorer.py takes expected.rubric and
    # silently drops the other list.
    errs = _errs("""
name: dual_l2
description: fine
layer: 2
skill: causal-dag
user_message: hello
expected:
  must_flag: []
  rubric:
    - id: under_expected
      question: "Q1?"
      required: true
rubric:
  - id: top_level
    question: "Q2?"
    required: true
""", name="dual_l2.yaml")
    assert any("both" in e for e in errs), errs


def test_object_rubric_requirement_is_layer2_only():
    """L1/L4/L5 rubrics are different shapes and must keep validating.

    L1 and L5 use flat string lists, L4 a dict of dimension -> string list. A
    generic "rubric entries must be objects" check would break 60+ cases.
    """
    l1 = """
name: good_l1
description: fine
layer: 1
skill: causal-did
user_message: hello
expected:
  rubric:
    - "Is DiD the right method?"
"""
    with tempfile.TemporaryDirectory() as t:
        assert validate_case(_write(t, "layer1", "good_l1.yaml", l1)) == []
        assert validate_case(_write(t, "layer4", "good_l4.yaml", L4_GOOD)) == []
        assert validate_case(_write(t, "layer5", "good_l5.yaml", L5_GOOD)) == []


#: The approved L2 gate policy: every criterion each case declares, by exact id.
#: Counts alone would let a rename through, and a required-only list would let an
#: extra informational criterion in — which cannot weaken the gate directly but does
#: add a question to the judge prompt, moving the model's answers to the ones that do.
#: This is the committed copy of the list; `tasks/todo.md` is gitignored.
APPROVED_L2_CRITERIA = {
    "dag_clean_confounder": ["backdoor_parental_path", "identifiable_design",
                             "minimal_parental_adjustment_set"],
    "dag_frontdoor": ["complete_mediation_no_affinity_to_visits",
                      "frontdoor_identification", "no_observed_backdoor_set"],
    "report_full_artifacts": ["all_nine_sections", "artifact_specific_details",
                              "hybrid_mode_tone", "no_fabricated_estimates"],
    "report_no_artifacts": ["interview_required_details", "no_fabricated_estimates"],
    "report_partial_artifacts": ["identify_missing_plan_and_audit",
                                 "produce_caveated_partial_report",
                                 "recommend_planner_and_auditor"],
    "roi_full_artifacts": ["executable_r_calculation", "interval_roi",
                           "normalization_gate", "per_period_not_cumulative",
                           "projection_waterfall", "same_pipeline_breakeven",
                           "six_pipeline_assumptions", "verdict_matches_numbers"],
    "roi_late_scaling": ["apply_complier_share", "exposure_not_compliance",
                         "normalize_time_and_margin",
                         "reject_full_population_scaling"],
    "roi_no_artifacts": ["offer_valid_input_routes",
                         "percentage_points_not_relative_lift",
                         "refuse_invented_inputs",
                         "request_conversion_value_and_baseline",
                         "request_costs_and_horizon", "request_projection_assumptions",
                         "withhold_verdict"],
}


def test_shipped_l2_cases_declare_the_34_required_criteria():
    """The release gate is only as real as the cases behind it.

    Asserts the exact id list per case and that every entry gates, so a rename, a
    demotion to informational, a deletion or a quiet addition all fail loudly rather
    than reshaping the gate in silence.
    """
    root = Path(__file__).resolve().parent / "cases" / "layer2"
    total = 0
    for name, ids in APPROVED_L2_CRITERIA.items():
        case = yaml.safe_load((root / f"{name}.yaml").read_text())
        rubric = (case.get("expected") or {}).get("rubric") or case.get("rubric") or []
        assert all(isinstance(r, dict) for r in rubric), name
        assert sorted(r.get("id") for r in rubric) == sorted(ids), name
        demoted = [r.get("id") for r in rubric if r.get("required") is not True]
        assert not demoted, (name, "not required", demoted)
        total += len(rubric)
    assert total == 34, total

    # No ninth case grew a rubric without being added to the approved list above.
    declared = {p.stem for p in root.glob("*.yaml")
                if ((yaml.safe_load(p.read_text()) or {}).get("expected") or {}).get("rubric")
                or (yaml.safe_load(p.read_text()) or {}).get("rubric")}
    assert declared == set(APPROVED_L2_CRITERIA), declared ^ set(APPROVED_L2_CRITERIA)


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
