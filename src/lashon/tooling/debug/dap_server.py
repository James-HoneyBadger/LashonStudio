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

from lashon.codegen import PythonTranspiler, TranspileOptions
from lashon.parser import PEGInterpreter
from lashon.tooling.commands.common import load_grammar


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
        self._conditions: dict[int, str] = {}
        self._hit_conditions: dict[int, int] = {}
        self._hit_counts: dict[int, int] = {}
        self._watches: list[str] = []
        self._variables_cache: dict[int, list[dict]] = {}
        self._next_variable_reference = 100
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
                    "supportsConditionalBreakpoints": True,
                    "supportsHitConditionalBreakpoints": True,
                    "supportsTerminateRequest": True,
                },
            )
            self.send_event("initialized")

        elif command == "launch":
            self._program = arguments.get("program") or self._program
            self._config = arguments.get("config") or self._config
            self._grammar = arguments.get("grammar") or self._grammar
            self._respond(request)

        elif command == "setBreakpoints":
            breakpoints = [
                item for item in arguments.get("breakpoints", [])
                if "line" in item
            ]
            lines = {int(item["line"]) for item in breakpoints}
            for item in breakpoints:
                line = int(item["line"])
                condition = (item.get("condition") or "").strip()
                if condition:
                    self._conditions[line] = condition
                else:
                    self._conditions.pop(line, None)
                hit_condition = str(item.get("hitCondition") or "").strip()
                if hit_condition.isdigit():
                    self._hit_conditions[line] = int(hit_condition)
                else:
                    self._hit_conditions.pop(line, None)
            removed = self._breakpoints - (lines | self.initial_breakpoints)
            for line in removed:
                self._conditions.pop(line, None)
                self._hit_conditions.pop(line, None)
                self._hit_counts.pop(line, None)
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
                        },
                        {
                            "name": "Watch",
                            "variablesReference": 2,
                            "expensive": False,
                        },
                    ]
                },
            )

        elif command == "variables":
            reference = int(arguments.get("variablesReference", 1))
            self._respond(
                request, {"variables": self._variables(reference)}
            )

        elif command == "evaluate":
            expression = arguments.get("expression", "")
            if arguments.get("context") == "watch" and expression.strip():
                if expression not in self._watches:
                    self._watches.append(expression)
            self._respond(
                request,
                {"result": self._evaluate(expression)},
            )

        elif command == "terminate":
            self._respond(request)
            self._shutdown.set()
            self._resume.set()

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
            should_stop = self._should_stop_at(source_line, frame)
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

    def _should_stop_at(self, source_line: int, frame) -> bool:
        """Apply hit counts and conditions for a breakpoint line."""
        self._hit_counts[source_line] = self._hit_counts.get(source_line, 0) + 1
        required = self._hit_conditions.get(source_line)
        if required is not None and self._hit_counts[source_line] < required:
            return False
        condition = self._conditions.get(source_line)
        if condition:
            try:
                if not eval(  # noqa: S307 - user-provided breakpoint condition
                    condition, frame.f_globals, frame.f_locals
                ):
                    return False
            except Exception:  # pylint: disable=broad-exception-caught
                return False
        return True

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

    def _variables(self, reference: int = 1) -> list[dict]:
        if reference == 2:
            return [
                {
                    "name": expression,
                    "value": self._evaluate(expression),
                    "type": "",
                    "variablesReference": 0,
                }
                for expression in self._watches
            ]
        if reference != 1:
            return self._variables_cache.get(reference, [])
        if self._frame is None:
            return []

        self._variables_cache.clear()
        variables = []
        for name, value in self._frame.f_locals.items():
            if name.startswith("__"):
                continue
            variables.append(self._describe(name, value))
        return variables

    def _describe(self, name: str, value: Any) -> dict:
        """Describe a value, expanding containers one level."""
        entry = {
            "name": name,
            "value": repr(value),
            "type": type(value).__name__,
            "variablesReference": 0,
        }
        children: list[dict] = []
        if isinstance(value, dict):
            children = [
                self._describe(str(key), item) for key, item in value.items()
            ]
        elif isinstance(value, (list, tuple, set)):
            children = [
                self._describe(str(index), item)
                for index, item in enumerate(value)
            ]
        elif hasattr(value, "__dict__") and not callable(value):
            children = [
                self._describe(attribute, item)
                for attribute, item in vars(value).items()
                if not attribute.startswith("__")
            ]

        if children:
            reference = self._next_variable_reference
            self._next_variable_reference += 1
            entry["variablesReference"] = reference
            self._variables_cache[reference] = children[:100]
        return entry

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
