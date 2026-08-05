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
import hashlib
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import regrade  # noqa: E402
import runner  # noqa: E402

SLOTS = regrade.SLOTS_PER_CASE
_DIMENSIONS = ("pedagogy", "safety", "actionable")


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
                "failure_reason", "prev", "digest"}
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
    reasons = {(e["case"], e["slot"], e["qid"]): (e.get("failure_reason") or "").strip()
               for e in pass2}
    gold, contested = [], []
    for entry in pass1:
        key = (entry["case"], entry["slot"], entry["qid"])
        if entry["label"] is False:
            gold.append(entry)
            continue
        if key not in reasons:
            raise ValueError(
                f"{entry['qid']} on {entry['case']} slot {entry['slot']} was labelled "
                "yes but has no inversion-pass entry — a half-labelled cell must not "
                "enter the key")
        reason = reasons[key]
        if reason.lower() in _NO_REASON:
            gold.append(entry)
        else:
            contested.append({**entry, "failure_reason": reason})
    return gold, contested


def score_judge_against_gold(gold: list[dict], sweep_dir, thresholds: dict | None = None,
                             slots: int = SLOTS) -> dict:
    """How often the judge's recorded answer matches a blind human read.

    Scored per criterion, and only when every slot carries a gold label. A
    criterion labelled in 3 of 5 slots reports `incomplete` and contributes
    nothing — scoring it over the slots that happen to be done is the
    never-shrink-the-denominator failure, and it would let a labeller stop the
    moment the numbers looked right.

    `gate_gold` is the criterion's gate result computed from the human labels
    through `runner._meets` and the SAME floor the release gate uses. It is
    diagnostic only: this function is never called by `case_gate`, and a gold
    label may not be substituted for a judge answer in a verdict.
    """
    floor = runner._threshold(thresholds, 4, "question_rate")
    ledger = json.loads((Path(sweep_dir) / "ledger.json").read_text())

    by_criterion: dict[tuple, list[dict]] = {}
    for entry in gold:
        by_criterion.setdefault((entry["case"], entry["qid"]), []).append(entry)

    rows, defects = [], []
    for (case_name, qid), entries in sorted(by_criterion.items()):
        case = runner.load_case(ledger["cases"][case_name]["path"])
        judge = judge_answers(sweep_dir, case_name, case, qid, slots)
        human = {e["slot"]: e["label"] for e in entries}
        defects.extend({"case": case_name, "qid": qid, "slot": e["slot"],
                        "note": e.get("note", "")}
                       for e in entries if e.get("suspect_case_defect"))

        shared = sorted(set(judge) & set(human))
        fp = sum(1 for s in shared if judge[s] and not human[s])
        fn = sum(1 for s in shared if not judge[s] and human[s])
        complete = len(human) == slots and len(judge) == slots
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
    lines = ["# Judge accuracy against the gold key", "",
             f"- criteria scored: {t['criteria']} ({t['incomplete']} incomplete)",
             f"- gold cells: {t['cells']}",
             f"- judge said yes where the gold label says no (false positive): "
             f"{t['false_positive']}",
             f"- judge said no where the gold label says yes (false negative): "
             f"{t['false_negative']}",
             f"- criteria where the judge and the gold labels disagree about the "
             f"gate result: {t['gate_disagreements']}", "",
             "A criterion labelled in fewer than every slot is reported incomplete "
             "and scored on nothing.", "",
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
                  "Recorded with evidence, acting on nothing. No question is "
                  "reworded, reordered or demoted by this file.", ""]
        for d in summary["suspected_case_defects"]:
            lines.append(f"- `{d['qid']}` on {d['case']} slot {d['slot']} — {d['note']}")
    return "\n".join(lines) + "\n"


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

    p_verify = sub.add_parser("verify", help="check a chain")
    p_verify.add_argument("--key", required=True)

    p_join = sub.add_parser("join", help="merge pass 1 and pass 2")
    p_join.add_argument("--pass1", default="evals/gold/pass1.jsonl")
    p_join.add_argument("--pass2", default="evals/gold/pass2.jsonl")
    p_join.add_argument("--out", default="evals/gold/key.jsonl")
    p_join.add_argument("--contested", default="evals/gold/contested.jsonl")

    p_score = sub.add_parser("score", help="score the judge against the key")
    p_score.add_argument("--key", default="evals/gold/key.jsonl")
    p_score.add_argument("--sweep", default=_DEFAULT_SWEEP)
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

    if args.command == "verify":
        try:
            print(f"{verify_chain(args.key)} entries, chain intact")
            return 0
        except (ValueError, json.JSONDecodeError) as e:
            print(f"chain verification FAILED: {e}", file=sys.stderr)
            return 1

    if args.command == "join":
        gold, contested = join_passes(read_entries(args.pass1),
                                      read_entries(args.pass2))
        Path(args.out).write_text(
            "".join(json.dumps(e, sort_keys=True) + "\n" for e in gold))
        Path(args.contested).write_text(
            "".join(json.dumps(e, sort_keys=True) + "\n" for e in contested))
        print(f"{len(gold)} gold, {len(contested)} contested")
        return 0

    if args.command == "score":
        summary = score_judge_against_gold(read_entries(args.key), args.sweep)
        Path(args.out + ".json").write_text(json.dumps(summary, indent=2,
                                                       sort_keys=True))
        Path(args.out + ".md").write_text(render_gold_md(summary))
        print(render_gold_md(summary))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
