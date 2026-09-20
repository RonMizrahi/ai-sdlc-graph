#!/usr/bin/env python3
"""Does the trace hook snapshot exactly what it should, and nothing else?

`hooks/scripts/snapshot_state.py` fires on **every** Write/Edit in **every** project where this
plugin is installed. Two things therefore have to be true, and only one of them is the feature:

1. It snapshots a traced run's state file, numbered and named so `ls` reads as the run's story.
2. It does **nothing at all** in every other case — an untraced run, another project's file, a
   half-written file, a file that merely lives near a run directory.

The second is the larger surface and the one nobody would notice breaking, so most of the cases
below are negative controls. **A hook that snapshots everything would satisfy case 1 and fail
here**, which is the point: `plan()` is a pure function of (path, text, existing names, timestamp),
so every assertion is exact and instant — no subprocess, no filesystem, no run.

    python3 evals/hooks/snapshot_state_selftest.py

Exit 0 when every case holds.
"""
import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

HOOK = paths.PLUGIN / "hooks" / "scripts" / "snapshot_state.py"
TS = "20260808T091422Z"
RUN = "docs/graph-runs/add-rate-limiting-08-08-2026/state.json"


def load():
    spec = importlib.util.spec_from_file_location("snapshot_state", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def state(**over):
    s = {"run_id": "add-rate-limiting-08-08-2026", "schema_version": 5, "node": "E2E",
         "status": "RUNNING", "trace": True,
         "history": [{"from": "GATE_A", "to": "E2E", "guard": "no re-run recommended",
                      "milestone": 2, "observation": "6 files, clean"}]}
    s.update(over)
    return json.dumps(s)


# (label, path, text, existing names, expected filename or None, why this case exists)
# A case may carry a 7th element: the contents of the newest snapshot already in `history/`.
CASES = [
    ("a traced run's state file is snapshotted", RUN, state(), [],
     f"0001_m2_GATE_A-to-E2E_{TS}.json",
     "the feature: numbered, milestone-tagged, and the transition read out of history[-1]"),

    ("numbering continues past what is already there", RUN, state(),
     ["0001_x.json", "0002_x.json"], f"0003_m2_GATE_A-to-E2E_{TS}.json",
     "the sequence is read from the DIRECTORY, not from len(history) — a snapshot is also taken "
     "for writes that do not advance the trail, so counting transitions would leave gaps"),

    ("the first write of a run names itself", RUN, state(history=[], node="INTAKE"), [],
     f"0001_INTAKE-created_{TS}.json",
     "INTAKE creates the file before any transition exists; without this the very first state — "
     "the only one showing what the run was handed — is the one state never kept"),

    ("a transition with no milestone drops the segment", RUN,
     state(history=[{"from": "SPEC", "to": "PLAN", "guard": "approved", "milestone": None}]), [],
     f"0001_SPEC-to-PLAN_{TS}.json",
     "the shared tail has no milestone; `m None` in a filename is noise pretending to be data"),

    # ---- negative controls: everything below MUST return None -------------------------------
    ("trace off does nothing", RUN, state(trace=False), [], None,
     "trace is opt-in and defaults false. If this returns a name, every run everyone ever starts "
     "silently accumulates a full copy of its state at every transition"),

    ("trace absent does nothing", RUN, state(trace=None), [], None,
     "absent is off, not on — the same rule the graph applies to a missing field everywhere else. "
     "A run written by an older orchestrator has no `trace` key at all"),

    ("trace as a truthy STRING does nothing", RUN, state(trace="true"), [], None,
     "`is True`, not truthiness. `\"false\"` is a truthy string, so a loose check would turn "
     "tracing ON for a state file that says it is off"),

    ("another project's file does nothing", "src/app/service.ts", state(), [], None,
     "this hook fires on EVERY Write/Edit in every project the plugin is installed in. This is "
     "the case that runs thousands of times a day and must cost nothing"),

    ("a file merely inside a run directory does nothing",
     "docs/graph-runs/add-rate-limiting-08-08-2026/journals/milestone-1.jsonl", state(), [], None,
     "journals live here too, and have exactly one writer that is not this hook"),

    ("a state.json somewhere else does nothing", "docs/sdlc/state.json", state(), [], None,
     "the path must be <...>/graph-runs/<run-id>/state.json. A bare filename match would snapshot "
     "any state.json in any project — config files are commonly called that"),

    ("a half-written file does nothing", RUN, '{"run_id": "x", "trace": tr', [], None,
     "PostToolUse fires after the write, but a crashed or interrupted tool can still leave "
     "unparseable bytes. A traceback here would surface as a hook error on an otherwise fine run"),

    ("a JSON scalar does nothing", RUN, '"just a string"', [], None,
     "valid JSON, not a state file. `.get` on a str raises, and this hook may never raise"),

    ("an empty file does nothing", RUN, "", [], None,
     "the window between create and first write is real, and it is exactly when a hook fires"),

    ("a write identical to the newest snapshot does nothing", RUN, state(),
     ["0001_m2_GATE_A-to-E2E_x.json"], None,
     "any project with two graph plugins installed fires this hook TWICE for every write, because "
     "each ships its own copy. Without this the second copy of every state lands as its own "
     "numbered entry, and a sequence whose whole purpose is that it has no gaps becomes a "
     "sequence where every state appears twice",
     state()),

    ("a write that DIFFERS from the newest snapshot is kept", RUN, state(node="GATE_B"),
     ["0001_m2_GATE_A-to-E2E_x.json"], f"0002_m2_GATE_A-to-E2E_{TS}.json",
     "the dedupe is on content, not on existence — a progress tick that changes one field is a "
     "state the run passed through, and dropping it would leave the gap this hook exists to fill",
     state()),
]


def main():
    mod = load()
    failures = []

    for case in CASES:
        label, path, text, existing, want, why = case[:6]
        previous = case[6] if len(case) > 6 else None
        try:
            got = mod.plan(path, text, existing, TS, previous)
        except Exception as exc:                       # noqa: BLE001 — a raise IS the failure
            failures.append(label)
            print(f"FAIL  {label}\n      raised {type(exc).__name__}: {exc}\n      ({why})")
            continue
        if got == want:
            print(f"ok    {label}" + (f"  ->  {got}" if got else "  ->  (nothing)"))
        else:
            failures.append(label)
            print(f"FAIL  {label}\n      want {want!r}\n      got  {got!r}\n      ({why})")

    # `ls` and any glob sort lexicographically, and the sequence is only readable as an order if
    # 10 sorts after 9. Zero-padding to four is what makes that true, and it is the kind of detail
    # that is correct until someone "simplifies" the format string.
    names = [mod.snapshot_name(n, json.loads(state()), TS) for n in (1, 2, 9, 10, 100, 1000)]
    if names != sorted(names):
        failures.append("names sort in run order")
        print(f"FAIL  names do not sort in run order — the numbering stops being an order\n"
              f"      {names}")
    else:
        print("ok    names sort in run order at 1, 2, 9, 10, 100, 1000")

    # The hook's own contract: never anything but 0. It is telemetry, and telemetry that can stop a
    # run is worse than no telemetry — the monitor this plugin retired failed exactly that way.
    source = HOOK.read_text(encoding="utf-8")
    if "return 2" in source or "sys.exit(2)" in source:
        failures.append("the hook can exit non-zero")
        print("FAIL  the hook can exit non-zero — a lost snapshot must never be an interrupted run")
    else:
        print("ok    the hook has no non-zero exit path")

    total = len(CASES) + 2
    if failures:
        print(f"\nFAIL  {len(failures)} of {total} hook cases: {', '.join(failures)}")
        return 1
    print(f"\n{total}/{total} trace-hook cases hold "
          f"({sum(1 for c in CASES if c[4] is None)} of them negative controls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
