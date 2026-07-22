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


def test_real_case_tree_declares_no_grading_contract_fields_yet():
    # D1 lands the mechanism; D2 (a separate, checkpoint-gated step) migrates
    # cases onto it. Between those two, every real case must still be silent
    # on all three fields — this is the literal backward-compatibility claim.
    import yaml
    cases_dir = Path("evals/cases")
    offenders = []
    for path in sorted(cases_dir.rglob("*.yaml")):
        case = yaml.safe_load(path.read_text()) or {}
        if any(k in case for k in ("response_contract", "input_mode", "deferred_rubric")):
            offenders.append(str(path))
    assert not offenders, offenders


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
