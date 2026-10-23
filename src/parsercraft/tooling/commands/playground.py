"""``parsercraft play`` — a local playground for a language project.

Serves a single-page editor in the browser and exposes a tiny JSON API that
runs source through the studio pipeline (parse → transpile → execute) and
returns the generated Python, C, WASM, and LLVM output.
"""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

from parsercraft.ide.studio import LanguageStudio

_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} — ParserCraft Playground</title>
<style>
  :root {{
    color-scheme: dark;
    --bg: #0d1117; --panel: #161b22; --border: #30363d;
    --fg: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--fg);
    font-family: "Segoe UI", system-ui, sans-serif; display: flex;
    flex-direction: column; height: 100vh;
  }}
  header {{
    display: flex; align-items: center; gap: 16px; padding: 12px 20px;
    border-bottom: 1px solid var(--border); background: var(--panel);
  }}
  header h1 {{ font-size: 16px; margin: 0; font-weight: 600; }}
  header span {{ color: var(--muted); font-size: 12px; }}
  main {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 1px;
    background: var(--border); flex: 1; min-height: 0;
  }}
  section {{ display: flex; flex-direction: column; background: var(--bg); }}
  .bar {{
    display: flex; gap: 8px; align-items: center; padding: 8px 12px;
    border-bottom: 1px solid var(--border); background: var(--panel);
  }}
  .bar strong {{ font-size: 12px; letter-spacing: .08em; color: var(--muted); }}
  textarea, pre {{
    flex: 1; margin: 0; border: 0; padding: 14px; font-family:
    "JetBrains Mono", "Cascadia Code", ui-monospace, monospace;
    font-size: 13px; line-height: 1.55; background: var(--bg);
    color: var(--fg); resize: none; overflow: auto;
  }}
  pre {{ white-space: pre-wrap; }}
  button {{
    background: #238636; color: #fff; border: 0; border-radius: 6px;
    padding: 6px 16px; font-size: 13px; cursor: pointer;
  }}
  button.secondary {{ background: #21262d; border: 1px solid var(--border); }}
  button:hover {{ filter: brightness(1.15); }}
  .status {{ font-size: 12px; color: var(--muted); margin-left: auto; }}
  .tabs {{ display: flex; gap: 4px; }}
  .tabs button {{
    background: transparent; border: 1px solid transparent; color: var(--muted);
    padding: 4px 10px; font-size: 12px;
  }}
  .tabs button.active {{
    color: var(--accent); border-color: var(--border); background: var(--bg);
  }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1><span>ParserCraft Playground</span>
  <span class="status" id="status">ready</span>
</header>
<main>
  <section>
    <div class="bar">
      <strong>SOURCE</strong>
      <button id="run">Run ▶</button>
      <button class="secondary" id="reset">Reset</button>
    </div>
    <textarea id="source" spellcheck="false">{source}</textarea>
  </section>
  <section>
    <div class="bar">
      <strong>OUTPUT</strong>
      <div class="tabs" id="tabs">
        <button data-pane="run" class="active">Run</button>
        <button data-pane="python">Python</button>
        <button data-pane="c">C</button>
        <button data-pane="wasm">WASM</button>
        <button data-pane="llvm">LLVM IR</button>
      </div>
    </div>
    <pre id="output">Press Run to execute the program.</pre>
  </section>
</main>
<script>
const source = document.getElementById("source");
const output = document.getElementById("output");
const status = document.getElementById("status");
const initial = source.value;
let result = null;
let pane = "run";

function render() {{
  if (!result) return;
  if (pane === "run") {{
    const parts = [];
    if (result.output) parts.push(result.output.trimEnd());
    if (!result.ok) parts.push(result.error);
    output.textContent = parts.join("\\n") || "(no output)";
  }} else {{
    output.textContent = result[pane] || "(not generated)";
  }}
}}

document.getElementById("tabs").addEventListener("click", (event) => {{
  const target = event.target.closest("button");
  if (!target) return;
  pane = target.dataset.pane;
  for (const button of document.querySelectorAll("#tabs button")) {{
    button.classList.toggle("active", button === target);
  }}
  render();
}});

async function run() {{
  status.textContent = "running…";
  const response = await fetch("api/run", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ source: source.value }}),
  }});
  result = await response.json();
  status.textContent = result.ok ? `ok — ${{result.elapsed_ms.toFixed(1)}} ms`
                                 : "error";
  render();
}}

document.getElementById("run").addEventListener("click", run);
document.getElementById("reset").addEventListener("click", () => {{
  source.value = initial;
}});
source.addEventListener("keydown", (event) => {{
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) run();
}});
</script>
</body>
</html>
"""


class PlaygroundHandler(BaseHTTPRequestHandler):
    """Serve the playground page and its JSON API."""

    studio: LanguageStudio
    project_root: Optional[Path] = None
    sample_source = ""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        if self.server.verbose:  # type: ignore[attr-defined]
            super().log_message(format, *args)

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.rstrip("/") in ("", "/index.html"):
            name = (
                self.studio.project.name
                if self.studio.project is not None
                else "ParserCraft"
            )
            page = _INDEX_HTML.format(
                title=name,
                source=_escape(self.sample_source),
            )
            self._send(
                HTTPStatus.OK, page.encode("utf-8"), "text/html; charset=utf-8"
            )
            return
        if self.path == "/api/health":
            self._send(
                HTTPStatus.OK, b'{"ok": true}', "application/json"
            )
            return
        self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/api/run":
            self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(
                HTTPStatus.BAD_REQUEST, b'{"ok": false}', "application/json"
            )
            return

        body = json.dumps(run_source(self.studio, payload.get("source", "")))
        self._send(
            HTTPStatus.OK, body.encode("utf-8"), "application/json"
        )


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def run_source(studio: LanguageStudio, source: str) -> dict[str, Any]:
    """Run ``source`` and collect everything the playground displays."""
    if studio.project is None:
        return {
            "ok": False,
            "error": "No language project loaded.",
            "output": "",
            "python": "",
            "c": "",
            "wasm": "",
            "llvm": "",
            "elapsed_ms": 0.0,
        }

    result = studio.run(source)
    python_code = studio.last_python
    backends: dict[str, str] = {}
    for backend, generated in studio.generate_all(source).items():
        backends[backend] = generated.text if generated.ok else ""
    return {
        "ok": result.ok,
        "output": result.text,
        "error": result.error,
        "python": python_code,
        "c": backends.get("c", ""),
        "wasm": backends.get("wasm", ""),
        "llvm": backends.get("llvm", ""),
        "elapsed_ms": result.elapsed_ms,
    }


def create_playground_server(
    project: str | Path,
    port: int = 8000,
    host: str = "127.0.0.1",
    verbose: bool = False,
) -> ThreadingHTTPServer:
    """Create (but do not start) a playground HTTP server."""
    studio = LanguageStudio()
    path = Path(project).expanduser()
    if path.is_file():
        path = path.parent
    studio.open_project(path)

    sample = ""
    if studio.project is not None and studio.project.sample_path.exists():
        sample = studio.project.sample_path.read_text(encoding="utf-8")

    handler = type(
        "BoundPlaygroundHandler",
        (PlaygroundHandler,),
        {"studio": studio, "sample_source": sample},
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.verbose = verbose  # type: ignore[attr-defined]
    return server


def cmd_play(args) -> int:
    """Start the local playground server."""
    project = Path(getattr(args, "project", None) or ".")
    if not project.exists():
        print(f"Error: not found: {project}", file=sys.stderr)
        return 1

    try:
        server = create_playground_server(
            project,
            port=args.port,
            host=getattr(args, "host", "127.0.0.1"),
            verbose=getattr(args, "verbose", False),
        )
    except OSError as error:
        print(f"Error: could not start server: {error}", file=sys.stderr)
        return 1

    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/"
    print(f"ParserCraft playground running at {url}")
    print("Press Ctrl+C to stop.")

    if getattr(args, "open", False):
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping playground.")
    finally:
        server.server_close()
    return 0
