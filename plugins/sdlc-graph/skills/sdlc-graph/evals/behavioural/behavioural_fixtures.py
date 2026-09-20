#!/usr/bin/env python3
"""The behavioural cases answer to a model; their FIXTURES answer to the spec.

    python3 behavioural_fixtures.py

`evals.json` is the one suite here that needs an agent, so nothing deterministic ever read it — and
its expected outputs quietly went stale against the graph they grade. Twice, in two days:

- **Phantom edges.** Three cases cited `18c`, `18d`, `26a` and `30a`, ids that have never existed.
  Three more cited `13 or 14` for `GATE_A`'s exits (they are 12 and 13), `edge 6` for a halt at
  `GATE_A` (edge 6 is `STRATEGY -> BRANCH`; the `GATE_A` halt edge was deleted), and `edge 18 ->
  BRANCH` (18 is `CONSOLIDATE -> GATE_B`; `GATE_B -> BRANCH` is 15). Every one dates from the
  release where `[start]` and `[end]` stopped being rows and the table renumbered.
- **Removed fields.** One case required `gate_a.applied` in the bundle and another required
  `journeys_state` — both deliberately deleted from `MILESTONE_BUNDLE`, each with a paragraph in
  `workflow-dispatch.md` saying so.

A stale expected output is worse than a missing one: it grades a correct answer as wrong, and the
cheapest way to make the suite green again is to teach the orchestrator the defect.

**Why these checks and not more.** Each is a defect that actually happened. The set deliberately
does not police prose, tone or coverage — a fixture is allowed to say anything the spec does not
contradict.

Every check carries its own planted control, run on every invocation rather than once by hand: a
check over a file nothing else reads is exactly the kind that can rot into always-green.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

paths.on_path()
import graph_walk  # noqa: E402  — the ONE parser of edges.md; nothing here re-reads the table


# --- what the fixtures are graded against -------------------------------------------------------

def edge_ids(edges_md):
    """Every legal edge id, as a fixture would cite it — `19·TEST` counts as `19`."""
    table = graph_walk.parse_edges(edges_md)
    return {eid.split("·")[0] for hops in table.values() for eid, _ in hops}


def _fences(md, langs):
    return re.findall(r"```(?:" + "|".join(langs) + r")\n(.*?)```", md, re.S)


def schema_vocabulary(dispatch_md, state_md):
    """The names **the two schemas the fixtures are written against** currently use.

    Scoped to the fenced schema blocks — `MILESTONE_BUNDLE`, the state file, and the `stopped`
    shape — rather than to the files. That scoping IS the check: both files also carry prose tables
    explaining what they *removed*, in which the removed names necessarily appear as quotations, and
    a file-wide read would therefore treat every deleted field as live. `gate_a.applied` is the
    standing case: the Workflow script still returns `applied`, so it sits legitimately in the `js`
    fence describing the script's result, and only the bundle dropped it.

    **Keys and identifier-shaped literals, never prose.** A whole-fence token scan reads the English
    inside example strings too — `"…4 simplifications + 2 security findings applied, 1 re-run"` in
    the `progress.headline` example is enough to make `applied` look like a live field, which is the
    one name this is here to catch.
    """
    blocks = [b for b in _fences(dispatch_md, ["jsonc", "json"]) if "milestone_id" in b]
    blocks += _fences(state_md, ["jsonc", "json"])
    text = "\n".join(blocks)
    keys = set(re.findall(r"\"?([A-Za-z_][A-Za-z0-9_]*)\"?\??\s*:", text))
    # Enum values, so a name that left the schema as a FIELD and came back as a VALUE still reads
    # as live: `paused` and `blocked` are now `stopped.kind` values, and a fixture saying
    # `stopped {kind: 'paused'}` is correct.
    literals = set(re.findall(r"['\"]([a-z][a-z0-9_]*)['\"]", text))
    return keys | literals


def _table_rows(md, heading_re):
    """The contiguous table immediately under a heading — blockquoted or not."""
    m = re.search(heading_re, md, re.M)
    if not m:
        return []
    rows, started = [], False
    for line in md[m.end():].splitlines():
        stripped = line.lstrip("> ").rstrip()
        if stripped.startswith("|"):
            started, _ = True, rows.append(stripped)
        elif started:
            break
    return rows


def removed_fields(dispatch_md, state_md):
    """Names the spec records as REMOVED, read from its own two removal tables.

    Read rather than listed, so a field deleted tomorrow starts policing the fixtures the moment its
    row is written — the alternative is a literal in this file, going stale the same way the fixtures
    did.

    Two scoping mistakes are already paid for. Splitting on the heading TEXT found `state.md`'s
    cross-reference to the section instead of the section, and parsed the field table; and matching a
    backticked cell anywhere in a row walked into the R0–R13 table further down `workflow-dispatch.md`
    and reported `of`, `was` and `passed` as deleted fields. So: the heading as a heading, the first
    cell as the first cell, and only the last segment of a dotted path — `trace[].result.journeys_state`
    is a rule about `journeys_state`, not about `trace`.
    """
    live = schema_vocabulary(dispatch_md, state_md)
    names = set()
    for md, heading in ((dispatch_md,
                         r"^>?\s*\*\*Three fields the bundle used to carry and does not"),
                        (state_md, r"^##+\s+What was removed, and why\s*$")):
        for row in _table_rows(md, heading):
            cell = row.split("|")[1] if row.count("|") > 1 else ""
            if not cell.strip() or set(cell.strip()) <= {"-", ":"}:
                continue
            for token in re.findall(r"`([^`]+)`", cell):
                segments = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", token)
                if segments and segments[-1] not in live:
                    names.add(segments[-1])
    return names


# --- the checks ---------------------------------------------------------------------------------

CITED_EDGE = re.compile(r"edges?\s+((?:\d+\s*(?:/|,|\s|or|and)\s*)*\d+)", re.I)
CITED_HOP = re.compile(r"edge\s+(\d+)\s*(?:->|to)\s*([A-Z][A-Z_]+)")
# Floors. A regex that stops matching is a check that stops checking, and this file is the only
# reader of evals.json — nothing else would notice it going quiet.
MIN_EDGE_CITATIONS = 6
MIN_HOP_CITATIONS = 3
MIN_REMOVED_FIELDS = 3


def check_edges_exist(cases, spec):
    """Every edge id a fixture cites is a row in `edges.md`."""
    ids = edge_ids(spec["edges"])
    found, bad = 0, []
    for case in cases:
        for field in ("prompt", "expected_output"):
            for m in CITED_EDGE.finditer(case[field]):
                for cited in re.findall(r"\d+", m.group(1)):
                    found += 1
                    if cited not in ids:
                        bad.append(f"case {case['id']} ({case['name']}) cites edge {cited}, "
                                   f"which is not a row in edges.md")
    if found < MIN_EDGE_CITATIONS:
        return (f"only {found} edge citations found in evals.json (expected at least "
                f"{MIN_EDGE_CITATIONS}) — the citation regex has stopped matching, so this check "
                f"is no longer reading anything")
    return "; ".join(sorted(set(bad)))


def check_edge_destinations(cases, spec):
    """`edge N -> NODE` names the node that edge actually goes to."""
    table = graph_walk.parse_edges(spec["edges"])
    dest = {}
    for (_frm, to), hops in table.items():
        for eid, _guard in hops:
            dest.setdefault(eid.split("·")[0], set()).add(to)
    found, bad = 0, []
    for case in cases:
        for field in ("prompt", "expected_output"):
            for eid, node in CITED_HOP.findall(case[field]):
                found += 1
                if eid in dest and node not in dest[eid]:
                    bad.append(f"case {case['id']} ({case['name']}) says edge {eid} -> {node}, "
                               f"but edge {eid} goes to {'/'.join(sorted(dest[eid]))}")
    if found < MIN_HOP_CITATIONS:
        return (f"only {found} `edge N -> NODE` citations found (expected at least "
                f"{MIN_HOP_CITATIONS}) — the destination regex has stopped matching")
    return "; ".join(sorted(set(bad)))


def check_no_removed_fields(cases, spec):
    """No fixture requires a field the spec's own removal tables say is gone."""
    gone = removed_fields(spec["dispatch"], spec["state"])
    if len(gone) < MIN_REMOVED_FIELDS:
        return (f"only {len(gone)} removed-field names parsed from the two removal tables "
                f"(expected at least {MIN_REMOVED_FIELDS}) — the table format changed and this "
                f"check is now policing an empty set")
    bad = []
    for case in cases:
        for field in ("prompt", "expected_output"):
            for name in sorted(gone):
                if re.search(rf"\b{re.escape(name)}\b", case[field]):
                    bad.append(f"case {case['id']} ({case['name']}) names `{name}`, which the spec "
                               f"records as removed — the fixture grades against a schema that no "
                               f"longer exists")
    return "; ".join(sorted(set(bad)))


CHECKS = [
    ("behavioural-cites-only-edges-that-exist",
     "seven expected outputs cited edge ids that do not exist — 18c, 18d, 26a, 30a from a table "
     "that never had them, and 13/14, 6, 18 from the renumbering when [start] and [end] stopped "
     "being rows. A fixture that grades against a phantom edge fails a correct orchestrator",
     check_edges_exist),
    ("behavioural-edge-citation-goes-where-it-says",
     "case 17 said `edge 18 -> BRANCH`. Edge 18 exists, so an existence check passes it — it is "
     "CONSOLIDATE -> GATE_B, and GATE_B -> BRANCH is edge 15. A live id pointing at the wrong node "
     "is the half of this drift that survives the first check",
     check_edge_destinations),
    ("behavioural-cites-no-field-the-schema-removed",
     "case 16 required `gate_a.applied` in the bundle and case 9 required `journeys_state`; both "
     "were deleted from MILESTONE_BUNDLE, each with a paragraph explaining why. An expected output "
     "demanding a deleted field teaches the milestone agent to invent one",
     check_no_removed_fields),
]


# --- controls: one planted defect per check, every run ------------------------------------------
#
# Not a separate runner. This suite reads one file that nothing else reads, so "it passed" is
# indistinguishable from "it read nothing" unless the proof rides along with the run.

def _clone(cases):
    return json.loads(json.dumps(cases))


def controls(cases, spec):
    """(check name, mutated cases, mutated spec, what the planted defect is)."""
    out = []

    bogus = _clone(cases)
    bogus[0]["expected_output"] += " Takes edge 47 to MERGE."
    out.append(("behavioural-cites-only-edges-that-exist", bogus, spec,
                "a citation of edge 47, which does not exist"))

    silent = _clone(cases)
    for case in silent:                      # every citation removed: the check must not go quiet
        case["prompt"] = case["prompt"].replace("edge", "hop")
        case["expected_output"] = case["expected_output"].replace("edge", "hop")
    out.append(("behavioural-cites-only-edges-that-exist", silent, spec,
                "no citations at all — the floor, so a dead regex cannot read as a pass"))

    wrong = _clone(cases)
    wrong[0]["expected_output"] += " So edge 15 -> CLOSE_OUT."
    out.append(("behavioural-edge-citation-goes-where-it-says", wrong, spec,
                "edge 15 pointed at CLOSE_OUT, which is edge 17's destination"))

    revived = _clone(cases)
    revived[0]["expected_output"] += " gate_a carries applied[] as usual."
    out.append(("behavioural-cites-no-field-the-schema-removed", revived, spec,
                "`applied`, deleted from the bundle, required again"))

    blinded = dict(spec)                     # the removal table reformatted out of recognition
    blinded["dispatch"] = spec["dispatch"].replace(
        "Three fields the bundle used to carry and does not", "Three fields, once")
    blinded["state"] = spec["state"].replace("What was removed, and why", "Removals")
    out.append(("behavioural-cites-no-field-the-schema-removed", cases, blinded,
                "both removal tables renamed — the check must report an empty set, not a pass"))

    return out


def main():
    spec = {"edges": paths.EDGES_MD.read_text(encoding="utf-8"),
            "state": paths.STATE_MD.read_text(encoding="utf-8"),
            "dispatch": paths.DISPATCH_MD.read_text(encoding="utf-8")}
    data = json.loads((paths.BEHAVIOURAL / "evals.json").read_text(encoding="utf-8"))
    cases = data["evals"]

    failed = []
    for name, _why, fn in CHECKS:
        problem = fn(cases, spec)
        print(f"{'FAIL' if problem else 'ok  '}  {name}")
        if problem:
            failed.append(name)
            for line in problem.split("; "):
                print(f"      {line}")

    dead = []
    for name, mutated, mspec, planted in controls(cases, spec):
        fn = next(f for n, _w, f in CHECKS if n == name)
        if not fn(mutated, mspec):
            dead.append(f"{name}: DID NOT FIRE on {planted}")
    for line in dead:
        print(f"DEAD  {line}")

    total = len(CHECKS)
    if failed or dead:
        print(f"FAIL  {len(failed)} of {total} checks red, {len(dead)} control(s) dead "
              f"over {len(cases)} behavioural cases")
        return 1
    print(f"ok    {total}/{total} checks passed over {len(cases)} behavioural cases, "
          f"{len(controls(cases, spec))} controls fired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
