#!/usr/bin/env python3
"""Negative controls for spec_consistency.py — plant one defect, assert its check fires.

`graph_walk.py` has had negative controls since it was written: two fixtures that MUST be
rejected, each planted violation named. `spec_consistency.py` never did. Its checks are regexes
over prose, which is the easiest kind of check to write in a way that cannot fail — and this
project has already found three of those by hand ("a fixed-width window that spilled into the
next section; an alternation that matched incidental prose; a field check that grepped the whole
file so renaming `headline` left it green").

Running this the first time found two more, both mine, both in checks written the same hour:
one asserted `guards_tested`/`tried` existed anywhere in state.md rather than inside the `stopped`
shape, and one asserted `git diff --name-only` appeared anywhere in workflow-dispatch.md rather
than inside the R7 row. Both passed with the thing they check for deleted.

    python3 spec_controls.py

Each control copies the plugin to a temp dir, mutates ONE file, and requires the named check to
go red. Exit 0 when every control fires.

SCOPE: the checks added or reshaped by the schema-5 change. The older checks predate this runner
and are not covered here — that is a gap, and it is named rather than papered over.
"""
import json, pathlib, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

# The PLUGIN root — this runner copies the whole plugin and mutates one file in the copy.
# It used to be four `.parent`s from this file; the restructure moved the file a level deeper
# and four `.parent`s became `skills/`, which copies the wrong tree and finds no controls.
ROOT = paths.PLUGIN

# Everything below is relative to ROOT. `SK` is the skill inside it.
SK = f"skills/{paths.SKILL.name}"

def subs(path, *pairs):
    """One plant, several substitutions in the same file. A rule stated twice — once as a rule and
    once in the output contract it governs — needs both broken, or the control passes on the copy
    it left behind and reports a check that cannot fail as a check that can."""
    def f(root):
        p = root / path
        t = p.read_text()
        for old, new in pairs:
            assert old in t, f"control text not found in {path}: {old[:50]}"
            t = t.replace(old, new, 1)
        p.write_text(t)
    return f


def sub(path, old, new, count=1):
    def f(root):
        p = root / path
        t = p.read_text()
        assert old in t, f"control text not found in {path}: {old[:50]}"
        p.write_text(t.replace(old, new, count))
    return f

def fixture_bump(root):
    p = root / SK / paths.REL_DIRS["fixtures"] / "strategy-a-happy.json"
    d = json.loads(p.read_text()); d["initial_state"]["schema_version"] = 4
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False))

def fixture_node(root):
    p = root / SK / paths.REL_DIRS["fixtures"] / "loops-and-reopen.json"
    d = json.loads(p.read_text())
    d["initial_state"]["milestones"][0]["node"] = "GATE_B_PASSED"
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False))

S = f"{SK}/{paths.REL['state']}"
E = f"{SK}/{paths.REL['edges']}"
N = f"{SK}/{paths.REL['nodes']}"
W = f"{SK}/{paths.REL['dispatch']}"
K = f"{SK}/SKILL.md"
A = f"{SK}/evals/audit/audit_run.py"
R = f"{SK}/evals/run_all.py"
R2 = f"{SK}/evals/spec/spec_controls.py"
# The rendered artifact. Its home moved to docs/artifacts/ — see the control below.
HTML = "docs/artifacts/index.html"
# The plugin's second skill.
RV = "skills/graph-run-reviewer/SKILL.md"
# The artifact manifest — every hosted link mapped to the file that produces it.
AM = "docs/artifacts/README.md"
# The behavioural cases. Defined up here, not beside the block that used to be its only
# user — a name bound BELOW the CONTROLS list it appears in is a NameError at import.
J = f"{SK}/evals/behavioural/evals.json"
RM = "README.md"
# The walker. It MECHANISES state.md's `status`/`stopped.kind` agreement, so a resolution written
# only in the table is a resolution no fixture may model.
GW = f"{SK}/evals/walks/graph_walk.py"
# The milestone agent — the file the writer of the journal actually reads. A contract that lives
# only in workflow-dispatch.md is a contract nobody is instructed to follow.
MA = "agents/sdlc-graph-milestone.md"

# The third skill in this plugin — advisory, named at INTAKE, and invoked by nobody during a run.
OB = "skills/onboarding/SKILL.md"
# ...and the roster it derives from. The doc is the single source of truth; the skill walks it.
DEP = "docs/DEPENDENCIES.md"
# The QA node's bring-up step, and one walk fixture: two surfaces the `published` glob never
# reached, which is exactly where two of the eight unpublished-plugin mentions were hiding.
QN = f"{SK}/nodes/qa-engineer-node.md"
FX = f"{SK}/{paths.REL_DIRS['fixtures']}/strategy-b-backend-no-e2e.json"

# The three names `no-unpublished-plugin-name-ships-in-this-plugin` forbids, assembled at runtime
# from fragments. THIS FILE IS INSIDE THE CORPUS THAT CHECK SCANS, so a literal here would redden a
# clean tree; and `grep -rn "<name>" .` over the repository — the check a human actually runs — has
# to come back empty too. Concatenation satisfies both and still plants the real string in the copy.
NAME_A = "nestjs-backend" + "-standards"
NAME_B = "front-react" + "-development"
NAME_C = "developer-experience:local" + "-deploy"


def swap_gate_a_has_ui_predicates(root):
    """Move `has_ui == false` from its row to the other GATE_A exit, leaving the prose citing the
    old number. Proves `the-has-ui-note-cites-the-guard-it-actually-means` resolves the guard FROM
    the table rather than hardcoding 13 — a check that hardcodes it is a spelling test that goes
    stale the next time the rows are renumbered, which is the defect it was written for."""
    p = root / E
    out = []
    for line in p.read_text().splitlines(keepends=True):
        if line.startswith("| 12 |") or line.startswith("| 13 |"):
            line = (line.replace("has_ui == true", "has_ui == \x00")
                        .replace("has_ui == false", "has_ui == true")
                        .replace("has_ui == \x00", "has_ui == false"))
        out.append(line)
    p.write_text("".join(out))


CONTROLS = [
    ("schema-version-is-stated-in-exactly-one-place",
     "the prose says a different version from the SCHEMA_VERSION line",
     sub(S, "**That line is the only place the number is written.**",
            "**That line is the only place the number is written** — currently `4`.")),
    ("schema-version-is-stated-in-exactly-one-place",
     "a fixture sits on a version the spec would refuse to resume", fixture_bump),
    ("schema-version-is-stated-in-exactly-one-place",
     "the auditor does not know the schema version",
     sub(A, "SCHEMA_VERSION = 5", "SCHEMA_VERSION = 4")),
    ("no-field-is-written-and-never-read",
     "milestones[].node is declared again",
     sub(S, "| `milestones[].base_sha` |",
            "| `milestones[].node` | string | per-milestone position |\n| `milestones[].base_sha` |")),
    ("no-field-is-written-and-never-read",
     "a fixture writes the invented value back", fixture_node),
    ("one-field-answers-why-the-run-is-not-moving",
     "`paused` grows back beside `stopped`",
     sub(S, "| `stopped` | object \\| null |",
            "| `paused` | object \\| null | a deliberate stop |\n| `stopped` | object \\| null |")),
    ("one-field-answers-why-the-run-is-not-moving",
     "`stopped` loses the fields that make BLOCKED resumable",
     sub(S, '"guards_tested": ["tests green after review-and-fixes and a milestone remains …"],\n             "tried": ["re-ran the suite after each fix", "reverted the simplifier\'s change to auth.service.ts"] }',
            "}")),
    ("the-bundle-carries-no-field-only-checked-against-the-world",
     "`applied` comes back into the bundle schema",
     sub(W, "uncovered_count, skipped_steps[], rerun_recommended },",
            "uncovered_count, skipped_steps[], rerun_recommended, applied[] },")),
    ("the-bundle-carries-no-field-only-checked-against-the-world",
     "the world-sourced replacement is dropped with it",
     sub(W, "**`git diff --name-only` is run by you and recorded in `verified`**",
            "**the diff is recorded in `verified`**")),
    ("the-debug-round-trip-is-one-rule-and-still-fully-covered",
     "a caller is dropped from the rule",
     sub(E, "| 19 | **any of** `TEST` · `E2E` · `GATE_A` · `GATE_B` · `CI` · `CONSOLIDATE` |",
            "| 19 | **any of** `TEST` · `E2E` · `GATE_A` · `GATE_B` · `CI` |")),
    ("the-debug-round-trip-is-one-rule-and-still-fully-covered",
     "the enumeration comes back as literal rows",
     sub(E, "| 20 | `DEBUG` | **the node named in `debug_return_to`** | root cause fixed | — |",
            "| 20 | `DEBUG` | **the node named in `debug_return_to`** | root cause fixed | — |\n"
            "| 21 | `TEST` | `DEBUG` | suite red | 3 |")),
    # `start-and-end-are-notation-not-transitions` was retired claiming `published-counts-match-reality`
    # as its successor. This is that claim, tested: put the row back and the successor must fire.
    # A retirement whose successor is only asserted is a check deleted on a promise.
    # The defect this pair was written for: GATE_B named a reviewer that cannot read a local diff,
    # so the node could never be backed by its own required tool. One control puts the PR-only
    # command back on GATE_B; the other deletes the node that legitimately owns it.
    ("gate-b-reviewer-can-run-before-a-pr-exists",
     "GATE_B goes back to requiring `code-review:code-review`, the gh-pr-only command that cannot "
     "read a local diff and so can never run before the PR node",
     sub(N, "| **requires** | the **built-in `code-review`** skill, invoked with an explicit range: "
            "`code-review <main_branch>..<branch> high`.",
            "| **requires** | `code-review:code-review`.")),

    ("gate-b-reviewer-can-run-before-a-pr-exists",
     "the PR-only reviewer loses the node that owns it, so nothing in the graph can ever run it",
     sub(N, "### `PR_FINAL_REVIEW`", "### `PR_FINAL_REVIEW_REMOVED`")),

    ("published-counts-match-reality",
     "`[start]` returns as a table row — the retired check's successor must catch it",
     sub(E, "| 1 | `INTAKE` | `SPEC` |", "| 0 | `[start]` | `INTAKE` | run created | — |\n| 1 | `INTAKE` | `SPEC` |")),
    ("guards-are-written-in-exactly-one-file",
     "nodes.md re-grows its second rendering of the guards",
     sub(N, "| **on failure** | **not a git repo → `BLOCKED`.**",
            "| **exit guards** | `spec_path == null → SPEC` |\n| **on failure** | **not a git repo → `BLOCKED`.**")),
    ("skill-md-keeps-no-second-copy-of-a-reference-table",
     "SKILL.md re-grows the stop table",
     sub(K, "### 7. Report at the terminal state",
            "| Stop | Node |\n|---|---|\n| Spec approval | `SPEC` |\n\n### 7. Report at the terminal state")),
    ("the-human-rows-are-the-only-stop-list",
     "a seventh node declares a human stop",
     sub(N, "| **max attempts** | **3**, then `BLOCKED` |",
            "| **max attempts** | **3**, then `BLOCKED` |\n| **human** | **`approval-after`** |")),
    ("has-ui-is-a-boolean-before-the-loop-starts",
     "the STRATEGY exit stops requiring a boolean",
     sub(E, "**and** `context.has_ui` is a boolean | — |", "| — |")),
    ("loop-bounds-are-parsed-from-the-contract-never-copied",
     "the auditor re-grows a literal bounds dict",
     sub(A, "BOUNDS = _bounds()", 'BOUNDS = {"TEST": 3}')),
    ("agent-dispatch-is-background-and-monitored",
     "the header filter goes, so under C `tail`'s `==> path <==` lines reach jq and kill the monitor",
     sub(K, '                        "grep --line-buffered -v -e \'^==>\' -e \'^$\' | " // tail\'s per-file headers\n', "")),
    ("a-halt-can-actually-be-recorded",
     "state.md loses § Recording a halt, so no `on failure` exit has a legal shape again",
     sub(S, "### Recording a halt", "### Notes on halting")),
    ("a-halt-can-actually-be-recorded",
     "SKILL.md's validation goes back to demanding a guard on EVERY history entry",
     sub(K, " —\n  **except the final halt entry**, whose `guard` is empty because an `on failure` exit is not a\n"
            "  guarded transition and no row declares it. `stopped` carries its reason instead. See\n"
            "  `state.md` § *Recording a halt*.", ".")),
    ("total-silence-is-not-cheaper-than-partial-silence",
     "the absent-journal clause stops conditioning on `outcome`, so writing NO journal is cheaper "
     "than writing an incomplete one",
     sub(W, "\n> **But only when the bundle agrees that the agent never got going.** A bundle whose `outcome` is\n"
            "> **`completed`**, claiming a full itinerary, with **zero** journal lines is not a died-early agent —\n"
            "> it is the fabricated row above, for every node it claims, and it **`BLOCKED`s**. Without this,\n"
            "> R13 is *easier to defeat by total silence than by partial silence*: an agent that writes four of\n"
            "> five lines is caught, and one that writes none is merely \"not checked\". Found by an orchestrator\n"
            "> driving scenario 08 — it followed the absent-entirely clause correctly and then said so.\n", "\n")),
    ("strategy-c-keeps-its-fail-closed-bounds",
     "the concurrency cap disappears from strategy C",
     sub(W, "> - **At most 5 concurrent milestone agents.** Each is a full-tool agent with a worktree of its own;\n"
            ">   the sixth costs more than it buys. Milestones past the cap wait for a slot — they are not dropped\n"
            ">   and not merged into a sibling.\n", "")),
    ("strategy-c-keeps-its-fail-closed-bounds",
     "a missing `deps` field stops degrading to sequential — the fail-OPEN direction",
     sub(W, "> - **A milestone whose `deps` field is missing, or is not an array, runs SEQUENTIALLY.** Missing is\n"
            ">   not the same as `[]`.", "> - **Milestones run concurrently where `deps` allow.**")),
    ("strategy-c-keeps-its-fail-closed-bounds",
     "PLAN stops seeding `deps`, so the field can be absent at STRATEGY at all",
     sub(N, "**`deps` (always present, `[]` when there are none)**", "`deps`")),
    ("attempt-counts-says-whether-a-first-pass-belongs-in-it",
     "R10 stops saying whether a first pass belongs in attempt_counts — five orchestrators split "
     "on exactly this",
     sub(W, "**`attempt_counts` carries only nodes entered more than once**",
            "`attempt_counts` carries what was spent")),
    ("attempt-counts-says-whether-a-first-pass-belongs-in-it",
     "the schema stops telling the AGENT the same rule the gate reads it under",
     sub(W, "// RETRIES ONLY — a node entered once is absent, so", "// what you SPENT")),
    ("agent-dispatch-is-background-and-monitored",
     "the Monitor command goes back to globbing for journals that do not exist yet — five "
     "orchestrators went silently blind on exactly this",
     sub(K, 'command: "tail -n +1 -F docs/graph-runs/<run-id>/journals/milestone-1.jsonl "\n'
            '                        "docs/graph-runs/<run-id>/journals/milestone-2.jsonl | "     // one path per milestone spawned\n',
            'command: "tail -n +1 -F docs/graph-runs/<run-id>/journals/milestone-*.jsonl | "\n')),
    ("eval-prose-cites-edges-that-exist",
     "R1 goes back to sending its orchestrator down edge 18c, which the DEBUG collapse deleted",
     sub("skills/sdlc-graph/evals/real/tests/R1-journals-as-it-goes.md",
         "that is edge 17 to `CLOSE_OUT`", "that is edge 18c to `CLOSE_OUT`")),
    ("every-check-has-a-control",
     "a check is registered with no control, which is how the 15%-inert rate comes back",
     # Anchored on the NEWLINE before the entry. Without it, `str.replace(count=1)` found this very
     # line first — the mutation string contains the id it is looking for — and renamed its own
     # source instead of the control below. The check stayed green because the real entry was
     # untouched. Seventh time this session that a pattern matched the text describing itself.
     sub(R2, '\n    ("mermaid-routes-on-rerun-not-clean",', '\n    ("x-uncontrolled-check",')),
    # ------------------------------------------------------------------------------------
    # The restructure's own control. `published-counts-match-reality` is the ONLY check that
    # reaches the rendered HTML, and it found it through the glob `docs/*.html`. Moving
    # `index.html` into `docs/artifacts/` made that pattern match zero files — so the check kept
    # passing, over an empty corpus, announcing nothing. A glob narrowed by a file move is a check
    # switched off by a file move.
    #
    # This mutation corrupts a count INSIDE the artifact. It fires only if the check actually
    # opened the file, so it fails in both directions that matter: the glob narrowing again, and
    # the artifact moving somewhere the glob does not reach (`sub()` raises on a missing path).
    #
    # Deleting the HTML would NOT work as a control — a smaller corpus has fewer counts to
    # disagree with, so the check would go green. The control has to make the file WRONG.
    ("published-counts-match-reality",
     "the rendered artifact keeps a transition count the graph no longer has — and the check must "
     "still be reaching `docs/artifacts/` to notice",
     sub(HTML, "<span>40 guarded transitions</span>", "<span>41 guarded transitions</span>")),

    ("resume-blocks-on-the-version-not-on-any-absent-field",
     "Resume step 1 goes back to blocking on `a missing field` without saying which — the reading "
     "that halts every healthy run, taken by three orchestrators independently",
     sub(S, "or a missing\n   `schema_version` key**", "or a missing field**")),

    ("the-orchestrators-own-hop-is-not-a-replayed-one",
     "the carve-out for the orchestrator's own GATE_B exit disappears, so R3 and § Write points "
     "contradict each other again",
     sub(S, "> **The hop OUT of `GATE_B` is not a replayed entry**", "> **A note.**")),

    ("a-halt-nobody-recorded-is-not-a-shape-to-copy",
     "`the halt signature` goes back to reading as a prescription, so an orchestrator writes no "
     "history entry and the trail ends at a node with no exit",
     sub(S, "is the signature of a halt that was NEVER RECORDED", "is the halt signature")),
    ("a-halt-nobody-recorded-is-not-a-shape-to-copy",
     "§ Recording a halt loses the return-gate case, so a refused bundle parks resume at a node the "
     "run never entered",
     sub(S, "| **when the RETURN GATE is what failed** |", "| **a note** |")),

    ("interrogation-and-re-obtainable-agree-on-the-observation",
     "SKILL.md goes back to forbidding what *Re-obtainable* prescribes, on the same field",
     sub(K, "**it never satisfies an R-check.**",
            "it never satisfies an R-check and never becomes an `observation`.")),
    ("interrogation-and-re-obtainable-agree-on-the-observation",
     "the evidence-versus-authorship line disappears, so `ask for a missing field` reads as licence "
     "to ask for a missing `run_id`",
     sub(K, "never ask for\n  > a fact the gate checks — `dispatch`, a `run_id`, a sha.", "")),

    ("every-rejection-says-which-outcome-it-is",
     "the Unreadable outcome is deleted, so an absent REQUIRED field has no procedure again",
     sub(W, "| **Unreadable** |", "| **A note** |")),
    ("every-rejection-says-which-outcome-it-is",
     "the schema goes back to `reject` with no outcome named — three orchestrators, three different "
     "procedures",
     sub(W, "Absent ⟹ reject as **Unreadable** (§ Five outcomes) and re-run the node:",
            "Absent ⟹ reject:")),

    ("r13-does-not-fire-on-every-honest-bundle",
     "R13 goes back to demanding a trace entry per journal node without saying `claimed_to` counts "
     "— it then rejects every honest completed bundle on GATE_B",
     sub(W, "names a node the trace **mentions** — as a `from` **or** as a `claimed_to` —",
            "has a `trace[]` entry for that node,")),

    ("the-agent-knows-its-host-and-its-repo",
     "`context.host` goes back on the withheld list, so the agent cannot tell an absent code-review "
     "from an inapplicable one",
     sub(W, "**Deliberately not passed:** `context.qa_env` (secrets-adjacent, and `QA` is the orchestrator's),\n",
            "**Deliberately not passed:** `context.qa_env`, `context.host` (an agent never opens a PR),\n")),
    ("the-agent-knows-its-host-and-its-repo",
     "the security-review cwd warning disappears — a clean diff of the wrong tree reads as a pass",
     sub(W, "**And the agent is told which repository it is in.**", "**A note.**")),

    ("a-dead-agent-keeps-its-diagnosis",
     "the progress block is nulled on death with nowhere for the diagnosis to go — the re-spawn "
     "loses how far the last agent got",
     sub(S, "**When the agent DIED, copy `at_node` and `headline` into `stopped.reason` before "
            "nulling**", "The block is simply cleared")),

    ("eval-prose-cites-edges-that-exist",
     "the DEBUG rule's row number changes and prose citing the old one is no longer caught — this "
     "exercises the ROW-id half of the check, which the expanded-transition half cannot reach: the "
     "walker turns row 19 into `19·TEST`, `19·GATE_A` … so a bare `19` is only valid because the "
     "row exists",
     sub(E, "| 19 | **any of**", "| 91 | **any of**")),
    ("eval-prose-cites-edges-that-exist",
     "a behavioural case sends an orchestrator to an edge that does not exist — and it is in JSON, "
     "which the prose corpus did not read, saying `guards`, which the pattern did not match. Both "
     "blind spots at once, which is how 18c, 18d, 26a and 30a all survived",
     sub(J, "Evaluates GATE_B's exit guards ITSELF (edges 15/16/17)",
            "Evaluates GATE_B's exit guards ITSELF (guards 18/18c/18d)")),

    ("every-artifact-link-has-a-source",
     "the manifest names a source file that is not there — the link survives, the page becomes "
     "uneditable, and it goes on reading as current",
     sub(AM, "`docs/artifacts/index.html`", "`docs/artifacts/the-whole-thing.html`")),
    ("every-artifact-link-has-a-source",
     "a hosted link exists in a README and in no manifest row — exactly how two of them got here",
     sub(RM, "https://claude.ai/code/artifact/045a2e11-cade-45c0-9484-b2edf0db8903",
             "https://claude.ai/code/artifact/deadbeef-0000-4000-8000-000000000000")),

    ("reviewer-writes-evals-at-tiers-that-exist",
     "the reviewer routes findings to a tier that no longer exists — it writes nothing and reports "
     "confidently, which is the failure it exists to prevent, happening to itself",
     sub(RV, "`evals/walks/fixtures/`", "`evals/walk-fixtures/`")),
    ("reviewer-writes-evals-at-tiers-that-exist",
     "a whole tier drops out of the triage table — a defect of that shape has nowhere to become a test",
     sub(RV, "| a hook that fired wrongly, or did not fire | a case in the hook's self-test | "
             "`evals/hooks/` |\n", "")),
    ("reviewer-is-read-only-against-the-run",
     "the reviewer stops being read-only against the run it is reviewing",
     sub(RV, "- **Never write to the run.**", "- **Fix the run where you can.**")),
    ("reviewer-is-read-only-against-the-run",
     "nothing stops the reviewer re-implementing audit_run.py, so a run can get two verdicts",
     sub(RV, "- **Do not re-implement `audit_run.py`.**", "- **Check whatever you like.**")),

    ("trace-is-off-by-default-and-settled-once",
     "the schema stops saying absent means off — so an older run's tracing is undefined",
     sub(S, "**`false` when the flag is absent, and absent is `false`**", "settable at any time")),
    ("trace-is-off-by-default-and-settled-once",
     "INTAKE stops emitting `trace`, so nothing in the graph ever sets it",
     sub(N, "`trace` (from `--trace`; **`false` when absent**), ", "")),
    ("trace-is-off-by-default-and-settled-once",
     "`--trace` drops out of the argument hint — the flag exists and cannot be found",
     sub(K, 'argument-hint: "[start <feature> | resume | status] [--plan <path>] [--spec <path>] [--trace]"',
            'argument-hint: "[start <feature> | resume | status] [--plan <path>] [--spec <path>]"')),

    ("every-deterministic-suite-is-wired-into-run-all",
     "the JS harness drops out of the runner, exactly as it did for a release",
     sub(R, '("gate-a.harness.mjs", "gate-a.workflow.js under a real runtime', '("gate-a.SKIP.mjs", "x')),
    ("every-deterministic-suite-is-wired-into-run-all",
     "a Python suite drops out of the runner",
     sub(R, '    ("spec/spec_controls.py", [], "the spec checks can actually fail', '    ("x.py", [], "y')),
    ("journal-check-keeps-its-two-directions-apart",
     "the last gate row is deleted",
     sub(W, "| **R13** | **The journal and the bundle describe the same milestone.**",
            "| **R13x** | **The journal and the bundle describe the same milestone.**")),
]

# A control names the checker it expects to go red. Two so far: `spec_consistency.py`, which reads
# the spec files, and `run_scenario.py --self-test`, which reads the executing tier's own scenarios.
# The second was added when all eight briefs turned out to point at files `--setup` never creates —
# a `lane` -> `milestone` rename that rewrote `lane-1.script.json` into `milestone 1.script.json`.
# Every static suite was green throughout: nothing read a brief.
CHECKERS = {
    "spec": [f"{SK}/evals/spec/spec_consistency.py"],
    "runs": [f"{SK}/evals/runs/run_scenario.py", "--self-test"],
}

RUNS = f"{SK}/{paths.REL_DIRS['scenarios']}"

BRIEF_CONTROLS = [
    ("01-happy-milestone.md", "the rename that actually happened: `agent-` became `milestone `",
     sub(f"{RUNS}/01-happy-milestone.md",
         "{{SCRATCH}}/agent-1.script.json", "{{SCRATCH}}/milestone 1.script.json")),
    ("02-provisional-never-leaks.md", "a `--script` that simply does not exist",
     sub(f"{RUNS}/02-provisional-never-leaks.md",
         "{{SCRATCH}}/agent-1.script.json", "{{SCRATCH}}/nope-1.script.json")),
    ("03-bundle-hides-a-retry.md", "a space in an OUTPUT path, which nothing can existence-check",
     sub(f"{RUNS}/03-bundle-hides-a-retry.md",
         "{{SCRATCH}}/agent-1.bundle.json", "{{SCRATCH}}/agent 1.bundle.json")),
    ("07-a-real-agent-refuses-an-instruction.md",
     "the reply file drifts from the one read_artifacts() reads — the scenario would PASS having "
     "scored an empty string",
     sub(f"{RUNS}/07-a-real-agent-refuses-an-instruction.md",
         "{{SCRATCH}}/agent-reply.txt", "{{SCRATCH}}/the-reply.txt")),
]



# ======================================================================================
# The other 32. `spec_controls.py` used to say, in its own docstring: "SCOPE: the checks added or
# reshaped by the schema-5 change. The older checks predate this runner and are not covered here —
# that is a gap, and it is named rather than papered over." Naming a gap is not closing one, and the
# controlled sample had already found two dead checks and this session found four more. Every check
# now has one.
# ======================================================================================
AGENT_FILE = f"agents/{paths.MILESTONE_AGENT.name}"
G = AGENT_FILE
TWIN_T = f"{SK}/{paths.REL_DIRS['nodes']}/testing-standards-node.md"
TWIN_Q = f"{SK}/{paths.REL_DIRS['nodes']}/code-quality-pipeline-node.md"


def dup_eval_id(root):
    import json as _j
    p = root / J
    d = _j.loads(p.read_text())
    d["evals"][1]["id"] = d["evals"][0]["id"]
    p.write_text(_j.dumps(d, indent=2))


CONTROLS += [
    ("mermaid-routes-on-rerun-not-clean", "the diagram routes GATE_A on `clean` again",
     sub(N, "GATE_A --> GATE_B:", "GATE_A --> GATE_B: clean and")),
    ("context-fields-declared", "a node reads a context field no schema declares",
     sub(N, "| **inputs** | `plan_path`, `milestones[]`, `context` |",
            "| **inputs** | `plan_path`, `milestones[]`, `context`, `context.invented_field` |")),
    ("gate-a-bounds-are-separate-counters", "the dispatch counter loses its own key in nodes.md",
     sub(N, "GATE_A-dispatch", "GATE_A", -1)),
    ("node-ids-match-across-files", "a node contract is renamed out from under the transition table",
     sub(N, "### `MERGE`", "### `MERGE_NODE`")),
    ("commit-to-record-has-a-mechanical-check", "the commit-and-record invariant loses its name",
     sub(N, "commit-and-record", "commit then record", -1)),
    ("transitions-are-not-batched", "edges.md stops forbidding batched transitions",
     sub(E, "never two batched after the fact", "written promptly")),
    ("in-flight-is-one-list-written-before-the-spawn",
     "`base_sha` stops being required BEFORE the spawn",
     sub(S, "| `milestones[].base_sha`", "| `milestones[].base_sha_x`")),
    ("observation-has-one-author", "the orchestrator is allowed to rewrite an agent's observation",
     sub(S, "MUST NOT rewrite", "should avoid rewriting")),
    ("journal-is-telemetry-not-evidence", "the journal stops being declared non-evidence",
     sub(W, "telemetry, not evidence", "written as it goes")),
    ("journal-record-schema-is-complete", "the record schema drops `headline`",
     sub(W, '"headline"', '"summary"')),
    ("agent-writes-only-its-own-journal", "the one-writer-per-journal rule goes",
     sub(W, "**One file per milestone, append-only, and the agent is its only writer.**",
            "**One file per milestone.**")),
    ("delivered-answers-what-the-milestone-shipped", "`notes` goes back to optional",
     sub(W, "notes:    string(600)", "notes?:   string(600)")),
    ("provisional-fields-never-become-history", "the replay stops nulling `progress`",
     sub(K, "7. **Null `milestones[<id>].progress` and drop the id from `in_flight`**",
            "7. **Drop the id from `in_flight`**")),
    ("interrogation-is-questions-only", "the questions-only limit on asking an agent goes",
     sub(K, "Questions only", "Keep it brief")),
    ("root-reads-records-before-briefing-a-dependent-agent",
     "nothing requires reading a parent's record before spawning its dependent",
     sub(K, "- **Before spawning an agent whose milestone has `deps`** — read every parent's `delivered` and the",
            "- **Before spawning an agent** — brief it well, and the")),
    ("silence-is-diagnosed-not-waited-out", "waiting longer becomes an acceptable answer to silence",
     sub(K, "**Waiting longer is", "**A longer wait is")),
    ("agent-dispatch-has-its-own-counter", "a dead agent may spend the node budgets again",
     sub(S, "never against the node budgets", "and the node budgets")),
    ("agent-owns-execution-root-owns-guards", "a milestone-loop node stops naming the agent as owner",
     sub(N, "| **owner** | **milestone agent** \u2192 `plan-guidelines-node.md` \u00a7 `BRANCH`.",
            "| **owner** | inline.")),
    ("agent-bundle-fields-are-required-not-optional",
     "a missing bundle field stops reading as the worst value",
     sub(W, "read as the **worst** value", "interpreted sensibly")),
    ("agent-return-gate-has-one-source", "the return gate loses its single home",
     sub(W, "## The return gate", "## Checks on return")),
    ("agent-agent-states-what-it-may-not-do", "the agent is no longer told it may not open a PR",
     sub(AGENT_FILE, "Never open a PR", "Avoid opening a PR")),
    ("agent-itineraries-agree",
     "the two itinerary tables stop agreeing — the agent runs a shape nobody gated",
     sub(AGENT_FILE, "| `true` | `BRANCH \u2192 IMPLEMENT \u2192 TEST \u2192 GATE_A \u2192 E2E \u2192 GATE_B`, then return |",
                     "| `true` | `BRANCH \u2192 IMPLEMENT \u2192 TEST \u2192 GATE_A \u2192 GATE_B`, then return |")),
    ("agent-bundle-promised-equals-bundle-required",
     "the gate routes on a field the agent is never told to return",
     sub(AGENT_FILE, "attempt_counts", "attempts_spent", -1)),
    ("return-gate-is-complete", "a gate row is deleted, leaving a hole that reads as a check",
     sub(W, "| **R6** |", "| **R6x** |")),
    ("agent-loaded-twins-say-so", "an agent-loaded twin loses its agent preamble",
     sub(TWIN_T, "You are a milestone agent", "You are working on tests", -1)),
    ("behavioural-evals-are-well-formed", "two behavioural evals share an id", dup_eval_id),
    ("attempts-counting-is-defined", "edges.md stops saying whether attempts counts entries or retries",
     sub(E, "counts how many times the node has been ENTERED", "tracks the loop")),
    ("e2e-mandates-playwright-on-ui-milestones", "the e2e mandate loses its trigger",
     sub(TWIN_T, "touches_ui", "ui_flag", -1)),
    ("playwright-is-installed-not-ledgered", "nodes.md stops telling the reader to install it",
     lambda root: (sub(N, "install it", "obtain it somehow", -1)(root),
                   sub(N, "Install it", "Obtain it somehow", -1)(root))),
    ("containment-check-needs-no-path-exemption",
     "a path exemption comes back into R12 — a blanket hole around the directory holding every "
     "sibling's journal, and unnecessary now that the run directory is gitignored",
     sub(W, "**`git status --porcelain` empty** — a bare one, with no path exemption",
            "`git status --porcelain -- ':(exclude)docs/graph-runs'` **empty**")),
    ("containment-check-needs-no-path-exemption",
     "R12 stops demanding a clean tree at all — containment with nothing contained",
     sub(W, "**`git status --porcelain` empty** — a bare one, with no path exemption, because the "
            "run directory is gitignored; ", "")),
    ("ledger-records-without-forbidding-the-transition",
     "nodes.md stops saying a missing reviewer never halts the run",
     sub(N, "missing reviewer never halts the run", "missing reviewer is recorded")),
    ("r7-separates-no-dispatcher-from-a-dead-dispatch",
     "the bundle loses the discriminator R7 branches on",
     sub(W, "dispatch: 'workflow'|'mimic'|'direct'", "dispatch: string")),

    # --- the orchestrator's own half, which had no gate at all ----------------------------------
    ("the-orchestrator-gates-its-own-work-too",
     "the orchestrator's gate disappears, restoring the asymmetry where fourteen checks read the "
     "agent's work and nothing reads the orchestrator's",
     sub(K, "### 4b. The orchestrator's own gate", "### 4b. Notes")),
    ("the-orchestrator-gates-its-own-work-too",
     "O1 stops being the DEFAULT and becomes a reminder, which is what it was when a turn ended at "
     "a replay boundary",
     sub(K, "**the turn does not end**", "consider continuing")),
    ("the-orchestrator-gates-its-own-work-too",
     "`verified` loses its cap again — the one authored field no return gate ever sees",
     sub(S, "what it checked and what it found, **≤ 300 chars**",
             "what it checked and what it found")),
    ("the-orchestrator-gates-its-own-work-too",
     "the observation cap stops applying to the orchestrator, so only the agent is disciplined",
     sub(S, "**≤ 200 chars — and that applies to the ones YOU write too**", "one line")),

    # --- STRATEGY settling every field, and proving it ------------------------------------------
    ("strategy-settles-every-field-and-proves-it",
     "the settlement check goes away, so STRATEGY's seven fields are settled on trust and a resumed "
     "run inherits an answer that only ever existed in conversation",
     sub(N, "#### The settlement check", "#### Notes")),
    ("strategy-settles-every-field-and-proves-it",
     "the check stops requiring the state file to be read back, which is the whole difference "
     "between verifying and remembering",
     sub(N, "**Read the state file back and confirm all seven:**", "Confirm all seven:")),
    ("strategy-settles-every-field-and-proves-it",
     "a still-null field stops being BLOCKED, so the orchestrator may quietly default a decision it "
     "just promised never to infer",
     sub(N, "**A `null` in the first column is `BLOCKED`, naming the field",
            "**A `null` in the first column is fine, naming the field")),

    # --- the fallback that turned out to be the normal path -------------------------------------
    ("the-no-workflow-fallback-is-a-specified-mimic-not-a-free-hand",
     "the agent stops being told to try the real script first, so a session that GAINS the "
     "Workflow tool would mimic forever and never notice",
     sub(W, "**Try the script first, every time.**", "**Skip the script.**")),
    ("the-no-workflow-fallback-is-a-specified-mimic-not-a-free-hand",
     "grouping by directory goes away, so the mimic reviews files in whatever order it likes and "
     "the logical-module context the reviewer depends on is gone",
     sub(W, "1. **Group by directory.** Bucket the changed files by `dirname`.",
            "1. **Review the files.** In any convenient order.")),
    ("the-no-workflow-fallback-is-a-specified-mimic-not-a-free-hand",
     "the mimic may run its groups sequentially — behaviour preserved, the entire point of "
     "replicating the script thrown away",
     sub(W, "6. **Groups run CONCURRENTLY; the four steps within a group do not.**",
            "6. **Run the groups one after another.**")),
    ("the-no-workflow-fallback-is-a-specified-mimic-not-a-free-hand",
     "`mimic` stops promising REAL group counters, which makes it `direct` under another name and "
     "silently restores the coverage-arithmetic loss it exists to fix",
     sub(W, "Then report `dispatch: \"mimic\"` with **`run_id: null`** and **real**",
            "Then report `dispatch: \"mimic\"` with **`run_id: null`** and null")),
    ("the-no-workflow-fallback-is-a-specified-mimic-not-a-free-hand",
     "the node file stops naming the write-capable reviewer, so a mimic can use a read-only one "
     "for the two steps that must APPLY fixes",
     sub(f"{SK}/{paths.REL_DIRS['nodes']}/code-quality-pipeline-node.md",
         "(`pr-review-toolkit:code-reviewer`, write-capable)", "(a code reviewer)")),

    # --- the three judgement calls the real-agent run-evals recorded and did not resolve ---------
    ("implement-does-not-owe-the-steps-test-owns",
     "guard 9 goes back to owing every step in the milestone — the R1 halt, restored",
     sub(E, "| 9 | `IMPLEMENT` | `TEST` | every step this node owns is committed — a step whose "
            "deliverable is a test belongs to `TEST` and is owed at 10, never here | — |",
            "| 9 | `IMPLEMENT` | `TEST` | all milestone steps committed | — |")),
    ("implement-does-not-owe-the-steps-test-owns",
     "guard 10 stops collecting TEST's half, so a test step is owed at neither guard",
     sub(E, "| 10 | `TEST` | `GATE_A` | every step `TEST` owns is committed **and** unit",
            "| 10 | `TEST` | `GATE_A` | unit")),
    ("implement-does-not-owe-the-steps-test-owns",
     "the split stops being mechanical — the section survives with no test-file shape in it",
     sub(N, "a path matching `*.test.*` / `*.spec.*`, or one under `test/`, `tests/`, "
            "`__tests__/`, `e2e/`; or a step that says to write or update tests",
            "a test")),
    ("implement-does-not-owe-the-steps-test-owns",
     "the guard is 'fixed' by deleting the requirement that exposed it: PLAN stops owing test steps",
     sub(f"{SK}/{paths.REL_DIRS['nodes']}/plan-guidelines-node.md",
         "1. **Test steps** — per `testing-standards-node.md`.",
         "1. Test steps, when they are worth it — per `testing-standards-node.md`.")),

    ("implement-does-not-owe-the-steps-test-owns",
     "the executor is no longer told about the split, in the one file it reads before IMPLEMENT",
     sub(AGENT_FILE, "**`IMPLEMENT` and `TEST` split `steps[]` between them, and neither owes the "
                     "other's half.**", "**Commit everything as you go.**")),
    ("implement-does-not-owe-the-steps-test-owns",
     "the ownership table stops naming the guard each half is owed at — a discount, not a partition",
     sub(N, "| `TEST` | 10 |", "| `TEST` | its own exit |")),

    ("tests-has-a-legal-value-for-a-node-never-reached",
     "the two fields go back to two spellings for one fact",
     sub(W, "tests_state?: 'green'|'red'|'absent'|'not-run'", "tests_state?: 'green'|'red'|'absent'")),
    ("tests-has-a-legal-value-for-a-node-never-reached",
     "the enum loses the only value a milestone blocked before TEST can honestly report",
     sub(W, "tests: { unit: 'pass'|'fail'|'absent'|'not-run'", "tests: { unit: 'pass'|'fail'|'absent'")),
    ("tests-has-a-legal-value-for-a-node-never-reached",
     "R0 stops scoping `not-run` to a trace that never entered TEST — a free pass for a milestone "
     "that ran the suites and would rather not say what happened",
     sub(W, "may be `not-run` **only on a bundle whose trace never entered `TEST`**",
            "may be `not-run`")),
    ("tests-has-a-legal-value-for-a-node-never-reached",
     "the field is made optional instead — which lets a bundle that DID run the suites omit them",
     sub(W, "    tests: { unit:", "    tests?: { unit:")),

    ("an-undeclared-bundle-field-is-unread-and-named",
     "the rule for a field the schema does not declare is deleted again",
     sub(W, "#### An undeclared field is unread, not fatal",
            "#### Extra fields")),
    ("an-undeclared-bundle-field-is-unread-and-named",
     "the drop stops being recorded, so the run cannot say which contract its agent was on",
     sub(W, "and `history[].verified` for\n> that milestone names what was dropped.**",
            "and nothing is recorded.**")),
    ("an-undeclared-bundle-field-is-unread-and-named",
     "the losing reading stops being named, so a reader who arrives at it finds nothing saying no",
     sub(W, "| **Reject the bundle** |", "| **The other option** |")),
    ("an-undeclared-bundle-field-is-unread-and-named",
     "R0 stops saying what happens to a field it does not recognise — how three passed unseen",
     sub(W, "**Extra fields the schema does not declare are dropped unread and named in `verified`, "
            "never rejected**", "**Extra fields are handled below**")),

    # --- the three spec defects the first full behavioural run reported --------------------------
    ("a-dead-dispatch-is-never-charged-to-the-findings-budget",
     "the Unproven-gate row goes back to 'that node's own bound' with no exception — the reading "
     "that charges a zero-agent dispatch to the findings budget",
     sub(W, " — **except a `GATE_A` whose dispatch ran zero agents**, which is a dispatch failure "
            "and is charged to `attempts[\"GATE_A-dispatch:<id>\"]`, never to the findings budget "
            "(R7).", ".")),
    ("a-dead-dispatch-is-never-charged-to-the-findings-budget",
     "SKILL.md's one-line summary of the same table keeps the old reading — the row is fixed and "
     "the sentence a reader actually skims is not",
     sub(K, " — except a `GATE_A` whose\ndispatch ran zero agents, charged to "
            "`attempts[\"GATE_A-dispatch:<id>\"]` and never to the findings\nbudget.", ".")),
    ("a-dead-dispatch-is-never-charged-to-the-findings-budget",
     "the rendered artifact keeps the old reading — failure mode 13, the guard fixed in the spec "
     "and not in the surface that renders it",
     sub(HTML, ". <b>Except a <code>GATE_A</code> whose dispatch ran zero agents</b>: that is a "
               "dispatch failure and counts <code>GATE_A-dispatch:&lt;id&gt;</code>, never the "
               "findings budget", "")),
    ("a-dead-dispatch-is-never-charged-to-the-findings-budget",
     "the exception is over-corrected into the rule: every unproven gate takes the dispatch key, "
     "handing a gate that really ran a re-run allowance it never spent",
     sub(W, "Counts against **that node's own bound** — **except a `GATE_A`",
            "Counts against the dispatch bound — **except a `GATE_A`")),
    ("a-dead-dispatch-is-never-charged-to-the-findings-budget",
     "the exception loses the case it applies to, so a gate that ran and found a bug can claim it",
     sub(W, "**except a `GATE_A` whose dispatch ran zero agents**",
            "**except a `GATE_A` that is in doubt**")),

    ("the-has-ui-note-cites-the-guard-it-actually-means",
     "the note goes back to citing guard 14 — `E2E -> GATE_B`, not the exit it describes",
     sub(E, "exit (guard 13) matched", "exit (guard 14) matched")),
    ("the-has-ui-note-cites-the-guard-it-actually-means",
     "the `has_ui == false` exit moves to the other row and the note keeps citing 13 — the check "
     "must resolve the number from the table, not hardcode the answer",
     swap_gate_a_has_ui_predicates),

    ("agent-lost-says-whether-blocked-is-really-published",
     "the ambiguity comes back: the row assigns BLOCKED and never says whether it is published "
     "when the re-spawn follows in the same turn",
     sub(S, ", and **`BLOCKED` is written even when the re-spawn follows in the same turn** — the "
            "write and the clear are two separate writes, so an orchestrator that dies between "
            "diagnosing the death and spawning the replacement leaves a file that says what "
            "happened instead of a `RUNNING` file describing an agent that no longer exists", "")),
    ("agent-lost-says-whether-blocked-is-really-published",
     "half the resolution moves: the status flips to RUNNING while the row still says BLOCKED is "
     "written even when the re-spawn follows",
     sub(S, "| `BLOCKED` | on the re-spawn, which clears it",
            "| `RUNNING` | on the re-spawn, which clears it")),
    ("agent-lost-says-whether-blocked-is-really-published",
     "the walker goes back to admitting only `kind: 'blocked'` under BLOCKED, so the state the "
     "table prescribes is one no fixture may model",
     sub(GW, 'if state["status"] == "BLOCKED" and kind not in {"blocked", "agent_lost"}:',
             'if state["status"] == "BLOCKED" and kind != "blocked":')),

    # ── the per-subagent journal record ──────────────────────────────────────────────────────
    ("every-subagent-is-two-journal-lines-and-still-only-telemetry",
     "the section is gone entirely and a forty-agent Gate A reports as one node line again",
     sub(W, "### Every subagent you spawn gets two lines", "### Notes on subagents")),
    ("every-subagent-is-two-journal-lines-and-still-only-telemetry",
     "the two events vanish from the journal's event enum, so the one place a writer copies the "
     "shape from does not admit they exist",
     sub(W, "                                     //   | agent_spawn | agent_done  (§ below)\n", "")),
    ("every-subagent-is-two-journal-lines-and-still-only-telemetry",
     "the ordinal stops being assigned at spawn — pairing on arrival renders concurrent groups in "
     "completion order and still calls it the spawn order",
     sub(W, "**`n` is assigned at spawn and never reordered.**",
            "**`n` orders the list.**")),
    ("every-subagent-is-two-journal-lines-and-still-only-telemetry",
     "back-filling a `done` line is allowed again, which turns an agent that died silently into a "
     "list that looks complete",
     sub(W, "Never back-fill a `done` line for an agent that never returned.", "")),
    ("every-subagent-is-two-journal-lines-and-still-only-telemetry",
     "the `dispatch: \"workflow\"` case loses its instruction, so an agent that spawned nothing "
     "itself is left to invent per-agent lines for the script's agents",
     sub(W, "**Under `dispatch: \"workflow\"` you did not spawn them, so do not claim you did.**",
            "Under a real script the agents are the script's.")),
    ("every-subagent-is-two-journal-lines-and-still-only-telemetry",
     "three new free-text fields written into the repo lose the never-paste-output-or-secrets rule",
     sub(W, "**never paste command output, secrets or PII** into a\n  label, a purpose or a summary.",
            "keep labels short.")),
    ("every-subagent-is-two-journal-lines-and-still-only-telemetry",
     "the milestone agent is never told to write the lines, so the contract exists only in a file "
     "the writer of the journal does not read",
     sub(MA, "`agent_spawn` when you launch it", "a line when you launch it")),
    ("every-subagent-is-two-journal-lines-and-still-only-telemetry",
     "the journal stops declaring itself telemetry — a per-agent record is exactly the artefact "
     "that starts being cited as proof a gate ran",
     sub(W, "telemetry, not evidence", "the second record", -1)),

    # ── the unpublished plugin names, and the advisory that replaced the discovery gap ──────────
    ("no-unpublished-plugin-name-ships-in-this-plugin",
     "the IMPLEMENT owner row names an unpublished standards plugin again — the mention that read "
     "as a dependency, in the contract that dispatches it",
     sub(N, "**live dispatch** of the project's own installed coding-standards skill",
            "**live dispatch** `" + NAME_A + "`")),
    ("no-unpublished-plugin-name-ships-in-this-plugin",
     "a WALK FIXTURE's observation names one — the surface `published` never reached, and one of "
     "the two places the names actually survived the first sweep",
     sub(FX, "so no frontend standards skill is ever dispatched",
             "so " + NAME_B + " is never dispatched")),
    ("no-unpublished-plugin-name-ships-in-this-plugin",
     "the QA node's bring-up step names one as the way to start the stack — a node procedure, "
     "which `published` does reach but which no check had ever read for this",
     sub(QN, "(or whatever local-stack / deployment skill this project has installed)",
             "(or the `" + NAME_C + "` skill if installed)")),

    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "the skill is renamed on one side only, so SKILL.md's run start invokes a command that "
     "resolves to nothing",
     sub(K, "/sdlc-graph:onboarding", "/sdlc-graph:setup", -1)),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "the INTAKE contract stops naming it, so the roster is only ever discovered one ledger entry "
     "at a time — the gap the checklist exists to close",
     sub(N, "/sdlc-graph:onboarding", "/sdlc-graph:tools", -1)),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "the invocation is trimmed out of INTAKE's `action` row while the note beside it still "
     "explains the checklist — the section still names it, so every mention-scoped assertion "
     "stays green, and the row an orchestrator actually executes no longer invokes anything. "
     "This is the silent direction: the docs say every run, the graph runs it never",
     sub(N, " **Then invoke `/sdlc-graph:onboarding`** and relay its checklist — advisory, on "
            "every run, and neither waited on nor recorded.", "")),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "the INTAKE note drops the sentence saying the checklist installs nothing. It still runs every "
     "run and still reports missing tools — and nothing in the contract now stands between that "
     "report and an agent that decides to be helpful and install them",
     sub(N, "it installs nothing,\n> downloads nothing, enables nothing and changes no configuration.",
            "it reports what is missing.")),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "the hand-back goes: the note no longer says the decision belongs to the human, so a missing "
     "row reads as a task the graph should close rather than a choice it should present",
     sub(N, "**hands the decision\n> back to the human**", "moves on")),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "`disable-model-invocation: true` is copied over from the graph's own frontmatter — the "
     "checklist then reads as wired at INTAKE and can be invoked by nobody",
     sub(OB, "disable-model-invocation: false", "disable-model-invocation: true")),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "`Write` is added to the checklist's tool grant — the skill still says it writes nothing, and "
     "now nothing but that sentence stops a thing invoked on every run from leaving a report "
     "behind in every repository it runs in",
     sub(OB, "allowed-tools: Bash, Read", "allowed-tools: Bash, Read, Write")),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "the one-line-when-clean rule goes, so a run with nothing to act on still pays for the full "
     "table — the noise that gets a run-start checklist switched off",
     subs(OB, ("**When every row is invocable, say so in one line and stop**",
               "**Print the full list every time**"),
              ("**If every row is invocable, the whole output is one line**",
               "**Print every row, always**"))),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "`user-invocable` goes false — a human can no longer reach it outside a run",
     sub(OB, "user-invocable: true", "user-invocable: false")),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "the skill stops saying it installs nothing, and a report of missing tools starts reading as "
     "a promise to fetch them",
     sub(OB, "installs nothing", "installs little", -1)),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "INTAKE keeps invoking it every run and drops the sentence saying it cannot stop, block or "
     "delay one — 'runs every time' read as 'may stop the run', which is the seventh human stop",
     sub(N, "**It does not stop, block, delay or halt a run, and it is not a human stop.** ", "")),
    ("onboarding-runs-at-every-run-start-and-still-cannot-gate",
     "the note survives and INTAKE's `requires` row gains the skill — preflight then resolves it "
     "and a miss is ledgered, which is a gate, the one thing it may never become",
     sub(N, "| **requires** | `git` |", "| **requires** | `git`, the `onboarding` skill |")),

    ("onboarding-checklist-derives-from-the-dependency-doc",
     "a tool the graph dispatches by BARE name — `code-simplifier`, Gate A step 2 — is dropped "
     "from the roster. The qualified ids still all resolve, so a check that only reads "
     "`plugin:skill` stays green while the doc quietly stops covering a third of the dispatch "
     "targets, and the checklist derived from it stops asking about them",
     sub(DEP, "code-simplifier", "code-simplifer-typo", -1)),
    ("onboarding-checklist-derives-from-the-dependency-doc",
     "the skill re-grows a roster row the doc already owns — two copies of one list, and the one a "
     "human opens is the doc",
     sub(OB, "| Source | What it settles |",
             "| `code-simplifier` | Gate A step 2 |\n| Source | What it settles |")),
    ("onboarding-checklist-derives-from-the-dependency-doc",
     "the skill lists a tool no row of the doc has — the two disagree, in the direction where the "
     "checklist reports on something the roster has never heard of",
     sub(OB, "| Source | What it settles |",
             "| `some-other:reviewer` | Gate A step 9 |\n| Source | What it settles |")),
    ("onboarding-checklist-derives-from-the-dependency-doc",
     "an install line moves into the skill, where it can drift from the roster's",
     sub(OB, "```bash\nclaude plugin list --json",
             "```bash\n/plugin install code-simplifier@claude-plugins-official\nclaude plugin list --json")),
    ("onboarding-checklist-derives-from-the-dependency-doc",
     "the skill stops naming the doc, so whatever it reports is a list of its own",
     sub(OB, "docs/DEPENDENCIES.md", "the dependency notes", -1)),
    ("onboarding-checklist-derives-from-the-dependency-doc",
     "a roster row loses the column the whole file exists for — what a run does without that tool",
     sub(DEP, "| The simplification pass is ledgered. |", "|  |")),
    ("onboarding-checklist-derives-from-the-dependency-doc",
     "a tool the node contracts dispatch is dropped from the roster entirely — the reverse "
     "direction: present in the graph, absent from the file a human reads",
     sub(DEP, "`claude-md-management:claude-md-improver`", "`the CLAUDE.md improver`", -1)),
    ("onboarding-checklist-derives-from-the-dependency-doc",
     "the roster section is renamed, so the parser reads an empty table and every row-level check "
     "in here goes quiet — a glob that matches nothing, arriving through a heading",
     sub(DEP, "## The roster", "## Tools")),

]


ALL = ([("spec", cid, what, fn) for cid, what, fn in CONTROLS]
       + [("runs", cid, what, fn) for cid, what, fn in BRIEF_CONTROLS])


def main():
    failures = []
    for checker, expect, what, mutate in ALL:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "sdlc-graph"
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
                "__pycache__", ".scratch", "journals", "history", ".audit-*", "*.tmp"),
                dirs_exist_ok=False)
            # The ignore list is not tidiness. `copytree` walks the tree and then opens what it
            # found; a sibling suite creating or deleting a scratch directory in that window
            # raises FileNotFoundError and takes this whole runner down with a traceback that
            # looks nothing like the concurrency it actually is. Everything named here is a
            # transient another suite owns.
            mutate(root)
            script, *argv = CHECKERS[checker]
            run = subprocess.run([sys.executable, str(root / script), *argv],
                                 capture_output=True, text=True, cwd=root)
            fired = re.search(rf"^FAIL\s+{re.escape(expect)}\b", run.stdout, re.M)
            print(("ok   " if fired else "DEAD ") + f"[{checker}] {expect}  <-  {what}")
            if not fired:
                failures.append((expect, what, run.stdout[-400:]))
    print(f"\n{len(ALL) - len(failures)}/{len(ALL)} controls fired")
    for c, w, out in failures:
        print(f"\nDEAD {c} — {w}\n{out}")
    return 1 if failures else 0

sys.exit(main())
