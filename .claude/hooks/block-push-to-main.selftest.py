#!/usr/bin/env python3
"""Does the main-branch guard block what it should, and — the harder half — allow what it should?

    python3 .claude/hooks/block-push-to-main.selftest.py

This hook fires on **every** Bash call in the repo, so what it declines to block is most of its
job. It had no self-test for four releases, and it shipped the exact false positive its sibling
`pre-push-eval-gate.py` documents at length and had already fixed:

    \\bgit\\b[^&|;]*\\bpush\\b

`\\b` treats a hyphen as a word boundary. This repo lives under `~/git/`, its scratchpad path
contains `-git-`, and `.claude/hooks/pre-push-eval-gate.py` contains a hyphen-bounded `push`. Any
command line mentioning both — *including the one that opens this project's own pull requests* —
read as a push to main and was denied. The regex ran no git and matched anyway.

The fix is the tokeniser the sibling hook already used. These cases are what stop it coming back.

Exit 0 when every case holds.
"""
import importlib.util
import io
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent

spec = importlib.util.spec_from_file_location("blockmain", HERE / "block-push-to-main.py")
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)

results = []


def case(name, ok, detail=""):
    results.append((name, ok))
    print(f"{'ok   ' if ok else 'FAIL '} {name}" + (f"\n      {detail}" if not ok and detail else ""))


def verdict(cmd, cwd=str(REPO)):
    """True when the hook DENIES this command."""
    saved_in, saved_out = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps({"tool_input": {"command": cmd}, "cwd": cwd}))
    sys.stdout = io.StringIO()
    try:
        H.decide()
        out = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = saved_in, saved_out
    if not out.strip():
        return False
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── 1. what must be BLOCKED ───────────────────────────────────────────────────────────────
for cmd, why in [
    ("git push origin main", "the plain case"),
    ("git push origin master", "the other protected name"),
    ("git push -u origin main", "a flag before the ref changes nothing"),
    ("git push origin HEAD:main", "the refspec form"),
    ("git -C /somewhere push origin main", "a global option with a value before the subcommand"),
    ("/usr/bin/git push origin main", "an absolute path to git"),
    ("echo hi && git push origin main", "the second segment of a chain"),
    ("git push --force-with-lease origin main", "force-with-lease is still a push to main"),
]:
    case(f"BLOCK  {cmd}", verdict(cmd) is True, why)


# ── 2. what must be ALLOWED — the larger surface, and the one that broke ───────────────────
#
# The first case is the incident, and it took TWO defects at once — which is why neither had been
# noticed on its own:
#
#   1. `\bgit\b[^&|;]*\bpush\b` matched a command that runs no git. `-git-` in the scratchpad
#      path supplied `\bgit\b`, `pre-push-eval-gate` supplied `\bpush\b`, and `[^&|;]*` spans
#      newlines happily. Both halves must sit in ONE segment — a `&&` breaks the span, so a chain
#      does NOT reproduce it, and a "control" built from a chain is green against the bug.
#   2. The protected-branch test then read the WHOLE command line for `main`, and found the
#      `--base main` of the `gh pr create` that came after.
#
# Either alone is harmless here. Together they denied the command that opens this repository's own
# pull requests.
INCIDENT = ("python3 - <<'PY'\n"
            "p = '/tmp/-Users-ronm-git-sdlc-graph-engineering/pr-body.md'\n"
            "t = t.replace('.claude/hooks/pre-push-eval-gate.selftest.py', 'x')\n"
            "PY\n"
            "gh pr create --base main --head sdlc/promote --body-file /tmp/pr-body.md")

for cmd, why in [
    (INCIDENT,
     "THE INCIDENT: `-git-` in a path and a hyphenated `push` in a filename, same segment, no git "
     "run at all. This is the case that has to fail against the old regex — if it passes there, it "
     "is not a control"),
    ("gh pr create --base main", "opening a PR against main is the thing this hook tells you to do"),
    ("python3 .claude/hooks/pre-push-eval-gate.selftest.py",
     "a FILENAME containing a hyphen-bounded `push`, and no git at all"),
    ("cd ~/git/sdlc-graph-engineering && ls", "a `git` DIRECTORY, no git command"),
    ("git push origin sdlc/promote-beta-to-stable", "an explicit non-protected ref"),
    ("git push -u origin feat/x", "...with a flag"),
    ("git log --oneline main", "another subcommand that names main"),
    ("git switch main", "checking out main is not pushing to it"),
    ("echo 'push to main'", "the words in an argument"),
    ("git push origin feat/x && gh pr create --base main",
     "a legitimate push chained with a PR against main — the ref that matters is in the push "
     "segment, and reading the whole line denies it"),
    ("git fetch origin main", "fetch is not push"),
]:
    case(f"ALLOW  {cmd[:64]}", verdict(cmd) is False, why)


# ── 3. the bare push — the one case that has to ask git where it is ────────────────────────
#
# `git push` with no ref is only a push to main when the CURRENT branch is main, so this is the one
# question the hook cannot answer from the command line alone. Driven against a real repo on each
# branch, because stubbing the answer would test nothing but the stub.
import subprocess                                                            # noqa: E402
import tempfile                                                              # noqa: E402

TMP = pathlib.Path(tempfile.mkdtemp(prefix="block-main-selftest-"))


def git(*a):
    return subprocess.run(["git", "-C", str(TMP), *a], capture_output=True, text=True).stdout


git("init", "-b", "main", "-q")
git("config", "user.email", "selftest@example.com")
git("config", "user.name", "selftest")
(TMP / "f").write_text("x")
git("add", "-A"), git("commit", "-qm", "first")

case("BLOCK  bare `git push` while ON main", verdict("git push", str(TMP)) is True,
     "no ref named, and the current branch is protected")
git("checkout", "-qb", "feature")
case("ALLOW  bare `git push` while on a feature branch", verdict("git push", str(TMP)) is False,
     "no ref named, and the current branch is not protected")

import shutil                                                                # noqa: E402
shutil.rmtree(TMP, ignore_errors=True)

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} main-guard cases hold "
      f"({sum(1 for n, _ in results if n.startswith('ALLOW'))} of them allow-cases)")
sys.exit(1 if bad else 0)
