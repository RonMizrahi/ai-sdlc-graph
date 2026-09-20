#!/usr/bin/env python3
"""
Static consistency checks over the graph spec — nodes.md, edges.md, state.md, SKILL.md.

Every check here exists because a real run hit the defect it catches. The spec is four files
that restate the same facts, so drift between them is the dominant defect class: a Mermaid
diagram that routes on a predicate the transition table forbids, a cycle count that says seven
in one file and eight in another, a context field read by a node and declared in no schema.

    python3 spec_consistency.py [--spec-dir <skills/sdlc-graph>]

Exit 0 when the spec is self-consistent, 1 otherwise. No dependencies.
"""
import argparse
import ast
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

CHECKS = []


def check(ident, why):
    """Registers a check. `why` is the real defect it was written for."""
    def wrap(fn):
        CHECKS.append((ident, why, fn))
        return fn
    return wrap


# --------------------------------------------------------------------------------------
@check("mermaid-routes-on-rerun-not-clean",
       "the diagram routed GATE_A on `clean`, the predicate edges.md says caused two deadlocks")
def _(spec):
    bad = []
    for line in spec["nodes"].splitlines():
        if re.search(r"GATE_A\s*-->\s*(E2E|GATE_B)", line) and "clean" in line:
            bad.append(line.strip())
    return bad and (
        "the Mermaid diagram routes GATE_A on `clean`; route on rerun_recommended:\n    "
        + "\n    ".join(bad))


@check("skill-md-keeps-no-second-copy-of-a-reference-table",
       "SKILL.md carried a bound table under a rule saying it 'must never disagree with' edges.md, "
       "and a stop table claiming to be 'derived from the node contracts, not maintained "
       "separately' while being a hand-written literal — which drifted to EIGHT rows under a "
       "heading that says six. A copy plus a hope needed two checks to hold; deleting the copy "
       "needs one, and this is it")
def _(spec):
    skill = spec["skill"]
    problems = []
    # A bound table is a row naming a counter key and a number. edges.md owns those.
    if re.search(r"^\|.*attempts\[?[\"`]?(TEST|GATE_A|E2E|GATE_B):", skill, re.M):
        problems.append("SKILL.md has re-grown a per-cycle bound table — edges.md § Loop bounds "
                        "is the only one")
    # A stop table is a row whose cells pair a stop with its node.
    if re.search(r"^\|\s*\**(Spec approval|Plan approval|Branching strategy|Open the PR|Merge|"
                 r"QA reopen)\**\s*\|", skill, re.M):
        problems.append("SKILL.md has re-grown a stop table — the `human:` rows in nodes.md are "
                        "the list, and the copy is what drifted to eight rows")
    # And it must still POINT at the authorities, or deleting the copies just lost the facts.
    for what, pattern in (("the bound table", r"edges\.md[^.\n]{0,80}(Loop bounds|authoritative)"),
                          ("the stop list", r"`human:?`?\s*rows[^.\n]{0,40}nodes\.md|"
                                            r"nodes\.md[^.\n]{0,40}`human")):
        if not re.search(pattern, skill, re.I):
            problems.append(f"SKILL.md deleted its copy of {what} without pointing at the file "
                            f"that owns it")
    return "; ".join(problems) or None


@check("context-fields-declared",
       "context.unborn_main was read by GATE_B, declared in no schema, emitted by no node")
def _(spec):
    read = set(re.findall(r"context\.(\w+)", spec["nodes"]))
    read |= set(re.findall(r"context\.(\w+)", spec["edges"]))
    declared = set(re.findall(r"`context\.(\w+)`", spec["state"]))
    declared |= set(re.findall(r'"(\w+)":', spec["state"]))
    missing = sorted(f for f in read - declared if f not in {"qa_env"})
    return missing and f"read by a node but not declared in state.md: {', '.join(missing)}"


@check("has-ui-is-a-boolean-before-the-loop-starts",
       "`NOT has_ui` is true for null, so an unresolved value erased E2E for a whole run with no "
       "ledger entry. It used to be caught 200 lines later at GATE_A by a dedicated halt edge that "
       "had to be tested BEFORE the two real exits — and that halt needed its own agent itinerary, "
       "its own nodes.md callout, its own diagram caveat and its own check. Resolving the field "
       "where it is settled costs one guard clause")
def _(spec):
    bad = []
    # 1. The loop cannot start on a tri-state: the STRATEGY exit demands a real boolean.
    row = re.search(r"^\|\s*6\s*\|\s*`STRATEGY`\s*\|\s*`BRANCH`\s*\|(.+?)\|", spec["edges"], re.M)
    if not row:
        bad.append("edges.md has no STRATEGY -> BRANCH row to carry the precondition")
    elif not re.search(r"has_ui`?\s+is\s+a\s+boolean", row.group(1), re.I):
        bad.append("the STRATEGY -> BRANCH guard does not require `context.has_ui` to be a boolean, "
                   "so a null can still reach GATE_A where `NOT null` is true")
    # 2. STRATEGY must actually RESOLVE it, or the guard is unsatisfiable rather than protective.
    strategy = re.search(r"^###\s+`STRATEGY`[\s\S]*?(?=\n## )", spec["nodes"], re.M)
    if not strategy or "has_ui" not in strategy.group(0):
        bad.append("the STRATEGY contract does not resolve `has_ui`, so guard 6 blocks every "
                   "greenfield run instead of protecting it")
    # 3. And the routing guards still test the two values explicitly, never a boolean operator.
    if not (re.search(r"has_ui\s*==\s*true", spec["edges"])
            and re.search(r"has_ui\s*==\s*false", spec["edges"])):
        bad.append("the GATE_A exits do not test has_ui == true / == false explicitly")
    return bad and "; ".join(bad)


@check("guards-are-written-in-exactly-one-file",
       "nodes.md carried an `exit guards` row per node restating every guard in different words, "
       "deliberately, 'for the implementer working inside one contract' — 20 rows of a second "
       "rendering that history[].guard then had to declare which of the two it quoted. This check "
       "used to be 'the two agree'; it is now 'there is only one'")
def _(spec):
    bad = []
    if "authoritative" not in spec["edges"].lower():
        bad.append("edges.md does not declare itself the authoritative rendering of guards")
    if not re.search(r"edges\.md[^.\n]{0,60}verbatim", spec["state"]):
        bad.append("state.md does not point history[].guard at edges.md verbatim")
    # The second rendering must not come back.
    if re.search(r"^\|\s*\*\*exit guards\*\*\s*\|", spec["nodes"], re.M):
        bad.append("nodes.md has re-grown an `exit guards` row — the node contract names "
                   "destinations (`exits`), and edges.md owns the conditions")
    if not re.search(r"^\|\s*\*\*exits\*\*\s*\|", spec["nodes"], re.M):
        bad.append("nodes.md declares no `exits` row, so the node contracts no longer enumerate "
                   "where a node can go — which is what made totality checkable")
    return bad and "; ".join(bad)


@check("gate-a-bounds-are-separate-counters",
       "one attempts key served both the findings re-run and the workflow retry; "
       "a harness crash silently spent the security re-review budget")
def _(spec):
    if "GATE_A-dispatch" not in spec["edges"]:
        return "edges.md does not give the GATE_A dispatch retry its own counter key"
    if "GATE_A-dispatch" not in spec["nodes"]:
        return "nodes.md GATE_A contract does not mention the separate dispatch counter"
    return None


@check("node-ids-match-across-files",
       "state that invents node values cannot be checked against the catalogue")
def _(spec):
    catalogue = set(re.findall(r"^###\s+`(\w+)`", spec["nodes"], re.M))
    # The walker's parser, not a second one: it expands the DEBUG fan-out/fan-in rules into their
    # six caller pairs, and a hand-rolled regex here called DEBUG an orphan the moment twelve rows
    # became two. A second parser of the authoritative file is a second opinion about it.
    sys.path.insert(0, str(paths.WALKS))
    import graph_walk
    in_edges = {n for pair in graph_walk.parse_edges(spec["edges"]) for n in pair}
    sentinels = {"start", "handoff", "end", "BLOCKED", "DONE", "HANDOFF"}
    unknown = sorted(n for n in in_edges - catalogue - sentinels)
    orphans = sorted(n for n in catalogue - in_edges - {"DONE"})
    problems = []
    if unknown:
        problems.append(f"edges.md references nodes with no contract in nodes.md: {', '.join(unknown)}")
    if orphans:
        problems.append(f"nodes.md defines nodes unreachable in edges.md: {', '.join(orphans)}")
    return "; ".join(problems) or None


@check("commit-to-record-has-a-mechanical-check",
       "the IMPLEMENT halt happened three times under prose-only warnings — and delegating the loop "
       "to an agent broke the original check in BOTH directions: it fires on every healthy agent "
       "(`node` is legitimately stale while one runs) and misses the case it existed for (an agent that "
       "commits and dies leaves `node` set to something other than IMPLEMENT)")
def _(spec):
    problems = []
    # The same-agent half: nodes.md still owns the rule for nodes the orchestrator runs itself.
    if "commit-and-record" not in spec["nodes"]:
        return "nodes.md has no commit-and-record invariant — prose warnings alone have failed 3x"
    if "commit" not in spec["state"] or "record" not in spec["state"]:
        problems.append("state.md write-points does not carry the commit-and-record invariant")
    # The cross-agent half. A rewrite that drops it is itself the defect.
    if not re.search(r"commit\s*⇒\s*bundle\s*⇒\s*record", spec["state"]):
        problems.append("state.md does not state the cross-agent form (commit ⇒ bundle ⇒ record)")
    if "evidence.commits" not in spec["state"]:
        problems.append("state.md names no field that makes a agent's commits checkable against the trail")
    return "; ".join(problems) or None


@check("transitions-are-not-batched",
       "batching transitions meant `node` never held the intermediate value; it preceded the halt — "
       "and delegating the loop to an agent makes after-the-fact writes UNAVOIDABLE, so the rule had to "
       "move from timing to evidence rather than be deleted")
def _(spec):
    both = spec["edges"] + spec["state"]
    problems = []
    # (a) the original prohibition survives, in BOTH files
    for name in ("edges", "state"):
        if not re.search(r"never\s+(two\s+)?batch", spec[name], re.I):
            problems.append(f"{name}.md no longer forbids batching transitions into one write")
    # (b) the ONE exception is named and scoped
    if not re.search(r"one\s+legal\s+batch\s+is\s+a\s+\*{0,2}verified\s+milestone\s+replay", both, re.I):
        problems.append("neither file names the verified milestone replay as the one legal batch")
    # (c) the replay is still ordered and per-transition
    if not re.search(r"one\s+transition\s+at\s+a\s+time,?\s+in\s+the\s+order", both, re.I):
        problems.append("the milestone replay is not required to write one transition at a time, in order")
    # (d) EVIDENCE is what forbids the failure now. Without this clause the rewrite is a permission
    #     slip: "write them afterwards" with nothing standing where the timing rule stood.
    if not re.search(r"(nothing\s+is\s+written\s+until\s+the\s+return\s+gate|only\s+after\s+the\s+return\s+gate)", both, re.I):
        problems.append("the exception does not require the return gate to pass before anything is written")
    return "; ".join(problems) or None


@check("in-flight-is-one-list-written-before-the-spawn",
       "the in-flight set was once TWO lists that had to agree — `cursor.milestones` shadowed by a "
       "`lanes` object keyed the same way — and there was a check that they did. Collapsing them "
       "deleted the disagreement instead of policing it, twice: `lanes` into `milestones[]`, then "
       "`cursor.milestones` into `in_flight` with `cursor` a plain id. What is left is the thing "
       "the pre-spawn write buys: an agent that dies before its first append is still findable, "
       "and its branch still diffable")
def _(spec):
    s = spec["state"]
    bad = []
    if re.search(r"^\|\s*`(lanes|cursor\.milestones)", s, re.M):
        bad.append("state.md declares a second in-flight list — `in_flight` is the only one")
    if not re.search(r"^\|\s*`in_flight`", s, re.M):
        bad.append("state.md declares no `in_flight` field")
    if not re.search(r"^\|\s*`cursor`\s*\|\s*number", s, re.M):
        bad.append("`cursor` is not declared as a plain milestone id — an object with its own "
                   "`milestones` list is the two-lists shape coming back")
    # Scope to THAT ROW. A character window spills into the next row, and the `journal` row already
    # says "before the spawn" — so a `base_sha` row that dropped the requirement still passed.
    for field in ("journal", "base_sha"):
        row = re.search(rf"^\|\s*`milestones\[\]\.{field}`.*$", s, re.M)
        if not row:
            bad.append(f"state.md declares no `milestones[].{field}`")
        elif not re.search(r"before the spawn|before the agent is spawned", row.group(0), re.I):
            bad.append(f"`milestones[].{field}` is not required to be written BEFORE the spawn")
    return bad and "; ".join(bad)


@check("observation-has-one-author",
       "the observation trail is the only per-node record, and there is no live auditor any more. An "
       "orchestrator that narrates a node it did not witness produces a trail that is cheerful by "
       "construction — the exact failure the trail exists to make visible")
def _(spec):
    problems = []
    if not re.search(r"MUST NOT rewrite", spec["state"]):
        problems.append("state.md does not forbid the orchestrator rewriting a agent's observation")
    if not re.search(r"MUST NOT invent", spec["state"]):
        problems.append("state.md does not forbid the orchestrator inventing an observation")
    if "verified" not in spec["state"]:
        problems.append("state.md declares no separate field for what the orchestrator itself checked")
    return "; ".join(problems) or None


@check("journal-is-telemetry-not-evidence",
       "a second artefact describing the run is a second thing that can be trusted by mistake. If a "
       "journal line could satisfy a gate, an agent would pass a gate by writing a line about it — "
       "which is the 'reported it, therefore it happened' failure the whole return gate exists to "
       "prevent. The separation has to be stated, not assumed from where the words happen to sit")
def _(spec):
    d, s = spec["dispatch"], spec["state"]
    problems = []
    if not re.search(r"telemetry,?\s+not\s+evidence", d, re.I):
        problems.append("workflow-dispatch.md never says the journal is telemetry and not evidence")
    if not re.search(r"never\s+satisfies\s+an\s+R-check|never\s+satisfy\s+an\s+R-check", d, re.I):
        problems.append("nothing says a journal line cannot satisfy an R-check")
    if not re.search(r"nothing\s+routes\s+on\s+it", d, re.I):
        problems.append("nothing says the journal is not routed on")
    # The provisional agent fields are the same hazard one file over: they are written DURING the run,
    # so they are the obvious thing to mistake for a recorded transition.
    if not re.search(r"provisional", s, re.I):
        problems.append("state.md does not mark the live milestones[] fields as provisional")
    if not re.search(r"only\s+after\s+the\s+bundle\s+passes", s, re.I):
        problems.append("state.md does not say history[] is written only after the bundle passes the gate")
    return "; ".join(problems) or None


@check("journal-record-schema-is-complete",
       "the agent writes this file blind — it reads the schema once and never sees a consumer. Every "
       "field a reader depends on has to be named where the agent will look, or it silently ships a "
       "journal that parses and answers nothing")
def _(spec):
    d = spec["dispatch"]
    problems = []
    # Scope the field check to the RECORD BLOCK, not the whole file. Grepping the file passes on a
    # schema that dropped `headline` entirely, because the word survives in the prose around it —
    # measured: renaming the field left this check green.
    block = re.search(r"###\s+The milestone journal[\s\S]*?```jsonc\n([\s\S]*?)```", d)
    if not block:
        return ("workflow-dispatch.md has no `### The milestone journal` section with a jsonc record "
                "schema — the agent writes this file blind and has nothing to write it from")
    fields = block.group(1)
    missing = [f for f in ("run_id", "milestone", "seq", "event", "node", "headline", "detail",
                           "node_done", "heartbeat", "interfaces")
               if f not in fields]
    if missing:
        problems.append("the journal record schema names no " + ", ".join(missing))
    if not re.search(r"as\s+the\s+(milestone\s+)?agent\s+leaves\s+each\s+node|append.{0,30}on\s+exit", d, re.I):
        problems.append("nothing says the line is appended as the node is left, so it may be batched at the end")
    # A heartbeat nobody explains gets dropped as noise the first time someone tidies the schema.
    if not re.search(r"silence\s+is\s+distinguishable\s+from\s+work|distinguishable\s+from\s+work", d, re.I):
        problems.append("the heartbeat is declared without the reason it exists (dead vs slow)")
    if "agent_file" in spec and not re.search(r"1.2k\s+tokens|1–2k\s+tokens|1-2k\s+tokens",
                                              spec["agent_file"], re.I):
        problems.append("the agent is not told how large `detail` should be, so it will write one line")
    return "; ".join(problems) or None


@check("agent-writes-only-its-own-journal",
       "under strategy C several inflight run at once. One shared file would give them concurrent "
       "read-modify-write with no lock — the exact race the run state file avoids by having a single "
       "writer. A agent appending to a sibling's journal corrupts it for both")
def _(spec):
    problems = []
    # NOT an alternation over three phrasings. "One file per milestone" is a layout fact; the
    # invariant is that the agent is the file's ONLY writer, and an or-list let the invariant be
    # deleted while the layout fact kept the check green — a check with spare lives. Its own control
    # caught that: the mutation removed "and the agent is its only writer" and nothing went red.
    if not re.search(r"(only|sole)\s+writer|one\s+writer\s+per\s+file", spec["dispatch"], re.I):
        problems.append("workflow-dispatch.md does not state one journal per milestone, one writer each")
    if "agent_file" in spec:
        if not re.search(r"[Nn]ever\s+write\s+another\s+(milestone\s+agent|milestone)'?s?\s+journal", spec["agent_file"]):
            problems.append("the agent's hard rules do not forbid writing another agent's journal")
        if not re.search(r"journal_path", spec["agent_file"]):
            problems.append("the agent is never told which file is its own (`journal_path`)")
    if "journal_path" not in spec["dispatch"]:
        problems.append("the brief does not carry journal_path, so the agent has no path to write to")
    return "; ".join(problems) or None


@check("delivered-answers-what-the-milestone-shipped",
       "`notes` shipped defined-but-unconsumed for a whole release: named in MILESTONE_BUNDLE, written by "
       "nobody, read by nobody. A run therefore ended with per-hop observations and no answer to "
       "'what did milestone 2 build?' — which is exactly what a dependent agent needs briefing from")
def _(spec):
    problems = []
    if "delivered" not in spec["state"]:
        problems.append("state.md declares no milestones[].delivered")
    # Emphasis-tolerant: the spec writes "**after** the bundle passes", and a check that a paragraph
    # can break by being bolded is a check that gets "fixed" by reflowing prose.
    elif not re.search(r"delivered[\s\S]{0,400}after\*{0,2}\s+the\s+bundle\s+passes", spec["state"], re.I):
        problems.append("state.md does not say `delivered` is written only after the gate passes")
    if not re.search(r"notes:\s+string\(600\)", spec["dispatch"]):
        problems.append("MILESTONE_BUNDLE still has `notes` optional — a field the root routes its rollup on")
    if "agent_file" in spec and not re.search(r"`notes`\s+is\s+required", spec["agent_file"], re.I):
        problems.append("the agent is not told that notes is required on completion")
    return "; ".join(problems) or None


@check("journal-check-keeps-its-two-directions-apart",
       "the two disagreements between journal and bundle are different failures. A journal with a "
       "node the bundle omitted is an agent that under-reported real work — repairable. A bundle "
       "claiming a node that left no trace while it happened is fabrication. Collapsing them either "
       "BLOCKS honest runs on a tidy-up, or silently repairs the one thing the gate exists to catch")
def _(spec):
    wd = spec.get("dispatch", "")
    if not wd:
        return None
    problems = []
    if not re.search(r"\|\s*\*\*R13\*\*\s*\|", wd):
        problems.append("the return gate has no R13 row")
    # Bounded at the next heading, NOT by a character count. A fixed window spilled into
    # "### Three outcomes on rejection", which uses the word "repairable" for its own reasons — so
    # deleting R15's repairable row left this green. Its own control caught it.
    section = re.search(r"####\s+R13[\s\S]*?(?=\n#{2,3} )", wd)
    if not section:
        return "workflow-dispatch.md has no R13 section explaining how the journal may be used"
    body = section.group(0)
    if not re.search(r"[Rr]epairable", body):
        problems.append("R13 does not name the repairable direction (journal has what the bundle omitted)")
    if not re.search(r"[Ff]abricat", body):
        problems.append("R13 does not name the fabricated direction (bundle claims what the journal never saw)")
    if not re.search(r"NOT\s+RUN", body):
        problems.append("R13 does not say it reports NOT RUN when the journal is absent")
    if not re.search(r"never\s+a\s+pass|[Ii]t is never a pass", body):
        problems.append("R13 does not say an absent journal is never a pass — absent is not a pass, applied here")
    # The direction is the whole reason this one check may read the journal at all.
    if not re.search(r"other\s+way\s+round|catch\s+the\s+bundle|check\s+the\s+\*?bundle", body, re.I):
        problems.append("R13 does not state that it uses the journal to check the BUNDLE, not to prove work happened")
    return "; ".join(problems) or None


@check("agent-dispatch-is-background-and-monitored",
       "a blocking dispatch makes the orchestrator deaf for a whole milestone — its turn never ends, "
       "so no notification can reach it — which is precisely the window the journal exists to close. "
       "And a monitor armed after the spawn misses every node the agent finished first")
def _(spec):
    s = spec["skill"]
    problems = []
    if not re.search(r"run_in_background:\s*true", s):
        problems.append("SKILL.md does not dispatch inflight with run_in_background")
    if not re.search(r"[Aa]rm the monitor\s+\*{0,2}before\*{0,2}|before\*{0,2}\s+the first spawn", s):
        problems.append("SKILL.md does not say the monitor is armed before the first spawn")
    if "Monitor(" not in s:
        problems.append("SKILL.md never names the Monitor tool, so the channel has no mechanism")
    # The monitor-agent failure, one layer out: a filter that only matches good news is silent
    # through a crash, and the orchestrator believes it is watching.
    if not re.search(r"blocked.{0,60}as well as|must pass\s+`?blocked`?", s, re.I | re.S):
        problems.append("nothing requires the monitor filter to match `blocked`, not only node_done")
    if not re.search(r"[Rr]e-arm", s):
        problems.append("nothing says to re-arm on a re-spawn — a re-spawn writes a NEW file")
    # The monitor is armed BEFORE the spawn, so the journals do not exist yet. A glob therefore
    # matches nothing and the shell kills the pipeline before `tail` starts: `Monitor` comes up,
    # reports no error, and delivers nothing all milestone — blind while believing it is watching,
    # the exact failure the monitor agent was retired for. FIVE orchestrators driving run-evals hit
    # it independently. `tail -F` on an EXPLICIT path waits for a file that is not there yet, which
    # is why naming them works and globbing cannot.
    #
    # Scoped to the command itself. The prose around it has to show the broken form in order to
    # explain it, so grepping the file would only check that someone once wrote `*.jsonl`. The first
    # version of this check demanded a `touch` instead — which worked, and made the ORCHESTRATOR
    # create the agent's journal, against the one-writer-per-file rule. A run-eval caught that too.
    # Window widened 500 -> 1200. It bounds the SEARCH, not the command: every real assertion
    # below runs on the matched block (no glob, has `^==>`, tolerant jq). At 500 the original
    # command already measured 496, so any correct change to it failed this check by overflowing
    # the scan rather than by being wrong — and a check that cannot pass on a correct spec is one
    # people learn to skip. Still bounded, so a runaway match is impossible.
    cmd = re.search(r"Monitor\(\{[\s\S]{0,1200}?\}\)", s)
    if not cmd:
        problems.append("SKILL.md shows no `Monitor({...})` call, so the channel has no mechanism")
    elif re.search(r"milestone-\*\.jsonl", cmd.group(0)):
        problems.append("the Monitor command globs for journals that do not exist when it is armed "
                        "— the glob matches nothing, the shell kills the pipeline before `tail` "
                        "runs, and the monitor is silently blind for the whole milestone. Name the "
                        "paths explicitly; `tail -F` waits for a file that is not there yet")
    elif not re.search(r"\^==>", cmd.group(0)):
        # Watching more than one file makes `tail` print a `==> path <==` header and a blank line
        # per file. `jq` rejects the header and EXITS, so the monitor dies on its first line — under
        # C only, because one file gets no header at all. A and B work; the strategy running the
        # most agents is the one that goes blind. Found by an orchestrator driving scenario 05.
        problems.append("the Monitor command pipes `tail` straight into `jq`, so under strategy C "
                        "the per-file `==> path <==` headers reach jq, which rejects them and exits "
                        "— the monitor dies on its first line, and only under C")
    elif not re.search(r"fromjson\?", cmd.group(0)):
        # Same failure, friendlier cause: `jq` EXITS on ANY parse error, so one malformed
        # journal line ends the monitor for the rest of the run. Observed in a real strategy-C
        # run — an agent serialized `detail` with a dropped closing brace, and its node_done
        # lines were the malformed ones, so the orchestrator saw BRANCH and then silence while
        # that milestone ran to GATE_B unseen. The agent emitting the bad line is precisely the
        # agent whose progress is lost, so the blast radius is never one line.
        problems.append("the Monitor command pipes journal lines into a plain `jq`, which "
                        "EXITS on the first malformed line and takes the monitor with it. Use "
                        "`-R` with `fromjson?` so a bad line is skipped, not fatal")
    if not re.search(r"agent_id", s):
        problems.append("SKILL.md never records agent_id, so an agent cannot be asked anything later")
    return "; ".join(problems) or None


@check("provisional-fields-never-become-history",
       "the orchestrator learns TEST went green while the agent is still running. Writing that "
       "transition then is the whole architecture inverted: nothing re-run, no sha looked up, no "
       "spec file opened — and a gate that runs after the write cannot refuse. The mirror defect is "
       "clearing too MUCH: the replay once wiped the whole record, deleting `agent_id` one step "
       "before interrogation needed it")
def _(spec):
    s, st = spec["skill"], spec["state"]
    bad = []
    if not re.search(r"progress[\s\S]{0,300}(not a transition|never appears in `?history)", st, re.I):
        bad.append("state.md does not say `milestones[].progress` is never a transition")
    if not re.search(r"[Nn]ull\s+`?milestones\[<id>\]\.progress`?", s):
        bad.append("the replay does not null `milestones[<id>].progress`, so it outlives its agent")
    # Both files, separately. Searching their concatenation let either one alone satisfy this,
    # so breaking the replay step in SKILL.md went undetected because state.md still said it.
    if not re.search(r"survive the replay|survives the replay", s, re.I):
        bad.append("SKILL.md's replay step does not say the durable fields survive it — clearing "
                   "`agent_id` there deletes the interrogation handle at the moment it becomes usable")
    if not re.search(r"not cleared on replay|survives? the replay", st, re.I):
        bad.append("state.md does not say `milestones[].agent_id` outlives the replay")
    return bad and "; ".join(bad)


@check("interrogation-is-questions-only",
       "a returned agent still has its tools. 'Just also fix that' re-drives a milestone outside its "
       "itinerary, outside its preflight and outside a gate that already passed on its bundle — "
       "every guarantee this architecture buys, spent in one message")
def _(spec):
    problems = []
    s = spec["skill"]
    if not re.search(r"[Qq]uestions only", s):
        problems.append("SKILL.md does not state the questions-only limit on asking a agent")
    if not re.search(r"[Aa]n answer is not evidence", s):
        problems.append("SKILL.md does not say an interrogation answer is not evidence")
    if not re.search(r"new (milestone )?agent|fresh (milestone )?agent", s):
        problems.append("SKILL.md does not route real follow-up work to a NEW agent")
    if "agent_file" in spec:
        la = spec["agent_file"]
        if not re.search(r"[Aa]nswering is not resuming", la):
            problems.append("the agent is not told that answering a question is not resuming work")
        if not re.search(r"decline", la, re.I):
            problems.append("the agent is not told to decline an instruction that arrives after its return")
    return "; ".join(problems) or None


@check("root-reads-records-before-briefing-a-dependent-agent",
       "`delivered` and the journal `detail` exist so a dependent agent can be briefed from its "
       "parents' actual output. Left to judgement, 'on demand' decays to 'never' and C spawns "
       "milestone 3 knowing nothing about milestone 1 — the failure C exists to avoid")
def _(spec):
    s = spec["skill"]
    problems = []
    if not re.search(r"deps`?[\s\S]{0,200}(read|brief)", s, re.I):
        problems.append("SKILL.md does not require reading the parents' records before a dependent spawn")
    if not re.search(r"CLOSE_OUT[\s\S]{0,200}read every milestone|read every milestone[\s\S]{0,120}CLOSE_OUT", s):
        problems.append("SKILL.md does not require reading the records at CLOSE_OUT")
    if not re.search(r"delivered", s):
        problems.append("SKILL.md never mentions `delivered`, so nothing writes the rollup")
    return "; ".join(problems) or None


@check("silence-is-diagnosed-not-waited-out",
       "the monitor agent this graph removed died at a session rollover and observed 0 of 28 "
       "transitions while nothing noticed. A root that answers a silent agent by waiting longer has "
       "reproduced exactly that, with the roles swapped")
def _(spec):
    s = spec["skill"]
    problems = []
    if not re.search(r"seen_at", s):
        problems.append("SKILL.md never reads seen_at, so it has no liveness signal")
    if not re.search(r"dead or hung|not slow", s, re.I):
        problems.append("SKILL.md does not distinguish a dead agent from a slow one")
    if not re.search(r"MILESTONE-dispatch", s):
        problems.append("silence does not route to the MILESTONE-dispatch retry")
    # One pattern, not an alternation. The alternation this replaced accepted the phrase "indefinite
    # wait" from the surrounding explanation, so deleting the actual RULE left the check green —
    # caught by its own control. An or-list of phrasings is a check with spare lives.
    if not re.search(r"[Ww]aiting\s+longer\s+is\s+not\s+a\s+diagnosis", s):
        problems.append("nothing forbids answering silence with a longer wait")
    return "; ".join(problems) or None


@check("agent-dispatch-has-its-own-counter",
       "verbatim the GATE_A-dispatch lesson: a checkpointed, unresumable dispatch consumed the "
       "findings budget, so the gate that actually ran had none left. A dead agent charged to "
       "TEST:<id> hands the milestone a re-run budget it never spent")
def _(spec):
    if "MILESTONE-dispatch" not in spec["edges"]:
        return "edges.md § Loop bounds has no MILESTONE-dispatch counter for an agent that died without returning"
    # Whitespace-tolerant: prose wraps, and a check that depends on where a line broke is a check
    # that will be "fixed" by reflowing a paragraph.
    if not re.search(r"never\s+(against|charged to)\s+the node budgets", spec["edges"] + spec["state"], re.I):
        return "nothing says a dead agent may not spend the node budgets — which is the whole point of the key"
    return None


@check("agent-owns-execution-root-owns-guards",
       "the same split failed once in the other direction: gate-a.workflow.js returned `clean`, the "
       "orchestrator routed on it, and the node deadlocked TWICE — because `clean` is also false when "
       "a tool was absent. An executor that both acts and decides is that defect at the root")
def _(spec):
    LOOP = ("BRANCH", "IMPLEMENT", "TEST", "GATE_A", "E2E", "GATE_B", "DEBUG")
    problems = []
    # Every milestone-loop node names the agent as its owner.
    for node in LOOP:
        m = re.search(rf"^###\s+`{node}`(.*?)(?=^###\s+`|\Z)", spec["nodes"], re.M | re.S)
        if not m:
            problems.append(f"no contract for {node}")
            continue
        owner = re.search(r"^\|\s*\*\*owner\*\*\s*\|(.*)$", m.group(1), re.M)
        # The cell must OPEN with `**milestone agent**`, which is the form all seven use. Searching
        # the cell for the substring "agent" was inert: BRANCH's cell goes on to say "the agent
        # creates the branch (and, under C, the worktree)", so an owner of `inline` passed. Its own
        # control caught that — the mutation set the owner to `inline.` and nothing went red.
        if not owner or not re.match(r"\s*\*\*milestone agent\*\*", owner.group(1)):
            problems.append(f"{node}'s owner row does not open by naming the **milestone agent** — "
                            f"got {(owner.group(1).strip()[:40] + '…') if owner else 'no owner row'}")
    # And the split itself is stated where the guards live.
    if not re.search(r"orchestrator evaluates every guard[\s\S]{0,120}(milestone agent|agent) evaluates none",
                     spec["edges"], re.I):
        problems.append("edges.md does not state that the orchestrator evaluates every guard and the executor none")
    # The twins are what the agent actually reads, so a AGENT-LOADED twin that still names an edge is
    # the same defect — this is exactly how `clean: true -> take edge 13` survived in the Gate A
    # twin long after edges.md forbade routing on `clean`. Orchestrator-loaded twins (watch-ci,
    # pr-mr-prepare, qa-engineer, brainstorming) may name edges: there, the executor IS the decider.
    LANE_LOADED = {
        "testing-standards-node.md": None,          # whole file
        "code-quality-pipeline-node.md": None,
        "systematic-debugging-node.md": None,
        "plan-guidelines-node.md": r"^##\s+§\s+BRANCH$",   # only the section the agent loads
    }
    for name, section in LANE_LOADED.items():
        text = spec.get("twins", {}).get(name)
        if text is None:
            continue
        if section:
            m = re.search(rf"{section}(.*?)(?=^##\s+§|\Z)", text, re.M | re.S)
            text = m.group(1) if m else ""
        if re.search(r"Take\s+\*{0,2}edge\s+\d", text, re.I):
            problems.append(f"{name} still tells the agent which edge to take")
    return "; ".join(problems) or None


@check("agent-bundle-fields-are-required-not-optional",
       "`tools_asserted` once meant no more than 'an object arrived', and a run recorded a gate "
       "passed on an unverified preflight; parallel-milestones had to grow a `no_test_evidence` "
       "channel for the identical reason — absent read as pass")
def _(spec):
    wd = spec.get("dispatch", "")
    if not wd:
        return None
    problems = []
    for field in ("tools_asserted", "groups_completed", "e2e", "preflight", "attempt_counts",
                  "skipped_gates_proposed"):
        if field not in wd:
            problems.append(f"MILESTONE_BUNDLE does not carry {field}")
    if not re.search(r"absent\s+is\s+not\s+a\s+pass", wd, re.I):
        problems.append("workflow-dispatch.md does not state that absent is not a pass")
    if not re.search(r"read\s+as\s+the\s+\*{0,2}worst\*{0,2}\s+value", wd, re.I):
        problems.append("a missing bundle field is not declared to read as the worst value")
    return "; ".join(problems) or None


@check("agent-return-gate-has-one-source",
       "two sources for one fact is how the six-stops list drifted — the reason "
       "`stop-table-matches-node-contracts` had to be written at all")
def _(spec):
    wd = spec.get("dispatch", "")
    if not wd:
        return None
    if not re.search(r"##+\s*The return gate", wd):
        return "workflow-dispatch.md has no § The return gate — the authoritative list has no home"
    # SKILL.md may point at it; it may not restate it. A second numbered R-list is a second source.
    rs = len(re.findall(r"\bR1[0-4]\b", spec["skill"]))
    if rs > 2:
        return (f"SKILL.md restates the return gate ({rs} R-check references) instead of pointing at "
                "workflow-dispatch.md")
    return None


@check("agent-agent-states-what-it-may-not-do",
       "the agent is a full-tool agent, in a worktree that shares .git with every sibling milestone, "
       "holding plan text a human wrote. Every rule below is a failure this graph has ALREADY had, "
       "one level up — and the agent reads its own file and nothing else, so a rule that lives only "
       "in nodes.md or SKILL.md is a rule the agent never sees")
def _(spec):
    agent = spec.get("agent_file")
    if agent is None:
        return "agents/sdlc-graph-milestone.md is missing — the milestone loop has no executor"
    REQUIRED = [
        (r"[Nn]ever write the run'?s state file", "that it may never write the state file"),
        (r"[Nn]ever ask the user anything", "that it cannot reach the user"),
        (r"[Nn]ever widen a budget", "that it may not widen a bound"),
        (r"absent\"? is NOT \"?pass", "that an absent suite is not a pass"),
        (r"[Nn]ever open a PR", "that it may not open a PR"),
        (r"[Nn]ever push to main", "that it may not push to the protected branch"),
        (r"[Nn]ever route on `?clean`?", "that `clean` is not a routing signal"),
        (r"[Nn]ever load a standalone twin", "the twin-suspension rule"),
        (r"PLAN-DATA", "the fence around untrusted plan text"),
        (r"evaluates? no guard", "that it evaluates no guard"),
        (r"[Rr]eturning is (your|its) final act", "that returning is its last act — the agent-side "
                                                 "half of commit => bundle => record"),
    ]
    missing = [what for pattern, what in REQUIRED if not re.search(pattern, agent)]
    return missing and ("the agent's brief does not state: " + "; ".join(missing))


@check("agent-itineraries-agree",
       "the itinerary is computed by the orchestrator and executed by the agent, from two different "
       "files; if they disagree the agent runs a shape nobody gated. There used to be a THIRD "
       "shape for `has_ui == null` — return immediately after GATE_A — which existed only to keep "
       "a halt edge reachable and the orchestrator's. Resolving `has_ui` at STRATEGY deleted the "
       "halt edge and the itinerary with it, so this now also asserts the third shape is gone: a "
       "reintroduced null itinerary is a tri-state back inside the loop")
def _(spec):
    agent, wd = spec.get("agent_file"), spec.get("dispatch", "")
    if agent is None or not wd:
        return None
    rows = lambda t: {m.group(1): re.sub(r"\s+", " ", m.group(2)).strip()
                      for m in re.finditer(r"^\|\s*`(true|false|null)`\s*\|\s*(.+?)\s*\|\s*$", t, re.M)}
    a, b = rows(agent), rows(wd)
    if not a:
        return "the agent states no itinerary table"
    if not b:
        return "workflow-dispatch.md states no itinerary table"
    problems = [f"has_ui {k}: agent says '{a.get(k)}', workflow-dispatch says '{b.get(k)}'"
                for k in set(a) | set(b) if a.get(k) != b.get(k)]
    if "null" in a or "null" in b:
        problems.append("a `has_ui == null` itinerary is declared — edge 6 refuses to leave "
                        "STRATEGY on a null, so the shape is unreachable and its existence means "
                        "the tri-state is back inside the loop")
    if set(a) != {"true", "false"}:
        problems.append(f"the agent declares itineraries for {sorted(a)}, not exactly true/false")
    return "; ".join(problems) or None


@check("agent-bundle-promised-equals-bundle-required",
       "the agent promises a return shape and the return gate routes on one. `tools_asserted` once "
       "meant no more than 'an object arrived'; a field the gate reads and the agent was never told "
       "to send is that defect with the roles swapped")
def _(spec):
    agent, wd = spec.get("agent_file"), spec.get("dispatch", "")
    if agent is None or not wd:
        return None
    # The fields the gate routes on. Each must be named in the agent's own file, or the agent has
    # no idea it owes it.
    ROUTED = ["outcome", "trace", "observation", "evidence", "commits", "tests",
              "preflight", "attempt_counts", "skipped_gates_proposed", "blocked", "stop"]
    missing = [f for f in ROUTED if f not in agent]
    return missing and ("the gate routes on fields the agent is never told to return: "
                        + ", ".join(missing))


@check("return-gate-is-complete",
       "a gate with a hole is worse than no gate: it reads as a check that ran. The floor is the "
       "part that actually holds — the bundle is agent-asserted throughout, and only git, the "
       "re-run suite, the workflow journal and the files on disk can contradict it")
def _(spec):
    wd = spec.get("dispatch", "")
    if not wd:
        return None
    problems = []
    # A ROW in the gate's table, not merely the token: R14 is also mentioned in the worktree
    # section, so a bare word-boundary match passed with the row deleted — the check was verifying
    # that someone had once written "R14", not that the gate still had a step called R14.
    missing = [f"R{i}" for i in range(14) if not re.search(rf"\|\s*\*\*R{i}\*\*\s*\|", wd)]
    # And nothing ABOVE the last one: a gate that grew R14 without renumbering is two schemes.
    extra = [f"R{i}" for i in range(14, 20) if re.search(rf"\|\s*\*\*R{i}\*\*\s*\|", wd)]
    if extra:
        problems.append("the return gate has rows past R13: " + ", ".join(extra))
    if missing:
        problems.append("the return gate skips " + ", ".join(missing))
    floor = re.search(r"floor[\s\S]{0,2000}", wd)
    for node in ("BRANCH", "IMPLEMENT", "TEST", "GATE_A", "E2E", "GATE_B", "DEBUG"):
        if floor and not re.search(rf"\|\s*`{node}`\s*\|", floor.group(0)):
            problems.append(f"the world-sourced floor names no check for {node}")
    if not re.search(r"world-sourced", wd, re.I):
        problems.append("workflow-dispatch.md never distinguishes agent-asserted from world-sourced")
    return "; ".join(problems) or None


@check("agent-loaded-twins-say-so",
       "the twins are the only files the agent reads besides its own brief. One that still reads as "
       "orchestrator instructions is how `clean: true -> take edge 13` survived in the Gate A twin "
       "long after edges.md forbade routing on it")
def _(spec):
    LANE_LOADED = {"testing-standards-node.md": ("§ TEST", "§ E2E"),
                   "code-quality-pipeline-node.md": ("§ GATE_A", "§ GATE_B"),
                   "systematic-debugging-node.md": ("§ DEBUG",),
                   "plan-guidelines-node.md": ("§ BRANCH",)}
    problems = []
    for name, sections in LANE_LOADED.items():
        text = spec.get("twins", {}).get(name)
        if text is None:
            problems.append(f"{name} is missing")
            continue
        if not re.search(r"\|\s*Loaded by\s*\|", text):
            problems.append(f"{name} has no 'Loaded by' column saying who reads each section")
        elif "agent" not in text:
            problems.append(f"{name} never names the agent as a reader")
        if not re.search(r"You are a milestone agent", text):
            problems.append(f"{name} carries no agent preamble — a fresh agent reads this file and "
                            f"nothing else, so 'you write no state, you evaluate no guard' has to "
                            f"be IN it")
    return "; ".join(problems) or None


@check("behavioural-evals-are-well-formed",
       "evals.json is the only thing that reaches obedience rather than structure, and it is run by "
       "hand — so a malformed or duplicated case is one nobody notices until the day it is needed")
def _(spec):
    cases = spec.get("behavioural")
    if cases is None:
        return None
    problems = []
    ids = [c.get("id") for c in cases]
    if len(ids) != len(set(ids)):
        problems.append("duplicate eval ids")
    for c in cases:
        for field in ("id", "name", "prompt", "expected_output"):
            if not c.get(field) and c.get(field) != 0:
                problems.append(f"eval {c.get('id', '?')} has no {field}")
    # The architecture's own failure modes must each have a case.
    blob = json.dumps(cases).lower()
    for topic, why in (("agent", "the agent"), ("bundle", "the return gate"),
                       ("observation", "the two-author rule")):
        if topic not in blob:
            problems.append(f"no behavioural eval covers {why}")
    return "; ".join(problems) or None


@check("eval-prose-cites-edges-that-exist",
       "the real-agent test `R1` told its orchestrator to 'take edge 18c to CLOSE_OUT' and to note "
       "that a ledgered gate 'proceeds via 13/14 and 18/18c'. There is no edge 18c, and there has "
       "not been since the DEBUG collapse renumbered the table — the exit is 17. Nothing checked it: "
       "`published-counts-match-reality` reads COUNTS, and the walk fixtures now carry edge ids the "
       "walker resolves, but a number written in *prose* was checked by nobody. An orchestrator sent "
       "to take an edge that does not exist has been handed Rule 3 as an instruction")
def _(spec):
    sys.path.insert(0, str(paths.WALKS))
    import graph_walk
    # Expanded transition ids AND bare table-row numbers. The two DEBUG rules (19 and 20) are one
    # row each covering six callers, and the walker expands them to `19·TEST`, `19·GATE_A`, … — so a
    # bare `19` is absent from the expanded set while being a perfectly real row someone may cite.
    # This check rejected exactly that, which makes the check guarding against citations of
    # non-existent edges the thing citing a non-existent rule. Found when RECEIPTS.json joined the
    # prose corpus carrying an honest reference to edge 19.
    real = {eid for v in graph_walk.parse_edges(spec["edges"]).values() for eid, _ in v}
    real |= {m.group(1) for m in
             re.finditer(r"^\|\s*(\d+)\s*\|\s*.+?\s*\|\s*.+?\s*\|", spec["edges"], re.M)}
    # Only where prose NAMES an edge — "edge 17", "edges 19/20", "guards 18/18c/18d". A bare
    # number is a number.
    #
    # `guards?` is in the alternation because the miss that got through said exactly that:
    # "GATE_B's exit guards ITSELF (18/18c/18d)" and "guards 18/18c/18d route on TEST STATE".
    # A transition is named by an id whichever noun the sentence reaches for, and a check that
    # only understood one of them was blind to the other.
    bad = []
    for path, text in sorted((spec.get("eval_prose") or {}).items()):
        # Case-INSENSITIVE. It was not, and `Edge 19` at the start of a sentence — the single most
        # ordinary way to write one — went straight past. Found while writing a paragraph that had
        # to be reworded to lowercase to satisfy this check's own negative control, which is the
        # check telling you about its blind spot and being ignored.
        for m in re.finditer(r"\b(?:edges?|guards?)\s+\(?(\d+[a-z]?(?:\s*/\s*\d+[a-z]?)+|\d+[a-z]?)\b",
                             text, re.I):
            for cited in re.split(r"\s*/\s*", m.group(1)):
                if cited not in real:
                    bad.append(f"{path} cites edge {cited}, which is not in the transition table")
    return bad and "; ".join(sorted(set(bad)))


@check("every-check-has-a-control",
       "this suite's first principle is that a check which cannot fail is not evidence, and for two "
       "releases it applied that to 18 of its own checks. `spec_controls.py` said so in its docstring "
       "— 'the older checks predate this runner and are not covered here; that is a gap, and it is "
       "named rather than papered over' — which is naming a gap, not closing one. The controlled "
       "sample ran at a 15% inert rate: two dead checks on its first run, four more this session, "
       "including one that greped a table cell whose prose necessarily contained the word it looked "
       "for. Adding a check without a control is how the 15% comes back")
def _(spec):
    controls = spec.get("controls")
    if controls is None:
        return None                                   # spec_controls.py not present in this checkout
    covered = set(re.findall(r'^\s{4}\("([a-z0-9-]+)",', controls, re.M))
    missing = sorted({ident for ident, _, _ in CHECKS} - covered - {"every-check-has-a-control"})
    return missing and (
        f"{len(missing)} check(s) have no negative control, so nothing knows whether they can fail: "
        + ", ".join(missing))


@check("every-deterministic-suite-is-wired-into-run-all",
       "two suites sat outside `run_all.py` for a release. `gate-a.harness.mjs` — 81 assertions over "
       "the only executable code the graph ships — because it is the one `.mjs` in a directory of "
       "Python. `run_scenario.py --self-test` — the 8 controls that keep the run-eval scenarios "
       "satisfiable — because the same file also has modes that need an agent, so it read as "
       "'not deterministic'. Together they cost 0.10s. A suite nothing runs is worth exactly what a "
       "check that cannot fail is worth, and the only defence against that is a check that reads the "
       "directory rather than trusting the list. "
       "SCOPE: this reaches `evals/` and `workflows/`, and stops at the plugin root — so it cannot "
       "see "
       "whether the repo's PostToolUse hook fires this runner at all. That half is covered by "
       "`.claude/hooks/run-graph-evals.selftest.py`, which is where the hook lives")
def _(spec):
    runner = spec.get("eval_runner")
    if runner is None:
        return "evals/run_all.py is missing — nothing runs the suites as one verdict"
    # The SUITES / JS_SUITES literals, not the file. Grepping the whole text passed with the JS
    # harness renamed out of the list, because run_all.py's own docstring explains that the harness
    # sat unrun for a release and so still contains its name — this check's first control caught
    # that on its first run. A check that reads the wrong scope is the class this suite exists to
    # keep out, and writing one while adding a check ABOUT unrun tests is the joke writing itself.
    try:
        tree = ast.parse(runner)
    except SyntaxError as exc:
        return f"evals/run_all.py does not parse ({exc}) — the runner cannot run"
    wired = set()
    for node in tree.body:
        if not (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") in {"SUITES", "JS_SUITES"} for t in node.targets)):
            continue
        for s in ast.walk(node.value):
            if isinstance(s, ast.Constant) and isinstance(s.value, str):
                wired.add(s.value)
    if not wired:
        return "evals/run_all.py declares no SUITES/JS_SUITES entries — it runs nothing"

    # Not suites. Each is exempt for a reason that would stop it running unattended, not because
    # it is inconvenient — an exemption without one is how the last two got out.
    EXEMPT = {
        "run_all.py": "is the runner",
        "audit/audit_run.py": "audits a REAL run — its input is a state file on disk, given as argv",
        "runs/mock_milestone.py": "is a scripted actor the run-evals drive, not a suite",
        "lib/invariants.py": "is a module the walker and the auditor both import — it asserts "
                             "nothing on its own, and both of its callers ARE in the list",
        "lib/paths.py": "is where the layout is written down — it resolves directories and asserts "
                        "nothing, and every suite that reads it IS in the list",
        "real/run_real_eval.py": "drives a REAL orchestrator against a REAL milestone agent — it "
                                 "needs a model, which is the one thing this runner cannot supply",
    }
    missing = [f"{name} (a suite on disk that the runner never invokes)"
               for name in (spec.get("eval_suites") or [])
               if name not in EXEMPT and name not in wired]
    # The JS harness is the one that actually went missing, so it is held by the same rule rather
    # than by someone remembering to name it.
    missing += [f"workflows/{name} (an executable harness the runner never invokes)"
                for name in (spec.get("eval_harnesses") or []) if name not in wired]
    return missing and ("not wired into run_all.py: " + "; ".join(missing))



@check("trace-is-off-by-default-and-settled-once",
       "`trace` turns on a hook that copies the whole state file at every write. Defaulted ON, or "
       "left changeable mid-run, it is either a surprise cost on every run anyone ever starts or a "
       "`history/` with a hole in it — and a hole in a numbered sequence looks exactly like a state "
       "that was never written, which is the one thing a trace exists to rule out. The schema, the "
       "node that settles it and the flag that sets it are three files, so this is the drift class "
       "the whole suite exists for")
def _(spec):
    bad = []
    row = next((l for l in spec["state"].splitlines()
                if l.startswith("| `trace` |")), None)
    if not row:
        return "state.md has no `trace` field row — the flag exists in SKILL.md and in no schema"
    if not re.search(r"`false`\s*when\s*(the flag is\s*)?absent|absent is `false`|defaults?\s*`?false", row):
        bad.append("the `trace` row does not say absent is false, so a run written by an older "
                   "orchestrator has undefined tracing")
    if not re.search(r"never changed mid-run|settled once|set once", row, re.I):
        bad.append("the `trace` row does not forbid changing it mid-run — a half-traced run leaves "
                   "a gap indistinguishable from a lost state")

    # The node that actually settles it. A field nothing emits is a field nothing sets.
    intake = re.search(r"###\s+`INTAKE`[\s\S]*?(?=\n### )", spec["nodes"])
    if not intake:
        bad.append("nodes.md has no INTAKE contract")
    elif "trace" not in intake.group(0):
        bad.append("INTAKE does not emit `trace`, so nothing in the graph ever sets it")

    # And the flag that reaches it. Scoped to the frontmatter line, not the file: the Inputs table
    # below describes the flag and would satisfy a file-wide grep on its own.
    hint = re.search(r"^argument-hint:.*$", spec["skill"], re.M)
    if not hint or "--trace" not in hint.group(0):
        bad.append("`--trace` is not in SKILL.md's argument-hint, so the only way to turn tracing "
                   "on is undiscoverable from the command itself")
    return bad and "; ".join(bad)


@check("reviewer-writes-evals-at-tiers-that-exist",
       "the reviewer's whole purpose is turning a run into a test, and it routes each finding to a "
       "tier by name. A tier that has been renamed or moved makes it write nothing and report "
       "confidently — the one failure this skill exists to prevent, happening to the skill itself. "
       "The suite has already renamed `evals/` wholesale once")
def _(spec):
    text = spec.get("reviewer")
    if text is None:
        return None                      # the skill is optional; absent is not a defect
    bad = []
    # Every eval path named in the skill, normalised to its DIRECTORY. The table names some tiers
    # as directories (`evals/walks/fixtures/`) and some as the file inside them
    # (`evals/spec/spec_consistency.py`); a pattern that only understood one shape reported the
    # other as missing, which is a check firing on its own formatting rather than on a defect.
    named = set()
    for raw in re.findall(r"`(evals/[A-Za-z0-9_./-]+)`", text):
        rel = raw.rstrip("/")
        if "." in rel.rsplit("/", 1)[-1]:
            rel = rel.rsplit("/", 1)[0]
        named.add(rel)
    for rel in sorted(named):
        if not (paths.SKILL / rel).exists():
            bad.append(f"the triage table routes findings to `{rel}/`, which does not exist")
    # ...and every tier that exists must be reachable from the table. A tier nobody is told to
    # write into is a tier that stops growing, which is how coverage quietly stops tracking the
    # graph.
    TIERS = {"evals/spec", "evals/walks/fixtures", "evals/runs/scenarios", "evals/real/tests",
             "evals/hooks"}
    missing = sorted(TIERS - named)
    if missing:
        bad.append(f"the triage table names no tier for {missing} — a defect of that shape has "
                   f"nowhere to become a test")
    return bad and "; ".join(bad)


@check("reviewer-is-read-only-against-the-run",
       "a reviewer that edits the run it is reviewing has no standing — the run is the evidence. "
       "This is exactly why the retired monitor agent was trustworthy, and the one property that "
       "lets this be pointed at a LIVE run without changing its outcome. It is also the easiest "
       "thing to erode: the reviewer already holds Write and Edit, for the evals it writes")
def _(spec):
    text = spec.get("reviewer")
    if text is None:
        return None
    bad = []
    if not re.search(r"Never write to the run", text):
        bad.append("the guardrails no longer forbid writing to the run")
    if not re.search(r"state\.json.*journal.*history/|not `state\.json`", text):
        bad.append("the read-only rule does not name the three artifacts it covers, so `history/` "
                   "or a journal reads as fair game")
    # Scoped to the GUARDRAILS section. The § 2 heading also says "do not re-implement it", so a
    # file-wide search stayed green with the guardrail deleted — the check matching its own
    # explanatory prose, which is this suite's most common way of being inert.
    guardrails = re.search(r"^## Guardrails$([\s\S]*?)(?=^## |\Z)", text, re.M)
    if not guardrails:
        bad.append("the reviewer has no ## Guardrails section")
    elif not re.search(r"re-implement `audit_run\.py`", guardrails.group(1)):
        bad.append("the guardrails no longer forbid re-implementing audit_run.py — a second "
                   "checker that disagrees with the first is how a run gets two verdicts")
    # The narrative taxonomy has to say a clean run is a real outcome, or the reviewer manufactures
    # a finding to justify having been run. Same rule the auditor's baseline case enforces.
    checks_text = spec.get("reviewer_checks") or ""
    if not re.search(r"[Zz]ero findings is a real answer|clean run is a real outcome", text + checks_text):
        bad.append("neither the skill nor its taxonomy says a clean run is a real outcome — a "
                   "reviewer that finds something in everything is not evidence")
    return bad and "; ".join(bad)


@check("every-artifact-link-has-a-source",
       "TWO of this plugin's three hosted links pointed at pages with NO source file anywhere in "
       "the repo. A hosted page nobody can edit is worse than no page: it reads as current, it is "
       "what people actually open, and it cannot be corrected. One of them duplicated a view of a "
       "page that DID have a source, so the two said different things about the same subject and "
       "only one could be fixed")
def _(spec):
    manifest = paths.ARTIFACTS / "README.md"
    if not manifest.exists():
        return "docs/artifacts/README.md is missing — nothing maps a hosted link to the file it "\
               "came from, which is how a page becomes uneditable"
    text = manifest.read_text(encoding="utf-8")
    # Rows are `| \`<uuid>\` | \`<path>\` | ... |` — id and source together, so a row cannot
    # claim an artifact without naming what produces it.
    rows = dict(re.findall(r"^\|\s*`([0-9a-f-]{36})`\s*\|\s*`([^`]+)`\s*\|", text, re.M))
    # A row whose second cell is NOT a backticked path: retired, or owned by a sibling
    # plugin. Either way the link is accounted for and this plugin does not claim it.
    accounted = set(re.findall(r"^\|\s*`([0-9a-f-]{36})`\s*\|(?!\s*`)", text, re.M))

    bad = []
    for rel, path in sorted(rows.items()):
        if not (paths.PLUGIN / path).exists():
            bad.append(f"the manifest says `{rel[:8]}` comes from `{path}`, which does not exist")

    # Every link ANYWHERE in the plugin must be in the manifest — as a live row or a retired one.
    # Scanning the files rather than trusting the table is the whole point: a link added to a README
    # without a manifest row is exactly how the two sourceless ones got there.
    linked = set()
    for pattern in ("README.md", "docs/**/*.md", "docs/**/*.html", "skills/*/SKILL.md"):
        for f in sorted(paths.PLUGIN.glob(pattern)):
            if f == manifest:
                continue
            linked |= set(re.findall(r"claude\.ai/code/artifact/([0-9a-f-]{36})", f.read_text(encoding="utf-8")))
    for rel in sorted(linked - set(rows) - accounted):
        bad.append(f"`{rel[:8]}` is linked from this plugin and appears in no manifest row — "
                   f"nothing says which file produces it, so nobody can correct it")
    return bad and "; ".join(bad)


@check("a-dead-agent-keeps-its-diagnosis",
       "`progress` is nulled the moment an agent stops running, and on DEATH that deletes the only "
       "in-state record of how far it got — precisely when `agent_lost` says 'the re-spawn is the "
       "resume' and the re-spawn needs to know. Two orchestrators driving run-evals hit it "
       "independently, and BOTH invented the same workaround: copy it into `stopped.reason`. Two "
       "agents inventing the same missing rule is the spec telling you what it should have said")
def _(spec):
    s = spec["state"]
    bad = []
    row = next((l for l in s.splitlines() if l.startswith("| `milestones[].progress` |")), None)
    if not row:
        return "state.md has no `milestones[].progress` row"
    # Scoped to the row that OWNS the nulling rule. The `agent_lost` row below restates the duty
    # and would satisfy a file-wide search on its own, which is the inert-check trap.
    if not re.search(r"stopped\.reason", row):
        bad.append("the `progress` row nulls the block on death without saying where the diagnosis "
                   "goes — so a correct orchestrator deletes how far the agent got")
    lost = next((l for l in s.splitlines() if l.startswith("| `agent_lost` |")), None)
    if lost and not re.search(r"how far|at_node", lost):
        bad.append("the `agent_lost` row asks `reason` for liveness evidence but not for how far "
                   "the agent got, which is the half the re-spawn actually needs")
    return bad and "; ".join(bad)


@check("resume-blocks-on-the-version-not-on-any-absent-field",
       "Resume step 1 read 'a mismatch or a missing field means the file was written by a different "
       "version'. THREE orchestrators driving separate run-evals independently took `a missing "
       "field` to mean any absent key in the schema — which blocks on every healthy run, since "
       "`stopped` is null until a halt, `spec_path` until SPEC, and `trace` is absent on anything "
       "written before it existed. A rule that halts a correct run is a rule orchestrators learn to "
       "ignore, and this one guards the single unconditional halt in the graph")
def _(spec):
    section = re.search(r"^## Resume$([\s\S]*?)(?=^## |\Z)", spec["state"], re.M)
    if not section:
        return "state.md has no ## Resume section"
    body = section.group(1)
    step1 = body.split("\n2.")[0]
    bad = []
    if not re.search(r"missing `schema_version`|`schema_version` key", step1):
        bad.append("Resume step 1 does not say WHICH missing key blocks, so `a missing field` reads "
                   "as any absent field in the schema")
    if not re.search(r"absent optional field is a value|only key whose absence blocks", body, re.I):
        bad.append("nothing in § Resume says an absent OPTIONAL field is a value rather than a "
                   "version mismatch — the reading that halts every healthy run")
    return bad and "; ".join(bad)


@check("the-orchestrators-own-hop-is-not-a-replayed-one",
       "R3 says record the `GATE_B` exit with `verified: null`; state.md § Write points says a "
       "replayed transition with no `verified` is exactly the defect the timing rule caught. Two "
       "orchestrators driving run-evals read those as a flat contradiction and one of them changed "
       "its behaviour over it. They are consistent only if `replayed` means `sourced from the "
       "agent`, which the text did not say — and the run-level exit is the orchestrator's own hop, "
       "where it was the witness and there is no claim to verify")
def _(spec):
    section = re.search(r"\*\*A\n  replayed transition with no `verified`[\s\S]{0,1400}", spec["state"])
    if not section:
        return "state.md § Write points no longer states the `verified`-on-every-replayed-entry rule"
    if not re.search(r"hop OUT of `GATE_B` is not a replayed entry|not a replayed entry", section.group(0)):
        return ("§ Write points demands `verified` on every replayed entry without excepting the "
                "orchestrator's OWN exit from `GATE_B`, which R3 requires to carry `verified: null` "
                "— read together, a correct replay is a defect")
    return None


@check("a-halt-nobody-recorded-is-not-a-shape-to-copy",
       "`in_flight` called an id with no history block and no `stopped` 'the halt signature'. It "
       "means a halt that was NEVER WRITTEN — a defect the auditor detects — but THREE "
       "orchestrators driving separate run-evals read it as the prescribed shape and wrote no "
       "`history[]` entry at all, which is precisely the trail-ends-nowhere state § Recording a "
       "halt was added to prevent. The two sections were consistent and the phrase was not")
def _(spec):
    s = spec["state"]
    bad = []
    row = next((l for l in s.splitlines() if l.startswith("| `in_flight` |")), None)
    if not row:
        return "state.md has no `in_flight` row"
    if "halt signature" in row and not re.search(r"never\s+recorded|NEVER RECORDED", row, re.I):
        bad.append("the `in_flight` row still calls the unwritten-halt state 'the halt signature' "
                   "without saying it is a halt nobody recorded — read as a prescription, it tells "
                   "an orchestrator to write no history entry")
    # And the gate-rejection case, which "the node that failed" does not cover: no node failed.
    section = re.search(r"### Recording a halt([\s\S]*?)(?=\n#{2,3} )", s)
    if not section:
        bad.append("state.md has no § Recording a halt")
    elif not re.search(r"RETURN GATE is what failed|return gate.*failed", section.group(1), re.I):
        bad.append("§ Recording a halt says `node` stays 'the node that failed', which says nothing "
                   "about a bundle the RETURN GATE refused — no node failed, and writing the "
                   "fabricated node strands resume at one the run never entered")
    return bad and "; ".join(bad)


@check("interrogation-and-re-obtainable-agree-on-the-observation",
       "SKILL.md said an answer 'never becomes an `observation`'; workflow-dispatch.md's "
       "*Re-obtainable* outcome says that when a field only the agent can author is missing — "
       "'in practice an empty `observation`' — you ask the agent for that field. Flatly opposed, on "
       "the same field, and the orchestrator driving the one scenario built to test interrogation "
       "found both and could obey only one. The line that resolves it is evidence versus "
       "authorship, and it was in neither file")
def _(spec):
    k, d = spec["skill"], spec.get("dispatch") or ""
    bad = []
    section = re.search(r"[Aa]n answer is not evidence[\s\S]{0,1600}", k)
    if not section:
        return "SKILL.md no longer carries the `an answer is not evidence` limit"
    body = section.group(0)
    # The RULE, not the paragraph explaining it. The blockquote below the bullet necessarily quotes
    # the old wording to say what it replaced, so a section-wide search matched its own rationale
    # and fired on the fix. That is this suite's most common way of being wrong, and it happened
    # while writing a check about two rules contradicting each other.
    rule = body.split("\n  > ")[0]
    if re.search(r"never becomes an `observation`", rule):
        bad.append("SKILL.md still forbids an answer becoming an `observation`, which is exactly "
                   "what *Re-obtainable* prescribes — the two cannot both be obeyed")
    if not re.search(r"Re-obtainable", body):
        bad.append("SKILL.md's interrogation limit does not reconcile with *Re-obtainable*, so the "
                   "two rules are left to be discovered as a contradiction mid-run")
    if not re.search(r"never ask for\s+.{0,40}fact the gate checks|`dispatch`, a `run_id`, a sha", body):
        bad.append("nothing draws the line at facts the GATE checks — without it, 'ask for a missing "
                   "field' reads as licence to ask for a missing `dispatch` or `run_id`")
    if "Re-obtainable" not in d:
        bad.append("workflow-dispatch.md no longer declares the *Re-obtainable* outcome")
    return bad and "; ".join(bad)


@check("every-rejection-says-which-outcome-it-is",
       "the bundle schema said a missing `evidence.gate_a.dispatch` means `reject`, and named no "
       "outcome. THREE orchestrators driving separate run-evals each picked a different one — an "
       "unproven gate, a bare ledger entry, and a strained Re-obtainable — and the third would have "
       "asked the agent for a fact the gate exists to check. A verdict with no procedure is a "
       "verdict every reader implements differently")
def _(spec):
    d = spec.get("dispatch") or ""
    section = re.search(r"###\s+\w+ outcomes on rejection[\s\S]*?(?=\n---)", d)
    if not section:
        return "workflow-dispatch.md has no § outcomes-on-rejection table"
    table = section.group(0)
    declared = set(re.findall(r"^\|\s*\*\*(\w[\w -]*)\*\*\s*\|", table, re.M))
    bad = []
    if "Unreadable" not in declared:
        bad.append("no outcome covers a REQUIRED field that is simply absent — the check cannot "
                   "evaluate in either direction, and none of the other outcomes fits")
    # The heading must count what the table holds. It said "Four" while listing four, then five.
    heading = re.search(r"###\s+(\w+) outcomes on rejection", d)
    words = {"Three": 3, "Four": 4, "Five": 5, "Six": 6, "Seven": 7}
    if heading and words.get(heading.group(1)) != len(declared):
        bad.append(f"the heading says {heading.group(1).lower()} outcomes and the table lists "
                   f"{len(declared)} — a count that outlived the thing it counted")
    # And every `⟹ reject` in the schema must name which one.
    for m in re.finditer(r"Absent ⟹ reject([^\n]*)", d):
        if not re.search(r"Fabricated|Repairable|Unproven|Re-obtainable|Unreadable", m.group(1)):
            bad.append("the schema says `Absent ⟹ reject` without naming the outcome, so the "
                       "reader has to invent the procedure")
    return bad and "; ".join(bad)


@check("r13-does-not-fire-on-every-honest-bundle",
       "R13 demanded a `trace[]` entry for every journal `node_done`, while R3 states the trace "
       "never LEAVES `GATE_B` — so `GATE_B` has a `node_done` on every completed milestone and is "
       "never a `trace[].from`. Compared naively, R13 rejects every honest bundle. TWO "
       "orchestrators — one driving strategy C, one driving the real-agent tier with a real "
       "milestone agent — each hit it and each silently read `claimed_to` as counting. A gate that "
       "fires on correct input is a gate people learn to route around")
def _(spec):
    row = _gate_row(spec.get("dispatch") or "", 13)
    if not row:
        return "workflow-dispatch.md has no R13 row"
    bad = []
    # The RULE, not the row. `claimed_to` also appears in the paragraph EXPLAINING why it counts and
    # in the jq command that implements it, so a row-wide search stayed green with the rule itself
    # reverted — the check matching its own rationale, twice over.
    rule = row.split("**`GATE_B`")[0]
    if not re.search(r"claimed_to", rule):
        bad.append("R13's rule does not say `claimed_to` counts, so `GATE_B` — which R3 makes a "
                   "`claimed_to` and never a `from` — reads as a node the trace omitted, on every "
                   "completed bundle")
    if not re.search(r"false positive|every honest", row, re.I):
        bad.append("R13 does not warn that the naive comparison fires on correct input, which is "
                   "the form both orchestrators reached for first")
    return bad and "; ".join(bad)


@check("the-agent-knows-its-host-and-its-repo",
       "TWO things a real milestone agent could not do without being told. `context.host` was on the "
       "*deliberately not passed* list because 'an agent never opens a PR' — true, and irrelevant: "
       "`GATE_B`'s `code-review` runs through `gh pr`, so on `host: none` it is structurally "
       "uninvocable, and an agent that does not know the host cannot tell an absent tool from an "
       "inapplicable one. And `security-review` computes its diff from the SESSION cwd, which under "
       "C is a worktree and in a nested run is the wrong repo — a real agent caught it scanning the "
       "marketplace checkout instead of its target. An unscoped reviewer returns a clean diff of the "
       "wrong tree, which is a false clean, and a false clean is indistinguishable from a pass")
def _(spec):
    d = spec.get("dispatch") or ""
    bad = []
    notpassed = re.search(r"\*\*Deliberately not passed:\*\*([\s\S]*?)\n\n", d)
    if not notpassed:
        return "workflow-dispatch.md no longer lists what the brief withholds"
    if "context.host" in notpassed.group(1):
        bad.append("`context.host` is withheld again — the agent cannot tell an absent `code-review` "
                   "from one that is structurally inapplicable on a repo with no remote")
    # Anchored on the paragraph's own lead sentence, not on its wording. Searching for "false
    # clean" matched the body of the very paragraph a control deletes the heading of — the check
    # surviving on the text it was meant to be guarding.
    if not re.search(r"\*\*And the agent is told which repository it is in\.\*\*", d):
        bad.append("the brief no longer names the repository root, so `security-review` scopes to "
                   "the session cwd — under C that is a worktree, and a clean diff of the wrong "
                   "tree is a false clean")
    return bad and "; ".join(bad)


@check("a-halt-can-actually-be-recorded",
       "seventeen node contracts declare an `on failure` exit and NONE of them is a numbered row in "
       "`edges.md` — while SKILL.md § Validation demanded every `history[]` entry name a guard that "
       "appears there, and state.md demanded `guard` quote it verbatim. Read together, an "
       "orchestrator that halted correctly could not record having halted. One driving a run-eval "
       "hit exactly that, wrote no halt entry at all, and reported it — leaving a trail that ends at "
       "a node with no exit, mechanically indistinguishable from a run that stopped being written to")
def _(spec):
    s, k = spec["state"], spec["skill"]
    bad = []
    if not re.search(r"###\s+Recording a halt", s):
        bad.append("state.md has no § Recording a halt, so the shape of the one entry every failed "
                   "run writes is undefined")
    else:
        section = re.search(r"###\s+Recording a halt[\s\S]*?(?=\n^#{2,3} )", s, re.M)
        body = section.group(0) if section else ""
        if not re.search(r"`guard`\s+is empty|guard.{0,20}empty", body, re.I):
            bad.append("§ Recording a halt does not say the halt entry's `guard` is empty — which is "
                       "the whole reason it needs its own rule")
        if not re.search(r"stays the node that failed|`history\[-1\]\.to` != `node`|!=\s*`?node`?", body):
            bad.append("§ Recording a halt does not say `node` stays the node that failed, so a "
                       "resume would try to pick the run up at `BLOCKED`")
    # And the validation rule has to grant the exemption, or the two still contradict.
    rule = re.search(r"^- \*\*Every transition is in `history\[\]`\*\*[\s\S]{0,400}?(?=\n^- )", k, re.M)
    if not rule:
        bad.append("SKILL.md § Validation no longer states the guard-appears-in-edges.md rule")
    elif not re.search(r"except the final halt|halt entry", rule.group(0), re.I):
        bad.append("SKILL.md § Validation still requires EVERY history entry to name a guard from "
                   "edges.md, which no `on failure` exit can satisfy")
    return bad and "; ".join(bad)


@check("total-silence-is-not-cheaper-than-partial-silence",
       "R13's absent-journal clause said a missing journal is NOT RUN, full stop — so an agent that "
       "journalled four of five nodes was caught as fabrication, and one that journalled NONE was "
       "merely 'not checked'. The gate was strictly easier to defeat by writing nothing than by "
       "writing almost everything. Found by an orchestrator driving scenario 08, which followed the "
       "clause correctly and then reported the consequence")
def _(spec):
    wd = spec.get("dispatch", "")
    if not wd:
        return None
    clause = re.search(r"When the journal is absent entirely[\s\S]{0,900}", wd)
    if not clause:
        return "workflow-dispatch.md has no absent-journal clause for R13"
    body = clause.group(0)
    if not re.search(r"`?completed`?", body):
        return ("the absent-journal clause does not condition on the bundle's `outcome`, so a "
                "`completed` bundle claiming a full itinerary with zero journal lines is treated as "
                "a died-early agent — which makes total silence cheaper than partial silence")
    if not re.search(r"easier to defeat by total silence|total silence", body, re.I):
        return ("the clause names no reason for the condition, and a condition without its reason "
                "is the first thing deleted when someone tidies the paragraph")
    return None


@check("strategy-c-keeps-its-fail-closed-bounds",
       "stable ran strategy C through `parallel-milestones.workflow.js`, which validated before it "
       "spawned anything: a hard cap of 5 concurrent agents, and a milestone whose `deps` field is "
       "MISSING refused to sequential rather than run concurrently — 'a malformed plan degrades to "
       "sequential, never to concurrent'. This fork spawns agents directly and inherited neither, so "
       "'N spawned in a single message' had no N and an absent `deps` read as no dependencies. Both "
       "are fail-OPEN, and the failure is two agents editing one module with one of them losing")
def _(spec):
    wd = spec.get("dispatch", "")
    if not wd:
        return None
    bad = []
    if not re.search(r"at most \d+ concurrent milestone agents", wd, re.I):
        bad.append("nothing caps how many milestone agents run at once under C")
    if not re.search(r"`deps`[^.]{0,80}(missing|absent)[\s\S]{0,120}sequential", wd, re.I):
        bad.append("nothing says a MISSING `deps` field degrades to sequential — missing is not `[]`, "
                   "and treating it as `[]` is the fail-open direction")
    # And PLAN has to seed it, or the rule above is the only thing standing between a plan and a race.
    plan = re.search(r"^###\s+`PLAN`[\s\S]*?(?=\n### )", spec["nodes"], re.M)
    if plan and not re.search(r"`deps`[^|]{0,40}always present", plan.group(0), re.I):
        bad.append("nodes.md `PLAN` does not seed `deps` on every milestone, so the field can be "
                   "absent at `STRATEGY` in the first place")
    return bad and "; ".join(bad)


@check("attempt-counts-says-whether-a-first-pass-belongs-in-it",
       "FIVE orchestrators driving run-evals reported the same ambiguity, independently. R10 "
       "'derives the counters from the trace and compares them with `attempt_counts`; a "
       "disagreement rejects', `edges.md` says a first pass writes `1`, and the schema comment said "
       "only 'what you SPENT'. Derive-with-first-passes gives {TEST:1, GATE_A:1, GATE_B:1} against a "
       "bundle's `{}` — so under one reading R10 rejects EVERY clean milestone, and under the other "
       "it accepts a bundle that dropped its counters entirely. Each orchestrator picked a reading "
       "and said so; none of them was wrong, which is the definition of the spec being wrong")
def _(spec):
    row = _gate_row(spec.get("dispatch", ""), 10)
    if not row:
        return "workflow-dispatch.md has no R10 row"
    if not re.search(r"only nodes entered more than once|retries only|RETRIES ONLY", row, re.I):
        return ("R10 does not say whether a first pass belongs in `attempt_counts`, so an empty "
                "object on a clean milestone is both a correct report and a rejectable disagreement")
    # And the schema has to agree, or the agent fills the field from one rule and the gate reads it
    # under the other — which is the same ambiguity with the two halves further apart.
    schema = re.search(r"attempt_counts:.*$", spec["dispatch"], re.M)
    if schema and not re.search(r"RETRIES ONLY|retries only", schema.group(0), re.I):
        return ("the MILESTONE_BUNDLE schema does not tell the agent that `attempt_counts` is "
                "retries-only, so it is filled under one rule and gated under another")
    return None


@check("attempts-counting-is-defined",
       "edges.md said `attempts` counts re-entries while every fixture — and the canonical clean-run "
       "walk — writes 1 on a FIRST pass. The two readings differ by one attempt on every cycle in the "
       "table, and only a green path makes the difference visible: a suite of failure cases never "
       "enters a node exactly once and cleanly")
def _(spec):
    if not re.search(r"counts how many times the node has been ENTERED", spec["edges"]):
        return ("edges.md does not say whether `attempts` counts entries or re-entries — so a bound of "
                "3 means either two retries or three")
    if not re.search(r"first pass writes `?1`?", spec["edges"], re.I):
        return "edges.md does not say what a first, clean pass writes — which is where the two readings diverge"
    return None


@check("loop-bounds-are-parsed-from-the-contract-never-copied",
       "the bounds existed in FOUR places — the node contracts, edges.md's table, SKILL.md's "
       "summary, and the offline auditor's own BOUNDS dict — and this check was the referee for the "
       "last of them. A referee is what you need when there are copies; a bound raised in the spec "
       "and not in the auditor is an auditor that passes a run which exceeded it, which is the "
       "exact failure the auditor exists to catch, in the auditor")
def _(spec):
    if "auditor" not in spec:
        return None                                  # audit_run.py not present in this checkout
    bad = []
    # The dict must be DERIVED. A literal is the copy coming back.
    if re.search(r"^BOUNDS\s*=\s*\{", spec["auditor"], re.M):
        bad.append("audit_run.py has re-grown a literal BOUNDS dict — parse it from the node "
                   "contracts, which is where `max attempts` is declared")
    if not re.search(r"BOUNDS\s*=\s*_bounds\(\)|parse_bounds", spec["auditor"]):
        bad.append("audit_run.py does not parse its bounds from nodes.md")
    if "walker" in spec and re.search(r"^BOUNDS\s*=\s*\{", spec["walker"], re.M):
        bad.append("graph_walk.py has re-grown a literal BOUNDS dict")
    # And the parse has to actually produce the numbers the contracts declare, or "derived" is a
    # word rather than a mechanism.
    sys.path.insert(0, str(paths.WALKS))
    import graph_walk
    got = graph_walk.parse_bounds(spec["nodes"])
    for node, want in (("TEST", 3), ("E2E", 3), ("GATE_A", 2), ("GATE_B", 2), ("CONSOLIDATE", 3)):
        if got.get(node) != want:
            bad.append(f"parsing nodes.md gives {node}={got.get(node)}, and the DEBUG round-trip "
                       f"bound IS the caller's `max attempts` (edges.md row 19)")
    return bad and "; ".join(bad)


@check("gate-b-reviewer-can-run-before-a-pr-exists",
       "GATE_B required `code-review:code-review`, whose allowed-tools are gh pr/issue only, so it "
       "could not read a local diff and could never back a node that always runs BEFORE `PR`. A real "
       "run ledgered it `uninvocable` on four consecutive milestones while a reviewer that takes a "
       "branch range sat unused")
def _(spec):
    row = next((l for l in spec["nodes"].splitlines()
                if l.startswith("| **requires**") and "code-review" in l
                and "built-in" in l), None)
    if row is None:
        return ("no `requires` row in nodes.md names the built-in `code-review` — GATE_B's reviewer "
                "must be the one that takes a branch range and needs no PR")
    problems = []
    # GATE_B's own requires row must NOT name the PR-only plugin command as its tool.
    gate_b = spec["nodes"].split("### `GATE_B`", 1)[-1].split("### `", 1)[0]
    req = next((l for l in gate_b.splitlines() if l.startswith("| **requires**")), "")
    if "`code-review:code-review`" in req:
        problems.append("GATE_B's `requires` row still names `code-review:code-review`, which is "
                        "gh-pr-only and cannot run before the PR node")
    if "built-in" not in req or "code-review" not in req:
        problems.append("GATE_B's `requires` row must name the built-in `code-review` with a branch range")
    # And the PR-only tool must be owned by the node that has a PR to give it.
    if "### `PR_FINAL_REVIEW`" not in spec["nodes"]:
        problems.append("`PR_FINAL_REVIEW` has no contract — the PR-only reviewer has no node to live in")
    else:
        pfr = spec["nodes"].split("### `PR_FINAL_REVIEW`", 1)[-1].split("### `", 1)[0]
        if "`code-review:code-review`" not in pfr:
            problems.append("`PR_FINAL_REVIEW` does not name `code-review:code-review` — the node "
                            "exists to be the one place that tool can run")
    return "; ".join(problems) or None


@check("published-counts-match-reality",
       "'41 edges' and '18-node lifecycle' outlived the graph they described, across five files "
       "and three plugins, and had to be resynced by hand")
def _(spec):
    # TRANSITIONS, not table rows. The two `DEBUG` rules are authored once and cover six callers
    # each, so the table has 30 rows and the graph has 40 transitions — and a published surface
    # claiming "29 edges" would be describing the table rather than the graph. The walker's parser
    # is what expands them, and it is the one that decides coverage.
    sys.path.insert(0, str(paths.WALKS))
    import graph_walk
    transitions = {eid for v in graph_walk.parse_edges(spec["edges"]).values() for eid, _ in v}
    rows = {m.group(1) for m in
            re.finditer(r"^\|\s*(\d+)\s*\|\s*.+?\s*\|\s*.+?\s*\|", spec["edges"], re.M)}
    contracts = re.findall(r"^###\s+`(\w+)`", spec["nodes"], re.M)
    actual = {"edges": len(transitions), "rows": len(rows), "nodes": len(contracts)}

    # Only WHOLE-GRAPH claims. A phase heading legitimately says "7 nodes", and Rule 1's
    # "a 20-node run becomes 20 interruptions" is rhetoric — neither is a count of this graph.
    # A line qualifies when it pairs the two counts, or names the lifecycle explicitly.
    problems = []
    for path, text in spec.get("published", {}).items():
        for line in text.splitlines():
            summary = re.search(r"\d+\s+nodes?\b", line) and re.search(r"\d+\s+(guarded\s+)?edges\b", line)
            # "edges" AND "transitions". SKILL.md said "29 guarded transitions" in two places — the
            # count of table ROWS, not of the graph — and this check read only the word "edges", so
            # it sat green through the whole DEBUG collapse that created the 39-vs-29 distinction.
            # Found by an orchestrator driving a run-eval, not by the suite that exists for it.
            # `(?<!of )` spares "observed 0 of 28 transitions" — the monitor-agent anecdote, which
            # counts one dead run's hops, not this graph's edges. A count check that cannot tell a
            # claim from a story flags the story, and then someone "fixes" the story.
            for m in re.finditer(r"(?<!of )\b(\d+)\s+(?:guarded\s+)?(edges|transitions)\b", line):
                if int(m.group(1)) != actual["edges"]:
                    problems.append(
                        f"{path} claims {m.group(1)} {m.group(2)}, the graph has {actual['edges']} "
                        f"(the TABLE has {actual['rows']} rows — the DEBUG rules cover six callers "
                        f"each, so the two numbers are different and both are real)")
            for m in re.finditer(r"\b(\d+)[- ]node\s+(?:lifecycle|graph)\b", line):
                if int(m.group(1)) != actual["nodes"]:
                    problems.append(
                        f"{path} claims a {m.group(1)}-node lifecycle, nodes.md defines {actual['nodes']}")
            for m in re.finditer(r"\b(\d+)\s+nodes\s+of\b", line):
                if int(m.group(1)) != actual["nodes"]:
                    problems.append(
                        f"{path} claims {m.group(1)} nodes, nodes.md defines {actual['nodes']}")
            if summary:
                for m in re.finditer(r"\b(\d+)\s+nodes?\b", line):
                    if int(m.group(1)) != actual["nodes"]:
                        problems.append(
                            f"{path} summary line claims {m.group(1)} nodes, "
                            f"nodes.md defines {actual['nodes']}")

    # The return gate is a published count too: "16 return-gate checks, R0–R15" outlived the gate
    # by exactly one release, in a KPI tile nobody greps. Same class as the edge count.
    gate = {int(m.group(1)) for m in
            re.finditer(r"^\|\s*\*\*R(\d+)\*\*\s*\|", spec.get("dispatch", ""), re.M)}
    if gate:
        top, count = max(gate), len(gate)
        for path, text in spec.get("published", {}).items():
            for m in re.finditer(r"R0[\s]*(?:&ndash;|–|-|to)[\s]*R(\d+)", text):
                if int(m.group(1)) != top:
                    problems.append(f"{path} says the gate runs to R{m.group(1)}, it runs to R{top}")
            for m in re.finditer(r"(\d+)\s*</span>\s*<span[^>]*>\s*return-gate checks", text):
                if int(m.group(1)) != count:
                    problems.append(f"{path} claims {m.group(1)} return-gate checks, there are {count}")

    # the same stale number usually repeats within one file
    return "; ".join(sorted(set(problems))) or None


@check("the-human-rows-are-the-only-stop-list",
       "SKILL.md claimed its six stops were 'derived from the node contracts, not maintained "
       "separately — the two lists cannot drift apart' while being a hand-written literal table, "
       "and it drifted to EIGHT rows under a heading that says six. The copy is now gone; what is "
       "left to check is that the contracts still say six, and that the count nodes.md publishes "
       "about itself is the count it has")
def _(spec):
    types = ("approval-after", "choice-after", "confirm-before", "await-external", "escalation")
    contracts = set()
    sections = re.split(r"^###\s+`(\w+)`", spec["nodes"], flags=re.M)
    for name, body in zip(sections[1::2], sections[2::2]):
        row = re.search(r"^\|\s*\*\*human\*\*\s*\|(.+)$", body, re.M)
        if row and any(t in row.group(1) for t in types):
            contracts.add(name)
    total = len(re.findall(r"^###\s+`(\w+)`", spec["nodes"], re.M))
    bad = []
    if len(contracts) != 6:
        bad.append(f"{len(contracts)} nodes declare a human stop ({', '.join(sorted(contracts))}) — "
                   f"the graph promises six, everywhere, and a seventh is an invented gate")
    silent = total - len(contracts)
    if not re.search(rf"\b{silent} of {total} nodes\b", spec["nodes"]):
        bad.append(f"nodes.md's `human` default row does not say '{silent} of {total} nodes'")
    # SKILL.md must name the six in prose and point at the contracts — deleting the table must not
    # have deleted the fact.
    named = {n for n in contracts if re.search(rf"`{n}`", spec["skill"].split("Stop for the human")[-1])}
    if named != contracts:
        bad.append(f"SKILL.md's stop section does not name {sorted(contracts - named)}")
    return bad and "; ".join(bad)


@check("e2e-mandates-playwright-on-ui-milestones",
       "'author a new journey only when this milestone adds a money path' made authoring a "
       "judgement call, and the judgement came out 'not this one' every time")
def _(spec):
    problems = []
    for name, text in (("nodes.md", spec["nodes"]), ("testing-standards-node.md", spec.get("e2e", ""))):
        if not text:
            continue
        if "touches_ui" not in text:
            problems.append(f"{name} never mentions touches_ui, so the mandate has no trigger")
        if not re.search(r"no\s+(network\s+)?mock", text, re.I):
            problems.append(f"{name} does not forbid mocking the API at the e2e level")
        if not re.search(r"skipped_gates", text):
            problems.append(f"{name} does not say an unwritten spec is ledgered")
    if "money path" in spec["nodes"] and "touches_ui" not in spec["nodes"]:
        problems.append("nodes.md still gates authoring on 'a user-facing money path' alone")
    return "; ".join(problems) or None


@check("playwright-is-installed-not-ledgered",
       "a real run ledgered E2E at milestone 1 for 'Playwright is not installed and there is no "
       "runnable front-end yet' — both halves true, conclusion wrong. The front-ends were nine "
       "milestones away, so the entry would have repeated every milestone until then, and the "
       "ledger is append-only so it could never be tidied away")
def _(spec):
    problems = []

    # nodes.md's E2E `requires` row must not list Playwright as a ledgerable absence. `requires`
    # is for capabilities the run CANNOT obtain; Playwright is a devDependency plus a browser
    # download, so "not installed" is work to do, never a gate to skip.
    #
    # Asserting the ABSENCE of a phrasing is how a check ossifies into a check on one sentence:
    # `Playwright … absent … skipped_gates` caught the wording this rule replaced and would have
    # waved through `Playwright missing → skipped_gates[]`, one synonym away. So the rule is
    # stated as it is meant: Playwright and skipped_gates must not co-occur in that cell, in
    # either order — with an allow-list for the one mention that is the fix rather than the
    # defect, the row saying Playwright is deliberately NOT a requirement.
    exempt = re.compile(r"Playwright is deliberately NOT listed here", re.I)
    for line in spec["nodes"].splitlines():
        if not line.lstrip().startswith("| **requires**"):
            continue
        if "Playwright" in line and "skipped_gates" in line and not exempt.search(line):
            problems.append(
                "nodes.md E2E `requires` still treats an absent Playwright as a skipped gate")

    # Both files must carry the positive instruction, or the negative rule above is unenforceable:
    # a reader told "don't ledger it" and nothing else has no next action.
    for name, text in (("nodes.md", spec["nodes"]), ("testing-standards-node.md", spec.get("e2e", ""))):
        if not text:
            continue
        if not re.search(r"install it", text, re.I):
            problems.append(f"{name} never tells the reader to INSTALL Playwright instead of ledgering it")

    # The app genuinely refusing to boot IS still a ledger entry — the change must not have
    # deleted the legitimate case along with the illegitimate one.
    if not re.search(r"(cannot be brought up|will not come up|unbootable)", spec["nodes"], re.I):
        problems.append("nodes.md no longer names the case that IS a skipped gate: an unbootable app")

    # And no published surface may still ASSERT the opposite. `docs/topologies.html` said
    # "has_ui true with Playwright missing <i>is</i> a skipped gate" for a full release after
    # nodes.md stopped saying it — inside this suite's reach the whole time, because nothing
    # looked past the two files the rule was written in. Matches the claim's shape (absence …
    # "is" … a skipped gate) through inline tags, and spares any span that negates it.
    claim = re.compile(
        r"Playwright\s+(?:is\s+)?(?:merely\s+)?(?:missing|absent|uninstalled|not installed)\b"
        r"(?:[^.<]|<[^>]*>){0,60}?\b(?:is|are)\b(?:[^.<]|<[^>]*>){0,20}?a\s+skipped[ _]gate",
        re.I)
    for path, text in spec.get("published", {}).items():
        for hit in claim.finditer(text):
            if re.search(r"\bnot\b|\bnever\b|\bneither\b", hit.group(0), re.I):
                continue
            problems.append(f"{path} still asserts that a missing Playwright IS a skipped gate")

    return "; ".join(problems) or None



# ======================================================================================
# The schema-5 removals. Each of these deleted a field AND the rule that field needed;
# each therefore owes the check that would notice it coming back.
# ======================================================================================

@check("schema-version-is-stated-in-exactly-one-place",
       "state.md said `schema_version` was 'currently 3' in the field table while its own example "
       "said 4 — for the one rule in the file defined as an unconditional halt. Nine of thirteen "
       "walk fixtures then sat on a version the spec would have refused to resume, and no eval read "
       "the field at all")
def _(spec):
    s = spec["state"]
    m = re.search(r"^SCHEMA_VERSION\s*=\s*(\d+)\s*$", s, re.M)
    if not m:
        return ("state.md declares no `SCHEMA_VERSION = <n>` line — that line is meant to be the "
                "single place the number is written")
    want = int(m.group(1))
    bad = []
    # The example must agree with it.
    ex = re.search(r'"schema_version"\s*:\s*(\d+)', s)
    if not ex:
        bad.append("the schema example carries no `schema_version`")
    elif int(ex.group(1)) != want:
        bad.append(f"the schema example says {ex.group(1)}, SCHEMA_VERSION says {want}")
    # No prose second opinion.
    for m2 in re.finditer(r"currently\s+`?(\d+)`?", s):
        if int(m2.group(1)) != want:
            bad.append(f"state.md prose says the version is 'currently {m2.group(1)}'")
    # And every fixture, because a corpus on a stale version is a corpus the spec would BLOCK.
    for name, fx in spec.get("fixtures", {}).items():
        got = (fx.get("initial_state") or {}).get("schema_version")
        if got != want:
            bad.append(f"{name} is schema_version {got}, and a mismatch is an unconditional halt")
    # The auditor has to know the number too, or it audits a schema it does not understand.
    if "auditor" in spec and not re.search(rf"^SCHEMA_VERSION\s*=\s*{want}\s*$",
                                           spec["auditor"], re.M):
        bad.append(f"audit_run.py does not declare SCHEMA_VERSION = {want}")
    return bad and "; ".join(bad)


@check("no-field-is-written-and-never-read",
       "`milestones[].node` was written by TEN nodes and read by none — it appeared in no node's "
       "`inputs` and in no guard. It was not free: a real run wrote the invented value "
       "`GATE_B_PASSED` into it, and the answer was a paragraph enumerating the legal values and "
       "explaining why `MERGED` is deliberately not `MERGE`. A field nothing reads acquired an "
       "invented value and got a rule instead of a delete")
def _(spec):
    bad = []
    fields = _fields_table(spec["state"])
    if re.search(r"^\|\s*`milestones\[\]\.node`", fields, re.M):
        bad.append("state.md declares `milestones[].node` again — a milestone's position is the "
                   "last history[] entry carrying its id, and its completion is `delivered != null`")
    if re.search(r"milestones\[[^\]]*\]\.node\s*=", spec["nodes"]):
        bad.append("a nodes.md `emits` row writes `milestones[].node`, which nothing reads")
    for name, fx in spec.get("fixtures", {}).items():
        for m in (fx.get("initial_state") or {}).get("milestones", []) or []:
            if isinstance(m, dict) and "node" in m and not fx.get("expect", {}).get("rejected"):
                bad.append(f"{name} still carries milestones[].node")
                break
    # The sentinels went with it. `CONSOLIDATED`/`MERGED` were values only that field could hold.
    for sentinel in ("CONSOLIDATED", "MERGED"):
        if re.search(rf"`{sentinel}`", fields):
            bad.append(f"the `{sentinel}` sentinel survives the field it was a value of")
    if "walker" in spec and "SENTINELS" in spec["walker"]:
        bad.append("graph_walk.py still carries a SENTINELS set for a field that no longer exists")
    return bad and "; ".join(bad)


@check("one-field-answers-why-the-run-is-not-moving",
       "`paused` and `blocked` were two nullable objects answering one question, which forced a "
       "rule about which one wins when a stop is ALSO a halt — VERDICT's escalation on the spent "
       "2nd reopen. state.md wrote 'two fields describing one pause is the drift this file exists "
       "to prevent' and then kept two fields")
def _(spec):
    s, fields = spec["state"], _fields_table(spec["state"])
    bad = []
    if not re.search(r"^\|\s*`stopped`", fields, re.M):
        bad.append("state.md declares no `stopped` field")
    for dead in ("paused", "blocked"):
        if re.search(rf"^\|\s*`{dead}`\s*\|", fields, re.M):
            bad.append(f"state.md has re-grown a top-level `{dead}` field — `stopped.kind` carries it")
    # The kinds must be enumerated, or `stopped` is just the old ambiguity with a new name.
    for kind in ("paused", "blocked", "handoff"):
        if not re.search(rf"`{kind}`", s):
            bad.append(f"state.md does not name the `{kind}` kind")
    # And the halt fields have to live IN THE `stopped` SHAPE. Grepping the whole file passed with
    # them deleted from the shape, because both words survive elsewhere — its own control caught it.
    shape = re.search(r'"stopped"\s*:\s*\{[\s\S]*?\n\s*```', s)
    if not shape:
        bad.append("state.md shows no `stopped` example, so nothing pins its shape")
    else:
        for field in ("guards_tested", "tried"):
            if field not in shape.group(0):
                bad.append(f"the `stopped` shape carries no {field}[] — a zero-match halt has a SET "
                           f"of guards that all failed, and without them BLOCKED is not resumable")
    return bad and "; ".join(bad)


@check("the-bundle-carries-no-field-only-checked-against-the-world",
       "three bundle fields existed so a return-gate check could compare them with a fact the "
       "orchestrator computes itself. `gate_a.applied` came back EMPTY in every observed run while "
       "the gate edited 5, 13, 5 and 13 files; `working_tree_clean` was documented as "
       "'corroboration, never the check'; `journeys_state` 'mirrors e2e.state and must agree — "
       "where they differ the orchestrator reads e2e.state and rejects'. A field carried only so a "
       "check can disagree with it is a second place to be wrong, inside an 8 KB budget")
def _(spec):
    wd = spec.get("dispatch", "")
    if not wd:
        return None
    schema = re.search(r"MILESTONE_BUNDLE[\s\S]*?```jsonc\n([\s\S]*?)```", wd)
    if not schema:
        return "workflow-dispatch.md has no MILESTONE_BUNDLE schema block"
    body = schema.group(1)
    bad = [f"the bundle schema has re-grown `{f}`" for f in
           ("applied", "working_tree_clean", "journeys_state") if f in body]
    # The world-sourced replacement must still be demanded BY THE ROW THAT REPLACED IT. Grepping
    # the whole file passed with the clause deleted from R7, because the floor table below also
    # says `git diff --name-only` — its own control caught it. A check that reads the wrong scope
    # is the "check that cannot fail" class this suite exists to keep out.
    for n, command, was in ((7, "git diff --name-only", "gate_a.applied"),
                            (12, "git status --porcelain", "working_tree_clean")):
        row = _gate_row(wd, n)
        if not row:
            bad.append(f"there is no R{n} row to carry the world-sourced replacement for `{was}`")
        elif command not in row:
            bad.append(f"R{n} no longer runs `{command}` itself — that is what `{was}` was standing "
                       f"in for, and dropping both leaves the node with no world-sourced check")
    return bad and "; ".join(bad)


def _edge_row(edges_md, n):
    """The one transition-table row for edge `n`, and nothing after it.

    One physical line, like `_gate_row` — a fixed-width window would spill into edge 10 and let the
    neighbour satisfy a check about edge 9, which is the bug that made three checks here inert.
    """
    m = re.search(rf"^\|\s*{n}\s*\|.*$", edges_md, re.M)
    return m.group(0) if m else None


@check("implement-does-not-owe-the-steps-test-owns",
       "guard 9 read `all milestone steps committed` while `PLAN` is REQUIRED to bake test steps "
       "into every milestone and `TEST` is the node that writes them. A real run (R1) planned "
       "`test/unit/token-store.test.js`, committed the implementation at `IMPLEMENT` and the test at "
       "`TEST` — exactly what testing-standards-node.md prescribes — and left the guard literally "
       "false at `IMPLEMENT -> TEST`, a node with one exit. A strict reader had to BLOCK a milestone "
       "on which nothing whatever had gone wrong, and a guard no correct run can satisfy teaches the "
       "next agent that BLOCKED is a normal way to finish")
def _(spec):
    bad = []
    row9, row10 = _edge_row(spec["edges"], 9), _edge_row(spec["edges"], 10)
    # Scoped to the ROWS. The callout below them quotes the old wording as history, and the whole
    # point of that quotation is that it contains the words a file-wide check would look for.
    if not row9 or "`IMPLEMENT`" not in row9 or "`TEST`" not in row9:
        bad.append("edges.md has no `IMPLEMENT` -> `TEST` row at 9 to carry the ownership split")
    else:
        if not re.search(r"\bowns\b", row9):
            bad.append("guard 9 does not scope what it collects to the steps `IMPLEMENT` OWNS, so a "
                       "milestone whose plan names a test file cannot satisfy it at a node with one "
                       "exit — the R1 halt, restored")
        if not re.search(r"\b10\b", row9):
            bad.append("guard 9 does not say where the steps it does NOT collect are owed, so a "
                       "narrowed guard 9 is a hole rather than a partition")
    if not row10:
        bad.append("edges.md has no `TEST` -> `GATE_A` row at 10")
    elif not re.search(r"`TEST` owns is committed|owns is committed", row10):
        bad.append("guard 10 does not collect the steps `TEST` owns, so a test step is owed at "
                   "NEITHER guard and can be dropped between the two nodes")
    # And the split itself is mechanical, in the node contract the milestone agent actually reads.
    section = re.search(r"^###\s+Which steps `IMPLEMENT` owns$([\s\S]*?)(?=^#{2,3} )",
                        spec["nodes"], re.M)
    if not section:
        bad.append("nodes.md carries no § *Which steps `IMPLEMENT` owns*, so the split is a guard's "
                   "adjective and every agent decides it again")
    else:
        body = section.group(1)
        if not re.search(r"\*\.test\.\*|\*\.spec\.\*", body):
            bad.append("the ownership section names no test-file shape, so 'a step whose deliverable "
                       "is a test' is a judgement call made under time pressure")
        if not (re.search(r"\|\s*9\s*\|", body) and re.search(r"\|\s*10\s*\|", body)):
            bad.append("the ownership section does not map each half to its guard (9 and 10), which "
                       "is what makes it a partition rather than a discount for `IMPLEMENT`")
    # And the EXECUTOR is told, in the one file it reads before `IMPLEMENT`. Its section allow-list
    # does not include nodes.md, so a split written only there is a rule the agent never sees — it
    # would hold `IMPLEMENT` open writing tests, or report `steps_committed` over the wrong set.
    agent = spec.get("agent_file", "")
    if agent and not re.search(r"split `steps\[\]` between them", agent):
        bad.append("the milestone agent is never told that `IMPLEMENT` and `TEST` split `steps[]` — "
                   "and nodes.md is not on its section allow-list, so it cannot find out")
    # The losing reading — delete test steps from plans so the old guard is true again — must stay
    # impossible: PLAN still REQUIRES them.
    plan = spec.get("twins", {}).get("plan-guidelines-node.md", "")
    must = re.search(r"^### Every milestone MUST include$([\s\S]*?)(?=^#{2,3} )", plan, re.M)
    if plan and (not must or not re.search(r"\*\*Test steps\*\*", must.group(1))):
        bad.append("plan-guidelines-node.md no longer requires test steps in every milestone — the "
                   "guard was fixed by deleting the requirement that exposed it")
    return bad and "; ".join(bad)


@check("tests-has-a-legal-value-for-a-node-never-reached",
       "`evidence.tests` was REQUIRED with enum `pass|fail|absent`, and every one of the three "
       "claims the suites were looked at. A bundle with `outcome: blocked` at `IMPLEMENT` never "
       "reached `TEST`, so it had no true value to report — and the honest `not-run` a real bundle "
       "returned is exactly what R0 rejected. R3 already scopes itinerary coverage by `outcome`; R0 "
       "did not, so the gate that exists to catch dishonesty was the one forcing it")
def _(spec):
    wd = spec.get("dispatch", "")
    if not wd:
        return None
    bad = []
    line = re.search(r"^\s*tests\??\s*:\s*\{.*$", wd, re.M)
    if not line:
        bad.append("the MILESTONE_BUNDLE schema has no `tests:` line")
    else:
        if "'not-run'" not in line.group(0):
            bad.append("`evidence.tests` declares no value for a suite the trace never reached, so "
                       "a milestone blocked before `TEST` must pick one of three lies")
        if re.match(r"^\s*tests\?", line.group(0)):
            bad.append("`evidence.tests` has become optional — that lets a bundle which DID run the "
                       "suites omit the result entirely, which is 'absent is not a pass' with the "
                       "check taken out. The fix was a legal value, not a missing field")
    # One spelling for one fact: `trace[].result.tests_state` already had `not-run`.
    if "'not-run'" in wd and "tests_state" in wd and not re.search(
            r"tests_state\?*\s*:[^\n]*'not-run'", wd):
        bad.append("`trace[].result.tests_state` has lost `not-run` while `evidence.tests` keeps it "
                   "— two spellings for one fact is the drift this schema keeps deleting")
    row = _gate_row(wd, 0)
    if not row:
        bad.append("there is no R0 row to scope the new value")
    else:
        if "not-run" not in row:
            bad.append("R0 does not mention `not-run`, so the enum it validates against and the "
                       "schema it validates are two documents again")
        if not re.search(r"only[^|]*never entered `TEST`", row):
            bad.append("R0 does not SCOPE `not-run` to a trace that never entered `TEST` — "
                       "unscoped it is a free pass for a milestone that ran the suites and would "
                       "rather not say what happened, which is the failure R0 was written for")
    return bad and "; ".join(bad)


@check("an-undeclared-bundle-field-is-unread-and-named",
       "R0 checked that required fields were present and enum-valid and said nothing about EXTRA "
       "ones. Run-eval bundles carried `gate_a.applied`, `working_tree_clean` and "
       "`worktree_removed` — two deleted from this schema, one never in it — and no check noticed "
       "any of them. Both silent readings are wrong: rejecting burns a milestone of real work over "
       "a stale key, and ignoring throws away the one thing the key proves, that this agent is "
       "working from a contract that is not this one")
def _(spec):
    wd = spec.get("dispatch", "")
    if not wd:
        return None
    bad = []
    section = re.search(r"^#### An undeclared field is unread, not fatal$([\s\S]*?)(?=^#{2,4} )",
                        wd, re.M)
    if not section:
        bad.append("workflow-dispatch.md states no rule for a field the schema does not declare, so "
                   "the three that arrived in real bundles are handled three different ways")
    else:
        body = section.group(1)
        # The RULE, not the section. The two readings it rejects are spelled out below it, and the
        # row explaining why ignoring is wrong necessarily says `verified` — so a section-wide read
        # stayed green with the rule itself gutted. Its own control caught that.
        rule = re.search(r"^> \*\*The rule:[\s\S]*?\n\n", body, re.M)
        if not rule:
            bad.append("the section states no rule — it explains two readings and picks neither")
        else:
            if not re.search(r"unread", rule.group(0), re.I):
                bad.append("the rule does not say the field is dropped UNREAD — a field read 'just "
                           "as corroboration' re-admits the agent-asserted evidence its deletion "
                           "removed")
            if not re.search(r"`(history\[\]\.)?verified`", rule.group(0)):
                bad.append("the rule does not say the drop is NAMED in `verified`, which is the "
                           "whole difference between this and ignoring it")
        # Both losing readings are named and refused, so neither can be arrived at by silence.
        for reading in (r"Reject the bundle", r"Ignore it silently"):
            if not re.search(reading, body):
                bad.append(f"the rule does not name the '{reading}' reading it rejects, so a reader "
                           f"who arrives at it finds nothing saying otherwise")
    row = _gate_row(wd, 0)
    if row and not re.search(r"unread[^|]*`verified`|`verified`[^|]*unread", row):
        bad.append("R0 — the check that reads the bundle's fields — does not say what happens to a "
                   "field it does not recognise, which is exactly how three of them passed unseen")
    return bad and "; ".join(bad)


@check("the-debug-round-trip-is-one-rule-and-still-fully-covered",
       "twelve near-identical rows — six `X -> DEBUG` / `DEBUG -> X` pairs — were 29% of the "
       "transition table, six of the ten bound rows, and six `debug_return_to = X` clauses, all "
       "restating one sentence DEBUG's own contract already carried. Collapsing them is only safe "
       "if the coverage gate still counts every caller, and if the guard stops restating the "
       "destination it is already the destination of")
def _(spec):
    sys.path.insert(0, str(paths.WALKS))
    import graph_walk
    edges = graph_walk.parse_edges(spec["edges"])
    callers = {"TEST", "E2E", "GATE_A", "GATE_B", "CI", "CONSOLIDATE"}
    bad = []
    for c in sorted(callers):
        if (c, "DEBUG") not in edges:
            bad.append(f"{c} -> DEBUG does not expand out of the rule, so no fixture must traverse it")
        if ("DEBUG", c) not in edges:
            bad.append(f"DEBUG -> {c} does not expand out of the rule")
    # Authored ONCE: more than a couple of literal DEBUG rows means the enumeration came back.
    literal = len(re.findall(r"^\|\s*\d+\s*\|\s*`(?:TEST|E2E|GATE_A|GATE_B|CI|CONSOLIDATE)`\s*\|"
                             r"\s*`DEBUG`\s*\|", spec["edges"], re.M))
    if literal:
        bad.append(f"{literal} literal `X | DEBUG` rows — the rule is meant to be authored once")
    # The return guard must not restate its own destination.
    for _, guard in edges.get(("DEBUG", "TEST"), []):
        if "return_to" in guard:
            bad.append("the DEBUG return guard restates `debug_return_to`, which IS the destination "
                       "— that clause is what kept twelve rows in the table")
    return bad and "; ".join(bad)



# ======================================================================================
# RETIRED CHECKS — kept as a list, not as code.
#
# Each of these guarded a real defect and was written the day it was fixed. Each asserts the
# ABSENCE of a phrasing, which is the shape that locks the prose: a rewrite of the paragraph that
# EXPLAINS a removal reads, to a regex, exactly like the removal coming back. They are retired only
# because something else now catches the same defect, named here so the retirement is checkable
# rather than a claim.
#
#   no-monitor-references-remain
#     -> the monitor agent file is deleted, so there is nothing to revive; a reference coming back would be a reference to a file that does not exist
#   checkpoint-stops-where-a-milestone-finishes
#     -> `the-human-rows-are-the-only-stop-list` owns where the run stops, and `checkpoint` is a `run_mode` documented in one place (STRATEGY's contract) rather than copied
#   evals-readme-describes-what-is-there
#     -> the README no longer restates the suite table; `run_all.py --list` prints it from the
#        suites themselves, so there is no copy left to drift. This check existed ONLY because
#        the copy did, and it read only README.md — it caught none of the same drift in
#        docs/TESTING.md or docs/artifacts/index.html, which is the argument for deleting the copy
#        rather than adding two more checks.
#   start-and-end-are-notation-not-transitions
#     -> `published-counts-match-reality` fires the moment a row is added — the graph would read 40 transitions against every surface's 39 — and `graph_walk.py`'s coverage gate would demand a fixture traverse it
# ======================================================================================

def _fields_table(state):
    """Only state.md's `## Fields` table — the surface that DECLARES the schema.

    Every removal in this file is documented in a closing "What was removed, and why" table, which
    necessarily names the deleted fields. A check that greps the whole file therefore fails on the
    explanation of the thing it is checking for. Both schema-5 removal checks did exactly that on
    their first run; EVAL-INSTRUCTIONS.md calls this out ("fixes explain what they replaced, so the
    wrong wording appears in the file as a quotation") and it is still the easiest one to walk into.
    """
    m = re.search(r"^## Fields\n([\s\S]*?)(?=\n^---|\n^## )", state, re.M)
    return m.group(1) if m else ""


def _gate_row(text, n):
    """The one table row for return-gate check R<n>, and nothing after it.

    A fixed-width window would spill into the next row and let a neighbour satisfy the check —
    that exact bug made three checks in this suite inert. A gate row is one physical line, so the
    row IS the window.
    """
    m = re.search(rf"^\|\s*\*\*R{n}\*\*\s*\|.*$", text, re.M)
    return m.group(0) if m else None


@check("containment-check-needs-no-path-exemption",
       "R12 used to carve `docs/sdlc` out of `git status --porcelain`, because the run's state file "
       "lived in the repo under test and a bare status could never come back clean on a CORRECT run "
       "— a real agent truthfully reported the tree as not-pristine about dirt the orchestrator had "
       "made. The run directory is gitignored now, so ignored files never reach `git status` and the "
       "exemption has nothing to exempt. This is the SUCCESSOR of "
       "`containment-check-exempts-the-runs-own-bookkeeping`, inverted: an exemption in R12 was "
       "required, and is now a defect. Restoring one would re-open a blanket hole around the very "
       "directory holding every sibling's journal — which is why the OLD exemption needed a second "
       "rule bounding it. That guarantee did not ride on the exemption and does not need restating "
       "here: `agent-writes-only-its-own-journal` owns it, and R13 enforces it by reading the "
       "artifact rather than inferring it from `git status`")
def _(spec):
    row = _gate_row(spec["dispatch"], 12)
    if not row:
        return "workflow-dispatch.md has no R12 row"
    bad = []
    # Scoped to the ROW, not the file: the section below the table explains the exemption that was
    # deleted, and necessarily quotes it. A check that read the whole file would fire on its own
    # rationale — the single most common way a check here turns out to be wrong.
    if re.search(r":\(exclude\)|porcelain\s*--\s*\S", row):
        bad.append("R12 carries a path exemption again (`:(exclude)` or `git status --porcelain -- "
                   "<path>`). The run directory is gitignored, so a bare status is already clean on "
                   "a correct run; an exemption now only hides real dirt")
    if not re.search(r"`git status --porcelain`\s*(?:\*\*)?\s*empty", row):
        bad.append("R12 no longer demands a bare `git status --porcelain` be empty — the containment "
                   "check has no containment left")
    return bad and "; ".join(bad)


@check("ledger-records-without-forbidding-the-transition",
       "R9 said a bare ledger entry forbids a pass-shaped transition; nodes.md says a missing "
       "reviewer never halts the run. On `host: none` both gates ledger bare every time, so the two "
       "rules pointed opposite ways and a real run had to referee them")
def _(spec):
    row = _gate_row(spec["dispatch"], 9)
    if not row:
        return "workflow-dispatch.md has no R9 row"
    proceeds = re.search(r"missing reviewer never halts the run", spec["nodes"], re.I)
    if not proceeds:
        return ("nodes.md no longer says a missing reviewer never halts the run — R9 and the "
                "GATE_A ledger rule have to agree, and this check cannot referee them without it")
    bad = []
    if re.search(r"no\s+pass-shaped\s+transition", row, re.I):
        bad.append("R9 forbids a `pass-shaped transition` on a bare entry, contradicting nodes.md's "
                   "'a missing reviewer never halts the run' — ledgering records, it never routes")
    # It must still forbid the thing it exists to forbid.
    if not re.search(r"never be recorded as passed|not be recorded as passed", row, re.I):
        bad.append("R9 no longer forbids recording a bare-ledgered node as PASSED — that is the "
                   "check, and only the routing half was meant to go")
    if "edges.md" not in row:
        bad.append("R9 does not name `edges.md` as the authority for the transition, which is the "
                   "half that resolves the contradiction")
    return bad and "; ".join(bad)


@check("r7-separates-no-dispatcher-from-a-dead-dispatch",
       "R7 assumed GATE_A always ran as a Workflow. The `Workflow` tool is not reliably available "
       "in a subagent session; a real agent ran the four steps directly, refused to invent a run_id, "
       "and its honest bundle read as a dispatch failure that would charge GATE_A-dispatch")
def _(spec):
    d = spec["dispatch"]
    row = _gate_row(d, 7)
    if not row:
        return "workflow-dispatch.md has no R7 row"
    bad = []
    # The discriminator has to exist in the schema, or R7 has nothing to branch on.
    if not re.search(r"dispatch:\s*'workflow'\s*\|\s*'mimic'\s*\|\s*'direct'", d):
        bad.append("MILESTONE_BUNDLE's `gate_a` declares no `dispatch: 'workflow'|'mimic'|'direct'` "
                   "discriminator, so R7 cannot tell a dead dispatch from an absent one, nor a "
                   "faithful mimic from an ad-hoc pass")
    for value in ("mimic", "direct"):
        if value not in row:
            bad.append(f"the R7 row does not mention `{value}` dispatch at all")
    if not re.search(r"nothing is charged|charge nothing", row, re.I):
        bad.append("the R7 row does not say that a non-workflow dispatch charges nothing to "
                   "`GATE_A-dispatch` — spending that bound on a dispatcher that never existed "
                   "is the defect")
    # Every surface that instructs the agent has to know, or the agent still reports `0`.
    for name, text in (("code-quality-pipeline-node.md", spec["twins"].get(
                            "code-quality-pipeline-node.md", "")),
                       ("agents/sdlc-graph-milestone.md",
                        spec["published"].get("agents/sdlc-graph-milestone.md", ""))):
        for value in ("mimic", "direct"):
            if f'dispatch: "{value}"' not in text and f'dispatch = "{value}"' not in text:
                bad.append(f"{name} never tells the agent to report `dispatch: \"{value}\"`")
    return bad and "; ".join(bad)


@check("the-no-workflow-fallback-is-a-specified-mimic-not-a-free-hand",
       "The `Workflow` tool is absent in every subagent session observed so far, so the fallback IS "
       "the path Gate A actually takes. It used to be specified as 'run the four steps yourself, "
       "same order, same files' — which says nothing about grouping, concurrency, or which agent "
       "runs which step, so every fallback threw away the script's parallel fan-out AND its coverage "
       "arithmetic, and reported `groups_*: null` because there was nothing to count. A fallback "
       "that is the normal path deserves a contract, not a shrug")
def _(spec):
    def section(text, needle):
        """The one section that must carry the mimic contract, not the whole file.

        Scoping matters here and the control harness proved it: the first version of this check
        greped whole files, and three of its five negative controls came back DEAD — `concurrent`,
        `groups_*`/`real` and `pr-review-toolkit:code-reviewer` all appear elsewhere in the same
        documents, so sabotaging the mimic section left the check green. A check that reads the
        rest of the file is a check the mutation cannot reach.
        """
        i = text.find(needle)
        if i < 0:
            return ""
        j = text.find("\n### ", i + len(needle))
        return text[i:j if j > 0 else len(text)]

    d = section(spec["dispatch"], "### Mimicking the script when there is no `Workflow` tool")
    node = section(spec["twins"].get("code-quality-pipeline-node.md", ""),
                   "### When there is no `Workflow` tool — mimic the script")
    bad = []
    if not d:
        bad.append("workflow-dispatch.md has no § Mimicking the script section")
    if not node:
        bad.append("code-quality-pipeline-node.md has no § When there is no Workflow tool — mimic section")
    for name, text in (("workflow-dispatch.md", d), ("code-quality-pipeline-node.md", node)):
        if not text:
            continue
        # The agent must TRY the real thing first, or it never notices the day it works.
        if not re.search(r"(try|attempt)[^.\n]{0,80}(script|workflow)[^.\n]{0,40}first"
                         r"|(try|always attempt)[^.\n]{0,40}first", text, re.I):
            bad.append(f"{name}'s mimic section does not tell the agent to attempt the Workflow "
                       "script FIRST, so a session that gains the tool would never use it")
        # The mechanics that make a mimic faithful rather than a free hand.
        if not re.search(r"group.{0,25}by (directory|`?dirname)", text, re.I):
            bad.append(f"{name}'s mimic section does not specify grouping by directory")
        if not re.search(r"never truncat", text, re.I):
            bad.append(f"{name}'s mimic section does not say an oversized module is SPLIT, never truncated")
        if not re.search(r"concurrent", text, re.I):
            bad.append(f"{name}'s mimic section does not say the groups run concurrently — a "
                       "sequential mimic throws away the only reason to replicate the script")
        if not re.search(r"write.capable", text, re.I):
            bad.append(f"{name}'s mimic section does not say steps 1 and 4 need a WRITE-CAPABLE "
                       "reviewer, so a mimic can use a read-only one for steps that must APPLY fixes")
    # And the whole point: a mimic keeps the counters a `direct` pass cannot have.
    if d and not re.search(r"\*\*real\*\*", d, re.I):
        bad.append("workflow-dispatch.md's mimic section does not say it reports REAL `groups_*` — "
                   "without that it is `direct` under another name, and the coverage arithmetic "
                   "this section exists to preserve is still lost")
    return bad and "; ".join(bad)


@check("the-orchestrator-gates-its-own-work-too",
       "R0-R13 check everything an AGENT claims and nothing the ORCHESTRATOR does. A run audited "
       "against SKILL.md found four defects and every one was on the ungated side: a turn ended at "
       "an undeclared point (at a REPLAY boundary, not IMPLEMENT — the documented warning named the "
       "wrong node), two of three declared stops wrote no `stopped`, and all four "
       "orchestrator-authored observations blew the 200-char cap while all five agent-authored ones "
       "obeyed it. Discipline exists where it is checked")
def _(spec):
    sk, st = spec["skill"], spec["state"]
    bad = []
    i = sk.find("### 4b. The orchestrator's own gate")
    if i < 0:
        return "SKILL.md has no § The orchestrator's own gate, so nothing checks the orchestrator"
    j = sk.find("\n### ", i + 10)
    gate = sk[i:j if j > 0 else len(sk)]
    for tag, what in (("O1", r"turn does not end|does not end"),
                      ("O2", r"stopped"),
                      ("O3", r"200|≤ ?200"),
                      ("O4", r"history\[-1\]"),
                      ("O5", r"in_flight"),
                      ("O6", r"attempts"),
                      ("O7", r"edges\.md")):
        if tag not in gate:
            bad.append(f"the orchestrator gate has no {tag} row")
        elif not re.search(what, gate, re.I):
            bad.append(f"{tag} is listed but the gate never mentions what it checks ({what})")
    # O1 is the one that actually breaks, so it must be stated as the DEFAULT, not a reminder.
    if not re.search(r"turn continues unless|does not end", gate, re.I):
        bad.append("the gate does not state continuing as the DEFAULT — a reminder to keep going "
                   "reads as optional, and the failure it exists to stop is an orchestrator that "
                   "felt like reporting")
    # And the cap it enforces has to actually exist in the schema, on BOTH authored fields.
    if not re.search(r"`history\[\]\.observation`.{0,400}200", st, re.S):
        bad.append("state.md does not cap `history[].observation` at 200 chars for the orchestrator too")
    if not re.search(r"`history\[\]\.verified`.{0,400}300", st, re.S):
        bad.append("state.md does not cap `history[].verified` — the one authored field with no "
                   "return gate over it, and the one that ran longest in the audited run")
    return bad and "; ".join(bad)


@check("strategy-settles-every-field-and-proves-it",
       "STRATEGY exists so the loop never stops to DECIDE anything, which only holds if every field "
       "it settles is on disk when it exits. An answer given in conversation and never written is "
       "exactly what a resumed run cannot recover — and it re-opens the interruption the node was "
       "built to close. A real run left `stopped` unwritten at this very node")
def _(spec):
    n = spec["nodes"]
    i = n.find("#### The settlement check")
    if i < 0:
        return "nodes.md § STRATEGY has no settlement check, so its seven fields are settled on trust"
    j = n.find("\n### ", i)
    sec = n[i:j if j > 0 else len(n)]
    bad = [f"the settlement check never names `{f}`" for f in
           ("context.branching", "context.auto_open_mr", "context.run_mode", "context.has_ui",
            "context.standards_handshake", "cursor", "milestones[].deps")
           if f not in sec]
    # No alternation here. `on disk` was the second half of this and it appears in the section's own
    # rationale, so deleting the actual instruction left the check green — the "matched incidental
    # prose" failure this suite was written for, reproduced by its own author.
    if not re.search(r"read the state file back", sec, re.I):
        bad.append("the settlement check does not say to READ THE STATE FILE BACK — eyeballing the "
                   "conversation is what it exists to replace")
    if not re.search(r"BLOCKED", sec):
        bad.append("the settlement check does not say a still-null field is BLOCKED, so the "
                   "orchestrator may quietly default a decision it just promised not to infer")
    return bad and "; ".join(bad)


@check("every-subagent-is-two-journal-lines-and-still-only-telemetry",
       "A milestone agent is not one worker: `GATE_A` fans out to four agents per group, so a "
       "38-file milestone is dozens of them — and the whole fan-out used to report as ONE node "
       "line. Who reviewed which module, which of them came back empty, and which never came back "
       "at all was unrecoverable the moment the milestone returned. Two journal lines per subagent "
       "fix that; the danger in adding them is that a per-agent record starts being read as proof "
       "the agent ran, which is the one thing a journal may never be")
def _(spec):
    d = spec["dispatch"]
    i = d.find("### Every subagent you spawn gets two lines")
    if i < 0:
        return ("workflow-dispatch.md has no § Every subagent you spawn gets two lines, so a "
                "forty-agent Gate A is still one sentence")
    j = d.find("\n### ", i + 10)
    sec = d[i:j if j > 0 else len(d)]
    bad = []
    for ev in ("agent_spawn", "agent_done"):
        if ev not in sec:
            bad.append(f"the section never names the `{ev}` event")
        # The enum in the schema block is what a writer actually copies from.
        if not re.search(rf"//.*{ev}|\|\s*{ev}", d):
            bad.append(f"`{ev}` is described but missing from the journal's event enum")
    # Spawn ORDER is the whole claim the panel makes, and returns arrive out of order because the
    # groups are concurrent — so the ordinal has to be assigned at spawn and never re-sorted.
    if not re.search(r"assigned at spawn", sec, re.I):
        bad.append("the section does not say the ordinal is assigned AT SPAWN — pairing on arrival "
                   "renders concurrent groups in completion order and calls it the fan-out")
    # The useful case is the one that looks like missing data.
    if not re.search(r"never back-?fill", sec, re.I):
        bad.append("the section does not forbid back-filling a `done` line for an agent that never "
                   "returned, which is how a dead agent becomes a complete-looking list")
    # Under a real Workflow the agent did not spawn them and must not say it did.
    if not re.search(r'dispatch: "workflow"', sec):
        bad.append("the section does not say what to write under `dispatch: \"workflow\"`, where "
                   "the milestone agent spawned nothing itself and per-agent lines would be invented")
    # GATE_B is one Skill call that fans out internally, so it does not LOOK like a fan-out and the
    # pair gets forgotten. Two real milestones returned journals whose every agent_spawn sat under
    # GATE_A: the per-file gate showed 16 agents, the whole-diff gate showed none, and a reader
    # cannot tell that from a Gate B that never ran.
    if not re.search(r"Skill:code-review", sec):
        bad.append("the section does not say GATE_B owes a pair for its `code-review` Skill call, so "
                   "the whole-diff gate appears in the journal to have run on no agents at all — "
                   "indistinguishable from a Gate B that never ran")
    if not re.search(r"secrets", sec, re.I):
        bad.append("the section does not carry the never-paste-output/secrets rule, and it adds "
                   "three new free-text fields written straight into the repo")
    # And the line that keeps it honest: this is still the tier NOTHING routes on.
    if "telemetry, not evidence" not in d:
        bad.append("workflow-dispatch.md no longer says the journal is telemetry rather than "
                   "evidence — a per-agent record is exactly the thing that starts being cited as "
                   "proof a gate ran")
    # The agent that has to write them must be told to.
    ag = spec["published"].get("agents/sdlc-graph-milestone.md", "")
    if "agent_spawn" not in ag or "agent_done" not in ag:
        bad.append("the milestone agent is never told to write the two lines, so the contract "
                   "exists only in a file the writer does not read")
    return bad and "; ".join(bad)


@check("a-dead-dispatch-is-never-charged-to-the-findings-budget",
       "the `Unproven gate` row of § Five outcomes said a re-run 'counts against that node's own "
       "bound' with no exception, and SKILL.md's one-line summary of the same table said it again. "
       "So a correct reader charged a `GATE_A` whose dispatch ran ZERO agents to "
       "`attempts['GATE_A:<id>']` — the findings budget R7, `edges.md` § Loop bounds and `SKILL.md` "
       "§ 5 all reserve for real findings. Five outcomes is the only place a reader lands AFTER "
       "deciding the bundle is bad, so it is the most likely to be obeyed, and spending the findings "
       "budget on a harness crash silently downgrades the next security re-review. Found by running "
       "behavioural case 3, which exists to prevent exactly this")
def _(spec):
    # One rendering per surface, each scoped to the CELL/SENTENCE that carries the rule — the
    # paragraph explaining this fix necessarily quotes "that node's own bound", so anything
    # file-wide would be satisfied by its own rationale.
    renderings = [
        ("workflow-dispatch.md § Five outcomes → Unproven gate",
         next((l for l in spec["dispatch"].splitlines()
               if l.startswith("| **Unproven gate** |")), None)),
        ("SKILL.md § The return gate, the one-line summary of that table",
         (lambda m: m and m.group(0))(
             re.search(r"Unproven gate →[\s\S]{0,400}?(?=Fabricated →)", spec["skill"]))),
        ("docs/artifacts/index.html, the rendered outcomes table",
         next((l for l in spec["published"].get("docs/artifacts/index.html", "").splitlines()
               if "Unproven gate" in l), None)),
    ]
    bad = []
    for where, text in renderings:
        if not text:
            bad.append(f"{where} no longer states the Unproven-gate outcome at all")
            continue
        # Emphasis is not content, and the three surfaces spell it three ways — `**bold**`,
        # `<b>`, backticked code. Normalise it away or the check tests which file it is reading.
        text = re.sub(r"\*\*|</?b>|</?code>|`|&nbsp;", "", text)
        # The default must survive: over-correcting to "always the dispatch key" hands every
        # unproven gate a budget it did not spend.
        if not re.search(r"that node's\s+(own\s+)?bound", text):
            bad.append(f"{where} dropped the default rule — an unproven gate is re-run against "
                       f"that node's own bound")
        if "GATE_A-dispatch" not in text:
            bad.append(f"{where} says an unproven gate counts against that node's own bound with "
                       f"no exception, so a `GATE_A` whose dispatch ran zero agents is charged to "
                       f"the findings budget — the defect R7 and `edges.md` § Loop bounds forbid")
        elif not re.search(r"zero agents|groups_completed\W*==\W*0", text):
            bad.append(f"{where} names `GATE_A-dispatch` without saying which case takes it, so a "
                       f"gate that really ran and found a bug can claim it too")
    return bad and "; ".join(bad)


@check("the-has-ui-note-cites-the-guard-it-actually-means",
       "the edge-6 note said `NOT has_ui` made 'guard 14' match null. Guard 14 is `E2E → GATE_B`; "
       "the exit being described is `GATE_A`'s `has_ui == false` one. A reader cross-referencing "
       "lands on the wrong row, in the file that is authoritative for guards — the same stale-number "
       "class that put edges 13/14 and 18 into behavioural fixtures citing rows that had moved")
def _(spec):
    # Resolved FROM the table, never hardcoded: renumber the exits and this check follows them,
    # which is the half that makes it more than a spelling test.
    rows = re.findall(r"^\|\s*(\d+)\s*\|\s*`GATE_A`\s*\|\s*`\w+`\s*\|(.+?)\|\s*[^|]*\|\s*$",
                      spec["edges"], re.M)
    false_exit = [n for n, guard in rows if re.search(r"has_ui\s*==\s*false", guard)]
    if len(false_exit) != 1:
        return (f"edges.md has {len(false_exit)} `GATE_A` exits guarded on `has_ui == false`; the "
                f"note under edge 6 describes exactly one and cannot be checked against a table "
                f"that has none or two")
    want = false_exit[0]
    # The paragraph carrying the claim, not the file: `edges.md` cites guard numbers in a dozen
    # other notes and any of them would satisfy a file-wide match.
    para = next((p for p in re.split(r"\n(?=>?\s*\n|\n)", spec["edges"]) if "NOT has_ui" in p), None)
    if not para:
        return None          # the note was rewritten without the claim; nothing left to mis-cite
    cited = re.findall(r"guard\s+(\d+)", para)
    wrong = sorted({n for n in cited if n != want})
    if wrong:
        return (f"the `NOT has_ui` note cites guard {', '.join(wrong)}, but the `has_ui == false` "
                f"exit it describes is guard {want} — a reader cross-referencing lands on another "
                f"row entirely")
    if not cited and not re.search(r"has_ui\s*==\s*false", para):
        return ("the `NOT has_ui` note names neither the guard number nor the `has_ui == false` "
                "predicate, so nothing says which exit the null used to slip through")
    return None


@check("agent-lost-says-whether-blocked-is-really-published",
       "the `agent_lost` row assigned `status: BLOCKED` while calling itself 'a diagnosis, not a "
       "failure of the graph', and `SKILL.md` § 4 with `edges.md` § Loop bounds treat a dead agent "
       "that still has `MILESTONE-dispatch` budget as a retry the orchestrator simply takes, in the "
       "same turn. Two defensible readings — write-then-clear, or stay `RUNNING` — and an "
       "orchestrator driving a behavioural case followed the table and published `BLOCKED` for a run "
       "that never stopped, which the viewer and `audit_run.py` both read as a failed run")
def _(spec):
    lost = next((l for l in spec["state"].splitlines() if l.startswith("| `agent_lost` |")), None)
    if not lost:
        return "state.md has no `agent_lost` row in the `stopped.kind` table"
    cells = [c.strip() for c in lost.strip().strip("|").split("|")]
    bad = []
    # Scoped to the row, which is the thing that carries the rule. The prose below the table
    # explains why one field replaced two and would match half of this on its own.
    if not re.search(r"even when the re-spawn", lost, re.I):
        bad.append("the `agent_lost` row still does not say whether `BLOCKED` is published when the "
                   "re-spawn follows in the same turn — the ambiguity itself, which one orchestrator "
                   "resolved by publishing `BLOCKED` for a run that never stopped")
    if not re.search(r"dies between", lost, re.I):
        bad.append("the row does not say WHY it is written: the crash window between diagnosing the "
                   "death and spawning the replacement is the whole reason to write it at all")
    if len(cells) < 4 or "BLOCKED" not in cells[2]:
        bad.append("the row no longer assigns `BLOCKED`, so 'written even when the re-spawn "
                   "follows' now describes a status the table does not set — the two halves of the "
                   "resolution have to move together")
    elif not re.search(r"re-spawn", cells[3], re.I):
        bad.append("the row writes `BLOCKED` and no longer says the re-spawn clears it, which is "
                   "the half that keeps a resumed run from reading as a failed one")
    # The walker is the only surface that MECHANISES this, and it rejected the exact state the
    # table now prescribes — failure mode 13 inside the eval directory itself.
    invariant = next((l for l in (spec.get("walker") or "").splitlines()
                      if 'status"] == "BLOCKED"' in l), None)
    if invariant is None:
        bad.append("graph_walk.py no longer checks `status: BLOCKED` against `stopped.kind`")
    elif "agent_lost" not in invariant:
        bad.append("graph_walk.py's BLOCKED invariant admits only `kind: 'blocked'`, so the "
                   "write-then-clear state state.md prescribes is one no fixture may model")
    return bad and "; ".join(bad)


def do_list():
    """Every check and the real defect it guards against, printed from the registry.

    The `why` strings are this suite's institutional memory and they used to be copied — a table in
    `evals/README.md` restated twenty of them by hand, which is a copy of a copy: the prose already
    lives beside the code it describes. That table drifted (it cited a check that had been renamed,
    and then one that had been retired), and it was policed by a check that read only `README.md`.

    So the registry prints itself, and the README points here. One source, always current, and the
    `why` for a check that does not exist cannot survive because there is nowhere for it to sit.
    """
    for ident, why, _ in CHECKS:
        print(f"\n{ident}\n    {re.sub(r'\\s+', ' ', why)}")
    print(f"\n{len(CHECKS)} checks.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-dir", default=str(paths.SKILL))
    ap.add_argument("--list", action="store_true",
                    help="print every check and the defect it guards against, then exit")
    args = ap.parse_args()
    if args.list:
        return do_list()
    root = pathlib.Path(args.spec_dir)

    # Resolved through `lib/paths.py` so the layout is written down once. `--spec-dir` points at a
    # COPY of the plugin when `spec_controls.py` is driving, so every path below must hang off
    # `root` — never off this file's own location.
    files = paths.spec_files(root)
    try:
        spec = {
            "nodes": files["nodes"].read_text(encoding="utf-8"),
            "edges": files["edges"].read_text(encoding="utf-8"),
            "state": files["state"].read_text(encoding="utf-8"),
            "skill": files["skill"].read_text(encoding="utf-8"),
        }
    except FileNotFoundError as exc:
        print(f"cannot read the spec: {exc}")
        return 2

    # The agent — the file the executor of the milestone loop reads, and the one component
    # of the new architecture nothing checked until it had already shipped.
    agent = root.parent.parent / "agents" / "sdlc-graph-milestone.md"
    if agent.exists():
        spec["agent_file"] = agent.read_text(encoding="utf-8")

    # The behavioural cases. Structure only — obedience needs a model, not a checker.
    behavioural = root / "evals" / "behavioural" / "evals.json"
    if behavioural.exists():
        try:
            spec["behavioural"] = json.loads(behavioural.read_text(encoding="utf-8"))["evals"]
        except (json.JSONDecodeError, KeyError) as exc:
            spec["behavioural"] = []
            print(f"warning: evals.json is unreadable ({exc})")

    # The dispatch contract, and the twins the agent actually reads. A rule that lives only in
    # nodes.md/edges.md is a rule the agent never sees — it reads these.
    dispatch = files["dispatch"]
    if dispatch.exists():
        spec["dispatch"] = dispatch.read_text(encoding="utf-8")
    spec["twins"] = {}
    for path in paths.node_files(root):
        spec["twins"][path.name] = path.read_text(encoding="utf-8")

    # What is actually on disk in evals/ — so the README can be checked against reality rather
    # than against the last time someone remembered to update it.
    #
    # **Keyed by path relative to `evals/`, not by bare filename.** The suites now live in
    # subdirectories and `run_all.py` names them the same way; comparing a bare `graph_walk.py`
    # against a wired `walks/graph_walk.py` would report every suite as unwired, and comparing the
    # other way round — one bare name matching two files in different directories — would report
    # none. Both sides use the one key.
    evals_dir = root / "evals"
    spec["eval_suites"] = sorted(str(f.relative_to(evals_dir)).replace("\\", "/")
                                 for f in evals_dir.rglob("*.py")
                                 if f.name != "run_all.py" and "__pycache__" not in f.parts
                                 and ".scratch" not in f.parts)
    spec["eval_fixtures"] = sorted(f.name for f in (root / paths.REL_DIRS["fixtures"]).glob("*.json"))
    # The runner itself, and the non-Python harnesses it has to remember to call. Read from disk so
    # a suite that exists and is never invoked is a red check rather than a thing someone notices.
    spec["eval_harnesses"] = sorted(f.name
                                    for f in (root / paths.REL_DIRS["workflows"]).glob("*.harness.mjs"))
    # The control table, so `every-check-has-a-control` can read it. A check with no control is a
    # check nobody knows can fail, which is this suite's own first principle applied to itself.
    controls = evals_dir / "spec" / "spec_controls.py"
    if controls.exists():
        spec["controls"] = controls.read_text(encoding="utf-8")
    runner = evals_dir / "run_all.py"
    if runner.exists():
        spec["eval_runner"] = runner.read_text(encoding="utf-8")

    # The two checkers. They used to carry their own copies of the loop bounds; both now parse the
    # node contracts, and `loop-bounds-are-parsed-from-the-contract-never-copied` is what keeps a
    # literal from growing back in either.
    for key, rel in (("auditor", "audit/audit_run.py"), ("walker", "walks/graph_walk.py")):
        path = evals_dir / rel
        if path.exists():
            spec[key] = path.read_text(encoding="utf-8")

    # Every walk fixture, parsed. Some invariants are about the CORPUS rather than the prose —
    # a schema version the spec would refuse to resume, a deleted field still being written.
    spec["fixtures"] = {}
    for path in sorted((root / paths.REL_DIRS["fixtures"]).glob("*.json")):
        try:
            spec["fixtures"][path.name] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    # The eval directory's own prose. Not part of `published` — it publishes no counts and is not
    # read during a run — but it does describe the graph, and stale text here has already survived
    # one sweep. `rglob` rather than a pattern list: the list named three directories and the
    # restructure made five, which is precisely how a corpus quietly shrinks to nothing.
    spec["eval_prose"] = {}
    # `*.md` AND `*.json`. It was Markdown only, so `behavioural/evals.json` — 18 prompts and 18
    # expected outputs, all of it prose about this graph — was in no corpus any check could see.
    # It cited edges 18c and 18d, which have never existed. Found by RUNNING a behavioural case,
    # not by the suite that exists to catch exactly that.
    for pattern in ("*.md", "*.json"):
        for path in sorted(evals_dir.rglob(pattern)):
            if ".scratch" in path.parts or "walks/fixtures" in path.as_posix():
                continue          # fixtures carry edge ids the WALKER resolves; prose is the gap
            spec["eval_prose"][f"evals/{path.relative_to(evals_dir)}"] = path.read_text(encoding="utf-8")

    # The plugin's second skill. It reads this plugin's spec and writes into this plugin's evals/,
    # so it can go stale in both directions: pointing at a tier that no longer exists, or missing a
    # tier that was added. Both are silent — a reviewer that never writes an eval still produces a
    # confident report.
    reviewer = root.parent / "graph-run-reviewer"
    for key, rel in (("reviewer", "SKILL.md"), ("reviewer_checks", "checks/what-to-look-for.md")):
        f = reviewer / rel
        if f.exists():
            spec[key] = f.read_text(encoding="utf-8")

    # The E2E node's procedure lives in the testing-standards twin, not in nodes.md — a mandate
    # stated in one and not the other is the drift these checks exist for.
    e2e = root / paths.REL_DIRS["nodes"] / "testing-standards-node.md"
    if e2e.exists():
        spec["e2e"] = e2e.read_text(encoding="utf-8")

    # Every surface that publishes a count of the graph — prose, README, and the rendered docs.
    # Drift lived in the HTML longest, because nobody greps HTML.
    #
    # `docs/**/*.html`, not `docs/*.html`. Moving `index.html` into `docs/artifacts/` made the old
    # pattern match nothing, and `published-counts-match-reality` — the only check that reaches the
    # rendered surfaces at all — went green by looking at zero files. A glob narrowed by a file move
    # is a check switched off by a file move, and it announces nothing.
    plugin_root = root.parent.parent
    spec["published"] = {}
    for pattern in ("SKILL.md", "README.md", "graph/*.md", "nodes/*.md", "nodes/qa/*.md",
                    "subagents/*.md", "observability/*.md", "agents/*.md", "docs/**/*.html"):
        for path in sorted(plugin_root.glob(pattern)) + sorted(root.glob(pattern)):
            try:
                spec["published"][str(path.relative_to(plugin_root))] = path.read_text(encoding="utf-8")
            except (ValueError, OSError):
                continue

    failures = []
    for ident, why, fn in CHECKS:
        problem = fn(spec)
        if problem:
            failures.append((ident, why, problem))
            print(f"FAIL  {ident}")
            print(f"      {problem}")
            print(f"      (guards against: {why})")
        else:
            print(f"ok    {ident}")

    print()
    print(f"{len(CHECKS) - len(failures)}/{len(CHECKS)} spec-consistency checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
