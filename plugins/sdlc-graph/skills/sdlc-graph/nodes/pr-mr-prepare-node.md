<!-- copied-from: the standalone `pr-mr-prepare` skill @ v0.5.0 — a separate, unbundled skill of the author's; this copy is graph-scoped and meant to diverge -->
<!-- trimmed: Step 4 ("Run the quality pipeline") REMOVED IN FULL — this is the most important trim in
     the file. Gate A and Gate B already ran as their own graph nodes (`GATE_A`, `GATE_B`); re-running
     the pipeline here is duplicated work on a diff that has already been reviewed twice.
     Step 2 ("Load the matching skills") REMOVED — loading the coding standards is the `IMPLEMENT`
     node's job, via live dispatch, so the code is written under the same rules it is reviewed under.
     Step 7 CHANGED — the source opens the PR automatically and never pauses; the graph honours
     `context.auto_open_mr` instead.
     Also removed: standalone trigger phrases, and the closing "frontend standards" note (it only
     existed to point at the deleted Step 2). Remaining steps renumbered 1–5. -->

# Node: pr-mr-prepare

Serves **one** graph node: `PR`. Entered from `CLOSE_OUT` on edge 27a; exits to `CI` on edge 21.

**Idempotent.** Check for an existing PR on this branch (`gh pr list --head <branch> --state open`)
before opening one — a QA reopen re-enters this node with the PR already open, and pushing the fix
commits updates it. A second PR would split the review this node exists to obtain.

Takes finished, reviewed work from "green on my machine" to "open for review": detect the stack, get
the build and tests green, then commit → push → open the PR/MR. Run the steps in order and fix every
failure before moving to the next.

> **The quality pipeline does NOT run here.** `GATE_A` (per-file) and `GATE_B` (holistic) are separate
> graph nodes that already ran on this diff. If you find yourself invoking `code-quality-pipeline`
> from this node, stop — you are re-reviewing an already-reviewed change and burning the run's budget
> on it. This node's job is the mechanical build/commit/push/open sequence, nothing more.

---

## Step 1 — Identify the project type

`context.stack` was resolved at `INTAKE`. Confirm it against the repo — root `package.json`,
workspaces, any `apps/*` / `packages/*` layout — and state what you are treating this as:

- **Backend** signals: `@nestjs/*`, `mongoose`, `express`, a server entry point, no UI framework.
- **Frontend** signals: `react`, `next`, `vite`, a UI tree (`app/`, `pages/`, `src/components/`,
  `public/`).
- **Both**: a monorepo containing both (e.g. `apps/api` + `apps/web`), or one package with server +
  UI deps. Handle each part with its own commands.

## Step 2 — Build, format, lint, test

Run these from the relevant package root with the project's package manager (`yarn` or `npm`), **in
this order**, fixing any failure before continuing:

1. `yarn install` / `npm install` — dependencies in sync with the lockfile.
2. `yarn format` / `npm run format` — apply formatting (e.g. Prettier).
3. `yarn lint` / `npm run lint` — fix lint violations (`--fix` where available).
4. `yarn build` / `npm run build` — compile / type-check. **A red build never goes up for review.**
5. `yarn test` / `npm test` — unit + integration (e.g. `test:unit`, `test:integration`).

**Only run scripts that actually exist in the project's `package.json`** — skip and note any that are
absent. For `stack == both`, run the set for each part.

**Scope `format`/`lint` fixes to your own diff.** Do not block on pre-existing violations in files
this milestone did not touch — that is a Surgical Changes violation, and it turns a PR node into an
unrelated cleanup commit.

## Step 3 — Commit

- **Never commit to a protected branch.** `main`, `master`, `develop` are off limits. `BRANCH` already
  put you on `<task-id>/<short-description>`; if you somehow find yourself on a protected branch,
  create the feature branch before committing.
- Stage only the files that belong to this change — no secrets, build output, or unrelated edits.
- Write a clear, conventional commit message summarising the change.

## Step 4 — Push

Push the branch to `origin`, setting the upstream on first push.

## Step 5 — Open the PR / MR

Detect the host from the `origin` remote URL and match it against `context.host`:

- **GitHub** → `gh pr create`, targeting `context.main_branch`.
- **GitLab** → `glab mr create`, targeting `context.main_branch` (or the connected GitLab MCP tool,
  if available).

Give it a clear title and a description summarising what changed and why; reference the Jira/issue ID
if there is one. For a milestone that branched off a **parent milestone** rather than
`main_branch`, name that dependency in the description.

### Honour `context.auto_open_mr`

| Value | Behaviour |
|---|---|
| `true` | Open the PR/MR **without pausing**. |
| `false` | **Pause and ask for confirmation** before opening it. |

> **`STRATEGY` settled this once, so the loop is never interrupted to *decide* it.** The source skill
> said "open it automatically; don't pause to confirm"; `plan-guidelines` said "ask for confirmation
> before creating the MR". The graph resolves the conflict by asking the user at strategy time and
> recording the answer — this node reads the flag, it never re-opens the question.

---

## Contract

| | |
|---|---|
| **inputs** | `milestones[cursor].branch`, `context.{host,main_branch,auto_open_mr,stack}` |
| **emits** | `milestones[cursor].pr`, `milestones[cursor].node = PR` |
| **exit guard** | PR/MR open → `PR_FINAL_REVIEW` (edge 22), which posts the PR review and passes straight to `CI` (edge 30) |
| **on failure** | red build/lint/test → fix in place and continue; push rejected → `BLOCKED` + `blocked` |
| **max attempts** | 2 |
| **requires** | `gh` (GitHub) **or** `glab` (GitLab), matching `context.host` |
| **interactive** | **only if `auto_open_mr == false`** — settled once at `STRATEGY`, never asked mid-loop |

> **`milestones[cursor].pr` is what `CI` and `MERGE` both read.** Record the PR/MR number (not just
> the URL) — `CI` resolves the run from it and `MERGE` polls its state.
