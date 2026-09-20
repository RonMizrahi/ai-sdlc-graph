#!/usr/bin/env python3
"""The milestone status pill: does it know the difference between "not started" and "running"?

The pill on each milestone row was derived from `history[]` alone:

    m.delivered ? 'delivered' : nlabel(last history entry for this milestone) || 'not started'

That is wrong for the one case strategy C exists to create. `history[]` is deliberately EMPTY for a
milestone whose agent is still running: the graph writes nothing until the milestone's bundle passes
the return gate (`graph/state.md` § *Provisional is not recorded* — "a run may therefore show
`progress.at_node: GATE_B` while `history[]` still ends at `BRANCH → IMPLEMENT`. That gap is the
design, not a lag to be closed"). So a milestone with a live agent, a worktree, commits landing and a
progress headline rendering two lines below the pill was labelled **NOT STARTED** for its entire life,
and only stopped being "not started" once it was entirely finished.

Observed in a real run: two concurrent milestones under strategy C, both mid-flight, both reading
NOT STARTED while the same card printed their `BRANCH` progress lines. The card disagreed with itself.

**Why the existing suite did not catch it, which is the more interesting half.** `parallel-live-*` is
the fixture built for exactly this shape — three milestones in flight — and every one of its in-flight
milestones carries `history[]` entries. That models a state the graph does not produce: an agent's
transitions appear all at once, on replay, after it returns. A fixture that gives running milestones a
recorded history cannot exhibit the bug, so the corpus quietly certified the defect. Hence check 2:
the corpus must contain the real shape, not only the comfortable one.

    python3 milestone_status.py

Every check runs twice — once against the real files, once against a copy with that specific defect
planted, which MUST come back red. A check that cannot fail is not evidence.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

VIEWER = paths.VIEWER
FIXTURES = paths.FIXTURES

# The pill expression, matched from `class="pill"` to the end of that interpolation.
#
# This MUST be searched inside `viewMilestones` and not across the whole page: `viewAgents` renders
# its own `class="pill"` ~60 lines earlier, so a file-wide search silently reads the subagent panel's
# badge instead. The first draft of this check did exactly that and came back red against a correct
# viewer AND a broken one — a check that cannot pass is worth less than no check at all.
PILL = re.compile(r'class="pill".*?\$\{(.*?)\}</span>', re.S)

PILL_FIXED = ("""          esc(m.delivered ? 'delivered' : nlabel((d.H.filter(e => e.milestone === m.id)"""
              """.slice(-1)[0] || {}).to)\n"""
              """            || (prog || (d.inflight || []).includes(m.id) ? 'in flight' : 'not started'))}</span>""")
PILL_HISTORY_ONLY = ("""          esc(m.delivered ? 'delivered' : nlabel((d.H.filter(e => e.milestone === m.id)"""
                     """.slice(-1)[0] || {}).to) || 'not started')}</span>""")


def body(js, name):
    """The source of one top-level `function name(...)`, by brace depth."""
    i = js.find("function " + name + "(")
    if i < 0:
        return ""
    depth, started = 0, False
    for j in range(i, len(js)):
        c = js[j]
        if c == "{":
            depth += 1
            started = True
        elif c == "}":
            depth -= 1
            if started and depth == 0:
                return js[i:j + 1]
    return js[i:]


def pill_expr(js):
    """The source of the milestone-row status pill's interpolated expression."""
    fn = body(js, "viewMilestones")
    if not fn:
        return ""
    m = PILL.search(fn)
    return m.group(1) if m else ""


# --- check 1 -------------------------------------------------------------------------------------

def pill_consults_liveness(js):
    """The pill must fall back through a liveness signal BEFORE reaching 'not started'.

    Reading `history[]` first is correct — a verified position beats a claimed one. What is not
    optional is that its absence routes through `progress` / `in_flight` rather than straight to
    'not started'.
    """
    expr = pill_expr(js)
    if not expr:
        return False, "no milestone status pill found in the viewer"
    if "'not started'" not in expr:
        return False, "pill no longer produces a 'not started' state — this check needs rewriting"
    liveness = ("prog" in expr) or ("progress" in expr) or ("inflight" in expr) or ("in_flight" in expr)
    if not liveness:
        return False, ("pill is derived from history[] alone, so a milestone with a running agent "
                       "reads 'not started' — history[] is empty until the return gate passes")
    return True, "pill consults progress/in_flight before falling back to 'not started'"


# --- check 2 -------------------------------------------------------------------------------------

def corpus_has_spawned_but_unrecorded(_js):
    """At least one fixture must show an in-flight milestone with NO history[] entries.

    This is the shape every strategy-C run passes through and the shape no fixture had.
    """
    worst = []
    for f in sorted(FIXTURES.glob("*-state.json")):
        try:
            s = json.loads(f.read_text())
        except Exception:
            continue
        inflight = s.get("in_flight") or []
        if not inflight:
            continue
        recorded = {h.get("milestone") for h in (s.get("history") or [])}
        unrecorded = [i for i in inflight if i not in recorded]
        if unrecorded:
            return True, f"{f.name} has in_flight {unrecorded} with no history[] rows"
        worst.append(f.name)
    if worst:
        return False, ("every in-flight fixture gives its running milestones history[] rows "
                       f"({', '.join(worst)}) — a state the graph never produces, so the corpus "
                       "cannot exhibit the running-reads-as-not-started defect")
    return False, "no fixture has any milestone in flight"


CHECKS = [
    ("running-milestone-does-not-read-not-started", pill_consults_liveness),
    ("a-fixture-covers-spawned-but-unrecorded", corpus_has_spawned_but_unrecorded),
]

# How to plant each defect, so the check is proven able to go red: put the pill back to the
# history-only form this commit removed.
PLANTS = {
    "running-milestone-does-not-read-not-started":
        lambda js: js.replace(PILL_FIXED, PILL_HISTORY_ONLY, 1),
}


def main():
    js = VIEWER.read_text()
    failed, inert = [], []

    for name, fn in CHECKS:
        ok, why = fn(js)
        print(f"{'ok   ' if ok else 'FAIL '} {name}" + ("" if ok else f"\n        {why}"))
        if not ok:
            failed.append(name)
            continue
        plant = PLANTS.get(name)
        if plant is None:
            # Check 2's defect lives in the fixture corpus, not the viewer source. Deleting a
            # fixture to prove the point would be a destructive self-test; the negative case is
            # instead the documented state the corpus was in before this commit, and the check
            # reads the corpus live, so it goes red the moment that fixture is removed.
            continue
        if fn(plant(js))[0]:
            inert.append(name)
            print(f"       INERT — planted defect did not make it fail")

    print()
    if failed:
        print(f"FAIL  {len(failed)} of {len(CHECKS)} checks: {', '.join(failed)}")
        return 1
    if inert:
        print(f"FAIL  {len(inert)} inert check(s): {', '.join(inert)}")
        return 1
    print(f"{len(CHECKS)}/{len(CHECKS)} checks pass, 0 inert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
