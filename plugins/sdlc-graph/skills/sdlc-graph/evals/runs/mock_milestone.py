#!/usr/bin/env python3
"""A milestone agent that does no work — the deterministic other side of a run eval.

Every eval in this directory except the ones under `runs/` is **static**: it reads the spec and asks
whether it contradicts itself. None of it executes anything, so none of it can catch an orchestrator
that reads the contract correctly and then behaves wrong — spawns before arming its monitor, writes
`history[]` from a bundle it never gated, or answers a dead milestone agent by waiting longer. Those are
behaviours, and behaviours have to be run.

Running them needs an *other side*, and a real milestone agent is the wrong one: two nondeterministic
actors prove nothing when the result disagrees, because you cannot tell which of them was wrong. So
this is a milestone agent with the model taken out. It appends exactly the journal lines a scenario dictates,
on the timing the scenario dictates, and returns exactly the bundle the scenario dictates — including
a dishonest one, which is the whole point of scenarios 03 and 05.

    python3 mock_milestone.py --script <scenario.json> --journal <path> [--bundle-out <path>]

What it is NOT: a model of a good agent. It is a fixture that happens to be executable. When a
scenario needs a *real* milestone agent's judgement — does a returned milestone agent refuse an instruction? — the scenario
says so and dispatches the real agent instead. See `runs/README.md`.
"""
import argparse
import datetime
import json
import pathlib
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True, help="JSON: {lines: [...], bundle: {...}, delay_s?}")
    ap.add_argument("--journal", required=True, help="the file to append to — one agent, one file")
    ap.add_argument("--bundle-out", default=None, help="where to write the returned bundle")
    ap.add_argument("--speed", type=float, default=1.0, help="multiplier on every scripted delay")
    args = ap.parse_args()

    script = json.loads(pathlib.Path(args.script).read_text(encoding="utf-8"))
    journal = pathlib.Path(args.journal)
    journal.parent.mkdir(parents=True, exist_ok=True)

    # Append, never rewrite, and flush per line. A scenario that watches this file live is reading it
    # while it is being written; a buffered writer would deliver every line at exit and quietly turn
    # a streaming test into a batch one that still passes.
    for line in script.get("lines", []):
        wait = float(line.pop("_delay_s", 0)) * args.speed
        if wait:
            time.sleep(wait)
        # `ts` is stamped HERE, at append time, not carried in the script.
        #
        # The journal contract declares `ts` on every line, and `state.md` defines
        # `progress.seen_at` as "timestamp of that line" and calls it THE liveness signal — the one
        # thing that distinguishes a working agent from a dead one. The mock emitted no `ts` at all,
        # so the scenario built to test provisional supervision could not exercise the staleness
        # check the spec routes on, and the orchestrator driving it had to stamp its own receipt
        # time. A stand-in that cannot satisfy the contract it stands in for tests the wrong thing.
        #
        # Stamped at write time rather than in the fixture because that is what makes timestamps
        # SPREAD across the run: a script carrying its own would deliver five identical ones, which
        # is the "written from memory on the way out" signature `real/` explicitly asserts against.
        line.setdefault("ts", datetime.datetime.now(datetime.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"))
        with journal.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            fh.flush()

    # A scenario can end without returning at all — that is scenario 04, the milestone agent that dies. There is
    # no bundle in that case, and the orchestrator's job is to notice the silence rather than wait.
    if script.get("dies"):
        print("mock milestone agent: died mid-node, no bundle", file=sys.stderr)
        return 137

    bundle = script.get("bundle")
    if bundle is None:
        print("mock milestone agent: script has neither `bundle` nor `dies`", file=sys.stderr)
        return 2
    out = json.dumps(bundle, ensure_ascii=False, indent=2)
    if args.bundle_out:
        pathlib.Path(args.bundle_out).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
