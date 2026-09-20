#!/usr/bin/env python3
"""Does `run-graph-evals.py` actually fire on the plugins it claims to watch?

The hook is the one piece of this system no plugin's eval suite can reach: it lives above every
plugin root, and the rule is that a plugin references nothing above its own. So a plugin's suite
can check that `run_all.py` invokes every suite on disk
(`every-deterministic-suite-is-wired-into-run-all`) and cannot check whether anything invokes
`run_all.py`. That gap once let a plugin ship a whole release with nothing running its evals — the
exclusion was written down, agreed, and then behaved exactly like an oversight.

This closes it from the only side that can see both: the hook's own directory.

    python3 .claude/hooks/run-graph-evals.selftest.py

`runners_for()` is a pure function over a path, so the assertions below are exact and instant —
no subprocess, no repo state, no eval suite actually run. Exit 0 when every case holds.

Each case is also a NEGATIVE control by construction: the cases assert both that a runner IS
selected and that the ones which must not be are absent. A routing table that returned every
runner for every path would satisfy "the graph is watched" and fail here — the method plugin has
no suite, and running somebody else's checks over its edits would report drift that does not
exist.
"""
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent

spec = importlib.util.spec_from_file_location("hook", HERE / "run-graph-evals.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

GRAPH = "plugins/sdlc-graph/skills/sdlc-graph/evals/run_all.py"
VIEWER = "plugins/sdlc-graph-viewer/skills/view-run/evals/run_all.py"

# (an edited file, exactly the runners that must fire for it, why this case exists)
CASES = [
    ("plugins/sdlc-graph/skills/sdlc-graph/graph/edges.md", [GRAPH, VIEWER],
     "the graph fires its own suite AND the viewer's — a guard edited here is what makes the "
     "viewer's copy of the transition table stale, and the viewer is the only side allowed to look"),
    ("plugins/sdlc-graph/.claude-plugin/plugin.json", [GRAPH, VIEWER],
     "the plugin root counts, not just the skill directory"),
    ("plugins/sdlc-graph-viewer/skills/view-run/viewer/run-viewer.html", [VIEWER],
     "editing the viewer fires the viewer's suite and never the graph's — the graph plugin cannot "
     "legally read the viewer, so its suite would say nothing about this edit"),
    ("plugins/sdlc-graph-viewer/README.md", [VIEWER],
     "the plugin root counts for the viewer too, not just its skill directory"),
    ("plugins/sdlc-graph-engineering-install/skills/sdlc-graph-engineering-install/SKILL.md", [],
     "the method plugin ships no suite, and the hook must not invent one for it by matching the "
     "`sdlc-graph` prefix — this is the negative control that a table returning everything for "
     "everything would fail"),
    ("README.md", [], "a repo-root file fires nothing"),
    ("", [], "an empty path (a tool call with no file_path) fires nothing"),
    ("/Users/x/git/sdlc-graph-engineering/plugins/sdlc-graph/skills/sdlc-graph/graph/nodes.md",
     [GRAPH, VIEWER],
     "an ABSOLUTE path routes the same as a relative one — the hook is handed whatever the tool "
     "call carried, and Edit reports absolute paths"),
]


def main():
    bad_routes, missing = 0, 0

    for path, want, why in CASES:
        got = hook.runners_for(path)
        if got == want:
            print(f"ok    {path or '(empty)'} -> {len(got)} runner(s)")
        else:
            bad_routes += 1
            print(f"FAIL  {path or '(empty)'}\n      want {want}\n      got  {got}\n      ({why})")

    # A runner named in the table but absent from disk is a hook that silently skips it: the hook
    # does `if not script.exists(): continue`, which is correct for a partial checkout and wrong
    # for a typo. Nothing else would tell the difference.
    for key, runners in hook.WATCHED.items():
        for runner in runners:
            if not (REPO / runner).exists():
                missing += 1
                print(f"FAIL  WATCHED{list(key)} names {runner}, which does not exist — the hook "
                      f"skips a missing runner in silence")

    print(f"\n{len(CASES) - bad_routes}/{len(CASES)} routing cases hold"
          + (f", {missing} runner(s) named but missing" if missing else ""))
    return 1 if (bad_routes or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
