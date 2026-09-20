#!/usr/bin/env python3
"""`APPLIES`: does each guard predicate still agree with the guard it claims to read?

The viewer dims the next-step buttons a run's own state already rules out. The graph decides
nothing here — `edges.md` order is the authority — so this is a reading aid, and a reading aid
that lies is worse than none: it says "this run cannot go there" about a run that can.

`GRAPH` is generated from the spec by `sync/sync_graph.py --write` and checked by
`sync/graph_sync.py`. **`APPLIES` is not**, and cannot be: predicates are functions, and the
GRAPH block has to stay parseable data for the drift checker to read it at all. So the map lives
outside the markers, where the generator does not reach — and it spent a release keyed on the
edge ids of the graph this viewer was FORKED from. Seven keys named edges that no longer existed
and evaluated for nothing. `'2'` (`spec_path != null`) was `!s.spec_path` and `'13'`
(`has_ui == false`) was `has_ui === true` — both the exact inverse of the guard beside them.
Every renumbered id landed on some other edge's meaning, and nothing anywhere went red.

So this suite closes the one hole the generated block leaves, in the only direction that works
without a second copy of the guards: it reads the guard CELL out of `GRAPH.EDGES`, extracts the
comparisons it can parse, and runs the real predicate under node against states built from them.

    python3 guard_predicates.py

Three rules, and what each one catches:

1. **Every key names a live edge.** A key that matches no id is dead — the code reads as a
   working feature and evaluates for nothing.
2. **A predicate is FALSE whenever a comparison in its own guard cell is false.** One-way on
   purpose: a cell's other conjuncts ("tests green", "user approved") are not in the state file,
   so a true predicate proves nothing — but a predicate that stays true while the state
   contradicts its own guard is wrong, and that is the inversion this map shipped.
3. **A predicate whose guard cell has no parseable comparison must be declared** in `UNCHECKED`
   with a reason. `'14'`'s guard is "journeys not red" and its predicate read `has_ui` — dimming
   on a dimension its guard never mentions. Declaring it is cheap; doing it by accident is what
   happened.

Every check runs twice: once against the real file, and once against a copy with that specific
defect planted, which MUST come back red. A check that cannot fail is not evidence.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

VIEWER = paths.VIEWER

# Predicates whose guard cell holds no comparison this file can parse, each with the reason it is
# still worth keeping. A predicate outside the grammar is then a decision someone wrote down,
# rather than the thing that goes unnoticed.
UNCHECKED = {
    "17": "the cell is one disjunction — (A|B and no milestone remains) or (C and integration "
          "open) — so there is no conjunct to test in isolation; the predicate mirrors it whole",
    "28": "`verdict == BLOCK or any S1/S2 present` is a disjunction, and `bugs[].severity` is not "
          "a comparison this grammar reads; the predicate covers the verdict half only",
}

# Comparisons that appear in real guard cells, mapped to the state path they read. Deliberately
# small: this grammar exists to catch a predicate pointing at the wrong field or the wrong
# polarity, not to become a second implementation of the guard language.
COMPARISONS = [
    (re.compile(r"^spec_path == null$"), ("spec_path", "eq", None)),
    (re.compile(r"^spec_path != null$"), ("spec_path", "ne", None)),
    (re.compile(r"^branching == ([A-D])$"), ("context.branching", "eq", 1)),
    (re.compile(r"^branching ∈ \{([A-D,]+)\}$"), ("context.branching", "in", 1)),
    (re.compile(r"^context\.has_ui == (true|false)$"), ("context.has_ui", "eq", 1)),
    (re.compile(r"^integration\.branch == null$"), ("integration.branch", "eq", None)),
    (re.compile(r"^integration\.branch != null$"), ("integration.branch", "ne", None)),
    (re.compile(r"^verdict == ([A-Z-]+)$"), ("qa.verdict", "eq", 1)),
]

# A value each path can hold that SATISFIES nothing in the grammar — used to build the state that
# must switch a predicate off. `context.branching` is the odd one: every letter satisfies some
# guard, so the violating value has to be chosen per-constraint rather than fixed here.
FALSIFY = {
    "spec_path": ["docs/specs/x.md", None],
    "context.branching": ["A", "B", "C", "D"],
    "context.has_ui": [True, False, None],
    "integration.branch": ["integration/x", None],
    "qa.verdict": ["PASS", "PASS-WITH-ISSUES", "BLOCK", None],
}


def graph_block(js):
    """The viewer's embedded GRAPH, which is data-only and therefore parseable."""
    a = js.index("/*__GRAPH_BEGIN__*/")
    b = js.index("/*__GRAPH_END__*/")
    s = js[a:b]
    return json.loads(s[s.index("{"):s.rindex("}") + 1])


def applies_source(js):
    """The `const ctx = …` through `};` span — the helpers and the map, as written."""
    a = js.find("const ctx = s =>")
    b = js.find("};", js.find("const APPLIES = {"))
    if a < 0 or b < 0:
        return ""
    return js[a:b + 2]


def applies_keys(js):
    """The keys of APPLIES, read from the source rather than trusted."""
    src = js[js.find("const APPLIES = {"):]
    src = src[:src.find("};") + 2]
    return re.findall(r"^\s*'([^']+)':", src, re.M)


def conjuncts(cell):
    """A guard cell split into top-level `and` terms, with trailing prose stripped.

    Parenthesised groups stay whole: `(no rerun-worthy finding or re-run budget spent)` is one
    term and matches nothing, which is the right answer. Splitting inside them would turn an
    `or` into two `and`s and invent constraints the guard never made.
    """
    cell = cell.split(" — ")[0].strip()
    out, depth, buf = [], 0, ""
    i = 0
    while i < len(cell):
        c = cell[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if depth == 0 and cell[i:i + 5] == " and ":
            out.append(buf.strip())
            buf, i = "", i + 5
            continue
        buf += c
        i += 1
    out.append(buf.strip())
    return [t for t in out if t]


def constraints(cell):
    """Every (path, op, value) this grammar can read out of one guard cell."""
    found = []
    for term in conjuncts(cell):
        if " or " in term:
            continue                      # a disjunction is not a constraint on its own
        for rx, (path, op, val) in COMPARISONS:
            m = rx.match(term)
            if not m:
                continue
            v = val
            if val == 1:
                v = m.group(1)
                if v == "true":
                    v = True
                elif v == "false":
                    v = False
                elif op == "in":
                    v = v.split(",")
            found.append((path, op, v))
            break
    return found


def put(state, path, value):
    node = state
    parts = path.split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = value


def violating_states(path, op, value):
    """States that make this one comparison FALSE, and nothing else in the grammar true."""
    out = []
    for candidate in FALSIFY[path]:
        if op == "eq" and candidate == value:
            continue
        if op == "ne" and candidate != value:
            continue
        if op == "in" and candidate in value:
            continue
        s = {"milestones": [{"id": "m1", "delivered": False}]}
        put(s, path, candidate)
        out.append((candidate, s))
    return out


def evaluate(src, cases):
    """Run the real predicates under node. `cases` is [(id, state)]; returns [bool|None]."""
    script = (src + "\nconst CASES = " + json.dumps(cases) + ";\n"
              "console.log(JSON.stringify(CASES.map(([id, s]) =>\n"
              "  (APPLIES[id] ? !!APPLIES[id](s) : null))));\n")
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as f:
        f.write(script)
        tmp = f.name
    try:
        run = subprocess.run(["node", tmp], capture_output=True, text=True, timeout=30)
        if run.returncode != 0:
            raise RuntimeError((run.stderr or run.stdout).strip()[:400])
        return json.loads(run.stdout)
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)


# ── the checks ────────────────────────────────────────────────────────────────────────────

def check_every_key_names_a_live_edge(js):
    G = graph_block(js)
    live = {e[0] for lst in G["EDGES"].values() for e in lst}
    keys = applies_keys(js)
    if not keys:
        return "APPLIES is empty or unreadable — nothing dims, and this whole suite is inert"
    dead = [k for k in keys if k not in live]
    if dead:
        return ("APPLIES keys " + ", ".join(sorted(dead)) + " match no edge in this graph — the "
                "code reads as a working feature and evaluates for nothing, which is exactly how "
                "a wholesale edge renumbering went unnoticed once")
    return ""


def check_unparseable_guards_are_declared(js):
    G = graph_block(js)
    cells = {e[0]: e[2] for lst in G["EDGES"].values() for e in lst}
    bad = []
    for k in applies_keys(js):
        if k not in cells:
            continue                      # the check above owns dead keys
        if not constraints(cells[k]) and k not in UNCHECKED:
            bad.append(f"`{k}` dims on a guard this suite cannot read (\"{cells[k][:52]}…\") and "
                       f"is not declared in UNCHECKED — nothing relates the predicate to its guard")
    stale = [k for k in UNCHECKED if k not in cells]
    if stale:
        bad.append("UNCHECKED excuses " + ", ".join(sorted(stale)) + ", which is not an edge id")
    return "; ".join(bad)


def check_parseable_guards_have_a_predicate(js):
    G = graph_block(js)
    keys = set(applies_keys(js))
    bad = []
    for lst in G["EDGES"].values():
        for eid, _to, cell in lst:
            if constraints(cell) and eid not in keys:
                bad.append(f"edge `{eid}` (\"{cell[:44]}…\") tests state this viewer holds, and "
                           f"has no predicate — the button never dims, so a run that cannot take "
                           f"that edge is drawn as though it could")
    return "; ".join(bad)


def check_predicates_agree_with_their_guard(js):
    """The one that catches an inversion: state contradicts the guard, predicate must go false."""
    G = graph_block(js)
    cells = {e[0]: e[2] for lst in G["EDGES"].values() for e in lst}
    src = applies_source(js)
    if not src:
        return "APPLIES is not a block this checker can extract, so nothing here was run"

    cases, meta = [], []
    for k in applies_keys(js):
        if k not in cells or k in UNCHECKED:
            continue
        for path, op, value in constraints(cells[k]):
            for candidate, state in violating_states(path, op, value):
                cases.append([k, state])
                meta.append((k, path, candidate, cells[k]))
    if not cases:
        return "no predicate had a parseable guard to test against — the grammar matched nothing"

    try:
        got = evaluate(src, cases)
    except Exception as exc:                                    # noqa: BLE001
        return f"the predicates could not be evaluated under node: {exc}"

    bad = []
    for fired, (k, path, candidate, cell) in zip(got, meta):
        if fired:
            bad.append(f"`{k}` stays true with {path}={candidate!r}, which its own guard "
                       f"(\"{cell[:44]}…\") forbids — the button is drawn available for a run "
                       f"that cannot take it")
    return "; ".join(sorted(set(bad)))


CHECKS = [
    ("every-applies-key-names-a-live-edge", check_every_key_names_a_live_edge,
     [("  '1':  s => !s.spec_path,", "  '1':  s => !s.spec_path,\n  '18c': s => true,")]),
    ("a-guard-this-suite-cannot-read-is-declared", check_unparseable_guards_are_declared,
     [("  '1':  s => !s.spec_path,", "  '1':  s => !s.spec_path,\n  '14': s => true,")]),
    ("every-state-testable-guard-has-a-predicate", check_parseable_guards_have_a_predicate,
     [("  '13': s => ctx(s).has_ui === false,", "")]),
    ("a-predicate-agrees-with-its-own-guard", check_predicates_agree_with_their_guard,
     [("  '2':  s => !!s.spec_path,", "  '2':  s => !s.spec_path,"),
      ("  '13': s => ctx(s).has_ui === false,", "  '13': s => ctx(s).has_ui === true,"),
      ("  '7':  s => ctx(s).branching === 'D',", "  '7':  s => ctx(s).branching !== 'D',")]),
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
            except Exception:                                   # noqa: BLE001
                still_green = False      # a checker that throws on the defect has still noticed it
            if still_green:
                dead.append(f"{name}: stayed green with `{old.strip()[:46]}…` broken")

    for d in dead:
        print("DEAD  " + d)
    n = len(CHECKS)
    print(f"\n{n - len(failures)}/{n} checks pass, {len(dead)} inert")
    return 1 if failures or dead else 0


sys.exit(main())
