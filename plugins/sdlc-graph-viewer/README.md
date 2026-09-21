# SDLC Graph Viewer

> **1.0.0 was a rewrite, not an update**: one zero-dependency page that renders **parallel
> milestone lanes**, reading the run-directory layout `docs/graph-runs/<run-id>/{state.json,journals/}`.
> Up to 0.1.4 it read the flat `docs/sdlc/<run-id>-state.json` at `schema_version 2`, and **it cannot
> render one** — the schema check is a hard stop, matching the graph's.

Live and snapshot HTML views of [`sdlc-graph`](../sdlc-graph) runs. **`sdlc-graph` declares this
plugin as a dependency**, so it installs and enables with the graph rather than being chosen — the
graph triggers it at run start. It remains a companion at run time: it renders a run, it never
gates one.

## What you get

| | |
|---|---|
| **Live view** | The graph with the current node pulsing, the outgoing guards from that node as next-step candidates (inapplicable ones dimmed *with the reason*), the transition trace with observations, milestones, retry counters against their bounds, and the skipped-gate ledger. |
| **Snapshot** | The same page with the state baked in — self-contained, opens from `file://`, safe to archive beside the plan. |
| **Banners** | `BLOCKED` with the guards tested · `paused` as a *declared* wait · and a possible-stall warning on the signature of an invented stop (`RUNNING` + quiet file + `paused: null`). |

## How it runs

**One server per project. Never shared.** Each project gets its own instance on a stable port
derived from the project path — same project, same port, every time. The server is
`skills/view-run/server/server.mjs`: plain `node:http`, **zero dependencies, no build step**.

```bash
cd <project> && node .../skills/view-run/server/server.mjs
```

It auto-loads `./sdlc-graph-viewer.env` (see `sdlc-graph-viewer.env.example` for every setting —
`PROJECT_DIR`, `RUNS_DIR`, `PORT`, `POLL_MS`, `HOST`, and the rest; `SDLC_DIR` is still honoured
as an alias for `RUNS_DIR`, so an env file written for 0.1.4 keeps working). **Every value the
server uses comes from the environment**; the code holds defaults only. Real environment variables beat the
file. Bound to `127.0.0.1` by default — run state is not LAN reading.

## How it updates

**Polling, not events — deliberately.** The graph writes the state file *before every transition*,
so a plain poll is guaranteed to see every step; there is no channel to subscribe to and none is
needed. The page polls every `POLL_MS` (default 1000) **forever — even after `DONE`**, because a
finished run can still gain a resumed transition.

## The one-copy rule

`viewer/run-viewer.html` is the **only** renderer — the server serves that same file, and snapshots
are generated from it. It mirrors `schema_version 5` of the graph's run state. Never hand-edit a
generated copy; change the template.

## Skill

`sdlc-graph-viewer:view-run` — no arguments, scoped to the current directory. It discovers runs,
**asks which subproject** when several have them, ensures the env file is filled, starts the server,
and relays the complete summary: port, URLs, config file in force, and how to stop it.

## How this is tested

Eight deterministic checkers live in `skills/view-run/evals/`, and `evals/run_all.py` runs them
all — `graph_sync.py` (this page's copy of the transition table against the graph's),
`graph_sync_selftest.py` (proves that checker can go red), `snapshot_safety.py` (proves a snapshot of
hostile run data is inert, using the injector extracted from `SKILL.md` rather than a copy of it),
`server_boot.py` (the server actually serves its page over HTTP), `viewer/agent_panel.py` (the
subagent fan-out), `viewer/node_labels.py` (every surface shows a node's display name, and every
lookup still keys on its id), `viewer/milestone_status.py` (a running milestone never reads NOT
STARTED), and `viewer/guard_predicates.py` (the predicates that dim next-step buttons name live
edges, and agree with the guards they claim to read).

They exist because **the graph's own eval suite cannot reach this plugin** — a plugin may not read
above its own root — so this is the one copy of the spec that has to check itself, in the only legal
direction. The wider picture, and the two testing methods, live with the graph itself — `sdlc-graph/docs/TESTING.md`, or its published form,
**[the whole plugin on one page](https://claude.ai/code/artifact/045a2e11-cade-45c0-9484-b2edf0db8903)**
→ the **Testing** view.
*(Named, not linked by path: a plugin may not reference files outside its own root. That artifact
belongs to `sdlc-graph` and is republished from there — linking a sibling's page is fine,
republishing it is not.)*

```bash
cd skills/view-run
python3 evals/run_all.py                     # all seven, ~3s
python3 evals/sync/sync_graph.py --write     # the one WRITER — regenerate GRAPH from the spec
```

> `sync_graph.py --write` rewrites everything between `/*__GRAPH_BEGIN__*/` and `/*__GRAPH_END__*/`
> from the graph spec. Anything the viewer owns rather than copies — the `NODE_LABEL` display-name
> map, the guard predicates in `APPLIES` — lives **outside** those markers for that reason, and
> `node_labels.py` fails if the map ever drifts back inside. Being outside the markers is also
> where `APPLIES` went wrong: the generator never corrected it, so it kept the edge ids of the
> graph this viewer was forked from. `guard_predicates.py` is the checker that direction needed.
