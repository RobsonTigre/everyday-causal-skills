"""Human-verified answers to the questions the L4 judge is asked.

`regrade.py` measures whether the judge repeats itself. It cannot measure whether
the judge is right, and a repeatable judge can be repeatably wrong — this repo has
one confirmed false positive on record (`tasks/lessons.md:38-41`): the judge
credited a method-skill recommendation on `dag_pedagogy_clean` in a response that
named none.

A gold entry answers exactly one question: does this response contain the behaviour
this criterion asks about? It does NOT answer whether the criterion is fair, or
whether the skill should satisfy it. Those are separate decisions — the freeze rule
owns the first and skill repair owns the second — and fusing them is what routes
every failure to "repair the skill".

A gold label may never be substituted for a judge answer in a verdict. The only
legal path from "the judge was wrong" to "the case passes" is: repair the judge,
demonstrate the repair against this key in both directions, then re-measure
everything under the unchanged decision rule.

Nothing here is imported by `case_gate`, `aggregate` or `compile_verdict`, and the
gate digest must not move for any change in this file.

Run: python3 evals/goldkey.py --help   (from repo root)
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import random
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import regrade  # noqa: E402
import runner  # noqa: E402

SLOTS = regrade.SLOTS_PER_CASE
_DIMENSIONS = ("pedagogy", "safety", "actionable")

# The exact shape of a unit. Asserted by the page builder, so a field added here
# without a decision about blinding cannot reach the labeller by accident.
_UNIT_FIELDS = {"unit_id", "case", "slot", "response", "response_sha256",
                "questions", "scenario"}


def question_position(case: dict, qid: str) -> tuple[str, int]:
    """Where a rubric id sits in the stored positional answer array.

    `scorer._judge_l4` transports answers positionally per dimension and ids live
    only in the case YAML, so this mapping has to be re-derived to read one
    criterion out of a slot file. `runner._l4_questions` does the same thing for
    every id at once; this is the single-id read, and it refuses rather than
    guessing so a renamed id cannot silently point at a neighbour.
    """
    rubric = case.get("rubric") or {}
    for dim in _DIMENSIONS:
        for i, entry in enumerate(rubric.get(dim) or []):
            if isinstance(entry, dict) and entry.get("id") == qid:
                return dim, i
    raise KeyError(f"{case.get('name')!r}: no rubric question with id {qid!r}")


def judge_answers(sweep_dir, case_name: str, case: dict, qid: str,
                  slots: int = SLOTS) -> dict[int, bool]:
    """What the judge recorded for one criterion, per slot.

    A slot whose stored array is too short is ABSENT from the result, never False.
    A missing answer read as a recorded no is the never-shrink-the-denominator
    failure Package F exists to prevent, one layer over.
    """
    dim, idx = question_position(case, qid)
    out: dict[int, bool] = {}
    for slot in range(slots):
        data = json.loads(regrade.slot_path(sweep_dir, case_name, slot).read_text())
        scores = data["cases"][0]["run_records"][0]["scores"]
        answers = (scores.get("question_answers") or {}).get(dim) or []
        if idx < len(answers):
            out[slot] = bool(answers[idx])
    return out


def answer_map_index(answer_map: dict, sweep_dir, config: dict
                     ) -> tuple[dict[tuple[str, int, str], bool], dict]:
    """Validate and index a response-, rubric-, config-, and scorer-bound answer map."""
    if not isinstance(answer_map, dict):
        raise TypeError("answer map must be an object")
    if answer_map.get("schema_version") != 1:
        raise ValueError(
            f"answer map schema_version is {answer_map.get('schema_version')!r}, expected 1")
    if not isinstance(config, dict):
        raise TypeError("answer-map config must be an object")
    rows = answer_map.get("answers")
    if not isinstance(rows, list):
        raise TypeError("answer map must contain an answers list")
    if not rows:
        raise ValueError("answer map contains no answers")

    selected_cases = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("answer map entries must be objects")
        case = row.get("case")
        if not isinstance(case, str) or not case.strip():
            raise ValueError("answer map case must be a non-empty string")
        selected_cases.add(case)
    cases = regrade.load_l4_cases(sweep_dir, selected_cases)
    expected_identity = regrade.answer_map_identity(sweep_dir, config, cases)
    for field, expected in expected_identity.items():
        if answer_map.get(field) != expected:
            raise ValueError(
                f"answer map {field} is {answer_map.get(field)!r}, expected {expected!r}")

    question_ids = {
        name: {entry["id"]
               for dimension in _DIMENSIONS
               for entry in ((case.get("rubric") or {}).get(dimension) or [])
               if isinstance(entry, dict) and isinstance(entry.get("id"), str)}
        for name, case in cases.items()
    }
    out: dict[tuple[str, int, str], bool] = {}
    for row in rows:
        case = row["case"]
        slot = row.get("slot")
        qid = row.get("qid")
        answer = row.get("answer")
        if type(slot) is not int:
            raise TypeError("answer map slot must be an integer")
        if not 0 <= slot < SLOTS:
            raise ValueError(f"answer map slot must be between 0 and {SLOTS - 1}")
        if not isinstance(qid, str) or not qid.strip():
            raise ValueError("answer map qid must be a non-empty string")
        if qid not in question_ids[case]:
            raise ValueError(f"answer map has unknown criterion {qid!r} for case {case!r}")
        if type(answer) is not bool:
            raise ValueError("answer map answer must be a bool")
        cell = (case, slot, qid)
        if cell in out:
            raise ValueError(
                f"answer map repeats {qid} on {case} slot {slot}")
        expected = sha256_text(regrade.stored_response(sweep_dir, case, slot))
        if row.get("response_sha256") != expected:
            raise ValueError(
                f"answer map response_sha256 for {qid} on {case} slot {slot} is "
                f"{row.get('response_sha256')}, selected sweep is {expected}")
        out[cell] = answer

    canonical = json.dumps(answer_map, sort_keys=True, separators=(",", ":")).encode()
    provenance = {
        "source": "answer_map",
        **expected_identity,
        "answer_map_content_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    return out, provenance


def mapped_judge_answers(index: dict[tuple[str, int, str], bool], case_name: str,
                         qid: str, slots: int = SLOTS) -> dict[int, bool]:
    """Read one criterion from a validated regrade answer map."""
    return {slot: index[(case_name, slot, qid)]
            for slot in range(slots) if (case_name, slot, qid) in index}


def distance_to_flip(judge: dict[int, bool], floor: float, slots: int) -> int:
    """How many answers would have to change for the gate result to move.

    Leverage, in answers rather than percentage points. Nine of the twenty failing
    criteria sit at 1 — a single different answer moves them across the floor —
    and those are the cells a human read decides.
    """
    passed = sum(1 for v in judge.values() if v)
    need = math.ceil(floor * slots - runner._GATE_EPS)
    return passed - need + 1 if passed >= need else need - passed


def _seed_for(sweep_dir) -> int:
    """A shuffle seed bound to the corpus and the rubric, not to the clock.

    Two extractions of the same corpus must produce the same page, or a labeller
    who restarts sees a different arrangement and the manifest stops describing
    what they read.
    """
    material = f"{Path(sweep_dir).name}:{regrade.l4_cases_sha256()}".encode()
    return int(hashlib.sha256(material).hexdigest()[:16], 16)


def worksheet_units(sweep_dir, thresholds: dict | None = None, decoy_cases: int = 2,
                    decoys_per_unit: int = 3, slots: int = SLOTS
                    ) -> tuple[list[dict], dict]:
    """Blind worksheets for every response of every failing case.

    Returns `(units, manifest)`. A unit carries the response and a shuffled
    question list with NO marker of which questions are disputed; the manifest
    carries that separately and is not part of what the labeller reads. Cases are
    ordered by leverage — the smallest distance-to-flip among their disputed
    criteria first — so a labeller who stops early has still decided something.

    `decoy_cases` whole passing cases are folded in so that not every response on
    the desk belongs to a failing case. Decoy QUESTIONS come from the same case as
    the unit: they are the co-resident required questions the judge already
    answered, which is a control arm that costs nothing to read.
    """
    failing = regrade.failing_criteria(sweep_dir, thresholds)
    floor = runner._threshold(thresholds, 4, "question_rate")
    ledger = json.loads((Path(sweep_dir) / "ledger.json").read_text())
    rng = random.Random(_seed_for(sweep_dir))

    order = []
    for name in sorted(failing):
        case = runner.load_case(ledger["cases"][name]["path"])
        best = min(distance_to_flip(judge_answers(sweep_dir, name, case, qid, slots),
                                    floor, slots)
                   for qid in sorted(failing[name]))
        order.append((best, name, case))
    order.sort(key=lambda row: (row[0], row[1]))

    passing = sorted(set(ledger["cases"]) - set(failing))
    for name in rng.sample(passing, min(decoy_cases, len(passing))):
        order.append((99, name, runner.load_case(ledger["cases"][name]["path"])))

    units, manifest = [], {}
    for _, name, case in order:
        disputed = sorted(failing.get(name, set()))
        pool = [(dim, e) for dim in _DIMENSIONS
                for e in ((case.get("rubric") or {}).get(dim) or [])
                if isinstance(e, dict) and e.get("id")
                and e["id"] not in disputed]
        decoys = [e["id"] for _, e in rng.sample(pool, min(decoys_per_unit, len(pool)))]
        texts = {e["id"]: e.get("question", "")
                 for dim in _DIMENSIONS
                 for e in ((case.get("rubric") or {}).get(dim) or [])
                 if isinstance(e, dict) and e.get("id")}
        # The text the model was actually given. `inject_schema` pastes a df.head()
        # sample and column dtypes into user_message and is called unconditionally at
        # runner.py:1180, above the layer branch, so every L4 run saw it. Showing the
        # bare user_message would show the labeller less context than the model read.
        # The raw `dataset` path is deliberately NOT carried: a real value is
        # `evals/data/iv_weak.csv`, whose filename states the method and the
        # condition — the same thing hiding `description` protects — and the schema it
        # points at is already inside `scenario`.
        scenario = runner.inject_schema(case).get("user_message") or ""
        for slot in range(slots):
            response = regrade.stored_response(sweep_dir, name, slot)
            shown = disputed + decoys
            rng.shuffle(shown)
            unit_id = hashlib.sha256(f"{name}:{slot}".encode()).hexdigest()[:12]
            units.append({
                "unit_id": unit_id, "case": name, "slot": slot,
                "response": response,
                "response_sha256": hashlib.sha256(response.encode()).hexdigest(),
                "questions": [{"qid": q, "text": texts[q]} for q in shown],
                "scenario": scenario,
            })
            manifest[unit_id] = {"case": name, "slot": slot,
                                 "disputed": disputed, "decoy": decoys}
    return units, manifest


def render_worksheet(unit: dict) -> str:
    """The page a labeller reads. Its chrome carries no case name, slot or answer.

    `unit_id` is a hash, so it identifies the page for the join without naming what
    is on it. Everything this module writes is scrubbed of anchors.

    The honest limit: the response itself is shown verbatim, because it is the
    thing being read, and a response can always name its own domain — "I'll use
    the IV skill" deanonymises which skill is under test no matter what the page
    around it says. Blinding here hides the case, the slot, the judge's answer and
    which question is disputed. It cannot hide the subject matter, and claiming
    otherwise would be the kind of guarantee nobody implemented.
    """
    lines = [f"## Unit {unit['unit_id']}", "",
             "Read the response, then answer each question **yes** or **no**.",
             "A **yes** requires a verbatim quote copied from the response —",
             "a yes with no quotable span is not a valid entry.", "",
             "### Response", "", "````", unit["response"], "````", "",
             "### Questions", ""]
    for n, q in enumerate(unit["questions"], 1):
        lines += [f"{n}. `{q['qid']}` — {q['text']}", "",
                  "   - label: ", "   - quote: ", "   - note: ", ""]
    return "\n".join(lines)


ENTRY_FIELDS = {"unit_id", "case", "slot", "qid", "response_sha256", "label",
                "quote", "note", "suspect_case_defect", "labeler", "pass_name",
                "failure_reason", "labeled_at", "supersedes", "amendments", "prev",
                "digest"}
_REQUIRED_FIELDS = {"unit_id", "case", "slot", "qid", "response_sha256", "label",
                    "labeler", "pass_name"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def validate_entry(entry: dict, response: str) -> None:
    """A yes must cite a literal span of the response it is about.

    The one confirmed judge failure on record was crediting a behaviour that was
    not in the text. A human label that cannot point at where the behaviour
    happened is the same failure with a person in the chair, so the schema refuses
    it instead of trusting care. The check is a substring test, which means the
    key is machine-verifiable rather than merely attested.

    `note` and `suspect_case_defect` record a labeller's belief that the CRITERION
    is wrong. They are deliberately inert: the label stays a fact about the text,
    the note routes the criterion to a separate decision with evidence attached,
    and nothing here demotes a question or moves a floor.
    """
    missing = _REQUIRED_FIELDS - set(entry)
    if missing:
        raise ValueError(f"entry is missing required field(s): {sorted(missing)}")
    unknown = set(entry) - ENTRY_FIELDS
    if unknown:
        raise ValueError(f"entry carries unknown field(s): {sorted(unknown)}")
    if type(entry["label"]) is not bool:
        raise ValueError(f"label must be a bool, got {entry['label']!r}")
    if entry["response_sha256"] != sha256_text(response):
        raise ValueError(
            "response_sha256 does not match the response supplied — this entry "
            "was written against different text")
    if entry["label"]:
        quote = (entry.get("quote") or "").strip()
        if not quote:
            raise ValueError("a yes label requires a verbatim quote from the response")
        if quote not in response:
            raise ValueError(
                "quote is not a literal substring of the response — a yes that "
                "cannot be located in the text is the judge's confirmed failure mode")


def entry_digest(record: dict) -> str:
    """Hash of everything in the record except the digest itself.

    `prev` is inside the hashed body, which is what binds line N to line N-1: an
    edit anywhere breaks every digest after it.
    """
    body = {k: v for k, v in record.items() if k != "digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def append_entry(path, entry: dict, response: str) -> str:
    """Validate, chain, append. Returns the new line's digest.

    Append-only and chained so that "I labelled this before I saw the tally" is
    checkable rather than asserted. The labeller here also wrote the questions and
    wants the release to ship; that is exactly the circumstance in which a
    silently-editable file is worth nothing as evidence.
    """
    path = Path(path)
    existing = path.read_text().splitlines() if path.exists() else []
    prev = json.loads(existing[-1])["digest"] if existing else ""
    record = {**entry, "prev": prev}
    validate_entry(record, response)
    record["digest"] = entry_digest(record)
    with path.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record["digest"]


_CORRECTION_FIELDS = {"case", "slot", "qid", "response_sha256", "from_label",
                      "to_label", "quote", "reason", "approved_by", "approved_at",
                      "prev", "digest"}
_CORRECTION_REQUIRED = _CORRECTION_FIELDS - {"prev", "digest"}


def validate_label_correction(correction: dict, response: str) -> None:
    """Validate one explicit human-approved correction to a derived gold label."""
    missing = _CORRECTION_REQUIRED - set(correction)
    if missing:
        raise ValueError(f"correction is missing required field(s): {sorted(missing)}")
    unknown = set(correction) - _CORRECTION_FIELDS
    if unknown:
        raise ValueError(f"correction carries unknown field(s): {sorted(unknown)}")
    if not isinstance(correction["case"], str) or not correction["case"].strip():
        raise ValueError("correction case must be a non-empty string")
    if type(correction["slot"]) is not int:
        raise ValueError("correction slot must be an integer")
    if not 0 <= correction["slot"] < SLOTS:
        raise ValueError(f"correction slot must be between 0 and {SLOTS - 1}")
    if not isinstance(correction["qid"], str) or not correction["qid"].strip():
        raise ValueError("correction qid must be a non-empty string")
    if type(correction["from_label"]) is not bool or \
            type(correction["to_label"]) is not bool:
        raise ValueError("correction labels must be bools")
    if correction["from_label"] == correction["to_label"]:
        raise ValueError("correction must change the label")
    if correction["response_sha256"] != sha256_text(response):
        raise ValueError("correction response_sha256 does not match the frozen response")
    if not isinstance(correction["reason"], str) or not correction["reason"].strip():
        raise ValueError("correction reason must be a non-empty string")
    if not isinstance(correction["approved_by"], str) or not correction["approved_by"].strip():
        raise ValueError("correction approved_by must be a non-empty string")
    approved_at = correction["approved_at"]
    if not isinstance(approved_at, str) or not approved_at.strip():
        raise ValueError("correction approved_at must be a non-empty ISO timestamp")
    try:
        approved_time = datetime.fromisoformat(
            approved_at[:-1] + "+00:00" if approved_at.endswith("Z") else approved_at)
    except ValueError as e:
        raise ValueError("correction approved_at is not a valid ISO timestamp") from e
    if approved_time.tzinfo is None:
        raise ValueError("correction approved_at must include a timezone")
    quote = correction["quote"]
    if not isinstance(quote, str):
        raise TypeError("correction quote must be a string")
    if correction["to_label"]:
        if not quote.strip():
            raise ValueError("a correction to yes requires a verbatim quote")
        if quote not in response:
            raise ValueError("correction quote is not a literal substring of the response")


def append_label_corrections(path, corrections: list[dict], sweep_dir) -> int:
    """Serialize one real destination; preserve symlinks and reject hard-link forks."""
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    lock_fd = os.open(path.parent, flags)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if path.exists() and path.stat().st_nlink != 1:
            raise ValueError(
                f"correction chain {path} has hard links; append through one canonical "
                "path only")
        return _append_label_corrections_locked(path, corrections, sweep_dir)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _append_label_corrections_locked(path, corrections: list[dict], sweep_dir) -> int:
    path = Path(path)
    existing = path.read_text() if path.exists() else ""
    raw = read_entries(path) if existing.strip() else []
    seen = {(e["case"], e["slot"], e["qid"]) for e in raw}
    planned = set()
    prev = raw[-1]["digest"] if raw else ""
    records = []
    for correction in corrections:
        case = correction.get("case")
        slot = correction.get("slot")
        qid = correction.get("qid")
        if not isinstance(case, str) or not case.strip():
            raise ValueError("correction case must be a non-empty string")
        if type(slot) is not int:
            raise TypeError("correction slot must be an integer")
        if not 0 <= slot < SLOTS:
            raise ValueError(f"correction slot must be between 0 and {SLOTS - 1}")
        if not isinstance(qid, str) or not qid.strip():
            raise ValueError("correction qid must be a non-empty string")
        cell = (case, slot, qid)
        if cell in seen or cell in planned:
            raise ValueError(
                f"{cell[2]} on {cell[0]} slot {cell[1]} already has a label correction")
        response = regrade.stored_response(sweep_dir, case, slot)
        record = {**correction, "prev": prev}
        validate_label_correction(record, response)
        record["digest"] = entry_digest(record)
        records.append(json.dumps(record, sort_keys=True) + "\n")
        prev = record["digest"]
        planned.add(cell)

    if not records:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", dir=path.parent, prefix=f".{path.name}.", delete=False) as fh:
            temp_path = Path(fh.name)
            fh.write(existing)
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.writelines(records)
            fh.flush()
            os.fsync(fh.fileno())
        if path.exists():
            temp_path.chmod(path.stat().st_mode)
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return len(records)


def apply_label_corrections(gold: list[dict], corrections: list[dict], sweep_dir) -> list[dict]:
    """Apply an append-only correction chain while rebuilding the derived gold key."""
    out = [dict(entry) for entry in gold]
    positions = {(e["case"], e["slot"], e["qid"]): i for i, e in enumerate(out)}
    applied = set()
    for correction in corrections:
        cell = (correction["case"], correction["slot"], correction["qid"])
        if cell in applied:
            raise ValueError(
                f"{cell[2]} on {cell[0]} slot {cell[1]} has multiple label corrections")
        if cell not in positions:
            raise ValueError(
                f"{cell[2]} on {cell[0]} slot {cell[1]} is not in the derived gold key")
        response = regrade.stored_response(sweep_dir, cell[0], cell[1])
        validate_label_correction(correction, response)
        target = out[positions[cell]]
        if target.get("response_sha256") != correction["response_sha256"]:
            raise ValueError(
                f"{cell[2]} on {cell[0]} slot {cell[1]}: correction and gold refer "
                "to different responses")
        if target.get("label") != correction["from_label"]:
            raise ValueError(
                f"{cell[2]} on {cell[0]} slot {cell[1]}: correction expects label "
                f"{correction['from_label']}, derived gold has {target.get('label')}")
        out[positions[cell]] = {
            **target,
            "label": correction["to_label"],
            "quote": correction["quote"],
            "note": correction["reason"],
            "labeler": correction["approved_by"],
            "labeled_at": correction["approved_at"],
            "supersedes": target.get("digest"),
            "label_corrections": target.get("label_corrections", 0) + 1,
            "correction_digest": correction["digest"],
        }
        applied.add(cell)
    return out


def verify_chain(path) -> int:
    """Walk the chain, raising on the first break. Returns the entry count."""
    prev = ""
    count = 0
    for i, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("prev") != prev:
            raise ValueError(
                f"line {i}: chain broken — prev is {record.get('prev')!r}, "
                f"expected {prev!r}")
        if entry_digest(record) != record.get("digest"):
            raise ValueError(f"line {i}: digest does not match its content — edited")
        prev = record["digest"]
        count += 1
    return count


def read_entries(path) -> list[dict]:
    """Every entry, after verifying the chain. A broken chain is not readable."""
    verify_chain(path)
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


_NO_REASON = {"", "none", "no reason", "n/a", "na", "-", "nothing"}


def resolve_entries(entries: list[dict]) -> list[dict]:
    """Collapse each cell's amendment chain into one current entry.

    The label is decided by the FIRST entry for a cell and is immutable; later
    entries may only correct supporting evidence — quote, note, case-defect flag.
    That split is the whole amendment policy: the fact being recorded is locked once
    chained, the evidence for it can be improved, and every prior value stays in the
    file because the store is append-only.

    A later entry carrying a different label is refused here as well as at collect
    time. Collect guards the writer; this guards every reader, including one pointed
    at a hand-edited file.

    `amendments` counts corrections, so a report can say a cell was revised without
    anyone having to diff the chain.
    """
    order: list[tuple] = []
    base: dict[tuple, dict] = {}
    for entry in entries:
        cell = (entry["case"], entry["slot"], entry["qid"],
                entry.get("pass_name", "pass1"))
        if cell not in base:
            base[cell] = {**entry, "amendments": 0}
            order.append(cell)
            continue
        current = base[cell]
        if entry.get("response_sha256") != current.get("response_sha256"):
            raise ValueError(
                f"{cell[2]} on {cell[0]} slot {cell[1]}: an amendment carries "
                f"response_sha256 {entry.get('response_sha256')!r} against locked "
                f"{current.get('response_sha256')!r} — evidence cannot move between "
                "responses")
        if entry.get("label") != current.get("label"):
            raise ValueError(
                f"{cell[2]} on {cell[0]} slot {cell[1]}: an amendment carries label "
                f"{entry.get('label')!r} against a locked {current.get('label')!r} — "
                "a decision is not amendable, only its evidence")
        if (entry.get("failure_reason") or "") != (current.get("failure_reason") or ""):
            raise ValueError(
                f"{cell[2]} on {cell[0]} slot {cell[1]}: an amendment changes the "
                "failure reason, which is decision-bearing and locked")
        base[cell] = {**current,
                      "quote": entry.get("quote", current.get("quote")),
                      "note": entry.get("note", current.get("note")),
                      "suspect_case_defect": entry.get(
                          "suspect_case_defect", current.get("suspect_case_defect")),
                      "labeled_at": entry.get("labeled_at", current.get("labeled_at")),
                      "amendments": current["amendments"] + 1}
    return [base[c] for c in order]


def inversion_targets(pass1: list[dict]) -> list[dict]:
    """The cells the second pass revisits: the ones labelled yes.

    A no is already a failure reason, so asking for one adds nothing. The generous
    pass — an author resolving ambiguity in favour of the question he wrote — only
    produces a yes, which is where the whole bias lives.
    """
    return [e for e in pass1 if e["label"] is True]


def render_inversion(unit: dict, qids: list[str]) -> str:
    """The second-pass page. Same response, opposite question, no first-pass label."""
    lines = [f"## Unit {unit['unit_id']} — failure pass", "",
             "For each question below, state the **strongest concrete reason this",
             "response FAILS the criterion**. If there is genuinely none, write",
             "`none`. Do not restate your earlier answer; look for the failure.", "",
             "### Response", "", "````", unit["response"], "````", "",
             "### Questions", ""]
    texts = {q["qid"]: q["text"] for q in unit["questions"]}
    for n, qid in enumerate(qids, 1):
        lines += [f"{n}. `{qid}` — {texts.get(qid, '')}", "",
                  "   - failure_reason: ", ""]
    return "\n".join(lines)


def join_passes(pass1: list[dict], pass2: list[dict]) -> tuple[list[dict], list[dict]]:
    """Merge the two passes into (gold, contested).

    A yes that also produced a concrete failure reason is contested: the generous
    pass usually comes from not looking for the failure, not from weighing it and
    rejecting it, so making the labeller look is a mechanical anti-anchor rather
    than a plea for self-discipline. Contested cells are reported as unresolved and
    never used to score the judge.
    """
    pass1, pass2 = resolve_entries(pass1), resolve_entries(pass2)
    second_pass = {(e["case"], e["slot"], e["qid"]): e for e in pass2}
    gold, contested = [], []
    for entry in pass1:
        key = (entry["case"], entry["slot"], entry["qid"])
        if entry["label"] is False:
            gold.append(entry)
            continue
        if key not in second_pass:
            raise ValueError(
                f"{entry['qid']} on {entry['case']} slot {entry['slot']} was labelled "
                "yes but has no inversion-pass entry — a half-labelled cell must not "
                "enter the key")
        inversion = second_pass[key]
        if inversion.get("response_sha256") != entry.get("response_sha256"):
            raise ValueError(
                f"{entry['qid']} on {entry['case']} slot {entry['slot']}: pass 2 "
                f"response_sha256 is {inversion.get('response_sha256')!r} against "
                f"pass 1 {entry.get('response_sha256')!r} — different responses "
                "cannot be joined")
        reason = (inversion.get("failure_reason") or "").strip()
        if reason.lower() in _NO_REASON:
            gold.append(entry)
        else:
            contested.append({**entry, "failure_reason": reason})
    return gold, contested


def _require_distinct_join_paths(**paths) -> None:
    """Refuse any input/output aliases before join can overwrite a source chain."""
    seen: list[tuple[str, Path, Path]] = []
    for name, raw in paths.items():
        path = Path(raw)
        resolved = path.resolve()
        for other_name, other_path, other_resolved in seen:
            same_file = resolved == other_resolved
            if not same_file and path.exists() and other_path.exists():
                same_file = path.samefile(other_path)
            if same_file:
                raise ValueError(
                    "join paths must be distinct: "
                    f"--{other_name} and --{name} both identify {resolved}")
        seen.append((name, path, resolved))


def write_chain(path, entries: list[dict]) -> None:
    """Write entries as a fresh derived chain, without mutating their source chains."""
    prev = ""
    lines = []
    for entry in entries:
        record = {k: v for k, v in entry.items() if k not in {"prev", "digest"}}
        record["prev"] = prev
        record["digest"] = entry_digest(record)
        lines.append(json.dumps(record, sort_keys=True) + "\n")
        prev = record["digest"]
    Path(path).write_text("".join(lines))


def score_judge_against_gold(gold: list[dict], sweep_dir, thresholds: dict | None = None,
                             slots: int = SLOTS, answer_map: dict | None = None,
                             answer_config: dict | None = None) -> dict:
    """How often the judge's recorded answer matches a blind human read.

    Gate agreement is scored per criterion, and only when every slot carries a
    gold label. A criterion labelled in 3 of 5 slots reports `incomplete` and
    has no gold gate result. Its labelled cells still contribute to cell-level
    false-positive and false-negative totals.

    `gate_gold` is the criterion's gate result computed from the human labels
    through `runner._meets` and the SAME floor the release gate uses. It is
    diagnostic only: this function is never called by `case_gate`, and a gold
    label may not be substituted for a judge answer in a verdict.
    """
    gold = resolve_entries(gold)
    response_hashes: dict[tuple[str, int], str] = {}
    for entry in gold:
        response_key = (entry["case"], entry["slot"])
        if response_key not in response_hashes:
            response_hashes[response_key] = sha256_text(
                regrade.stored_response(sweep_dir, *response_key))
        expected = response_hashes[response_key]
        if entry["response_sha256"] != expected:
            raise ValueError(
                f"{entry['qid']} on {entry['case']} slot {entry['slot']}: gold "
                f"response_sha256 is {entry['response_sha256']}, selected sweep is "
                f"{expected} — labels from another response cannot be scored")
    floor = runner._threshold(thresholds, 4, "question_rate")
    ledger = json.loads((Path(sweep_dir) / "ledger.json").read_text())
    if answer_map is not None:
        mapped_answers, judge_provenance = answer_map_index(
            answer_map, sweep_dir, answer_config or {})
    else:
        mapped_answers = None
        judge_provenance = {
            "source": "historical_sweep",
            "sweep": str(Path(sweep_dir).resolve()),
        }

    by_criterion: dict[tuple, list[dict]] = {}
    for entry in gold:
        by_criterion.setdefault((entry["case"], entry["qid"]), []).append(entry)

    rows, defects = [], []
    for (case_name, qid), entries in sorted(by_criterion.items()):
        case = runner.load_case(ledger["cases"][case_name]["path"])
        judge = (mapped_judge_answers(mapped_answers, case_name, qid, slots)
                 if mapped_answers is not None
                 else judge_answers(sweep_dir, case_name, case, qid, slots))
        human = {e["slot"]: e["label"] for e in entries}
        expected_slot_ids = set(range(slots))
        human_slot_ids = set(human)
        if not human_slot_ids <= expected_slot_ids:
            raise ValueError(
                f"{qid} on {case_name}: expected slots {sorted(expected_slot_ids)}, "
                f"got {sorted(human_slot_ids)}")
        defects.extend({"case": case_name, "qid": qid, "slot": e["slot"],
                        "note": e.get("note", "")}
                       for e in entries if e.get("suspect_case_defect"))

        shared = sorted(set(judge) & set(human))
        fp = sum(1 for s in shared if judge[s] and not human[s])
        fn = sum(1 for s in shared if not judge[s] and human[s])
        complete = (human_slot_ids == expected_slot_ids
                    and set(judge) == expected_slot_ids)
        gold_pass = sum(1 for v in human.values() if v)
        judge_pass = sum(1 for v in judge.values() if v)
        rows.append({
            "case": case_name, "qid": qid,
            "status": "ok" if complete else "incomplete",
            "labelled": len(human), "slots": slots,
            "judge_pass": judge_pass, "gold_pass": gold_pass if complete else None,
            "false_positive": fp, "false_negative": fn,
            "gate_judge": runner._meets(judge_pass / slots, floor)
                          if len(judge) == slots else None,
            "gate_gold": runner._meets(gold_pass / slots, floor) if complete else None,
            "distance_to_flip": distance_to_flip(judge, floor, slots),
        })
    for row in rows:
        row["gate_disagrees"] = (row["gate_gold"] is not None
                                 and row["gate_judge"] is not None
                                 and row["gate_gold"] != row["gate_judge"])
    return {
        "judge_provenance": judge_provenance,
        "criteria": rows,
        "suspected_case_defects": defects,
        "totals": {
            "criteria": len(rows),
            "cells": sum(r["labelled"] for r in rows),
            "false_positive": sum(r["false_positive"] for r in rows),
            "false_negative": sum(r["false_negative"] for r in rows),
            "gate_disagreements": sum(1 for r in rows if r["gate_disagrees"]),
            "incomplete": sum(1 for r in rows if r["status"] == "incomplete"),
        },
    }


def render_gold_md(summary: dict) -> str:
    """The human-readable report.

    Deliberately incapable of printing a verdict token: this measures the
    instrument, and a reader who finds a familiar word here will treat it as a
    gate result. Every row says what the judge recorded, what the gold label says,
    and where they disagree — nothing more.
    """
    t = summary["totals"]
    provenance = summary.get("judge_provenance") or {}
    if provenance.get("source") == "answer_map":
        provenance_lines = [
            "- judge source: regrade answer map",
            f"- sweep: `{provenance.get('sweep', '')}`",
            (
                f"- answer-map content SHA-256: "
                f"`{provenance.get('answer_map_content_sha256', '')}`"
            ),
            f"- case-input SHA-256: `{provenance.get('case_inputs_sha256', '')}`",
            f"- config SHA-256: `{provenance.get('config_sha256', '')}`",
            f"- scorer SHA-256: `{provenance.get('scorer_sha256', '')}`",
        ]
    elif provenance.get("source") == "historical_sweep":
        provenance_lines = [
            "- judge source: historical sweep",
            f"- sweep: `{provenance.get('sweep', '')}`",
        ]
    else:
        provenance_lines = ["- judge source: unspecified"]
    lines = ["# Judge accuracy against the gold key", "", *provenance_lines, "",
             f"- criteria scored: {t['criteria']} ({t['incomplete']} incomplete)",
             f"- gold cells: {t['cells']}",
             f"- judge said yes where the gold label says no (false positive): "
             f"{t['false_positive']}",
             f"- judge said no where the gold label says yes (false negative): "
             f"{t['false_negative']}",
             f"- criteria where the judge and the gold labels disagree about the "
             f"gate result: {t['gate_disagreements']}", "",
             "A criterion labelled in fewer than every slot is reported incomplete "
             "and has no gold gate result. Its labelled cells still contribute to "
             "cell-level false-positive and false-negative totals.", "",
             "| case | criterion | judge | gold | FP | FN | disagree | to flip |",
             "|---|---|---|---|---|---|---|---|"]
    for r in summary["criteria"]:
        gold = f"{r['gold_pass']}/{r['slots']}" if r["status"] == "ok" \
               else f"{r['labelled']} of {r['slots']} labelled"
        lines.append(
            f"| {r['case']} | `{r['qid']}` | {r['judge_pass']}/{r['slots']} | {gold} "
            f"| {r['false_positive']} | {r['false_negative']} "
            f"| {'yes' if r['gate_disagrees'] else 'no'} | {r['distance_to_flip']} |")
    if summary["suspected_case_defects"]:
        lines += ["", "## Criteria a labeller flagged as possibly unsatisfiable", "",
                  ("Recorded with evidence, acting on nothing. No question is "
                   "reworded, reordered or demoted by this file."), ""]
        for d in summary["suspected_case_defects"]:
            lines.append(f"- `{d['qid']}` on {d['case']} slot {d['slot']} — {d['note']}")
    return "\n".join(lines) + "\n"


# Only these reach the browser. `case` and `slot` are dropped: the page joins back
# on `unit_id`, so it never needs to know which case it is showing. Defined here
# rather than beside the builder because `build_id` hashes exactly this projection,
# and the page and the collector must agree on what a build IS.
_PAGE_FIELDS = ("unit_id", "response", "response_sha256", "questions", "scenario")

_EVIDENCE_FIELDS = ("quote", "note", "suspect_case_defect")


def build_id(units: list[dict]) -> str:
    """Identity of a built page: the exact units it carries.

    Rebuilding the same corpus reproduces it, so a progress file survives a rebuild.
    Different units produce a different id, so answers cannot silently attach to
    questions they were never given against.
    """
    page = [{k: u[k] for k in _PAGE_FIELDS} for u in units]
    return hashlib.sha256(json.dumps(page, sort_keys=True).encode()).hexdigest()[:16]


def _plan_entry(answer: dict, unit: dict, meta: dict, labeler: str,
                pass_no: int) -> dict:
    cell_common = {"unit_id": answer["unit_id"], "case": meta["case"],
                   "slot": meta["slot"], "qid": answer["qid"],
                   "response_sha256": unit["response_sha256"],
                   "labeler": labeler, "pass_name": f"pass{pass_no}",
                   "labeled_at": answer["labeled_at"], "supersedes": None}
    if pass_no == 1:
        return {**cell_common, "label": answer["label"],
                "quote": answer.get("quote") or "", "note": answer.get("note") or "",
                "suspect_case_defect": answer.get("suspect_case_defect", False)}
    # A pass-2 entry is not a label. It carries label False and an empty quote so
    # the yes-needs-a-quote rule cannot fire on a cell that records a reason.
    return {**cell_common, "label": False, "quote": "",
            "failure_reason": answer["failure_reason"].strip()}


def collect_export(export: dict, units: list[dict], manifest: dict,
                   pass1_path, pass2_path, labeler: str, pass_no: int = 1) -> dict:
    """Ingest a browser export. Validates the whole export before writing anything.

    Two-phase deliberately: a half-ingested export leaves a chain that is valid and
    incomplete, which is indistinguishable from a finished one and worse than a
    refusal. Every rejection names the cell.

    Idempotent across days, because every export carries everything answered so far
    and the second ingest necessarily re-presents the first one's cells. What
    happens on a repeat depends on what changed:

    - identical                       -> skipped
    - label / failure reason changed  -> CONFLICT, nothing written. The decision is
      locked once chained; overwriting it is the edit-after-seeing-the-tally the
      chain exists to prevent.
    - quote / note / defect changed   -> an amendment appended, `supersedes` pointing
      at the entry it corrects. Nothing is overwritten, the prior value stays in the
      file, and an amended quote is revalidated against the response.
    """
    by_unit = {u["unit_id"]: u for u in units}
    expected = build_id(units)
    if export.get("build") != expected:
        return {"written": 0, "skipped": 0, "amended": 0, "conflicts": [],
                "rejected": [f"export build {export.get('build')!r} is not this build "
                             f"{expected!r} — it was made from a different set of "
                             "units"]}

    path = pass1_path if pass_no == 1 else pass2_path
    on_file, head = {}, {}
    if Path(path).exists() and Path(path).read_text().strip():
        raw = read_entries(path)
        for e in raw:
            head[(e["case"], e["slot"], e["qid"])] = e["digest"]
        for e in resolve_entries(raw):
            on_file[(e["case"], e["slot"], e["qid"])] = e

    rejected, conflicts, actions = [], [], []
    planned_cells: dict[tuple, dict] = {}
    rows = sorted((export.get("answers") or {}).items(),
                  key=lambda item: (item[1].get("labeled_at") or "",
                                    item[1].get("qid") or ""))

    for answer_key, answer in rows:
        unit = by_unit.get(answer.get("unit_id"))
        meta = manifest.get(answer.get("unit_id"))
        who = f"{answer.get('unit_id')}/{answer.get('qid')}"
        expected_key = f"{answer.get('unit_id')}|{answer.get('qid')}|p{pass_no}"
        if answer_key != expected_key:
            rejected.append(f"{who}: answer key {answer_key!r} is not {expected_key!r}")
            continue
        if unit is None or meta is None:
            rejected.append(f"{who}: not a unit of this build")
            continue
        if answer.get("response_sha256") != unit["response_sha256"]:
            rejected.append(f"{who}: response_sha256 does not match the unit")
            continue
        if answer.get("qid") not in {q["qid"] for q in unit["questions"]}:
            rejected.append(f"{who}: this unit never asked {answer.get('qid')!r}")
            continue
        if answer.get("pass") != pass_no:
            rejected.append(f"{who}: pass {answer.get('pass')!r} in a pass {pass_no} "
                            "collection")
            continue
        labeled_at = answer.get("labeled_at")
        if not isinstance(labeled_at, str) or not labeled_at.strip():
            rejected.append(f"{who}: labeled_at must be a non-empty ISO timestamp")
            continue
        try:
            labeled_time = datetime.fromisoformat(
                labeled_at[:-1] + "+00:00" if labeled_at.endswith("Z") else labeled_at)
        except ValueError:
            rejected.append(f"{who}: labeled_at is not a valid ISO timestamp")
            continue
        if labeled_time.tzinfo is None:
            rejected.append(f"{who}: labeled_at must include a timezone")
            continue

        if pass_no == 1:
            if "label" not in answer:
                continue                                   # opened, not answered
            if type(answer["label"]) is not bool:
                rejected.append(f"{who}: label must be a bool, got "
                                f"{answer['label']!r} — never coerced")
                continue
            if not isinstance(answer.get("quote", ""), str):
                rejected.append(f"{who}: quote must be a string")
                continue
            if not isinstance(answer.get("note", ""), str):
                rejected.append(f"{who}: note must be a string")
                continue
            if type(answer.get("suspect_case_defect", False)) is not bool:
                rejected.append(f"{who}: suspect_case_defect must be a bool")
                continue
        else:
            if not isinstance(answer.get("failure_reason", ""), str):
                rejected.append(f"{who}: failure_reason must be a string")
                continue
            if not (answer.get("failure_reason") or "").strip():
                continue                                   # opened, not answered

        entry = _plan_entry(answer, unit, meta, labeler, pass_no)
        cell = (entry["case"], entry["slot"], entry["qid"])
        planned = planned_cells.get(cell)
        if planned is not None:
            if planned["response_sha256"] != entry["response_sha256"]:
                rejected.append(
                    f"{cell[0]} slot {cell[1]} {cell[2]}: one export carries "
                    "different response_sha256 values for the same stored cell")
            else:
                rejected.append(
                    f"{cell[0]} slot {cell[1]} {cell[2]}: one export carries the "
                    "same stored cell more than once")
            continue
        planned_cells[cell] = entry
        prior = on_file.get(cell)

        if prior is None:
            try:
                validate_entry({**entry, "prev": ""}, unit["response"])
            except ValueError as e:
                rejected.append(f"{cell[0]} slot {cell[1]} {cell[2]}: {e}")
                continue
            actions.append(("write", entry, unit))
            continue

        if prior["response_sha256"] != entry["response_sha256"]:
            rejected.append(
                f"{cell[0]} slot {cell[1]} {cell[2]}: response_sha256 on file is "
                f"{prior['response_sha256']}, current unit is {entry['response_sha256']} — "
                "different responses require separate label stores")
            continue
        if pass_no == 1 and prior["label"] != entry["label"]:
            conflicts.append(f"{cell[0]} slot {cell[1]} {cell[2]}: label on file is "
                             f"{prior['label']}, export says {entry['label']}")
            continue
        if pass_no == 2 and (prior.get("failure_reason") or "") != \
                entry["failure_reason"]:
            conflicts.append(f"{cell[0]} slot {cell[1]} {cell[2]}: the failure reason "
                             "on file differs from the export")
            continue

        changed = [f for f in _EVIDENCE_FIELDS if prior.get(f, "") != entry.get(f, "")]
        if not changed:
            actions.append(("skip", entry, unit))
            continue
        prior_labeled_at = prior.get("labeled_at")
        if prior_labeled_at:
            prior_time = datetime.fromisoformat(
                prior_labeled_at[:-1] + "+00:00"
                if prior_labeled_at.endswith("Z") else prior_labeled_at)
            if labeled_time <= prior_time:
                rejected.append(
                    f"{cell[0]} slot {cell[1]} {cell[2]}: evidence timestamp "
                    f"{labeled_at!r} is not newer than {prior_labeled_at!r}")
                continue
        amendment = {**entry, "supersedes": head.get(cell)}
        try:
            validate_entry({**amendment, "prev": ""}, unit["response"])
        except ValueError as e:
            rejected.append(f"{cell[0]} slot {cell[1]} {cell[2]}: {e}")
            continue
        actions.append(("amend", amendment, unit))

    if rejected or conflicts:
        return {"written": 0, "skipped": 0, "amended": 0,
                "conflicts": conflicts, "rejected": rejected}

    written = skipped = amended = 0
    path = Path(path)
    existing = path.read_text() if path.exists() else ""
    prev = json.loads(existing.splitlines()[-1])["digest"] if existing.strip() else ""
    records = []
    for kind, entry, unit in actions:
        if kind == "skip":
            skipped += 1
            continue
        record = {**entry, "prev": prev}
        validate_entry(record, unit["response"])
        record["digest"] = entry_digest(record)
        records.append(json.dumps(record, sort_keys=True) + "\n")
        prev = record["digest"]
        written += kind == "write"
        amended += kind == "amend"

    # One export is one transaction. Build the complete next chain beside the target,
    # then atomically replace it; an interrupted write or failed replace leaves the
    # prior chain byte-for-byte intact rather than committing a valid-looking prefix.
    if records:
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                    "w", dir=path.parent, prefix=f".{path.name}.", delete=False) as fh:
                temp_path = Path(fh.name)
                fh.write(existing)
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.writelines(records)
                fh.flush()
                os.fsync(fh.fileno())
            if path.exists():
                temp_path.chmod(path.stat().st_mode)
            temp_path.replace(path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
    return {"written": written, "skipped": skipped, "amended": amended,
            "conflicts": [], "rejected": []}


def pass2_units(units: list[dict], pass1_path) -> list[dict]:
    """Units for the inversion pass: only the cells labelled yes in a CHAINED pass 1.

    This is the pass boundary, and it is why the two passes are separate builds. A
    single page with a mode toggle lets a pass-1 label be revised after the inversion
    prompt has been read — the exact anchoring the second pass exists to detect, and
    `join_passes` cannot see it because it only merges by cell key. Requiring pass 1
    to be on file and hash-chained before this page can exist makes the boundary a
    fact about the filesystem rather than a matter of discipline.
    """
    path = Path(pass1_path)
    if not path.exists() or not path.read_text().strip():
        raise ValueError(
            f"{path} is empty or absent — collect pass 1 before building pass 2; "
            "the inversion page is generated from the yes-cells already on file")
    stored = {(e["case"], e["slot"], e["qid"]): e
              for e in resolve_entries(read_entries(path))}
    out = []
    for unit in units:
        keep = []
        for question in unit["questions"]:
            cell = (unit["case"], unit["slot"], question["qid"])
            entry = stored.get(cell)
            if entry is None:
                continue
            if entry["response_sha256"] != unit["response_sha256"]:
                raise ValueError(
                    f"{question['qid']} on {unit['case']} slot {unit['slot']}: pass 1 "
                    f"response_sha256 is {entry['response_sha256']}, current unit is "
                    f"{unit['response_sha256']} — different responses require separate "
                    "label stores")
            if entry["label"] is True:
                keep.append(question)
        if keep:
            out.append({**unit, "questions": keep})
    return out


TEMPLATE_PATH = Path(__file__).resolve().parent / "gold" / "labeller.template.html"


def build_labeller(units: list[dict], pass_no: int = 1,
                   template: str | None = None) -> str:
    """One self-contained page carrying every unit for one pass.

    The page is a data-entry surface, not an evidence store: it exports plain JSON
    and `collect_export` does the validating and chaining in Python. A second chain
    implementation in JS would drift from this one, and `crypto.subtle` is not
    reliably available on `file://` anyway.

    A unit whose shape this function does not recognise is refused rather than
    passed through. Adding a field to a unit has to be a decision about what the
    labeller may see, not a diff that quietly widens it.
    """
    for unit in units:
        unknown = set(unit) - _UNIT_FIELDS
        if unknown:
            raise ValueError(
                f"unit {unit.get('unit_id')} carries field(s) the page does not know "
                f"how to blind: {sorted(unknown)}")
    page_units = [{k: unit[k] for k in _PAGE_FIELDS} for unit in units]
    # `<` is escaped so a response containing `</script>` cannot terminate the script
    # element. Zero of the 185 stored responses do today; the cost of being wrong
    # later is a page that silently stops working.
    data = json.dumps(page_units).replace("<", "\\u003c")
    html = template if template is not None else TEMPLATE_PATH.read_text()
    bid = build_id(units)
    return (html
            .replace("__GOLDKEY_STORAGE_KEY__", f"goldkey:{bid}:p{pass_no}")
            .replace("__GOLDKEY_BUILD_ID__", bid)
            .replace("__GOLDKEY_PASS__", str(int(pass_no)))
            .replace("__GOLDKEY_DATA__", data))


_DEFAULT_SWEEP = "evals/results/sweep-2026-08-04_102745_pid96394"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="goldkey",
        description="Human-verified answers to the questions the L4 judge is asked. "
                    "Makes zero model calls.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="write blind worksheets")
    p_extract.add_argument("--sweep", default=_DEFAULT_SWEEP)
    p_extract.add_argument("--out", default="evals/gold/worksheets")
    p_extract.add_argument("--decoy-cases", type=int, default=2)
    p_extract.add_argument("--max-units", type=int, default=0,
                           help="0 means every unit; units are leverage-ordered")

    p_build = sub.add_parser("build", help="write a self-contained labelling page")
    p_build.add_argument("--sweep", default=_DEFAULT_SWEEP)
    p_build.add_argument("--pass", dest="pass_no", type=int, choices=(1, 2), default=1)
    p_build.add_argument("--out", default=None)
    p_build.add_argument("--pass1", default="evals/gold/pass1.jsonl")
    p_build.add_argument("--decoy-cases", type=int, default=2)

    p_collect = sub.add_parser("collect", help="ingest a browser export")
    p_collect.add_argument("--export", required=True)
    p_collect.add_argument("--sweep", default=_DEFAULT_SWEEP)
    p_collect.add_argument("--pass", dest="pass_no", type=int, choices=(1, 2),
                           default=1)
    p_collect.add_argument("--pass1", default="evals/gold/pass1.jsonl")
    p_collect.add_argument("--pass2", default="evals/gold/pass2.jsonl")
    p_collect.add_argument("--decoy-cases", type=int, default=2)
    p_collect.add_argument("--labeler", default="robson")

    p_verify = sub.add_parser("verify", help="check a chain")
    p_verify.add_argument("--key", required=True)

    p_join = sub.add_parser("join", help="merge pass 1 and pass 2")
    p_join.add_argument("--pass1", default="evals/gold/pass1.jsonl")
    p_join.add_argument("--pass2", default="evals/gold/pass2.jsonl")
    p_join.add_argument("--corrections", default=None)
    p_join.add_argument("--sweep", default=_DEFAULT_SWEEP)
    p_join.add_argument("--out", default="evals/gold/key.jsonl")
    p_join.add_argument("--contested", default="evals/gold/contested.jsonl")

    p_score = sub.add_parser("score", help="score the judge against the key")
    p_score.add_argument("--key", default="evals/gold/key.jsonl")
    p_score.add_argument("--sweep", default=_DEFAULT_SWEEP)
    p_score.add_argument("--answers", default=None,
                         help="optional regrade answer-map JSON; leaves the sweep unchanged")
    p_score.add_argument("--config", default="evals/config.release.yaml",
                         help="judge config used to create --answers")
    p_score.add_argument("--out", default="evals/results/gold-judge-accuracy")

    args = parser.parse_args(argv)

    if args.command == "extract":
        units, manifest = worksheet_units(args.sweep, decoy_cases=args.decoy_cases)
        if args.max_units:
            units = units[:args.max_units]
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for unit in units:
            (out / f"{unit['unit_id']}.md").write_text(render_worksheet(unit))
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2,
                                                      sort_keys=True))
        print(f"{len(units)} worksheet(s) written to {out}")
        return 0

    if args.command == "build":
        units, manifest = worksheet_units(args.sweep, decoy_cases=args.decoy_cases)
        if args.pass_no == 2:
            units = pass2_units(units, args.pass1)
        out = Path(args.out or ("evals/gold/labeller"
                                + ("" if args.pass_no == 1 else "-pass2") + ".html"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_labeller(units, pass_no=args.pass_no))
        (out.parent / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True))
        cells = sum(len(u["questions"]) for u in units)
        print(f"pass {args.pass_no}: {len(units)} pages, {cells} cells -> {out} "
              f"({out.stat().st_size // 1024} KB)")
        print(f"open it with: open {out}")
        return 0

    if args.command == "collect":
        units, manifest = worksheet_units(args.sweep, decoy_cases=args.decoy_cases)
        if args.pass_no == 2:
            units = pass2_units(units, args.pass1)
        result = collect_export(json.loads(Path(args.export).read_text()),
                                units, manifest, args.pass1, args.pass2,
                                args.labeler, pass_no=args.pass_no)
        print(f"{result['written']} written, {result['amended']} amended, "
              f"{result['skipped']} already on file")
        for line in result["conflicts"]:
            print(f"CONFLICT (nothing written): {line}", file=sys.stderr)
        for line in result["rejected"]:
            print(f"REJECTED (nothing written): {line}", file=sys.stderr)
        return 1 if (result["conflicts"] or result["rejected"]) else 0

    if args.command == "verify":
        try:
            print(f"{verify_chain(args.key)} entries, chain intact")
            return 0
        except (ValueError, json.JSONDecodeError) as e:
            print(f"chain verification FAILED: {e}", file=sys.stderr)
            return 1

    if args.command == "join":
        join_paths = {
            "pass1": args.pass1, "pass2": args.pass2,
            "out": args.out, "contested": args.contested,
        }
        if args.corrections:
            join_paths["corrections"] = args.corrections
        _require_distinct_join_paths(**join_paths)
        gold, contested = join_passes(read_entries(args.pass1),
                                      read_entries(args.pass2))
        if args.corrections:
            gold = apply_label_corrections(
                gold, read_entries(args.corrections), args.sweep)
        write_chain(args.out, gold)
        write_chain(args.contested, contested)
        print(f"{len(gold)} gold, {len(contested)} contested")
        return 0

    if args.command == "score":
        answer_map = json.loads(Path(args.answers).read_text()) if args.answers else None
        answer_config = yaml.safe_load(Path(args.config).read_text()) or {} \
            if answer_map is not None else None
        summary = score_judge_against_gold(
            read_entries(args.key), args.sweep, answer_map=answer_map,
            answer_config=answer_config)
        Path(args.out + ".json").write_text(json.dumps(summary, indent=2,
                                                       sort_keys=True))
        Path(args.out + ".md").write_text(render_gold_md(summary))
        print(render_gold_md(summary))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
