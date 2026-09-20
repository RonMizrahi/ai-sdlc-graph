#!/usr/bin/env python3
"""Audit a REAL run's state file, offline, after the fact.

This replaces something. The graph used to spawn a read-only monitor agent alongside every run; it
cost tokens continuously and, in the one event it existed to catch, died at a session rollover having
observed 0 of 28 transitions while nothing noticed. It is gone.

What it took with it was **independence**. The return gate that now stands between a milestone agent and
`history[]` is run BY the orchestrator, ON its own work — and a self-check reported by the thing being
checked is structurally weaker than an outside look, however good the checks are. This script is the
honest replacement: the same checks, re-runnable by anyone, from the file alone, at any time, with no
live agent and no transcript.

    python3 audit_run.py docs/graph-runs/<run-id>/state.json [--repo .] [--spec-dir <skills/sdlc-graph>]

Exit 0 when the trail holds up. Exit 1 when it does not. No dependencies.

**A check that cannot run is reported as NOT RUN, never as a pass.** That is the rule the whole graph
turns on, and it applies to its auditor first: without `--repo` the git-sourced checks say so out
loud rather than quietly counting as green.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

AGENT_NODES = {"BRANCH", "IMPLEMENT", "TEST", "GATE_A", "E2E", "GATE_B", "DEBUG"}

# The schema this auditor understands. A file written against a different one is not audited
# leniently — state.md makes a mismatch an unconditional halt, with no migration path.
SCHEMA_VERSION = 5

# The spec the checks read. `main()` overwrites it from `--spec-dir` before any check runs.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

SPEC_DIR = paths.SKILL

# Bounds are PARSED from the node contracts, never copied. They used to live in this dict as a
# third hand-maintained copy — after edges.md and the viewer — and `auditor-bounds-match-the-spec`
# existed only to police it. A bound raised in the spec and not here is an auditor that passes a
# run which exceeded it: the exact failure the auditor exists to catch, in the auditor.
def _bounds():
    paths.on_path()
    import graph_walk
    return graph_walk.parse_bounds(
        paths.NODES_MD
        .read_text(encoding="utf-8"))


BOUNDS = _bounds()
SECRETS = re.compile(r"ghp_[A-Za-z0-9]|glpat-|Bearer\s+\S|-----BEGIN|://[^/\s:]+:[^/\s@]+@")
# A pass-shaped guard is one that claims the node did its job. It is the exact shape that may not
# coexist with a ledger entry for that node at that milestone.
PASS_SHAPED = re.compile(r"\bgreen\b|not red|passing|verdict returned|merged|clean", re.I)
# …except where the guard ITSELF names the ledger. Several guards cover the degraded case in their
# own text — `CI -> QA` ("or host ∈ {gitlab, none} … logged to skipped_gates[]"), `E2E -> GATE_B`
# ("tool or app absent while has_ui → skipped_gates[]"), `TEST -> GATE_A` ("an absent suite is
# recorded to skipped_gates[] and never counted as passed"). On those edges a ledger entry beside
# the transition is the DESIGNED outcome: the run proceeds and the gate is recorded as NOT passed.
# Flagging them would be a false positive on every honest run, which is how a checker gets ignored.
#
# What remains — and what this check is actually for — is a node whose guard makes no such
# allowance exiting green while its own tool is in the ledger. `GATE_B -> CLOSE_OUT` on "tests green
# after review-and-fixes" with a `GATE_B` ledger entry is the shape: the reviewer never ran, and the
# gate went green anyway.
LEDGER_AWARE = re.compile(r"skipped_gates|ledger|logged to|recorded to", re.I)

results = []          # (level, check, message) — level: 'fail' | 'warn' | 'skip' | 'ok'


def report(level, check, message=""):
    results.append((level, check, message))


def git(repo, *args):
    try:
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


# ── the checks ────────────────────────────────────────────────────────────────────────────
def entries(s):
    """The history, minus anything that is not a transition record.

    This auditor is pointed at exactly the files that went wrong, so a malformed one is its normal
    input, not an edge case — and a traceback is the worst possible response to it: `main` prints the
    report only at the end, so a crash yields ZERO findings rather than a partial audit, and the
    person holding a broken run learns nothing. Every check reads the history through here."""
    return [h for h in (s.get("history") or []) if isinstance(h, dict)]


def check_history_shape(s):
    """A transition needs a `from` and a `to`, and the rest of the audit assumes it. Say so once,
    here, instead of crashing four checks later."""
    raw = s.get("history")
    if raw is None:
        return report("skip", "history-well-formed", "no history in this file")
    if not isinstance(raw, list):
        return report("fail", "history-well-formed", f"history is {type(raw).__name__}, not a list")
    bad = [f"#{i} is {type(h).__name__}" for i, h in enumerate(raw, 1) if not isinstance(h, dict)]
    bad += [f"#{i} has no {'/'.join(k for k in ('from', 'to') if not h.get(k))}"
            for i, h in enumerate(raw, 1) if isinstance(h, dict) and not (h.get("from") and h.get("to"))]
    if bad:
        return report("fail", "history-well-formed",
                      "the trail has entries that are not transitions: " + "; ".join(bad[:6]))
    report("ok", "history-well-formed")


def check_inflight(s):
    """Every milestone claimed in flight is real, and was written to BEFORE its agent was spawned.

    This replaced a check that two in-flight lists named the same set.
    Two lists of the same thing could disagree, so there was a check that they didn't; collapsing
    the second into `milestones[]` deleted the disagreement instead of policing it.

    What is left is the invariant that actually earns a check: the pre-spawn write. `journal` and
    `base_sha` are written before the Agent call, precisely so that an agent which dies before its
    first append is still findable and its branch still diffable. An id in flight whose milestone
    carries neither means the orchestrator spawned first and recorded second — and a crash in that
    window leaves a run nobody can reconstruct."""
    ms = {str(m.get("id")): m for m in (s.get("milestones") or []) if isinstance(m, dict)}
    in_flight = s.get("in_flight")
    if in_flight is None:
        return report("fail", "inflight-agree",
                      "no `in_flight` — schema 5 requires it, and a file without it cannot say "
                      "whether an agent died mid-milestone")
    unknown = [m for m in in_flight if str(m) not in ms]
    if unknown:
        return report("fail", "inflight-agree",
                      f"in_flight names {sorted(unknown)}, which are not milestones")
    missing = [m for m in in_flight
               if not ((ms[str(m)].get("journal")) and ms[str(m)].get("base_sha"))]
    if missing:
        return report("fail", "inflight-agree",
                      f"milestones {sorted(missing)} are in flight with no journal/base_sha recorded "
                      f"— the pre-spawn write did not happen, so a death in that window is unrecoverable")
    if s.get("status") in {"DONE", "BLOCKED", "HANDOFF"} and in_flight:
        return report("fail", "inflight-agree",
                      f"run ended {s['status']} with milestones still in flight: {sorted(in_flight)}")
    report("ok", "inflight-agree")


def check_stalled(s):
    """A RUNNING run with nobody working and nothing saying why.

    `in_flight` empty is normal between milestones — for the instant it takes to replay a bundle and
    spawn the next agent. It is NOT normal at rest: if the run is `RUNNING`, work remains, no agent is
    in flight and `stopped` is null, then nothing is happening and the file does not say so. That is
    byte-identical to a healthy run caught mid-write, which is exactly why it survives — and it is the
    halt this orchestrator actually commits. Observed: five milestones replayed, four continuing
    correctly into the next spawn, the fifth ending the turn on a summary with `cursor` pointing at a
    milestone that had no agent behind it.

    The rule is not "in_flight must be non-empty". It is: **either somebody is working, or `stopped`
    says why nobody is.**"""
    if s.get("status") != "RUNNING":
        return report("ok", "not-stalled")
    if s.get("in_flight"):
        return report("ok", "not-stalled")
    if s.get("stopped"):
        return report("ok", "not-stalled")
    ms = [m for m in (s.get("milestones") or []) if isinstance(m, dict)]
    remaining = [m.get("id") for m in ms if m.get("delivered") in (None, "")]
    # Past the milestone loop the tail nodes run inline, so an empty `in_flight` is correct there.
    if s.get("node") not in {"BRANCH", "IMPLEMENT", "TEST", "GATE_A", "E2E", "GATE_B", "DEBUG"}:
        return report("ok", "not-stalled")
    if remaining:
        return report("fail", "not-stalled",
                      f"RUNNING at {s.get('node')} with milestones {sorted(x for x in remaining if x is not None)} "
                      f"undelivered, in_flight empty and no `stopped` record — nobody is working and "
                      f"the file does not say why. Either spawn the next agent or write `stopped`")
    report("ok", "not-stalled")


def check_verified(s):
    """Every milestone-replayed transition records what the orchestrator checked before writing it.

    A milestone-replayed transition is one whose BOTH ends are milestone agent nodes. That is the whole milestone block —
    `BRANCH->IMPLEMENT` through the last hop into `GATE_B`, DEBUG round-trips included — and it
    deliberately excludes the root's own DEBUG traffic (`CI->DEBUG`, `DEBUG->CONSOLIDATE`) and the
    root-executed `GATE_B->CLOSE_OUT`, which the orchestrator witnessed itself.

    It is emphatically NOT keyed on `evidence` being present. It was, once, and that inverted the
    incentive it exists to create: a transition that returned evidence got checked, and one that
    returned nothing at all was exempt. Absent is not a pass, and it is least of all a pass here."""
    H = [h for h in (s.get("history") or []) if isinstance(h, dict)]
    replayed = [(i, h) for i, h in enumerate(H, 1)
                if h.get("from") in AGENT_NODES and h.get("to") in AGENT_NODES]
    if not replayed:
        return report("skip", "milestone-transitions-verified", "no milestone-replayed transitions in this trail")
    if (s.get("schema_version") or 0) != SCHEMA_VERSION and not any(
            h.get("verified") or h.get("evidence") for h in H):
        return report("skip", "milestone-transitions-verified",
                      "pre-delegation file — these nodes ran in the orchestrator, which witnessed them")
    bare = [f"#{i} {h.get('from')}->{h.get('to')}" for i, h in replayed if not h.get("verified")]
    if bare:
        return report("fail", "milestone-transitions-verified",
                      "written on the milestone agent's word, with no verification recorded: " + ", ".join(bare[:6]))
    report("ok", "milestone-transitions-verified")


def check_unearned_passes(s):
    """No node exits on a pass-shaped guard while a ledger entry exists for it at that milestone."""
    # `GATE_A.step2` and `GATE_A` mean different things, and collapsing them costs a real run a
    # false accusation. A SUB-STEP entry says one of the gate's four reviewers was absent — the gate
    # ran, degraded, and workflow-dispatch.md says the run proceeds. A BARE node entry says the gate
    # itself never ran, and that is the one that may not sit beside a pass-shaped exit.
    ledger = {(g.get("node", ""), g.get("at_milestone")) for g in s.get("skipped_gates") or []
              if "." not in g.get("node", "")}
    bad = [f"#{i} {h.get('from')} on '{(h.get('guard') or '')[:44]}'"
           for i, h in enumerate(entries(s), 1)
           if (h.get("from"), h.get("milestone")) in ledger
           and PASS_SHAPED.search(h.get("guard") or "")
           and not LEDGER_AWARE.search(h.get("guard") or "")]
    if bad:
        return report("fail", "no-unearned-passes",
                      "recorded as passed while its own gate is in the ledger: " + ", ".join(bad[:6]))
    report("ok", "no-unearned-passes")


def check_shared(s):
    """Every invariant `invariants.py` owns — the ones `graph_walk.py` also enforces.

    These used to live here AND in the walker, in two vocabularies, and they had drifted: the walker
    rejected a `milestones[].node`, a ledger entry naming an unknown node or missing its reason, a
    ledger entry blaming an uninstalled Playwright, and a counter past its bound; this file did not.
    The auditor is the tool pointed at REAL runs, and it was the weaker of the two.
    """
    import invariants
    node_ids = set(re.findall(r"^###\s+`(\w+)`",
                              (pathlib.Path(SPEC_DIR) / paths.REL["nodes"])
                              .read_text(encoding="utf-8"), re.M)) if SPEC_DIR else set()
    found = {}
    for check_id, message in invariants.check_all(s, BOUNDS, node_ids):
        found.setdefault(check_id, []).append(message)
    for check_id in ("bounds-respected", "inflight-agree", "history-contiguous",
                     "history-well-formed", "observations-present", "no-unearned-passes"):
        if check_id in found:
            report("fail", check_id, "; ".join(found[check_id][:6]))
        else:
            report("ok", check_id)


def check_bounds(s):
    bad = []
    for key, value in (s.get("attempts") or {}).items():
        prefix = key.split(":")[0]
        if prefix not in BOUNDS:
            bad.append(f"{key} names no bounded cycle")
        elif not isinstance(value, int) or isinstance(value, bool):
            bad.append(f"{key}={value!r} is not a count — a counter that is not a number is not counting")
        elif BOUNDS[prefix] is not None and value > BOUNDS[prefix]:
            bad.append(f"{key}={value} exceeds {BOUNDS[prefix]}")
    return report("fail", "bounds-respected", "; ".join(bad)) if bad else report("ok", "bounds-respected")


def check_observations(s):
    H = entries(s)
    empty = [i for i, h in enumerate(H, 1) if not (h.get("observation") or "").strip()]
    leaky = [i for i, h in enumerate(H, 1) if SECRETS.search(h.get("observation") or "")]
    if empty:
        report("fail", "observations-present",
               f"{len(empty)} transitions have no observation (entries {empty[:6]}) — the trail is the "
               f"only per-node record, and nothing else watches a run while it happens")
    else:
        report("ok", "observations-present")
    if leaky:
        report("fail", "observations-secret-free", f"possible credential in entries {leaky[:6]}")
    else:
        report("ok", "observations-secret-free")
    # Uniform cheerfulness is not a failure, but it is worth saying out loud.
    if H and not any(re.search(r"\bbut\b|degraded|absent|skipped|2nd|retry|failed|only just", h.get("observation") or "", re.I) for h in H):
        report("warn", "observations-say-something",
               "no observation records anything awkward across the whole run — possible, but it is "
               "also what a trail written after the fact looks like")


def check_chain(s):
    H = entries(s)
    breaks = [f"#{i} {a.get('to')} -> {b.get('from')}" for i, (a, b) in enumerate(zip(H, H[1:]), 1)
              if a.get("to") != b.get("from") and a.get("to") not in {"DONE", "BLOCKED", "HANDOFF"}]
    if breaks:
        return report("fail", "history-contiguous", "; ".join(breaks[:6]))
    if len(H) > 250:
        return report("fail", "history-contiguous", f"{len(H)} transitions exceeds the 250 ceiling")
    report("ok", "history-contiguous")


def check_guards_verbatim(s, spec_dir):
    edges_md = pathlib.Path(spec_dir) / paths.REL["edges"]
    if not edges_md.exists():
        return report("skip", "guards-verbatim", f"edges.md not found at {edges_md}")
    # ONE parser, shared with the walker. This file used to carry a second copy, which then had to
    # learn the `[handoff]` alias separately (it did not, and every legal strategy-D run looked like
    # it took an undeclared edge) and would have had to learn the `DEBUG` rule expansion separately
    # too. A second parser of the authoritative file is a second opinion about it.
    paths.on_path()
    import graph_walk
    declared = {k: [g for _, g in v]
                for k, v in graph_walk.parse_edges(edges_md.read_text(encoding="utf-8")).items()}
    norm = lambda x: re.sub(r"\s+", " ", re.sub(r"[`*]", "", x or "")).strip().lower()
    bad = []
    for i, h in enumerate(entries(s), 1):
        # A halt is an `on failure` row, not a numbered edge — there is no guard to quote, and
        # `blocked` is what makes it resumable. Requiring a guard here would fail every BLOCKED run.
        if h.get("to") == "BLOCKED":
            continue
        frm, to, guard = h.get("from"), h.get("to"), norm(h.get("guard"))
        opts = declared.get((frm, to))
        if opts is None:
            bad.append(f"#{i} {frm}->{to} is not a declared edge")
        # `norm(None)` and `norm("")` are both `""`, and `"" in anything` is True — so the substring
        # arm below used to turn GREEN precisely when there was no guard to quote, which is the one
        # case this check exists for. A missing guard is the failure, not the exemption.
        elif not guard:
            bad.append(f"#{i} {frm}->{to} records no guard at all")
        elif not any(guard == norm(o) or (len(guard) >= 12 and guard in norm(o)) for o in opts):
            bad.append(f"#{i} {frm}->{to} guard is not edges.md verbatim")
    return report("fail", "guards-verbatim", "; ".join(bad[:6])) if bad else report("ok", "guards-verbatim")


def check_trace_history(s, state_path):
    """With `trace: true`, is `history/` a complete numbered record of every state written?

    `trace` is opt-in, so **absence is NOT RUN, never a pass** — the same rule the journals get.
    That distinction is the whole value here: a run whose hook never fired looks identical, from
    `state.json` alone, to a run that was never traced, and reporting either as green would make
    the trace worth nothing at exactly the moment someone relies on it.
    """
    if s.get("trace") is not True:
        return report("skip", "trace-history-is-complete",
                      "the run was not started with --trace, so there is no history/ to check. "
                      "NOT a pass")
    hist_dir = pathlib.Path(state_path).parent / "history"
    snaps = sorted(p.name for p in hist_dir.glob("*.json")) if hist_dir.exists() else []
    if not snaps:
        return report("fail", "trace-history-is-complete",
                      "trace is on and history/ is empty or absent — the snapshot hook never fired. "
                      "The run believes it is being traced and nothing is being kept")

    seqs = []
    for name in snaps:
        m = re.match(r"^(\d{4})_", name)
        if not m:
            return report("fail", "trace-history-is-complete",
                          f"{name} has no NNNN_ prefix — the sequence is what makes history/ an "
                          f"order rather than a pile")
        seqs.append(int(m.group(1)))
    if seqs != list(range(1, len(seqs) + 1)):
        missing = sorted(set(range(1, max(seqs) + 1)) - set(seqs))
        return report("fail", "trace-history-is-complete",
                      f"the sequence has holes at {missing} — a gap looks exactly like a state that "
                      f"was never written, which is the one thing a trace exists to rule out")

    # Every transition the trail records should appear as a snapshot. MORE snapshots than
    # transitions is correct and expected: a `progress` tick while an agent works is a state the
    # run passed through, and there are usually several per node.
    hops = len([h for h in entries(s) if isinstance(h, dict)])
    if len(seqs) < hops:
        return report("fail", "trace-history-is-complete",
                      f"{len(seqs)} snapshots for {hops} transitions — the trail records states the "
                      f"history never kept, so the hook stopped firing part-way through the run")
    return report("ok", "trace-history-is-complete")


def check_journals(s, state_path):
    """R15, re-run offline: does each milestone agent's journal agree with the history it produced?

    The journals outlive the `inflight` entries on purpose — an entry is cleared when its replay is
    written, and the file stays as the run's account of how the milestone was built. So they are
    found beside the state file by run id, not from `inflight`, which by the end is empty on a healthy
    run."""
    state_path = pathlib.Path(state_path)
    run_id = s.get("run_id")
    # Journals are the state file's SIBLING DIRECTORY, not its siblings: docs/graph-runs/<run-id>/
    # holds state.json and journals/milestone-<id>.jsonl. Deriving them from the state path keeps
    # the auditor working on a run directory copied anywhere — which is how it is usually read.
    found = sorted((state_path.parent / "journals").glob("milestone-*.jsonl")) if run_id else []
    if not found:
        return report("skip", "journal-agrees-with-history",
                      f"no journals/milestone-*.jsonl beside the state file — an agent that died before its first append, or "
                      f"journals that were never written. NOT a pass: R13 did not run")

    H = entries(s)
    problems = []
    for path in found:
        # `milestone-2.jsonl` -> "2". It used to be `<run-id>-milestone-2.jsonl`, and the old
        # split left `mid` as the whole stem when the prefix went away — so every entry was
        # attributed to a milestone called "milestone-1", matched nothing in `history[]`, and
        # a HEALTHY run was reported as one that hid every node it ran. Caught by the
        # baseline case, which exists because a checker that fails on everything is not
        # evidence either.
        mid = path.stem.split("milestone-", 1)[-1]
        seen, seqs = {}, []
        for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                line = json.loads(raw)
            except json.JSONDecodeError as exc:
                problems.append(f"milestone {mid} line {n} is not JSON ({exc.msg}) — an append-only file "
                                f"with a torn line is a milestone agent that died mid-write")
                continue
            if not isinstance(line, dict):
                problems.append(f"milestone {mid} line {n} is not an object")
                continue
            if isinstance(line.get("seq"), int):
                seqs.append(line["seq"])
            if line.get("event") == "node_done" and line.get("node"):
                seen[line["node"]] = max(seen.get(line["node"], 1), line.get("attempt") or 1)
        if seqs != sorted(seqs) or len(set(seqs)) != len(seqs):
            problems.append(f"milestone {mid}: seq is not strictly increasing — appends were reordered, "
                            f"rewritten, or the file has more than one writer")
        # The direction that matters: work the journal saw and the trail does not contain.
        #
        # …EXCEPT on a halted run, where that gap is the CORRECT outcome rather than the defect. An
        # orchestrator that ran R15, caught a fabricated bundle and refused to record any of it
        # leaves exactly the same shape as the milestone agent that hid the work: a journal full of nodes and a
        # trail that never reaches them. Flagging it accused the run of the thing it had just
        # successfully prevented — found by a run eval, where an orchestrator did the right thing and
        # the auditor called it a fabrication.
        #
        # `blocked` is what tells them apart, and it is not a soft signal: it is written only by a
        # halt, and it names the node and the guards tested.
        halted = s.get("status") == "BLOCKED" or (s.get("stopped") or {}).get("kind") == "blocked"
        left = {h.get("from") for h in H if str(h.get("milestone")) == str(mid)}
        hidden = sorted(n for n in seen if n not in left)
        if hidden and halted:
            report("skip", "journal-agrees-with-history",
                   f"milestone {mid}: the trail stops short of {', '.join(hidden)}, and the run is halted "
                   f"— which is what a REFUSED bundle looks like, not a hidden one. R15's comparison "
                   f"needs a completed replay to mean anything")
            return
        if hidden:
            problems.append(f"milestone {mid}: the journal records {', '.join(hidden)} finishing and the "
                            f"trail never leaves {'them' if len(hidden) > 1 else 'it'} — a bundle "
                            f"that dropped work it had already written down (R15)")
        for node, attempt in seen.items():
            if attempt > 1:
                key = f"{node}:{mid}"
                charged = (s.get("attempts") or {}).get(key)
                if not isinstance(charged, int) or charged < attempt:
                    problems.append(f"milestone {mid}: journal shows attempt {attempt} at {node}, "
                                    f"attempts[{key}] is {charged!r} — a retry nobody was charged for")
    if problems:
        return report("fail", "journal-agrees-with-history", "; ".join(problems[:6]))
    report("ok", "journal-agrees-with-history")


def check_commits(s, repo):
    """commit => bundle => record, against git. The one check that needs the world."""
    if not repo:
        return report("skip", "commit-bundle-record",
                      "no --repo given, so nothing compared the branch against the trail — NOT a pass")
    recorded = {c for h in entries(s) for c in ((h.get("evidence") or {}).get("commits") or [])}
    inflight = {str(m.get("id")): m for m in (s.get("milestones") or [])
                if isinstance(m, dict) and m.get("base_sha")}
    problems = []
    for mid, rec in inflight.items():
        branch, base = rec.get("branch"), rec.get("base_sha")
        if not (branch and base):
            continue
        log = git(repo, "log", "--format=%H", f"{base}..{branch}")
        if log is None:
            problems.append(f"milestone {mid}: cannot read {base}..{branch} — the branch or base is gone")
            continue
        made = [c for c in log.splitlines() if c]
        unaccounted = [c[:8] for c in made if not any(c.startswith(r) or r.startswith(c[:7]) for r in recorded)]
        if unaccounted:
            problems.append(f"milestone {mid}: {len(unaccounted)} commit(s) on {branch} that no history entry "
                            f"accounts for ({', '.join(unaccounted[:4])})")
    # A milestone agent entry with no transitions after it and no `blocked` is the halt signature.
    if inflight and (s.get("stopped") or {}).get("kind") != "blocked":
        H = entries(s)
        for mid, rec in inflight.items():
            # `rec`, not `agent`. This read `agent.get(...)` — a name that has never existed in
            # this scope — so the whole check died with a NameError the moment anyone passed
            # `--repo`. It went unnoticed because the self-test only ever asserted the NO-repo path
            # (that it reports NOT RUN), so the branch that needs git was never executed. Found by
            # running the reviewer's own step-2 command against a real repository.
            at = rec.get("spawned_at_history_len")
            if isinstance(at, int) and len(H) <= at:
                problems.append(f"milestone {mid} was spawned at history length {at} and the trail has not "
                                f"grown since — the milestone agent died, or its replay was forgotten")
    return report("fail", "commit-bundle-record", "; ".join(problems)) if problems else report("ok", "commit-bundle-record")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("state")
    ap.add_argument("--repo", default=None, help="repo root, for the git-sourced checks")
    ap.add_argument("--spec-dir", default=str(paths.SKILL))
    args = ap.parse_args()

    try:
        s = json.loads(pathlib.Path(args.state).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"cannot read the run: {exc}")
        return 1

    # A check that dies takes its own finding down with it, but it may not take the other eight —
    # the whole point of this script is to say something useful about a file that is already wrong.
    global SPEC_DIR
    SPEC_DIR = pathlib.Path(args.spec_dir)

    for name, run_check in (("history-shape", check_history_shape),
                            ("not-stalled", check_stalled),
                            ("shared-invariants", check_shared),
                            ("milestone-transitions-verified", check_verified),
                            ("unearned-passes", check_unearned_passes),
                            ("observations", check_observations),
                            ("guards-verbatim", lambda st: check_guards_verbatim(st, args.spec_dir)),
                            ("journal-agrees-with-history", lambda st: check_journals(st, args.state)),
                            ("trace-history-is-complete", lambda st: check_trace_history(st, args.state)),
                            ("commit-bundle-record", lambda st: check_commits(st, args.repo))):
        try:
            run_check(s)
        except Exception as exc:
            report("fail", name, f"the check itself died on this file: {type(exc).__name__}: {exc}")

    print(f"audit — {s.get('run_id', '?')} · {s.get('status', '?')} at {s.get('node', '?')} · "
          f"{len(s.get('history') or [])} transitions\n")
    for level, ident, message in results:
        mark = {"ok": "ok   ", "fail": "FAIL ", "warn": "warn ", "skip": "NOT RUN"}[level]
        print(f"{mark} {ident}" + (f"\n        {message}" if message else ""))

    fails = [r for r in results if r[0] == "fail"]
    skips = [r for r in results if r[0] == "skip"]
    print(f"\n{len(results) - len(fails) - len(skips)} passed · {len(fails)} failed · {len(skips)} not run")
    if skips:
        print("A check that did not run is not a check that passed.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
