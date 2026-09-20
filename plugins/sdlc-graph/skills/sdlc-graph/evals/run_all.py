#!/usr/bin/env python3
"""
Runs every deterministic eval suite for the graph and reports one verdict.

    python3 run_all.py           # full output
    python3 run_all.py --quiet   # only the failures, and the one-line summary

Exit 0 only when the spec is self-consistent, every scripted walk is legal, the walk set covers
every node and every edge, and every check in here can still be made to fail.

**Everything deterministic goes in this list.** Two suites sat outside it for a release —
`gate-a.harness.mjs` because it is the only `.mjs` in a directory of Python, and
`run_scenario.py --self-test` because the same file also has modes that need an agent. Neither
omission was a budget decision: together they cost 0.10s against the 3.5s the list already spent,
and the hook that runs this allows 130s. `every-deterministic-suite-is-wired-into-run-all` in
`spec_consistency.py` is what now notices a suite that never got added.

The behavioural set (`evals.json`), `run_scenario.py --setup/--check` and `real/` are NOT here:
each needs a model, and this list is the part that answers in seconds with no agent.

The viewer is a separate plugin and cannot be reached from inside this one — it has its own
`run_all.py`. The repo's PostToolUse hook runs both, because editing `edges.md` here is exactly
what makes the viewer's copy stale.
"""
import argparse
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import paths  # noqa: E402

HERE = paths.EVALS

# (script relative to evals/, argv, what it asks)
SUITES = [
    ("spec/spec_consistency.py", [],
     "the spec files agree with each other, and with the milestone agent"),
    ("spec/spec_controls.py", [], "the spec checks can actually fail — one planted defect at a time"),
    ("walks/graph_walk.py", [], "every scripted walk is legal, and the set covers the whole graph"),
    ("audit/audit_selftest.py", [],
     "the offline auditor can actually fail — one planted defect at a time"),
    ("walks/audit_walks.py", [],
     "every legal walk still holds up as a FINISHED run, audited from the file"),
    ("runs/run_scenario.py", ["--self-test"],
     "every run-eval scenario is satisfiable AND breakable — no agent needed"),
    ("hooks/snapshot_state_selftest.py", [],
     "the trace hook snapshots a traced run — and nothing else, in every other project"),
    ("behavioural/behavioural_fixtures.py", [],
     "the behavioural cases grade against edges and fields that still exist"),
]

# The only executable code the graph ships is `gate-a.workflow.js`, and its 81-assertion harness sat
# unrun for a release — every other suite here is Python, so a `.mjs` file simply never got added to
# the list. A test nothing runs is worth exactly what a check that cannot fail is worth.
JS_SUITES = [
    ("gate-a.harness.mjs", "gate-a.workflow.js under a real runtime — grouping, args, dead agents",
     ["gate-a.workflow.js"]),
]


def run_js(script, argv):
    return subprocess.run(["node", str(paths.WORKFLOWS / script),
                           *[str(paths.WORKFLOWS / a) for a in argv]],
                          capture_output=True, text=True)


def do_list():
    """Print what each suite asks and how much of it there currently is.

    This exists so no prose surface has to restate it. `evals/README.md`, `docs/TESTING.md` and
    `docs/artifacts/index.html` each carried a table of suites and their counts, and all three drifted: 41
    checks against 49, 7 against 8, 63 assertions against 81, and one that named a suite which had
    never been added. There was a check policing the first of those — and it read only `README.md`,
    so it caught none of the other two. Deleting the copies deletes the drift and the check.
    """
    print(f"{'suite':34} {'now':>10}  asks")
    for script, argv, what in SUITES:
        run = subprocess.run([sys.executable, str(HERE / script), *argv],
                             capture_output=True, text=True)
        tail = [l for l in run.stdout.splitlines() if l.strip()]
        count = next((l.strip() for l in reversed(tail)
                      if re.match(r"^\s*(ok\s+)?\d+/\d+", l) or "passed" in l or "fired" in l), "?")
        print(f"{(script + ' ' + ' '.join(argv)).strip():34} {count[:10]:>10}  {what}")
    for script, what, _ in JS_SUITES:
        print(f"{script:34} {'81 assert':>10}  {what}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="print only failures and the summary")
    ap.add_argument("--list", action="store_true",
                    help="print the suite table, counts read from the suites themselves")
    args = ap.parse_args()

    if args.list:
        return do_list()

    failed = []
    for script, argv, what in SUITES:
        run = subprocess.run([sys.executable, str(HERE / script), *argv],
                             capture_output=True, text=True)
        ok = run.returncode == 0
        if not ok:
            failed.append(script)
        if not args.quiet:
            print(f"── {script} {' '.join(argv)} — {what}")
            print(run.stdout.rstrip() or run.stderr.rstrip())
            print()
        elif not ok:
            print(f"── {script} FAILED")
            for line in (run.stdout + run.stderr).splitlines():
                if line.startswith(("FAIL", "DEAD", "      ")) or "/" in line and "passed" in line:
                    print(line)
            print()

    for script, what, argv in JS_SUITES:
        run = run_js(script, argv)
        ok = run.returncode == 0
        if not ok:
            failed.append(script)
        if not args.quiet:
            print(f"── {script} — {what}")
            print((run.stdout or run.stderr).rstrip().splitlines()[-1] if (run.stdout or run.stderr)
                  else "(no output)")
            print()
        elif not ok:
            print(f"── {script} FAILED")
            print((run.stdout + run.stderr).rstrip()[-2000:])
            print()

    total = len(SUITES) + len(JS_SUITES)
    if failed:
        print(f"FAIL  {len(failed)} of {total} eval suites: {', '.join(failed)}")
        return 1
    print(f"ok    {total}/{total} eval suites pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
