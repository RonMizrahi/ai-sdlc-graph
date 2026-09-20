#!/usr/bin/env python3
"""The invariants a finished run state must satisfy, in one place.

`graph_walk.py` checks a run **while it is walked**; `audit_run.py` checks one **from the file
afterwards**. Different questions — but the properties of the resulting state are the same
properties, and they were implemented twice, in two files, in two vocabularies.

That is not only duplication. Measured before this module existed, the two implementations had
**diverged**: the walker enforced five invariants the auditor did not, so a real run could carry a
`milestones[].node` field deleted at schema 5, a ledger entry blaming an uninstalled Playwright, a
counter past its bound, a ledger entry naming a node that does not exist, or one missing its reason —
and `audit_run.py` would report it clean. The auditor is the tool pointed at *real* runs. It was the
weaker of the two.

So: one implementation, both callers. Each function takes the finished state and returns a list of
`(check-id, message)`. The check-ids are the auditor's, because those are the ones a person reads in
a report about a real run; the walker renders them as its own `problems` strings.

`audit_walks.py` is what keeps them honest — it replays every walk fixture to its end state and
audits it, so a rule the walker enforces and the auditor does not now fails on nine fixtures at once.
"""

# Fields deleted at schema 5. A run carrying one was written by a different graph, and `state.md`
# makes that an unconditional halt rather than something to interpret leniently.
DELETED_AT_5 = ("paused", "blocked", "debug")

TERMINALS = {"DONE", "BLOCKED", "HANDOFF"}

# A ledger entry blaming an uninstalled Playwright is the defect this exists to catch: `requires` is
# for capabilities a run CANNOT obtain, and Playwright is a devDependency plus a browser download.
# A real run ledgered E2E at milestone 1 for "Playwright is not installed and there is no runnable
# front-end yet" — both halves true, conclusion wrong, and the ledger is append-only so it could
# never be tidied away. The lookahead spares the legitimate entry: a `touches_ui` milestone that
# shipped without its Playwright SPECS is a mandate violation, not a missing tool.
import re

PLAYWRIGHT_BLAMED = re.compile(
    r"playwright(?!\s+(?:spec|test))[^.;]{0,60}?"
    r"(?:not installed|isn'?t installed|uninstalled|not available|unavailable|absent|missing)",
    re.I)


def entries(state):
    """`history[]`, or [] when it is not a list. Every caller wants the same defensive read."""
    h = state.get("history")
    return h if isinstance(h, list) else []


def bounds_respected(state, bounds):
    """No counter names an unbounded cycle, and none is past its limit."""
    out = []
    attempts = state.get("attempts") or {}
    if not isinstance(attempts, dict):
        return [("bounds-respected", "`attempts` is not an object")]
    for key, value in attempts.items():
        prefix = str(key).split(":")[0]
        # ABSENT and None are different answers. `CI` is in the table with no number — watch-ci's
        # bound is a 15-minute time budget and a 2-same-error guard, not a count — so `bounds.get()`
        # returning None conflated "this cycle has no declared bound" with "this cycle's bound is
        # not a number", and every fixture carrying a `CI:<id>` counter went red.
        if prefix not in bounds:
            out.append(("bounds-respected", f"attempts key {key!r} names no bounded cycle"))
            continue
        limit = bounds[prefix]
        if isinstance(limit, int) and isinstance(value, int) and value > limit:
            out.append(("bounds-respected", f"bound exceeded: attempts[{key}]={value} > {limit}"))
        elif not isinstance(value, int):
            out.append(("bounds-respected", f"attempts[{key}] is {value!r}, not a number"))
    return out


def inflight_agrees(state):
    """Every id in flight is a real milestone whose pre-spawn write happened, and a terminal run
    has none. The pre-spawn write is the whole point: an agent that dies before its first append is
    still findable, and its branch still diffable."""
    out = []
    ms = {str(m.get("id")): m for m in (state.get("milestones") or []) if isinstance(m, dict)}
    in_flight = state.get("in_flight")
    if in_flight is None:
        return [("inflight-agree", "no `in_flight` — schema 5 requires it, and a file without it "
                                   "cannot say whether an agent died mid-milestone")]
    unknown = [m for m in in_flight if str(m) not in ms]
    if unknown:
        out.append(("inflight-agree", f"in_flight names {sorted(unknown)}, which are not milestones"))
    blind = [m for m in in_flight
             if str(m) in ms and not (ms[str(m)].get("journal") and ms[str(m)].get("base_sha"))]
    if blind:
        out.append(("inflight-agree",
                    f"milestones {sorted(blind)} are in flight with no journal/base_sha recorded — "
                    f"the pre-spawn write did not happen, so a death in that window is unrecoverable"))
    if state.get("status") in TERMINALS and in_flight:
        out.append(("inflight-agree",
                    f"run ended {state['status']} with milestones still in flight: {sorted(in_flight)}"))
    return out


def history_is_sound(state):
    """Contiguous, under the runaway ceiling, and every entry carries its author's observation."""
    out = []
    h = entries(state)
    for a, b in zip(h, h[1:]):
        if isinstance(a, dict) and isinstance(b, dict) and a.get("to") != b.get("from"):
            out.append(("history-contiguous", f"history chain breaks: {a.get('to')} -> {b.get('from')}"))
    if len(h) > 250:
        out.append(("history-well-formed",
                    f"history length {len(h)} exceeds the 250 runaway ceiling — `state.md` makes that "
                    f"an unconditional halt above the per-cycle bounds"))
    missing = [i for i, e in enumerate(h, 1) if isinstance(e, dict) and not e.get("observation")]
    if missing:
        out.append(("observations-present", f"{len(missing)} history entries have no observation"))
    return out


def no_deleted_fields(state):
    """Nothing from schema 4 survives. Each of these was removed WITH the rule it needed, so a file
    carrying one is a file written against a graph whose rules are not these."""
    out = []
    for dead in DELETED_AT_5:
        if dead in state:
            out.append(("history-well-formed",
                        f"top-level `{dead}` — removed at schema 5, where `stopped` carries it"))
    for m in (state.get("milestones") or []):
        if isinstance(m, dict) and "node" in m:
            out.append(("history-well-formed",
                        f"milestone {m.get('id')} carries a `node` field — deleted at schema 5; a "
                        f"milestone's position is the last history[] entry carrying its id, and its "
                        f"completion is `delivered != null`"))
    return out


def ledger_is_well_formed(state, node_ids):
    """Every entry names a real node (or a return-gate check `R<n>`), carries a reason and a
    milestone, and does not blame an absent Playwright for a gate it should have installed."""
    out = []
    for g in (state.get("skipped_gates") or []):
        if not isinstance(g, dict):
            out.append(("no-unearned-passes", f"ledger entry is not an object: {g!r}"))
            continue
        name = str(g.get("node", ""))
        base = name.split(".")[0]
        if base not in node_ids and not re.fullmatch(r"R\d+", base):
            out.append(("no-unearned-passes", f"ledger entry names unknown node {name!r}"))
        if not g.get("reason") or g.get("at_milestone") is None:
            out.append(("no-unearned-passes",
                        f"ledger entry for {name} is missing a reason or milestone"))
        if PLAYWRIGHT_BLAMED.search(str(g.get("reason", ""))):
            out.append(("no-unearned-passes",
                        f"ledger entry for {name} blames an uninstalled Playwright — that is a "
                        f"dependency to install, not a capability the run cannot obtain"))
    return out


def check_all(state, bounds, node_ids):
    """Every invariant above, as one list of `(check-id, message)`."""
    return (bounds_respected(state, bounds)
            + inflight_agrees(state)
            + history_is_sound(state)
            + no_deleted_fields(state)
            + ledger_is_well_formed(state, node_ids))
