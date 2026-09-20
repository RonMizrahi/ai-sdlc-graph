#!/usr/bin/env python3
"""Can `audit_run.py` actually fail?

An auditor nobody audits is the shape this plugin keeps rediscovering: the monitor was assumed to be
watching while it observed 0 of 28 transitions, and Gate A once returned `clean: true` having run
zero agents. So this file takes a **healthy** run state, breaks it one way at a time, and asserts
that the auditor goes red for the right reason each time.

    python3 audit_selftest.py

Exit 0 when every mutation is caught AND the unmutated baseline passes. A control that cannot fail
is not evidence — and neither is a checker that fails on everything, which is why the baseline is
asserted too.
"""
import os
import json
import pathlib
import shutil
import tempfile
import subprocess
import sys

# The fixtures name an EDGE; the guard text is read from `edges.md` here. That is what makes
# `guards-verbatim` in audit_run.py meaningful rather than circular: the trail being audited quotes
# the authoritative file because it was BUILT from it, so a paraphrase can only come from a mutation
# — which is precisely what `paraphrase_a_guard` plants.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402
sys.path.insert(0, str(paths.WALKS))
import graph_walk as _gw

_EDGES = _gw.parse_edges(
    paths.EDGES_MD
    .read_text(encoding="utf-8"))


def guard_of(step):
    """The declared guard for a step's edge, or "" for a halt (no numbered edge declares it)."""
    for eid, guard in _EDGES.get((step["from"], step["to"]), []):
        if eid == step.get("edge"):
            return guard
    return ""


HERE = paths.AUDIT
AUDIT = HERE / "audit_run.py"

# A healthy delegated run, replayed from the walk fixture that exercises the delegated path. Built
# here rather than committed as a second copy: the fixture is the source of truth for what a legal
# run looks like, and a hand-written state file beside it would drift.
FIXTURE = paths.FIXTURES / "milestone-dies-and-is-respawned.json"


def baseline():
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    state = json.loads(json.dumps(spec["initial_state"]))
    for step in spec["steps"]:
        for key, value in (step.get("set") or {}).items():
            node, parts = state, key.split(".")
            for part in parts[:-1]:
                node = node[int(part)] if part.isdigit() and isinstance(node, list) else node.setdefault(part, {})
            last = parts[-1]
            if last.isdigit() and isinstance(node, list):
                idx = int(last)
                node.append(value) if idx == len(node) else node.__setitem__(idx, value)
            else:
                node[last] = value
        state["skipped_gates"].extend(step.get("skipped_gates", []))
        state["node"] = step["to"]
        state["history"].append({
            "from": step["from"], "to": step["to"], "guard": guard_of(step),
            "milestone": step.get("milestone"), "observation": step["observation"],
            "evidence": step.get("evidence"), "verified": (step.get("agent") or {}).get("verified")})
    return state


def audit(state, tmp, repo=None):
    tmp.write_text(json.dumps(state), encoding="utf-8")
    run = subprocess.run([sys.executable, str(AUDIT), str(tmp)] + (["--repo", str(repo)] if repo else []),
                         capture_output=True, text=True)
    red = [line.split()[1] for line in run.stdout.splitlines() if line.startswith("FAIL")]
    return run.returncode, red, run.stdout, run.stderr


# A malformed state file is this auditor's NORMAL input — it is pointed at the runs that went wrong.
# The report is printed only at the end of `main`, so an exception yields zero findings rather than a
# partial audit, and the person holding a broken run learns nothing at all. Each of these parses as
# JSON and once killed a different check outright.
MALFORMED = [
    ("a milestone agent entry with no `to`", lambda s: s["history"][1].pop("to")),
    ("a history entry that is not an object", lambda s: s["history"].append("oops")),
    ("an attempts counter that is a string", lambda s: s["attempts"].__setitem__("TEST:1", "3")),
    ("an entry with no `from`", lambda s: s["history"][2].pop("from")),
    ("a history that is not a list", lambda s: s.__setitem__("history", {"a": 1})),
]


# (label, mutation, the check that must go red). Each mutation is a defect this architecture can
# actually produce — not a syntactic corruption, which would prove nothing about the checks.
def drop_verified(s):        s["history"][1]["verified"] = None
# The five the auditor did NOT have before `invariants.py` existed. Each was enforced by
# `graph_walk.py` and by nothing that looks at a real run — so a run could carry any of them and
# audit clean. These are here to prove the shared module actually closed the hole rather than
# merely being imported.
def readd_milestone_node(s): s["milestones"][0]["node"] = "GATE_B_PASSED"
def readd_paused(s):         s["paused"] = {"reason": "a schema-4 field, back from the dead"}
def blame_playwright(s):     s["skipped_gates"].append(
                                 {"node": "E2E", "reason": "Playwright is not installed",
                                  "at_milestone": 1})
def ledger_unknown_node(s):  s["skipped_gates"].append(
                                 {"node": "WOBBLE", "reason": "no such node", "at_milestone": 1})
def ledger_no_reason(s):     s["skipped_gates"].append({"node": "TEST", "at_milestone": 1})


def ledger_a_green_gate(s):  s["skipped_gates"].append(
                                 {"node": "GATE_B", "reason": "code-review needs a PR; host is none",
                                  "at_milestone": 1})
def blow_a_bound(s):         s["attempts"]["TEST:1"] = 9
def invent_a_counter(s):     s["attempts"]["WOBBLE:1"] = 1
def empty_an_observation(s): s["history"][2]["observation"] = ""
def leak_a_token(s):         s["history"][2]["observation"] = "pushed with ghp_A1b2C3d4E5f6G7h8"
def paraphrase_a_guard(s):   s["history"][2]["guard"] = "tests were fine"
# A paraphrase is the EASY half. `norm(None)` and `norm("")` both flatten to `""`, and `"" in x` is
# always true — so for a while the substring arm of guards-verbatim went green precisely when there
# was no guard to compare, and a trail with every guard stripped audited clean. Both shapes are
# controls now, because the missing one is what an invented trail actually looks like.
def delete_a_guard(s):       s["history"][2].pop("guard", None)
def blank_every_guard(s):    [h.__setitem__("guard", "") for h in s["history"]]
# `verified` used to be demanded only where `evidence` was present, which exempted exactly the
# transitions that returned the least. Drop both from a milestone agent hop: absent is not a pass.
def drop_verified_and_evidence(s):
    for h in s["history"]:
        if h.get("from") in {"BRANCH", "IMPLEMENT", "TEST", "GATE_A", "E2E", "GATE_B", "DEBUG"} \
           and h.get("to") in {"BRANCH", "IMPLEMENT", "TEST", "GATE_A", "E2E", "GATE_B", "DEBUG"}:
            h["verified"] = None; h["evidence"] = None
            return
def strand_an_agent(s):      s.update(status="DONE", in_flight=[1])
# The pre-spawn write is what `in_flight` buys: a milestone claimed in flight whose `journal` and
# `base_sha` were never written is an orchestrator that spawned first and recorded second, and a
# crash in that window leaves a run nobody can reconstruct. This used to be "two lists disagree",
# which stopped being possible when the second list was deleted.
def spawn_before_recording(s):
    s.update(status="RUNNING", in_flight=[1])
    for m in s["milestones"]:
        if m.get("id") == 1:
            m.pop("journal", None); m.pop("base_sha", None)
def hide_a_commit(s):        s["history"][1]["evidence"] = {"commits": [], "run_id": None}
# The replay-boundary halt, exactly as a real run committed it: a milestone replayed and recorded,
# `in_flight` cleared, the cursor advanced — and then the turn ended instead of spawning the next
# agent. Nothing failed, so nothing wrote `stopped`, and the file is byte-identical to a healthy run
# caught between two writes. That indistinguishability is why it survives, and why the check is
# "somebody is working OR `stopped` says why nobody is" rather than "in_flight must be non-empty".
def stall_at_a_replay_boundary(s):
    s.update(status="RUNNING", node="BRANCH", in_flight=[], stopped=None)
    for m in s["milestones"]:
        m["delivered"] = None

MUTATIONS = [
    ("a milestone agent transition written with no verification", drop_verified, "milestone-transitions-verified"),
    ("a gate exiting green while its own tool is ledgered", ledger_a_green_gate, "no-unearned-passes"),
    ("a milestone carrying the `node` field deleted at schema 5", readd_milestone_node,
     "history-well-formed"),
    ("a top-level `paused`, which `stopped` replaced at schema 5", readd_paused,
     "history-well-formed"),
    ("a ledger entry blaming an uninstalled Playwright — a dependency, not a capability",
     blame_playwright, "no-unearned-passes"),
    ("a ledger entry naming a node that does not exist", ledger_unknown_node, "no-unearned-passes"),
    ("a ledger entry with no reason — an unexplained skip is an unexamined one", ledger_no_reason,
     "no-unearned-passes"),
    ("a bound exceeded", blow_a_bound, "bounds-respected"),
    ("an attempts key naming no bounded cycle", invent_a_counter, "bounds-respected"),
    ("an emptied observation", empty_an_observation, "observations-present"),
    ("a credential pasted into an observation", leak_a_token, "observations-secret-free"),
    ("a paraphrased guard", paraphrase_a_guard, "guards-verbatim"),
    ("a transition recording no guard at all", delete_a_guard, "guards-verbatim"),
    ("every guard in the trail blanked", blank_every_guard, "guards-verbatim"),
    ("a milestone agent hop with neither evidence nor verification", drop_verified_and_evidence,
     "milestone-transitions-verified"),
    ("a milestone agent still in flight at a terminal state", strand_an_agent, "inflight-agree"),
    ("a milestone spawned before its journal and base_sha were written",
     spawn_before_recording, "inflight-agree"),
    ("a run left at a replay boundary with nobody working and no `stopped`",
     stall_at_a_replay_boundary, "not-stalled"),
]


# R13 offline. The journals live beside the state file, so this mutation writes a real one rather
# than editing the state: it is the only check here whose input is a second file, and a self-test
# that faked it would not be exercising the lookup that makes the check work at all.
JOURNAL_CASES = [
    ("a journal recording a node the trail never got", "journal-agrees-with-history", [
        {"seq": 1, "event": "node_done", "node": "BRANCH", "milestone": 1, "attempt": 1,
         "headline": "branch created off main"},
        {"seq": 2, "event": "node_done", "node": "IMPLEMENT", "milestone": 1, "attempt": 1,
         "headline": "3 steps committed"},
        {"seq": 3, "event": "node_done", "node": "DEBUG", "milestone": 1, "attempt": 1,
         "headline": "root-caused the fixture failure"},   # ← the trail never leaves DEBUG
    ]),
    ("a retry the counters were never charged for", "journal-agrees-with-history", [
        {"seq": 1, "event": "node_done", "node": "BRANCH", "milestone": 1, "attempt": 1,
         "headline": "branch created off main"},
        {"seq": 2, "event": "node_done", "node": "TEST", "milestone": 1, "attempt": 3,
         "headline": "green on the 3rd attempt"},          # ← attempts["TEST:1"] says otherwise
    ]),
    ("a journal whose seq went backwards", "journal-agrees-with-history", [
        {"seq": 5, "event": "node_done", "node": "BRANCH", "milestone": 1, "attempt": 1,
         "headline": "branch created off main"},
        {"seq": 2, "event": "node_done", "node": "IMPLEMENT", "milestone": 1, "attempt": 1,
         "headline": "3 steps committed"},                 # ← rewritten, reordered, or two writers
    ]),
    ("a torn line from a milestone agent that died mid-write", "journal-agrees-with-history", "RAW:{\"seq\": 1, \"ev"),
]


def main():
    # A PRIVATE directory per run, not a fixed path inside the repo.
    #
    # This wrote `.audit-selftest-state.json`, `journals/` and `history/` straight into `evals/audit/`.
    # One run at a time that is fine. Ten agents driving run-evals in parallel — which is how this
    # suite is now actually exercised, and how the PostToolUse hook fires it — means every one of
    # them clobbers the others' fixtures mid-assertion. Observed: the same suite reporting 29/37 and
    # then 34/37 minutes apart with no edit between, and `spec_controls.py` crashing inside
    # `shutil.copytree` because a sibling created a directory while the tree was being copied.
    #
    # A suite whose result depends on who else is running is not evidence, and the failure it
    # produces looks exactly like a real regression.
    _tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="audit-selftest-"))
    tmp = _tmpdir / "state.json"
    failures = []
    # the baseline, the malformed corpus, the healthy journal, the journal mutations, and --repo
    # +4: baseline, healthy journal, halted-run exemption, --repo NOT RUN.
    # +6: the trace check — its NOT RUN case, four failure modes, and its baseline.
    # +1: the --repo branch executing at all.
    extra = len(MALFORMED) + len(JOURNAL_CASES) + 4 + 6 + 1
    try:
        code, red, out, _ = audit(baseline(), tmp)
        if code != 0:
            failures.append(f"the UNMUTATED baseline does not pass: {red}\n{out}")
            print(f"FAIL  baseline — a healthy run must audit clean, got {red}")
        else:
            print("ok    baseline audits clean")

        for label, mutate, expect in MUTATIONS:
            state = baseline()
            mutate(state)
            code, red, _, _ = audit(state, tmp)
            if expect in red:
                print(f"ok    caught: {label}")
            else:
                failures.append(f"{label!r} was NOT caught by {expect} (red: {red or 'nothing'})")
                print(f"FAIL  MISSED: {label} — expected {expect}, got {red or 'nothing'}")

        for label, mutate in MALFORMED:
            state = baseline()
            mutate(state)
            _, red, out, err = audit(state, tmp)
            if err.strip():
                failures.append(f"{label!r} crashed the auditor: {err.strip().splitlines()[-1]}")
                print(f"FAIL  CRASHED on {label} — a traceback prints no findings at all")
            elif not red:
                failures.append(f"{label!r} produced a clean audit")
                print(f"FAIL  {label} audits clean — a trail that is not a trail is not a pass")
            else:
                print(f"ok    survives and reports: {label}")

        # A healthy journal beside a healthy state must NOT trip the check — otherwise the four
        # mutations below prove only that the check fires on everything.
        state = baseline()
        healthy = [{"seq": i, "event": "node_done", "node": h["from"], "milestone": 1,
                    "attempt": 1, "headline": h.get("observation", "")[:120]}
                   for i, h in enumerate(state["history"], 1)
                   if h.get("from") in {"BRANCH", "IMPLEMENT", "TEST", "GATE_A", "E2E", "GATE_B"}]
        (tmp.parent / "journals").mkdir(exist_ok=True)
        jrn = tmp.parent / "journals" / "milestone-1.jsonl"
        try:
            jrn.write_text("\n".join(json.dumps(e) for e in healthy) + "\n", encoding="utf-8")
            _, red, out, _ = audit(state, tmp)
            if "journal-agrees-with-history" in red:
                failures.append(f"a HEALTHY journal was rejected: {out}")
                print("FAIL  a healthy journal trips the check — it would fire on every real run")
            else:
                print("ok    a healthy journal audits clean")

            # The exemption added after a run eval: on a HALTED run the same shape is the correct
            # outcome, not the defect. It must not become a loophole — a run that simply sets
            # `status: BLOCKED` should not thereby escape every journal check, so this asserts the
            # check reports NOT RUN (which is loud) rather than `ok` (which reads as verified).
            state = baseline()
            state["status"] = "BLOCKED"
            state["stopped"] = {"kind": "blocked", "at_node": "TEST", "guards_tested": ["R13"],
                                "tried": ["compared journal"], "at_milestone": 1}
            state["history"] = state["history"][:1]
            jrn.write_text("\n".join(json.dumps(e) for e in healthy) + "\n", encoding="utf-8")
            _, red, out, _ = audit(state, tmp)
            if "journal-agrees-with-history" in red:
                failures.append("a correctly-HALTED run is accused of hiding the work it refused")
                print("FAIL  a refused bundle is reported as a hidden one — the opposite outcome")
            elif "NOT RUN journal-agrees-with-history" not in out:
                failures.append("on a halted run the journal check went quiet instead of NOT RUN")
                print("FAIL  the halted-run exemption reads as a pass, not as a check that did not run")
            else:
                print("ok    a halted run reports NOT RUN, not a fabrication and not a pass")

            for label, expect, lines in JOURNAL_CASES:
                jrn.write_text(lines[len("RAW:"):] if isinstance(lines, str)
                               else "\n".join(json.dumps(e) for e in lines) + "\n", encoding="utf-8")
                _, red, _, err = audit(baseline(), tmp)
                if err.strip():
                    failures.append(f"{label!r} crashed the auditor: {err.strip().splitlines()[-1]}")
                    print(f"FAIL  CRASHED on {label}")
                elif expect in red:
                    print(f"ok    caught: {label}")
                else:
                    failures.append(f"{label!r} was NOT caught by {expect} (red: {red or 'nothing'})")
                    print(f"FAIL  MISSED: {label} — expected {expect}, got {red or 'nothing'}")
        finally:
            jrn.unlink(missing_ok=True)

        # ---- trace-history-is-complete -------------------------------------------------------
        # `trace` is opt-in, so the first case is the one that matters most: a run that was never
        # traced must report NOT RUN. If it reported `ok`, every untraced run in existence would
        # carry a green check about a directory that does not exist.
        hist = tmp.parent / "history"
        def snap(names):
            shutil.rmtree(hist, ignore_errors=True)
            hist.mkdir(parents=True, exist_ok=True)
            for n in names:
                (hist / n).write_text("{}", encoding="utf-8")

        try:
            state = baseline()
            _, red, out, _ = audit(state, tmp)
            if "NOT RUN trace-history-is-complete" not in out:
                failures.append("an untraced run must report NOT RUN for the trace check")
                print("FAIL  an untraced run does not report NOT RUN — absence reads as a pass")
            else:
                print("ok    an untraced run reports NOT RUN, never a pass")

            hops = len(baseline()["history"])
            TRACE_CASES = [
                ("trace on and history/ absent — the hook never fired",
                 "trace-history-is-complete", None),
                ("trace on and the sequence has a hole — a state that was never kept",
                 "trace-history-is-complete",
                 [f"{i:04d}_x_20260808T000000Z.json" for i in range(1, hops + 2) if i != 2]),
                ("a snapshot with no NNNN_ prefix — the numbering stops being an order",
                 "trace-history-is-complete",
                 ["first.json"] + [f"{i:04d}_x_20260808T000000Z.json" for i in range(1, hops + 1)]),
                ("fewer snapshots than transitions — the hook stopped part-way",
                 "trace-history-is-complete",
                 [f"{i:04d}_x_20260808T000000Z.json" for i in range(1, hops)]),
            ]
            for label, expect, names in TRACE_CASES:
                state = baseline(); state["trace"] = True
                shutil.rmtree(hist, ignore_errors=True)
                if names is not None:
                    snap(names)
                _, red, _, err = audit(state, tmp)
                if err.strip():
                    failures.append(f"{label!r} crashed the auditor")
                    print(f"FAIL  CRASHED on {label}")
                elif expect in red:
                    print(f"ok    caught: {label}")
                else:
                    failures.append(f"{label!r} was NOT caught by {expect}")
                    print(f"FAIL  MISSED: {label} — expected {expect}, got {red or 'nothing'}")

            # And the baseline for it: a COMPLETE trace must audit clean, or the four cases above
            # prove only that the check fires on everything.
            state = baseline(); state["trace"] = True
            snap([f"{i:04d}_x_20260808T000000Z.json" for i in range(1, hops + 4)])
            _, red, out, _ = audit(state, tmp)
            if "trace-history-is-complete" in red:
                failures.append("a COMPLETE trace was rejected")
                print(f"FAIL  a complete trace trips the check — it would fire on every traced run")
            else:
                print("ok    a complete trace audits clean (more snapshots than hops is correct)")
        finally:
            shutil.rmtree(hist, ignore_errors=True)

        # ---- the --repo branch actually EXECUTING ---------------------------------------------
        # `commit-bundle-record` is the one check that needs git, and for a long time the only
        # thing asserted about it was that it reports NOT RUN *without* `--repo`. So the branch
        # that needs git was never executed by any test, and it carried a NameError — `agent.get`
        # for a name that has never existed in that scope. The whole check died the moment anyone
        # passed a real repository, which is the only way it is ever used.
        #
        # Found by running the reviewer's own step-2 command against a real repo, not by this
        # suite. That is the gap this case closes: NOT RUN is a valid outcome to assert, and
        # asserting only NOT RUN means the code under test never ran.
        # Hermetic against an INHERITED git environment. `git` exports GIT_DIR, GIT_INDEX_FILE,
        # GIT_WORK_TREE and friends into every hook subprocess, so when this suite runs from a
        # pre-push hook those point at the pushing repository — and `git -C <tmp> commit` then
        # commits against the WRONG repo and dies. Standalone it passed every time; under the
        # repo's own pre-push eval gate it failed every time, which reads as a flaky suite and is
        # not one. Scrub the whole GIT_* namespace for these children.
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

        def git(*args, **kw):
            return subprocess.run(["git", *args], env=env, **kw)

        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td)
            git("init", "-q", "-b", "main", str(repo), check=True)
            for cmd in (["config", "user.email", "e@x"], ["config", "user.name", "n"]):
                git("-C", str(repo), *cmd, check=True)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            git("-C", str(repo), "add", "-A", check=True)
            git("-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-qm", "base", check=True)
            base = git("-C", str(repo), "rev-parse", "HEAD",
                       capture_output=True, text=True).stdout.strip()
            git("-C", str(repo), "checkout", "-q", "-b", "m1/work", check=True)
            (repo / "f.txt").write_text("work\n", encoding="utf-8")
            git("-C", str(repo), "add", "-A", check=True)
            git("-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-qm", "work", check=True)
            head = git("-C", str(repo), "rev-parse", "HEAD",
                       capture_output=True, text=True).stdout.strip()

            state = baseline()
            for m in state["milestones"]:
                if m.get("id") == 1:
                    m["branch"], m["base_sha"] = "m1/work", base
            for h in state["history"]:
                if h.get("evidence"):
                    h["evidence"] = {"commits": [head], "run_id": None}
                    break
            code, red, out, err = audit(state, tmp, repo=repo)
            if err.strip() or "the check itself died" in out:
                failures.append("commit-bundle-record dies when --repo is actually supplied")
                print(f"FAIL  the --repo branch CRASHES: "
                      f"{(err.strip() or out).splitlines()[-1][:120]}")
            elif "NOT RUN commit-bundle-record" in out:
                failures.append("commit-bundle-record still reports NOT RUN with a real --repo")
                print("FAIL  --repo was given and the check still did not run")
            else:
                print("ok    the --repo branch executes against a real repository")

        # --- this suite does not commit into whatever repo it is run from -----------------------
        # The case above used to inherit the ambient git environment. `git` exports GIT_DIR,
        # GIT_INDEX_FILE and GIT_WORK_TREE into every hook subprocess, so under the repo's own
        # pre-push gate its `git init` / `git add -A` / `git commit` ran against the PUSHING
        # repository: three commits and a branch `m1/work` landed on the branch being pushed, and
        # README.md was overwritten with "base". Standalone the suite passed every time, which is
        # why it read as a flaky test rather than a destructive one.
        #
        # So the regression is not "does it pass" — it did — but "does it leave the surrounding
        # repository alone". Point GIT_DIR at a real, empty repo and require it to still have zero
        # commits afterwards.
        # Re-runs THIS suite under a hostile git environment, so the whole file is covered rather
        # than the one case that happened to be caught. `SDLC_SELFTEST_HERMETIC_CHILD` stops the
        # child running this probe again — without it the recursion never bottoms out.
        if not os.environ.get("SDLC_SELFTEST_HERMETIC_CHILD"):
            with tempfile.TemporaryDirectory() as sentinel_dir:
                sentinel = pathlib.Path(sentinel_dir) / "sentinel"
                clean_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
                subprocess.run(["git", "init", "-q", "-b", "main", str(sentinel)],
                               env=clean_env, check=True)
                hostile = dict(os.environ, GIT_DIR=str(sentinel / ".git"),
                               SDLC_SELFTEST_HERMETIC_CHILD="1")
                probe = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve())],
                                       env=hostile, capture_output=True, text=True)
                landed = subprocess.run(["git", "-C", str(sentinel), "rev-list", "--all", "--count"],
                                        env=clean_env, capture_output=True,
                                        text=True).stdout.strip()
                extra += 1
                if probe.returncode != 0:
                    failures.append("the suite fails when a git environment is inherited")
                    print("FAIL  inherited GIT_* breaks this suite — it is not hermetic: "
                          f"{(probe.stdout + probe.stderr).strip().splitlines()[-1][:110]}")
                elif landed not in ("", "0"):
                    failures.append(f"the suite committed {landed} time(s) into the ambient repo")
                    print(f"FAIL  NOT HERMETIC: {landed} commit(s) landed in the repo "
                          "GIT_DIR pointed at")
                else:
                    print("ok    inherited GIT_* is scrubbed — this suite commits into no repo "
                          "but its own")

        # `hide_a_commit` is the one that needs git, so it is asserted as NOT RUN without --repo
        # rather than quietly counted. The rule the graph turns on applies to its auditor first.
        state = baseline(); hide_a_commit(state)
        _, _, out, _ = audit(state, tmp)
        if "NOT RUN commit-bundle-record" not in out:
            failures.append("without --repo, commit-bundle-record must report NOT RUN, not pass")
            print("FAIL  commit-bundle-record is silently passing without a repo to check against")
        else:
            print("ok    commit-bundle-record reports NOT RUN without --repo, never a pass")
    finally:
        shutil.rmtree(_tmpdir, ignore_errors=True)

    print(f"\n{len(MUTATIONS) + extra - len(failures)}/{len(MUTATIONS) + extra} auditor self-tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
