#!/usr/bin/env python3
"""
Runs every deterministic eval suite for the viewer and reports one verdict.

    python3 run_all.py           # full output
    python3 run_all.py --quiet   # only the failures, and the one-line summary

The viewer carries a COPY of the graph's transition table, and the graph plugin's own suite cannot
reach it — a plugin may not read above its own root. So the drift checks live here, and until now
there was nothing to run them all at once: three scripts, each invoked by hand, in a repo whose
dominant defect class is "a guard fixed in `edges.md` and not in the surface that renders it".

`sync_graph.py` is deliberately NOT in this list. It is the WRITER — it regenerates the viewer's
`GRAPH` block from the spec — and `graph_sync.py` already fails on exactly the state a stale
generated block produces. Running the generator as a check would be a second opinion about the
same fact, and a checker that can rewrite the thing it checks is not a checker.

When the graph plugin is absent (a standalone viewer install) `graph_sync.py` exits 0 and says so,
so this runner stays green rather than failing on a legitimate install.
"""
import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "lib"))
import paths  # noqa: E402

HERE = paths.EVALS

SUITES = [
    ("sync/graph_sync.py", "the viewer's copy of the graph still matches the spec it renders"),
    ("sync/graph_sync_selftest.py", "...and that drift checker can actually go red"),
    ("safety/snapshot_safety.py", "a snapshot of hostile run data renders as text, not as markup"),
    ("server/server_boot.py", "the server actually serves its viewer page over HTTP"),
    ("viewer/agent_panel.py", "the subagent panel escapes its journal text, orders it by spawn, "
                             "and admits what it cut"),
    ("viewer/node_labels.py", "every surface shows a node's display name, and every lookup still "
                              "keys on its id"),
    ("viewer/milestone_status.py", "the milestone status pill tells a running milestone apart "
     "from one that never started, and the fixture corpus contains that shape"),
    ("viewer/guard_predicates.py", "the guard predicates that dim next-step buttons still name "
                                   "live edges, and still agree with the guards they read"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="print only failures and the summary")
    args = ap.parse_args()

    failed = []
    for script, what in SUITES:
        run = subprocess.run([sys.executable, str(HERE / script)], capture_output=True, text=True)
        ok = run.returncode == 0
        if not ok:
            failed.append(script)
        if not args.quiet:
            print(f"── {script} — {what}")
            print(run.stdout.rstrip() or run.stderr.rstrip())
            print()
        elif not ok:
            print(f"── {script} FAILED")
            print((run.stdout + run.stderr).rstrip()[-2000:])
            print()

    if failed:
        print(f"FAIL  {len(failed)} of {len(SUITES)} viewer eval suites: {', '.join(failed)}")
        return 1
    print(f"ok    {len(SUITES)}/{len(SUITES)} viewer eval suites pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
