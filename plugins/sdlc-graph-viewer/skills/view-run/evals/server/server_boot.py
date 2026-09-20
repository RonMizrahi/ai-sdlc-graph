#!/usr/bin/env python3
"""The server actually serves its page — booted, on a real port, over real HTTP.

This suite exists because of a defect that shipped and survived: `VIEWER` defaulted to
`run-viewer.html` BESIDE `server.mjs`, where no viewer has ever shipped. Every project that did not
set `VIEWER_HTML` by hand got `404 not found` on `/` and `/view` — while `/api/runs`,
`/api/config` and `/api/runs/<id>/state` all answered perfectly.

That combination is why nobody caught it: the API working is exactly what makes a 404 on the page
read as a mistyped URL rather than a broken install. And every existing suite reads FILES —
`graph_sync.py` parses the viewer's embedded graph, `snapshot_safety.py` builds a snapshot in
memory. **Nothing had ever started the server.** A checker that only reads files cannot see a path
that is wrong only at runtime.

Four checks, all against a live process:

  page-is-served          `/` and `/view` return 200 and the real viewer HTML
  api-still-answers       the API routes keep working (guards against a fix that breaks them)
  missing-viewer-is-fatal a VIEWER_HTML that does not resolve exits non-zero at SPAWN,
                          rather than binding a port and 404-ing later
  env-viewer-is-honoured  an explicit VIEWER_HTML overrides the default
"""
import http.client
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "lib"))
import paths  # noqa: E402

BOOT_TIMEOUT_S = 15


def _spawn(env_extra, project_dir):
    """Start the server with a fixed port; return (proc, port, stdout_so_far)."""
    env = dict(os.environ)
    env.pop("SDLC_GRAPH_VIEWER_ENV", None)
    # A fixed port keeps the test deterministic AND exercises the non-derived path.
    port = 8399
    env.update({"PROJECT_DIR": str(project_dir), "PORT": str(port), "HOST": "127.0.0.1"})
    env.update(env_extra)
    proc = subprocess.Popen(
        [_node(), str(paths.SERVER)],
        cwd=str(project_dir), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    return proc, port


def _node():
    return os.environ.get("NODE", "node")


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


def _wait_listening(port, proc):
    deadline = time.time() + BOOT_TIMEOUT_S
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            _get(port, "/api/config")
            return True
        except OSError:
            time.sleep(0.15)
    return False


def _project(tmp):
    """A project dir with one real run in it, so /api/runs has something to list."""
    root = pathlib.Path(tmp)
    run = root / "docs" / "graph-runs" / "boot-check-01-01-2026"
    run.mkdir(parents=True)
    (run / "state.json").write_text(json.dumps({
        "run_id": "boot-check-01-01-2026", "schema_version": 5,
        "node": "INTAKE", "status": "RUNNING", "stopped": None,
        "milestones": [], "history": [], "skipped_gates": [], "attempts": {},
    }))
    return root


def main():
    failures = []

    def check(name, ok, detail=""):
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}{'' if ok else ' — ' + detail}")
        if not ok:
            failures.append(name)

    print("── server boots and serves its page")

    # ---- the default path, which is the whole point of this file -------------------------
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(tmp)
        proc, port = _spawn({}, project)
        try:
            if not _wait_listening(port, proc):
                out = proc.stdout.read() if proc.stdout else ""
                check("page-is-served", False, f"server never listened: {out.strip()[:400]}")
                check("api-still-answers", False, "server never listened")
            else:
                viewer_html = paths.VIEWER.read_bytes()
                for path in ("/", "/view"):
                    status, body = _get(port, path)
                    check(
                        f"page-is-served {path}",
                        status == 200 and body == viewer_html,
                        f"got {status}, {len(body)} bytes (viewer is {len(viewer_html)})",
                    )
                status, body = _get(port, "/api/runs")
                runs = json.loads(body) if status == 200 else []
                check("api-still-answers /api/runs",
                      status == 200 and len(runs) == 1 and runs[0]["runId"] == "boot-check-01-01-2026",
                      f"got {status}: {body[:200]}")
                status, _ = _get(port, "/api/config")
                check("api-still-answers /api/config", status == 200, f"got {status}")
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    # ---- an unreadable viewer must be fatal at spawn, not a 404 later ---------------------
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(tmp)
        proc, port = _spawn({"VIEWER_HTML": str(project / "does-not-exist.html")}, project)
        try:
            proc.wait(timeout=BOOT_TIMEOUT_S)
            out = proc.stdout.read() if proc.stdout else ""
            check("missing-viewer-is-fatal",
                  proc.returncode != 0 and "cannot read the viewer page" in out,
                  f"exit={proc.returncode}, output={out.strip()[:300]!r}")
        except subprocess.TimeoutExpired:
            proc.terminate(); proc.wait(timeout=10)
            check("missing-viewer-is-fatal", False,
                  "server kept running with an unreadable viewer — this is the 404 defect")

    # ---- an explicit VIEWER_HTML still wins ----------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        project = _project(tmp)
        custom = project / "custom-viewer.html"
        custom.write_text("<!doctype html><title>custom</title>")
        proc, port = _spawn({"VIEWER_HTML": str(custom)}, project)
        try:
            if not _wait_listening(port, proc):
                out = proc.stdout.read() if proc.stdout else ""
                check("env-viewer-is-honoured", False, f"never listened: {out.strip()[:300]}")
            else:
                status, body = _get(port, "/view")
                check("env-viewer-is-honoured",
                      status == 200 and b"custom" in body,
                      f"got {status}: {body[:120]!r}")
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    print()
    if failures:
        print(f"FAIL  {len(failures)} server boot check(s): {', '.join(failures)}")
        return 1
    print("ok    the server serves its viewer page, keeps its API, and refuses to start without one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
