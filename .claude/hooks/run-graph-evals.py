#!/usr/bin/env python3
"""Claude Code PostToolUse hook: run the graph's eval suites after any change to a graph plugin.

Each graph is described across four spec files, a milestone agent, rendered HTML surfaces and a
viewer, all of which restate the same facts. **Drift between them is the dominant defect class** —
a guard fixed in `edges.md` and not in the viewer, a count that outlived the graph it described,
a cycle that says eight in one file and nine in another. Every one of those was found by hand,
late, after shipping.

So: any Edit/Write under a watched plugin re-runs the suites that could see that edit, and a
failure comes back as feedback on the very edit that caused it.

**Nothing with a suite is excluded.** An excluded suite is run by hand, which means run late:
the one plugin ever left out of this table went two releases with two of its runners wired into
nothing at all. The whole deterministic set costs 3.6 seconds against a 120s budget, so there is no
budget argument, and therefore no exclusion.

Two of this repo's three plugins carry suites and both are watched. The third,
`sdlc-graph-engineering-install`, ships a method rather than a graph, has no suite, and routes to
nothing — which the routing self-test asserts, so the absence stays deliberate rather than becoming
an oversight.

**Cross-plugin fan-out.** A plugin may not read above its own root, so the graph's own suite
cannot check the viewer that copies its transition table. The direction that IS legal is the
viewer reading the graph — which is why editing a graph plugin runs the *viewer's* suites too.
That fan-out is the only thing standing between `edges.md` and a viewer drawing a retired edge.

**A failure mid-change is expected and is the point.** Editing `nodes.md` before `SKILL.md`
leaves the spec inconsistent for one tool call; the hook says so, and the change is not finished
until it stops saying so. Treat it as the second half of the edit, not as an error.

Exit 0 = silent pass. Exit 2 = stderr is shown to Claude (PostToolUse: advisory, the edit stands).
"""
import json
import pathlib
import subprocess
import sys

TIMEOUT = 120

GRAPH = "plugins/sdlc-graph/skills/sdlc-graph/evals/run_all.py"
VIEWER = "plugins/sdlc-graph-viewer/skills/view-run/evals/run_all.py"

# Which plugin was edited -> which runners can see that edit. Matched on path SEGMENTS, so a
# directory whose name merely starts with `sdlc-graph` is never swallowed: an entry has to name a
# plugin exactly, and a plugin with no suite has no entry.
#
# `sdlc-graph-engineering-install` is that plugin. It is deliberately absent, not forgotten — it
# ships a method for building graphs, not a graph, and the routing self-test asserts that an edit
# to it runs nothing, so the absence cannot quietly become an oversight.
WATCHED = {
    ("plugins", "sdlc-graph"): [GRAPH, VIEWER],
    ("plugins", "sdlc-graph-viewer"): [VIEWER],
}


def runners_for(path):
    """Every runner that could see a change to `path`, in order, without duplicates."""
    parts = pathlib.PurePosixPath(path.replace("\\", "/")).parts
    found = []
    for i in range(len(parts)):
        for runner in WATCHED.get(parts[i:i + 2], []):
            if runner not in found:
                found.append(runner)
    return found


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # malformed payload -> don't interfere

    path = (data.get("tool_input") or {}).get("file_path") or ""
    runners = runners_for(path)
    if not runners:
        return 0

    root = pathlib.Path(data.get("cwd") or ".")
    failures = []
    for runner in runners:
        script = root / runner
        if not script.exists():
            continue
        try:
            run = subprocess.run([sys.executable, str(script), "--quiet"],
                                 capture_output=True, text=True, timeout=TIMEOUT, cwd=str(root))
        except Exception as exc:
            failures.append((runner, f"the suite could not run: {exc}"))
            continue
        if run.returncode != 0:
            failures.append((runner, (run.stdout + run.stderr).strip()))

    if not failures:
        return 0

    print("The graph evals now fail. This edit either introduced the drift or is half of a "
          "change that is not finished yet — either way, resolve it before moving on.\n",
          file=sys.stderr)
    for runner, output in failures:
        print(f"=== {runner}", file=sys.stderr)
        print(output, file=sys.stderr)
        print(file=sys.stderr)
    print("Re-run with:", file=sys.stderr)
    for runner, _ in failures:
        print(f"  python3 {runner}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
