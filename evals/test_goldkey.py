"""Offline tests for the gold key. No model calls, no network, no real sweep dirs."""
import glob
import json
import sys
import tempfile
from pathlib import Path

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
            assert set(unit) == {"unit_id", "case", "slot", "response",
                                 "response_sha256", "questions"}
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
