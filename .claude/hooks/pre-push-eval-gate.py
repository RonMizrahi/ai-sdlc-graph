#!/usr/bin/env python3
"""Nothing leaves this machine against an sdlc plugin with a red deterministic suite.

It gates **pushes**, not commits, and that is a deliberate move. Commits are cheap, frequent and
local — a gate on them charges tier-1 suite time against every `wip` save and gets uninstalled
inside a week. A push is the moment work leaves the machine and becomes something someone else can
read as tested, which is the moment the evidence has to be real.

Two ways in, one verdict:

- **`.githooks/pre-push`** — a human typing `git push`. Bootstrap once:
  `git config core.hooksPath .githooks`. Git feeds it `<local ref> <local sha> <remote ref>
  <remote sha>` lines on stdin, one per ref being pushed, and those lines are the whole range.
- **A `PreToolUse` hook on Bash** — an agent typing `git push`, which never touches a git hook.
  It self-filters to `git push` commands the same way `block-push-to-main.py` does, because a hook
  matcher matches the tool, not the command. There is no stdin to read on that path (stdin carries
  the hook payload), so the range comes from the current branch and its upstream instead.

Both compute the files actually being pushed and exit 0 in silence unless one of them lives under a
directory whose name contains `sdlc`. Pushing `docs/` or the repo's own root files is silent and
instant; `sdlc-graph`, `sdlc-graph-viewer` and `sdlc-graph-engineering-install` are all caught, by
the one rule, with no list of plugin names to keep up to date.

The match is on path **segments**, and on directory segments only. `plugins/sdlc-graph-viewer/x.md`
counts; a repo-root file called `sdlc-graph-notes.md` does not, and neither does
`docs/sdlc-summary.md` — a filename mentioning the letters is not a change to a plugin.

## What it checks — and what it only reports

**Tier 1 — the deterministic suites, and the ONLY thing that can block.** Run for real, right now,
routed by the same `runners_for()` the PostToolUse hook uses. One routing table, so the gate cannot
drift from the thing that has been running these all along. Plus that hook's own self-test. They
cost about four seconds, they need no model, and a red one is a real defect in what is being pushed.

Two of the three plugins here carry suites. `sdlc-graph-engineering-install` carries none — it
ships a method for building graphs rather than a graph — so a push of it alone runs the routing
self-test and nothing else. That self-test runs for **any** sdlc push, matched or not: a plugin the
routing table has stopped naming is exactly the case where nothing else would speak up.

**Tier 2 — the executing tests, REPORTED and never blocking.** `eval-receipts.py` knows, per
scenario / real-agent test / behavioural case, whether it has a receipt whose recorded input hashes
still match the files on disk. Stale means the spec moved under a test that was passing against the
old spec. That is worth knowing, and it is printed on every sdlc push — passing or failing.

**This repo has no receipts, and that is honest rather than broken.** The registry stayed with the
development fork, so `--list` reports every executing test as having none. Authoring the case is
mandatory; driving it is a decision someone makes on purpose, with the minutes in front of them.

It is not a gate, and the reason is worth keeping: these tests need a model and real minutes each,
so the only ways past a red tier 2 are to spend that money at the exact moment someone is trying to
push, or to reach for the override. An override people reach for routinely stops meaning anything,
and it takes the tier-1 gate's credibility with it. It also made the cheap signal hostage to the
expensive one — a push whose deterministic suites were perfectly green, blocked by evidence that had
gone stale three PRs earlier in a file nobody in that push had touched. **The executing tier is run
on demand, by a human who decided to spend the minutes**, with `--list` in front of them.

## Failing, and the escape hatch

The agent-facing path exits **2**, which feeds stderr back to the model. The git path exits 1 with
the same text. Only a red tier 1 produces either.

`SDLC_SKIP_EVAL_GATE=1 git push ...` overrides — and prints every test it just waved through. A
gate with no override gets deleted; an override that is silent is worse than no gate, because the
push then looks exactly like one that passed. (The variable keeps its name across the move from
commit to push: it never said `COMMIT`, and anyone's muscle memory still works.)
"""
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
SELFTEST = ".claude/hooks/run-graph-evals.selftest.py"
DRIVE_CMD = "python3 .claude/hooks/eval-receipts.py --drive"

# `git diff` against this is "every file in the ref", and it is the last resort when there is no
# remote to compare with at all.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


evalhook = _load("run_graph_evals", "run-graph-evals.py")
receipts = _load("eval_receipts", "eval-receipts.py")


# --------------------------------------------------------------------------- what is being pushed

def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def _rev(root, spec):
    """A resolved sha, or "" — never the caller's own text back.

    `git rev-parse <unresolvable>` exits 128 *and prints the argument it could not resolve to
    stdout*, so the naive read hands back `<sha>^` for a root commit or the literal `@{upstream}`
    for a branch with no upstream. Both then flow into `git diff` as a revision, which fails, which
    empties the range — a gate that goes silent on precisely the first push of a new branch.
    `--verify -q` prints a sha or nothing at all.
    """
    return _git(root, "rev-parse", "--verify", "-q", spec).stdout.strip()


def _is_zero(sha):
    """Git spells "this ref does not exist on the other side" as an all-zero sha."""
    return not sha or set(sha) == {"0"}


def refs_from_stdin(text):
    """Git's pre-push lines: `<local ref> <local sha> <remote ref> <remote sha>`, one per ref.

    Returns [(local_sha, remote_sha)]. Anything that is not four fields is not a ref line.
    """
    out = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 4:
            out.append((fields[1], fields[3]))
    return out


def refs_from_branch(root):
    """The agent path's substitute for stdin: this branch against its upstream.

    An agent pushes through Bash, so the hook payload owns stdin and git's ref lines do not exist
    here. `@{upstream}` is the same question git would have answered — where the remote currently
    is — and when there is no upstream yet the zero sha routes into the new-branch case below,
    exactly as git would have reported it.
    """
    local = _rev(root, "HEAD")
    if not local:
        return []
    return [(local, _rev(root, "@{upstream}") or "0" * 40)]


def _remote_default_refs(root):
    """Candidate bases for a branch the remote has never seen, best guess first."""
    head = _git(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD").stdout.strip()
    cands = [head[len("refs/remotes/"):]] if head.startswith("refs/remotes/") else []
    return cands + ["origin/main", "origin/master"]


def push_base(root, local_sha, remote_sha):
    """What to diff `local_sha` against, for one ref being pushed.

    Normal case: the remote's current tip — precisely the commits the other side is about to gain.
    **New branch** (`remote_sha` all zeros): the merge base with the remote's default branch, so the
    range is this branch's own work rather than the whole project. With no remote at all, everything
    no remote already has; and failing even that, the ref's entire history.

    The fallbacks widen rather than narrow on purpose. A base that guesses too far back costs a few
    seconds of suite time; a base that guesses too far forward makes the gate silent on exactly the
    push it exists to catch.
    """
    if not _is_zero(remote_sha):
        return remote_sha
    for cand in _remote_default_refs(root):
        base = _git(root, "merge-base", cand, local_sha).stdout.strip()
        if base:
            return base
    unpushed = _git(root, "rev-list", local_sha, "--not", "--remotes").stdout.split()
    if unpushed:
        parent = _rev(root, f"{unpushed[-1]}^")   # empty at a root commit — fall through
        if parent:
            return parent
    return EMPTY_TREE


def pushed_files(root, refs):
    """Every path in the push, across all refs. Sorted and de-duplicated."""
    out = set()
    for local_sha, remote_sha in refs:
        if _is_zero(local_sha):
            continue  # deleting a remote ref pushes no content, so there is nothing to test
        base = push_base(root, local_sha, remote_sha)
        run = _git(root, "diff", "--name-only", base, local_sha)
        out.update(l.strip() for l in run.stdout.splitlines() if l.strip())
    return sorted(out)


def sdlc_paths(paths):
    """Paths that live under a DIRECTORY whose name contains `sdlc`.

    Segment-matched, and directory segments only. `plugins/sdlc-graph-viewer/x.md` counts and so
    does `plugins/sdlc-graph-engineering-install/…`, with no list of plugin names to keep current.
    A repo-root file called `sdlc-graph-notes.md` does not, and neither does `docs/sdlc-plan.md`:
    naming a thing is not changing it, and a gate that fires on prose is a gate that gets removed.
    """
    return [p for p in paths
            if any("sdlc" in seg for seg in pathlib.PurePosixPath(p).parts[:-1])]


# --------------------------------------------------------------------------- the verdict

def tier1_runners(paths):
    """Every deterministic runner that can see these pushed paths, plus the hook's own self-test."""
    found = []
    for p in paths:
        for runner in evalhook.runners_for(p):
            if runner not in found:
                found.append(runner)
    # `if paths`, not `if found`: a push that carries an sdlc directory the routing table names
    # nothing for would otherwise run NOTHING — not even this — and exit 0 in silence, which is
    # indistinguishable from a push that was checked. The self-test is the one thing that can tell
    # a deliberate absence (the method plugin has no suite) from a table that stopped naming a
    # plugin that does.
    if paths:
        found.append(SELFTEST)
    return found


def wants_receipts(paths):
    """Should the tier-2 REPORT be printed for this push? It never decides the exit code.

    Only a plugin with an executing tier is reported on — `receipts.GRAPH_PLUGINS` is that list,
    and it is the same list `eval-receipts.py` drives from, so the report cannot describe a plugin
    the driver cannot run.
    """
    return any(pathlib.PurePosixPath(p).parts[:2] == ("plugins", n)
               for p in paths for n in receipts.GRAPH_PLUGINS)


def run_tier1(runners, root):
    failures = []
    for runner in runners:
        script = root / runner
        if not script.exists():
            failures.append((runner, "the runner named in the routing table does not exist"))
            continue
        argv = [sys.executable, str(script)] + ([] if runner == SELFTEST else ["--quiet"])
        run = subprocess.run(argv, capture_output=True, text=True, cwd=str(root), timeout=300)
        if run.returncode != 0:
            failures.append((runner, (run.stdout + run.stderr).strip()))
    return failures


def tier2_notice(paths):
    """The advisory block, or "". Computed for information; it never decides anything."""
    if not wants_receipts(paths):
        return ""
    tests = receipts.discover()
    problems = receipts.problems_for(tests, receipts.all_receipts(tests))
    if not problems:
        return (f"\ntier 2 — {len(tests)}/{len(tests)} executing tests have a valid receipt.\n")
    by_reason = {}
    for tid, reason, _detail in problems:
        by_reason.setdefault(reason, []).append(tid)
    summary = " · ".join(f"{len(v)} {k}" for k, v in sorted(by_reason.items()))
    return (f"\ntier 2 — FYI, not a gate: {len(problems)} of {len(tests)} executing tests have no "
            f"valid receipt ({summary}).\n"
            f"  These need a model and real minutes; they are run ON DEMAND, by you, never by a "
            f"hook and never by this push.\n"
            f"  python3 .claude/hooks/eval-receipts.py --list        # which ones, and why\n"
            f"  {DRIVE_CMD} --only <id>                              # drive one, deliberately\n")


def report(root, paths):
    """(ok, text). `ok` is TIER 1 ONLY — the deterministic suites are the whole gate.

    Tier 2 was a blocking condition for one release and it was the wrong shape. Those tests need a
    model and real minutes each, so the only way past a red tier 2 is either to spend that money at
    the exact moment someone is trying to push, or to reach for the override — and an override
    people reach for routinely stops meaning anything, taking the tier-1 gate's credibility with
    it. Worse, it made the *cheap* signal hostage to the expensive one: a push whose deterministic
    suites were perfectly green was blocked by evidence that had gone stale three PRs earlier, in a
    file nobody in that push had touched.

    So tier 2 reports and never blocks. The report is the useful half — it says which executing
    tests the spec has moved under, so driving them is a decision someone makes on purpose, with
    the list in front of them, rather than a toll booth.
    """
    lines = []
    t1 = run_tier1(tier1_runners(paths), root)
    for runner, out in t1:
        lines.append(f"  DETERMINISTIC  {runner}\n{out}")

    notice = tier2_notice(paths)
    if not lines:
        return True, notice

    head = (f"{len(t1)} deterministic suite(s) failing. This push carries an sdlc plugin, and the "
            f"deterministic suites have to be green.\n")
    tail = (f"\nRun them yourself to iterate:\n"
            f"  python3 <plugin>/skills/<skill>/evals/run_all.py\n"
            f"\nOverride (and say so out loud when you do):\n"
            f"  SDLC_SKIP_EVAL_GATE=1 git push ...")
    return False, head + "\n".join(lines) + tail + notice


def gate(root, pretooluse, refs=None):
    paths = sdlc_paths(pushed_files(root, refs if refs is not None else refs_from_branch(root)))
    if not paths:
        return 0

    ok, text = report(root, paths)
    if os.environ.get("SDLC_SKIP_EVAL_GATE") == "1":
        print("SDLC_SKIP_EVAL_GATE=1 — the eval gate was overridden for this push.",
              file=sys.stderr)
        print(text or "Nothing was wrong; the override was not needed.", file=sys.stderr)
        return 0
    if ok:
        # The tier-2 notice still prints on a passing push — that is the whole point of demoting it
        # from a gate to a report. Exit 0 regardless: stderr on a zero exit is information, and a
        # push that is allowed must not look like one that was not.
        if text:
            print(text, file=sys.stderr)
        return 0
    print(text, file=sys.stderr)
    return 2 if pretooluse else 1


# --------------------------------------------------------------------------- the agent path

GIT_GLOBAL_OPTS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path")


def is_git_push(cmd):
    """Does this shell command actually run `git push`?

    Tokenised, not grepped. The obvious regex — `\\bgit\\b[^&|;]*\\bpush\\b` — matches a command
    line that runs no git at all: this repo lives under `~/git/`, and the same class of false
    positive already blocked this hook's own development back when it keyed on `commit` and the
    script was called `pre-commit-eval-gate.py`. A gate that fires on commands it has no business
    seeing is a gate that gets turned off within the hour.
    """
    for seg in re.split(r"&&|\|\||;|\|", cmd):
        toks = seg.split()
        for i, tok in enumerate(toks):
            if tok != "git" and not tok.endswith("/git"):
                continue
            args, j = toks[i + 1:], 0
            while j < len(args):
                if args[j] in GIT_GLOBAL_OPTS_WITH_VALUE:
                    j += 2
                elif args[j].startswith("-"):
                    j += 1
                else:
                    break
            if j < len(args) and args[j] == "push":
                return True
    return False


def main():
    if "--pretooluse" not in sys.argv:
        # The git path. Git hands the hook `<local ref> <local sha> <remote ref> <remote sha>` on
        # stdin, one line per ref; no lines means nothing is being pushed.
        return gate(REPO, pretooluse=False, refs=refs_from_stdin(sys.stdin.read()))

    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # malformed payload -> don't interfere
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    if not is_git_push(cmd):
        return 0
    # The failure message says to override with `SDLC_SKIP_EVAL_GATE=1 git push ...`, and an
    # inline assignment sets the environment of the SHELL, not of this hook — which Claude Code
    # spawns separately. Following our own printed instructions therefore did nothing, and the
    # first commit of this gate was blocked by it. Read the override off the command line too.
    if re.search(r"(^|[\s;&|(])SDLC_SKIP_EVAL_GATE=1(\s|$)", cmd):
        os.environ["SDLC_SKIP_EVAL_GATE"] = "1"
    return gate(pathlib.Path(data.get("cwd") or REPO), pretooluse=True)


if __name__ == "__main__":
    sys.exit(main())
