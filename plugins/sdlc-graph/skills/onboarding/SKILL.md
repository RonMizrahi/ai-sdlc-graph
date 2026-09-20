---
name: onboarding
description: >-
  Produce the sdlc-graph tooling checklist — walk the plugin's dependency roster, report tool by tool
  what this session can actually invoke and what it cannot, print the install line for each gap, and
  say what a run does without it. Every tool on that roster is third-party and optional: the graph
  requires git and nothing else, and every absence is recorded in `skipped_gates[]` while the run
  continues. Invoked at the start of every sdlc-graph run, and by a human any time the question comes
  up. Purely advisory — it installs nothing, gates nothing, and never stops or delays a run.
when_to_use: >-
  at the start of an sdlc-graph run, what does sdlc-graph need installed, which graph tools am I
  missing, check my sdlc-graph tooling, why was that gate skipped, install the run viewer
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash, Read
---

# sdlc-graph — the tooling checklist

## Goal

Answer one question, tool by tool: **which of the things a run would dispatch to can this session
actually invoke, and what does a run lose for each one it cannot?**

**Everything on the roster is third-party and optional.** The graph's only hard requirement is `git`.
Every other tool is somebody else's plugin or a capability built into Claude Code, dispatched rather
than copied — because a copied reviewer drifts and then reviews against a stale rulebook. Exactly one
of them ships in this bundle (`sdlc-graph-viewer`), and even that is a separate, optional install.

**Every absence is recorded in `skipped_gates[]` and the run continues.** Nothing is ever reported as
passed because its tool was missing, and the ledger is append-only: installing a tool later does not
retroactively pass a gate that ran without it.

## Use When

- **Every `sdlc-graph` run start.** `INTAKE` invokes this, always, before the run proceeds past it.
- A human asks what `sdlc-graph` needs, or why a finished run's report led with `skipped_gates[]`.

## Do Not Use When

- You want a *machine* set up — language toolchains, editors, containers. That is a different skill
  entirely; this one only looks at what this session can invoke for a graph run.

## Rules

1. **Advisory. This gates nothing, blocks nothing, and stops nothing.** It prints a checklist. A run
   behaves identically whether every row is green or every row is missing — the ledger, not this
   skill, is what records an absence. **It is never a human stop**: the graph has six and this is not
   one of them. Report and hand control straight back.
2. **It installs nothing, fetches nothing, enables nothing.** A skill cannot run `/plugin install` —
   that is a user command — and this one would not if it could. Print the line; the human runs it,
   whenever they like, including after the run. **The check is automatic; acting on it is not.**
   Never install, download, enable, or modify configuration on the reader's behalf, and never offer
   to: an unasked-for install is a change to somebody's machine that they did not choose.
3. **Quiet, and written only in the session.** The checklist is text in the conversation — it
   writes no file, touches no run directory, creates no report and changes no configuration. That is
   why `allowed-tools` is `Bash, Read` and carries nothing that can write: a checklist that leaves
   artefacts behind is a checklist someone has to clean up, and this one is paid for on every run.
   **When every row is invocable, say so in one line and stop** — the full list is for when there is
   something to act on, or when a human asked for it.
4. **Cheap enough to pay on every run.** One shell call, no network, no per-tool probing, output in
   the tens of lines. If this ever costs more than that, it has stopped being affordable at the place
   it is invoked from.
5. **`${CLAUDE_PLUGIN_ROOT}/docs/DEPENDENCIES.md` is the roster. This file keeps no copy of it.**
   Read it and walk **every** row. A second list here could disagree with the one a human reads, and
   the one a human reads would still be right — so there is only one.
6. **Test invocability, not the filesystem.** A file on disk is not a tool you can call.
7. **Never invent a marketplace name.** The roster carries the install lines and the rule for an
   uncertain source; follow what it says rather than guessing a plausible one.
8. **Never present an optional tool as a requirement**, and never name a plugin this bundle does not
   ship as something the graph depends on. It depends on `git`.

## Step 1 — read the roster

Read `${CLAUDE_PLUGIN_ROOT}/docs/DEPENDENCIES.md`. Its table gives, per tool: the exact id, whether
it ships in this bundle, the node that dispatches it, what a run does without it, and how to install
it. The section below the table names what is deliberately *not* a roster row, and why. **Everything
you report comes from there** — this skill contributes the detection and the formatting, nothing else.

## Step 2 — detect what is invocable

Two sources. They answer different halves, and together they cost one shell call.

| Source | What it settles |
|---|---|
| **The session's own skill/command inventory** — the skills this session lists as available, by exact id | **The authority.** Listed → invocable now. Not listed → not invocable now, whatever is on disk. |
| `claude plugin list --json` | *Why*, and what to do: absent from the output → not installed; present with `"enabled": false` → installed and switched off (`/plugin enable <id>`, no reinstall); present and enabled but missing from the session inventory → almost certainly installed after this session started, so it needs a restart, not an install. |

```bash
claude plugin list --json      # read once, reuse for every row — never shell out per tool
```

A CLI row (`gh`, `glab`) is settled by whether the command resolves, not by the plugin list.

> The `@marketplace` suffix on an installed id is ground truth for where that copy came from. Prefer
> it over anything written anywhere when the two disagree — and never copy a private or personal
> marketplace name out of it into a report.

## Step 3 — print the checklist

**If every row is invocable, the whole output is one line** — at run start nobody needs a table to
be told there is nothing to do:

> Tooling check — all N optional tools invocable. Nothing installed or changed.

**Otherwise**, open with what this is, because a reader who did not ask for it deserves to know why
it appeared and what it just did:

> Tooling check for this run — read-only. Nothing was installed, downloaded or changed.

One line per roster row, in the roster's own order, each marked **✓ invocable** or **✗ missing**.
Then, for the missing ones only:

- **what a run does without it** — the roster's own words, not a paraphrase of your own;
- **the install line**, verbatim from the roster. A plugin that is installed but *disabled* gets
  `/plugin enable <id>` instead — reinstalling it fixes nothing.

Close with this line, always:

> None of this blocks a run. Every absence is recorded in `skipped_gates[]`, carried into the plan at
> close-out, and led with in the final report — nothing is reported as passed because its tool was
> missing.

**And when at least one row is ✗ missing, close with the hand-back as well** — the decision is the
human's, and it is never taken for them:

> Installing is your call, not the graph's: **nothing here installs, downloads or enables anything
> on its own.** Run `/sdlc-graph:onboarding` whenever you want this list again with the exact
> install lines, then run the ones you want. The run continues either way.

That sentence is the whole shape of this skill at run start: **the check is automatic, the install
never is.** An agent that reads a missing row as licence to fetch, install, enable or "just set it
up quickly" has broken the one rule this file exists to hold.

Never print a verdict, a score, a readiness percentage, or anything a reader could mistake for a
gate. **There is no such thing as failing this checklist.**

### When you cannot confirm a source

If `claude plugin marketplace list` does not show the marketplace an install line names, do **not**
substitute another name and do not guess a fork. Say it plainly:

> `<tool>` is not invocable here. It is a public plugin, but this session cannot confirm which
> marketplace it came from — install it the same way you got your other plugins, then re-run
> `/sdlc-graph:onboarding`.

## Why `disable-model-invocation: false`

Deliberate, and the opposite of the graph's own setting.

**The graph invokes this at `INTAKE`, on every run.** A checklist that only a human could trigger
would be a checklist most runs never get, and the whole point is that the roster is answered once, up
front, instead of one ledger entry at a time as each gate discovers its tool is gone. Model
invocation is therefore required, not merely allowed.

**The safety is structural, not a trigger flag.** This skill reads two things and prints text: it
writes no state, evaluates no guard, and has no way to stop a run. `INTAKE` neither waits on its
result nor records anything from it, so the worst case of an unwanted invocation is some wasted
output — never a stalled run, and never a seventh human stop. `sdlc-graph` itself sets
`disable-model-invocation: true` because *starting an entire SDLC* on a description match is a real
hazard; printing a tooling checklist is not.

`user-invocable: true` keeps `/sdlc-graph:onboarding` one keystroke away for the person who wants it
outside a run.

## References

- **`${CLAUDE_PLUGIN_ROOT}/docs/DEPENDENCIES.md`** — the roster. The only list.
- `${CLAUDE_PLUGIN_ROOT}/skills/sdlc-graph/graph/nodes.md` — each node's `requires` row, if someone
  asks *why* a tool is needed where it is.
- `${CLAUDE_PLUGIN_ROOT}/skills/sdlc-graph/graph/state.md` § the skipped-gate ledger — what happens
  to an absence during a run.
