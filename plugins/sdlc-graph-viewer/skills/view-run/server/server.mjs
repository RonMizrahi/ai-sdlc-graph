#!/usr/bin/env node
// sdlc-graph-viewer — one server per project, zero dependencies.
//
// Serves:  /  and  /view          the run viewer (viewer/run-viewer.html — the ONE copy).
//                                 Its sidebar IS the run list; there is no second list to drift.
//          /api/runs              JSON listing of docs/graph-runs/*/state.json, newest first
//          /api/runs/<id>/progress  the milestone journals under that run's journals/
//          /api/runs/<id>/state   one state file, no-store, read fresh per request
//
// Rules: one server per project, never shared — the port is derived from the
// project path, so the same project always gets the same port. The viewer page
// polls its state URL every 1s, forever, even after DONE.
import { createServer } from 'node:http'
import { readFile, readdir, stat } from 'node:fs/promises'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

// ── config: a NATIVE .env file — no JSON, no parser of ours ──────────────
// $SDLC_GRAPH_VIEWER_ENV → ./sdlc-graph-viewer.env (if present). Node's loadEnvFile fills
// process.env; variables already set in the real environment WIN over the file
// (Node's documented precedence — exactly the env > file > default order).
//   PROJECT_DIR=/abs/path      where the project lives (default: cwd)
//   RUNS_DIR=/abs/path         where the run DIRECTORIES live (default: $PROJECT_DIR/docs/graph-runs)
//   PORT=8477                  fixed port (default: stable derived per-project port)
//   POLL_MS=500                page poll interval (default: 1000)
const ENV_FILE = process.env.SDLC_GRAPH_VIEWER_ENV ?? join(process.cwd(), 'sdlc-graph-viewer.env')
const DEFAULTS = 'defaults + env'   // sentinel, never sent to the page: /api/config reports null
let ENV_SOURCE = DEFAULTS
try { process.loadEnvFile(ENV_FILE); ENV_SOURCE = ENV_FILE } catch (err) {
  if (process.env.SDLC_GRAPH_VIEWER_ENV) {            // an explicitly named file that is MISSING is an error,
    console.error(`env file ${ENV_FILE}: ${err.message}`); process.exit(1)   // never a silent fallback.
  }                                             // (Node's own parser is lenient: malformed LINES are
}                                               //  skipped, not thrown — standard .env semantics.)
// EVERY setting comes from the environment (file or real env) — the values
// below are only the defaults when a variable is absent. Nothing else in this
// file assumes a place or a name.
const num = (v, dflt) => (Number(v) > 0 ? Number(v) : dflt)
const PROJECT_DIR = process.env.PROJECT_DIR ?? process.cwd()
// A run is a DIRECTORY now — docs/graph-runs/<run-id>/{state.json,journals/} — not a pile of
// <run-id>-prefixed files in one folder. `SDLC_DIR` is still read so an existing
// sdlc-graph-viewer.env keeps working, and it is the only way to point at a run from the old
// layout: that layout is not discovered.
const RUNS_DIR = process.env.RUNS_DIR ?? process.env.SDLC_DIR ?? join(PROJECT_DIR, 'docs', 'graph-runs')
const POLL_MS = num(process.env.POLL_MS, 1000)
// `viewer/run-viewer.html` — one directory OVER, because this file lives in `server/`. The default
// used to resolve beside server.mjs, where no viewer has ever shipped, so every project that did not
// set VIEWER_HTML by hand answered `404 not found` on `/` and `/view` while `/api/*` worked
// perfectly — the shape that reads as "wrong URL" rather than "broken install".
// `evals/lib/paths.py` has resolved this correctly the whole time; only the server was wrong.
const VIEWER = process.env.VIEWER_HTML ?? join(dirname(fileURLToPath(import.meta.url)), '..', 'viewer', 'run-viewer.html')
const HOST = process.env.HOST ?? '127.0.0.1'   // localhost-only by default — state files are not LAN reading
const PORT_BASE = num(process.env.PORT_BASE, 8400)
const PORT_RANGE = num(process.env.PORT_RANGE, 400)
const PORT_RETRIES = num(process.env.PORT_RETRIES, 20)

/** Stable per-project port: FNV-1a of the project path. */
function derivePort(dir) {
  let h = 0x811c9dc5
  for (let i = 0; i < dir.length; i++) { h ^= dir.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0 }
  return PORT_BASE + (h % PORT_RANGE)
}

async function listRuns() {
  let names = []
  try {
    names = (await readdir(RUNS_DIR, { withFileTypes: true })).filter(d => d.isDirectory()).map(d => d.name)
  } catch (err) {
    // A directory that is not there yet is genuinely "no runs" — that is the pre-first-run state and
    // it deserves an empty list. Anything else (a typo'd RUNS_DIR, EACCES, a file where a directory
    // should be) is a broken configuration, and returning [] for it made the page fall through to
    // its built-in DEMO run: a plausible-looking graph, labelled as a real one, for a path that does
    // not exist. Same rule the graph itself runs on — absent is not a pass.
    if (err.code === 'ENOENT') return []
    throw Object.assign(new Error(`cannot read ${RUNS_DIR}: ${err.message}`), { statusCode: 500 })
  }
  const runs = []
  for (const id of names) {
    // `unreadable` is its own flag, and the parse error is carried rather than swallowed.
    // It used to be reported as `status: 'unreadable'` — a fifth value in a four-value enum
    // (state.md: RUNNING | BLOCKED | HANDOFF | DONE), which left the page unable to tell a
    // corrupt file apart from a status it had never heard of, and with nothing to show a human
    // about WHY. A run you cannot read is a fact about the run: list it, and say what happened.
    const entry = { runId: id, node: null, status: null, updatedAt: null, unreadable: true, error: null,
      stateUrl: `/api/runs/${id}/state`, viewUrl: `/view?state=/api/runs/${id}/state` }
    try {
      const statePath = join(RUNS_DIR, id, 'state.json')
      const st = await stat(statePath)
      entry.updatedAt = st.mtime.toISOString()
      const s = JSON.parse(await readFile(statePath, 'utf8'))
      entry.node = s.node ?? '?'; entry.status = s.status ?? '?'; entry.unreadable = false
    } catch (err) { entry.error = String(err.message ?? err) }
    runs.push(entry)
  }
  return runs.sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)))
}


const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? '/', 'http://x')
  const send = (code, type, body) =>
    res.writeHead(code, { 'Content-Type': type, 'Cache-Control': 'no-store' }).end(body)
  try {
    // The app IS the run list now — its sidebar polls /api/runs. `/view` stays as an alias so
    // the relay block's URLs and anyone's bookmark keep working.
    if (url.pathname === '/' || url.pathname === '/view') {
      // A viewer page that cannot be read is a broken CONFIGURATION, never a missing route — the
      // same distinction this file already draws for RUNS_DIR below. Letting the ENOENT fall
      // through to the catch produced a bare `404 not found` for a server whose only page was
      // misconfigured, which is indistinguishable from a typo'd URL and sent people hunting the
      // wrong thing.
      try {
        return send(200, 'text/html; charset=utf-8', await readFile(VIEWER))
      } catch (err) {
        throw Object.assign(new Error(`cannot read viewer page ${VIEWER}: ${err.message}`), { statusCode: 500 })
      }
    }
    if (url.pathname === '/api/config') return send(200, 'application/json',
      JSON.stringify({ pollMs: POLL_MS, projectDir: PROJECT_DIR, runsDir: RUNS_DIR, host: HOST, envFile: ENV_SOURCE === DEFAULTS ? null : ENV_SOURCE }))
    if (url.pathname === '/api/runs') return send(200, 'application/json', JSON.stringify(await listRuns()))
    const m = url.pathname.match(/^\/api\/runs\/([A-Za-z0-9._-]+)\/state$/) // sanitized — no traversal
    if (m) return send(200, 'application/json', await readFile(join(RUNS_DIR, m[1], 'state.json')))

    // The milestone journals: what each milestone agent said WHILE it ran, which the state file deliberately does not
    // carry. Same sanitized id class as /state — the run id is the only thing from the URL that
    // touches a path, and it never contains a separator.
    const inflightMatch = url.pathname.match(/^\/api\/runs\/([A-Za-z0-9._-]+)\/progress$/)
    if (inflightMatch) {
      const runId = inflightMatch[1]
      // A milestone now journals two lines per subagent it spawns, and one Gate A over a 38-file
      // diff is dozens of them — the old 200-line ceiling silently cut the START of the list, which
      // is precisely the part the page shows as "spawn order". Raised to 5000, and what gets cut is
      // REPORTED (`dropped`) so a truncated list can say so instead of reading as the whole run.
      const tail = Math.min(5000, Math.max(1, Number(url.searchParams.get('tail')) || 40))
      const journalDir = join(RUNS_DIR, runId, 'journals')
      let names = []
      try {
        names = await readdir(journalDir)
      } catch (err) {
        if (err.code !== 'ENOENT') throw Object.assign(new Error(`cannot read ${journalDir}: ${err.message}`), { statusCode: 500 })
      }
      const out = {}
      for (const name of names.filter(n => n.startsWith('milestone-') && n.endsWith('.jsonl'))) {
        const mid = name.slice('milestone-'.length, -'.jsonl'.length)
        // A journal is append-only and read while it is being written, so a torn final line is the
        // NORMAL case rather than corruption. Report it as one unreadable entry and keep the rest —
        // dropping the whole file because its last line is half-written would blank a live milestone agent.
        const entry = { lines: [], unreadable: 0, dropped: 0, error: null }
        try {
          for (const raw of (await readFile(join(journalDir, name), 'utf8')).split('\n')) {
            if (!raw.trim()) continue
            try { entry.lines.push(JSON.parse(raw)) } catch { entry.unreadable++ }
          }
          // What the tail cut off is REPORTED, never silently dropped. The page renders these lines
          // as "the subagents this milestone spawned, in order"; a truncated list that does not say
          // it is truncated is that same sentence about a different, smaller run.
          entry.dropped = Math.max(0, entry.lines.length - tail)
          entry.lines = entry.lines.slice(-tail)
        } catch (err) { entry.error = String(err.message ?? err) }
        out[mid] = entry
      }
      return send(200, 'application/json', JSON.stringify(out))
    }
    return send(404, 'text/plain', 'not found')
  } catch (err) {
    // A missing state file is a 404 and always was. A broken CONFIGURATION is not — collapsing the
    // two sent `404 not found` for an unreadable RUNS_DIR, which the page reads as "no runs here"
    // and answers with its demo. Carry the real status and the real reason.
    if (err?.statusCode) return send(err.statusCode, 'text/plain', String(err.message))
    return send(404, 'text/plain', 'not found')
  }
})

// Fail at SPAWN, not at the first page load. The server's whole job is to serve one HTML page, so
// a server that binds a port while unable to read that page is not "started" in any sense the user
// cares about — and the failure surfaces minutes later, in a browser, as a 404 that looks like a
// bad URL. Checked before listen() so the error is what the spawning agent relays instead of a
// summary promising a page that is not there.
try {
  await stat(VIEWER)
} catch (err) {
  console.error([
    `cannot read the viewer page: ${VIEWER}`,
    `  ${err.message}`,
    process.env.VIEWER_HTML
      ? '  VIEWER_HTML is set — check it points at run-viewer.html.'
      : '  Set VIEWER_HTML to the run-viewer.html you want served.',
  ].join('\n'))
  process.exit(1)
}

const fixed = process.env.PORT !== undefined ? Number(process.env.PORT) : undefined
const first = fixed ?? derivePort(PROJECT_DIR)
let attempt = 0

// One global handler pair. Passing a callback to listen() on every retry is a
// trap: the failed attempt's callback stays registered and fires alongside the
// successful one — observed as a double summary with the wrong port. Instead:
// retry on 'error', and print ONCE from 'listening' using the port the server
// actually bound (server.address(), not a closure).
server.on('error', err => {
  if (err.code === 'EADDRINUSE' && fixed === undefined && attempt < PORT_RETRIES) {
    attempt++
    server.listen(first + attempt, HOST)
  } else {
    console.error(String(err))
    process.exit(1)
  }
})
server.once('listening', () => {
  const { port } = server.address()
  // The one-server-per-project summary — printed, always.
  console.log([
    '',
    '● sdlc-graph-viewer — one server per project, this one is:',
    `  project   ${PROJECT_DIR}`,
    `  runs from ${RUNS_DIR}`,
    `  config    ${ENV_SOURCE}  (poll ${POLL_MS}ms)`,
    `  port      ${port}`,
    `  host      ${HOST}${HOST === '127.0.0.1' ? '  (localhost only — set HOST=0.0.0.0 to expose)' : ''}`,
    `  viewer    ${VIEWER}`,
    `  home      http://localhost:${port}/`,
    `  live view http://localhost:${port}/view?state=/api/runs/<run-id>/state   (polls 1s, forever — even after DONE)`,
    `  runs api  http://localhost:${port}/api/runs`,
    '',
  ].join('\n'))
})
server.listen(first, HOST)
