#!/usr/bin/env python3
"""Regenerate the viewer's `GRAPH.EDGES` / `GRAPH.BOUNDS` from the graph's own spec.

`graph_sync.py` checks that the viewer's copy of the graph agrees with `edges.md` and `nodes.md`.
It has always been a *checker*: when it went red, someone hand-edited 42 entries in an HTML file
until it went green again. This writes them instead.

    python3 sync_graph.py            # report what would change
    python3 sync_graph.py --write    # rewrite the GRAPH block in run-viewer.html

Only `EDGES` and `BOUNDS` are generated — the two blocks that are pure restatements of the spec.
`POS`, `RANK`, `DESC` and `HUMAN` stay hand-authored: layout and prose are the viewer's own, and
`HUMAN` is already checked against the node contracts rather than copied blind.

The spec lives in the sibling plugin, which is why this is a *tool you run* and not part of the
suite: a plugin may not read above its own root, so the path is supplied, not assumed.
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
DEFAULT_SPEC = paths.GRAPH_SPEC


def parse(spec_dir):
    """(edges-by-source, bounds) exactly as the viewer needs them."""
    g = paths.graph_files(spec_dir)
    return (parse_edges(g["edges"].read_text(encoding="utf-8"))[0],
            parse_bounds(g["nodes"].read_text(encoding="utf-8")))


def parse_edges(edges_md):
    """({source: [[edge-id, target, guard], …]}, callers) from the transition table.

    The two `DEBUG` rows are RULES over six callers each. A board draws real arrows, so both
    expand here — the table gets shorter, the picture does not get thinner.
    """
    clean = lambda x: re.sub(r"[`*]", "", x).strip()
    rows = [m for m in (re.match(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", ln)
                        for ln in edges_md.splitlines()) if m]

    # The `DEBUG` fan-out row names its callers; the fan-in row returns to the same set. The viewer
    # draws real arrows, so both rules expand — a board cannot draw "any of six".
    callers = next((re.findall(r"`(\w+)`", m.group(2)) for m in rows
                    if len(re.findall(r"`(\w+)`", m.group(2))) > 1), [])

    def endpoints(cell):
        if "debug_return_to" in cell:
            return callers
        named = re.findall(r"`(\w+)`", cell)
        return named if len(named) > 1 else [clean(cell)]

    by_source = {}
    for m in rows:
        eid, guard = m.group(1), clean(m.group(4))
        froms, tos = endpoints(m.group(2)), endpoints(m.group(3))
        for frm in froms:
            for to in tos:
                one = eid if len(froms) == len(tos) == 1 else f"{eid}·{frm if len(froms) > 1 else to}"
                by_source.setdefault(frm, []).append([one, to, guard])
    return by_source, callers


def parse_bounds(nodes_md):
    """{attempts-key prefix: bound} from the node contracts.

    A node's `max attempts` row IS its `DEBUG` round-trip's bound (`edges.md` row 19). The three
    keys that are not node names are the two dispatch retries and the run-level reopen bound.
    """
    bounds = {}
    sections = re.split(r"^###\s+`(\w+)`", nodes_md, flags=re.M)
    for name, body in zip(sections[1::2], sections[2::2]):
        row = re.search(r"^\|\s*\*\*max attempts\*\*\s*\|(.+)$", body, re.M)
        if not row:
            continue
        cell = re.sub(r"[`]", "", row.group(1))
        n = re.search(r"\*\*(\d+)[^*]*\*\*|^\s*(\d+)\b", cell)
        if name == "CI":
            bounds["CI"] = "15m"                      # a time budget, not a count
        elif n and name in {"TEST", "E2E", "GATE_A", "GATE_B", "CONSOLIDATE"}:
            bounds[name] = int(n.group(1) or n.group(2))
    bounds["GATE_A-dispatch"] = 1
    bounds["MILESTONE-dispatch"] = 1
    bounds["QA"] = 2                                   # VERDICT's reopen bound, keyed bare
    return bounds


def block(name, value, indent="  "):
    body = json.dumps(value, indent=2, ensure_ascii=False)
    return f'{indent}"{name}": ' + body.replace("\n", "\n" + indent)


def rewrite(html, name, value):
    """Replace one top-level key of the GRAPH object, brace-matched rather than regexed."""
    start = html.index(f'\n  "{name}": ')
    i = html.index(("[" if isinstance(value, list) else "{"), start)
    depth, j = 0, i
    while True:
        if html[j] in "[{":
            depth += 1
        elif html[j] in "]}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return html[:start] + "\n" + block(name, value) + html[j + 1:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-dir", default=str(DEFAULT_SPEC))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    spec_dir = pathlib.Path(args.spec_dir)
    if not paths.graph_files(spec_dir)["edges"].exists():
        print(f"no {paths.GRAPH_REL['edges']} under {spec_dir} — pass --spec-dir")
        return 2

    edges, bounds = parse(spec_dir)
    html = VIEWER.read_text(encoding="utf-8")
    updated = rewrite(rewrite(html, "EDGES", edges), "BOUNDS", bounds)

    if updated == html:
        print("ok    the viewer's GRAPH already matches the spec")
        return 0
    if not args.write:
        print(f"the viewer's GRAPH is stale: {sum(len(v) for v in edges.values())} transitions, "
              f"{len(bounds)} bounds. Re-run with --write.")
        return 1
    VIEWER.write_text(updated, encoding="utf-8")
    print(f"wrote {sum(len(v) for v in edges.values())} transitions and {len(bounds)} bounds "
          f"into {VIEWER.name} — now run graph_sync.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
