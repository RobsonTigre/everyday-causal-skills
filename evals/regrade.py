"""Is a failing L4 criterion's gate result reproducible under the present judge?

A criterion satisfied in 3 of 5 runs fails the per-question floor. That can mean a
skill producing the behaviour 60% of the time, or a judge that would answer
differently on the very same bytes. Nine of the twenty currently-failing criteria sit
exactly one cell below the gate, so a single flipped answer moves them across it.
Repairing a skill against a criterion whose failure does not reproduce is how the ROI
arc became five commits in four days, each fixing one criterion and regressing
another.

This re-grades stored responses K times and reports whether each criterion's 4-of-5
gate result comes out the same every round. Two labels, both strictly observational:

- `OBSERVED_GATE_SENSITIVE` — the gate result moved between rounds. No skill may be
  repaired for this criterion until validity work says otherwise.
- `NO_GATE_CHANGE_OBSERVED_K5` — it did not move. This rules out **nothing**: not
  judge variance below the detection limit of K rounds, not a stable judge error, not
  an invalid case. It removes no explanation; it only failed to find one.

What this cannot do is attribute a failure to a skill. Reliability is not validity —
a perfectly repeatable judge can be repeatably wrong, and this repo has a confirmed
judge false positive on record. Validity work is required before any skill repair
regardless of what this returns.

Nothing here is imported by `case_gate`, `aggregate` or `compile_verdict`, and the
gate digest must not move for any change in this file.

Run: python3 evals/regrade.py --help   (from repo root)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner  # noqa: E402
import scorer  # noqa: E402

_SLOT_RE = re.compile(r"^case-(?P<case>.+)-slot(?P<slot>\d+)\.json$")
L4_CASES_DIR = Path("evals/cases/layer4")
SLOTS_PER_CASE = 5


# --- identity -------------------------------------------------------------

def cell_key(case: str, slot: int, question_id: str) -> tuple:
    """One (response, criterion) observation site.

    Case-qualified because rubric ids are NOT globally unique:
    `provide_complete_runnable_code` is declared by both `did_pedagogy_clean` and
    `experiments_pedagogy_messy`, so 230 questions carry only 229 distinct ids.
    Keying by bare id would merge two different criteria into one row of evidence.
    """
    return (case, slot, question_id)


def criterion_key(case: str, question_id: str) -> tuple:
    """One criterion, across all its stored responses. Case-qualified, same reason."""
    return (case, question_id)


# --- corpus ---------------------------------------------------------------

def slot_path(sweep_dir: str | Path, case: str, slot: int) -> Path:
    return Path(sweep_dir) / f"case-{case}-slot{slot}.json"


def stored_response(sweep_dir: str | Path, case: str, slot: int) -> str:
    """The one recorded response in a slot file."""
    entry = json.loads(slot_path(sweep_dir, case, slot).read_text())["cases"][0]
    records = entry["run_records"]
    if len(records) != 1:
        raise ValueError(f"{case} slot {slot}: expected 1 run_record, found "
                         f"{len(records)}")
    return records[0]["response"]


def validate_corpus(sweep_dir: str | Path, cases: set, slots: int = SLOTS_PER_CASE) -> int:
    """Refuse anything short of the complete expected corpus. Returns the cell count.

    Fails closed on purpose. Grading whatever happens to be on disk turns a missing
    measurement into a smaller, quieter statistic — the denominator failure this
    whole arc exists to prevent. A partial corpus is UNMEASURED, never a result.
    """
    missing, empty = [], []
    for case in sorted(cases):
        for slot in range(slots):
            path = slot_path(sweep_dir, case, slot)
            if not path.exists():
                missing.append(f"{case} slot {slot}")
                continue
            try:
                text = stored_response(sweep_dir, case, slot)
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                missing.append(f"{case} slot {slot} ({e.__class__.__name__})")
                continue
            if not text or not text.strip():
                empty.append(f"{case} slot {slot}")
    problems = []
    if missing:
        problems.append("absent or unreadable: " + ", ".join(missing))
    if empty:
        problems.append("stored response is empty: " + ", ".join(empty))
    if problems:
        raise ValueError(
            f"corpus incomplete for {len(cases)} case(s) x {slots} slots — "
            + "; ".join(problems)
            + ". Refusing: a smaller corpus is a different experiment, not a "
              "quieter one")
    return len(cases) * slots


def l4_cases_sha256(cases_dir: str | Path = L4_CASES_DIR) -> str:
    """One hash over every L4 case file, sorted.

    The stored responses are only half the corpus. If a rubric question is reworded
    between the pin and the run, the re-grade grades a different instrument under the
    old protocol's name — the 2026-08-03 drift, repeated deliberately.
    """
    h = hashlib.sha256()
    for path in sorted(Path(cases_dir).glob("*.yaml")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


# --- the population under screen ------------------------------------------

def failing_criteria(sweep_dir: str | Path, thresholds: dict | None = None) -> dict:
    """Which criteria miss the per-question floor in a stored sweep, by case.

    Derived by re-aggregating the ledger through the production gate rather than
    typed by hand: a hand-typed list is a list that can be aimed.
    """
    ledger = json.loads((Path(sweep_dir) / "ledger.json").read_text())
    floor = runner._threshold(thresholds, 4, "question_rate")
    out: dict[str, set] = {}
    for entry in ledger["cases"].values():
        runs = [s["result"] for s in (entry.get("slots") or [])
                if s["status"] == "done"]
        case = runner.load_case(entry["path"])
        if case.get("layer") != 4:
            continue
        agg = runner.aggregate(runs, case)
        name = Path(entry["path"]).stem
        for qid, block in (agg.get("question_stats") or {}).items():
            if not block.get("required"):
                continue
            status, rate = runner.criterion_status(block, agg["runs_valid"])
            if status != "ok" or not runner._meets(rate, floor):
                out.setdefault(name, set()).add(qid)
    return out


# --- scoring --------------------------------------------------------------

def regrade_once(response: str, case: dict, config: dict) -> dict:
    """Grade one stored response once, keyed by rubric id.

    `config` is REQUIRED, not defaulted. Hashing a config in the protocol does not
    prove it reached the scorer, and `_judge_l4` falls back to its own defaults when
    handed None. Those defaults happen to match `config.release.yaml` byte for byte
    today, so a divergence would be completely invisible until one side moved.

    Calls `scorer._judge_l4` unmodified — a second prompt builder would drift from
    the one that produced the ledger, and the screen would describe an instrument
    nobody runs. The positional answer array is mapped back onto ids through
    `runner._l4_questions`, the single place that mapping lives.
    """
    scores = scorer._judge_l4(response, case, config)
    run = {"run": 1, "scores": scores, "tokens": {"input": 0, "output": 0}}
    stats = runner._l4_questions([run], case) or {}
    return {qid: bool(block["passed"]) for qid, block in stats.items()}


def round_gate_result(answers: dict, floor: float,
                      slots: int = SLOTS_PER_CASE) -> bool | None:
    """Reconstruct one criterion's 4-of-5 gate result from one round's answers.

    `answers` maps slot index -> bool. Returns None when the round is incomplete:
    four answers over five stored responses must never read as 4/4, which is Package
    F's never-shrink-the-denominator rule.

    Scored through `runner.criterion_status` and `runner._meets`, the same helpers
    `case_gate` uses. A second copy of the rule here would let the screen and the
    release disagree about what failing means.
    """
    block = {"passed": sum(1 for a in answers.values() if a),
             "answered": len(answers), "valid": slots}
    status, rate = runner.criterion_status(block, slots)
    if status != "ok":
        return None
    return runner._meets(rate, floor)


def label(round_results: list) -> str:
    """The observational label for one criterion across K rounds.

    Deliberately says only what was seen, at the K it was seen at. A criterion that
    did not move across five rounds has not been shown stable — five rounds can miss
    low-frequency instability, and cannot see a stable judge error at all.
    """
    if any(r is None for r in round_results) or not round_results:
        return "UNMEASURED"
    if len(set(round_results)) > 1:
        return "OBSERVED_GATE_SENSITIVE"
    return f"NO_GATE_CHANGE_OBSERVED_K{len(round_results)}"


# --- durable state --------------------------------------------------------

def save_atomically(payload: dict, path: Path) -> None:
    """Write-then-rename, the same discipline `sweep.save_ledger` uses.

    350 gradings is one to two hours. A run that persists nothing until the end
    loses all of it to a single exhausted retry, and its summary would not be
    reproducible from its own artifact anyway.
    """
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    os.replace(tmp, path)
