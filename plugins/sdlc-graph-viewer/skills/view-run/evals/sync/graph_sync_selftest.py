#!/usr/bin/env python3
"""Can `graph_sync.py` actually detect drift?

`graph_sync.py` is the only thing standing between the viewer's copy of the transition table and the
spec it claims to render. It shipped with a guard-identifier extractor that read the guard cell
*after* the backticks had been stripped from it — so the pattern matched nothing, corpus-wide, and 26
of the 42 guards were compared against an empty set for as long as it existed. It printed `ok` every
time. Nothing was wrong with the check's intent; nothing was checking the check.

So: take the real viewer and the real spec, break one thing at a time in a temporary copy, and assert
the drift-checker goes red for the right reason. A checker that cannot fail is not evidence.

    python3 graph_sync_selftest.py

Exit 0 when every mutation is caught AND the untouched pair passes. Both halves matter — a checker
that fails on everything is as useless as one that passes on everything. No dependencies.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

HERE = paths.SYNC
SYNC = HERE / "graph_sync.py"
VIEWER = paths.VIEWER
DEFAULT_SPEC = paths.GRAPH_SPEC


def sync(viewer, spec, fixtures=None):
    cmd = [sys.executable, str(SYNC), "--viewer", str(viewer), "--spec-dir", str(spec)]
    if fixtures is not None:
        cmd += ["--fixtures", str(fixtures)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    red = [line.split()[1] for line in run.stdout.splitlines() if line.startswith("FAIL")]
    return run.returncode, red, run.stdout, run.stderr


# ── mutations on the VIEWER side — the page drifting away from the spec ────────────────────
def guard_drops_a_field(text):
    """The exact defect the dead regex could not see: the guard still reads plausibly, and tests a
    different thing than the spec says it does."""
    return text.replace("spec_path == null", "no design doc", 1)


def guard_drops_a_dotted_field(text):
    """A dotted field, dropped. It used to be `debug.return_to`, which the guards no longer carry:
    the DEBUG return guard stopped restating its own destination when twelve rows became one rule."""
    return text.replace("integration.branch", "the integration branch", 1)


def an_edge_is_retargeted(text):
    """The drift that looks most like working software — the arrow is still drawn."""
    return re.sub(r'("10",\s*\n\s*")GATE_A(")', r"\1E2E\2", text, count=1)


def a_bound_is_wrong(text):
    return re.sub(r'("TEST":\s*)3', r"\g<1>99", text, count=1)


def a_stop_is_invented(text):
    return re.sub(r'("HUMAN":\s*\{)', r'\1\n    "TEST": "approval-after",', text, count=1)


def the_page_fetches_something(text):
    return text.replace("<script>", '<script src="https://unpkg.com/react@18"></script>\n<script>', 1)


VIEWER_MUTATIONS = [
    ("a guard that tests a different field", guard_drops_a_field, "guard-identifiers-survive"),
    ("a guard that drops a dotted field", guard_drops_a_dotted_field, "guard-identifiers-survive"),
    ("an edge retargeted at another node", an_edge_is_retargeted, "edge-endpoints-match"),
    ("a retry bound the spec never declared", a_bound_is_wrong, "bounds-match"),
    ("a human stop the node contract does not declare", a_stop_is_invented, "human-stops-match"),
    ("the page loading a script at view time", the_page_fetches_something,
     "page-loads-nothing-external"),
]


# ── mutations on the SPEC side — the graph moving and the page not following ───────────────
def a_bound_moves_in_the_contract(nodes_md):
    """The bounds are now parsed from each node's `max attempts` row rather than from a table in
    `edges.md`, because that row IS the DEBUG round-trip's bound. Raising one there and not in the
    viewer is a board printing a counter against a limit that no longer exists.

    This replaced `§ Loop bounds renamed`, which stopped being a defect the moment the numbers
    stopped living under that heading — the old mutation went INERT, which the runner reports as a
    failure rather than a pass, and is why it was noticed."""
    return nodes_md.replace("| **max attempts** | **3**, then `BLOCKED` |",
                            "| **max attempts** | **5**, then `BLOCKED` |", 1)


def an_edge_is_retired(edges_md):
    """Eight edges were retired in one release. A viewer still offering one as a next step is telling
    a human the run can go somewhere it cannot."""
    return re.sub(r"^\|\s*11\s*\|.*$", "", edges_md, count=1, flags=re.M)


SPEC_MUTATIONS = [
    ("a bound raised in the node contract and not in the viewer", a_bound_moves_in_the_contract,
     "bounds-match", "nodes.md"),
    ("an edge retired from the spec and still drawn", an_edge_is_retired, "edge-ids-match",
     "edges.md"),
]


def main():
    if not paths.graph_files(DEFAULT_SPEC)["edges"].exists():
        print(f"skip: sdlc-graph not installed at {DEFAULT_SPEC} — nothing to drift from")
        return 0

    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        shutil.copytree(DEFAULT_SPEC, tmp / "spec")
        original = VIEWER.read_text(encoding="utf-8")

        code, red, out, err = sync(VIEWER, DEFAULT_SPEC)
        if code != 0 or err.strip():
            failures.append(f"the UNTOUCHED pair does not pass: {red}\n{out}{err}")
            print(f"FAIL  baseline — the shipped viewer must agree with the shipped spec, got {red}")
        else:
            print("ok    baseline: the shipped viewer agrees with the shipped spec")

        for label, mutate, expect in VIEWER_MUTATIONS:
            broken = tmp / "run-viewer.html"
            mutated = mutate(original)
            if mutated == original:
                failures.append(f"{label!r}: the mutation changed nothing — the CONTROL is broken, "
                                f"not the check. Fix the mutation before trusting this line.")
                print(f"FAIL  INERT MUTATION: {label} — it did not alter the viewer at all")
                continue
            broken.write_text(mutated, encoding="utf-8")
            _, red, _, _ = sync(broken, DEFAULT_SPEC)
            if expect in red:
                print(f"ok    caught: {label}")
            else:
                failures.append(f"{label!r} was NOT caught by {expect} (red: {red or 'nothing'})")
                print(f"FAIL  MISSED: {label} — expected {expect}, got {red or 'nothing'}")

        # The spec is now two files the viewer copies from: `edges.md` for the transitions and
        # `nodes.md` for the bounds — a node's `max attempts` IS its DEBUG round-trip's bound.
        for label, mutate, expect, which in SPEC_MUTATIONS:
            target = paths.graph_files(tmp / "spec")[pathlib.Path(which).stem]
            pristine = paths.graph_files(DEFAULT_SPEC)[pathlib.Path(which).stem].read_text(encoding="utf-8")
            mutated = mutate(pristine)
            if mutated == pristine:
                failures.append(f"{label!r}: the mutation changed nothing — the CONTROL is broken")
                print(f"FAIL  INERT MUTATION: {label} — it did not alter {which} at all")
                continue
            target.write_text(mutated, encoding="utf-8")
            _, red, _, _ = sync(VIEWER, tmp / "spec")
            if expect in red:
                print(f"ok    caught: {label}")
            else:
                failures.append(f"{label!r} was NOT caught by {expect} (red: {red or 'nothing'})")
                print(f"FAIL  MISSED: {label} — expected {expect}, got {red or 'nothing'}")
            target.write_text(pristine, encoding="utf-8")

        # ...and the corpus, which is neither the viewer nor the spec. The fixtures are what every
        # hand-check of this page runs against, so a fixture walking a retired edge shows a wrong
        # board to the one activity meant to catch a wrong board. That is not hypothetical: when
        # PR_FINAL_REVIEW was inserted between PR and CI, both fixtures reaching the tail kept
        # their `PR -> CI` hop, the board drew a bold visited curve straight past the new node, and
        # every suite stayed green — the checks compared viewer to spec, and nothing read the RUNS.
        stale = tmp / "fixtures"
        shutil.copytree(paths.FIXTURES, stale)
        hit = None
        for f in sorted(stale.glob("*.json")):
            s = json.loads(f.read_text(encoding="utf-8"))
            H = s.get("history") or []
            i = next((k for k, e in enumerate(H)
                      if isinstance(e, dict) and e.get("to") == "PR_FINAL_REVIEW"), None)
            if i is None:
                continue
            H[i]["to"] = H[i + 1]["to"]          # collapse the two hops back into the pre-#38 one
            del H[i + 1]
            f.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            hit = f.name
            break
        label = "a fixture still walking the edge a new node replaced"
        if hit is None:
            failures.append(f"{label!r}: no fixture reaches PR_FINAL_REVIEW — the CONTROL is broken, "
                            f"so this line proves nothing about the check")
            print(f"FAIL  INERT MUTATION: {label} — no fixture to make stale")
        else:
            _, red, _, _ = sync(VIEWER, DEFAULT_SPEC, fixtures=stale)
            if "fixtures-only-walk-edges-the-graph-still-has" in red:
                print(f"ok    caught: {label} ({hit})")
            else:
                failures.append(f"{label!r} was NOT caught (red: {red or 'nothing'})")
                print(f"FAIL  MISSED: {label} — got {red or 'nothing'}")

    total = len(VIEWER_MUTATIONS) + len(SPEC_MUTATIONS) + 2
    print(f"\n{total - len(failures)}/{total} drift-checker self-tests passed")
    if failures:
        print("\nA drift-checker that cannot go red is worse than none: it reads as a check that ran.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
