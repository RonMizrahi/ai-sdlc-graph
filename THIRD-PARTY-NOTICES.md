# Third-party notices

Everything in this repository is original work by Ron Mizrahi and MIT-licensed under
[`LICENSE`](LICENSE), **with two exceptions**, both listed below. They are MIT-licensed too, and the
notice below is what MIT asks be carried with them.

---

## Superpowers

- **Source:** <https://github.com/obra/superpowers>
- **License:** MIT
- **Upstream version:** not recorded at the time the material was adapted. The derivation is stated
  in each file's own header rather than pinned to a commit.

### Required notice

```
MIT License

Copyright (c) 2025 Jesse Vincent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Which files are derived

Two node procedures in `sdlc-graph`. Each already carries a `copied-from:` header naming its
immediate source and a `trimmed:` header stating what was removed and why:

| File in this repository | Derived from |
|---|---|
| `plugins/sdlc-graph/skills/sdlc-graph/nodes/systematic-debugging-node.md` | `skills/systematic-debugging/SKILL.md` — the Iron Law and the four-phase root-cause method are upstream expression, kept in full because they *are* the substance of the node |
| `plugins/sdlc-graph/skills/sdlc-graph/nodes/brainstorming-node.md` | `skills/brainstorming/SKILL.md` — the Socratic one-question-at-a-time method and the spec-file discipline |

Both reached this repository through an intermediate adaptation (standalone skills of the
author's, not published here), and both were then trimmed for the graph: the standalone trigger
phrases, the terminal hand-offs and the pointers to files that do not ship here were removed, and
the graph-only material — the re-entrancy contract, the four callers, the bounds — was added. The
headers in each file record exactly what was kept, removed, and added.

### Not derived

Everything else, including: the graph model itself (nodes, edges, guards, bounds, the run-state
schema), the milestone agent, the run viewer and its server, every eval suite, the six remaining
node procedures, and the whole of `sdlc-graph-engineering-install`.

### What is *not* granted

The MIT License covers copyright, not trademarks. **"Superpowers" is the name of Jesse Vincent's
project**, and nothing here claims rights in that name or implies endorsement. This project is
independent — not a fork, not a replacement, and not affiliated with or endorsed by the Superpowers
maintainers.

### One diagram, also derivative

`plugins/sdlc-graph-engineering-install/docs/assets/superpowers-graph-spine.svg` renders Superpowers'
own node names — it is the output of `sdlc-graph-engineering-install` pointed at that project, shown
in that plugin's README as an example of what the method produces. It is a derivative analysis of an MIT-licensed project, covered by the same
notice above, and it is credited beside the image. The other diagram in `docs/assets/` is original.

---

## Dispatched, never copied

`sdlc-graph` invokes several tools **by name at runtime** — `code-review`, `security-review`,
`pr-review-toolkit:code-reviewer`, `code-simplifier`, `claude-md-management:claude-md-improver`. None
of them is redistributed here in any form; each is invoked if installed and recorded as a skipped
gate if not. Invoking software by name creates no notice obligation, so none of them appears above.
