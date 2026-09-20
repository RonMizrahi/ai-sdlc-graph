# Before you change this plugin

**1.0.0 was not a patch on 0.11.1**: the milestone loop runs in a milestone agent with
per-milestone journals, there is no monitor, the state schema is at `schema_version 5`, and a run is
**one gitignored directory** — `docs/graph-runs/<run-id>/` — rather than a pile of prefixed files.

**The edge ids were renumbered wholesale** at 1.0.0 — 2…36 became 1…30 plus the expanded
`19·<caller>` / `20·<caller>` DEBUG rules. That breaks the never-renumber rule
(`sdlc-graph-engineering-install` → failure mode 11), and it is legal exactly once, here, for one
reason: `schema_version` 2 → 5 is an unconditional halt with no migration, so no run written against
the old ids can ever be read by this version. There is no corpus to be ambiguous about. **The rule
is back in force from 1.0.0 on** — retire an id, never reuse it.

The tree is grouped by kind: `graph/` (the model) · `nodes/` (the eight procedures) · `subagents/` ·
`workflows/` · `observability/` · `evals/`. **Everything in the eval suite resolves paths through
`evals/lib/paths.py`** — nothing counts `../` for itself, because the restructure invalidated every
such count and three of them broke silently, globbing a directory that no longer existed.

The plugin ships **three** skills now: `sdlc-graph` drives a run, `graph-run-reviewer` reviews a
finished one and writes the evals it should have had, and `onboarding` reports which optional tools
this session can invoke and what a run loses without each. `INTAKE` invokes that one on **every**
run; it is advisory, emits nothing, and cannot stop a run. **Its roster is `docs/DEPENDENCIES.md`
and that file is the only copy** — a second list in the skill is a check failure, not a style note. And it ships **its own hook** —
`hooks/hooks.json` — which snapshots every state a `--trace` run passes through.

## 1. The deterministic evals run on every edit — the rest are yours

The repo's PostToolUse hook watches this plugin. Editing anything under `plugins/sdlc-graph/`
runs **both** `run_all.py`s — this plugin's and the viewer's, because a guard edited here is what
makes the viewer's copy of the transition table stale. A red suite mid-change is expected; it is
the second half of the edit, not an error.

> A suite left out of a runner, or a plugin left out of the routing table, reads as a decision and
> behaves as an oversight — it has happened both ways here. Nothing is excluded now: the whole
> deterministic set costs **3.6 seconds** against the hook's 120s budget. Two checks hold the
> arrangement —
> `every-deterministic-suite-is-wired-into-run-all` (a suite on disk that no runner invokes) and
> `.claude/hooks/run-graph-evals.selftest.py` (a plugin the hook stopped routing to). The second
> lives with the hook because a plugin may not read above its own root, so nothing inside this
> plugin can see whether anything invokes it.

Commands, what each method catches, and why both exist: **[`TESTING.md`](TESTING.md)** — or the
illustrated version, [`artifacts/index.html`](artifacts/index.html) → **Testing**.

```bash
# what the hook already ran for you, if you want it on demand:
cd plugins/sdlc-graph/skills/sdlc-graph
python3 evals/run_all.py                     # spec + controls, walks, auditor, run-eval and hook controls, JS harness
cd ../../../sdlc-graph-viewer/skills/view-run
python3 evals/run_all.py                     # the viewer's copy agrees, and that checker can go red

# what it CANNOT run — these need a model:
cd ../../../sdlc-graph/skills/sdlc-graph
python3 evals/runs/run_scenario.py --list         # executing — a real orchestrator against a scripted agent
python3 evals/real/run_real_eval.py --list   # executing — real root + real milestone agent

# and the one WRITER, when edges.md or nodes.md moved:
cd ../../../sdlc-graph-viewer/skills/view-run
python3 evals/sync/sync_graph.py --write     # regenerate the viewer's GRAPH from the spec
```

**A change is not done until it adds the eval that would have caught its absence**, and that eval is
not done until a deliberately broken input makes it fail. *A check that cannot fail is not evidence.*
Contract and fixture format: [`../skills/sdlc-graph/evals/EVAL-INSTRUCTIONS.md`](../skills/sdlc-graph/evals/EVAL-INSTRUCTIONS.md).

## 2. Twinned skills — ask before changing either side

Eight skills exist twice: the author's standalone skill, and a graph-scoped copy at
`skills/sdlc-graph/nodes/<name>-node.md`, trimmed to that node's role. `plan-guidelines`
has its Phase 2 removed there because that phase *is* the loop the graph drives.

**Before editing either side, STOP and ask the human.** Each copy's `copied-from:` header names its
source version; `git log` that path to see what has moved.

`brainstorming` · `plan-guidelines` · `testing-standards` · `code-quality-pipeline` ·
`pr-mr-prepare` · `watch-ci` · `systematic-debugging` · `qa-engineer`

## 2b. The executing tier is where the defects actually are

`run_all.py` answers in 3.6 seconds and finds **drift**. Driving `evals/runs/` with real
orchestrator subagents finds **contradictions** — rules that are individually sensible and cannot
both be obeyed. The last full drive of ten scenarios produced six, and the signal on each was
independent agreement: three orchestrators reading the same sentence the same wrong way is not
three mistakes, it is one defect.

**When you change a rule, drive the scenarios that touch it.** The self-test only proves a scenario
is satisfiable and breakable; it cannot tell you that your new sentence contradicts an old one.

```bash
python3 evals/runs/run_scenario.py evals/runs/scenarios/<NN>-*.md --setup   # prints the brief
#   ...hand the brief to a subagent, let it drive...
python3 evals/runs/run_scenario.py evals/runs/scenarios/<NN>-*.md --check   # assert on the artifacts
```

### ...and `evals/RECEIPTS.json` records that you did — but nothing makes you

**The executing tier runs on demand, by you, and blocks nothing.** No hook drives it, and the
pre-push gate *reports* what has gone stale and then lets the push through. Only the deterministic
suites can stop a push.

That is deliberate, and it replaced a version where tier 2 did gate. Blocking left exactly two
options at the moment of pushing — spend minutes and real money right then, or reach for
`SDLC_SKIP_EVAL_GATE=1` — and an override people reach for routinely stops meaning anything, taking
the tier-1 gate's credibility with it. It also made the cheap signal hostage to the expensive one: a
push whose deterministic suites were perfectly green, blocked by evidence that had gone stale three
PRs earlier in a file nobody in that push had touched.

**You still write the case.** A change that needs an executing eval gets one authored and registered
*with the change*, and **not driven**. It lists as `NO RECEIPT`, which is the honest state: the case
exists, is discoverable, and has not been paid for yet. A case nobody wrote can never be driven; a
case written and not driven can be, any time, by name. This is the rule that keeps the tier growing
with the graph instead of ossifying at whatever was affordable the day it was built.

`RECEIPTS.json` records, per test: when it was driven, the verdict, and a **content hash of every
input the verdict depends on** — `SKILL.md`, `graph/*.md`, `subagents/*.md`, `agents/*.md` for the
tests that spawn a real milestone agent, the test file, and the harness. Change `edges.md` and every
receipt that read it goes **stale by name**. That is the moment re-driving is worth what it costs,
and the gate's report is how you find out.

```bash
python3 .claude/hooks/eval-receipts.py --list                  # checked · attested · stale · no receipt
python3 .claude/hooks/eval-receipts.py --drive --only <id>     # drive ONE, deliberately (`claude -p`)
python3 .claude/hooks/eval-receipts.py --record scenario:01-happy-milestone   # you drove it by hand
```

Three rules that are not negotiable, each with its own control in
`.claude/hooks/pre-push-eval-gate.selftest.py`:

- **A receipt is written only by a `--check` that exited 0.** A failed drive records nothing and
  prints the assertions that failed. A receipt for a red run is worse than none.
- **`--drive` is never automatic**, refuses to run unattended without an explicit opt-in, is capped,
  and names anything it left behind.
- **Hand-editing is visible.** Each receipt is sealed over its own fields — tamper-evident, not
  tamper-proof, but the cheap forgery of typing `passed` over `never-run` stops working.

The gate is *repo* infrastructure, not part of any plugin — it lives in `.claude/hooks/` and
`.githooks/`, because a plugin may not reach above its own root and a push gate is a property of the
repository. Arm it once per clone with `git config core.hooksPath .githooks`.

**Known gap, named rather than implied:** `nodes/**` is not in `inputs`. Editing a node procedure
can genuinely invalidate a drive, and including it would redden every scenario on every node edit.
If that trade reads wrong later, `spec_inputs()` is one function.

## 3. Surfaces the suite cannot reach

A plugin may not read above its own root, so these mirror the graph and are yours by hand:

| Surface | Checked by |
|---|---|
| `sdlc-graph-viewer` | its own `evals/graph_sync.py` — the only legal direction |
| `docs/*.html` | `published-counts-match-reality` reaches these — it globs `docs/*.html` and checks every node, edge, transition and return-gate count they publish |
| the **published artifacts** | `every-artifact-link-has-a-source` — every hosted link must have a row in `docs/artifacts/README.md` naming the file that produces it. Republishing the file is still yours. |

**A guard fixed in `edges.md` is not fixed until it is fixed in the surface that renders it.**

## 4. Version history that has to survive

Two facts here are user-facing, not archaeology, and they belong in any rewrite of this file:

- **A 0.11.1 run cannot be resumed by 1.0.0 or later.** The `schema_version` check is an
  unconditional halt with no migration, because a half-understood state file drives a graph into
  transitions nobody wrote.
- **Retire an edge id, never reuse it.** The wholesale renumbering at 1.0.0 was legal exactly once,
  for the reason given at the top of this file; the rule has been back in force ever since.

**This repository has no receipts.** The `RECEIPTS.json` registry stayed with the development fork
this graph was promoted out of, so `eval-receipts.py --list` reports every executing test as having
none. That is accurate rather than broken: authoring the case is mandatory, driving it is a decision
someone makes with the minutes in front of them. Arm the push gate once per clone with
`git config core.hooksPath .githooks`.
