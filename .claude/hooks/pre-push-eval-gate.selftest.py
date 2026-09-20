#!/usr/bin/env python3
"""Can the eval gate actually fail? Prove it, one planted defect at a time.

    python3 .claude/hooks/pre-push-eval-gate.selftest.py

The gate exists to say "this push rests on stale test evidence". A gate that always says yes is
worth exactly what a check that cannot fail is worth — and this repo has shipped two of those, both
written the same hour as the thing they guard. So every case below is a **negative control**: it
plants one specific defect and requires the gate to name it, and the green cases sit beside them so
that "it passes everything" fails here too.

Nothing here touches the committed receipts file or the real repository state:
`SDLC_EVAL_RECEIPTS` is redirected to a temp file before the modules load, and the two drive cases
stand a stub in for `claude` via `SDLC_EVAL_CLAUDE_BIN`. The whole run costs seconds and no money.

**The drive cases are the ones worth reading.** `--drive` spends minutes and real money per test,
so nothing can afford to exercise it for real on every check. What it CAN prove for free, against
the real `run_scenario.py`, is the rule the whole mechanism rests on: *a driven run that fails
writes no receipt*. A receipt for a red run is worse than no receipt at all, because the gate
would then go green on it forever.
"""
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
TMP = pathlib.Path(tempfile.mkdtemp(prefix="eval-gate-selftest-"))

# Before the modules load: they read this at import time, and nothing below may reach the real file.
os.environ["SDLC_EVAL_RECEIPTS"] = str(TMP / "RECEIPTS.json")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load("eval_receipts", "eval-receipts.py")
G = _load("gate", "pre-push-eval-gate.py")

VIEWER = "plugins/sdlc-graph-viewer/skills/view-run/viewer/run-viewer.html"
STABLE = "plugins/sdlc-graph/skills/sdlc-graph/references/edges.md"
INSTALL = "plugins/sdlc-graph-engineering-install/skills/x/references/evals.md"
OUTSIDE = "docs/assets/superpowers-graph-spine.svg"

results = []


def case(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'ok   ' if ok else 'FAIL '} {name}" + (f"\n      {detail}" if not ok and detail else ""))


def receipts_for(tests, status="passed", provenance="checked"):
    """A full set of valid, correctly sealed receipts — the state a repo is in when it is honest."""
    doc = {}
    for t in tests:
        body = {"kind": t.kind, "test": R.rel(t.path), "claim": t.claim,
                "status": status, "provenance": provenance, "run_at": "2026-08-08T00:00:00Z",
                "verdict": "PASS", "inputs": dict(t.inputs)}
        body["seal"] = R.seal_of(body)
        doc[t.id] = body
    return doc


# --------------------------------------------------------------------- 1. the staleness rule
tests = R.discover()
case("there is a tier-2 registry at all", len(tests) >= 11,
     f"discovered only {len(tests)} tests — a registry that finds nothing passes everything")

fresh = receipts_for(tests)
case("a fresh receipt passes", R.problems_for(tests, fresh) == [],
     str(R.problems_for(tests, fresh)[:1]))

# NEGATIVE CONTROL: the spec moved under one test. This is the only moment re-driving is worth
# minutes and money, so it is the one the gate exists to catch.
stale = json.loads(json.dumps(fresh))
target = tests[0]
stale[target.id]["inputs"]["graph/edges.md"] = "sha256:0000000000000000"
stale[target.id]["seal"] = R.seal_of(stale[target.id])       # resealed — a real edit, not a forgery
problems = R.problems_for(tests, stale)
case("a STALE receipt fails, and names the input that moved",
     [p[:2] for p in problems] == [(target.id, "stale")] and "graph/edges.md" in problems[0][2],
     f"got {problems}")

# NEGATIVE CONTROL: no receipt. A test that has never run and a test whose receipt was deleted are
# the same fact, and both have to be red — otherwise deleting a receipt is a way to pass.
missing = {k: v for k, v in fresh.items() if k != target.id}
problems = R.problems_for(tests, missing)
case("a MISSING receipt fails",
     [p[:2] for p in problems] == [(target.id, "no receipt")], f"got {problems}")

# NEGATIVE CONTROL: recorded, honestly, as never having run. Must not read as evidence.
never = json.loads(json.dumps(fresh))
never[target.id] = {"kind": target.kind, "test": R.rel(target.path),
                    "status": "never-run", "provenance": "none", "note": "never driven"}
problems = R.problems_for(tests, never)
case("a NEVER-RUN receipt fails",
     [p[:2] for p in problems] == [(target.id, "never-run")], f"got {problems}")

# NEGATIVE CONTROL: the cheap forgery — flip a field by hand and commit it. The seal is
# tamper-evident, not tamper-proof (there is no secret to keep in a public repo), and this is
# exactly the class it is meant to stop: a `never-run` typed into a `passed`.
forged = json.loads(json.dumps(fresh))
forged[target.id]["run_at"] = "2026-12-31T00:00:00Z"
problems = R.problems_for(tests, forged)
case("a HAND-EDITED receipt fails its seal",
     [p[:2] for p in problems] == [(target.id, "seal broken")], f"got {problems}")

# ...and a correctly resealed receipt is still caught by the hashes. The seal is not the only
# check, so re-sealing a lie about which spec was tested does not buy anything.
case("resealing does not launder a stale receipt",
     [p[1] for p in R.problems_for(tests, stale)] == ["stale"])

# --------------------------------------------------------------------- 2. scope: what fires at all
#
# The rule is one sentence — a path fires if any DIRECTORY in it has `sdlc` in its name — and the
# cases below are what that sentence has to buy. Everything outside the plugins must be silent and
# instant, because that is the whole reason this gate moved off `git commit`: a developer pushing a
# diagram should never pay for a graph suite. And `sdlc-graph-engineering-install` must be caught
# without anyone having remembered to add it to a list, because nobody did.
for name, paths, want in [
    ("an sdlc plugin fires", [VIEWER], [VIEWER]),
    ("...and so does the one nobody would have remembered to list", [INSTALL], [INSTALL]),
    ("a non-plugin path is silent", [OUTSIDE], []),
    ("...as is the rest of the repo's own furniture", [
        "docs/assets/a-diagram.svg",
        "THIRD-PARTY-NOTICES.md",
        ".githooks/pre-push"], []),
    ("a repo-root file is silent", ["README.md"], []),
    ("...even one whose own NAME says sdlc — naming a thing is not changing it",
     ["sdlc-graph-notes.md"], []),
    ("...and so is an sdlc-named FILE under a non-sdlc directory",
     ["docs/sdlc-graph-plan.md"], []),
    ("a MIXED push fires, and selects only the sdlc paths",
     ["README.md", OUTSIDE, VIEWER, "CLAUDE.md"], [VIEWER]),
]:
    got = G.sdlc_paths(paths)
    case(name, got == want, f"got {got}, want {want}")

case("an unrelated set selects nothing",
     G.sdlc_paths(["README.md", "CLAUDE.md", "docs/assets/x.svg"]) == [])
case("tier 1 routes through the SAME table as the PostToolUse hook",
     G.tier1_runners([VIEWER]) == G.evalhook.runners_for(VIEWER) + [G.SELFTEST],
     f"got {G.tier1_runners([VIEWER])}")
# The method plugin sits under an sdlc-named directory and has no suite. Before this case, such a
# push ran NOTHING — not one runner, not even the routing self-test — and exited 0 in silence,
# which looks exactly like a push that was checked. The self-test is what tells a deliberate
# absence from a routing table that has quietly stopped naming a plugin that does have a suite.
case("an sdlc plugin with no suite still runs the routing self-test, and only that",
     G.tier1_runners([INSTALL]) == [G.SELFTEST], f"got {G.tier1_runners([INSTALL])}")
case("the graph's edit does not drag in a runner that is not on disk",
     all((REPO / r).exists() for r in G.tier1_runners([STABLE])))
# Tier 2 is REPORTED for the plugins that carry an executing tier, and it decides nothing either
# way. The verdict cases below are what hold that second half.
case("tier 2 is reported for the plugin that carries an executing tier",
     G.wants_receipts([STABLE]))
case("...and not for one that carries none — the viewer, the method plugin, a diagram",
     not G.wants_receipts([VIEWER]) and not G.wants_receipts([OUTSIDE])
     and not G.wants_receipts([INSTALL]))

# The agent-facing path sees EVERY Bash command in the repo, so what it declines to look at matters
# as much as what it blocks. The last case here is not hypothetical: back when this gate keyed on
# `commit`, a `\bgit\b[^&|;]*\bcommit\b` regex blocked its own development, matching `~/git/` and
# `pre-commit-eval-gate.py` on a command line that ran no git at all. Same shape, new subcommand.
for cmd, want, why in [
    ("git push", True, "the plain case"),
    ("git -C /tmp/repo push -u origin wip", True, "a global option with a value before the subcmd"),
    ("/usr/bin/git push --force-with-lease", True, "an absolute path to git"),
    ("git commit -m x && git push", True, "the second segment of a chain"),
    ("git push --dry-run", True, "a dry run still asks the same question of the same range"),
    ("git log --oneline", False, "another subcommand"),
    ("git show HEAD:file", False, "not a push at all"),
    ("echo 'push'", False, "the word in an argument"),
    ("cd ~/git/marketplace && python3 .claude/hooks/pre-push-eval-gate.py", False,
     "a `git` DIRECTORY and a hyphenated `pre-push` FILENAME — the same false positive that "
     "blocked this hook's own development, one subcommand later"),
]:
    case(f"is_git_push({cmd!r}) is {want}", G.is_git_push(cmd) is want, why)

# --------------------------------------------------------------------- 2b. the range being pushed
#
# A gate on `git commit` asks git one question with one answer: `--cached`. A gate on `git push` has
# to work out what the other side is about to gain, and getting that wrong is silent in both
# directions — too narrow and it waves the push through, too wide and it charges suite time for
# files nobody touched. So this runs against a REAL repository rather than a mocked `git`.
REPO_A = TMP / "range-repo"


def git(*args, cwd=REPO_A):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True).stdout


REPO_A.mkdir()
git("init", "-b", "main", "-q")
git("config", "user.email", "selftest@example.com")
git("config", "user.name", "selftest")
(REPO_A / "README.md").write_text("one\n")
git("add", "-A"), git("commit", "-qm", "first")
first = git("rev-parse", "HEAD").strip()

(REPO_A / "plugins" / "sdlc-graph-viewer").mkdir(parents=True)
(REPO_A / "plugins" / "sdlc-graph-viewer" / "edges.md").write_text("two\n")
git("add", "-A"), git("commit", "-qm", "second")
second = git("rev-parse", "HEAD").strip()

case("git's four-field lines parse into (local, remote) shas",
     G.refs_from_stdin(f"refs/heads/main {second} refs/heads/main {first}\n"
                       "\ngarbage\n") == [(second, first)],
     str(G.refs_from_stdin(f"refs/heads/main {second} refs/heads/main {first}\n\ngarbage\n")))

case("an ordinary push diffs against the remote's tip, and nothing else",
     G.pushed_files(REPO_A, [(second, first)]) == ["plugins/sdlc-graph-viewer/edges.md"],
     str(G.pushed_files(REPO_A, [(second, first)])))

# NEGATIVE CONTROL: the zero sha. Git spells "the remote has never seen this ref" as forty zeros,
# and reading that literally as a revision makes every `git diff` fail — which fails OPEN, silently,
# on exactly the push a brand-new feature branch makes. There is no remote here at all, so the
# widest fallback is the one that has to answer.
new_branch = G.pushed_files(REPO_A, [(second, "0" * 40)])
case("a NEW branch (all-zero remote sha) still yields its files, not an empty range",
     new_branch == ["README.md", "plugins/sdlc-graph-viewer/edges.md"], str(new_branch))
case("...and it fires the gate rather than going quietly", G.sdlc_paths(new_branch) != [])

# NEGATIVE CONTROL: deleting a remote branch (`git push origin :old`) sends a zero LOCAL sha. There
# is no content in that push, so there is nothing to test — and treating the zeros as a revision
# would make the deletion of any branch an error instead of a no-op.
#
# The assertion is on the git calls, not just on the empty answer: a `git diff <base> 000…0` also
# returns nothing, because it FAILS. That would leave a deletion looking handled while actually
# being an error the gate swallowed, so the case requires that no diff was attempted at all.
calls, real_git = [], G._git
G._git = lambda root, *a: (calls.append(a), real_git(root, *a))[1]
deleted = G.pushed_files(REPO_A, [("0" * 40, first)])
G._git = real_git
case("deleting a remote ref pushes no content, so it asks git nothing",
     deleted == [] and not any("diff" in a for a in calls), f"{deleted}, git calls {calls}")
case("no refs at all is an empty range", G.pushed_files(REPO_A, []) == [])

# With a real remote, a new branch must scope to its OWN work — merge-base with the default branch —
# rather than replaying the whole history. Both answers fire the gate here; only one of them is
# honest about what is being pushed.
#
# `shared` exists so that the merge-base is the only thing that can give the right answer. With the
# branch's commit already on some remote ref, "everything no remote has" is empty and the widest
# fallback takes over, which is correct-but-useless: it reports every file in the repo. That is the
# shape a fallback chain hides — each link plausible, the preference order doing all the work.
BARE = TMP / "range-remote.git"
subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(BARE)], capture_output=True)
git("remote", "add", "origin", str(BARE))
git("push", "-q", "origin", f"{first}:refs/heads/main")
git("push", "-q", "origin", f"{second}:refs/heads/shared")
git("fetch", "-q", "origin")
git("remote", "set-head", "origin", "main")
git("checkout", "-qb", "feature", second)
base = G.push_base(REPO_A, second, "0" * 40)
case("a new branch bases on the merge-base with the remote's default branch",
     base == first, f"got {base}, want {first} (the tip main is already at)")
case("...so its range is its own commits only",
     G.pushed_files(REPO_A, [(second, "0" * 40)]) == ["plugins/sdlc-graph-viewer/edges.md"],
     str(G.pushed_files(REPO_A, [(second, "0" * 40)])))

# The agent path has no stdin to read — the hook payload owns it — so the range comes from the
# branch. It must agree with what git itself would have reported for the same push.
git("checkout", "-q", "main")
git("branch", "--set-upstream-to=origin/main", "-q", "main")
case("with no stdin, the range is HEAD against its upstream",
     G.refs_from_branch(REPO_A) == [(second, first)], str(G.refs_from_branch(REPO_A)))
git("checkout", "-q", "feature")
case("...and a branch with no upstream reads as a new branch, not as an error",
     G.refs_from_branch(REPO_A) == [(second, "0" * 40)], str(G.refs_from_branch(REPO_A)))

# --------------------------------------------------------------------- 3. the gate's own verdict
#
# Tier 1 is stubbed for the verdict cases, deliberately. The real suites are exercised above
# (routing) and below (a runner that does not exist), and once for real against the hook's own
# self-test — but a case that asks "is the whole repo green right now" is not a test of the gate,
# it is a test of whatever anybody else is halfway through editing. This self-test failed exactly
# that way on its first run, mid-restructure, while the gate was working perfectly.
saved_files, saved_tier1 = G.pushed_files, G.run_tier1
try:
    G.pushed_files = lambda root, refs: ["README.md", "CLAUDE.md"]
    out = G.gate(REPO, pretooluse=False, refs=[])
    case("a push with nothing sdlc in it -> exit 0, in silence", out == 0, f"exit {out}")
    # ...and the case the move to pre-push was FOR: the repo's own root files and docs, which must
    # never pay for a graph suite. Stubbing tier 1 out would prove nothing here, so it is left real — if this push were
    # in scope, the suites would run and this case would be seconds slower and, when the repo is
    # mid-edit, red.
    G.pushed_files = lambda root, refs: [OUTSIDE, "README.md"]
    out = G.gate(REPO, pretooluse=False, refs=[])
    case("a push of NON-sdlc plugins is silent and runs no suite", out == 0, f"exit {out}")

    case("tier 1 really runs, and a passing runner is silent",
         G.run_tier1([G.SELFTEST], REPO) == [], str(G.run_tier1([G.SELFTEST], REPO)))
    # NEGATIVE CONTROL: the routing table naming a runner that is not on disk. The PostToolUse
    # hook skips a missing runner in silence, which is right for a partial checkout and wrong for
    # a typo; a push gate must never count an absent suite as a pass.
    bogus = G.run_tier1(["plugins/sdlc-graph/skills/nope/run_all.py"], REPO)
    case("a runner that does not exist FAILS rather than being skipped",
         len(bogus) == 1 and "does not exist" in bogus[0][1], str(bogus))

    G.pushed_files = lambda root, refs: [STABLE]
    G.run_tier1 = lambda runners, root: []
    R.save_receipts({"version": 1, "receipts": fresh})
    ok, text = G.report(REPO, [STABLE])
    case("tier 1 green and every receipt fresh -> the gate passes", ok, text[:600])

    G.run_tier1 = lambda runners, root: [("some/run_all.py", "3 of 9 eval suites: spec/…")]
    ok, text = G.report(REPO, [STABLE])
    case("a RED deterministic suite blocks, whatever the receipts say",
         not ok and "some/run_all.py" in text, text[:300])

    # THE RULE THIS GATE NOW TURNS ON. A stale receipt is worth saying out loud and worth nobody's
    # push. These tests need a model and real minutes each, so blocking on them leaves two options
    # at the exact moment someone is trying to push — spend the money, or reach for the override —
    # and an override reached for routinely stops meaning anything, taking tier 1's credibility
    # with it. It also made the cheap signal hostage to the expensive one: a push whose
    # deterministic suites were perfectly green, blocked by evidence that went stale three PRs
    # earlier in a file nobody in that push had touched. That is the exact shape that got this
    # changed.
    G.run_tier1 = lambda runners, root: []
    R.save_receipts({"version": 1, "receipts": stale})
    ok, text = G.report(REPO, [STABLE])
    case("a stale receipt does NOT block — tier 2 is a report, not a gate", ok, text[:400])
    case("...and it is still named, with the on-demand command",
         "tier 2" in text and "no valid receipt" in text and "--drive" in text, text[:400])
    case("...and the report says out loud that driving is the human's call",
         "ON DEMAND" in text, text[:400])

    out = G.gate(REPO, pretooluse=True, refs=[])
    case("a push with stale receipts and green suites exits 0", out == 0, f"exit {out}")

    # The exit codes belong to tier 1 alone now, so the fixture that produces them has to be a red
    # SUITE. Driving them off a stale receipt would have quietly stopped testing the exit path the
    # day tier 2 was demoted.
    G.run_tier1 = lambda runners, root: [("some/run_all.py", "3 of 9 eval suites: spec/…")]
    out = G.gate(REPO, pretooluse=True, refs=[])
    case("the agent-facing path exits 2, so stderr reaches the model", out == 2, f"exit {out}")
    out = G.gate(REPO, pretooluse=False, refs=[])
    case("the git path exits 1", out == 1, f"exit {out}")

    # The git path is the one git actually calls, and it is reached through `main()` reading git's
    # ref lines off stdin. A gate whose stdin parsing is only ever exercised by a unit case is a
    # gate that can be perfect in pieces and dead as installed.
    # The stub answers only for the exact ref pair those lines encode, so a `main()` that dropped
    # stdin on the floor would see `README.md`, pass, and turn this case red.
    saved_stdin, saved_argv = sys.stdin, sys.argv
    G.pushed_files = lambda root, refs: [STABLE] if refs == [("a" * 40, "b" * 40)] else ["README.md"]
    sys.stdin = io.StringIO(f"refs/heads/x {'a' * 40} refs/heads/x {'b' * 40}\n")
    sys.argv, err, sys.stderr = ["gate"], sys.stderr, io.StringIO()
    out = G.main()
    sys.argv, sys.stderr, sys.stdin = saved_argv, err, saved_stdin
    G.pushed_files = lambda root, refs: [STABLE]
    case("the git path blocks on the range git actually handed it on stdin", out == 1, f"exit {out}")
    # Still red from the case above; the override case below needs something to wave through.

    # NEGATIVE CONTROL on the escape hatch itself. An override that passes in silence is worse
    # than no gate: the push then looks exactly like one that had evidence.
    os.environ["SDLC_SKIP_EVAL_GATE"] = "1"
    err, sys.stderr = sys.stderr, io.StringIO()
    out, spoken = G.gate(REPO, pretooluse=False, refs=[]), sys.stderr.getvalue()
    sys.stderr = err
    case("the override passes, and says out loud what it waved through",
         out == 0 and "some/run_all.py" in spoken and "SDLC_SKIP_EVAL_GATE" in spoken,
         f"exit {out}, said {spoken[:200]!r}")
    # The override an AGENT can actually reach. An inline `VAR=1 git push` assignment sets the
    # shell's environment, not this hook's — Claude Code spawns the hook itself — so following the
    # gate's own printed instructions did nothing, and the first commit of this gate was blocked by
    # it. The command line is the only place that override is visible from here.
    saved_stdin = sys.stdin
    for cmd, want_env in [("SDLC_SKIP_EVAL_GATE=1 git push", True),
                          ("git push", False)]:
        os.environ.pop("SDLC_SKIP_EVAL_GATE", None)
        sys.stdin = io.StringIO(json.dumps({"tool_input": {"command": cmd}, "cwd": str(REPO)}))
        err, sys.stderr = sys.stderr, io.StringIO()
        saved_argv, sys.argv = sys.argv, ["gate", "--pretooluse"]
        out = G.main()
        sys.argv, sys.stderr = saved_argv, err
        case(f"the inline override is honoured: {cmd!r} -> {'skipped' if want_env else 'blocked'}",
             (out == 0) is want_env, f"exit {out}")
    # ...and a Bash command that is not a push is not this hook's business at all, however red the
    # receipts are. `git commit` used to block here; after the move it must not.
    for cmd in ["git commit -m x", "git status"]:
        os.environ.pop("SDLC_SKIP_EVAL_GATE", None)
        sys.stdin = io.StringIO(json.dumps({"tool_input": {"command": cmd}, "cwd": str(REPO)}))
        saved_argv, sys.argv = sys.argv, ["gate", "--pretooluse"]
        out = G.main()
        sys.argv = saved_argv
        case(f"{cmd!r} is no longer gated — commits are cheap, pushes are not", out == 0,
             f"exit {out}")
    sys.stdin = saved_stdin
finally:
    os.environ.pop("SDLC_SKIP_EVAL_GATE", None)
    G.pushed_files, G.run_tier1 = saved_files, saved_tier1

# --------------------------------------------------------------------- 4. driving
# A synthetic scenario, so the controls never disturb the ten real ones or their artifacts.
SCEN = TMP / "selftest-drive-control.md"
SCEN.write_text("""# selftest drive control

**Claim:** a driven run writes a receipt only when its check passes.

```setup
{"state": {"run_id": "selftest-drive", "schema_version": 5, "node": "IMPLEMENT", "history": []}}
```

```brief
Never sent to a model. `SDLC_EVAL_CLAUDE_BIN` stands a stub in for `claude` in both controls.
```

```assert
len(history) == 1
```

```control
state["history"] = []
```
""", encoding="utf-8")

# This control drives a real harness, so it names the plugin that has one; a Test carries the
# plugin it belongs to, because the registry is per-plugin.
DRIVE_PLUGIN = R.Plugin("sdlc-graph")
drive_test = R.Test(DRIVE_PLUGIN, "scenario:selftest-drive-control", "scenario", "drive control",
                    SCEN, {"synthetic": "sha256:1111111111111111"},
                    drive_cmd=(DRIVE_PLUGIN.run_scenario, SCEN))

STUB_DEAD = TMP / "claude-does-nothing"
STUB_DEAD.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
STUB_DEAD.chmod(0o755)
STUB_LIVE = TMP / "claude-drives-it"
STUB_LIVE.write_text(
    "#!/usr/bin/env python3\n"
    "import json, pathlib\n"
    "p = pathlib.Path('docs/graph-runs/selftest-drive/state.json')\n"
    "s = json.loads(p.read_text())\n"
    "s['history'] = [{'from': 'IMPLEMENT', 'to': 'TEST'}]\n"
    "p.write_text(json.dumps(s))\n", encoding="utf-8")
STUB_LIVE.chmod(0o755)

try:
    R.save_receipts({"version": 1, "receipts": {}})

    R.CLAUDE_BIN = str(STUB_DEAD)
    ok, verdict, evidence = R.drive_one(drive_test)
    before = R.load_receipts()["receipts"]
    case("a driven run that FAILS its check writes NO receipt",
         not ok and drive_test.id not in before, f"ok={ok} receipts={list(before)}")
    case("...and the failing assertions are surfaced, not swallowed",
         "len(history) == 1" in verdict, verdict[:200])

    # ...and the same through `do_drive`, which is the path the failure message actually tells
    # people to run. `drive_one` refusing is worth nothing if its caller records anyway.
    R.save_receipts({"version": 1, "receipts": {}})
    out_buf, real_out = io.StringIO(), sys.stdout
    sys.stdout = out_buf
    os.environ["SDLC_EVAL_ALLOW_UNATTENDED"] = "1"   # these two test the DRIVE logic,
    rc = R.do_drive([drive_test], {}, limit=3, model=None)   # not the opt-in guard itself
    sys.stdout = real_out
    case("--drive over a failing test exits non-zero and records nothing",
         rc == 1 and R.load_receipts()["receipts"] == {},
         f"rc={rc} receipts={list(R.load_receipts()['receipts'])}")

    R.CLAUDE_BIN = str(STUB_LIVE)
    ok, verdict, evidence = R.drive_one(drive_test)
    case("a driven run that PASSES yields a receipt with real evidence",
         ok and evidence and evidence["files"] >= 1, f"ok={ok} verdict={verdict[:120]}")

    doc = R.load_receipts()
    R.write_receipt(doc, drive_test, verdict, "checked", evidence)
    R.save_receipts(doc)
    # By KEY, not by id: the file is per-plugin, so it does not repeat the plugin name in every
    # key. `all_receipts()` is what re-qualifies them for `problems_for`.
    written = R.load_receipts()["receipts"][drive_test.key]
    case("a receipt is stored under its unqualified key, and read back qualified",
         drive_test.key in R.load_receipts()["receipts"] and
         drive_test.id in R.all_receipts([drive_test]))
    case("the written receipt verifies against itself",
         R.problems_for([drive_test], R.all_receipts([drive_test])) == [] and
         written["provenance"] == "checked")

    # NEGATIVE CONTROL on the cap. Silent truncation would read as "covered everything".
    many = tests[:5]
    R.save_receipts({"version": 1, "receipts": {}})
    out_buf, real_out = io.StringIO(), sys.stdout
    sys.stdout = out_buf
    os.environ["SDLC_EVAL_ALLOW_UNATTENDED"] = "1"
    rc = R.do_drive(many, {}, limit=3, model=None)
    sys.stdout = real_out
    spoken = out_buf.getvalue()
    case("--drive refuses to exceed its cap, and names what it did not drive",
         rc == 1 and "--limit" in spoken and all(t.id in spoken for t in many if t.drivable),
         f"rc={rc} said {spoken[:300]!r}")
    # THE GUARD ON UNATTENDED EXECUTION. Driving means `claude -p --permission-mode
    # bypassPermissions` — a session with no approval prompt for any read, write or shell command
    # it makes. No gate calls it (the gate PRINTS the command and never runs it), but the script
    # must also refuse to do it merely because someone typed `--drive`. This is the case that goes
    # red the moment that guard is removed for convenience.
    os.environ.pop("SDLC_EVAL_ALLOW_UNATTENDED", None)
    drove, real_drive = [], R.drive_one
    R.drive_one = lambda *a, **k: (drove.append(a), (True, "", {}))[1]
    out_buf, real_out = io.StringIO(), sys.stdout
    sys.stdout = out_buf
    try:
        rc = R.do_drive(tests[:1], {}, limit=3, model=None)
    finally:
        sys.stdout, R.drive_one = real_out, real_drive
    case("--drive refuses to run unattended without an explicit opt-in", rc == 2, f"exit {rc}, want 2")
    case("...and starts no session while refusing", not drove, f"{len(drove)} started anyway")
    case("...and says what the opt-in grants, not just its name",
         "bypassPermissions" in out_buf.getvalue() and "SDLC_EVAL_ALLOW_UNATTENDED" in out_buf.getvalue(),
         out_buf.getvalue()[:200])

finally:
    shutil.rmtree(DRIVE_PLUGIN.evals / ".scratch" / SCEN.stem, ignore_errors=True)
    shutil.rmtree(TMP, ignore_errors=True)

bad = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} gate cases hold")
if bad:
    print("A gate that cannot fail is not a gate. Failing cases:")
    for n in bad:
        print(f"  {n}")
sys.exit(1 if bad else 0)
