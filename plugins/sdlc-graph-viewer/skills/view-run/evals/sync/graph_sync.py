#!/usr/bin/env python3
"""Does the viewer still describe the graph it claims to render?

The viewer carries its own copy of the transition table so it can show what happens next — and the
graph plugin's own eval suite **cannot reach it**: a plugin may not read above its own root, so
`spec_consistency.py` globs `plugins/sdlc-graph/` and stops there. That leaves the viewer as the
one copy of the spec with nothing checking it, which is the failure mode this whole family keeps
having: a guard fixed in `edges.md` and not in the surface that renders it.

The restriction runs one way only. Nothing stops the VIEWER's evals from reading the graph plugin, so
that is where this check lives.

    python3 graph_sync.py [--spec-dir <…/sdlc-graph/skills/sdlc-graph>]

Exit 0 when the viewer agrees with the spec, or when the graph plugin is not installed (a checker
that fails on a legitimate standalone install is a checker people delete). Exit 1 on real drift.
No dependencies.
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

HERE = paths.SYNC
VIEWER = paths.VIEWER
FIXTURES = paths.FIXTURES
VIEWER_TEXT = ""                       # set by main(), so --viewer can point at a copy
DEFAULT_SPEC = paths.GRAPH_SPEC

CHECKS = []

# edges.md backticks a handful of ordinary words for emphasis, and they are not fields the viewer's
# abbreviated guard has to keep. Everything else backticked IS treated as a predicate — an
# allow-nothing default, so a genuinely new field is caught the day it lands, and a new prose word
# turns this check red and gets added here deliberately. Loud is the correct failure direction: the
# alternative was a pattern that quietly matched nothing at all.
PROSE = {"absent"}


def check(ident, why):
    """Registers a check. `why` is the real defect it guards against — same shape as the graph
    plugin's own `spec_consistency.py`, so the two read as siblings."""
    def wrap(fn):
        CHECKS.append((ident, why, fn))
        return fn
    return wrap


# ── reading the two sides ─────────────────────────────────────────────────────────────────
def viewer_graph(text):
    """The GRAPH block, parsed. It is strict JSON on purpose: the guard PREDICATES live in a
    separate APPLIES map keyed by edge id precisely so this block stays parseable without a JS
    engine. If someone inlines a function here, this is where it stops being checkable."""
    m = re.search(r"/\*__GRAPH_BEGIN__\*/\s*const GRAPH\s*=\s*(\{.*?\});?\s*/\*__GRAPH_END__\*/",
                  text, re.S)
    if not m:
        raise SystemExit("run-viewer.html has no /*__GRAPH_BEGIN__*/ … /*__GRAPH_END__*/ block")
    return json.loads(m.group(1))


def spec_edges(edges_md):
    """{edge-id: (from, to, guard, guard_raw)} straight from the transition table.

    The two `DEBUG` rows are RULES over six callers each — `edges.md` authors them once, and this
    expands them into the twelve transitions a board actually has to draw. The expansion lives in
    `sync_graph.py`, which is also what WRITES the viewer's copy: one parser per plugin, so the
    generator and the checker cannot form their own opinions about the same file.

    `guard_raw` keeps the backticks. It exists because `guard-identifiers-survive` reads the spec's
    guard for backticked field names, and `clean` had already stripped every backtick out by the time
    it looked — so its extractor matched nothing, corpus-wide, and 26 of the 42 guards were checked
    against an empty identifier set. Keep the two apart: display strips, extraction does not."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import sync_graph
    by_source, _ = sync_graph.parse_edges(edges_md)
    raws = {}
    for line in edges_md.splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", line)
        if m:
            raws[m.group(1)] = m.group(4).strip()
    out = {}
    for frm, rows in by_source.items():
        for eid, to, guard in rows:
            out[eid] = (frm, {"[handoff]": "HANDOFF"}.get(to, to), guard,
                        raws.get(eid.split("·")[0], guard))
    return out


def spec_nodes(nodes_md):
    return set(re.findall(r"^###\s+`(\w+)`", nodes_md, re.M))


def spec_stops(nodes_md):
    """NODE -> stop type, from the `human` row of each contract. Derived, never hand-kept."""
    TYPES = ("approval-after", "choice-after", "confirm-before", "await-external", "escalation")
    stops, parts = {}, re.split(r"^###\s+`(\w+)`", nodes_md, flags=re.M)
    for name, body in zip(parts[1::2], parts[2::2]):
        row = re.search(r"^\|\s*\*\*human\*\*\s*\|(.+)$", body, re.M)
        if not row:
            continue
        hit = [t for t in TYPES if t in row.group(1)]
        if hit:
            stops[name] = hit[0]
    return stops


def spec_bounds(edges_md, nodes_md):
    """{attempts-key prefix: bound}, parsed from the NODE CONTRACTS.

    It used to be parsed out of `edges.md` § Loop bounds, which listed the six `DEBUG` round-trips
    as six rows. Those six rows are now one rule — a node's `max attempts` IS its round-trip's
    bound — so the numbers live where they always really lived, in the contract of the node that
    owns them. Same source as `graph_walk.py` and `audit_run.py` use, reached through the
    generator so this plugin keeps exactly one parser.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import sync_graph
    return sync_graph.parse_bounds(nodes_md)


# ── the checks ────────────────────────────────────────────────────────────────────────────
@check("edge-ids-match",
       "edges.md retired eight edges in one release; a viewer still offering a retired edge as a "
       "next-step candidate is telling a human the run can go somewhere it cannot")
def _(G, edges, nodes, stops, bounds):
    have = {eid for lst in G["EDGES"].values() for eid, *_ in lst}
    want = {e for e in edges if edges[e][0] != "[start]"}   # [start] has no source node to draw from
    missing, extra = sorted(want - have), sorted(have - want)
    problems = []
    if missing:
        problems.append("edges.md declares edges the viewer does not draw: " + ", ".join(missing))
    if extra:
        problems.append("the viewer draws edges edges.md does not declare: " + ", ".join(extra))
    return "; ".join(problems) or None


@check("edge-endpoints-match",
       "a rerouted edge is the drift that looks most like working software: the board still draws "
       "an arrow, and it points at the wrong node")
def _(G, edges, nodes, stops, bounds):
    bad = []
    for frm, lst in G["EDGES"].items():
        for eid, to, _guard in lst:
            if eid not in edges:
                continue                      # already reported by edge-ids-match
            want_from, want_to = edges[eid][0], edges[eid][1]
            if (frm, to) != (want_from, want_to):
                bad.append(f"edge {eid}: viewer {frm}->{to}, edges.md {want_from}->{want_to}")
    return bad and ("; ".join(bad))


@check("node-set-matches",
       "a node added to the catalogue and never drawn is invisible on the board — and the board is "
       "what a human reads to decide whether a run is where it should be")
def _(G, edges, nodes, stops, bounds):
    SENTINELS = {"BLOCKED", "HANDOFF"}        # real board nodes, not `### ` contracts
    drawn = set(G["POS"]) - SENTINELS
    missing, extra = sorted(nodes - drawn), sorted(drawn - nodes)
    problems = []
    if missing:
        problems.append("nodes.md defines nodes the board does not place: " + ", ".join(missing))
    if extra:
        problems.append("the board places nodes with no contract: " + ", ".join(extra))
    return "; ".join(problems) or None


@check("bounds-match",
       "the viewer prints a retry counter against its bound. A decorative bound — a number with no "
       "real limit behind it, or a limit the spec never declared — is worse than printing nothing, "
       "because it reads as a check that ran")
def _(G, edges, nodes, stops, bounds):
    if not bounds:
        # `spec_bounds` splits on the literal "## Loop bounds", so retitling that heading empties
        # this table — and returning None here turned the whole check into a no-op that reported ok.
        # Every other extractor in this file fails loudly when it comes back empty; this one went
        # quiet, which is the worse half of the drift it exists to catch.
        return ("edges.md yielded no loop bounds at all — has '## Loop bounds' been renamed? "
                "Nothing checked the viewer's BOUNDS table")
    problems = []
    for key, want in bounds.items():
        got = G["BOUNDS"].get(key)
        if got is None:
            problems.append(f"{key} is bounded at {want} in edges.md and absent from the viewer")
        elif isinstance(want, int) and got != want:
            problems.append(f"{key}: viewer says {got}, edges.md says {want}")
    for key in G["BOUNDS"]:
        if key not in bounds:
            problems.append(f"the viewer bounds {key}, which edges.md § Loop bounds never declares")
    return "; ".join(problems) or None


@check("human-stops-match",
       "the six stops are derived from the node contracts so the two lists cannot drift; a viewer "
       "with its own copy is exactly the drift that rule exists to prevent")
def _(G, edges, nodes, stops, bounds):
    got = G["HUMAN"]
    problems = []
    for node, kind in stops.items():
        if node not in got:
            problems.append(f"{node} declares a '{kind}' stop the viewer does not mark")
        elif got[node] != kind:
            problems.append(f"{node}: viewer says '{got[node]}', nodes.md says '{kind}'")
    for node in got:
        if node not in stops:
            problems.append(f"the viewer marks {node} as a human stop; its contract declares none")
    return "; ".join(problems) or None


@check("guard-identifiers-survive",
       "the viewer legitimately abbreviates a 200-character guard to fit a board, so equality would "
       "be deleted within a month. What may NOT change is which fields the guard tests — that is the "
       "predicate, and a predicate that quietly differs is a viewer showing the wrong next step")
def _(G, edges, nodes, stops, bounds):
    bad = []
    for frm, lst in G["EDGES"].items():
        for eid, _to, guard in lst:
            if eid not in edges:
                continue
            want, raw = edges[eid][2], edges[eid][3]
            # every backticked identifier in the spec's guard must appear somewhere in the viewer's.
            # Read the RAW cell — `want` has had its backticks stripped for display, and reading it
            # here is what silently emptied this set for three quarters of the table.
            idents = {t.strip() for t in re.findall(r"`([^`]+)`", raw)}
            idents |= set(re.findall(r"\b(context\.\w+|integration\.\w+|attempts|branching|verdict)\b", want))
            for ident in sorted(idents):
                head = ident.split()[0].strip("*_,.;:()").removesuffix("[]")
                if not head or head in PROSE or head.endswith(".md"):
                    continue
                if head not in guard:
                    bad.append(f"edge {eid}: guard drops '{head}'")
    return bad and ("; ".join(sorted(set(bad))))


@check("page-loads-nothing-external",
       "the prototype this page was ported from fetched React from unpkg at load time. A snapshot "
       "that needs the network is a page that renders differently for the person you sent it to — "
       "and it would pass any check made on a machine with a warm cache")
def _(G, edges, nodes, stops, bounds):
    # Deliberately NOT a grep for 'http': a run's own qa_env.api_base_url is legitimately
    # http://localhost:3000, and a naive check fails on real state data. What matters is markup
    # or code that FETCHES something at load time.
    text = VIEWER_TEXT
    bad = []
    for pat, what in ((r"<script[^>]+\bsrc\s*=", "<script src>"),
                      (r"<link[^>]+\bhref\s*=", "<link href>"),
                      (r"@import\b", "CSS @import"),
                      (r"<(img|iframe|video|audio)[^>]+\bsrc\s*=\s*[\"']https?:", "remote media"),
                      (r"fetch\(\s*[\"'`]https?://", "fetch() of an absolute URL"),
                      (r"\bimport\s*\(\s*[\"']https?://", "dynamic import of a URL")):
        if re.search(pat, text, re.I):
            bad.append(what)
    return bad and ("the page loads something at view time: " + ", ".join(bad))


@check("fixtures-never-record-ahead-of-what-an-agent-claims",
       "`history[]` is written only after a bundle passes the return gate, so a milestone whose "
       "agent is still in flight cannot have a RECORDED position past the hop that entered BRANCH "
       "— the rest is replayed on return. Three fixtures recorded IMPLEMENT/TEST/GATE_A for "
       "milestones whose agents had not returned, so the board's recorded position ran AHEAD of "
       "what those agents CLAIMED. Nothing noticed, because the pill read a `milestones[].node` "
       "field instead of the trail: a field written by ten nodes and read by nothing else was "
       "standing between the viewer and the invariant")
def _(G, edges, nodes, stops, bounds):
    import json
    bad = []
    for path in sorted(FIXTURES.glob("*.json")):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue                       # one fixture is deliberately malformed; that is its job
        in_flight = set(s.get("in_flight") or [])
        for h in s.get("history") or []:
            if isinstance(h, dict) and h.get("milestone") in in_flight and h.get("from") != "GATE_B":
                bad.append(f"{path.name}: milestone {h['milestone']} is in flight and its trail "
                           f"already records {h.get('from')} -> {h.get('to')}")
                break
        for m in s.get("milestones") or []:
            if isinstance(m, dict) and m.get("id") in in_flight and m.get("delivered"):
                bad.append(f"{path.name}: milestone {m['id']} is in flight and already `delivered`")
    return bad and "; ".join(sorted(set(bad)))


@check("fixtures-only-walk-edges-the-graph-still-has",
       "The fixtures are the corpus every hand-check of this page runs against, so a fixture that "
       "walks a retired edge shows a WRONG BOARD to the one activity meant to catch a wrong board. "
       "When `PR_FINAL_REVIEW` was inserted between `PR` and `CI`, edge 22 was retargeted and 30 "
       "appended — but both fixtures that reach the tail kept their recorded `PR -> CI` hop. The "
       "board drew a bold visited curve straight past the new node and greyed it out as off-path, "
       "in every fixture, and every deterministic suite stayed green: the checks compared the "
       "viewer's edge table to the spec, and nothing compared the RUNS to either")
def _(G, edges, nodes, stops, bounds):
    import json
    legal = {(frm, to) for frm, lst in G["EDGES"].items() for _eid, to, _g in lst}
    bad = []
    for path in sorted(FIXTURES.glob("*.json")):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue                       # one fixture is deliberately malformed; that is its job
        for h in s.get("history") or []:
            if not isinstance(h, dict):
                continue
            frm, to = h.get("from"), h.get("to")
            if frm in (None, "[start]") or to is None:
                continue
            # Two transitions are real and are NOT numbered rows, so asserting on them would be
            # this checker over-claiming rather than the data being wrong:
            #   · `-> BLOCKED` — every bounded node halts there when its budget is spent
            #     (nodes.md, "*red at the 2nd attempt* -> BLOCKED (bound)"). Ten nodes, no edge ids.
            #   · `DEBUG -> …` — edge 20's target is "**the node named in `debug_return_to`**",
            #     decided at runtime. The viewer expands it into six `20·X` rows for drawing, and
            #     a set of six is a drawing convenience, not a claim that no seventh is reachable.
            if to == "BLOCKED" or frm == "DEBUG":
                continue
            if (frm, to) not in legal:
                bad.append(f"{path.name}: records {frm} -> {to}, which is not an edge in the graph")
    return bad and "; ".join(sorted(set(bad)))


def main():
    global VIEWER, VIEWER_TEXT, FIXTURES
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-dir", default=str(DEFAULT_SPEC))
    # Both sides are overridable so `graph_sync_selftest.py` can point the checker at a deliberately
    # broken copy and assert it goes red. A drift-checker nobody drifts is the same shape of unproven
    # as the auditor nobody audits — and this one shipped with a dead regex for exactly that reason.
    ap.add_argument("--viewer", default=str(VIEWER))
    # The fixture corpus is checked too, so the self-test must be able to point this
    # at a deliberately stale copy — same reason as --viewer above.
    ap.add_argument("--fixtures", default=str(FIXTURES))
    args = ap.parse_args()
    spec = pathlib.Path(args.spec_dir)
    VIEWER = pathlib.Path(args.viewer)
    FIXTURES = pathlib.Path(args.fixtures)

    g = paths.graph_files(spec)
    edges_md = g["edges"]
    nodes_md = g["nodes"]
    if not (edges_md.exists() and nodes_md.exists()):
        print(f"skip: sdlc-graph not installed at {spec} — nothing to compare against")
        return 0

    VIEWER_TEXT = VIEWER.read_text(encoding="utf-8")
    G = viewer_graph(VIEWER_TEXT)
    et, nt = edges_md.read_text(encoding="utf-8"), nodes_md.read_text(encoding="utf-8")
    edges, nodes, stops, bounds = spec_edges(et), spec_nodes(nt), spec_stops(nt), spec_bounds(et, nt)

    failures = []
    for ident, why, fn in CHECKS:
        problem = fn(G, edges, nodes, stops, bounds)
        if problem:
            failures.append((ident, why, problem))
            print(f"FAIL  {ident}\n      {problem}\n      (guards against: {why})")
        else:
            print(f"ok    {ident}")

    print(f"\n{len(CHECKS) - len(failures)}/{len(CHECKS)} viewer-vs-spec checks passed")
    if failures:
        print("\nThe viewer is a COPY of the graph. When it disagrees, the graph is right and this\n"
              "page is stale — fix the page, never the spec, and never the check.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
