"""Where everything is, resolved once — the viewer's copy.

The same module exists in `sdlc-graph`. It is **not** shared, and that is the marketplace
rule rather than an oversight: a plugin references nothing outside its own root, so each side
owns its own layout. Twenty lines duplicated is the price of two plugins that install
independently.

The one deliberate exception is `GRAPH_SPEC` below, which reaches into the sibling plugin.
That direction — the viewer reading the graph — is the only legal one, because the viewer holds
a **copy** of the transition table and something has to notice when the original moves. The
graph's own suite may not look back this way.
"""
import pathlib

LIB = pathlib.Path(__file__).resolve().parent
EVALS = LIB.parent
SKILL = EVALS.parent                      # .../skills/view-run
PLUGIN = SKILL.parent.parent              # .../plugins/sdlc-graph-viewer
PLUGINS = PLUGIN.parent                   # .../plugins

# --- the skill's own directories ---------------------------------------------------------
VIEWER_DIR = SKILL / "viewer"
SERVER_DIR = SKILL / "server"
FIXTURES = SKILL / "fixtures"
DOCS = PLUGIN / "docs"
ARTIFACTS = DOCS / "artifacts"

VIEWER = VIEWER_DIR / "run-viewer.html"
SERVER = SERVER_DIR / "server.mjs"
ENV_EXAMPLE = SERVER_DIR / "sdlc-graph-viewer.env.example"
SKILL_MD = SKILL / "SKILL.md"

# --- the eval suite ----------------------------------------------------------------------
SYNC = EVALS / "sync"
SAFETY = EVALS / "safety"

# --- the sibling plugin, read-only, one direction only ------------------------------------
GRAPH_SPEC = PLUGINS / "sdlc-graph" / "skills" / "sdlc-graph"

# Where the graph keeps its model, relative to a graph skill root. Mirrors `REL` in the
# graph's own `lib/paths.py`; when the graph moves these, this is the one place that follows.
GRAPH_REL = {
    "edges": "graph/edges.md",
    "nodes": "graph/nodes.md",
    "state": "graph/state.md",
}


def graph_files(spec_dir):
    """`{name: pathlib.Path}` for the graph's model files, under an arbitrary spec root.

    `graph_sync_selftest.py` copies the graph spec to a temp dir and mutates it, so this must
    resolve against the root it is handed rather than against `GRAPH_SPEC`.
    """
    spec_dir = pathlib.Path(spec_dir)
    return {name: spec_dir / rel for name, rel in GRAPH_REL.items()}
