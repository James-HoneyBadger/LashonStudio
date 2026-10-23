"""Tests for the local browser playground."""

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from parsercraft.tooling.commands.playground import (
    create_playground_server,
    run_source,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent / "projects" / "aurora"


@pytest.fixture
def server():
    httpd = create_playground_server(PROJECT_ROOT, port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _url(server, path):
    host, port = server.server_address[:2]
    return f"http://{host}:{port}{path}"


def test_index_page_serves_editor(server):
    with urllib.request.urlopen(_url(server, "/"), timeout=5) as response:
        body = response.read().decode("utf-8")
    assert response.status == 200
    assert "ParserCraft Playground" in body
    assert 'id="source"' in body
    assert "api/run" in body


def test_health_endpoint(server):
    with urllib.request.urlopen(_url(server, "/api/health"), timeout=5) as r:
        assert json.loads(r.read()) == {"ok": True}


def test_run_endpoint_executes_source(server):
    payload = json.dumps({"source": 'print "hello" ;\n'}).encode()
    request = urllib.request.Request(
        _url(server, "/api/run"),
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.loads(response.read())

    assert data["ok"] is True
    assert data["output"].strip() == "hello"
    assert data["python"].strip() == "print('hello')"
    assert "int main" in data["c"]
    assert "(module" in data["wasm"]
    assert "LLVM" in data["llvm"]


def test_run_endpoint_reports_parse_errors(server):
    payload = json.dumps({"source": "x = ;\n"}).encode()
    request = urllib.request.Request(
        _url(server, "/api/run"),
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.loads(response.read())

    assert data["ok"] is False
    assert "Parse error" in data["error"]


def test_unknown_path_returns_404(server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(_url(server, "/nope"), timeout=5)
    assert excinfo.value.code == 404


def test_run_source_without_project_is_reported():
    from parsercraft.ide.studio import LanguageStudio

    result = run_source(LanguageStudio(), "print 1 ;")
    assert result["ok"] is False
    assert "No language project" in result["error"]
