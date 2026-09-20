#!/usr/bin/env python3
"""Does the snapshot the SKILL tells you to build survive hostile run data?

A snapshot is the copy that leaves the machine — attached to a ticket, mailed to a reviewer, archived
next to the run. It is also the only mode where run data is not merely rendered but **inlined into
the page's own source**, between `/*__STATE__*/` and `/*__END__*/`, inside a script block.

That makes it the one path where escaping at render time is not enough. HTML ends a script block at
the first literal closing-script tag anywhere inside it — JS string literals included — and
`json.dumps` escapes neither `<` nor `/`. So an observation reading

    fixed the parser </scr!pt><img src=x onerror=…>          (spelled around, for this file's sake)

truncated the script, stopped `boot()` from ever running, and handed the rest of the run to the HTML
parser as live markup. The page went blank, and the payload ran. The hostile fixture beside this file
did not catch it: its note says "drag it onto the viewer", which exercises `esc()` on the render path
and never touches the injector.

    python3 snapshot_safety.py

This runs **the injector as SKILL.md documents it**, extracted from the SKILL at check time rather
than copied here — a copy would let the documented command drift away from the checked one, which is
the whole family of bug this plugin keeps having. Exit 0 when a snapshot built from hostile data is
inert; exit 1 when it is not. No dependencies, no browser.
"""
import json
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

HERE = paths.SAFETY
SKILL = paths.SKILL_MD
VIEWER = paths.VIEWER
FIXTURES = paths.FIXTURES

CLOSE = "</" + "script>"          # never write this literally in a file the viewer might inline

# Payloads that must survive as text. Each is a real shape: a plan-authored observation, a milestone
# name typed by a human, a reason quoted from a tool's stderr.
HOSTILE = {
    "run_id": "hostile-snapshot",
    "plan_path": "docs/plans/p.md", "spec_path": None,
    "node": "GATE_A", "status": "RUNNING", "schema_version": 5,
    "cursor": {"milestone": 1, "milestones": [1]},
    "milestones": [{"id": 1, "name": "milestone agent " + CLOSE + "<img src=x onerror=w()>", "node": "GATE_A"}],
    "attempts": {"TEST:1": "<img src=x onerror=w()>"},
    "skipped_gates": [{"node": "E2E", "reason": CLOSE + "<img src=x onerror=w()>", "at_milestone": 1}],
    "history": [{"from": "BRANCH", "to": "IMPLEMENT", "guard": "branch created", "milestone": 1,
                 "observation": "fixed the parser " + CLOSE + "<img src=x onerror=w()>",
                 "verified": "3 commits confirmed"}],
}


def documented_injector():
    """The python heredoc out of SKILL.md's snapshot section, as source."""
    blocks = re.findall(r"```bash\n(.*?)```", SKILL.read_text(encoding="utf-8"), re.S)
    for b in blocks:
        m = re.search(r"<<'PY'\n(.*?)\nPY\b", b, re.S)
        if m and "__STATE__" in m.group(1):
            return m.group(1)
    raise SystemExit("SKILL.md no longer contains the snapshot injector — this check reads the "
                     "documented command, and it could not find one")


def run_injector(src, source, state_path, out_path, where):
    """Execute the injector source as written. It opens with `import sys`, which rebinds any stub —
    so the arguments have to arrive the way the real command delivers them: on sys.argv."""
    saved = sys.argv
    sys.argv = ["injector", str(source), str(state_path), str(out_path)]
    try:
        exec(compile(src, where, "exec"), {"__name__": "__main__", "print": lambda *a, **k: None})
    finally:
        sys.argv = saved
    return pathlib.Path(out_path).read_text(encoding="utf-8")


def build(source, state_path, out_path):
    return run_injector(documented_injector(), source, state_path, out_path, "SKILL.md:injector")


def problems_with(page, label):
    bad = []
    tags = page.count(CLOSE)
    if tags != 1:
        bad.append(f"{label}: the page has {tags} closing-script tags — run data closed the block, "
                   f"so boot() never runs and everything after the payload is live markup")
    # the raw payload must not appear un-escaped anywhere in the source
    if "<img src=x" in page:
        bad.append(f"{label}: an unescaped `<img` from the run reached the page source")
    return bad


def main():
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        state = tmp / "hostile-state.json"
        state.write_text(json.dumps(HOSTILE), encoding="utf-8")

        page = build(VIEWER, state, tmp / "view.html")
        bad = problems_with(page, "hostile state")
        failures += bad
        print(("FAIL  " + bad[0]) if bad else "ok    a snapshot of hostile run data is inert")

        # Every shipped fixture, through the same injector. These are the pages people actually build.
        for f in sorted(FIXTURES.glob("*-state.json")):
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f"skip  {f.name} — deliberately corrupt; the injector is meant to refuse it")
                continue
            bad = problems_with(build(VIEWER, f, tmp / "view.html"), f.name)
            failures += bad
            print(("FAIL  " + bad[0]) if bad else f"ok    {f.name}")

        # THE CONTROL. Strip the escaping line out of the documented injector and assert the same
        # fixture then breaks — otherwise this file proves only that today's data happens to be tame.
        stripped = re.sub(r"^data = data\.replace\(.*$", "", documented_injector(), flags=re.M)
        if stripped == documented_injector():
            failures.append("the control could not find the escaping line to remove — if the "
                            "injector was rewritten, rewrite this control with it")
            print("FAIL  control: nothing was stripped, so the control asserts nothing")
        elif problems_with(run_injector(stripped, VIEWER, state, tmp / "ctl.html", "control"), "control"):
            print("ok    control: without the escaping line the same data DOES break the page")
        else:
            failures.append("the control did not break — this check cannot fail and proves nothing")
            print("FAIL  control: removing the escaping changed nothing. The check is inert.")

    print(f"\n{'snapshot injection: ' + str(len(failures)) + ' problem(s)' if failures else 'snapshot injection: clean'}")
    if failures:
        print("\nRun data is DATA. In snapshot mode it is inlined into the page's own source, so it\n"
              "must be escaped by the INJECTOR — esc() at render time is too late to help.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
