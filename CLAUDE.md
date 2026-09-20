# sdlc-graph-engineering — repository guide

**A bundle of three Claude Code plugins, not a catalog.** Two of them are one product in two halves
— `sdlc-graph` (the SDLC as a guarded graph) and `sdlc-graph-viewer` (the page that renders a run).
The third, `sdlc-graph-engineering-install`, is the method that produces a graph for any *other*
process. The `plugins/<name>/` layout and the root `marketplace.json` exist because installing from
a repository requires a manifest — the manifest is a bundle, not a catalog.

## Sources of truth

- Bundle manifest: `.claude-plugin/marketplace.json` · plugin manifests: `plugins/*/.claude-plugin/plugin.json`
- The graph model: `plugins/sdlc-graph/skills/sdlc-graph/graph/{nodes,edges,state}.md`
- **A plugin's own rules live with the plugin.** Before changing the graph, read
  [`plugins/sdlc-graph/docs/EDITING.md`](plugins/sdlc-graph/docs/EDITING.md) — it comes before this
  file, and testing is [`plugins/sdlc-graph/docs/TESTING.md`](plugins/sdlc-graph/docs/TESTING.md).
- A skill directory groups files by kind (`graph/ nodes/ evals/ …`) — never a pile.

## Rules that bind every change here

- **A plugin references nothing above its own root.** No `../`; `${CLAUDE_PLUGIN_ROOT}` for absolute
  paths. A plugin that reads above its root breaks on install.
  **One legal exception:** the viewer's `evals/lib/paths.py` reads the sibling graph spec, because
  the viewer holds a copy of the transition table and is the only side allowed to look. That is why
  both plugin directories must keep their names.
- **Twinned skills.** The eight `nodes/*-node.md` carry a `copied-from:` header naming a source that
  does not live in this repository. They are *meant* to diverge — `plan-guidelines-node.md` has its
  milestone loop removed because the graph drives that loop; `pr-mr-prepare-node.md` has its quality
  step removed because Gate A and Gate B are their own nodes. "Make them identical" is the wrong
  default.
- **Bump `version` in BOTH manifests** — `plugin.json` and `marketplace.json`. They must agree, and
  installed users only receive a change if it moves.
- **Re-check published counts.** Node, edge, cycle and stop counts appear in `SKILL.md`, both
  READMEs, the manifests and the rendered HTML. They drift silently, and they are the first thing a
  reader uses to decide whether the docs are current. `published-counts-match-reality` checks them.
- **Validate before opening a PR:** `claude plugin validate ./plugins/<plugin> --strict` and
  `claude plugin validate .`
- **`main` is PR-only.** Push a side branch and open a PR.
- The repo is public: no private paths, hostnames or internal repo names. The optional private
  plugins `sdlc-graph` dispatches to are named in the README, as optional, and that is the only
  place they belong.
- Keep this file under 100 lines; describe current state, not history.

## The evals — what runs when

```bash
git config core.hooksPath .githooks                                   # once per clone
python3 plugins/sdlc-graph/skills/sdlc-graph/evals/run_all.py         # 9 suites
python3 plugins/sdlc-graph-viewer/skills/view-run/evals/run_all.py    # 8 suites
python3 .claude/hooks/run-graph-evals.selftest.py                     # the hook still routes
python3 .claude/hooks/pre-push-eval-gate.selftest.py                  # the gate can still fail
python3 plugins/sdlc-graph-viewer/skills/view-run/evals/sync/sync_graph.py --write   # regenerate the
                                                                      # viewer's GRAPH from the spec
```

- **`.claude/hooks/run-graph-evals.py` (PostToolUse)** runs the affected suites after every
  Edit/Write under a graph plugin. **Editing the graph also fires the viewer's suite** — a guard
  edited in `edges.md` is exactly what makes the viewer's copy stale. The whole set costs ~3.6s.
- **`.claude/hooks/pre-push-eval-gate.py`** blocks a push carrying a red suite. It fires on any
  pushed path under a directory whose name contains `sdlc`, so `sdlc-graph-engineering-install` is
  in scope; it has no suite of its own, so such a push runs the routing self-test and nothing else.
  `SDLC_SKIP_EVAL_GATE=1` overrides, loudly. A `PreToolUse` twin catches agents, who push through
  Bash and never reach a git hook.
- **A red suite mid-change is expected** — it is the second half of the edit, not an error.
- **The executing tier is reported, never gated, and driven on demand:**
  `python3 .claude/hooks/eval-receipts.py --list` (`--drive --only <id>` runs one). **This repo
  carries no receipts** — the registry stayed with the fork this graph was promoted out of — so
  every executing test reads `NO RECEIPT` and the gate passes anyway. That is honest: authoring the
  case is mandatory, driving it is a decision someone makes with the minutes in front of them.

> `sdlc-graph` also ships **its own** hook (`plugins/sdlc-graph/hooks/hooks.json`), separate from
> the repo's: it snapshots every state a `--trace` run passes through. It fires in every project the
> plugin is installed in, so it self-gates to a no-op and never exits non-zero.

## Licensing

MIT, and every plugin manifest says so. Two node procedures derive from obra/superpowers (MIT) and
are covered by [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md); each points at it from its own
header. **Anything new that is not first-party gets a row there in the same change.**
