"""Offline tests for the gold key. No model calls, no network, no real sweep dirs."""
import glob
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goldkey  # noqa: E402
import runner  # noqa: E402
import sweep  # noqa: E402

_CASE = {"layer": 4, "name": "t", "rubric": {
    "pedagogy": [{"id": "explains_why", "question": "Does it explain why?",
                  "required": True},
                 {"id": "is_tailored", "question": "Is it tailored?",
                  "required": True}],
    "safety": [{"id": "warns", "question": "Does it warn?", "required": True}]}}


def _slot_file(d: Path, case: str, slot: int, response: str, answers: dict) -> Path:
    """One sweep slot file, shaped exactly like runner.py's --json-out writer."""
    p = d / f"case-{case}-slot{slot}.json"
    p.write_text(json.dumps({
        "runs": 1, "backend": "cli",
        "cases": [{"name": case, "layer": 4, "aggregate": {}, "verdict": "FAIL",
                   "invalid_reasons": [],
                   "run_records": [{"run": 1, "response": response,
                                    "scores": {"question_answers": answers},
                                    "tokens": {}}]}],
    }))
    return p


def test_a_rubric_id_resolves_to_its_positional_slot():
    assert goldkey.question_position(_CASE, "is_tailored") == ("pedagogy", 1)
    assert goldkey.question_position(_CASE, "warns") == ("safety", 0)


def test_an_unknown_id_is_refused_not_guessed():
    try:
        goldkey.question_position(_CASE, "no_such_question")
    except KeyError as e:
        assert "no_such_question" in str(e)
    else:
        raise AssertionError("expected KeyError")


def test_judge_answers_are_read_per_slot_by_position():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for slot, tailored in enumerate([True, True, False, True, False]):
            _slot_file(d, "t", slot, f"resp {slot}",
                       {"pedagogy": [True, tailored], "safety": [True]})
        got = goldkey.judge_answers(d, "t", _CASE, "is_tailored")
        assert got == {0: True, 1: True, 2: False, 3: True, 4: False}, got


def test_a_slot_whose_answer_array_is_short_is_absent_not_false():
    """A missing answer must never read as a recorded no — Package F's rule."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for slot in range(5):
            answers = {"pedagogy": [True], "safety": [True]} if slot == 2 else \
                      {"pedagogy": [True, True], "safety": [True]}
            _slot_file(d, "t", slot, f"resp {slot}", answers)
        got = goldkey.judge_answers(d, "t", _CASE, "is_tailored")
        assert 2 not in got, got
        assert len(got) == 4, got


def test_distance_to_flip_counts_answers_not_percentages():
    three_of_five = {0: True, 1: True, 2: True, 3: False, 4: False}
    assert goldkey.distance_to_flip(three_of_five, 0.8, 5) == 1
    five_of_five = {i: True for i in range(5)}
    assert goldkey.distance_to_flip(five_of_five, 0.8, 5) == 2
    zero_of_five = {i: False for i in range(5)}
    assert goldkey.distance_to_flip(zero_of_five, 0.8, 5) == 4


def _sweep_with_ledger(d: Path, cases: dict) -> Path:
    """A synthetic sweep dir: slot files plus the ledger failing_criteria reads.

    `cases` maps case name -> (case dict, list of 5 answer dicts).
    """
    entries = {}
    for name, (case, per_slot) in cases.items():
        case_path = d / "cases" / f"{name}.yaml"
        case_path.parent.mkdir(parents=True, exist_ok=True)
        case_path.write_text(json.dumps(case))  # load_case is patched in tests
        slots = []
        for slot, answers in enumerate(per_slot):
            _slot_file(d, name, slot, f"response body for {name} slot {slot}", answers)
            slots.append({"status": "done", "result": {
                "run": 1, "response": f"response body for {name} slot {slot}",
                "scores": {"question_answers": answers,
                           "dimensions_present": sorted(answers)}}})
        entries[name] = {"path": str(case_path), "layer": 4, "slots": slots}
    (d / "ledger.json").write_text(json.dumps({"cases": entries}))
    return d


def _with_loaded_cases(cases: dict, fn):
    """Serve case dicts by path without touching the real repo tree."""
    real = runner.load_case

    def fake(path):
        return cases[Path(path).stem][0]

    runner.load_case = fake
    try:
        return fn()
    finally:
        runner.load_case = real


def test_a_unit_is_one_response_and_carries_no_disputed_marker():
    failing = [{"pedagogy": [True, t], "safety": [True]}
               for t in (True, True, False, True, False)]
    cases = {"alpha": (dict(_CASE, name="alpha"), failing)}
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        units, manifest = _with_loaded_cases(
            cases, lambda: goldkey.worksheet_units(d, decoy_cases=0))
        assert len(units) == 5, len(units)
        for unit in units:
            assert set(unit) == goldkey._UNIT_FIELDS
            for q in unit["questions"]:
                assert set(q) == {"qid", "text"}, q
        assert manifest[units[0]["unit_id"]]["disputed"] == ["is_tailored"]


def test_units_are_ordered_by_leverage_lowest_distance_first():
    near = [{"pedagogy": [True, t], "safety": [True]}
            for t in (True, True, True, False, False)]          # 3/5 -> distance 1
    far = [{"pedagogy": [True, True], "safety": [s]}
           for s in (False, False, False, False, False)]        # 0/5 -> distance 4
    cases = {"alpha": (dict(_CASE, name="alpha"), near),
             "bravo": (dict(_CASE, name="bravo"), far)}
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        units, _ = _with_loaded_cases(
            cases, lambda: goldkey.worksheet_units(d, decoy_cases=0))
        assert [u["case"] for u in units[:5]] == ["alpha"] * 5
        assert [u["case"] for u in units[5:]] == ["bravo"] * 5


def test_the_shuffle_is_seeded_so_two_extractions_agree():
    failing = [{"pedagogy": [True, t], "safety": [True]}
               for t in (True, True, False, True, False)]
    cases = {"alpha": (dict(_CASE, name="alpha"), failing)}
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        first, _ = _with_loaded_cases(
            cases, lambda: goldkey.worksheet_units(d, decoy_cases=0))
        second, _ = _with_loaded_cases(
            cases, lambda: goldkey.worksheet_units(d, decoy_cases=0))
        assert [q["qid"] for q in first[0]["questions"]] == \
               [q["qid"] for q in second[0]["questions"]]


def test_the_rendered_page_chrome_shows_no_case_name_slot_or_judge_answer():
    """Blinding is a property of the page's chrome, not of the response.

    The fixture response deliberately contains both the case name and the word
    "slot", because a real response can always mention its own domain and that
    leak is unfixable — you cannot scrub the text the labeller is there to read.
    What must never appear is the case name, the slot index, or anything the
    judge recorded, in the parts of the page this module writes.
    """
    failing = [{"pedagogy": [True, t], "safety": [True]}
               for t in (True, True, False, True, False)]
    cases = {"alpha": (dict(_CASE, name="alpha"), failing)}
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        units, _ = _with_loaded_cases(
            cases, lambda: goldkey.worksheet_units(d, decoy_cases=0))
        unit = units[0]
        page = goldkey.render_worksheet(unit)
        assert "alpha" in unit["response"], "fixture must be adversarial"

        blocks = page.split("````")
        chrome = blocks[0] + "````".join(blocks[2:])
        assert "alpha" not in chrome, chrome
        assert "slot" not in chrome.lower(), chrome
        assert "true" not in chrome.lower() and "false" not in chrome.lower(), chrome

        assert unit["response"] in page
        assert "Does it explain why?" in page
        assert "verbatim" in chrome.lower()


_RESPONSE = "First we check the first stage. The F statistic is 8.4, which is weak."


def _entry(**over):
    base = {"unit_id": "abc123", "case": "alpha", "slot": 0, "qid": "explains_why",
            "response_sha256": goldkey.sha256_text(_RESPONSE),
            "label": True, "quote": "The F statistic is 8.4",
            "note": "", "suspect_case_defect": False,
            "labeler": "robson", "pass_name": "pass1"}
    base.update(over)
    return base


def test_a_yes_without_a_quote_is_refused():
    try:
        goldkey.validate_entry(_entry(quote=""), _RESPONSE)
    except ValueError as e:
        assert "quote" in str(e).lower()
    else:
        raise AssertionError("expected ValueError")


def test_a_quote_that_is_not_in_the_response_is_refused():
    try:
        goldkey.validate_entry(_entry(quote="the F statistic is 42"), _RESPONSE)
    except ValueError as e:
        assert "substring" in str(e).lower()
    else:
        raise AssertionError("expected ValueError")


def test_a_no_needs_no_quote():
    goldkey.validate_entry(_entry(label=False, quote=""), _RESPONSE)


def test_a_response_that_is_not_the_one_labelled_is_refused():
    try:
        goldkey.validate_entry(_entry(), "a completely different response")
    except ValueError as e:
        assert "response_sha256" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_a_label_that_is_not_a_bool_is_refused():
    for bad in ("yes", 1, None):
        try:
            goldkey.validate_entry(_entry(label=bad), _RESPONSE)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted {bad!r}")


def test_an_unknown_field_is_refused_not_ignored():
    try:
        goldkey.validate_entry(_entry(confidence=0.9), _RESPONSE)
    except ValueError as e:
        assert "confidence" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_a_suspected_case_defect_does_not_change_the_label():
    """The note routes a criterion to Phase 4; it never touches the fact."""
    e = _entry(label=False, quote="",
               note="the skill is right to withhold hints until asked",
               suspect_case_defect=True)
    goldkey.validate_entry(e, _RESPONSE)
    assert e["label"] is False


def test_entries_chain_so_an_edited_earlier_line_is_detectable():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pass1.jsonl"
        goldkey.append_entry(p, _entry(qid="explains_why"), _RESPONSE)
        goldkey.append_entry(p, _entry(qid="is_tailored", label=False, quote=""),
                             _RESPONSE)
        assert goldkey.verify_chain(p) == 2

        lines = p.read_text().splitlines()
        first = json.loads(lines[0])
        first["label"] = False
        lines[0] = json.dumps(first, sort_keys=True)
        p.write_text("\n".join(lines) + "\n")

        try:
            goldkey.verify_chain(p)
        except ValueError as e:
            assert "line 1" in str(e)
        else:
            raise AssertionError("an edited line passed verification")


def test_an_appended_line_cannot_be_reordered():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pass1.jsonl"
        goldkey.append_entry(p, _entry(qid="explains_why"), _RESPONSE)
        goldkey.append_entry(p, _entry(qid="is_tailored", label=False, quote=""),
                             _RESPONSE)
        lines = p.read_text().splitlines()
        p.write_text("\n".join([lines[1], lines[0]]) + "\n")
        try:
            goldkey.verify_chain(p)
        except ValueError as e:
            assert "chain" in str(e).lower()
        else:
            raise AssertionError("a reordered chain passed verification")


def test_an_invalid_entry_never_reaches_the_file():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pass1.jsonl"
        try:
            goldkey.append_entry(p, _entry(quote="not in the text"), _RESPONSE)
        except ValueError:
            pass
        assert not p.exists() or p.read_text() == ""


def test_read_entries_round_trips_what_was_appended():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pass1.jsonl"
        goldkey.append_entry(p, _entry(qid="explains_why"), _RESPONSE)
        got = goldkey.read_entries(p)
        assert len(got) == 1
        assert got[0]["qid"] == "explains_why"
        assert got[0]["label"] is True


def test_only_yes_cells_go_to_the_inversion_pass():
    pass1 = [_entry(qid="explains_why", label=True),
             _entry(qid="is_tailored", label=False, quote=""),
             _entry(qid="warns", label=True)]
    targets = goldkey.inversion_targets(pass1)
    assert sorted(t["qid"] for t in targets) == ["explains_why", "warns"]


def test_a_yes_with_a_concrete_failure_reason_is_contested_not_gold():
    pass1 = [_entry(qid="explains_why", label=True)]
    pass2 = [{"unit_id": "abc123", "case": "alpha", "slot": 0, "qid": "explains_why",
              "failure_reason": "it names the F statistic but never says what weak means"}]
    gold, contested = goldkey.join_passes(pass1, pass2)
    assert gold == []
    assert len(contested) == 1
    assert "weak means" in contested[0]["failure_reason"]


def test_a_yes_that_survives_the_inversion_pass_becomes_gold():
    pass1 = [_entry(qid="explains_why", label=True)]
    pass2 = [{"unit_id": "abc123", "case": "alpha", "slot": 0, "qid": "explains_why",
              "failure_reason": "none"}]
    gold, contested = goldkey.join_passes(pass1, pass2)
    assert len(gold) == 1 and contested == []


def test_a_no_needs_no_second_pass_and_goes_straight_to_gold():
    pass1 = [_entry(qid="is_tailored", label=False, quote="")]
    gold, contested = goldkey.join_passes(pass1, [])
    assert len(gold) == 1 and contested == []


def test_a_yes_with_no_second_pass_entry_is_refused_not_promoted():
    """A half-labelled cell must never enter the key by omission."""
    pass1 = [_entry(qid="explains_why", label=True)]
    try:
        goldkey.join_passes(pass1, [])
    except ValueError as e:
        assert "explains_why" in str(e)
    else:
        raise AssertionError("a yes entered the key without its inversion pass")


def _gold_for(case, qid, labels):
    return [_entry(case=case, qid=qid, slot=s, label=v,
                   quote="The F statistic is 8.4" if v else "")
            for s, v in enumerate(labels)]


def test_a_criterion_labelled_in_every_slot_is_scored_against_the_judge():
    judge = [{"pedagogy": [True, t], "safety": [True]}
             for t in (True, True, True, False, False)]      # judge 3/5 -> FAIL
    cases = {"alpha": (dict(_CASE, name="alpha"), judge)}
    gold = _gold_for("alpha", "is_tailored", [True, True, True, True, False])
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        summary = _with_loaded_cases(
            cases, lambda: goldkey.score_judge_against_gold(gold, d))
        row = summary["criteria"][0]
        assert row["judge_pass"] == 3 and row["gold_pass"] == 4
        assert row["false_negative"] == 1 and row["false_positive"] == 0
        assert row["gate_judge"] is False and row["gate_gold"] is True
        assert row["gate_disagrees"] is True
        assert summary["totals"]["gate_disagreements"] == 1


def test_a_partly_labelled_criterion_is_incomplete_not_scored_over_what_exists():
    judge = [{"pedagogy": [True, t], "safety": [True]}
             for t in (True, True, True, False, False)]
    cases = {"alpha": (dict(_CASE, name="alpha"), judge)}
    gold = _gold_for("alpha", "is_tailored", [True, True, True])  # 3 of 5 labelled
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        summary = _with_loaded_cases(
            cases, lambda: goldkey.score_judge_against_gold(gold, d))
        row = summary["criteria"][0]
        assert row["status"] == "incomplete"
        assert row["gate_gold"] is None
        assert summary["totals"]["incomplete"] == 1
        assert summary["totals"]["gate_disagreements"] == 0


def test_a_judge_yes_against_a_gold_no_is_counted_as_a_false_positive():
    judge = [{"pedagogy": [True, True], "safety": [True]} for _ in range(5)]
    cases = {"alpha": (dict(_CASE, name="alpha"), judge)}
    gold = _gold_for("alpha", "is_tailored", [False, False, False, False, False])
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        summary = _with_loaded_cases(
            cases, lambda: goldkey.score_judge_against_gold(gold, d))
        row = summary["criteria"][0]
        assert row["false_positive"] == 5 and row["false_negative"] == 0
        assert row["gate_judge"] is True and row["gate_gold"] is False


def test_suspected_case_defects_are_reported_apart_from_the_scores():
    judge = [{"pedagogy": [True, False], "safety": [True]} for _ in range(5)]
    cases = {"alpha": (dict(_CASE, name="alpha"), judge)}
    gold = _gold_for("alpha", "is_tailored", [False] * 5)
    gold[0]["suspect_case_defect"] = True
    gold[0]["note"] = "the skill is right to withhold this"
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        summary = _with_loaded_cases(
            cases, lambda: goldkey.score_judge_against_gold(gold, d))
        assert len(summary["suspected_case_defects"]) == 1
        assert summary["criteria"][0]["false_positive"] == 0
        assert summary["criteria"][0]["gate_gold"] is False


def test_the_report_never_prints_a_pass_fail_verdict():
    judge = [{"pedagogy": [True, True], "safety": [True]} for _ in range(5)]
    cases = {"alpha": (dict(_CASE, name="alpha"), judge)}
    gold = _gold_for("alpha", "is_tailored", [False] * 5)
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        summary = _with_loaded_cases(
            cases, lambda: goldkey.score_judge_against_gold(gold, d))
        md = goldkey.render_gold_md(summary)
        assert "gold label" in md.lower()
        assert "false positive" in md.lower()
        assert "PASS" not in md and "FAIL" not in md


# Recorded at HEAD ff39f79 in Task 0. A change here means the decision rule moved
# and needs its own review — it is never a reason to update this literal.
_GATE_DIGEST = "a001661d4fde630ad4f6bea537746fcf77d50ab149391c1270b25d5a41bd68e0"


def test_no_gate_path_module_imports_the_gold_key():
    """The key must be unreachable from the gate, not merely unused by it."""
    here = Path(__file__).resolve().parent
    for name in ("runner.py", "scorer.py", "sweep.py", "validate_cases.py"):
        assert "goldkey" not in (here / name).read_text(), \
            f"{name} references goldkey — the gate must not be able to read it"


def test_the_gate_digest_does_not_move_when_the_gold_key_is_imported():
    config = yaml.safe_load(Path("evals/config.release.yaml").read_text())
    cases = sorted(glob.glob("evals/cases/*/*.yaml"))
    assert sweep._gate_digest(config, cases) == _GATE_DIGEST


def test_verify_reports_a_broken_chain_through_the_cli():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "pass1.jsonl"
        goldkey.append_entry(p, _entry(qid="explains_why"), _RESPONSE)
        assert goldkey.main(["verify", "--key", str(p)]) == 0
        p.write_text(p.read_text().replace('"label": true', '"label": false'))
        assert goldkey.main(["verify", "--key", str(p)]) == 1


def test_the_cli_refuses_an_unknown_subcommand():
    try:
        goldkey.main(["measure-everything"])
    except SystemExit as e:
        assert e.code != 0
    else:
        raise AssertionError("expected SystemExit")


def test_the_scenario_is_the_schema_injected_message_the_model_actually_saw():
    """runner.inject_schema pastes a df.head() sample into user_message before any
    L4 run (runner.py:1180, unconditional and above the layer branch). Showing the
    bare user_message would show the labeller LESS than the model read."""
    failing = [{"pedagogy": [True, t], "safety": [True]}
               for t in (True, True, False, True, False)]
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        csv = d / "iv_weak.csv"
        csv.write_text("educ,earnings,distance\n12,40000,3.1\n16,62000,0.4\n")
        case = dict(_CASE, name="alpha", skill="causal-iv",
                    description="IV with a borderline instrument",
                    user_message="Effect of education on earnings.",
                    dataset=str(csv))
        cases = {"alpha": (case, failing)}
        d = _sweep_with_ledger(d, cases)
        units, _ = _with_loaded_cases(
            cases, lambda: goldkey.worksheet_units(d, decoy_cases=0))
        unit = units[0]
        assert set(unit) == goldkey._UNIT_FIELDS
        assert "dataset" not in unit
        assert unit["scenario"].startswith("Effect of education on earnings.")
        assert "educ" in unit["scenario"] and "distance" in unit["scenario"]


def test_the_dataset_path_never_reaches_a_unit():
    """A real dataset value is a path like evals/data/iv_weak.csv — the filename
    states the method and the condition, which is what hiding `description`
    protects. The schema it points at is already in the injected message."""
    failing = [{"pedagogy": [True, t], "safety": [True]}
               for t in (True, True, False, True, False)]
    case = dict(_CASE, name="alpha", user_message="A question.",
                dataset="evals/data/iv_weak.csv")   # a real path in this repo
    cases = {"alpha": (case, failing)}
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        units, _ = _with_loaded_cases(
            cases, lambda: goldkey.worksheet_units(d, decoy_cases=0))
        blob = json.dumps(units[0])
        assert "iv_weak" not in blob
        assert "evals/data" not in blob
        # The schema the path points at IS carried — that is what the model saw —
        # while the filename that names the method and condition is not.
        assert units[0]["scenario"].startswith("A question.")
        assert "Column types" in units[0]["scenario"]


def test_a_dataset_path_that_does_not_exist_leaves_the_message_alone():
    failing = [{"pedagogy": [True, t], "safety": [True]}
               for t in (True, True, False, True, False)]
    case = dict(_CASE, name="alpha", user_message="A question.",
                dataset="evals/data/no_such_file_12345.csv")
    cases = {"alpha": (case, failing)}
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        units, _ = _with_loaded_cases(
            cases, lambda: goldkey.worksheet_units(d, decoy_cases=0))
        assert units[0]["scenario"] == "A question."


def _base(**over):
    e = {"unit_id": "u1", "case": "alpha", "slot": 0, "qid": "explains_why",
         "response_sha256": goldkey.sha256_text(_RESPONSE), "label": True,
         "quote": "The F statistic is 8.4", "note": "", "suspect_case_defect": False,
         "labeler": "robson", "pass_name": "pass1", "supersedes": None}
    e.update(over)
    return e


def test_an_amendment_updates_evidence_and_never_the_label():
    base = _base(quote="The F statistic is 8.4", note="")
    amend = _base(quote="which is weak", note="clearer span", supersedes="d0")
    out = goldkey.resolve_entries([base, amend])
    assert len(out) == 1
    assert out[0]["label"] is True
    assert out[0]["quote"] == "which is weak"
    assert out[0]["note"] == "clearer span"
    assert out[0]["amendments"] == 1


def test_the_latest_amendment_wins_over_an_earlier_one():
    entries = [_base(note="first"),
               _base(note="second", supersedes="d0"),
               _base(note="third", supersedes="d1")]
    assert goldkey.resolve_entries(entries)[0]["note"] == "third"
    assert goldkey.resolve_entries(entries)[0]["amendments"] == 2


def test_an_amendment_carrying_a_different_label_is_refused_on_read():
    """collect refuses this at write time; a hand-edited file must not slip past."""
    entries = [_base(label=True), _base(label=False, quote="", supersedes="d0")]
    try:
        goldkey.resolve_entries(entries)
    except ValueError as e:
        assert "label" in str(e).lower() and "explains_why" in str(e)
    else:
        raise AssertionError("a label change survived resolution")


def test_unamended_entries_pass_through_unchanged():
    a = _base(qid="explains_why")
    b = _base(qid="warns", label=False, quote="")
    out = goldkey.resolve_entries([a, b])
    assert sorted(e["qid"] for e in out) == ["explains_why", "warns"]
    assert all(e["amendments"] == 0 for e in out)


def test_scoring_reads_the_amended_defect_flag_not_the_original():
    judge = [{"pedagogy": [True, False], "safety": [True]} for _ in range(5)]
    cases = {"alpha": (dict(_CASE, name="alpha"), judge)}
    gold = _gold_for("alpha", "is_tailored", [False] * 5)
    # Both the base entry and its amendment carry the flag, so without resolution
    # the same cell is counted twice. That is what makes this test discriminating:
    # it fails on the unresolved path rather than passing by luck.
    gold[0] = {**gold[0], "suspect_case_defect": True, "note": "first"}
    gold.append({**gold[0], "suspect_case_defect": True,
                 "note": "unfair", "supersedes": "d0"})
    with tempfile.TemporaryDirectory() as d:
        d = _sweep_with_ledger(Path(d), cases)
        summary = _with_loaded_cases(
            cases, lambda: goldkey.score_judge_against_gold(gold, d))
        assert len(summary["suspected_case_defects"]) == 1
        assert summary["criteria"][0]["labelled"] == 5


def _units_for_build():
    r = "The first stage F is 8.4, which is weak."
    return [{"unit_id": "u1", "case": "alpha", "slot": 3, "response": r,
             "response_sha256": goldkey.sha256_text(r),
             "questions": [{"qid": "explains_why", "text": "Does it explain why?"}],
             "scenario": "Effect of education on earnings."}]


def _one_unit_env():
    return _units_for_build(), {"u1": {"case": "alpha", "slot": 3,
                                       "disputed": ["explains_why"], "decoy": []}}


def _answer(**over):
    units = _units_for_build()
    a = {"unit_id": "u1", "qid": "explains_why", "pass": 1, "label": True,
         "quote": "The first stage F is 8.4", "note": "",
         "suspect_case_defect": False,
         "response_sha256": units[0]["response_sha256"],
         "labeled_at": "2026-08-05T11:00:00Z"}
    a.update(over)
    return a


def _export(answers, build=None):
    units, _ = _one_unit_env()
    return {"build": build or goldkey.build_id(units),
            "exported": "2026-08-05T12:00:00Z", "answers": answers}


def _collect(export, units, manifest, d, **kw):
    p1, p2 = Path(d) / "pass1.jsonl", Path(d) / "pass2.jsonl"
    return goldkey.collect_export(export, units, manifest, p1, p2, "robson", **kw), p1, p2


def test_an_export_from_a_different_build_is_refused_with_answers_in_it():
    """The draft's version passed an EMPTY export, so it proved only that nothing
    was written when there was nothing to write."""
    units, manifest = _one_unit_env()
    export = _export({"u1|explains_why|p1": _answer()}, build="someone-elses-build")
    with tempfile.TemporaryDirectory() as d:
        out, p1, _ = _collect(export, units, manifest, d)
        assert out["written"] == 0
        assert any("build" in r for r in out["rejected"])
        assert not p1.exists()


def test_an_answer_against_a_changed_response_is_refused():
    units, manifest = _one_unit_env()
    export = _export({"u1|explains_why|p1": _answer(response_sha256="deadbeef")})
    with tempfile.TemporaryDirectory() as d:
        out, _p1, _ = _collect(export, units, manifest, d)
        assert out["written"] == 0
        assert any("response_sha256" in r for r in out["rejected"])


def test_a_question_the_unit_never_asked_is_refused():
    units, manifest = _one_unit_env()
    export = _export({"u1|invented|p1": _answer(qid="invented")})
    with tempfile.TemporaryDirectory() as d:
        out, _, _ = _collect(export, units, manifest, d)
        assert out["written"] == 0
        assert any("invented" in r for r in out["rejected"])


def test_a_label_that_is_not_a_bool_is_refused_never_coerced():
    """bool('false') is True. The judge parser has the same latent bug on record."""
    units, manifest = _one_unit_env()
    for bad in ("false", 0, 1, None):
        export = _export({"u1|explains_why|p1": _answer(label=bad)})
        with tempfile.TemporaryDirectory() as d:
            out, _, _ = _collect(export, units, manifest, d)
            assert out["written"] == 0, bad
            assert any("label" in r for r in out["rejected"]), bad


def test_an_answer_whose_pass_does_not_match_the_collection_is_refused():
    units, manifest = _one_unit_env()
    export = _export({"u1|explains_why|p1": _answer(**{"pass": 3})})
    with tempfile.TemporaryDirectory() as d:
        out, _, _ = _collect(export, units, manifest, d)
        assert out["written"] == 0
        assert any("pass" in r for r in out["rejected"])


def test_one_export_cannot_smuggle_two_answers_for_the_same_cell():
    units, manifest = _one_unit_env()
    export = _export({
        "first-hand-edited-key": _answer(),
        "second-hand-edited-key": _answer(label=False, quote=""),
    })
    with tempfile.TemporaryDirectory() as d:
        out, p1, _ = _collect(export, units, manifest, d)
        assert out["written"] == 0
        assert out["rejected"] or out["conflicts"]
        assert not p1.exists()


def test_an_io_failure_cannot_leave_half_an_export_on_disk():
    units, manifest = _one_unit_env()
    units[0]["questions"].append({"qid": "warns", "text": "Does it warn?"})
    manifest["u1"]["decoy"] = ["warns"]
    export = _export({
        "u1|explains_why|p1": _answer(),
        "u1|warns|p1": _answer(qid="warns", label=False, quote="")},
        build=goldkey.build_id(units))
    with tempfile.TemporaryDirectory() as d:
        with patch.object(Path, "replace", side_effect=OSError(
                "simulated replace failure")) as replace:
            try:
                _collect(export, units, manifest, d)
            except OSError:
                pass
        assert replace.call_count == 1
        assert not (Path(d) / "pass1.jsonl").exists()


def test_nothing_is_written_when_any_answer_in_the_export_is_invalid():
    """A half-ingested export is worse than a refused one."""
    units, manifest = _one_unit_env()
    export = _export({"u1|explains_why|p1": _answer(),
                      "u1|invented|p1": _answer(qid="invented")})
    with tempfile.TemporaryDirectory() as d:
        out, p1, _ = _collect(export, units, manifest, d)
        assert out["written"] == 0
        assert not p1.exists()


def test_collecting_the_same_export_twice_writes_nothing_the_second_time():
    units, manifest = _one_unit_env()
    export = _export({"u1|explains_why|p1": _answer()})
    with tempfile.TemporaryDirectory() as d:
        _collect(export, units, manifest, d)
        out, p1, _ = _collect(export, units, manifest, d)
        assert out["written"] == 0 and out["skipped"] == 1 and out["amended"] == 0
        assert goldkey.verify_chain(p1) == 1


def test_a_changed_label_is_a_conflict_and_the_file_keeps_the_first_answer():
    units, manifest = _one_unit_env()
    first = _export({"u1|explains_why|p1": _answer()})
    second = _export({"u1|explains_why|p1": _answer(
        label=False, quote="", labeled_at="2026-08-06T11:00:00Z")})
    with tempfile.TemporaryDirectory() as d:
        _collect(first, units, manifest, d)
        out, p1, _ = _collect(second, units, manifest, d)
        assert out["written"] == 0 and len(out["conflicts"]) == 1
        assert goldkey.resolve_entries(goldkey.read_entries(p1))[0]["label"] is True


def test_a_corrected_quote_is_appended_as_an_amendment_not_an_overwrite():
    units, manifest = _one_unit_env()
    first = _export({"u1|explains_why|p1": _answer()})
    second = _export({"u1|explains_why|p1": _answer(
        quote="which is weak", note="tighter span",
        labeled_at="2026-08-06T11:00:00Z")})
    with tempfile.TemporaryDirectory() as d:
        _collect(first, units, manifest, d)
        out, p1, _ = _collect(second, units, manifest, d)
        assert out["amended"] == 1 and out["written"] == 0
        raw = goldkey.read_entries(p1)
        assert len(raw) == 2
        assert raw[1]["supersedes"] == raw[0]["digest"]
        resolved = goldkey.resolve_entries(raw)
        assert len(resolved) == 1
        assert resolved[0]["quote"] == "which is weak"
        assert resolved[0]["label"] is True


def test_an_older_export_cannot_revert_newer_evidence():
    units, manifest = _one_unit_env()
    older = _export({"u1|explains_why|p1": _answer(note="old note")})
    newer = _export({"u1|explains_why|p1": _answer(
        note="better note", labeled_at="2026-08-06T11:00:00Z")})
    with tempfile.TemporaryDirectory() as d:
        _collect(older, units, manifest, d)
        amended, p1, _ = _collect(newer, units, manifest, d)
        assert amended["amended"] == 1

        stale, _, _ = _collect(older, units, manifest, d)
        assert stale["amended"] == 0
        assert stale["rejected"]
        resolved = goldkey.resolve_entries(goldkey.read_entries(p1))
        assert resolved[0]["note"] == "better note"


def test_an_amended_quote_is_revalidated_against_the_response():
    units, manifest = _one_unit_env()
    first = _export({"u1|explains_why|p1": _answer()})
    second = _export({"u1|explains_why|p1": _answer(
        quote="a sentence that is not there", labeled_at="2026-08-06T11:00:00Z")})
    with tempfile.TemporaryDirectory() as d:
        _collect(first, units, manifest, d)
        out, p1, _ = _collect(second, units, manifest, d)
        assert out["amended"] == 0
        assert any("substring" in r for r in out["rejected"])
        assert goldkey.verify_chain(p1) == 1


def test_entries_are_chained_in_the_order_they_were_labelled():
    units, manifest = _one_unit_env()
    units[0]["questions"].append({"qid": "warns", "text": "Does it warn?"})
    manifest["u1"]["decoy"] = ["warns"]
    # The build id must come from THESE units: adding a question changes the build,
    # and an export stamped with the old id is correctly refused.
    export = _export({
        "u1|warns|p1": _answer(qid="warns", label=False, quote="",
                               labeled_at="2026-08-05T10:00:00Z"),
        "u1|explains_why|p1": _answer(label=False, quote="",
                                      labeled_at="2026-08-05T09:00:00Z")},
        build=goldkey.build_id(units))
    with tempfile.TemporaryDirectory() as d:
        out, p1, _ = _collect(export, units, manifest, d)
        assert out["written"] == 2, out
        assert [e["qid"] for e in goldkey.read_entries(p1)] == \
               ["explains_why", "warns"]


def test_clicking_a_question_card_does_not_rebuild_its_textareas():
    template = goldkey.TEMPLATE_PATH.read_text()
    assert "div.onclick = () => { focus = n; render(); };" not in template
    assert 'card.classList.toggle("focus"' in template


def test_the_built_page_has_no_network_capable_construct():
    """Not a URL grep: one real stored response contains https://cloud.r-project.org,
    and rendering it through textContent issues no request. What matters is whether
    the TEMPLATE can reach the network."""
    html = goldkey.build_labeller(_units_for_build())
    template = goldkey.TEMPLATE_PATH.read_text()
    for construct in ("<script src", "<link ", "<img ", "<iframe", "@import",
                      "fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon",
                      "EventSource", "importScripts"):
        assert construct not in template, construct
    assert "__GOLDKEY_DATA__" not in html


def test_a_response_containing_a_closing_script_tag_cannot_break_out():
    unit = _units_for_build()[0]
    unit["response"] = "Use </script><script>alert(1)</script> carefully."
    unit["response_sha256"] = goldkey.sha256_text(unit["response"])
    html = goldkey.build_labeller([unit])
    assert "</script><script>alert" not in html
    assert "\\u003c/script" in html


def test_template_markers_inside_response_text_are_not_rewritten():
    unit = _units_for_build()[0]
    unit["response"] = "Literal __GOLDKEY_BUILD_ID__ evidence."
    unit["response_sha256"] = goldkey.sha256_text(unit["response"])
    html = goldkey.build_labeller([unit])
    blob = html.split("const UNITS = ")[1].split("\n")[0].rstrip(";")
    embedded = json.loads(blob.replace("\\u003c", "<"))[0]
    assert embedded["response"] == unit["response"]
    assert embedded["response_sha256"] == goldkey.sha256_text(embedded["response"])


def test_the_embedded_unit_keeps_only_what_the_page_needs():
    html = goldkey.build_labeller(_units_for_build())
    blob = html.split("const UNITS = ")[1].split("\n")[0].rstrip(";")
    embedded = json.loads(blob.replace("\\u003c", "<"))
    assert set(embedded[0]) == {"unit_id", "response", "response_sha256",
                                "questions", "scenario"}
    assert "alpha" not in html


def test_a_unit_shape_the_builder_does_not_recognise_is_refused():
    unit = _units_for_build()[0]
    unit["judge_said"] = True
    try:
        goldkey.build_labeller([unit])
    except ValueError as e:
        assert "judge_said" in str(e)
    else:
        raise AssertionError("an unrecognised unit field reached the page")


def test_the_two_passes_get_different_storage_keys():
    """Pass 2 must not inherit pass 1's answers out of the same browser slot."""
    units = _units_for_build()
    one = goldkey.build_labeller(units, pass_no=1)
    two = goldkey.build_labeller(units, pass_no=2)
    key = lambda h: h.split('STORAGE_KEY = "')[1].split('"')[0]
    assert key(one) != key(two)
    assert key(one).endswith(":p1") and key(two).endswith(":p2")


def test_pass_two_units_come_only_from_chained_pass_one_yes_cells():
    units, manifest = _one_unit_env()
    units[0]["questions"].append({"qid": "warns", "text": "Does it warn?"})
    manifest["u1"]["decoy"] = ["warns"]
    export = _export({
        "u1|explains_why|p1": _answer(),                               # yes
        "u1|warns|p1": _answer(qid="warns", label=False, quote="")},   # no
        build=goldkey.build_id(units))
    with tempfile.TemporaryDirectory() as d:
        out, p1, _ = _collect(export, units, manifest, d)
        assert out["written"] == 2, out
        got = goldkey.pass2_units(units, p1)
        assert len(got) == 1
        assert [q["qid"] for q in got[0]["questions"]] == ["explains_why"]


def test_pass_two_refuses_to_build_before_pass_one_is_collected():
    units, _ = _one_unit_env()
    with tempfile.TemporaryDirectory() as d:
        try:
            goldkey.pass2_units(units, Path(d) / "pass1.jsonl")
        except ValueError as e:
            assert "pass 1" in str(e).lower()
        else:
            raise AssertionError("pass 2 built with no chained pass 1")


def test_pass_two_carries_no_pass_one_label_into_the_page():
    units, manifest = _one_unit_env()
    export = _export({"u1|explains_why|p1": _answer()})
    with tempfile.TemporaryDirectory() as d:
        out, p1, _ = _collect(export, units, manifest, d)
        assert out["written"] == 1
        html = goldkey.build_labeller(goldkey.pass2_units(units, p1), pass_no=2)
        # Assert on the embedded data, not the whole page: `"label"` appears in the
        # template as document.createElement("label"), a DOM tag name. A substring
        # grep over the page tests the wrong thing.
        blob = html.split("const UNITS = ")[1].split("\n")[0].rstrip(";")
        embedded = json.loads(blob.replace("\\u003c", "<"))
        assert all("label" not in u for u in embedded)
        assert all(set(u) == {"unit_id", "response", "response_sha256",
                              "questions", "scenario"} for u in embedded)
        assert "The first stage F is 8.4" in html


def test_the_cli_exposes_build_and_collect():
    for cmd in ("build", "collect"):
        try:
            goldkey.main([cmd, "--help"])
        except SystemExit as e:
            assert e.code == 0, cmd
        else:
            raise AssertionError(f"{cmd} --help did not exit")


def test_the_cli_rejects_a_pass_outside_one_and_two():
    try:
        goldkey.main(["build", "--pass", "3"])
    except SystemExit as e:
        assert e.code != 0
    else:
        raise AssertionError("expected SystemExit on an out-of-range pass")
