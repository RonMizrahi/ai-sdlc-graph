#!/usr/bin/env python3
"""
Walks a scripted run through the graph with every node body mocked, and checks four things
the graph is supposed to guarantee:

  1. Every transition is a declared edge in edges.md, quoting its guard verbatim.
  2. The resulting state file satisfies the invariants in state.md — bounds respected,
     counters keyed correctly, ledger well-formed, history contiguous, no invented values.
  3. **The run stops for the human exactly where a node declares a stop, and nowhere else.**
     Stops are read out of the `human` rows in nodes.md, so the walker cannot drift from the
     contracts; conditional stops (`PR`, `VERDICT`) are evaluated against the run's own state.
  4. **Every node and every edge is exercised by the fixture set as a whole.** A walk suite
     that never enters `CONSOLIDATE` is not evidence about `CONSOLIDATE`.
  5. **Every transition an agent produced was verified before it was written.** The milestone loop
     runs in an agent that returns a bundle; a milestone step therefore carries what the
     orchestrator checked (`agent.verified`), and a step that names no check is a transition
     written on an agent's word — the failure mode delegation introduces.

The coverage gate stays at 40 transitions / 20 nodes. `edges.md` authors those 40 as **30 rows**,
because the `DEBUG` fan-out and fan-in are written once as rules over their six callers; this file
expands them, so a shorter table never means thinner coverage. **If either number moves, the design
has grown something** — delegation was a change of `owner`, and nothing else.

Nothing real happens: no code is written, no agent spawned, no branch created. The point is
to exercise the graph's control flow — including the loops a happy-path run never reaches.

    python3 walks/graph_walk.py                            # every fixture, coverage enforced
    python3 walks/graph_walk.py walks/fixtures/strategy-a-happy.json   # one, coverage not enforced

Exit 0 when every walk is legal, every invariant holds, and coverage is total. No dependencies.
"""
import argparse
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

HERE = paths.WALKS
SPEC = paths.SKILL

# Keys that are not node names, so no `max attempts` row declares them. Two dispatch retries and
# the run-level reopen bound, which is declared on VERDICT.
NON_NODE_BOUNDS = {"GATE_A-dispatch": 1, "MILESTONE-dispatch": 1, "QA": "VERDICT"}


def parse_bounds(nodes_text):
    """Every loop bound, read from the node contract that declares it — never a second copy.

    A node's `max attempts` row IS its `DEBUG` round-trip's bound: `edges.md` row 19 says so, and
    that is the point of collapsing twelve rows into one. Before, the number lived in the node
    contract AND in the transition table AND in `SKILL.md` AND in this dict, and a real drift had
    `GATE_B ↔ DEBUG` reading 2 in one file and 3 in another.
    """
    bounds = {}
    sections = re.split(r"^###\s+`(\w+)`", nodes_text, flags=re.M)
    for name, body in zip(sections[1::2], sections[2::2]):
        row = re.search(r"^\|\s*\*\*max attempts\*\*\s*\|(.+)$", body, re.M)
        if not row:
            continue
        n = re.search(r"\*\*(\d+)[^*]*\*\*|^\s*(\d+)\b", re.sub(r"[`]", "", row.group(1)))
        bounds[name] = int(n.group(1) or n.group(2)) if n else None
    for key, src in NON_NODE_BOUNDS.items():
        bounds[key] = bounds.get(src) if isinstance(src, str) else src
    return bounds


BOUNDS = parse_bounds(paths.NODES_MD.read_text(encoding="utf-8"))

# The seven nodes an agent executes. A milestone block is a contiguous run of steps over these,
# starting at BRANCH and ending on the step INTO GATE_B — GATE_B's own exits read run-level state
# the agent is not given, so they are the orchestrator's.
AGENT_NODES = {"BRANCH", "IMPLEMENT", "TEST", "GATE_A", "E2E", "GATE_B", "DEBUG"}

# The world-sourced check each agent-owned node owes, from workflow-dispatch.md § The return gate.
# The bundle is agent-asserted throughout; these are the parts git, the re-run suite, the workflow
# journal and the filesystem can contradict. A milestone step naming none of them is the defect.
REQUIRED_VERIFICATION = {
    "BRANCH":    {"R4"},         # the branch exists and descends from base_sha
    "IMPLEMENT": {"R4", "R5"},   # the commits exist; the diff is non-empty and not a fake green
    "TEST":      {"R6"},         # the orchestrator re-ran the suite itself
    "GATE_A":    {"R7"},         # the runId is in the journal; `git diff --name-only` run by you
    "E2E":       {"R8"},         # the spec files exist on disk and are not mocked
    "GATE_B":    {"R6"},         # the re-run suite, against the whole diff
    "DEBUG":     {"R4"},         # the fix commit exists between the failing and passing runs
}

# Every key this walker reads off a step. Anything else in a fixture is an assertion that does
# nothing, so it is rejected rather than ignored — see the `unknown step key` problem below.
STEP_KEYS = {"from", "to", "edge", "milestone", "observation", "set", "skipped_gates",
             "stops", "halt", "e2e_specs", "agent", "agent_stop", "evidence", "violation"}

TERMINALS = {"DONE", "BLOCKED", "HANDOFF"}

# edges.md writes the strategy-D park as `[handoff]`; the state file calls that status HANDOFF.
ALIASES = {"[handoff]": "HANDOFF"}

STOP_TYPES = ("approval-after", "choice-after", "confirm-before", "await-external", "escalation")
# Stops the run_mode adds on top of the six. Declared at STRATEGY, never invented mid-run.
MODE_STOPS = ("checkpoint", "on-exception")

# A ledger entry blaming an uninstalled Playwright is the defect this pattern exists to catch:
# `requires` is for capabilities the run CANNOT obtain, and Playwright is an npm devDependency plus
# a browser download. The lookahead spares the legitimate entry — the one saying a `touches_ui`
# milestone shipped without its **Playwright specs** — which is a mandate violation, not a missing
# tool. See nodes.md § E2E and testing-standards-node.md § "a dependency, not a capability".
PLAYWRIGHT_BLAMED = re.compile(
    r"playwright(?!\s+(?:spec|test))[^.;]{0,60}?"
    r"(?:not installed|isn'?t installed|uninstalled|not available|unavailable|absent|missing)",
    re.I)

# The two node stops that are conditional rather than unconditional. Both conditions are stated
# in the node contracts; they live here as code because a walk has to evaluate them per-step.
#   PR       — `confirm-before` only when auto_open_mr == false (nodes.md § PR, human row)
#   VERDICT  — `escalation` only once the 2nd reopen is spent (nodes.md § VERDICT, max attempts)
def stop_applies(node, state):
    if node == "PR":
        return state["context"].get("auto_open_mr") is False
    if node == "VERDICT":
        return (state.get("attempts") or {}).get("QA", 0) >= BOUNDS["QA"]
    return True


def parse_edges(text):
    """(from, to) -> [(edge-id, guard), …] straight from the transition table.

    Two rows are *rules* rather than single transitions — the `DEBUG` fan-out and fan-in — and each
    expands here into its six caller pairs. That expansion is the whole reason the collapse from
    twelve hand-written rows to two is safe: the table gets shorter, the COVERAGE GATE does not.
    Every caller must still be traversed by some fixture, exactly as when the twelve rows existed.

    A rule is recognised by a `From` or `To` cell naming several nodes, or by naming the field
    `debug_return_to` — not by hard-coding DEBUG here, so a second rule in the same shape would
    expand without touching this parser.
    """
    clean = lambda x: re.sub(r"[`*]", "", x).strip()
    rows = [m for m in (re.match(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", ln)
                        for ln in text.splitlines()) if m]

    # The fan-out row names its callers; the fan-in row says "the node named in `debug_return_to`",
    # which is the same set. Read it once, from the table.
    callers = next((re.findall(r"`(\w+)`", m.group(2)) for m in rows
                    if len(re.findall(r"`(\w+)`", m.group(2))) > 1), [])

    def endpoints(cell):
        if "debug_return_to" in cell:
            return callers
        named = re.findall(r"`(\w+)`", cell)
        return named if len(named) > 1 else [clean(cell)]

    edges = collections.defaultdict(list)
    for m in rows:
        eid, guard = m.group(1), clean(m.group(4))
        froms, tos = endpoints(m.group(2)), endpoints(m.group(3))
        for frm in froms:
            for to in tos:
                f, t = ALIASES.get(frm, frm), ALIASES.get(to, to)
                # An expanded rule gets one id per caller, so coverage counts them separately.
                one = eid if len(froms) == len(tos) == 1 else f"{eid}·{f if len(froms) > 1 else t}"
                edges[(f, t)].append((one, guard))
    return edges


def node_ids(text):
    return set(re.findall(r"^###\s+`(\w+)`", text, re.M))


def parse_stops(text):
    """NODE -> declared human-stop type, read from the `human` row of each node contract.

    Derived, never maintained separately: SKILL.md's stop table says the six are "derived from
    the node contracts, not maintained separately — the two lists cannot drift apart", and a
    checker with its own hand-written copy would be the drift it exists to catch.
    """
    stops = {}
    sections = re.split(r"^###\s+`(\w+)`", text, flags=re.M)
    for name, body in zip(sections[1::2], sections[2::2]):
        row = re.search(r"^\|\s*\*\*human\*\*\s*\|(.+)$", body, re.M)
        if not row:
            stops[name] = "none"
            continue
        hits = [(body.index(t), t) for t in STOP_TYPES if t in row.group(1)]
        stops[name] = min(hits)[1] if hits else "none"
    return stops


def apply_set(state, path, value):
    node = state
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[int(part)] if part.isdigit() and isinstance(node, list) else node.setdefault(part, {})
    last = parts[-1]
    if last.isdigit() and isinstance(node, list):
        idx = int(last)
        node.append(value) if idx == len(node) else node.__setitem__(idx, value)
    else:
        node[last] = value


def milestone_by_id(state, mid):
    return next((m for m in state["milestones"] if m.get("id") == mid), None)


def walk(path, edges, catalogue, declared_stops):
    spec = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    state = json.loads(json.dumps(spec["initial_state"]), object_pairs_hook=collections.OrderedDict)
    problems = []
    edges_used = set()
    actual_stops = []
    in_milestone_block, milestone_seq = False, 0
    block_journal_nodes, block_trace_nodes = set(), set()

    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[`*]", "", s)).strip().lower()

    for i, step in enumerate(spec["steps"], 1):
        # A key this walker does not read is a fixture assertion that silently does nothing. That
        # is not hypothetical: `milestone-early-return-on-exception` carried `"milestone agent_stop"`
        # — a blind rename of `agent_stop` — so the one fixture written to exercise the on-exception
        # early return never exercised it, and passed on an unrelated `skipped_gates` instead.
        unknown = sorted(set(step) - STEP_KEYS)
        if unknown:
            problems.append(f"step {i}: unknown step key(s) {unknown} — this walker reads only "
                            f"{sorted(STEP_KEYS)}, so anything else is an assertion that does "
                            f"nothing. Check EVAL-INSTRUCTIONS.md § Writing a walk fixture")

        frm, to = step["from"], step["to"]
        halt = step.get("halt")
        declared = edges.get((frm, to))

        # A step names its EDGE, and the guard is looked up here. It used to carry the guard text
        # verbatim: 170 copies of 39 distinct strings across the corpus, the most-copied appearing
        # 17 times, so rewording one guard in `edges.md` was a seventeen-file JSON edit. An edge id
        # is also strictly more precise — it names one transition, where a guard string was matched
        # by substring and could match two. `history[].guard` is still written verbatim from
        # `edges.md` below, so what `state.md` actually requires is better served, not weakened.
        if "guard" in step:
            problems.append(f"step {i}: carries `guard`. Fixtures name the EDGE (\"edge\": \"12\"); "
                            f"the guard is read from edges.md, so it cannot drift and cannot be "
                            f"reworded here")
        eid = step.get("edge")
        if declared:
            match = next((e for e, _ in declared if e == eid), None)
            if match:
                edges_used.add(match)
                guard = next(d for e, d in declared if e == match)
            else:
                guard = ""
                problems.append(
                    f"step {i}: {frm} -> {to} names edge {eid!r}, which is not one of its declared "
                    f"edges ({', '.join(e for e, _ in declared)})")
        else:
            guard = ""
            if not (to == "BLOCKED" and halt):
                problems.append(f"step {i}: {frm} -> {to} is not a declared edge"
                                + ("" if to != "BLOCKED" else " and declares no halt"))

        # A bound-exhaustion or zero-match halt. Most are rendered in nodes.md as `on failure`
        # rows rather than numbered edges, so there is no guard to quote — `blocked` is what
        # makes the pause resumable, and it is required either way.
        if halt:
            if to != "BLOCKED":
                problems.append(f"step {i}: halt declared on a transition to {to}, not BLOCKED")
            if not halt.get("guards_tested"):
                problems.append(f"step {i}: halt at {frm} names no guards_tested — "
                                f"a zero-match halt has a SET of guards that all failed")
            if not halt.get("tried"):
                problems.append(f"step {i}: halt at {frm} records nothing in tried[]")

        # ---- the milestone block: executed by an agent, verified before it was written ---------
        # A step carries `agent` when its facts came from a milestone bundle. `verified` is what the
        # orchestrator checked against the world BEFORE writing it — the whole point of the gate.
        agent = step.get("agent")
        if agent:
            if frm not in AGENT_NODES:
                problems.append(f"step {i}: {frm} is not a node an agent executes — the agent owns "
                                f"{', '.join(sorted(AGENT_NODES))} and nothing else")
            # Inside the itinerary an agent only moves between its own nodes. The exception is the
            # step LEAVING GATE_B, which is the orchestrator evaluating 18/18c/18d on the agent's
            # evidence — that step closes the block.
            elif frm != "GATE_B" and to not in AGENT_NODES and to != "BLOCKED":
                problems.append(f"step {i}: milestone step {frm} -> {to} leaves the seven nodes an agent "
                                f"owns — its itinerary ends at GATE_B")
            if not in_milestone_block:
                if frm != "BRANCH":
                    problems.append(f"step {i}: milestone block opens at {frm}, not BRANCH — an agent is "
                                    f"spawned for a milestone, never resumed mid-itinerary")
                in_milestone_block, milestone_seq = True, 0
                block_journal_nodes, block_trace_nodes = set(), set()
            missing = REQUIRED_VERIFICATION.get(frm, set()) - set(agent.get("verified") or [])
            if missing:
                problems.append(f"step {i}: agent transition leaving {frm} records no "
                                f"{'/'.join(sorted(missing))} verification — a transition written "
                                f"on the agent's word is the failure delegation introduces")
            if frm == "IMPLEMENT" and not (step.get("evidence") or {}).get("commits"):
                problems.append(f"step {i}: agent IMPLEMENT -> {to} carries no evidence.commits — "
                                f"commit => bundle => record has nothing to check the branch against")
            if [s for s in (step.get("stops") or []) if s.get("type") in STOP_TYPES]:
                problems.append(f"step {i}: a node stop is declared inside a milestone block — an agent "
                                f"cannot reach the user; the orchestrator serves stops at the boundary")

            # ---- the journal: what the agent emitted WHILE it ran -------------------------------
            # R15 compares this against the trace, so a fixture that omits it cannot express the
            # defect R15 exists for. `journal: null` is how a fixture says "no journal" on purpose
            # (a schema_version 2 replay); an ABSENT key on a milestone step is the fixture forgetting.
            if "journal" not in agent:
                problems.append(f"step {i}: milestone step leaving {frm} declares no `journal` — R15 has "
                                f"nothing to check the bundle against, and a fixture that cannot "
                                f"express a hidden retry cannot prove the gate catches one")
            elif agent["journal"] is not None:
                entries = agent["journal"]
                if not any(e.get("event") == "node_done" and e.get("node") == frm for e in entries):
                    problems.append(f"step {i}: the journal records no node_done for {frm}, which "
                                    f"the agent is leaving — every node appends on exit, so a node "
                                    f"with no line is the fabrication signature R15 blocks on")
                for e in entries:
                    if e.get("milestone") not in (None, step.get("milestone")):
                        problems.append(f"step {i}: journal line names milestone {e.get('milestone')} "
                                        f"on a step for milestone {step.get('milestone')} — an agent "
                                        f"writes only its own file, and a shared one is the race "
                                        f"the per-milestone split removes")
                    if e.get("event") == "node_done" and not (e.get("headline") or "").strip():
                        problems.append(f"step {i}: a node_done line carries no headline — the "
                                        f"headline is the only thing pushed to the orchestrator "
                                        f"while the agent runs, so an empty one is a silent node")
                # `seq` is per MILESTONE, not per step — it counts appends across the whole block. Checking
                # it inside one step would pass a journal that restarted at 1 in every node, which is
                # what an agent reconstructing its story at the end would produce.
                seqs = [e["seq"] for e in entries if isinstance(e.get("seq"), int)]
                if seqs != sorted(seqs) or len(set(seqs)) != len(seqs):
                    problems.append(f"step {i}: journal `seq` is not increasing within the step ({seqs})")
                elif seqs and seqs[0] <= milestone_seq:
                    problems.append(f"step {i}: journal `seq` restarts at {seqs[0]} after {milestone_seq} "
                                    f"earlier in this agent — seq is per milestone and contiguous, so a "
                                    f"reset means the lines were not appended as the agent ran")
                if seqs:
                    milestone_seq = seqs[-1]
                # R15, as a walk invariant. Accumulated across the block and compared when it
                # closes: every node the journal recorded finishing must be a node the trace
                # actually leaves. A journal line for a node the trace never visits IS the hidden
                # retry — the agent fought with a node, wrote it down while it happened, and the
                # bundle came back showing one clean pass.
                block_journal_nodes.update(e.get("node") for e in entries
                                           if e.get("event") == "node_done")
                seen = max((e.get("attempt") or 1) for e in entries)
                key = f"{frm}:{step.get('milestone')}"
                claimed = (step.get("set") or {}).get(f"attempts.{key}")
                if isinstance(claimed, int) and seen > claimed:
                    problems.append(f"step {i}: the journal shows attempt {seen} at {frm} but "
                                    f"attempts.{key} was written as {claimed} — a retry the counter "
                                    f"never charged, which is the budget quietly widening")
            block_trace_nodes.add(frm)
            # The block closes where the agent's evidence runs out: LEAVING GATE_B for good, or on
            # a halt (which includes the has_ui == null itinerary returning at GATE_A). GATE_B's
            # own DEBUG round-trip is inside the agent — the agent runs that node body and its loop.
            if (frm == "GATE_B" and to != "DEBUG") or to == "BLOCKED":
                hidden = sorted(block_journal_nodes - block_trace_nodes)
                if hidden:
                    problems.append(f"step {i}: the journal recorded {', '.join(hidden)} finishing, "
                                    f"and the trace never leaves {'them' if len(hidden) > 1 else 'it'} "
                                    f"— work the agent did while it ran and the bundle came back "
                                    f"without. R15 rejects this bundle; a legal walk cannot contain it")
                in_milestone_block = False
        elif in_milestone_block:
            problems.append(f"step {i}: {frm} -> {to} is not marked as agent-sourced but sits inside "
                            f"a milestone block — the replay is serial, and an orchestrator step cannot "
                            f"interleave with transitions that have not been written yet")
            in_milestone_block = False

        # ---- human stops: fire exactly where declared, and nowhere else -------------------
        # Conditions are read BEFORE the step's `set` is applied: VERDICT's escalation asks
        # whether the reopen budget was ALREADY spent, not whether this pass just spent it.
        stops = step.get("stops") or []
        mode = state["context"].get("run_mode")
        # checkpoint watches a milestone FINISHING its gates; a GATE_B that routes to DEBUG
        # has not finished one, so it is not a checkpoint.
        checkpoint_due = mode == "checkpoint" and frm == "GATE_B" and to != "DEBUG"
        exception_due = (mode == "on-exception"
                         and bool(step.get("skipped_gates") or halt
                                  or step.get("agent_stop") == "on-exception"))
        seen = set()
        for stop in stops:
            kind, answer = stop.get("type"), stop.get("answer")
            bad = None
            if not answer:
                bad = (f"step {i}: stop '{kind}' at {frm} records no answer — "
                       f"an unanswered stop is a stall, not a stop")
            elif kind in MODE_STOPS and kind != mode:
                bad = (f"step {i}: '{kind}' stop declared while run_mode is '{mode}' — "
                       f"extra stops are declared at STRATEGY, never invented")
            elif kind == "checkpoint" and not checkpoint_due:
                bad = (f"step {i}: checkpoint stop leaving {frm} for {to}; checkpoint mode "
                       f"stops after every milestone's GATE_B")
            elif kind == "on-exception" and not exception_due:
                bad = (f"step {i}: on-exception stop at {frm} with no skipped gate and no "
                       f"exhausted bound to justify it")
            elif kind not in MODE_STOPS and kind != declared_stops.get(frm):
                bad = (f"step {i}: {frm} declares human '{declared_stops.get(frm)}' in "
                       f"nodes.md but the walk stops with '{kind}'")
            elif kind not in MODE_STOPS and not stop_applies(frm, state):
                bad = (f"step {i}: {frm} stopped for '{kind}' but its condition is false — "
                       f"this is the run stopping where it was told to continue")
            if bad:
                problems.append(bad)
            else:
                actual_stops.append(f"{frm}:{kind}")
            seen.add(kind)

        want = declared_stops.get(frm, "none")
        if want != "none" and want not in seen and stop_applies(frm, state):
            problems.append(f"step {i}: left {frm} without its declared '{want}' stop — "
                            f"the run continued where a human was owed a say")
        # A mode stop asks for the run to PAUSE, not for a second question. Where a node stop
        # already fired at the same node the human is being asked anyway, and demanding both
        # would invent the seventh stop the graph forbids.
        if checkpoint_due and not seen:
            problems.append(f"step {i}: left GATE_B without the checkpoint stop run_mode asks for")
        if exception_due and not seen:
            problems.append(f"step {i}: a gate was skipped (or a bound exhausted) under "
                            f"on-exception mode and the run did not stop")

        # `stopped` is what makes a deliberate stop distinguishable, on disk, from the IMPLEMENT
        # halt. Written at the stop, cleared by the transition that resumes. A stop that coincides
        # with a halt is one `stopped` with kind "blocked" — it was two fields, and keeping them
        # apart needed a rule about which won.
        state["stopped"] = ({"kind": "handoff" if to == "HANDOFF" else "paused",
                             "reason": stops[0].get("answer"), "at_node": frm}
                            if stops and not halt else None)

        # ---- E2E: a touches_ui milestone owes Playwright specs, or a ledger entry ---------
        if frm == "E2E":
            m = milestone_by_id(state, step.get("milestone"))
            touches = True if m is None else m.get("touches_ui", True)
            evidence = step.get("e2e_specs")
            if evidence not in {"authored", "regression-only", "ledgered", None}:
                problems.append(f"step {i}: e2e_specs '{evidence}' is not one of "
                                f"authored / regression-only / ledgered")
            if state["context"].get("has_ui") is True and touches:
                ledgered = any(g.get("node", "").startswith("E2E")
                               for g in step.get("skipped_gates") or [])
                if evidence == "authored":
                    # `authored` is an agent's claim about files it says it wrote. R8 is what opens
                    # them: exists on disk, contains test(/expect(, and does not mock the API.
                    if agent and "R8" not in set(agent.get("verified") or []):
                        problems.append(f"step {i}: e2e_specs 'authored' on a milestone step with no R8 "
                                        f"verification — nobody opened the spec files")
                elif ledgered and evidence == "ledgered":
                    pass
                else:
                    problems.append(
                        f"step {i}: left E2E on a touches_ui milestone without authoring "
                        f"component specs and without a skipped_gates entry — this is the "
                        f"'Playwright tests are missing' outcome with nothing recording it")
            elif evidence == "regression-only" and touches:
                problems.append(f"step {i}: e2e_specs 'regression-only' on a touches_ui milestone")

        for key, value in step.get("set", {}).items():
            apply_set(state, key, value)
        state["skipped_gates"].extend(step.get("skipped_gates", []))

        if halt:
            state["stopped"] = collections.OrderedDict(
                [("kind", "blocked"), ("at_node", frm),
                 ("guards_tested", halt.get("guards_tested", [])),
                 ("tried", halt.get("tried", [])), ("at_milestone", step.get("milestone"))])

        if to in TERMINALS:
            state["status"] = to
            # DONE is not a pause. The old table had a `DONE -> [end]` step whose absence of stops
            # happened to clear `paused`; with `[end]` gone (it is notation, not a node) the clear
            # has to be stated. A halt or a park keeps its `stopped` — that is the record.
            if to == "DONE":
                state["stopped"] = None
        else:
            state["node"] = to
        state["history"].append(collections.OrderedDict(
            [("from", frm), ("to", to), ("guard", guard),
             ("milestone", step.get("milestone")), ("observation", step["observation"]),
             ("evidence", step.get("evidence")),
             ("verified", (step.get("agent") or {}).get("verified"))]))

    # ---- invariants from state.md ------------------------------------------------------
    # One implementation, shared with `audit_run.py`. These lived in both files, in two
    # vocabularies, and had drifted: five of them existed only here, so a REAL run could carry a
    # schema-4 field, a ledger entry blaming an uninstalled Playwright, or a counter past its bound
    # and the auditor would report it clean. The auditor is the tool pointed at real runs.
    paths.on_path()
    import invariants
    for _check_id, message in invariants.check_all(state, BOUNDS, catalogue):
        problems.append(message)

    # Walker-only, because a fixture is the only place they can go wrong: a `cursor` shaped like the
    # object it stopped being, a milestone PLAN forgot to seed, and a cursor pointing outside the
    # set actually in flight.
    if isinstance(state.get("cursor"), dict):
        problems.append("`cursor` is a milestone id, not an object — `cursor.milestones` became "
                        "`in_flight` at schema 5")
    for m in state["milestones"]:
        if "touches_ui" not in m:
            problems.append(f"milestone {m['id']} has no touches_ui — PLAN seeds it on every "
                            f"milestone so E2E never reads an absent field")
    _in_flight = state.get("in_flight") or []
    _cur = state.get("cursor")
    if _in_flight and _cur is not None and _cur not in _in_flight:
        problems.append(f"cursor {_cur} is not among the milestones in flight {sorted(_in_flight)}")

    # `status` and `stopped.kind` answer the same question and must not disagree. One field with a
    # kind makes that checkable; two nullable objects made it a rule about which one wins.
    stopped = state.get("stopped") or None
    kind = (stopped or {}).get("kind")
    # `agent_lost` is the second legal kind here, not a third status: state.md's row publishes
    # `BLOCKED` for it *even when the re-spawn follows in the same turn*, so the crash window
    # between diagnosis and re-spawn is on disk. Reading BLOCKED as "kind blocked, always" made
    # the one state the spec asks an orchestrator to write a state no fixture could model.
    if state["status"] == "BLOCKED" and kind not in {"blocked", "agent_lost"}:
        problems.append(f"status BLOCKED with stopped.kind {kind!r} — the pause is not resumable "
                        f"without guards_tested[] and tried[]")
    if state["status"] == "HANDOFF" and kind != "handoff":
        problems.append(f"status HANDOFF with stopped.kind {kind!r} — a park needs action, and the "
                        f"file must say so rather than reading as a stall")
    if state["status"] == "DONE" and stopped:
        problems.append(f"status DONE with stopped.kind {kind!r} still set — resume clears a pause "
                        f"and DONE is not one")
    if state["status"] == "RUNNING" and kind in {"blocked", "handoff"}:
        problems.append(f"status RUNNING with stopped.kind {kind!r} — a run that is moving is not "
                        f"stopped")

    for expected in spec.get("expect", {}).get("reaches", []):
        if not any(h["to"] == expected for h in state["history"]):
            problems.append(f"walk never reached {expected}, which it claims to exercise")

    want_stops = spec.get("expect", {}).get("stops")
    if want_stops is not None and want_stops != actual_stops:
        problems.append("the stops the walk took are not the stops it declares\n"
                        f"        expected: {want_stops}\n"
                        f"        actual:   {actual_stops}")

    final = spec.get("expect", {}).get("final_status")
    if final and state["status"] != final:
        problems.append(f"final status {state['status']}, expected {final}")

    return spec, state, problems, edges_used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("walks", nargs="*", help="walk fixtures; defaults to every file in walks/fixtures/")
    args = ap.parse_args()

    edges_text = paths.EDGES_MD.read_text(encoding="utf-8")
    nodes_text = paths.NODES_MD.read_text(encoding="utf-8")
    edges = parse_edges(edges_text)
    catalogue = node_ids(nodes_text)
    declared_stops = parse_stops(nodes_text)

    fixtures = [pathlib.Path(p) for p in args.walks] or sorted(paths.FIXTURES.glob("*.json"))
    if not fixtures:
        print("no walk fixtures found")
        return 2

    failed = 0
    covered_edges, covered_nodes = set(), set()
    for path in fixtures:
        spec, state, problems, edges_used = walk(path, edges, catalogue, declared_stops)
        # A fixture may declare itself illegal — the negative controls. For those, finding no
        # problem IS the failure: a checker that cannot fail is not evidence of anything. Their
        # transitions are deliberately wrong, so they contribute nothing to coverage.
        must_reject = spec.get("expect", {}).get("rejected")
        if must_reject:
            wanted = spec["expect"].get("because", [])
            missed = [w for w in wanted if not any(w in p for p in problems)]
            bad = missed or not problems
            print(f"{'FAIL' if bad else 'ok':5} {path.name}  —  {spec['name']}")
            print(f"      negative control: {len(problems)} violation(s) detected, "
                  f"{len(wanted)} required")
            if not problems:
                print("      the harness accepted a walk it should have rejected")
            for m in missed:
                print(f"      did not detect: {m}")
            failed += bool(bad)
        else:
            covered_edges |= edges_used
            covered_nodes |= {h["from"] for h in state["history"]} | {h["to"] for h in state["history"]}
            stops = [s for s in spec.get("expect", {}).get("stops", [])]
            print(f"{'FAIL' if problems else 'ok':5} {path.name}  —  {spec['name']}")
            print(f"      {len(spec['steps'])} transitions, {len(edges_used)} edges, "
                  f"{len(stops)} human stops, {len(state['skipped_gates'])} ledger entries, "
                  f"final {state['status']}")
            for p in problems:
                print(f"      {p}")
            failed += bool(problems)
        print()

    print(f"{len(fixtures) - failed}/{len(fixtures)} walks legal against edges.md and state.md")

    # ---- coverage: the fixture set as a whole must reach every node and every edge --------
    all_edges = {eid for targets in edges.values() for eid, _ in targets}
    missing_edges = sorted(all_edges - covered_edges, key=lambda e: (int(re.match(r"\d+", e).group()), e))
    missing_nodes = sorted(catalogue - covered_nodes)
    enforce = not args.walks
    print(f"coverage: {len(covered_edges)}/{len(all_edges)} edges, "
          f"{len(covered_nodes & catalogue)}/{len(catalogue)} nodes")
    if missing_edges:
        print(f"      edges no walk traverses: {', '.join(missing_edges)}")
    if missing_nodes:
        print(f"      nodes no walk enters:    {', '.join(missing_nodes)}")
    if (missing_edges or missing_nodes) and enforce:
        print("      an untraversed edge is an untested guard — add a walk or retire the edge")
        failed += 1
    elif (missing_edges or missing_nodes):
        print("      (not enforced: specific fixtures were named on the command line)")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
