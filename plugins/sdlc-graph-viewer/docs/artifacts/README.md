# Published artifacts — what is hosted, and what file it came from

Every `claude.ai/code/artifact/...` link in this plugin has a row here. The graph plugin's
`every-artifact-link-has-a-source` check enforces the same rule on its side; this file is the
viewer's half of it, and the reason it exists is that this plugin published a demo for four
releases with **no `docs/` directory at all** — the link was in the graph's README, the page was
generated from a viewer nobody could identify, and there was nowhere to say which file produced
it.

| Artifact | Source | What it is |
|---|---|---|
| `de145d90-62da-4778-a84f-7049ef11f3a6` | `skills/view-run/viewer/run-viewer.html` | The run viewer, opened with no state — it renders its own built-in demo run. |

> **The source is the viewer itself, not a copy of it.** `run-viewer.html` falls back to a demo run
> when it is given no state file, so the shipped page and the hosted demo are the same artifact. A
> separate `demo.html` would be a second copy of a 1,400-line file, drifting from the first, to
> publish something the first already does.

## Linked from here, owned elsewhere

The README points at the graph plugin's page for the wider testing story. That link is accounted
for here so this plugin is not silently claiming it — and because a rename nearly shipped it
wrong once: a README carried over a link to the page of the plugin it was renamed from, and a
rename does not touch a UUID.

| Artifact | Owner | What it is |
|---|---|---|
| `045a2e11-cade-45c0-9484-b2edf0db8903` | Owned by `sdlc-graph`, whose own `docs/artifacts/README.md` names its source | The graph plugin on one page, including how both plugins are tested. |

> **This side is not machine-checked, and that is a gap rather than a decision.**
> `every-artifact-link-has-a-source` lives in the graph plugin's suite and scans the graph plugin.
> The viewer has one link and no prose-checking suite to add it to, so adding one would be a whole
> runner for a single row. The gap is named here instead, rather than left for someone to discover
> by finding an uneditable page. If this file grows a second row, it has earned a checker.

## Republishing

Edit `run-viewer.html`, then republish **passing the existing `url`** — without it a new URL is
minted and the README points at a page nobody updates.

**Republish it from this plugin.** The graph's README links this demo, which is fine; a README
naming a sibling plugin is normal. Republishing a sibling's artifact is not — it has happened here
before, in the other direction, and produced two hosted pages describing different graphs under
names that gave no clue which was which.
