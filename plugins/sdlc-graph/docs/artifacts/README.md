# Published artifacts — what is hosted, and what file it came from

A hosted page nobody can edit is worse than no page: it reads as current, it is what people
actually open, and it cannot be corrected. This plugin has been on both sides of that: it once
published three separate pages, two of which described the graph as it was before the milestone
loop moved into an agent, and neither could be corrected without re-authoring the source they no
longer matched.

So every `claude.ai/code/artifact/...` link in this plugin has a row here, and
`every-artifact-link-has-a-source` in `evals/spec/spec_consistency.py` fails on one that does not.

| Artifact | Source | What it is |
|---|---|---|
| `045a2e11-cade-45c0-9484-b2edf0db8903` | `docs/artifacts/index.html` | The whole plugin on one page — Run · Graph · Nodes · Delegation · Files & state · Testing. |

## Linked from here, owned elsewhere

A README naming a sibling plugin is normal; **republishing a sibling's artifact is not**. These
rows exist so the link is accounted for without this plugin claiming it.

| Artifact | Owner | What it is |
|---|---|---|
| `de145d90-62da-4778-a84f-7049ef11f3a6` | Owned by `sdlc-graph-viewer`, whose own `docs/artifacts/README.md` names its source | The run viewer, rendering its built-in demo run. |

## Retired

Three pages predate 1.0.0 and did not survive it. **All three are still
hosted**, and there is no way to take one down — which is exactly why they are written here rather
than forgotten. Anyone who opens one is reading the pre-agent graph: 19 nodes, a live monitor, a
flat `docs/sdlc/<run-id>-state.json`, and edge ids that no longer exist.

| Artifact | Why |
|---|---|
| `83c98af5-c8dd-4d63-b1cc-67d6d7ed9de5` | *"Schematic"* — the spine, the milestone loop, the node catalog and the nine bounds. **Superseded by `index.html` → Graph/Nodes**, which is generated from the same spec the suite checks. Its source, `docs/schematic.html`, was deleted rather than carried forward as a second hand-maintained drawing of a 30-row table. |
| `557c2bb0-a03f-4073-8e80-77e7752cff04` | *"Topologies"* — the four branching strategies, interactive. **Superseded with no direct replacement**: `index.html` → Graph covers strategies A–D as prose and the run viewer draws the parallel lanes live. Re-authoring the interactive explorer against the new table is real work nobody has asked for; saying so is better than shipping a page that quietly describes the old one. |
| `8da5f926-1110-46d0-82b4-264e9c7153c3` | *"How the graph is tested"* — superseded, and it never had a source. Everything it said now lives in `index.html` → **Testing**, which does have one. |

## Republishing

**Edit the source, then republish it to the same URL.** Passing the existing `url` is what keeps the
link alive — publishing without it mints a new one and the README then points at a page nobody
updates.

**Never republish another plugin's artifact.** The viewer's demo belongs to `sdlc-graph-viewer` and
is republished from there; this plugin's README may *link* it, which is fine — a README naming a
sibling plugin is normal.
