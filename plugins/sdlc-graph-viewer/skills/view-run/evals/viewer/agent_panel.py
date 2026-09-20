#!/usr/bin/env python3
"""The subagent panel: does it render the journal honestly, and can this check go red?

A milestone journal now carries two lines per subagent the milestone agent spawns (`agent_spawn`,
`agent_done` — graph plugin, `workflow-dispatch.md` § *Every subagent you spawn gets two lines*), and
the viewer renders them as the milestone's fan-out. That panel is the first place in this page where
**a subagent's own free text is displayed**: its label, why it was spawned, and its 2-3 line summary.

Three ways that goes wrong, and one assertion each:

1. **It renders as markup.** Every other surface here goes through `esc()`; a new one that forgets is
   an injection from anything that can write a journal line.
2. **It sorts by arrival.** Gate A's groups run CONCURRENTLY, so returns interleave. Pairing the two
   events by the writer's spawn ordinal is the difference between "the fan-out" and "the order things
   happened to finish", and the page labels it as the former.
3. **It reads as more than it is.** The journal is telemetry — nothing routes on it, and no subagent
   appears in `history[]`. A panel that does not say so invites a reader to treat it as the record.

Plus the scale case the whole thing exists for: Gate A can spawn dozens, so the truncation the server
applies has to be visible rather than silent.

    python3 agent_panel.py

Every check runs twice: once against the real files, and once against a copy with that specific
defect planted, which MUST come back red. A check that cannot fail is not evidence — the graph
plugin's spec suite learned that at a 15% inert rate, and this file is not exempt from it.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

VIEWER = paths.VIEWER
SERVER = paths.EVALS.parent / "server" / "server.mjs"


def body(js, name):
    """The source of one top-level `function name(...)`, by brace depth."""
    i = js.find("function " + name + "(")
    if i < 0:
        return ""
    depth, started = 0, False
    for j in range(i, len(js)):
        if js[j] == "{":
            depth += 1
            started = True
        elif js[j] == "}":
            depth -= 1
            if started and depth == 0:
                return js[i:j + 1]
    return js[i:]


def interpolations(src):
    """Every `${ … }` in a template, by brace depth so nested templates come back whole."""
    out = []
    for m in re.finditer(r"\$\{", src):
        depth, k = 1, m.end()
        while k < len(src) and depth:
            if src[k] == "{":
                depth += 1
            elif src[k] == "}":
                depth -= 1
            k += 1
        out.append(src[m.end():k - 1])
    return out


# Fields that come from a journal line — i.e. from a subagent's own text — and therefore may never
# reach the page unescaped.
UNTRUSTED = re.compile(r"\ba\.(label|type|purpose|headline|outcome|node)\b|\br\.error\b|\bs\b(?=\))")


def check_escaped(html, server):
    bad = []
    src = body(html, "viewAgents")
    if not src:
        return "run-viewer.html has no viewAgents() — the subagent panel is gone"
    for expr in interpolations(src):
        if UNTRUSTED.search(expr) and "esc(" not in expr:
            bad.append("an interpolation carries journal text unescaped: " + " ".join(expr.split())[:90])
    return "; ".join(bad)


def check_spawn_order(html, server):
    src = body(html, "agentsOf")
    if not src:
        return "run-viewer.html has no agentsOf() — nothing reads the agent events"
    bad = []
    for ev in ("agent_spawn", "agent_done"):
        if ev not in src:
            bad.append(f"agentsOf() never looks for `{ev}`")
    # Paired by the writer's ordinal, and ordered by it. Arrival order is `ord`, which may only be
    # the tie-break — a sort that uses it first is completion order wearing a spawn-order label.
    if not re.search(r"a\.n\s*!=\s*null", src):
        bad.append("agentsOf() does not pair the two events on the writer's `n`, so a concurrent "
                   "Gate A pairs on arrival instead")
    if not re.search(r"\.sort\([\s\S]{0,90}?x\.n[\s\S]{0,140}?y\.n", src):
        bad.append("agentsOf() does not sort by `n` — the panel calls itself spawn order and shows "
                   "whatever order the returns arrived in")
    return "; ".join(bad)


def check_says_where_it_came_from(html, server):
    src = body(html, "viewAgents")
    bad = []
    if "journals/milestone-" not in src:
        bad.append("the panel never names the file it is reading, so its rows are indistinguishable "
                   "from the verified history[] rows above them")
    if not re.search(r"telemetry", src, re.I):
        bad.append("the panel does not say the journal is telemetry — a per-agent list is exactly "
                   "what a reader starts citing as proof a gate ran")
    if "info(" not in src:
        bad.append("the panel has no provenance marker, unlike every other number on the page")
    return "; ".join(bad)


def check_unknown_outcome_is_not_success(html, server):
    src = body(html, "agentsOf")
    if not re.search(r"\[['\"]returned['\"],\s*['\"]died['\"],\s*['\"]absent['\"]\]", src):
        return ("agentsOf() does not restrict `outcome` to the three the spec defines, so an "
                "outcome this page has never heard of renders in whichever branch it falls through "
                "to — the run list already refuses to do that with an unknown `status`")
    return ""


def check_truncation_is_visible(html, server):
    bad = []
    m = re.search(r"Math\.min\((\d+),\s*Math\.max\(1,\s*Number\(url\.searchParams\.get\('tail'\)\)", server)
    if not m:
        bad.append("server.mjs no longer clamps the journal tail where this check can read it")
    elif int(m.group(1)) < 2000:
        bad.append(f"the journal tail is capped at {m.group(1)} lines — Gate A alone writes two per "
                   "agent and can spawn dozens, so the list silently starts partway in")
    if "entry.dropped" not in server:
        bad.append("server.mjs does not report how many lines the tail cut, so a truncated fan-out "
                   "renders as the whole one")
    if "r.dropped" not in body(html, "viewAgents"):
        bad.append("the panel never shows the dropped count it is handed — a silent cap on a list "
                   "labelled 'everything this milestone spawned'")
    return "; ".join(bad)


CHECKS = [
    ("subagent-text-is-escaped", check_escaped,
     [(0, "esc(a.label || a.type || 'unlabelled agent')", "a.label || a.type || 'unlabelled agent'")]),
    ("paired-and-ordered-by-spawn", check_spawn_order,
     [(0, "(x.n == null ? Infinity : x.n) - (y.n == null ? Infinity : y.n) || x.ord - y.ord",
       "x.ord - y.ord"),
      (0, "l.event !== 'agent_spawn'", "l.event !== 'nope'")]),
    ("panel-names-its-source", check_says_where_it_came_from,
     [(0, "journals/milestone-' + m.id + '.jsonl", "some file"),
      (0, "telemetry, never evidence", "the record")]),
    ("unknown-outcome-is-not-success", check_unknown_outcome_is_not_success,
     [(0, "['returned', 'died', 'absent'].includes(a.outcome)", "a.outcome !== 'x'")]),
    ("truncation-is-visible", check_truncation_is_visible,
     [(1, "Math.min(5000,", "Math.min(200,"),
      (1, "entry.dropped = Math.max", "entry.cut = Math.max")]),
]


def main():
    html = VIEWER.read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")
    failures, dead = [], []
    for name, fn, mutations in CHECKS:
        why = fn(html, server)
        print(("ok    " if not why else "FAIL  ") + name + ("" if not why else "\n      " + why))
        if why:
            failures.append(name)
            continue
        # ...and the same check against a copy with the defect planted. Red is the pass here.
        for which, old, new in mutations:
            src = [html, server][which]
            if old not in src:
                dead.append(f"{name}: control text not found — {old[:50]}")
                continue
            pair = [html, server]
            pair[which] = src.replace(old, new, 1)
            if not fn(*pair):
                dead.append(f"{name}: stayed green with `{old[:46]}…` broken")

    for d in dead:
        print("DEAD  " + d)
    n = len(CHECKS)
    print(f"\n{n - len(failures)}/{n} checks pass, {len(dead)} inert")
    return 1 if failures or dead else 0


sys.exit(main())
