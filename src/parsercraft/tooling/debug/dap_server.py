"""A small Debug Adapter Protocol server with real execution and stepping.

The server listens on TCP, compiles the program to Python with source maps,
runs it in a worker thread, and pauses at source lines using ``sys.settrace``.
It implements the subset of DAP needed by VS Code and the test suite.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Optional

from parsercraft.codegen import PythonTranspiler, TranspileOptions
from parsercraft.parser import PEGInterpreter
from parsercraft.tooling.commands.common import load_grammar


class _Output:
    """Thread-aware stdout proxy: debuggee output becomes DAP events."""

    def __init__(
        self,
        server: "DAPServer",
        category: str,
        fallback,
        worker_id: int,
    ):
        self.server = server
        self.category = category
        self.fallback = fallback
        self.worker_id = worker_id

    def write(self, text: str) -> int:
        if not text:
            return 0
        if threading.get_ident() == self.worker_id:
            self.server.send_event(
                "output", {"category": self.category, "output": text}
            )
        else:
            self.fallback.write(text)
        return len(text)

    def flush(self) -> None:
        self.fallback.flush()


class DAPServer:
    """Minimal DAP server over TCP with breakpoints, stepping, and evaluation."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5678):
        self.host = host
        self.port = port
        self.initial_breakpoints: set[int] = set()

        self._server: Optional[socket.socket] = None
        self._connection: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._sequence = 1

        self._program: Optional[str] = None
        self._config: Optional[str] = None
        self._grammar: Optional[str] = None
        self._breakpoints: set[int] = set()
        self._line_map: dict[int, int] = {}
        self._source_text = ""
        self._source_path = ""

        self._thread: Optional[threading.Thread] = None
        self._frame = None
        self._stopped_line: Optional[int] = None
        self._resume = threading.Event()
        self._configured = threading.Event()
        self._pause_requested = False
        self._step_mode: Optional[str] = None
        self._step_depth = 0
        self._terminated = False
        self._shutdown = threading.Event()

    # -- transport -------------------------------------------------------

    def serve_forever(self, ready: Optional[threading.Event] = None) -> None:
        """Accept one client and serve DAP messages until disconnect."""
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen(1)
        self.port = self._server.getsockname()[1]
        if ready is not None:
            ready.set()
        print(
            f"DAP server listening on {self.host}:{self.port}",
            file=sys.stderr,
        )
        try:
            connection, _ = self._server.accept()
        except OSError:
            return
        self._connection = connection
        self._serve_connection(connection)
        connection.close()
        self._server.close()

    def stop(self) -> None:
        """Stop the server and release the program if it is paused."""
        self._shutdown.set()
        self._resume.set()
        self._configured.set()
        if self._connection is not None:
            try:
                self._connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._connection.close()
            except OSError:
                pass
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass

    def _serve_connection(self, connection: socket.socket) -> None:
        stream = connection.makefile("rb")
        try:
            while not self._shutdown.is_set():
                headers: dict[str, str] = {}
                while True:
                    try:
                        line = stream.readline()
                    except (ConnectionResetError, OSError):
                        return
                    if not line:
                        return
                    text = line.decode("ascii", "replace").strip()
                    if not text:
                        break
                    key, _, value = text.partition(":")
                    headers[key.lower()] = value.strip()
                try:
                    length = int(headers.get("content-length", "0"))
                except ValueError:
                    continue
                if length <= 0:
                    continue
                body = stream.read(length)
                try:
                    request = json.loads(body)
                except json.JSONDecodeError:
                    continue
                self._dispatch(request)
        finally:
            try:
                stream.close()
            except OSError:
                pass

    def _send(self, message: dict) -> None:
        if self._connection is None:
            return
        payload = json.dumps(message).encode("utf-8")
        with self._lock:
            try:
                self._connection.sendall(
                    f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
                    + payload
                )
            except OSError:
                pass

    def send_event(self, event: str, body: Optional[dict] = None) -> None:
        self._send(
            {
                "type": "event",
                "event": event,
                "body": body or {},
                "seq": self._next_sequence(),
            }
        )

    def _respond(self, request: dict, body: Optional[dict] = None) -> None:
        self._send(
            {
                "type": "response",
                "request_seq": request.get("seq", 0),
                "command": request.get("command"),
                "success": True,
                "body": body or {},
                "seq": self._next_sequence(),
            }
        )

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    # -- dispatch --------------------------------------------------------

    def _dispatch(self, request: dict) -> None:
        command = request.get("command")
        arguments = request.get("arguments") or {}

        if command == "initialize":
            self._respond(
                request,
                {
                    "supportsConfigurationDoneRequest": True,
                    "supportsEvaluateForHovers": True,
                    "supportsStepBack": False,
                },
            )
            self.send_event("initialized")

        elif command == "launch":
            self._program = arguments.get("program") or self._program
            self._config = arguments.get("config") or self._config
            self._grammar = arguments.get("grammar") or self._grammar
            self._respond(request)

        elif command == "setBreakpoints":
            lines = {
                int(item["line"])
                for item in arguments.get("breakpoints", [])
                if "line" in item
            }
            self._breakpoints = lines | self.initial_breakpoints
            self._respond(
                request,
                {
                    "breakpoints": [
                        {"verified": True, "line": line}
                        for line in sorted(self._breakpoints)
                    ]
                },
            )

        elif command == "configurationDone":
            self._respond(request)
            self._configured.set()
            self._start_program()

        elif command == "threads":
            self._respond(
                request, {"threads": [{"id": 1, "name": "main"}]}
            )

        elif command == "stackTrace":
            self._respond(request, self._stack_trace())

        elif command == "scopes":
            self._respond(
                request,
                {
                    "scopes": [
                        {
                            "name": "Locals",
                            "variablesReference": 1,
                            "expensive": False,
                        }
                    ]
                },
            )

        elif command == "variables":
            self._respond(request, {"variables": self._variables()})

        elif command == "evaluate":
            self._respond(
                request,
                {"result": self._evaluate(arguments.get("expression", ""))},
            )

        elif command in ("continue", "next", "stepIn", "stepOut"):
            if command == "continue":
                self._step_mode = None
            else:
                self._step_mode = command
                self._step_depth = self._depth(self._frame)
            self._respond(request, {"allThreadsContinued": True})
            self._resume.set()

        elif command == "pause":
            self._pause_requested = True
            self._respond(request)

        elif command == "disconnect":
            self._respond(request)
            self._shutdown.set()
            self._resume.set()

        elif command in (
            "setExceptionBreakpoints",
            "source",
            "loadedSources",
        ):
            self._respond(request)

        else:
            self._send(
                {
                    "type": "response",
                    "request_seq": request.get("seq", 0),
                    "command": command,
                    "success": False,
                    "message": f"Unsupported request: {command}",
                    "seq": self._next_sequence(),
                }
            )

    # -- program execution ----------------------------------------------

    def _start_program(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_program, daemon=True)
        self._thread.start()

    def _run_program(self) -> None:
        self._configured.wait(timeout=30)
        try:
            if not self._program:
                raise ValueError("launch did not provide a program")
            source_path = Path(self._program)
            source = source_path.read_text(encoding="utf-8")
            grammar = load_grammar(
                config_path=self._config,
                grammar_path=self._grammar,
                require_rules=True,
            )
            ast = PEGInterpreter(grammar).parse(source)
            transpiler = PythonTranspiler(
                TranspileOptions(source_maps=True)
            )
            code = transpiler.transpile(ast)

            self._line_map = dict(transpiler.line_map)
            self._source_text = source
            self._source_path = str(source_path)

            namespace: dict[str, Any] = {"__name__": "__main__"}
            compiled = compile(code, str(source_path), "exec")

            original_stdout, original_stderr = sys.stdout, sys.stderr
            worker_id = threading.get_ident()
            sys.stdout = _Output(self, "stdout", original_stdout, worker_id)
            sys.stderr = _Output(self, "stderr", original_stderr, worker_id)
            sys.settrace(self._trace)
            try:
                exec(compiled, namespace)  # noqa: S102
            finally:
                sys.settrace(None)
                sys.stdout = original_stdout
                sys.stderr = original_stderr

            self._terminated = True
            self.send_event("terminated")
            self.send_event("exited", {"exitCode": 0})

        except Exception as error:  # pylint: disable=broad-exception-caught
            self.send_event(
                "output",
                {
                    "category": "stderr",
                    "output": traceback.format_exc(),
                },
            )
            self._terminated = True
            self.send_event("terminated")
            self.send_event("exited", {"exitCode": 1})
            self.send_event(
                "output",
                {"category": "stderr", "output": f"Debuggee error: {error}\n"},
            )

    def _trace(self, frame, event, _arg):
        if event != "line":
            return self._trace

        source_line = self._line_map.get(frame.f_lineno)
        if source_line is None:
            return self._trace

        should_stop = False
        reason = "breakpoint"

        if source_line in self._breakpoints:
            should_stop = True
        elif self._pause_requested:
            should_stop = True
            reason = "pause"
        elif self._step_mode is not None:
            depth = self._depth(frame)
            if self._step_mode == "next":
                should_stop = depth <= self._step_depth
            elif self._step_mode == "stepOut":
                should_stop = depth < self._step_depth
            else:
                should_stop = True
            if should_stop:
                reason = "step"

        if not should_stop:
            return self._trace

        self._pause_requested = False
        self._step_mode = None
        self._frame = frame
        self._stopped_line = source_line
        self._resume.clear()
        self.send_event(
            "stopped",
            {
                "reason": reason,
                "threadId": 1,
                "allThreadsStopped": True,
            },
        )
        self._resume.wait(timeout=300)
        self._frame = None
        self._stopped_line = None
        return self._trace

    @staticmethod
    def _depth(frame) -> int:
        depth = 0
        while frame is not None:
            depth += 1
            frame = frame.f_back
        return depth

    # -- inspection ------------------------------------------------------

    def _stack_trace(self) -> dict:
        if self._frame is None:
            return {"stackFrames": [], "totalFrames": 0}
        frames = []
        frame = self._frame
        index = 0
        while frame is not None and index < 20:
            line = self._line_map.get(frame.f_lineno, self._stopped_line or 1)
            frames.append(
                {
                    "id": index,
                    "name": frame.f_code.co_name,
                    "source": {
                        "name": Path(self._source_path).name,
                        "path": self._source_path,
                    },
                    "line": line,
                    "column": 1,
                }
            )
            frame = frame.f_back
            index += 1
        return {"stackFrames": frames, "totalFrames": len(frames)}

    def _variables(self) -> list[dict]:
        if self._frame is None:
            return []
        variables = []
        for name, value in self._frame.f_locals.items():
            if name.startswith("__"):
                continue
            variables.append(
                {
                    "name": name,
                    "value": repr(value),
                    "type": type(value).__name__,
                    "variablesReference": 0,
                }
            )
        return variables

    def _evaluate(self, expression: str) -> str:
        if self._frame is None or not expression.strip():
            return ""
        try:
            value = eval(  # noqa: S307 - debugger evaluation is user-driven
                expression,
                self._frame.f_globals,
                self._frame.f_locals,
            )
            return repr(value)
        except Exception as error:  # pylint: disable=broad-exception-caught
            return f"<error: {error}>"
