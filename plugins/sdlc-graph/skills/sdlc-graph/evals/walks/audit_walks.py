#!/usr/bin/env python3
"""Audit the state file every legal walk fixture would have left behind.

`graph_walk.py` proves a run is legal **while it is walked** — the right edge, the right guard, the
stop where one was declared. `audit_run.py` asks a different question of the **wreckage afterwards**:
does the trail hold up to someone who was not there? Between them sits a gap, and this closes it for
free: every legal fixture already describes a complete run, so replaying it to its end state gives
the auditor a corpus of real trails at no authoring cost.

    python3 walks/audit_walks.py

Exit 0 when every legal walk's final state audits clean. The negative controls are skipped — they
are *supposed* to be broken, and `graph_walk.py` already asserts that they are rejected.

This is where an auditor check that is too strict shows up first: it will go red across many
fixtures at once, which is the signal that the CHECK is wrong rather than the runs.
"""
import json
import pathlib
import shutil
import subprocess
import sys

# The fixtures name an EDGE; the guard text is read from `edges.md` here. That is what makes
# `guards-verbatim` in audit_run.py meaningful rather than circular: the trail being audited quotes
# the authoritative file because it was BUILT from it, so a paraphrase can only come from a mutation
# — which is precisely what `paraphrase_a_guard` plants.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402
sys.path.insert(0, str(paths.WALKS))
import graph_walk as _gw

_EDGES = _gw.parse_edges(
    paths.EDGES_MD
    .read_text(encoding="utf-8"))


def guard_of(step):
    """The declared guard for a step's edge, or "" for a halt (no numbered edge declares it)."""
    for eid, guard in _EDGES.get((step["from"], step["to"]), []):
        if eid == step.get("edge"):
            return guard
    return ""


HERE = paths.WALKS
WALKS = paths.FIXTURES
AUDIT = paths.AUDIT / "audit_run.py"


def apply_set(state, path, value):
    node, parts = state, path.split(".")
    for part in parts[:-1]:
        node = node[int(part)] if part.isdigit() and isinstance(node, list) else node.setdefault(part, {})
    last = parts[-1]
    if last.isdigit() and isinstance(node, list):
        idx = int(last)
        node.append(value) if idx == len(node) else node.__setitem__(idx, value)
    else:
        node[last] = value


def replay(spec):
    """The state file this walk would have left on disk, transition by transition."""
    state = json.loads(json.dumps(spec["initial_state"]))
    TERMINAL = {"DONE", "BLOCKED", "HANDOFF"}
    for step in spec["steps"]:
        for key, value in (step.get("set") or {}).items():
            apply_set(state, key, value)
        state.setdefault("skipped_gates", []).extend(step.get("skipped_gates", []))
        stops = step.get("stops") or []
        if step.get("halt"):
            state["stopped"] = {"kind": "blocked", "at_node": step["from"],
                                "guards_tested": step["halt"].get("guards_tested", []),
                                "tried": step["halt"].get("tried", []),
                                "at_milestone": step.get("milestone")}
        elif stops:
            state["stopped"] = {"kind": "handoff" if step["to"] == "HANDOFF" else "paused",
                                "reason": stops[0].get("answer"), "at_node": step["from"]}
        else:
            state["stopped"] = None
        if step["to"] in TERMINAL:
            state["status"] = step["to"]
            if step["to"] == "DONE":
                state["stopped"] = None     # DONE is not a pause
        else:
            state["node"] = step["to"]
        state.setdefault("history", []).append({
            "from": step["from"], "to": step["to"], "guard": guard_of(step),
            "milestone": step.get("milestone"), "observation": step["observation"],
            "evidence": step.get("evidence"), "verified": (step.get("agent") or {}).get("verified")})
    return state


def journals(spec, state, into):
    """Write out the per-milestone journals the fixture already carries.

    `journal-agrees-with-history` is the offline twin of R13 — the check that catches a bundle
    quietly dropping a retry — and it reported **NOT RUN on every walk**, because the journals
    only ever existed inside the fixture's `agent` blocks and nothing wrote them to disk beside
    the state file. This suite printed "9/9 legal walks audit clean" over 22% of its checks
    never running, under a header that says *a check that did not run is not a check that
    passed*. The data was there the whole time.
    """
    lines = {}
    for step in spec["steps"]:
        for entry in ((step.get("agent") or {}).get("journal") or []):
            lines.setdefault(entry.get("milestone", step.get("milestone")), []).append(entry)
    for mid, entries in lines.items():
        (into / "journals").mkdir(exist_ok=True)
        (into / "journals" / f"milestone-{mid}.jsonl").write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return bool(lines)


def main():
    tmp_dir = HERE / ".audit-walks"
    tmp = tmp_dir / "state.json"
    fixtures, failures, unjournalled = [], [], []
    try:
        for path in sorted(WALKS.glob("*.json")):
            spec = json.loads(path.read_text(encoding="utf-8"))
            if spec.get("expect", {}).get("rejected"):
                print(f"skip  {path.name} — a negative control is meant to be broken")
                continue
            fixtures.append(path.name)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            tmp_dir.mkdir(parents=True)
            state = replay(spec)
            tmp.write_text(json.dumps(state), encoding="utf-8")
            if not journals(spec, state, tmp_dir):
                unjournalled.append(path.name)
            run = subprocess.run([sys.executable, str(AUDIT), str(tmp)], capture_output=True, text=True)
            red = [l.split()[1] for l in run.stdout.splitlines() if l.startswith("FAIL")]
            skipped = [l.split(None, 2)[2] for l in run.stdout.splitlines() if l.startswith("NOT RUN")]
            if run.returncode == 0:
                print(f"ok    {path.name}"
                      + (f"  ({len(skipped)} not run)" if skipped else ""))
            else:
                failures.append((path.name, red))
                print(f"FAIL  {path.name} — {', '.join(red)}")
                for line in run.stdout.splitlines():
                    if line.startswith("        "):
                        print(f"      {line.strip()[:160]}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{len(fixtures) - len(failures)}/{len(fixtures)} legal walks audit clean as finished runs")
    if unjournalled:
        # Loud, and non-fatal: a fixture may legitimately describe a run with no delegated
        # milestones (strategy D parks before BRANCH). Silence would be the defect.
        print(f"      no journal in {len(unjournalled)}: {', '.join(unjournalled)} — "
              f"journal-agrees-with-history is NOT RUN on those, which is not a pass")
    if failures:
        print("A trail that is legal to walk but does not survive an audit is the gap between "
              "'the run followed the graph' and 'the run can be shown to have done so'.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
