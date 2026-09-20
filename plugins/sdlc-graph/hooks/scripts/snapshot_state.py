#!/usr/bin/env python3
"""PostToolUse hook: keep every state a traced run passed through.

`state.json` is overwritten at every transition, so by the time a run is worth asking questions
about, every state but the last one is gone. `history[]` records that the graph *moved*; it does
not record what the file looked like while it was moving — the counters, the provisional
`progress` block, the ledger as it grew. Reconstructing that from the final file is guesswork.

So when a run is started with `--trace`, every write to its state file is copied into

    docs/graph-runs/<run-id>/history/0007_m2_GATE_A-to-E2E_20260808T091422Z.json

Numbered, so the order is never in doubt; named from the transition the state file itself
records, so `ls` reads as the run's story without opening anything.

**Telemetry, not evidence.** Nothing routes on `history/`. The return gate reads the bundle, the
auditor reads `state.json`. This hook never blocks, never exits 2, and a failed snapshot is a lost
snapshot rather than an interrupted run — the same rule the milestone journal already carries. If
that ever stops being true, this becomes a second thing that can stop a run, and it is not worth
that.

**Trace lives in the state file, not in the hook's own configuration.** The hook reads `trace` out
of the very file it is about to copy, so it cannot disagree with the run about whether tracing is
on, and there is nothing to keep in sync.

**It self-gates to nothing.** A plugin hook fires on every Write/Edit in every project the plugin
is installed in. `hooks.json` narrows by path before Python even starts; the guards below repeat
that check, because an `if` that a future runtime evaluates differently must not turn a no-op into
a surprise. Every exit path is 0.

    python3 evals/hooks/snapshot_state_selftest.py     # the pure core, with negative controls
"""
import datetime
import json
import pathlib
import re
import sys

RUNS_SEGMENT = "graph-runs"
STATE_NAME = "state.json"
SEQ = re.compile(r"^(\d{4})_")


def is_run_state(file_path):
    """Is this path a graph run's state file?

    Deliberately structural rather than clever: `<anything>/graph-runs/<run-id>/state.json`.
    Matching on the segment means the check holds when the project lives at an absolute path, a
    relative one, or on Windows.
    """
    if not file_path:
        return False
    parts = pathlib.PurePosixPath(str(file_path).replace("\\", "/")).parts
    return (len(parts) >= 3 and parts[-1] == STATE_NAME and parts[-3] == RUNS_SEGMENT)


def next_seq(existing):
    """One past the highest `NNNN_` already in `history/`. Starts at 1.

    Reads the directory rather than counting `history[]`, because a snapshot is also taken for
    writes that do not advance the trail — a `progress` tick while an agent works is a state the
    run passed through, and dropping it would leave gaps in a sequence whose whole purpose is
    that it has none.
    """
    highest = 0
    for name in existing:
        m = SEQ.match(name)
        if m:
            highest = max(highest, int(m.group(1)))
    return highest + 1


def _slug(text, limit=48):
    """A filename-safe fragment. Node ids are already `[A-Z_]`, so this only ever bites on junk."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(text)).strip("-")[:limit] or "unknown"


def snapshot_name(seq, state, ts):
    """`0007_m2_GATE_A-to-E2E_20260808T091422Z.json` — the story, readable from `ls`.

    The transition is read out of `history[-1]`, which already carries `from`, `to` and
    `milestone`. Nothing is guessed and nothing is passed in: if the state file cannot say where
    it just came from, neither can this.
    """
    history = state.get("history")
    last = history[-1] if isinstance(history, list) and history and isinstance(history[-1], dict) else None
    if last is None:
        # The first write of a run — INTAKE created the file and no transition has happened yet.
        where = f"{_slug(state.get('node') or 'INTAKE')}-created"
        milestone = None
    else:
        where = f"{_slug(last.get('from'))}-to-{_slug(last.get('to'))}"
        milestone = last.get("milestone")
    parts = [f"{seq:04d}"]
    if milestone is not None:
        parts.append(f"m{_slug(milestone, 8)}")
    parts += [where, ts]
    return "_".join(parts) + ".json"


def plan(file_path, text, existing, ts, previous=None):
    """The filename to write, or `None` to do nothing. Pure — this is what the self-test drives.

    Returning `None` is the overwhelmingly common case: this hook fires on every file edit in
    every project where the plugin is installed, and does nothing in all but a traced graph run.

    `previous` is the contents of the newest snapshot already in `history/`, or `None` when there
    is none. **A write that changed nothing is not a state the run passed through** — and any
    project with two graph plugins installed fires this hook twice for every single write, because
    each ships its own copy. Without this the second copy of every state lands as its own numbered
    entry and the sequence stops meaning anything. It used to live in `main()`, outside the pure
    function, so the self-test could not reach the one rule a double install depends on.
    """
    if not is_run_state(file_path):
        return None
    try:
        state = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None                      # a half-written file is not a state to keep
    if not isinstance(state, dict) or state.get("trace") is not True:
        return None                      # trace is opt-in, and absent is off
    if previous is not None and previous == text:
        return None
    return snapshot_name(next_seq(existing), state, ts)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not is_run_state(path):
        return 0

    try:
        state_path = pathlib.Path(path)
        if not state_path.is_absolute():
            state_path = pathlib.Path(data.get("cwd") or ".") / state_path
        text = state_path.read_text(encoding="utf-8")

        history_dir = state_path.parent / "history"
        existing = sorted(p.name for p in history_dir.glob("*.json")) if history_dir.exists() else []
        previous = (history_dir / existing[-1]).read_text(encoding="utf-8") if existing else None

        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = plan(path, text, existing, ts, previous)
        if not name:
            return 0
        history_dir.mkdir(parents=True, exist_ok=True)
        (history_dir / name).write_text(text, encoding="utf-8")
    except Exception:
        # A lost snapshot, never an interrupted run. `history/` is telemetry: nothing routes on it,
        # so there is no failure here worth surfacing into a run that is otherwise fine.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
