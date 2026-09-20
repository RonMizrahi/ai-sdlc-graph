"""Where everything is, resolved once.

Nine scripts in this suite used to count `../` from their own location — `HERE.parent`,
`parent.parent`, `parent.parent.parent.parent`. That works exactly until the tree is
restructured, and then every count is wrong in a different way. Three of those were wrong
**silently**: they globbed a directory that no longer existed, found nothing, and reported
a clean pass over an empty set. *A glob that matches nothing is a check that cannot fail* —
the same failure mode this suite exists to catch, arriving through the back door of a
file move.

So the layout is written down once, here, and nothing else counts directories.

Two kinds of path live in this module and they are not interchangeable:

- **Absolute constants** (`NODES_MD`, `FIXTURES`, …) — for a script reading *this* plugin.
- **`spec_files(root)` and `REL`** — for the checkers that run against a **copy** of the
  plugin. `spec_controls.py` copies the plugin to a temp dir, mutates one file, and runs
  `spec_consistency.py --spec-dir <copy>`; `audit_run.py` takes `--spec-dir` for the same
  reason. Those must resolve relative to the root they were handed, never to this file.
"""
import pathlib

LIB = pathlib.Path(__file__).resolve().parent
EVALS = LIB.parent
SKILL = EVALS.parent                      # .../skills/sdlc-graph
PLUGIN = SKILL.parent.parent              # .../plugins/sdlc-graph

# --- the skill's own directories ---------------------------------------------------------
GRAPH = SKILL / "graph"                   # the model: nodes.md, edges.md, state.md
NODES = SKILL / "nodes"                   # the eight node procedures, and qa/
SUBAGENTS = SKILL / "subagents"           # the milestone-agent contract
OBSERVABILITY = SKILL / "observability"
WORKFLOWS = SKILL / "workflows"           # gate-a.workflow.js and its harness

NODES_MD = GRAPH / "nodes.md"
EDGES_MD = GRAPH / "edges.md"
STATE_MD = GRAPH / "state.md"
SKILL_MD = SKILL / "SKILL.md"
DISPATCH_MD = SUBAGENTS / "workflow-dispatch.md"
OBSERVABILITY_MD = OBSERVABILITY / "observability.md"

# --- the plugin, above the skill ---------------------------------------------------------
AGENTS = PLUGIN / "agents"
DOCS = PLUGIN / "docs"
ARTIFACTS = DOCS / "artifacts"
MILESTONE_AGENT = AGENTS / "sdlc-graph-milestone.md"

# The plugin's second skill. It reads this one's spec and writes into this one's evals/,
# which is why it lives inside the same plugin rather than beside it — a plugin may not
# reference anything outside its own root.
REVIEWER = PLUGIN / "skills" / "graph-run-reviewer"
REVIEWER_MD = REVIEWER / "SKILL.md"
REVIEWER_CHECKS = REVIEWER / "checks" / "what-to-look-for.md"

# --- the eval suite ----------------------------------------------------------------------
SPEC = EVALS / "spec"
WALKS = EVALS / "walks"
FIXTURES = WALKS / "fixtures"
AUDIT = EVALS / "audit"
RUNS = EVALS / "runs"
SCENARIOS = RUNS / "scenarios"
REAL = EVALS / "real"
BEHAVIOURAL = EVALS / "behavioural"
HOOKS = EVALS / "hooks"

# --- the same layout, relative --- for anything running against a COPY of the plugin ------
#
# Keyed by the name `spec_consistency.py` uses for each file, so the two cannot drift apart.
REL = {
    "nodes": "graph/nodes.md",
    "edges": "graph/edges.md",
    "state": "graph/state.md",
    "skill": "SKILL.md",
    "dispatch": "subagents/workflow-dispatch.md",
    "observability": "observability/observability.md",
}

# Directories, relative to a skill root. Same purpose, same no-drift rule.
REL_DIRS = {
    "graph": "graph",
    "nodes": "nodes",
    "qa": "nodes/qa",
    "subagents": "subagents",
    "observability": "observability",
    "workflows": "workflows",
    "evals": "evals",
    "fixtures": "evals/walks/fixtures",
    "scenarios": "evals/runs/scenarios",
}


def spec_files(root):
    """`{name: pathlib.Path}` for every core spec file, under an arbitrary skill root."""
    root = pathlib.Path(root)
    return {name: root / rel for name, rel in REL.items()}


def node_files(root):
    """The eight graph-scoped node procedures, under an arbitrary skill root."""
    return sorted((pathlib.Path(root) / REL_DIRS["nodes"]).glob("*-node.md"))


def on_path():
    """Put the two importable directories on `sys.path`: `lib/` and `walks/`.

    Three modules in this suite are imported by other suites rather than run:
    `lib/invariants.py` (the walker and the auditor share it), `lib/paths.py` (this
    file), and `walks/graph_walk.py` — whose `parse_edges` / `parse_bounds` are the
    single parser of `edges.md` and `nodes.md` that everything else defers to.

    **Both go on the path together, deliberately.** They were added separately at
    first and the auditor imported `graph_walk` with only `lib/` inserted — a crash
    at import time, which for a tool whose whole contract is *"never answer a broken
    run with a traceback"* is the worst possible way to fail. One call, both
    directories, no caller deciding which it needs.
    """
    import sys
    for d in (LIB, WALKS):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
    return LIB
