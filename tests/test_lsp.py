"""Tests for the LSP server and analyzer."""

import pytest

from lashon.config import LanguageConfig
from lashon.tooling.lsp.lsp_server import LSPServer, Position


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


class TestGrammarDiagnostics:
    """Diagnostics produced by parsing against the project grammar."""

    AURORA = (
        "program       <- statement+\n"
        "statement     <- print_stmt / assignment\n"
        "print_stmt    <- 'print' expr ';'\n"
        "assignment    <- IDENT '=' expr ';'\n"
        "expr          <- term (('+' / '-') term)*\n"
        "term          <- NUMBER / IDENT\n"
    )

    @staticmethod
    def _server():
        from lashon.parser.grammar import GrammarParser

        grammar = GrammarParser().parse(TestGrammarDiagnostics.AURORA)
        return LSPServer(LanguageConfig(), grammar=grammar)

    def test_valid_document_has_no_grammar_error(self):
        server = self._server()
        server.handle_did_open(URI, "x = 1 ;\nprint x ;\n")
        assert server.diagnostics(URI) == []

    def test_syntax_error_reports_real_position(self):
        server = self._server()
        server.handle_did_open(URI, "x = 1 ;\nprint ;\n")
        diagnostics = server.diagnostics(URI)

        assert diagnostics
        error = diagnostics[0]
        assert error["severity"] == 1
        assert error["code"] == "parse-error"
        assert error["range"]["start"] == {"line": 1, "character": 0}
        assert "Parse error" in error["message"] or "Unexpected" in error["message"]
        assert "|" not in error["message"]

    def test_diagnostics_notification_is_published(self):
        server = self._server()
        server.handle_did_open(URI, "print ;\n")
        notification = server.drain_notifications()[0]
        assert notification["method"] == "textDocument/publishDiagnostics"
        assert notification["params"]["diagnostics"]

    def test_without_grammar_no_parse_error_diagnostic(self):
        server = LSPServer(LanguageConfig())
        server.handle_did_open(URI, "print ;\n")
        codes = [d.get("code") for d in server.diagnostics(URI)]
        assert "parse-error" not in codes


class TestGrammarIntelligence:
    """Rule-aware hover, definition, references, rename, and completion."""

    TEXT = (
        "// demo grammar\n"
        "program   <- statement+\n"
        "statement <- 'print' expr ';'\n"
        "expr      <- term (('+' / '-') term)*\n"
        "term      <- NUMBER / IDENT\n"
    )
    URI = "file:///demo/grammar.peg"

    @pytest.fixture
    def server(self):
        from lashon.tooling.lsp.grammar_index import GrammarIndex

        assert GrammarIndex(self.TEXT).rules
        from lashon.parser.grammar import GrammarParser

        grammar = GrammarParser().parse(
            "program <- statement+\n"
            "statement <- 'print' expr ';'\n"
            "expr <- term (('+' / '-') term)*\n"
            "term <- NUMBER / IDENT\n"
        )
        server = LSPServer(
            LanguageConfig(), grammar=grammar, grammar_path="/demo/grammar.peg"
        )
        server.handle_did_open(self.URI, self.TEXT)
        return server

    def test_hover_shows_rule_pattern(self, server):
        result = server.hover(self.URI, Position(3, 0))
        assert result is not None
        assert "expr <- term" in result["contents"]["value"]

    def test_definition_jumps_to_rule(self, server):
        result = server.definition(self.URI, Position(1, 1))
        assert result["range"]["start"] == {"line": 1, "character": 0}
        assert result["uri"] == self.URI

    def test_references_finds_every_use(self, server):
        result = server.references(self.URI, Position(3, 0))
        lines = sorted({ref["range"]["start"]["line"] for ref in result})
        assert lines == [2, 3]

    def test_rename_returns_workspace_edits(self, server):
        result = server.rename(self.URI, Position(3, 0), "expression")
        edits = result["changes"][self.URI]
        assert len(edits) == 2
        assert all(edit["newText"] == "expression" for edit in edits)

    def test_completion_offers_rules(self, server):
        items = server.completions(self.URI, Position(4, 18))
        labels = [item["label"] for item in items]
        assert "NUMBER" in labels

    def test_document_symbols_list_rules(self, server):
        names = [symbol["name"] for symbol in server.document_symbols(self.URI)]
        assert names == ["program", "statement", "expr", "term"]

    def test_hover_builtin_token_describes_token(self, server):
        result = server.hover(self.URI, Position(4, 16))
        assert "built-in token" in result["contents"]["value"]


def test_grammar_document_reports_undefined_rules():
    from lashon.parser.grammar import GrammarParser

    server = LSPServer(
        LanguageConfig(),
        grammar=GrammarParser().parse("program <- statement+\nstatement <- IDENT\n"),
        grammar_path="/g/grammar.peg",
    )
    server.handle_did_open(
        "file:///g/grammar.peg", "program <- statement+\nstatement <- mystery\n"
    )

    diagnostics = server.diagnostics("file:///g/grammar.peg")
    assert diagnostics
    assert diagnostics[0]["code"] == "undefined-rule"
    assert diagnostics[0]["severity"] == 2
    assert "mystery" in diagnostics[0]["message"]
