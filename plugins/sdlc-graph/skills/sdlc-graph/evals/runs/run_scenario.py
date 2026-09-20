#!/usr/bin/env python3
"""Run evals — scenarios that execute, and are judged on what they left behind.

    python3 runs/run_scenario.py runs/scenarios/01-happy-milestone.md --setup   # build it, print the brief
    python3 runs/run_scenario.py runs/scenarios/01-happy-milestone.md --check   # assert against what it produced
    python3 run_scenario.py --list                             # every scenario and its one-line claim
    python3 run_scenario.py --self-test                        # every scenario's control must fail

**Nothing here asks a model whether it did well.** The orchestrator under test is an agent, so it is
not deterministic — but the artifacts it leaves are: a state file, a set of journals, a git repo.
Every assertion reads those, offline, and could be re-run by someone who was not there. A judged
transcript would be a self-report from the thing being tested, which is the exact failure the return
gate exists to prevent, reproduced one layer up in the test harness.

A scenario is one Markdown file with three fenced blocks:

  ```setup      JSON — the starting state file, and the mock milestone agent's script per milestone
  ```brief      the prompt handed to the orchestrator subagent, verbatim
  ```assert     one Python expression per line, `#` for a comment; every one must be true

`assert` runs with `state` (the parsed state file), `journals` ({milestone: [lines]}), `scratch`
(pathlib.Path), and `history` (state["history"]) in scope.

**Every scenario also carries a `control` block** — a mutation applied to the *artifacts*, after
which the assertions must FAIL. A scenario whose assertions pass on deliberately broken artifacts is
a demo. `--self-test` runs only that, needs no agent, and is the part that keeps this suite honest.
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

HERE = paths.RUNS
RUNS = paths.SCENARIOS
# Under `evals/`, not under `evals/runs/` — `.gitignore` carries `**/evals/.scratch/`, and a
# scratch tree one directory deeper would be committed by the next `git add -A`.
SCRATCH_ROOT = paths.EVALS / ".scratch"

# The one artifact read back by name rather than by glob. Named once, so the brief and the reader
# cannot drift — which they did, silently, for two commits.
REPLY_FILE = "agent-reply.txt"


def blocks(text):
    """{name: body} for every ```<name> … ``` fence in the file."""
    return {m.group(1): m.group(2) for m in
            re.finditer(r"^```(\w+)\n([\s\S]*?)^```$", text, re.M)}


def load(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    b = blocks(text)
    missing = [k for k in ("setup", "brief", "assert", "control") if k not in b]
    if missing:
        raise SystemExit(f"{path}: scenario has no {', '.join(missing)} block")
    title = re.search(r"^#\s+(.+)$", text, re.M)
    claim = re.search(r"^\*\*Claim:\*\*\s*(.+)$", text, re.M)
    return {"path": pathlib.Path(path), "title": title.group(1) if title else path,
            "claim": claim.group(1).strip() if claim else "",
            "setup": json.loads(b["setup"]), "brief": b["brief"].strip(),
            "asserts": b["assert"], "control": b["control"]}


def scratch_for(scenario):
    return SCRATCH_ROOT / scenario["path"].stem


def do_setup(scenario):
    """Build a scratch run directory: the state file, the mock milestone agent scripts, and a git repo when the
    scenario needs one. Wiped first — a scenario that inherits the last run's artifacts can pass on
    them."""
    root = scratch_for(scenario)
    if root.exists():
        shutil.rmtree(root)
    rundir = root / "docs" / "graph-runs" / scenario["setup"]["state"]["run_id"]
    (rundir / "journals").mkdir(parents=True)
    # The run directory is gitignored in a real project, and the scratch repo below is a real
    # git repo — without this, `git add -A` sweeps the run state into the commit and R12's bare
    # `git status` no longer means what the spec says it means.
    (root / ".gitignore").write_text("docs/graph-runs/\n", encoding="utf-8")

    setup = scenario["setup"]
    state = setup["state"]
    run_id = state["run_id"]
    (rundir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    for mid, script in (setup.get("agents") or {}).items():
        (root / f"agent-{mid}.script.json").write_text(json.dumps(script, indent=2) + "\n",
                                                      encoding="utf-8")

    # Journals a scenario starts WITH. Not every scenario begins at the start of a milestone:
    # scenario 07 opens after one has completed and returned, and its whole claim is that an
    # interrogation adds nothing to the record. Without a way to seed the journal there was nothing
    # for "did not grow" to be measured against, so the assertion could only ever fail — the
    # scenario asserted a milestone had happened while the harness could only build a run where
    # none had.
    # Snapshots a traced run starts WITH. The hook that writes `history/` is a Claude Code
    # PostToolUse hook and cannot fire inside this harness, so a scenario about tracing seeds the
    # directory and then asserts what the ORCHESTRATOR did to it — which is nothing. That is the
    # rule worth testing here: `history/` has exactly one writer and it is not the orchestrator.
    if setup.get("history"):
        (rundir / "history").mkdir(exist_ok=True)
        for name in setup["history"]:
            (rundir / "history" / name).write_text("{}\n", encoding="utf-8")

    for mid, lines in (setup.get("journals") or {}).items():
        (rundir / "journals" / f"milestone-{mid}.jsonl").write_text(
            "".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lines), encoding="utf-8")
    if setup.get("git"):
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "README.md").write_text("scratch\n", encoding="utf-8")
        for cmd in (["add", "-A"], ["-c", "user.email=e@x", "-c", "user.name=n", "commit", "-qm", "base"]):
            subprocess.run(["git", "-C", str(root), *cmd], check=True)
    return root


def read_artifacts(root, run_id):
    state_path = root / "docs" / "graph-runs" / run_id / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    journals = {}
    for p in sorted((root / "docs" / "graph-runs" / run_id / "journals").glob("milestone-*.jsonl")):
        mid = p.stem.rsplit("milestone-", 1)[-1]
        lines = []
        for raw in p.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if raw:
                try:
                    lines.append(json.loads(raw))
                except json.JSONDecodeError:
                    lines.append({"_torn": raw})
        journals[mid] = lines
    # Some scenarios are about something an actor SAID, not something it wrote to the run — a milestone agent
    # declining an instruction leaves no state change, which is exactly what makes it worth checking.
    # The brief tells the actor to write its reply here, so the assertion still reads an artifact
    # rather than a transcript someone has to be trusted to summarise.
    reply_path = root / REPLY_FILE
    reply = reply_path.read_text(encoding="utf-8") if reply_path.exists() else ""
    hist = root / "docs" / "graph-runs" / run_id / "history"
    snapshots = sorted(p.name for p in hist.glob("*.json")) if hist.exists() else []
    return state, journals, reply, snapshots


def evaluate(source, state, journals, root, reply="", snapshots=()):
    """Every non-comment line is an expression that must be truthy. Returns [(line, why)].

    **On `eval` here.** The expressions come from `runs/scenarios/*.md`, which are committed to this repo and
    reviewed like any other file in it — they are test code that happens to live in Markdown, at the
    same trust level as this script. They are never fetched, never written by a run, and never taken
    from a state file. `ast.literal_eval` cannot express what an assertion needs (`len(history) == 5`,
    `all(...)`), and a bespoke expression parser would be a second thing to get wrong. Builtins are
    stripped anyway, so a stray expression fails loudly rather than reaching the filesystem.
    """
    # Builtins are stripped, so anything an assertion may call has to be named here. A missing name
    # surfaces as a failed assertion rather than a silent skip — which is how `max` was found absent.
    env = {"state": state or {}, "journals": journals, "scratch": root,
           "history": (state or {}).get("history") or [], "milestones": (state or {}).get("milestones") or [],
           "m1": (lambda: ([m for m in ((state or {}).get("milestones") or [])
                            if m.get("id") == 1] or [{}])[0]),
           "inflight": (state or {}).get("in_flight") or [],
           "milestones": (state or {}).get("milestones") or [],
           "m1": (lambda: ([m for m in ((state or {}).get("milestones") or [])
                            if m.get("id") == 1] or [{}])[0]), "json": json, "re": re, "any": any,
           "all": all, "len": len, "sum": sum, "sorted": sorted, "set": set, "str": str, "int": int,
           "max": max, "min": min, "abs": abs, "list": list, "dict": dict, "bool": bool,
           "reply": reply, "snapshots": list(snapshots)}
    # Passed as GLOBALS, not locals. A generator expression gets its own scope, and that scope
    # resolves names against globals only — so with env as locals, `all(len(x) for x in y)` raised
    # NameError on `len` while the identical expression outside a genexp worked. Found by a
    # scenario's own ideal artifacts failing its own assertions, which is what that check is for.
    env["__builtins__"] = {}
    failures = []
    for raw in source.splitlines():
        expr, _, why = raw.partition("#")
        expr = expr.strip()
        if not expr:
            continue
        try:
            if not eval(expr, env):                                # noqa: S307 — fixture expressions
                failures.append((expr, why.strip()))
        except Exception as exc:
            failures.append((expr, f"raised {type(exc).__name__}: {exc}"))
    return failures


def do_check(scenario):
    root = scratch_for(scenario)
    run_id = scenario["setup"]["state"]["run_id"]
    if not root.exists():
        raise SystemExit(f"{scenario['path'].name}: no scratch run — did --setup and the agent run?")
    state, journals, reply, snapshots = read_artifacts(root, run_id)
    return evaluate(scenario["asserts"], state, journals, root, reply, snapshots)


def check_brief(scenario):
    """Do the paths the brief hands the orchestrator actually resolve? Returns [problem, …].

    A scenario can be perfectly satisfiable and perfectly breakable and still be **unrunnable**,
    because `--self-test` reads `ideal_artifacts` and never touches the paths in the brief. All eight
    briefs were unrunnable for two commits: a `lane` -> `milestone` rename rewrote `lane-1.script.json`
    into `milestone 1.script.json` — a file `--setup` never creates, with a space in it, unquoted in a
    shell command. Scenario 07 was worse, because it still *passed*: the brief said to write the
    reply to `milestone reply.txt` and `read_artifacts` reads `agent-reply.txt`, so the assertion
    scored an empty string against a scenario whose whole point is what an agent said.

    Nothing static could see it. The check is cheap and it is here rather than in `spec_consistency.py`
    because it needs the scenario's own `setup` block to know what `--setup` would create.
    """
    brief, setup = scenario["brief"], scenario["setup"]
    ids = [str(k) for k in (setup.get("agents") or {})]
    # What do_setup() writes — computed, never a second literal list.
    creates = {f"agent-{mid}.script.json" for mid in ids}
    creates.add(f"docs/graph-runs/{setup['state']['run_id']}/state.json")
    problems = []

    # Scoped to the mock-agent command, because that is where a path is a shell WORD. Elsewhere a
    # filename is prose and the space after it is a sentence. Each flag sits on its own line, so
    # the rest of the line IS the argument — which is exactly why an embedded space breaks it.
    for flag, value in re.findall(r"(--script|--journal|--bundle-out)\s+\{\{SCRATCH\}\}/(.+)$",
                                  brief, re.M):
        value = value.rstrip(" \\")
        if " " in value:
            problems.append(f"`{flag} {value}` has a space in the path and is unquoted — the shell "
                            f"splits it into two arguments, so the command is broken whatever the "
                            f"file is called")

    # Every --script is an INPUT: it must already exist, or the mock agent cannot start.
    for path in re.findall(r"--script\s+\{\{SCRATCH\}\}/(\S+)", brief):
        for concrete in ([path.replace("<N>", mid) for mid in ids] if "<N>" in path else [path]):
            if concrete not in creates:
                problems.append(f"the brief runs the mock agent with `--script {concrete}`, which "
                                f"`--setup` never creates (it writes {sorted(creates)})")

    # The reply file is an OUTPUT, and the only one read back by name rather than by glob.
    if "reply" in brief.lower() and REPLY_FILE not in brief:
        problems.append(f"the brief asks for a written reply but never names `{REPLY_FILE}` — "
                        f"read_artifacts() reads exactly that path, so the assertion would score "
                        f"an empty string and the scenario would pass having tested nothing")
    return problems


# The six nodes the milestone agent runs. Its exits out of them are replayed on its word, so each
# carries the orchestrator's `verified`. Everything else is a transition the orchestrator took
# itself — including `GATE_B`'s exit, per R3: "its exits are yours".
AGENT_OWNED = {"BRANCH", "IMPLEMENT", "TEST", "GATE_A", "E2E", "DEBUG"}


def check_ideal(scenario):
    """Is `ideal_artifacts` a run the graph would actually produce? Returns [problem, …].

    `--self-test` asks two questions of the ideal — do the assertions hold on it, and does the
    control break them — and **neither of them asks whether the ideal is legal.** So a scenario can
    be hand-written to a model of the graph that the graph does not have, and every static suite
    stays green: the ideal satisfies the assertions because both were written from the same
    misunderstanding.

    That is not hypothetical. Scenario 01's ideal ended `GATE_B -> CLOSE_OUT` carrying a `verified`
    string, and `workflow-dispatch.md` R3 says **"`GATE_B` never appears as a `from` — its exits are
    yours"** while `state.md` says `verified` is *"`null` on a transition the orchestrator ran
    itself"*. The scenario therefore demanded an artifact no correct orchestrator can produce, and a
    real one driving it failed four assertions by being right.

    Two rules, both read from the spec rather than restated here:

    1. **Contiguous and declared** — each entry's `from` is the previous entry's `to`, and every
       `(from, to)` is a row in the transition table.
    2. **Authorship** — `verified` is the orchestrator's line about a node it did **not** run, so it
       is set exactly on transitions out of the six nodes the milestone agent owns, and null on
       every other. `GATE_B` is not one of them: the agent runs Gate B, the orchestrator takes its
       exit.
    """
    seeded = scenario["setup"]["state"]
    ideal = (scenario["setup"].get("ideal_artifacts") or {}).get("state")
    problems = []

    # The seeded state is a v5 file or it is not one. Every run-eval declared `schema_version: 5`
    # while carrying all four fields v5 removed — and `state.md` makes that an unconditional halt,
    # so strictly none of these scenarios should ever have started. Two orchestrators said so
    # independently, in the same words, and drove them anyway because the harness told them to.
    # `no-field-is-written-and-never-read` checks `walks/fixtures/` and has never looked at `runs/`.
    for dead, why in (("paused", "`stopped.kind` carries it"), ("blocked", "`stopped.kind` carries it"),
                      ("debug", "`debug_return_to` replaced it")):
        if dead in seeded:
            problems.append(f"the seeded state has a top-level `{dead}` — removed in schema 5, where "
                            f"{why}. It declares `schema_version` "
                            f"{seeded.get('schema_version')}, so state.md would BLOCK this run at entry")
    for i, m in enumerate(seeded.get("milestones") or []):
        if isinstance(m, dict) and "node" in m:
            problems.append(f"the seeded state has `milestones[{i}].node`, removed in schema 5 — a "
                            f"milestone's position is the last history[] entry carrying its id")

    # `node` is the run's position and `history[]` is how it got there, so the ideal's first
    # transition must LEAVE the node the run was seeded in. Scenario 01 seeded `STRATEGY` and its
    # ideal began at `BRANCH -> IMPLEMENT`, so a correct orchestrator recorded `STRATEGY -> BRANCH`
    # and failed four assertions by being right.
    history = (ideal or {}).get("history") or []
    seeded_history = seeded.get("history") or []
    if ideal and history and seeded.get("node"):
        # The ideal is the FINAL state, so it must continue the seeded trail rather than replace it.
        # Scenario 07 begins after a milestone has completed and adds nothing at all; scenario 01
        # begins at a node and adds five hops. Both are legal, and the rule that covers both is:
        # the seeded trail is a prefix of the ideal one, and the first hop AFTER it leaves the node
        # the run was seeded in.
        if history[:len(seeded_history)] != seeded_history:
            problems.append("the ideal's history does not start with the seeded history — the "
                            "scenario's final state contradicts its own starting point")
        elif len(history) == len(seeded_history):
            if seeded["node"] != (history[-1]["to"] if history else seeded["node"]):
                problems.append(f"the run is seeded at `node: {seeded['node']}` but its trail "
                                f"arrives at `{history[-1]['to']}` — `node` and `history[-1].to` "
                                f"must agree on a run that has moved")
        elif history[len(seeded_history)].get("from") != seeded["node"]:
            problems.append(f"the run is seeded at `node: {seeded['node']}` but the ideal's first "
                            f"NEW transition leaves `{history[len(seeded_history)].get('from')}` — "
                            f"the trail does not continue from where the run is, so the scenario "
                            f"and a correct orchestrator disagree about the first thing that happens")
    if not ideal:
        return problems
    prev = None

    paths.on_path()
    import graph_walk
    edges = graph_walk.parse_edges(paths.EDGES_MD
                                   .read_text(encoding="utf-8"))

    for i, h in enumerate(history):
        frm, to = h.get("from"), h.get("to")
        # The halt entry is not a transition and no row declares it — `state.md` § *Recording a
        # halt* gives it an empty `guard` for exactly that reason, and `graph_walk.py` has always
        # exempted it. This validator did not, so a scenario whose ideal recorded its halt
        # CORRECTLY was rejected twice: once for citing an undeclared edge, once for the missing
        # `verified` on a row nobody replayed. Found by fixing scenario 09's ideal to obey the spec.
        if to == "BLOCKED":
            if h.get("guard"):
                problems.append(f"ideal history[{i}] halts to BLOCKED but carries a guard — no row "
                                f"in edges.md declares an `on failure` exit, so `guard` is empty")
            prev = frm          # a halt does not move `node`; the trail continues from where it was
            continue
        if prev is not None and frm != prev:
            problems.append(f"ideal history[{i}] starts at {frm}, but history[{i - 1}] arrived at "
                            f"{prev} — the trail is not contiguous, so it is not a run")
        if (frm, to) not in edges:
            problems.append(f"ideal history[{i}] is {frm} -> {to}, which is not a row in the "
                            f"transition table")
        # Authorship. `verified` is what the orchestrator checked about work it did not witness.
        if frm in AGENT_OWNED and not h.get("verified"):
            problems.append(f"ideal history[{i}] ({frm} -> {to}) is the milestone agent's and "
                            f"carries no `verified` — the orchestrator recorded it on the agent's word")
        if frm not in AGENT_OWNED and h.get("verified"):
            problems.append(f"ideal history[{i}] ({frm} -> {to}) is the ORCHESTRATOR's own "
                            f"transition and carries `verified` — state.md: null on a transition "
                            f"the orchestrator ran itself. A scenario asserting this demands an "
                            f"artifact no correct orchestrator produces")
        prev = to
    return problems


def do_self_test(scenario):
    """The control: break the artifacts the way the `control` block says, and require the assertions
    to fail. Needs no agent — it is pure fixture surgery on a synthetic 'ideal' run."""
    ideal = scenario["setup"].get("ideal_artifacts")
    if not ideal:
        return None, f"{scenario['path'].name}: setup has no `ideal_artifacts` to break"
    state = ideal["state"]
    journals = {str(k): v for k, v in (ideal.get("journals") or {}).items()}
    reply = ideal.get("reply", "")
    snapshots = list(ideal.get("history") or [])

    clean = evaluate(scenario["asserts"], state, journals, scratch_for(scenario), reply, snapshots)
    if clean:
        return False, ("the IDEAL artifacts do not satisfy the scenario's own assertions "
                       f"({len(clean)} failed: {clean[0][0]}) — the scenario is unsatisfiable")

    env = {"state": json.loads(json.dumps(state)),
           "journals": json.loads(json.dumps(journals)), "reply": reply,
           "snapshots": list(snapshots)}
    exec(scenario["control"], {"__builtins__": {"len": len, "range": range, "list": list,
                                                "dict": dict, "str": str, "int": int}}, env)
    broken = evaluate(scenario["asserts"], env["state"], env["journals"],
                      scratch_for(scenario), env.get("reply", ""), env.get("snapshots") or [])
    if not broken:
        return False, ("the control mutation did not break a single assertion — this scenario "
                       "cannot fail, so passing it means nothing")
    return True, f"control breaks {len(broken)} assertion(s): {broken[0][0]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", nargs="?")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.list or args.self_test:
        scenarios = [load(p) for p in sorted(RUNS.glob("*.md")) if p.name != "README.md"]
        if args.list:
            for s in scenarios:
                print(f"  {s['path'].name:34} {s['claim']}")
            return 0
        failures = []
        for s in scenarios:
            ok, note = do_self_test(s)
            # Satisfiable-and-breakable is only half of honest. A scenario whose brief names files
            # that do not exist is unrunnable, and `ideal_artifacts` hides that completely.
            broken_paths = check_brief(s) + check_ideal(s)
            if ok and not broken_paths:
                print(f"ok    {s['path'].name:34} {note}")
                continue
            note = note if not ok else "; ".join(broken_paths)
            failures.append((s["path"].name, note))
            print(f"FAIL  {s['path'].name:34} {note}")
        print(f"\n{len(scenarios) - len(failures)}/{len(scenarios)} run-eval scenarios are "
              f"runnable, satisfiable, and broken by their own control")
        if failures:
            print("\nA scenario whose assertions survive deliberately broken artifacts is a demo, "
                  "and one whose brief points at files that do not exist is not even that.")
        return 1 if failures else 0

    if not args.scenario:
        ap.error("give a scenario, or --list / --self-test")
    scenario = load(args.scenario)

    if args.setup:
        root = do_setup(scenario)
        print(f"scratch: {root}\n")
        print(scenario["brief"].replace("{{SCRATCH}}", str(root)).replace("{{EVALS}}", str(paths.EVALS))
                                  .replace("{{SKILL}}", str(paths.SKILL))
                                  .replace("{{AGENT}}", str(paths.MILESTONE_AGENT)))
        return 0

    if args.check:
        failures = do_check(scenario)
        for expr, why in failures:
            print(f"FAIL  {expr}\n      {why}")
        print(f"\n{scenario['path'].name}: "
              f"{'PASS' if not failures else str(len(failures)) + ' assertion(s) failed'}")
        return 1 if failures else 0

    ap.error("pass --setup or --check")


if __name__ == "__main__":
    sys.exit(main())
