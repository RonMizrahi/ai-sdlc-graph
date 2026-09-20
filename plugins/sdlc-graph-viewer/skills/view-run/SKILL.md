---
name: view-run
description: >-
  Generate a visual, LangSmith-style HTML view of an sdlc-graph run from its state file
  (docs/graph-runs/<run-id>/state.json) — the graph with the current node highlighted, next-step guards,
  the transition trace, milestones, retry counters vs bounds, and the skipped-gate ledger. Produces
  a self-contained snapshot HTML (openable and shareable anywhere). One invocation, no arguments:
  it works on the current directory, and asks which subproject when more than one has runs. Use this
  skill WHENEVER the user wants to SEE a graph run — "show me the run", "where is the graph now",
  "visualize the state", "open the run viewer", "what's the current state of the sdlc run",
  "generate the run report page" — or asks to watch a run live.
allowed-tools: Read, Write, Bash, Glob
disable-model-invocation: false
---

# View Run

## Goal

Turn `docs/graph-runs/<run-id>/state.json` into something a human can *look at*: the run's position on
the graph, what can fire next and why, the full trace, and the ledger — without reading JSON.

## Use When

- The user wants to **see** a run rather than read its JSON — *"show me the run"*, *"where is the
  graph now"*, *"visualize the state"*, *"open the run viewer"*, *"what's the current state"*.
- They ask to **watch** a run as it happens, or for a page they can leave open.
- **`sdlc-graph` triggers this at run start** when the plugin is installed — that is the common case,
  and it expects the printed summary relayed verbatim.
- They want a **shareable snapshot** of a finished run to attach to a review or a report.

## Do Not Use When

- **Nothing has run yet.** No `docs/graph-runs/*/state.json` means there is nothing to render; say so
  rather than producing an empty page.
- **The question is "is this run sound?"** — that is the graph's own eval suite and the trail in
  `history[]`. This skill renders what the file says; it does not judge it.
- **Something needs changing.** This skill is read-only with respect to the run, always.

## Inputs

**None.** One invocation, always scoped to **the current working directory**. Everything else is
discovered — or asked.

## Workflow

### 1. Discover runs under the current directory

```bash
find . -maxdepth 6 -path '*/docs/graph-runs/*/state.json' \
  -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/.worktrees/*' 2>/dev/null
```

Group the hits by **project directory** — the path prefix before `/docs/graph-runs/`.

- **No hits** → say so and stop. **Do not invent a state file** — a run that never started has
  nothing to view.
- **One project** → proceed with it.
- **More than one project** (a monorepo, nested test repos) → **ask the user which directory**,
  listing each project dir with its newest run id and that run's `status` so the choice is
  informed. Never pick a subproject silently — the newest file across projects is exactly how the
  wrong project's run gets rendered.

Within the chosen project, use the **newest** `docs/graph-runs/*/state.json` — and *say which one* so a stale pick
is visible. If the user's message named a specific run, prefer that match over newest.

### 2. Sanity-check it, honestly

Read the JSON. If it fails to parse, report the parse error and stop. If `schema_version` is absent
or not `5`, still generate — the viewer shows what it can, and an older file degrades to blank
fields rather than wrong ones — but **say which version the file was written against**, and say it
first. The graph itself is stricter: a mismatch there is an unconditional halt with no migration
path, so a viewer quietly rendering a stale file is showing a run the graph would refuse to resume.

### 3. Generate the snapshot

The template is `${CLAUDE_PLUGIN_ROOT}/skills/view-run/viewer/run-viewer.html`. It contains an injection slot:

```js
const INLINE=/*__STATE__*/null/*__END__*/
```

Replace the `null` between the markers with the state JSON, and write the result **next to the
state file** as `docs/graph-runs/<run-id>/view.html`:

All paths below are **relative to the chosen project directory** from step 1 — in a monorepo the
state file lives under the subproject, and the snapshot belongs beside it:

```bash
python3 - "${CLAUDE_PLUGIN_ROOT}/skills/view-run/viewer/run-viewer.html" \
  "<project>/docs/graph-runs/<run-id>/state.json" "<project>/docs/graph-runs/<run-id>/view.html" <<'PY'
import sys, json
tpl, state, out = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(tpl).read()
data = json.dumps(json.load(open(state)))          # parse first: invalid JSON must fail HERE
# The slot is inside a <script> block, and HTML ends that block at the first literal `</script>`
# ANYWHERE — inside a JS string included. json.dumps escapes neither `<` nor `/`, so an observation
# reading `fixed the parser </script><img src=x onerror=…>` used to truncate the script, kill boot(),
# and execute the rest as markup. These three escapes are legal inside a JS string literal and
# JSON.parse back to the identical characters, so the snapshot is unchanged and can no longer close
# its own tag. Run data is data: it reaches the DOM through esc(), never as markup.
data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
marker_a, marker_b = "/*__STATE__*/", "/*__END__*/"
i, j = s.index(marker_a) + len(marker_a), s.index(marker_b)
open(out, "w").write(s[:i] + data + s[j:])
print("wrote", out)
PY
```

The snapshot is **fully self-contained** — no server, no polling, works from `file://`, safe to
attach or archive. Its stall banner is disabled (a snapshot is a moment, not a feed), and its
sidebar shows exactly one run, the one baked in. Both are expected, not defects.

### 4. Deliver it

- Send the generated file to the user (rendered, not as a download card, when the client supports it).
- On macOS, also offer: `open docs/graph-runs/<run-id>/view.html`.

### 5. Live mode — the default when a server can run

**Live is preferred; the snapshot is the fallback and the archive format.** Check whether this
project's viewer server is already up (sdlc-graph starts one per project at run start when this
plugin is installed). If not, start the **bundled server — ~120 lines, zero dependencies, shipped
in this plugin**:

**First, ensure the env file — the configuration must be explicit on disk, never implicit.**

1. **No `sdlc-graph-viewer.env` in the project root** → create it from the example, **filled in**:

   ```bash
   # <project>/sdlc-graph-viewer.env — written by view-run, resolved values, no placeholders
   PROJECT_DIR=<absolute project path>
   RUNS_DIR=<absolute path to the run directories>   # usually $PROJECT_DIR/docs/graph-runs
   POLL_MS=1000
   HOST=127.0.0.1
   # PORT unset on purpose -> stable per-project derived port
   ```

   Defaults are fine — the point is that **every value the server will use is written down**, so
   any agent (or human) can read one file and know exactly what is configured. Nothing secret goes
   in it; committing it is safe.

2. **File already exists** → read it and **verify `PROJECT_DIR` points at this project**. It does →
   use it untouched (the user's `PORT`/`POLL_MS` choices stand). It points elsewhere → say so, and
   start with an inline `PROJECT_DIR=<this project>` override (env beats file) rather than silently
   rewriting the user's file.

Then start the server from the project root — it auto-loads `./sdlc-graph-viewer.env`:

```bash
cd "<project>" && node "${CLAUDE_PLUGIN_ROOT}/skills/view-run/server/server.mjs" &
```

**Configuration is a native `.env` file — nothing is ever edited in code.** The server loads
`$SDLC_GRAPH_VIEWER_ENV`, else `./sdlc-graph-viewer.env` if present, via Node's own `process.loadEnvFile` —
so real environment variables always beat the file (env > file > default):

```bash
# sdlc-graph-viewer.env
PROJECT_DIR=/abs/path/to/project     # where the project lives (default: cwd)
RUNS_DIR=/abs/path/to/docs/graph-runs      # where the run DIRECTORIES live (default: $PROJECT_DIR/docs/graph-runs)
PORT=8477                            # fixed port (default: stable derived per-project port)
POLL_MS=500                          # page poll interval (default: 1000)
HOST=127.0.0.1                       # bind address (default: localhost only)
VIEWER_HTML=/abs/path.html           # viewer page (default: the bundled viewer/run-viewer.html)
PORT_BASE=8400  PORT_RANGE=400  PORT_RETRIES=20   # derived-port parameters
```

**Every setting the server uses comes from the environment** — the code holds only the defaults
above; no path, suffix, or address is assumed anywhere else.

The pages read `POLL_MS` from `GET /api/config` at load — with a 1000ms fallback, so snapshot and
drag-drop modes stay fully serverless. The printed summary names which env file (or `defaults +
env`) is in force.

**The env file is the contract between agent and server.** The skill fills it at spawn (step
above) precisely so nothing about the running server is implicit: what an agent must provide to
have the HTML + server running is exactly that file's contents, and reading it back is how anyone
verifies the configuration. Later user requests ("set the port to 9000") edit the same file —
copy-and-fill from `server/sdlc-graph-viewer.env.example` for any variable not yet present, never
hand-written from memory.

It prints the summary — project, **its own per-project port**, home, live-view and API URLs, and
which config is in force. **Relay it as a complete block, never partially** — every one of these
lines, every time a server is started or found already running:

```
● sdlc-graph-viewer — <project>
  port        <port>
  home        http://localhost:<port>/            (the run list is the app's own sidebar)
  live view   http://localhost:<port>/view?state=/api/runs/<run-id>/state
  runs api    http://localhost:<port>/api/runs
  config      <path to sdlc-graph-viewer.env in force> · or: defaults (no env file — example at
              ${CLAUDE_PLUGIN_ROOT}/skills/view-run/server/sdlc-graph-viewer.env.example)
  viewer      <path to the run-viewer.html being served>
  stop        kill <pid>
```

A summary missing the port, a URL, or the config location is an incomplete delivery of this skill.

> **If the server prints `cannot read the viewer page` and exits, that is the whole diagnosis** —
> `VIEWER_HTML` (or the bundled default) does not resolve to a readable file. It fails at spawn on
> purpose: a server whose only page is missing used to bind its port anyway and answer `404 not
> found` on `/` and `/view` while every `/api/*` route worked, which reads as a bad URL rather than
> a broken install and sends people hunting the wrong thing. The page polls the state JSON every **1s, forever — even after `DONE`**.
**One server per project, never shared**; a second project gets a second server on its own port.
**Tell the user what is running and how to stop it** whenever you started a server.

## Output Contract

- `docs/graph-runs/<run-id>/view.html` — a self-contained snapshot of the named run, delivered to the user.
- Live mode: the **complete summary block** — project, port, all three URLs, the config file in force (or "defaults" plus where the example lives), and how to stop the server. All of it, every time.
- Any anomaly seen while generating (parse error, missing `schema_version`, `RUNNING` with a quiet
  file) **stated, not smoothed over**.

## Validation

Before telling the user it is done:

- **The page opens standalone, and that is now a command, not a squint:**
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/view-run/evals/sync/graph_sync.py` — its
  `page-loads-nothing-external` check looks for markup or code that FETCHES at load time
  (`<script src>`, `<link href>`, `@import`, an absolute-URL `fetch`). **Do not "simplify" it to a
  grep for `http`** — a run's own `qa_env.api_base_url` is legitimately `http://localhost:3000`, and
  that grep fails on real state data while catching nothing a snapshot actually loads.
- **The rendered node matches the file — with one deliberate exception.** `state.node` (or `status`
  at a terminal) is what the header and the **run facts** panel show, always. The **board** may
  differ: with several milestones in flight it highlights the **least advanced** one, because a run is
  only as far along as its slowest milestone agent, and the now-card says so in as many words ("least advanced
  of N milestones"). Board ≠ `state.node` **without** that line is a real defect; with it, it is the
  point. If header and file disagree, the injection went wrong and every other panel is suspect.
- **The counters show budget, not just count** — `attempts["TEST:2"] 1/3`, never a bare `1`. A number
  with no bound beside it is the decorative-bound failure one layer out.
- **Display names are everywhere or nowhere, and never in a key** —
  `python3 …/evals/viewer/node_labels.py`. A node's ID is schema (`state.node`, both endpoints of
  every `history[]` entry, the `attempts["GATE_B:<id>"]` keys); `NODE_LABEL` is the name a human
  reads, and `GATE_B` renders as **`ms-final-review`** — the milestone's final review, as opposed to
  `PR_FINAL_REVIEW` on the open PR. Two failure modes, opposite directions: a surface that misses the
  label reads as a *different node* to anyone comparing panels, and a label that reaches a lookup
  (`data-node`, `A.selNode`, any `GRAPH.*[id]`) matches nothing and **throws nothing** — the board
  just highlights empty. The checker counts label sites per renderer rather than testing presence,
  because a five-site panel that keeps one is exactly the half-fixed surface this repo keeps
  producing. **`run facts` stays raw on purpose**: it is the panel that says what the file says.
- **The dimmed next-step buttons still mean what the guard beside them says** —
  `python3 …/evals/viewer/guard_predicates.py`. `APPLIES` is the other thing the viewer owns
  outside the `__GRAPH__` markers, and it is the one the generator therefore never corrected: it
  kept the edge ids of the graph this viewer was forked from, so seven keys named edges that no
  longer existed and `'2'` and `'13'` dimmed the exact **inverse** of their own guard. A reading
  aid that lies is worse than none — it says "this run cannot go there" about a run that can — and
  it stays invisible, because a wrong predicate and a missing one both just draw a button a
  slightly different grey. The checker reads each guard cell out of `GRAPH.EDGES`, runs the real
  predicate under node, and fails when they disagree; a guard whose cell it cannot parse must be
  declared in `UNCHECKED` with a reason.
- **A liveness claim is only ever made in live mode, and only from a real clock.** The milestone agent line may
  say a milestone agent has gone silent **only** when the page is polling — not in a snapshot, not on a
  dropped file, not on a `paused` run, and not on one that is no longer `RUNNING`. `Date.now()` in a
  snapshot is the *viewing* time, so an unguarded marker reports every milestone agent in a shared snapshot dead
  minutes after capture; the stall banner has always been guarded this way and the milestone agent line must
  match it. Two more rules learned the same way: `seen_at` advances at **node boundaries only** — the
  orchestrator's monitor filters heartbeats out — so judge against the journal's own last timestamp
  where the server can supply it, and use a window measured in *tens of minutes* where it cannot, or
  a healthy seven-minute `GATE_A` reads as a corpse. And an absent or unparseable timestamp is
  **unknown, never fresh**: `NaN > threshold` is false, so the input that most suggests a milestone agent died
  mid-write is exactly the one that renders healthiest.
- **The ledger is visible without scrolling past the happy path.** A run with a non-empty
  `skipped_gates[]` is not a clean run, and the page must not read as though it were.
- **Live mode: fetch `/api/runs` and the state endpoint once** and confirm both answer. A summary
  naming a port nothing is listening on is worse than no summary.
- **The guard list still matches the graph** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/view-run/evals/sync/graph_sync.py`.
  **A non-zero exit is a stale viewer, not a warning.** The graph's own eval suite cannot reach this
  plugin (a plugin may not read above its own root), so this checker reads in the other direction —
  edge ids and endpoints, the node set, the bounds, the six stops, and whether each guard still
  tests the same fields. It prints `skip` and exits 0 when `sdlc-graph` is not installed.
- **A snapshot survives its own run data** —
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/view-run/evals/safety/snapshot_safety.py`. **Run this after any
  edit to the injector above or to the slot's surroundings.** Snapshot mode is the one place run data
  is inlined into the page's *source* rather than rendered through `esc()`, so a closing script tag
  in an observation ends the block, `boot()` never runs, and the rest of the run is handed to the
  HTML parser as markup — a blank page that also executes. The checker builds a snapshot using **the
  injector extracted from this file**, not a copy of it, so the documented command and the checked
  one cannot drift apart.
- **Both checkers can still fail** — `python3 …/evals/sync/graph_sync_selftest.py` breaks the viewer and
  the spec one way at a time and asserts the drift checker goes red for each. It exists because
  `graph_sync.py` shipped with a guard extractor that read the guard cell *after* its backticks had
  been stripped: it matched nothing at all, left 26 of the 42 guards compared against an empty set,
  and printed `ok` the whole time. A checker nobody checks is the recurring shape here.

## Guardrails

- **Read-only with respect to the run.** Never write to `docs/graph-runs/<run-id>/state.json` — the orchestrator is
  the single writer, and this skill racing it would corrupt the one durable record.
- Never regenerate the template's graph data by hand — copy `run-viewer.html` as-is and inject only
  the state. The embedded graph lives between `/*__GRAPH_BEGIN__*/` and
  `/*__GRAPH_END__*/` and is **data only**, which is what makes `graph_sync.py` able to parse it at
  all. Any hand-edit inside those markers — and any function put in there — must be followed by
  running the checker.
- The snapshot may contain the run's file paths and branch names — fine for the repo, but do not
  publish it outside the repo (artifact, gist) unless the user asks.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/view-run/viewer/run-viewer.html` — the template (demo mode when opened
  directly). **The one viewer copy in this plugin** — the bundled site serves this same file.
- `${CLAUDE_PLUGIN_ROOT}/skills/view-run/server/sdlc-graph-viewer.env.example` — the annotated config
  template; copy to `sdlc-graph-viewer.env` beside wherever the server is started.
- `${CLAUDE_PLUGIN_ROOT}/skills/view-run/server/server.mjs` — the server: plain `node:http`, zero
  dependencies, no build. Serves `/` **and** `/view` (both the viewer — its sidebar is the run
  list), `/api/runs`, `/api/runs/<id>/state`, `/api/runs/<id>/progress` — everything `no-store`.
  Per-project port derived from the project path. **`/progress`** returns the tail of each milestone's
  journal: a torn last line is the normal case there (append-only, read while being written), so it
  is counted as `unreadable` rather than allowed to blank a live milestone agent.
- `${CLAUDE_PLUGIN_ROOT}/skills/view-run/fixtures/` — ten state files for checking this
  page by hand: three parallel inflight, a `BLOCKED` halt, a 40-transition run paused at `MERGE`, a
  strategy-D park, a pre-plan empty run, one deliberately corrupt file, `parallel-live-*` (three milestones
  mid-flight, one of them deliberately silent for hours), and
  `hostile-run-data-*` — every field markup- or instruction-shaped, because run data is DATA and
  the tags must render as visible text. **Not shipped inside a snapshot** — they are a test
  corpus, and drag-and-drop is how you open one.
- `${CLAUDE_PLUGIN_ROOT}/skills/view-run/evals/` — `run_all.py` runs the seven deterministic
  suites: `graph_sync.py` (the drift checker), `graph_sync_selftest.py` (proves it can go red),
  `snapshot_safety.py` (a snapshot of hostile run data is inert), `server_boot.py`,
  `viewer/agent_panel.py`, `viewer/node_labels.py` (display names), and
  `viewer/guard_predicates.py`. Described under *Validation*.
  The one WRITER, `sync/sync_graph.py --write`, regenerates the `GRAPH` block from the spec —
  which is why anything the viewer owns rather than copies (`NODE_LABEL`, the `APPLIES` guard
  predicates) is deliberately outside `/*__GRAPH_BEGIN__*/…/*__GRAPH_END__*/`. **That is also the
  hole `guard_predicates.py` closes:** the generator does not reach `APPLIES`, so it kept the edge
  ids of the graph this viewer was forked from — seven keys naming edges that no longer existed,
  and two predicates that dimmed the exact inverse of their own guard.
- `graph/state.md` in the **sdlc-graph plugin** — the schema this viewer renders
  (`schema_version 5`: `in_flight` names the milestones with a live agent, `milestones[].progress`
  is what each one claims, and `stopped.kind` is why a run is not moving).
