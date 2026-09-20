# Dependencies — every tool this graph dispatches to, and what a run does without it

**This file is the roster.** `/sdlc-graph:onboarding` walks the table below and reports what this
session can actually invoke; nothing else in this plugin keeps a second list. If you add, remove or
rename a tool, do it here — `onboarding-checklist-derives-from-the-dependency-doc` in
`skills/sdlc-graph/evals/spec/spec_consistency.py` fails when a roster grows back anywhere else.

## The one hard requirement

**`git`.** `INTAKE` blocks without a repository, and that is the only tool whose absence stops a run.

**Everything below is optional, and every single one is third-party** — somebody else's plugin or a
capability built into Claude Code. Exactly one of them ships in this bundle (`sdlc-graph-viewer`) and
even that one is a separate, optional install. **The graph depends on none of them.** It dispatches
whatever is there, and an absence is *recorded*, never quietly passed:

> A tool that does not resolve at preflight gets its own `skipped_gates[]` entry and the node is
> **not** marked passed. The ledger is append-only and copied into the plan at `CLOSE_OUT` — so
> installing a tool later does not retroactively pass a gate that ran without it.

**Preflight tests invocability, not installed-ness.** A plugin on disk but disabled, or installed
after this session started, is as absent as one never installed.

## The roster

| Tool (exact id) | In this bundle? | Dispatched at | Without it | Install |
|---|---|---|---|---|
| `sdlc-graph-viewer:view-run` | **yes** — a separate, optional plugin in this same bundle | run start, for the live and snapshot views | No live view of the run. One line at run start and the run carries on — it is a companion, never a gate. | `/plugin marketplace add RonMizrahi/sdlc-graph-engineering` then `/plugin install sdlc-graph-viewer@sdlc-graph-engineering` |
| `code-review` — built into Claude Code | no | `GATE_B`, as `code-review <main>..<branch> high` (a branch range, no open PR, **no `--comment`**) | The whole-diff review is ledgered and `GATE_B` is not recorded as passed. The milestone still finishes. | Built in — nothing to install. |
| `security-review` — built into Claude Code | no | `GATE_A` step 3 | The security pass is ledgered; the other three Gate A steps still run. | Built in — nothing to install. |
| `pr-review-toolkit:code-reviewer` | no | `GATE_A` steps 1 and 4 | Review and final review are ledgered; simplify and security still run. | `/plugin install pr-review-toolkit@claude-plugins-official` |
| `code-simplifier` | no | `GATE_A` step 2 | The simplification pass is ledgered. | `/plugin install code-simplifier@claude-plugins-official` |
| `code-review:code-review` (with `--comment`) | no | `PR_FINAL_REVIEW`, on the now-open PR | No inline PR comments; ledgered. The run still reaches `MERGE`. | `/plugin install code-review@claude-plugins-official` |
| `claude-md-management:claude-md-improver` | no | `CLOSE_OUT` | Ledgered — do the CLAUDE.md update by hand and say the improver was skipped. | `/plugin install claude-md-management@claude-plugins-official` |
| `gh` (GitHub) · `glab` (GitLab) | no — a CLI, not a plugin | `PR` and `MERGE`; `CI` needs `gh` specifically | No PR is opened and `MERGE` asks you to merge locally, then confirms. All ledgered. `host: none` makes this structural rather than missing. | <https://cli.github.com> · <https://gitlab.com/gitlab-org/cli> |
| **the project's own coding-standards skill** — no fixed id, dispatched by role | no — the project's choice | `IMPLEMENT`, backend / frontend / both per `context.stack` | Code is written against the repository's own conventions and the absence is ledgered. | **No install line, deliberately** — see below. |

The four `claude-plugins-official` rows are Anthropic's public marketplace
(`anthropics/claude-plugins-official`); add it once with
`/plugin marketplace add anthropics/claude-plugins-official`.

> **`pr-review-toolkit:code-reviewer` must be write-capable** — Gate A steps 1 and 4 apply fixes.
> `feature-dev:code-reviewer` is a different agent with no Edit/Write tool and is not a substitute.

## The coding-standards skill has no install line, and that is the design

`IMPLEMENT` live-dispatches **whatever standards skill the project has installed** for its stack. A
copied coding standard drifts, and then code is reviewed against a stale rulebook — which is worse
than the coupling a copy would remove. So this plugin **bundles no coding standard and names none**:
which skill a team uses is a property of that team, not of this graph.

If the project has none, `IMPLEMENT` writes code against the repository's own conventions and records
the absence. That is a complete, supported way to run the graph — not a degraded one to apologise for.

## Not on the roster, deliberately

| | Why it is not an optional tool |
|---|---|
| **Playwright** | At `E2E` a missing Playwright is **work to do, not a gate to skip**: it is a devDependency plus a browser download. Install it and run the suite. The ledgerable case at `E2E` is an app that genuinely cannot be brought up, which is a different thing. |
| **`git`** | The hard requirement, above. Not optional, so not a row here. |
| **project test scripts** | `TEST` requires the project's own scripts. Absent is ledgered, but there is nothing to install — a project without tests is a project fact. |

## When the install source is uncertain

**Never invent a marketplace name.** An install line that does not work costs the reader the minute
*and* their trust in every other line on the page.

The `@marketplace` suffix on an already-installed plugin is ground truth for where that copy came
from (`claude plugin list --json`). If an id here does not resolve on your machine, say so in those
words — *"this session cannot confirm which marketplace it came from; install it the way you got your
other plugins"* — rather than substituting a plausible-looking name. Do not copy a private or
personal marketplace name out of a local install into anything published.

## How this file is used

`/sdlc-graph:onboarding` reads **this file** and reports the roster row by row. It installs nothing —
a skill cannot run `/plugin install` — and it gates nothing: the graph invokes it at run start on
every run, ignores its result, and continues. See
[`../skills/onboarding/SKILL.md`](../skills/onboarding/SKILL.md) and `graph/nodes.md` § `INTAKE`.
