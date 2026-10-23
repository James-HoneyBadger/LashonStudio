#!/usr/bin/env python3
"""
LSP Features Integration for ParserCraft

Integrates Phase 4 LSP advanced features (refactoring, formatting, DAP) with
the main LSP server for comprehensive IDE support.

Features:
    - Refactoring operations (rename, extract, inline)
    - Code formatting
    - Semantic token highlighting
    - Debug Adapter Protocol integration
    - Server capability registration
    - Feature negotiation with clients

Usage:
    from parsercraft.lsp_integration import LSPFeaturesIntegration
    
    integration = LSPFeaturesIntegration(lsp_server)
    
    # Register all features
    integration.register_all_features()
    
    # Handle requests
    response = integration.handle_refactoring_request(request)
    formatted = integration.handle_formatting_request(document)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from parsercraft.tooling.debug.debug_adapter import DebugAdapter, Debugger
from parsercraft.tooling.lsp.lsp_advanced import (
    CodeFormatter,
    RefactoringEngine,
    SemanticHighlighter,
)


@dataclass
class ServerCapability:
    """Represents an LSP server capability."""

    name: str
    enabled: bool = True
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RefactoringRequest:
    """Request for refactoring operation."""

    operation: str  # "rename", "extract", "inline"
    uri: str
    position: Tuple[int, int]  # (line, column)
    new_name: Optional[str] = None
    range: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RefactoringResponse:
    """Response from refactoring operation."""

    success: bool
    changes: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=dict
    )  # uri -> edits
    error_message: str = ""


@dataclass
class FormattingRequest:
    """Request for code formatting."""

    uri: str
    range: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FormattingResponse:
    """Response from formatting operation."""

    edits: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""


class LSPFeaturesIntegration:
    """Integrates LSP advanced features with main server."""

    def __init__(self, lsp_server: Any = None):
        """Initialize LSP features integration.

        Args:
            lsp_server: The main LSP server instance (optional)
        """
        self.lsp_server = lsp_server

        # Initialize feature engines
        self.refactoring_engine = RefactoringEngine()
        self.code_formatter = CodeFormatter()
        self.semantic_highlighter = SemanticHighlighter()
        # Provide a lightweight debugger instance for DAP wiring in non-server contexts.
        self.debug_adapter = DebugAdapter(Debugger(program_path=""))

        # Feature registry
        self.capabilities: Dict[str, ServerCapability] = {}
        self._register_capabilities()

        # Handlers registry
        self.request_handlers: Dict[str, Callable] = {}
        self.notification_handlers: Dict[str, Callable] = {}
        self._register_handlers()

        # Cache for performance
        self.formatting_cache: Dict[str, str] = {}
        self.highlight_cache: Dict[str, List[Dict[str, Any]]] = {}

    def _register_capabilities(self) -> None:
        """Register LSP server capabilities."""
        self.capabilities = {
            "textDocument/formatting": ServerCapability(
                name="formatting",
                options={
                    "provider": True,
                },
            ),
            "textDocument/rangeFormatting": ServerCapability(
                name="rangeFormatting",
                options={
                    "provider": True,
                },
            ),
            "textDocument/refactoring": ServerCapability(
                name="refactoring",
                options={
                    "rename": True,
                    "extractVariable": True,
                    "extractFunction": True,
                    "inline": True,
                },
            ),
            "textDocument/semanticTokens": ServerCapability(
                name="semanticTokens",
                options={
                    "legend": {
                        "tokenTypes": [
                            "namespace",
                            "type",
                            "class",
                            "enum",
                            "interface",
                            "struct",
                            "typeParameter",
                            "parameter",
                            "variable",
                            "property",
                            "enumMember",
                            "event",
                            "function",
                            "method",
                            "macro",
                            "keyword",
                            "modifier",
                            "comment",
                            "string",
                            "number",
                            "regexp",
                            "operator",
                        ],
                        "tokenModifiers": [
                            "declaration",
                            "definition",
                            "readonly",
                            "static",
                            "deprecated",
                            "abstract",
                            "async",
                            "modification",
                            "documentation",
                            "defaultLibrary",
                        ],
                    },
                    "full": True,
                    "range": True,
                },
            ),
            "debug/adapter": ServerCapability(
                name="debugAdapter",
                options={
                    "protocol": "DAP/1.51",
                },
            ),
        }

    def _register_handlers(self) -> None:
        """Register request and notification handlers."""
        # Refactoring handlers
        self.request_handlers["textDocument/refactor"] = self.handle_refactoring
        self.request_handlers["textDocument/rename"] = self.handle_rename
        self.request_handlers["textDocument/codeAction"] = self.handle_code_actions

        # Formatting handlers
        self.request_handlers["textDocument/formatting"] = self.handle_formatting
        self.request_handlers[
            "textDocument/rangeFormatting"
        ] = self.handle_range_formatting

        # Semantic tokens
        self.request_handlers[
            "textDocument/semanticTokens/full"
        ] = self.handle_semantic_tokens_full
        self.request_handlers[
            "textDocument/semanticTokens/range"
        ] = self.handle_semantic_tokens_range

        # Debug adapter
        self.request_handlers["debug/start"] = self.handle_debug_start
        self.request_handlers["debug/stop"] = self.handle_debug_stop
        self.notification_handlers["debug/breakpoint"] = self.handle_breakpoint

    def get_server_capabilities(self) -> Dict[str, Any]:
        """Get LSP server capabilities object.

        Returns:
            Dictionary with server capabilities for InitializeResult
        """
        return {
            "textDocumentSync": 1,  # FULL
            "completionProvider": {"resolveProvider": True},
            "hoverProvider": True,
            "definitionProvider": True,
            "referencesProvider": True,
            "implementationProvider": True,
            "typeDefinitionProvider": True,
            "documentSymbolProvider": True,
            "workspaceSymbolProvider": True,
            "codeActionProvider": {
                "codeActionKinds": ["quickfix", "refactor"],
                "resolveProvider": True,
            },
            "renameProvider": {"prepareProvider": True},
            "documentFormattingProvider": True,
            "documentRangeFormattingProvider": True,
            "semanticTokensProvider": self.capabilities[
                "textDocument/semanticTokens"
            ].options,
            "debugAdapterProvider": True,
        }

    def handle_refactoring(self, request: Dict[str, Any]) -> RefactoringResponse:
        """Handle refactoring request.

        Args:
            request: LSP refactoring request

        Returns:
            RefactoringResponse with changes or errors
        """
        try:
            params = request.get("params", {})
            operation = params.get("operation", "")
            uri = params.get("textDocument", {}).get("uri", "")

            if not operation:
                return RefactoringResponse(
                    success=False, error_message="Missing operation type"
                )

            if operation == "rename":
                return self._handle_rename_refactoring(params, uri)
            elif operation == "extractVariable":
                return self._handle_extract_variable(params, uri)
            elif operation == "extractFunction":
                return self._handle_extract_function(params, uri)
            elif operation == "inline":
                return self._handle_inline(params, uri)
            else:
                return RefactoringResponse(
                    success=False,
                    error_message=f"Unknown refactoring operation: {operation}",
                )

        except Exception as e:
            return RefactoringResponse(
                success=False, error_message=str(e)
            )

    def _handle_rename_refactoring(
        self, params: Dict[str, Any], uri: str
    ) -> RefactoringResponse:
        """Handle rename refactoring.

        Args:
            params: Request parameters
            uri: Document URI

        Returns:
            RefactoringResponse
        """
        old_name = params.get("oldName")
        new_name = params.get("newName")

        if not old_name or not new_name:
            return RefactoringResponse(
                success=False, error_message="Missing oldName or newName"
            )

        # Use refactoring engine — signature is rename(old_name, new_name, source)
        content = self.lsp_server.document_manager.get_document(uri) if self.lsp_server else ""
        edits = self.refactoring_engine.rename(
            old_name, new_name, content
        )

        return RefactoringResponse(
            success=True,
            changes={uri: edits},
        )

    def _handle_extract_variable(
        self, params: Dict[str, Any], uri: str
    ) -> RefactoringResponse:
        """Handle extract variable refactoring."""
        var_name = params.get("name", "extracted")
        range_ = params.get("range")

        if not range_:
            return RefactoringResponse(
                success=False, error_message="Missing range"
            )

        edits = self.refactoring_engine.extract_variable(uri, var_name, range_)

        return RefactoringResponse(
            success=True,
            changes={uri: edits},
        )

    def _handle_extract_function(
        self, params: Dict[str, Any], uri: str
    ) -> RefactoringResponse:
        """Handle extract function refactoring."""
        func_name = params.get("name", "extracted_function")
        range_ = params.get("range")

        if not range_:
            return RefactoringResponse(
                success=False, error_message="Missing range"
            )

        edits = self.refactoring_engine.extract_function(uri, func_name, range_)

        return RefactoringResponse(
            success=True,
            changes={uri: edits},
        )

    def _handle_inline(
        self, params: Dict[str, Any], uri: str
    ) -> RefactoringResponse:
        """Handle inline refactoring."""
        position = params.get("position")

        if not position:
            return RefactoringResponse(
                success=False, error_message="Missing position"
            )

        edits = self.refactoring_engine.inline(uri, position)

        return RefactoringResponse(
            success=True,
            changes={uri: edits},
        )

    def handle_rename(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle rename request (textDocument/rename).

        Args:
            request: LSP rename request

        Returns:
            WorkspaceEdit with changes
        """
        params = request.get("params", {})
        uri = params.get("textDocument", {}).get("uri", "")
        position = params.get("position", {})
        new_name = params.get("newName", "")

        if not uri or not position or not new_name:
            return {"error": "Missing required parameters"}

        # Extract the old name from the document at the cursor position
        old_name = ""
        if self.lsp_server:
            content = self.lsp_server.document_manager.get_document(uri)
            if content:
                lines = content.split('\n')
                line_num = position.get("line", 0)
                char = position.get("character", 0)
                if line_num < len(lines):
                    line = lines[line_num]
                    # Find word boundaries around cursor
                    import re as _re
                    for m in _re.finditer(r'\w+', line):
                        if m.start() <= char <= m.end():
                            old_name = m.group()
                            break

        if not old_name:
            return {"error": "Could not identify symbol at position"}

        response = self._handle_rename_refactoring(
            {"oldName": old_name, "newName": new_name, "position": position},
            uri,
        )

        if response.success:
            return {"changes": response.changes}
        else:
            return {"error": response.error_message}

    def handle_code_actions(self, request: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle code actions request.

        Args:
            request: LSP code action request

        Returns:
            List of code actions
        """
        # Return refactoring actions as code actions
        actions = [
            {
                "title": "Rename",
                "kind": "refactor.rewrite",
                "command": {
                    "title": "Rename",
                    "command": "textDocument/refactor",
                    "arguments": [{"operation": "rename"}],
                },
            },
            {
                "title": "Extract Variable",
                "kind": "refactor.extract",
                "command": {
                    "title": "Extract Variable",
                    "command": "textDocument/refactor",
                    "arguments": [{"operation": "extractVariable"}],
                },
            },
            {
                "title": "Extract Function",
                "kind": "refactor.extract",
                "command": {
                    "title": "Extract Function",
                    "command": "textDocument/refactor",
                    "arguments": [{"operation": "extractFunction"}],
                },
            },
        ]

        return actions

    def handle_formatting(self, request: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle document formatting request.

        Args:
            request: LSP formatting request

        Returns:
            List of text edits
        """
        params = request.get("params", {})
        uri = params.get("textDocument", {}).get("uri", "")

        if not uri:
            return []

        # Check cache
        if uri in self.formatting_cache:
            return self.formatting_cache[uri]

        # Format document using code_formatter.format()
        content = self.lsp_server.document_manager.get_document(uri) if self.lsp_server else ""
        if not content:
            return []
        formatted = self.code_formatter.format(content)
        edits = [{
            "range": {
                "start": {"line": 0, "character": 0},
                "end": {"line": len(content.split('\n')), "character": 0},
            },
            "newText": formatted,
        }]

        # Cache result
        self.formatting_cache[uri] = edits

        return edits

    def handle_range_formatting(
        self, request: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Handle range formatting request.

        Args:
            request: LSP range formatting request

        Returns:
            List of text edits
        """
        params = request.get("params", {})
        uri = params.get("textDocument", {}).get("uri", "")
        range_ = params.get("range", {})

        if not uri or not range_:
            return []

        # Format range using code_formatter.format()
        content = self.lsp_server.document_manager.get_document(uri) if self.lsp_server else ""
        if not content:
            return []
        lines = content.split('\n')
        start_line = range_["start"]["line"]
        end_line = range_["end"]["line"] + 1
        range_text = '\n'.join(lines[start_line:end_line])
        formatted = self.code_formatter.format(range_text)
        edits = [{
            "range": range_,
            "newText": formatted,
        }]

        return edits

    def handle_semantic_tokens_full(
        self, request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle semantic tokens full request.

        Args:
            request: LSP semantic tokens request

        Returns:
            SemanticTokensResponse
        """
        params = request.get("params", {})
        uri = params.get("textDocument", {}).get("uri", "")

        if not uri:
            return {"data": []}

        # Check cache
        if uri in self.highlight_cache:
            tokens = self.highlight_cache[uri]
        else:
            # Generate tokens using semantic_highlighter.extract_tokens()
            content = self.lsp_server.document_manager.get_document(uri) if self.lsp_server else ""
            if not content:
                tokens = []
            else:
                extracted = self.semantic_highlighter.extract_tokens(content)
                tokens = [t.to_lsp_format() if hasattr(t, 'to_lsp_format') else t for t in extracted]
                self.highlight_cache[uri] = tokens

        # Convert to LSP format (array of relative positions and token types)
        data = []
        last_line = 0
        last_char = 0

        for token in tokens:
            line = token.get("line", 0)
            char = token.get("character", 0)
            type_idx = token.get("tokenType", 0)
            mod_mask = token.get("modifiers", 0)

            # Relative line delta
            data.append(line - last_line)

            # Relative character delta (reset if line changed)
            if line != last_line:
                data.append(char)
            else:
                data.append(char - last_char)

            # Token length
            data.append(token.get("length", 1))

            # Token type
            data.append(type_idx)

            # Token modifiers (bitmask)
            data.append(mod_mask)

            last_line = line
            last_char = char

        return {"data": data}

    def handle_semantic_tokens_range(
        self, request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle semantic tokens range request."""
        params = request.get("params", {})
        uri = params.get("textDocument", {}).get("uri", "")
        range_ = params.get("range", {})

        if not uri or not range_:
            return {"data": []}

        # Get range
        start_line = range_.get("start", {}).get("line", 0)
        end_line = range_.get("end", {}).get("line", 0)

        content = self.lsp_server.document_manager.get_document(uri) if self.lsp_server else ""
        if not content:
            return {"data": []}
        lines = content.split('\n')
        range_text = '\n'.join(lines[start_line:end_line + 1])
        extracted = self.semantic_highlighter.extract_tokens(range_text)
        tokens = [t.to_lsp_format() if hasattr(t, 'to_lsp_format') else t for t in extracted]

        # Convert to LSP format
        data = []
        for token in tokens:
            data.extend(
                [
                    token.get("line", 0),
                    token.get("character", 0),
                    token.get("length", 1),
                    token.get("tokenType", 0),
                    token.get("modifiers", 0),
                ]
            )

        return {"data": data}

    def handle_debug_start(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle debug start request.

        Args:
            request: Debug initialization request

        Returns:
            Debug session response
        """
        params = request.get("params", {})
        program = params.get("program", "")
        # args = params.get("args", [])

        if not program:
            return {"error": "Missing program path"}

        # Initialize debug adapter for the program
        self.debug_adapter = DebugAdapter(Debugger(program_path=program))
        session_id = id(self.debug_adapter)

        return {
            "sessionId": session_id,
            "threadId": 1,
            "capabilities": {
                "supportsSetVariable": True,
                "supportsBreakpointHitConditions": True,
                "supportsLogPoints": True,
                "supportsConditionalBreakpoints": True,
            },
        }

    def handle_debug_stop(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle debug stop request."""
        params = request.get("params", {})
        session_id = params.get("sessionId", "")

        if session_id:
            # Reset debug adapter to idle state
            self.debug_adapter = DebugAdapter(Debugger(program_path=""))

        return {"success": True}

    def handle_breakpoint(
        self, notification: Dict[str, Any]
    ) -> None:
        """Handle breakpoint notification."""
        params = notification.get("params", {})
        uri = params.get("textDocument", {}).get("uri", "")
        line = params.get("line", 0)
        condition = params.get("condition", "")

        if uri:
            self.debug_adapter.set_breakpoint(uri, line, condition)

    def register_all_features(self) -> None:
        """Register all LSP features with server.

        This is called during server initialization to enable all features.
        """
        if not self.lsp_server:
            return

        # Store handlers on the server for dispatch
        if not hasattr(self.lsp_server, '_feature_handlers'):
            self.lsp_server._feature_handlers = {}
        if not hasattr(self.lsp_server, '_notification_handlers'):
            self.lsp_server._notification_handlers = {}

        for req_type, handler in self.request_handlers.items():
            self.lsp_server._feature_handlers[req_type] = handler

        for notif_type, handler in self.notification_handlers.items():
            self.lsp_server._notification_handlers[notif_type] = handler

    def clear_caches(self) -> None:
        """Clear formatting and highlighting caches."""
        self.formatting_cache.clear()
        self.highlight_cache.clear()

    def get_feature_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered features.

        Returns:
            Dictionary with feature status information
        """
        status = {}

        for name, capability in self.capabilities.items():
            status[name] = {
                "enabled": capability.enabled,
                "options": capability.options,
                "handler_registered": name in self.request_handlers,
            }

        return status
