#!/usr/bin/env python3
"""Real-subagent evals — a real orchestrator, real inflight, real code, judged on real artifacts.

    python3 run_real_eval.py tests/R1-journals-as-it-goes.md --setup   # build the repo, print the brief
    #   ...the top-level orchestrator spawns a mock-root subagent with that brief...
    #   ...which spawns REAL milestone agent subagents, which write REAL code...
    python3 run_real_eval.py tests/R1-journals-as-it-goes.md --check   # emit the evidence bundle
    python3 run_real_eval.py --list

## Why this exists beside `../runs/`

`../runs/` scripts the agent, and a script cannot fail the milestone agent's half of the contract. It writes
perfect journal lines, in order, with correct `seq`, appended before it returns — **by construction**.
But almost every demand in the journal contract is on the *milestone agent*: append as you leave each node rather
than reconstructing on the way out, write a `detail` useful to a reader with none of your context,
heartbeat through a long node, never touch a sibling's file, `notes` required on completion. None of
those can be observed against a fixture that satisfies them by definition, and the likeliest real
failure — a thin, useless `detail`, or a journal written from memory at the end — is invisible there.

So here both sides are real. Attribution does not require a scripted counterpart: the artifacts are
already separated by author. Journal shape is the milestone agent's. State-file writes are the root's.

`../runs/` keeps its place for the two things a real agent cannot be relied on to do: lie in one
exact way (a bundle that hides precisely one retry), and die mid-node.

## Deterministic first, judged second

A test declares a **start**, an expected **path**, and an **end** — so most of what matters is a
mechanical comparison, and `--check` runs it. What it cannot express is quality: whether a `detail`
would actually help the next milestone, whether a trail is uniformly cheerful, whether a journal
reads as though it were written after the fact.

That is what the judge is for, and the judge is the **top-level orchestrator** — which did none of
this work and is not reporting on itself. `--check` hands it an evidence bundle: expected path vs
actual, every assertion with its result, and the artifacts to read. Judging without that evidence
would be an opinion; the evidence without judgement misses everything a predicate cannot say.
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
GRAPH = HERE.parent.parent                      # .../skills/sdlc-graph
PLUGIN = GRAPH.parent.parent                    # .../plugins/sdlc-graph
TESTS = HERE / "tests"
SCRATCH_ROOT = HERE / ".scratch"


def blocks(text):
    return {m.group(1): m.group(2) for m in
            re.finditer(r"^```(\w+)\n([\s\S]*?)^```$", text, re.M)}


def load(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    b = blocks(text)
    for need in ("setup", "brief", "assert", "judge"):
        if need not in b:
            raise SystemExit(f"{path}: no ```{need} block")
    return {"path": pathlib.Path(path),
            "title": (re.search(r"^#\s+(.+)$", text, re.M) or [None, path])[1],
            "claim": (re.search(r"^\*\*Claim:\*\*\s*(.+)$", text, re.M) or [None, ""])[1].strip(),
            "setup": json.loads(b["setup"]), "brief": b["brief"].strip(),
            "asserts": b["assert"], "judge": b["judge"].strip()}


def scratch_for(t):
    return SCRATCH_ROOT / t["path"].stem


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=check).stdout.strip()


def do_setup(t):
    """A REAL repository, with real test scripts that really run. The milestone agent has to do actual work —
    that is the entire difference between this path and `../runs/`."""
    root = scratch_for(t)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    for rel, body in (t["setup"].get("repo") or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")

    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    git(root, "config", "user.email", "eval@example.invalid")
    git(root, "config", "user.name", "sdlc-graph eval")
    git(root, "add", "-A")
    git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "base: project skeleton")

    state = t["setup"]["state"]
    state.setdefault("context", {})["main_branch"] = "main"

    # The ignore rule lands and is COMMITTED before the run directory exists — the order `INTAKE`
    # itself is required to follow. Reversed, the state file is a tracked change every later
    # `git status` has to explain away, and R12's bare status check would fail on a correct run.
    (root / ".gitignore").write_text("docs/graph-runs/\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "base: ignore the run directory")

    rundir = root / "docs" / "graph-runs" / state["run_id"]
    (rundir / "journals").mkdir(parents=True, exist_ok=True)
    (rundir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return root


def read_artifacts(root, run_id):
    sp = root / "docs" / "graph-runs" / run_id / "state.json"
    state = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else None
    journals = {}
    for p in sorted((root / "docs" / "graph-runs" / run_id / "journals").glob("milestone-*.jsonl")):
        # `milestone-2.jsonl` -> "2". The old split assumed a `<run-id>-` prefix that the run
        # directory removed, and left `mid` as the whole stem — matching nothing in history[].
        mid = p.stem.split("milestone-", 1)[-1]
        lines, torn = [], 0
        for raw in p.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                lines.append(json.loads(raw))
            except json.JSONDecodeError:
                torn += 1
        journals[mid] = {"lines": lines, "torn": torn, "path": str(p)}
    return state, journals


def evaluate(source, env):
    env["__builtins__"] = {}
    out = []
    for raw in source.splitlines():
        expr, _, why = raw.partition("#")
        expr = expr.strip()
        if not expr:
            continue
        try:
            # Test expressions live in tests/*.md, committed and reviewed like the rest of this
            # directory. Builtins are stripped; a stray name fails loudly instead of reaching disk.
            ok = bool(eval(expr, env))                       # noqa: S307
            out.append({"expr": expr, "why": why.strip(), "ok": ok, "error": None})
        except Exception as exc:
            out.append({"expr": expr, "why": why.strip(), "ok": False,
                        "error": f"{type(exc).__name__}: {exc}"})
    return out


def do_check(t):
    root = scratch_for(t)
    if not root.exists():
        raise SystemExit(f"{t['path'].name}: no scratch run — run --setup, then the agent")
    run_id = t["setup"]["state"]["run_id"]
    state, journals = read_artifacts(root, run_id)

    actual = [[h.get("from"), h.get("to")] for h in ((state or {}).get("history") or [])
              if isinstance(h, dict)]
    expected = t["setup"].get("expect_path")
    path_report = None
    if expected is not None:
        path_report = {"expected": expected, "actual": actual, "matches": expected == actual}

    # Every `node_done` across every journal, and a helper for "did this node get one". Most
    # assertions are about these rather than raw lines, and spelling that out in each test would
    # bury the claim under list comprehensions.
    node_done = [l for v in journals.values() for l in v["lines"]
                 if isinstance(l, dict) and l.get("event") == "node_done"]
    env = {"state": state or {}, "journals": {k: v["lines"] for k, v in journals.items()},
           "torn": {k: v["torn"] for k, v in journals.items()},
           "history": (state or {}).get("history") or [],
           # `in_flight`, top level. This read `cursor.milestones` — the SCHEMA-4 shape, where
           # `cursor` was an object. At schema 5 `cursor` is a number, so this resolved to `[]`
           # on every run and any assertion using `inflight` was vacuously true.
           "inflight": (state or {}).get("in_flight") or [],
           "milestones": (state or {}).get("milestones") or [], "path": actual,
           "nd": node_done, "done": lambda n: any(l.get("node") == n for l in node_done),
           "json": json, "re": re, "any": any, "all": all, "len": len, "sum": sum, "max": max,
           "min": min, "sorted": sorted, "set": set, "str": str, "int": int, "abs": abs,
           "list": list, "dict": dict, "bool": bool, "isinstance": isinstance}
    results = evaluate(t["asserts"], env)

    branches = git(root, "branch", "--format=%(refname:short)", check=False).splitlines()
    log = git(root, "log", "--oneline", "--all", check=False).splitlines()
    main_clean = git(root, "status", "--porcelain", check=False) == ""

    bundle = {
        "test": t["path"].name, "claim": t["claim"], "scratch": str(root),
        "path": path_report,
        "assertions": results,
        "assertions_passed": sum(1 for r in results if r["ok"]),
        "assertions_total": len(results),
        # An assertion that RAISED is a broken TEST, not a failed run, and the two must not read
        # alike. R1 carried `not milestone agents` — rename residue, and not valid Python — which
        # scored as one more failed assertion among many while the run itself was fine. A judge
        # reading "17 of 18 passed" has no way to tell that the one was the harness.
        "assertions_unevaluable": [{"expr": r["expr"], "error": r["error"]}
                                   for r in results if r["error"]],
        "world": {"branches": branches, "commits": log, "working_tree_clean": main_clean},
        "journals": {k: {"lines": len(v["lines"]), "torn": v["torn"], "path": v["path"]}
                     for k, v in journals.items()},
        "judge_rubric": t["judge"],
    }
    print(json.dumps(bundle, indent=2, ensure_ascii=False))
    broken = [r for r in results if r["error"]]
    if broken:
        print(f"\nHARNESS DEFECT: {len(broken)} assertion(s) could not be EVALUATED — the test is "
              f"broken, not the run. Fix these before reading any verdict:", file=sys.stderr)
        for r in broken:
            print(f"  {r['expr']}\n    {r['error']}", file=sys.stderr)

    failed = [r for r in results if not r["ok"]]
    if path_report and not path_report["matches"]:
        failed.append({"expr": "path == expect_path"})
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test", nargs="?")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for p in sorted(TESTS.glob("*.md")):
            if p.name == "README.md":
                continue
            t = load(p)
            # The PATH, not the bare name — `--list` printed a name the runner then rejected with a
            # FileNotFoundError, so its output could not be pasted back into it.
            print(f"  {str(p.relative_to(HERE)):44} {t['claim']}")
        return 0
    if not args.test:
        ap.error("give a test, or --list")
    t = load(args.test)

    if args.setup:
        root = do_setup(t)
        sysmsg = (HERE / "SYSTEM.md").read_text(encoding="utf-8")
        full = (sysmsg + "\n\n---\n\n# This run\n\n" + t["brief"])
        full = (full.replace("{{SCRATCH}}", str(root)).replace("{{GRAPH}}", str(GRAPH))
                    .replace("{{PLUGIN}}", str(PLUGIN)))
        print(f"scratch: {root}\n{'=' * 78}")
        print(full)
        return 0
    if args.check:
        return do_check(t)
    ap.error("pass --setup or --check")


if __name__ == "__main__":
    sys.exit(main())
