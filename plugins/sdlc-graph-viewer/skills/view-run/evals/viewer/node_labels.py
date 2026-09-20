#!/usr/bin/env python3
"""Display labels: does every surface show them, and does the page still key on IDS?

A node's id is schema — `state.node`, both endpoints of every `history[]` entry,
`stopped.at_node`, `skipped_gates[].node`, and the `attempts["GATE_B:<id>"]` keys are written
with it in every state file already on disk. Renaming one is a migration. So the viewer carries
a `NODE_LABEL` map instead: the name a human reads, applied at render and nowhere else.

That arrangement has exactly two failure modes, and they pull in opposite directions:

1. **A surface misses the label.** The board says `ms-final-review`, the trace still says
   `GATE_B`, and a reader reasonably concludes they are two different nodes. This is the
   recurring defect class in this repo wearing new clothes — a fact fixed in one renderer and
   not in the other five — and it is why a rename "just in the UI" needs a checker at all.
2. **A label leaks into a key.** `data-node`, `A.selNode`, `GRAPH.POS[id]`, `GRAPH.EDGES[id]`,
   `INBOUND[id]` and the `history[]` comparisons all index by id. The first one that indexes by
   display name silently stops matching: the board highlights nothing, the node panel opens
   empty, and nothing throws.

Plus the rule that keeps both honest: `run facts` prints the raw field values, and the map
lives OUTSIDE `/*__GRAPH_BEGIN__*/…/*__GRAPH_END__*/`, because `sync/sync_graph.py --write`
regenerates everything between those markers from the spec and would silently delete it.

    python3 node_labels.py

Every check runs twice: once against the real file, and once against a copy with that specific
defect planted, which MUST come back red. A check that cannot fail is not evidence.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

VIEWER = paths.VIEWER


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


def label_map(js):
    """`NODE_LABEL` as a dict, parsed from the source rather than trusted."""
    m = re.search(r"const NODE_LABEL\s*=\s*\{([^}]*)\}", js)
    if not m:
        return None
    out = {}
    for k, v in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*'([^']*)'", m.group(1)):
        out[k] = v
    return out


def graph_block(js):
    """The viewer's embedded GRAPH, which is data-only and therefore parseable."""
    a = js.index("/*__GRAPH_BEGIN__*/")
    b = js.index("/*__GRAPH_END__*/")
    s = js[a:b]
    return json.loads(s[s.index("{"):s.rindex("}") + 1])


# ── the checks ────────────────────────────────────────────────────────────────────────────

def check_map_is_outside_the_generated_block(js):
    if "const NODE_LABEL" not in js:
        return "there is no NODE_LABEL map — nothing renders a display name"
    if "const nlabel" not in js:
        return "there is no nlabel() — every surface would have to remember the map itself"
    a, b = js.index("/*__GRAPH_BEGIN__*/"), js.index("/*__GRAPH_END__*/")
    if a < js.index("const NODE_LABEL") < b:
        return ("NODE_LABEL sits inside the GRAPH markers, which `sync/sync_graph.py --write` "
                "regenerates wholesale from the spec — the next resync deletes it and the UI "
                "silently reverts to bare ids")
    return ""


def check_labels_name_real_nodes(js):
    lab, G = label_map(js), graph_block(js)
    if lab is None:
        return "NODE_LABEL is not a flat literal this checker can read"
    if not lab:
        return "NODE_LABEL is empty — no node is labelled, so this whole mechanism is inert"
    bad = [k for k in lab if k not in G["POS"]]
    if bad:
        return ("NODE_LABEL labels " + ", ".join(bad) + " — not node ids in this graph, so the "
                "label never fires and a reader never learns why")
    # Two nodes rendering the same name is worse than no rename at all.
    names = list(lab.values()) + [n for n in G["POS"] if n not in lab]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        return "two nodes would render as the same name: " + ", ".join(sorted(dupes))
    return ""


# Every surface that shows a node to a human: the function that owns it, how many node names it
# renders, and what it is. The COUNT is the point. Checking mere presence lets a five-site
# renderer lose four of them and stay green, which is this repo's whole defect class — a fact
# fixed in one place and not the others. Adding a render site means bumping the number here, on
# purpose; losing one turns this red without anyone having to notice by eye.
SURFACES = [
    ("paintRuns", 2, "the run list — each run's current node, and its tooltip"),
    ("paintBanners", 2, "the blocked and the paused/handed-off banners"),
    ("paintKpis", 1, "the at-budget KPI's list of spent counters"),
    ("attemptRow", 1, "the retry-budget counter labels"),
    ("viewAgents", 1, "the subagent fan-out's per-node groups"),
    ("viewMilestones", 3, "each card's progress line, recorded-position pill, and skipped-here pills"),
    ("viewGraph", 6, "the board: node boxes, tooltips, panel title, outgoing and inbound edges"),
    ("viewTrace", 4, "the transition rows, and the search that has to match what they show"),
    ("viewLedger", 2, "the ledger summary and each entry's pill"),
    ("paintSide", 6, "the now-card, in-flight rows, next-step buttons and last transition"),
]

HELPER = re.compile(r"\b(?:nlabel|klabel|nboth)\(")


def check_every_surface_labels(js):
    bad = []
    for fn, n, what in SURFACES:
        src = body(js, fn)
        if not src:
            bad.append(f"{fn}() is gone — {what} has no renderer")
            continue
        found = len(HELPER.findall(src))
        if found < n:
            bad.append(f"{fn}() labels {found} of {n} node names ({what}) — the rest still show "
                       f"the raw id while every other surface shows the display name")
    return "; ".join(bad)


def check_facts_panel_stays_raw(js):
    src = body(js, "viewFacts")
    if not src:
        return "viewFacts() is gone — nothing shows the raw field values any more"
    if not re.search(r"\['state\.node',\s*s\.node\]", src):
        return ("the run-facts state.node row no longer prints s.node straight — that panel is "
                "the one place a reader can see what the FILE says, and a label there is a claim "
                "about bytes that are not on disk")
    if "NODE_LABEL" not in src:
        return ("run facts prints ids but never says why they differ from every other surface — "
                "the panel has to name the mapping or it reads as a third node name")
    return ""


def check_keys_are_still_ids(js):
    """Ids index everything. A display name reaching a lookup matches nothing and throws nothing."""
    bad = []
    src = body(js, "viewGraph")
    if not re.search(r'data-node="\$\{id\}"', src):
        bad.append("the board's data-node is no longer the raw id — bindGraph() puts it straight "
                   "into A.selNode, which indexes GRAPH.POS/DESC/BOUNDS/EDGES")
    if not re.search(r"const p = xy\(id\)", src):
        bad.append("viewGraph() no longer positions by id")
    side = body(js, "paintSide")
    if not re.search(r'data-goto="\$\{esc\(e\.to\)\}"', side):
        bad.append("the next-step buttons no longer carry the raw id in data-goto — the click "
                   "sets A.selNode, so a label there opens an empty node panel")
    d = body(js, "derive")
    if "nlabel(" in d:
        bad.append("derive() calls nlabel() — it computes `cur`, the visited set and the "
                   "candidate edges, all by id; a label in there stops matching GRAPH and "
                   "history[] and the board simply highlights nothing")
    return "; ".join(bad)


def check_search_matches_both_names(js):
    src = body(js, "viewTrace")
    m = re.search(r"if \(q &&[\s\S]{0,400}?return false;", src)
    if not m:
        return "viewTrace() has no search filter where this check can read it"
    if "nlabel(" not in m.group(0):
        return ("the trace search matches raw ids only — the rows now read `ms-final-review`, so "
                "typing what is on the screen finds nothing")
    return ""


def interpolations(src):
    """Every `${ … }` in a template as (text, start), by brace depth so nested ones come whole."""
    out = []
    for m in re.finditer(r"\$\{", src):
        depth, k = 1, m.end()
        while k < len(src) and depth:
            if src[k] == "{":
                depth += 1
            elif src[k] == "}":
                depth -= 1
            k += 1
        out.append((src[m.end():k - 1], m.start()))
    return out


def deferred_spans(src):
    """Ranges building a value that is escaped later, at the point it is emitted.

    `viewLedger` composes `summary` from a template and emits `${esc(summary)}`. Escaping
    inside the composition as well would double-encode it — the file carries a comment saying
    so, from the time it did. Interpolations in that span are escaped, just not there.
    """
    spans = []
    for v in set(re.findall(r"\besc\((\w+)\)", src)):
        a = re.search(r"\bconst\s+" + v + r"\s*=", src)
        b = re.search(r"\besc\(" + v + r"\)", src)
        if a and b and a.start() < b.start():
            spans.append((a.start(), b.start()))
    return spans


def check_labels_are_escaped(js):
    """These helpers take an id STRAIGHT FROM THE STATE FILE and hand it back for display.

    `nlabel(g.node)` returns `g.node` verbatim for the 19 nodes with no label — so an
    un-escaped call site is a run-data injection wearing a helper's name, on the one surface
    that looked too boring to check. Same rule the rest of the page already follows.
    """
    bad = []
    for fn, _, _ in SURFACES:
        src = body(js, fn)
        spans = deferred_spans(src)
        for expr, at in interpolations(src):
            if not HELPER.search(expr) or "esc(" in expr:
                continue
            # Arithmetic over the name — a length-based font-size step renders no text.
            if ".length" in expr:
                continue
            if any(a <= at < b for a, b in spans):
                continue
            bad.append(f"{fn}(): an id reaches innerHTML unescaped — " +
                       " ".join(expr.split())[:80])
    return "; ".join(bad)


CHECKS = [
    ("label-map-is-outside-the-generated-graph", check_map_is_outside_the_generated_block,
     [("/*__GRAPH_END__*/\n\n/* ── display labels",
       "/* ── display labels"),
      ("const NODE_LABEL = {", "const NOPE_LABEL = {")]),
    ("every-label-names-a-real-node", check_labels_name_real_nodes,
     [("const NODE_LABEL = { GATE_B:", "const NODE_LABEL = { GATE_Q:"),
      ("GATE_B: 'ms-final-review'", "GATE_B: 'CI'")]),
    ("every-node-surface-shows-the-label", check_every_surface_labels,
     [("${esc(nlabel(e.from))} → ${esc(nlabel(e.to))}", "${esc(e.from)} → ${esc(e.to)}"),
      ("${esc(nlabel(g.node))}</span>\n      <span style=\"flex:1\">",
       "${esc(g.node)}</span>\n      <span style=\"flex:1\">")]),
    ("run-facts-still-prints-the-raw-field", check_facts_panel_stays_raw,
     [("['state.node', s.node]", "['state.node', nlabel(s.node)]")]),
    ("lookups-still-key-on-ids", check_keys_are_still_ids,
     [('data-node="${id}"', 'data-node="${nlabel(id)}"'),
      ('data-goto="${esc(e.to)}"', 'data-goto="${esc(nlabel(e.to))}"')]),
    ("trace-search-matches-both-names", check_search_matches_both_names,
     [("+ ' ' + nlabel(e.from) + ' ' + nlabel(e.to)", "")]),
    ("labels-are-escaped-like-run-data", check_labels_are_escaped,
     [("${esc(nlabel(id))}${GRAPH.HUMAN[id]", "${nlabel(id)}${GRAPH.HUMAN[id]")]),
]


def main():
    js = VIEWER.read_text(encoding="utf-8")
    failures, dead = [], []
    for name, fn, mutations in CHECKS:
        why = fn(js)
        print(("ok    " if not why else "FAIL  ") + name + ("" if not why else "\n      " + why))
        if why:
            failures.append(name)
            continue
        for old, new in mutations:
            if old not in js:
                dead.append(f"{name}: control text not found — {old[:56]!r}")
                continue
            broken = js.replace(old, new, 1)
            try:
                still_green = not fn(broken)
            except Exception:
                still_green = False      # a checker that throws on the defect has still noticed it
            if still_green:
                dead.append(f"{name}: stayed green with `{old[:46]}…` broken")

    for d in dead:
        print("DEAD  " + d)
    n = len(CHECKS)
    print(f"\n{n - len(failures)}/{n} checks pass, {len(dead)} inert")
    return 1 if failures or dead else 0


sys.exit(main())
