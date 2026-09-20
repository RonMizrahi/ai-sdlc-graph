#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block Claude from pushing to main/master.

Reads the PreToolUse JSON payload on stdin. If the Bash command is a `git push`
that targets a protected branch (explicitly, or a bare push while the current
branch is protected), deny it and tell Claude to use a side branch + PR.

Only affects Claude's own Bash tool calls — a human pushing in a terminal is not
intercepted. Scope is this repo (wired via .claude/settings.json).
"""
import json
import re
import subprocess
import sys

PROTECTED = ("main", "master")
REASON = (
    "Direct push to main/master is blocked in this repo. Open a PR instead:\n"
    "  git switch -c feat/<name> && git push -u origin feat/<name> && gh pr create --base main\n"
    "If a direct push is genuinely required, ask the user to run it themselves."
)


GIT_GLOBAL_OPTS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path")


def is_git_push(cmd):
    """Does this shell command actually run `git push`?

    Tokenised, not grepped. The obvious regex — `\\bgit\\b[^&|;]*\\bpush\\b` — matches command lines
    that run no git at all, because `\\b` treats a hyphen as a word boundary: this repo lives under
    `~/git/`, and `.claude/hooks/pre-push-eval-gate.py` contains a hyphen-bounded `push`. A single
    command mentioning both paths was denied as a push to main, and *that is what this comment is
    made of* — the hook blocked its own repository's tooling.

    `pre-push-eval-gate.py` carries the identical function, and the duplication is deliberate: this
    hook fires on **every** Bash call in the repo, and importing that module would pull the whole
    receipts registry in on each one. Twenty lines is cheaper than the coupling; if a third hook
    needs it, that is the moment to extract it.
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


def decide():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return  # malformed payload -> don't interfere

    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    cwd = data.get("cwd") or "."

    # Only care about git push commands (allow `git -C x push`, chains, flags).
    if not is_git_push(cmd):
        return

    # Scope every question below to the `git push` SEGMENT, never the whole command line. A chain
    # like `git push -u origin sdlc/x && gh pr create --base main` names a protected branch — in a
    # different command, about a different thing — and reading the whole line denies it.
    seg = next((s for s in re.split(r"&&|\|\||;|\|", cmd) if is_git_push(s)), cmd)

    # Explicit protected target: `origin main`, ` main `, `HEAD:main`, `:main`.
    if re.search(r"(?:^|[\s:])(?:main|master)(?:\s|$)", seg) or re.search(
        r"HEAD:(?:main|master)\b", seg
    ):
        return deny()

    # The push's positional (non-flag) args.
    toks = seg.split()
    args = toks[toks.index("push") + 1:] if "push" in toks else []
    refs = [t for t in args if not t.startswith("-") and t != "origin"]
    if refs:
        return  # an explicit non-protected ref is named -> allow (feature push)

    # Bare push (no explicit ref): block only if the current branch is protected.
    try:
        branch = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        branch = ""
    if branch in PROTECTED:
        return deny()


def deny():
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": REASON,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    decide()
    sys.exit(0)
