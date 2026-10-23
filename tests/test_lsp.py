"""Tests for the LSP server and analyzer."""

import pytest

from parsercraft.config import LanguageConfig
from parsercraft.tooling.lsp.lsp_server import LSPServer, Position


@pytest.fixture
def server():
    return LSPServer(LanguageConfig.from_preset("python_like"))


URI = "file:///tmp/example.test"


def test_initialize_reports_capabilities(server):
    result = server.initialize("/tmp")
    assert "capabilities" in result
    assert "completionProvider" in result["capabilities"]
    assert result["serverInfo"]["name"]


def test_document_lifecycle(server):
    server.handle_did_open(URI, "x = 1\n")
    assert server.document_manager.get_document(URI) == "x = 1\n"

    server.handle_did_change(URI, [{"text": "x = 2\n"}], version=2)
    assert server.document_manager.get_document(URI) == "x = 2\n"

    server.handle_did_close(URI)
    assert server.document_manager.get_document(URI) == ""


def test_incremental_change(server):
    server.handle_did_open(URI, "x = 1\n")
    server.handle_did_change(
        URI,
        [{
            "range": {
                "start": {"line": 0, "character": 4},
                "end": {"line": 0, "character": 5},
            },
            "text": "42",
        }],
        version=2,
    )
    assert server.document_manager.get_document(URI) == "x = 42\n"


def test_completions_include_keywords(server):
    labels = [item["label"] for item in server.completions(URI, Position(0, 0))]
    assert "if" in labels


def test_hover_uses_word_under_cursor(server):
    server.handle_did_open(URI, "def foo(x):\n")
    hover = server.hover(URI, Position(0, 1))
    assert hover is not None
    assert "def" in hover["contents"]
    start = hover["range"]["start"]["character"]
    end = hover["range"]["end"]["character"]
    assert start == 0
    assert end == 3


def test_hover_returns_none_for_unknown_word(server):
    server.handle_did_open(URI, "def foo(x):\n")
    assert server.hover(URI, Position(0, 4)) is None


def test_document_symbols_find_function(server):
    server.handle_did_open(URI, "def foo(x):\n    return x\n")
    symbols = server.document_symbols(URI)
    assert [symbol["name"] for symbol in symbols] == ["foo"]


def test_format_trims_trailing_whitespace(server):
    server.handle_did_open(URI, "def foo(x):   \n    return x   \n")
    edits = server.format_document(URI)
    assert len(edits) == 1
    assert edits[0]["newText"] == "def foo(x):\n    return x\n"


def test_format_is_noop_for_formatted_document(server):
    server.handle_did_open(URI, "x = 1\n")
    assert server.format_document(URI) == []


class TestStdioDispatch:
    """JSON-RPC dispatch used by the stdio transport."""

    def test_did_open_queues_diagnostics_notification(self, server):
        server._handle_request({
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": URI,
                    "languageId": "python",
                    "version": 1,
                    "text": 'x = "unterminated\n',
                }
            },
        })

        notifications = server.drain_notifications()
        assert len(notifications) == 1
        assert notifications[0]["method"] == "textDocument/publishDiagnostics"
        assert notifications[0]["params"]["uri"] == URI
        assert notifications[0]["params"]["diagnostics"]

        # Draining clears the queue.
        assert server.drain_notifications() == []

    def test_did_change_republishes_diagnostics(self, server):
        server.handle_did_open(URI, "x = 1\n")
        server.drain_notifications()

        server._handle_request({
            "jsonrpc": "2.0",
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {"uri": URI, "version": 2},
                "contentChanges": [{"text": 'x = "open\n'}],
            },
        })

        notifications = server.drain_notifications()
        assert notifications[0]["params"]["diagnostics"]

    def test_request_methods_return_results(self, server):
        server.handle_did_open(URI, "def foo(x):\n    return x\n")
        server.drain_notifications()

        hover = server._handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/hover",
            "params": {
                "textDocument": {"uri": URI},
                "position": {"line": 0, "character": 1},
            },
        })
        assert hover["id"] == 2
        assert hover["result"] is not None

        symbols = server._handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "textDocument/documentSymbol",
            "params": {"textDocument": {"uri": URI}},
        })
        assert [symbol["name"] for symbol in symbols["result"]] == ["foo"]

        formatting = server._handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "textDocument/formatting",
            "params": {"textDocument": {"uri": URI}, "options": {}},
        })
        assert formatting["result"] == []

    def test_unknown_request_returns_method_not_found(self, server):
        response = server._handle_request({
            "jsonrpc": "2.0",
            "id": 9,
            "method": "workspace/nonesuch",
            "params": {},
        })
        assert response["error"]["code"] == -32601

    def test_unknown_notification_is_ignored(self, server):
        assert server._handle_request({
            "jsonrpc": "2.0",
            "method": "workspace/didChangeConfiguration",
            "params": {},
        }) is None
