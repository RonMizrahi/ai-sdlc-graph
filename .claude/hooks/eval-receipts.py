#!/usr/bin/env python3
"""Receipts for the eval tier a hook cannot run — and a driver that can run it.

There are two kinds of test in this repo and only one of them fits in a hook.

**Tier 1 — deterministic.** `run_all.py` in each graph plugin, plus this directory's own
`run-graph-evals.selftest.py`. Four seconds, no model. The PostToolUse hook already runs those on
every edit, and the pre-push gate runs them again against what is actually being pushed.

**Tier 2 — driven by a model.** `evals/runs/scenarios/*.md` (a real orchestrator against the
scripted `mock_milestone.py`), `evals/real/tests/*.md` (both sides real), and
`evals/behavioural/evals.json`. Minutes of wall time and real money each. Nothing automatic runs
them; this file answers a different question: **did they run, and is that run still valid?**

## Run on demand. Author always, drive deliberately.

Two rules govern this tier, and they are the reason it is worth having at all:

1. **Driving is a human decision, never a gate and never a hook.** The pre-push gate *reports* what
   is stale and moves on; only the deterministic suites can block a push. Blocking here left two
   options at the moment of pushing — spend minutes and money, or reach for the override — and an
   override reached for routinely stops meaning anything, taking the tier-1 gate's credibility with
   it.
2. **Adding a test still means adding the tier-2 case, even though you will not drive it.** Author
   the scenario / real test / behavioural case with the change that needs it. It shows as
   `NO RECEIPT`, which is the honest state: the case exists, is registered, is discoverable, and has
   not been paid for yet. That costs nothing and it is what makes the tier grow with the graph
   instead of ossifying at whatever was affordable the day it was built. A case nobody wrote can
   never be driven; a case written and not driven can be, any time, by name.

One plugin here carries the tier and a registry — `sdlc-graph`. Discovery is per plugin, and so is
the file, so a second one that grows an executing tier needs no change but its own directory.

## The staleness rule is the whole mechanism

A receipt records, per tier-2 test, when it was driven, what the verdict was, and a content hash of
every input the verdict depends on — the test file itself, and the spec the agent under test reads.
The gate recomputes those hashes. Equal → the receipt still describes reality. Different → the spec
moved under the test and the receipt is **stale**, which is exactly and only the moment re-driving
is worth minutes and money.

`inputs` is deliberately narrow: `SKILL.md`, `graph/*.md`, `subagents/*.md`, `agents/*.md` for the
tests that drive a real milestone agent, the test file, and the harness that executes the
assertions. **`nodes/**` is NOT in it** — a named gap, not an oversight. The eight node procedures
are spec the orchestrator obeys, so editing one can genuinely invalidate a run; including them would
also redden all ten scenarios on any node edit, and a gate that is red every day is a gate that gets
deleted. If that trade ever reads wrong, widen `spec_inputs()` — it is one function.

The harness IS in `inputs`, because a receipt claims "these assertions passed" and the assertions are
executed by that file. This repo has already shipped an assertion that was vacuously true for every
run (`inflight` read `cursor.milestones`, a schema-4 shape) — every receipt taken before that fix
was a lie about what had been checked.

## What a receipt is, and what it is not

A receipt is written by exactly two paths, and both are recorded in `provenance`:

- **`checked`** — `--drive` or `--record` ran the real `--check` and it exited 0. A failing check
  writes nothing.
- **`attested`** — a human ran a test with no machine-checkable artifact (the behavioural set is
  prompt/expected-output judged by a model) and signed a note. Weaker evidence, and it says so in
  the file rather than being laundered into the same word as a checked run.

Each receipt carries a `seal` over its own canonical form. **That is tamper-EVIDENT, not
tamper-proof** — the algorithm is right here and there is no secret to hold in a public repo. What
it buys is that the cheap forgery stops working: you cannot flip `never-run` to `passed`, or bump a
date, or paste one test's hashes onto another, without the gate saying so on the next commit.

## Usage

    python3 .claude/hooks/eval-receipts.py --list           # every tier-2 test and its receipt state
    python3 .claude/hooks/eval-receipts.py --verify         # exit 1 if anything is stale or missing
    python3 .claude/hooks/eval-receipts.py --drive          # DRIVE the stale ones with `claude -p`
    python3 .claude/hooks/eval-receipts.py --record <id>    # --check existing artifacts, record on pass
    python3 .claude/hooks/eval-receipts.py --attest <id> --note "..."   # for the un-drivable tier
    python3 .claude/hooks/eval-receipts.py --list --plugin sdlc-graph   # one plugin only

A test is addressed by `<plugin>/<kind>:<id>` — `sdlc-graph/scenario:01-happy-milestone` — and
by the bare `<kind>:<id>` when only one plugin has it.

`--drive` is opt-in per invocation and never the default: it spends minutes and money, and anything
that does that without being asked is something people turn off. It refuses to drive more than
`--limit` (default 3) tests without being told to, names what it left behind, and refuses outright
to run unattended without an explicit opt-in. `--verify` exits non-zero, but **nothing calls it in
anger** — the pre-push gate prints the same information and passes regardless.
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent

class Plugin:
    """One graph plugin's tier-2 layout, resolved once.

    The plugin is a parameter rather than a constant. It was once hardcoded to whichever plugin
    happened to have the executing tier first, and a registry that can only ever describe one
    plugin says nothing about any other plugin people install.
    """

    def __init__(self, name):
        self.name = name
        self.root = REPO / "plugins" / name
        self.skill = self.root / "skills" / name
        self.evals = self.skill / "evals"
        self.scenarios = self.evals / "runs" / "scenarios"
        self.real_tests = self.evals / "real" / "tests"
        self.behavioural = self.evals / "behavioural" / "evals.json"
        self.run_scenario = self.evals / "runs" / "run_scenario.py"
        self.run_real = self.evals / "real" / "run_real_eval.py"

    @property
    def receipts_path(self):
        # The env override collapses every plugin onto one file. That is what the self-test wants —
        # a synthetic registry in a temp dir — and it is why the override is read here rather than
        # bound once at import.
        override = os.environ.get("SDLC_EVAL_RECEIPTS")
        return pathlib.Path(override) if override else self.evals / "RECEIPTS.json"

    def exists(self):
        return self.evals.is_dir()

    def __repr__(self):
        return f"<Plugin {self.name}>"


GRAPH_PLUGINS = ("sdlc-graph",)


def plugins():
    """Every graph plugin with an eval tree, in a stable order. Absent ones are simply not there."""
    return [p for p in (Plugin(n) for n in GRAPH_PLUGINS) if p.exists()]


CLAUDE_BIN = os.environ.get("SDLC_EVAL_CLAUDE_BIN") or "claude"

DRIVE_TIMEOUT = int(os.environ.get("SDLC_EVAL_DRIVE_TIMEOUT") or 1800)
DEFAULT_LIMIT = 3

SEAL_DOMAIN = "sdlc-eval-receipt/v1\n"
DRIVE_CMD = "python3 .claude/hooks/eval-receipts.py --drive"


# --------------------------------------------------------------------------- hashing

def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()[:16]


# Which version of the inputs to hash. `None` = the working tree, which is what the GATE always
# wants: it is asking about the files being committed. `--from-rev` sets a git revision instead,
# and exists for one honest reason — a receipt taken for a run that already happened must record
# the spec that run actually READ. Recording today's working tree for this morning's run would
# claim the run had seen edits made after it finished, which is the exact overclaim this whole
# mechanism exists to catch. It caught it on day one: a concurrent restructure touched `nodes.md`
# and `edges.md` between the ten scenario drives and the receipts being written.
INPUT_REV = None


def hash_file(path):
    p = pathlib.Path(path)
    if INPUT_REV:
        rel = p.relative_to(REPO).as_posix()
        run = subprocess.run(["git", "-C", str(REPO), "show", f"{INPUT_REV}:{rel}"],
                             capture_output=True, cwd=str(REPO))
        return digest(run.stdout) if run.returncode == 0 else "MISSING"
    return digest(p.read_bytes()) if p.exists() else "MISSING"


def spec_inputs(plugin):
    """The spec surface an orchestrator under test reads. See the module docstring on `nodes/`."""
    out = {"SKILL.md": hash_file(plugin.skill / "SKILL.md")}
    for d in ("graph", "subagents"):
        for p in sorted((plugin.skill / d).glob("*.md")):
            out[f"{d}/{p.name}"] = hash_file(p)
    return out


def agent_inputs(plugin):
    """The milestone agent's own contract — an input only to the tests that spawn a real one."""
    return {f"agents/{p.name}": hash_file(p) for p in sorted((plugin.root / "agents").glob("*.md"))}


# --------------------------------------------------------------------------- discovery

class Test:
    """One tier-2 test, discovered from disk rather than from a hand-kept list.

    Hand-kept lists are how a new scenario ends up with no receipt and nothing notices. Discovery
    means adding `11-*.md` makes the gate red until someone drives it, which is the correct default
    for a test that has never run.
    """

    def __init__(self, plugin, key, kind, claim, path, inputs, drive_cmd=None):
        self.plugin, self.key = plugin, key
        self.kind, self.claim, self.path = kind, claim, path
        self.inputs, self.drive_cmd = inputs, drive_cmd

    @property
    def id(self):
        """How a human addresses it: `sdlc-graph/scenario:01-happy-milestone`.

        The RECEIPT key is `self.key` — `scenario:01-happy-milestone`, unqualified — because each
        plugin owns its own `RECEIPTS.json` and a file that repeated its own plugin's name in every
        one of its keys would be saying it twice. Qualifying only the display id is also what let
        the fork's twenty-nine existing receipts survive this becoming multi-plugin.
        """
        return f"{self.plugin.name}/{self.key}"

    @property
    def drivable(self):
        return self.drive_cmd is not None


def _claim(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("**Claim:**"):
            return line.split("**Claim:**", 1)[1].strip()
    return ""


def discover_in(plugin):
    tests = []
    spec = spec_inputs(plugin)
    agents = agent_inputs(plugin)

    harness = {"evals/runs/run_scenario.py": hash_file(plugin.run_scenario),
               "evals/runs/mock_milestone.py": hash_file(plugin.evals / "runs" / "mock_milestone.py")}
    for p in sorted(plugin.scenarios.glob("*.md")):
        if p.name == "README.md":
            continue
        tests.append(Test(plugin, f"scenario:{p.stem}", "scenario", _claim(p), p,
                          {**spec, **harness, f"scenarios/{p.name}": hash_file(p)},
                          drive_cmd=(plugin.run_scenario, p)))

    harness = {"evals/real/run_real_eval.py": hash_file(plugin.run_real),
               "evals/real/SYSTEM.md": hash_file(plugin.evals / "real" / "SYSTEM.md")}
    for p in sorted(plugin.real_tests.glob("*.md")):
        if p.name == "README.md":
            continue
        tests.append(Test(plugin, f"real:{p.stem}", "real", _claim(p), p,
                          {**spec, **agents, **harness, f"real/{p.name}": hash_file(p)},
                          drive_cmd=(plugin.run_real, p)))

    # Per CASE, not per file: `evals.json` holds eighteen independent cases, and hashing the whole
    # file would mark all eighteen stale every time one of them is reworded.
    if plugin.behavioural.exists():
        cases = json.loads(plugin.behavioural.read_text(encoding="utf-8")).get("evals") or []
        for case in cases:
            canon = json.dumps(case, sort_keys=True, separators=(",", ":")).encode()
            tests.append(Test(plugin, f"behavioural:{case['id']}", "behavioural",
                              case.get("name", ""), plugin.behavioural,
                              {**spec, **agents, "case": digest(canon)}))
    return tests


def discover(only=None):
    """Every tier-2 test across every graph plugin, or just the named one."""
    out = []
    for p in plugins():
        if only and p.name != only:
            continue
        out.extend(discover_in(p))
    return out


# --------------------------------------------------------------------------- the file

NEW_DOC = {
    "version": 1,
    "$comment": [
        "Evidence that the eval tier a hook CANNOT run has actually been run.",
        "Written only by .claude/hooks/eval-receipts.py, and only by a --check that exited 0 "
        "(provenance `checked`) or a human signing a note for the tier that has no check at all "
        "(provenance `attested`). Do not edit by hand: every receipt is sealed over its own "
        "fields, and the pre-push gate re-computes the seal.",
        "`inputs` is a content hash of everything the verdict depends on. The gate re-computes "
        "those against the working tree; any difference means the spec moved under the test and "
        "the receipt is STALE — re-drive with `python3 .claude/hooks/eval-receipts.py --drive`.",
    ],
    "receipts": {},
}


def load_receipts(plugin=None):
    """One plugin's registry document. With no plugin, the first one that exists.

    The no-argument form is what the self-test uses: `SDLC_EVAL_RECEIPTS` points every plugin at
    one temp file, so "the first" and "the only" are the same document.
    """
    plugin = plugin or (plugins() or [Plugin(GRAPH_PLUGINS[0])])[0]
    path = plugin.receipts_path
    if not path.exists():
        return json.loads(json.dumps(NEW_DOC))
    return json.loads(path.read_text(encoding="utf-8"))


def save_receipts(doc, plugin=None):
    plugin = plugin or (plugins() or [Plugin(GRAPH_PLUGINS[0])])[0]
    path = plugin.receipts_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def all_receipts(tests):
    """`{test.id: receipt}` across every plugin these tests belong to.

    Keyed by the QUALIFIED id so `problems_for` stays a pure function of two plain dicts, while
    each plugin's file keeps its own unqualified keys.
    """
    out, seen = {}, {}
    for t in tests:
        if t.plugin.name not in seen:
            seen[t.plugin.name] = (load_receipts(t.plugin).get("receipts") or {})
        body = seen[t.plugin.name].get(t.key)
        if body is not None:
            out[t.id] = body
    return out


def seal_of(body):
    canon = json.dumps({k: v for k, v in body.items() if k != "seal"},
                       sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256((SEAL_DOMAIN + canon).encode("utf-8")).hexdigest()[:32]


def rel(path):
    """Repo-relative when it can be — a receipt naming an absolute path is not portable."""
    path = pathlib.Path(path)
    return str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)


def write_receipt(doc, test, verdict, provenance, evidence=None, note=None):
    body = {
        "kind": test.kind,
        "test": rel(test.path),
        "claim": test.claim,
        "status": "passed",
        "provenance": provenance,
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": verdict,
        "inputs": test.inputs,
    }
    if INPUT_REV:
        body["inputs_at"] = INPUT_REV
    if evidence:
        body["evidence"] = evidence
    if note:
        body["note"] = note
    body["seal"] = seal_of(body)
    doc.setdefault("receipts", {})[test.key] = body
    return body


# --------------------------------------------------------------------------- verification

def problems_for(tests, receipts):
    """[(test_id, reason, detail)] — pure over its arguments, so the self-test can plant any state.

    Every branch here is a way a green receipt can be worthless, and each is reported separately:
    a gate that answers "something is wrong" tells you nothing about which minutes to spend.
    """
    out = []
    for t in tests:
        r = receipts.get(t.id)
        if r is None:
            out.append((t.id, "no receipt", "never recorded — this test has no evidence at all"))
            continue
        if r.get("status") != "passed":
            out.append((t.id, r.get("status") or "unknown status",
                        r.get("note") or "recorded as not passing"))
            continue
        if r.get("seal") != seal_of(r):
            out.append((t.id, "seal broken",
                        "the receipt's fields do not match its seal — it was edited by hand, "
                        "not written by a check that ran"))
            continue
        was, now = r.get("inputs") or {}, t.inputs
        changed = sorted(k for k in set(was) | set(now) if was.get(k) != now.get(k))
        if changed:
            out.append((t.id, "stale", "inputs changed since it was driven: " + ", ".join(changed)))
    return out


# --------------------------------------------------------------------------- driving

def _setup(test):
    """Run the harness's `--setup` and return (scratch_root, brief)."""
    run = subprocess.run([sys.executable, str(test.drive_cmd[0]), str(test.drive_cmd[1]), "--setup"],
                         capture_output=True, text=True, cwd=str(test.plugin.skill))
    if run.returncode != 0:
        raise RuntimeError(f"--setup failed: {(run.stdout + run.stderr).strip()[:400]}")
    lines = run.stdout.splitlines()
    root = pathlib.Path(lines[0].split("scratch:", 1)[1].strip())
    body = [l for l in lines[1:] if set(l.strip()) != {"="}]
    return root, "\n".join(body).strip()


def _check(test):
    return subprocess.run([sys.executable, str(test.drive_cmd[0]), str(test.drive_cmd[1]), "--check"],
                          capture_output=True, text=True, cwd=str(test.plugin.skill))


def _evidence(root):
    """A digest over the artifacts the check just read — the run's own leavings.

    The scratch tree is gitignored and will be wiped by the next `--setup`, so this is the only
    durable trace that a receipt was taken against a real run rather than typed.
    """
    files, h = 0, hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".git/" not in str(p) and p.suffix in (".json", ".jsonl", ".txt"):
            h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes())
            files += 1
    return {"artifacts_sha256": "sha256:" + h.hexdigest()[:16], "files": files,
            "scratch": str(root.relative_to(REPO)) if root.is_relative_to(REPO) else str(root)}


def drive_one(test, model=None):
    """setup → hand the brief to a headless `claude -p` → check. Returns (ok, verdict, evidence).

    The briefs are self-contained and name every path absolutely — that is why they can be handed
    to a fresh session with no other context. The session runs with `cwd` inside the scratch tree.
    """
    root, brief = _setup(test)
    cmd = [CLAUDE_BIN, "-p", brief, "--output-format", "json",
           "--permission-mode", "bypassPermissions", "--add-dir", str(test.plugin.skill)]
    if model:
        cmd += ["--model", model]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=DRIVE_TIMEOUT, cwd=str(root))
    except subprocess.TimeoutExpired:
        return False, f"the driven session did not finish inside {DRIVE_TIMEOUT}s", None
    except FileNotFoundError:
        return False, f"`{CLAUDE_BIN}` is not on PATH — nothing drove this test", None

    run = _check(test)
    tail = (run.stdout + run.stderr).strip().splitlines()
    if run.returncode != 0:
        # A failed driven run writes NO receipt. The receipt means "this passed against these
        # inputs" and nothing weaker; a receipt for a red run is worse than no receipt, because
        # the gate would go green on it.
        fails = [l for l in tail if l.startswith("FAIL")] or tail[-6:]
        return False, "check failed:\n      " + "\n      ".join(fails[:8]), None
    return True, (tail[-1] if tail else "check passed"), _evidence(root)


UNATTENDED_ENV = "SDLC_EVAL_ALLOW_UNATTENDED"


def _unattended_allowed():
    """`--drive` spawns headless model sessions with NO per-action approval. Explicit opt-in only.

    Driving a scenario means handing its brief to `claude -p --permission-mode bypassPermissions`:
    a session that can read, write and run shell commands with nothing asking first. That is what
    makes unattended driving possible, and it is also a real escalation — so it may never happen as
    a side effect of anything.

    Two things keep it contained, and both matter:

    - **No gate ever calls this.** `pre-push-eval-gate.py` PRINTS the `--drive` command and never
      runs it. A push cannot spawn an agent, on either the git path or the agent path.
    - **A human sets this variable, per shell, deliberately.** Nothing in the repo sets it, no
      script exports it, and the message below says exactly what is being granted rather than
      naming a flag and hoping.

    The scenario briefs are generated from files in this repo, so this is not a defence against
    hostile input — it is a defence against *unattended* execution happening without someone
    deciding it should.
    """
    if os.environ.get(UNATTENDED_ENV) == "1":
        return True
    print(f"--drive is refusing to run.\n\n"
          f"It hands each stale test's brief to a headless `claude -p` session started with\n"
          f"`--permission-mode bypassPermissions` — no approval prompt for any read, write or\n"
          f"shell command it makes. That is required for an unattended run and it is not something\n"
          f"to enable by accident, so it is opt-in per shell:\n\n"
          f"    {UNATTENDED_ENV}=1 {DRIVE_CMD}\n\n"
          f"Everything else works without it: this script reports staleness, and\n"
          f"`run_scenario.py <file> --setup` prints the brief for you to drive yourself.")
    return False


def do_drive(tests, receipts, limit, model, only=None):
    if not _unattended_allowed():
        return 2
    stale = [t for t in tests if t.id in {p[0] for p in problems_for(tests, receipts)}]
    if only:
        stale = [t for t in stale if t.id in only]
    drivable = [t for t in stale if t.drivable]
    skipped = [t for t in stale if not t.drivable]

    if len(drivable) > limit:
        print(f"{len(drivable)} tests are stale and --limit is {limit}. Driving all of them is "
              f"{len(drivable)} model sessions of 2-7 minutes each.\n"
              f"Name them, or raise the cap explicitly:\n"
              f"  {DRIVE_CMD} --limit {len(drivable)}\n"
              f"  {DRIVE_CMD} --only {' '.join(t.id for t in drivable[:3])}\n")
        for t in drivable:
            print(f"  stale  {t.id}")
        return 1

    docs = {}
    failed = []
    for t in drivable:
        print(f"── driving {t.id} ...", flush=True)
        ok, verdict, evidence = drive_one(t, model)
        if ok:
            doc = docs.setdefault(t.plugin.name, load_receipts(t.plugin))
            write_receipt(doc, t, verdict, "checked", evidence)
            save_receipts(doc, t.plugin)
            print(f"ok    {t.id} — receipt written\n")
        else:
            failed.append((t.id, verdict))
            print(f"FAIL  {t.id} — NO receipt written\n      {verdict}\n")

    if skipped:
        print("Not driven — no harness can execute these; they are judged by a model and recorded "
              "by hand:")
        for t in skipped:
            print(f"  {t.id}  ->  --attest {t.id} --note \"...\"")
    return 1 if (failed or skipped) else 0


# --------------------------------------------------------------------------- CLI

def do_list(tests, receipts):
    """Grouped by plugin, because "which of these is stale" is always asked about one of them."""
    seen = None
    for t in tests:
        if t.plugin.name != seen:
            seen = t.plugin.name
            print(f"\n{seen}")
        r = receipts.get(t.id)
        state = "NO RECEIPT"
        if r:
            bad = [p for p in problems_for([t], receipts)]
            state = bad[0][1].upper() if bad else f"{r['provenance']} {r['run_at'][:10]}"
        print(f"  {state:22} {t.key:46} {t.claim[:58]}")
    print()
    return 0


def do_verify(tests, receipts, quiet=False):
    problems = problems_for(tests, receipts)
    if not problems:
        if not quiet:
            print(f"ok    {len(tests)}/{len(tests)} tier-2 tests have a valid receipt")
        return 0
    print(f"{len(problems)} of {len(tests)} tier-2 tests have no valid evidence:\n")
    for tid, reason, detail in problems:
        print(f"  {reason.upper():12} {tid}\n               {detail}")
    print(f"\nRe-drive them:\n  {DRIVE_CMD}                 # the stale ones, capped at "
          f"{DEFAULT_LIMIT}\n  {DRIVE_CMD} --only <id>     # one at a time")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--drive", action="store_true", help="drive stale tests with `claude -p`")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--only", nargs="*", help="restrict --drive to these test ids")
    ap.add_argument("--model", help="model for the driven session")
    ap.add_argument("--record", metavar="ID",
                    help="run the real --check against artifacts already on disk; record on pass")
    ap.add_argument("--attest", metavar="ID",
                    help="record a test that has no machine-checkable artifact (needs --note)")
    ap.add_argument("--never-run", metavar="ID", help="record a test as deliberately not yet run")
    ap.add_argument("--plugin", choices=GRAPH_PLUGINS,
                    help="restrict to one graph plugin (default: all of them)")
    ap.add_argument("--note")
    ap.add_argument("--from-rev", metavar="REV",
                    help="hash the inputs as they were at this git revision, not as they are now — "
                         "for a receipt taken after the fact, so it records the spec the run READ")
    args = ap.parse_args()

    if args.from_rev:
        global INPUT_REV
        # The resolved sha, never the name: `HEAD` in a receipt means nothing a week later.
        INPUT_REV = subprocess.run(["git", "-C", str(REPO), "rev-parse", args.from_rev],
                                   capture_output=True, text=True).stdout.strip() or args.from_rev

    tests = discover(args.plugin)
    # Addressable by the qualified id, and — when it is unambiguous — by the bare key, so
    # `--only scenario:01-happy-milestone` keeps working the way it always has.
    by_id = {t.id: t for t in tests}
    bare = {}
    for t in tests:
        bare.setdefault(t.key, []).append(t)
    for key, group in bare.items():
        if len(group) == 1:
            by_id.setdefault(key, group[0])
    receipts = all_receipts(tests)

    if args.record or args.attest or args.never_run:
        tid = args.record or args.attest or args.never_run
        if tid not in by_id:
            dupes = [x.id for x in tests if x.key == tid]
            hint = ("that id exists in more than one plugin — qualify it: "
                    + ", ".join(dupes)) if dupes else "--list shows them all."
            print(f"unknown test `{tid}`. {hint}", file=sys.stderr)
            return 2
        t = by_id[tid]
        doc = load_receipts(t.plugin)
        if args.record:
            if not t.drivable:
                print(f"{tid} has no harness to --check; use --attest", file=sys.stderr)
                return 2
            run = _check(t)
            if run.returncode != 0:
                print(f"the check FAILED — no receipt written\n{(run.stdout + run.stderr).strip()}",
                      file=sys.stderr)
                return 1
            root = _scratch_of(t)
            tail = run.stdout.strip().splitlines()
            write_receipt(doc, t, tail[-1] if tail else "check passed", "checked",
                          _evidence(root) if root and root.exists() else None, args.note)
        elif args.attest:
            if not args.note:
                print("--attest needs --note: who ran it, and against what", file=sys.stderr)
                return 2
            write_receipt(doc, t, "attested by a human — no machine-checkable artifact", "attested",
                          None, args.note)
        else:
            body = {"kind": t.kind, "test": rel(t.path), "claim": t.claim,
                    "status": "never-run", "provenance": "none",
                    "note": args.note or "never driven"}
            doc.setdefault("receipts", {})[t.id] = body
        save_receipts(doc, t.plugin)
        print(f"recorded {t.id}")
        return 0

    if args.drive:
        return do_drive(tests, receipts, args.limit, args.model, set(args.only or []) or None)
    if args.list:
        return do_list(tests, receipts)
    return do_verify(tests, receipts, args.quiet)


def _scratch_of(test):
    """Where the harness put this test's artifacts. Both harnesses key scratch on the file stem."""
    ev = test.plugin.evals
    base = ev / ".scratch" if test.kind == "scenario" else ev / "real" / ".scratch"
    return base / test.path.stem


if __name__ == "__main__":
    sys.exit(main())
