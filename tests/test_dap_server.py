"""End-to-end tests for the DAP server (TCP, real execution)."""

import json
import socket
import threading
import time
from pathlib import Path

import pytest

from parsercraft.tooling.debug.dap_server import DAPServer

PROGRAM = """\
i = 0 ;
x = 2 ;
while i < 2 {
  i = i + 1 ;
  print i ;
}
"""


class DAPClient:
    def __init__(self, program: Path, config: Path):
        self.server = DAPServer(port=0)
        self.ready = threading.Event()
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            args=(self.ready,),
            daemon=True,
        )
        self.thread.start()
        assert self.ready.wait(5), "server did not start"
        self.socket = socket.create_connection(
            ("127.0.0.1", self.server.port), timeout=5
        )
        self.stream = self.socket.makefile("rb")
        self.sequence = 0
        self.program = program
        self.config = config

    def close(self):
        self.server.stop()
        try:
            self.socket.close()
        except OSError:
            pass
        self.thread.join(timeout=5)

    def send(self, command, arguments=None):
        self.sequence += 1
        payload = json.dumps({
            "seq": self.sequence,
            "type": "request",
            "command": command,
            "arguments": arguments or {},
        }).encode("utf-8")
        self.socket.sendall(
            f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
            + payload
        )

    def read(self, timeout=5.0):
        self.socket.settimeout(timeout)
        headers = {}
        while True:
            line = self.stream.readline()
            if not line:
                raise AssertionError("connection closed")
            if line in (b"\r\n", b"\n"):
                break
            key, _, value = line.decode("ascii").partition(":")
            headers[key.lower()] = value.strip()
        return json.loads(self.stream.read(int(headers["content-length"])))

    def wait_for(self, predicate, timeout=8.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = self.read(timeout=max(0.1, deadline - time.time()))
            if predicate(message):
                return message
        raise AssertionError("expected message not received")

    def initialize(self):
        self.send("initialize", {"adapterID": "parsercraft"})
        self.wait_for(lambda m: m.get("type") == "response")
        self.wait_for(lambda m: m.get("event") == "initialized")

    def launch(self, breakpoints):
        self.send("launch", {
            "program": str(self.program),
            "config": str(self.config),
        })
        self.wait_for(lambda m: m.get("type") == "response")
        self.send("setBreakpoints", {
            "source": {"path": str(self.program)},
            "breakpoints": [{"line": line} for line in breakpoints],
        })
        response = self.wait_for(
            lambda m: m.get("type") == "response"
            and m.get("command") == "setBreakpoints"
        )
        assert all(bp["verified"] for bp in response["body"]["breakpoints"])
        self.send("configurationDone")
        self.wait_for(
            lambda m: m.get("type") == "response"
            and m.get("command") == "configurationDone"
        )

    def request(self, command, arguments=None):
        self.send(command, arguments)
        return self.wait_for(
            lambda m: m.get("type") == "response"
            and m.get("command") == command
        )


@pytest.fixture
def dap(tmp_path):
    config = tmp_path / "lang.yaml"
    config.write_text(
        "grammar:\n"
        "  rules:\n"
        "    program: 'statement+'\n"
        "    statement: 'while_stmt / assignment / print_stmt'\n"
        "    while_stmt: \"'while' comparison block\"\n"
        "    block: \"'{' statement* '}'\"\n"
        "    comparison: 'expr (\"<\" / \">\" / \"==\") expr'\n"
        "    assignment: 'IDENT \"=\" expr \";\"'\n"
        "    print_stmt: \"'print' expr ';'\"\n"
        "    expr: 'term ((\"+\" / \"-\") term)*'\n"
        "    term: 'factor ((\"*\" / \"/\") factor)*'\n"
        "    factor: 'NUMBER / IDENT'\n",
        encoding="utf-8",
    )
    program = tmp_path / "program.src"
    program.write_text(PROGRAM, encoding="utf-8")
    client = DAPClient(program, config)
    try:
        yield client
    finally:
        client.close()


def test_breakpoint_variables_and_continue(dap):
    dap.initialize()
    dap.launch([4])

    stopped = dap.wait_for(lambda m: m.get("event") == "stopped")
    assert stopped["body"]["reason"] == "breakpoint"

    stack = dap.request("stackTrace", {"threadId": 1})
    assert stack["body"]["stackFrames"][0]["line"] == 4

    dap.request("scopes", {"frameId": 0})
    variables = dap.request("variables", {"variablesReference": 1})
    values = {v["name"]: v["value"] for v in variables["body"]["variables"]}
    assert values["i"] == "0"
    assert values["x"] == "2"

    evaluated = dap.request("evaluate", {"expression": "x + 1", "frameId": 0})
    assert evaluated["body"]["result"] == "3"

    dap.request("setBreakpoints", {
        "source": {"path": str(dap.program)},
        "breakpoints": [],
    })
    dap.request("continue", {"threadId": 1})
    dap.wait_for(lambda m: m.get("event") == "terminated", timeout=10)


def test_step_over_advances_to_next_line(dap):
    dap.initialize()
    dap.launch([1])

    first = dap.wait_for(lambda m: m.get("event") == "stopped")
    assert first["body"]["reason"] == "breakpoint"
    dap.request("next", {"threadId": 1})

    second = dap.wait_for(lambda m: m.get("event") == "stopped")
    stack = dap.request("stackTrace", {"threadId": 1})
    assert stack["body"]["stackFrames"][0]["line"] == 2
    assert second["body"]["reason"] == "step"


def test_unknown_request_returns_error(dap):
    dap.initialize()
    dap.send("workspace/nonesuch", {})
    response = dap.wait_for(
        lambda m: m.get("type") == "response"
        and m.get("command") == "workspace/nonesuch"
    )
    assert response["success"] is False


def test_conditional_breakpoint_skips_until_true(dap):
    dap.initialize()
    dap.send("launch", {
        "program": str(dap.program),
        "config": str(dap.config),
    })
    dap.wait_for(lambda m: m.get("type") == "response")
    dap.send("setBreakpoints", {
        "source": {"path": str(dap.program)},
        "breakpoints": [{"line": 4, "condition": "i == 1"}],
    })
    dap.wait_for(
        lambda m: m.get("type") == "response"
        and m.get("command") == "setBreakpoints"
    )
    dap.send("configurationDone")
    dap.wait_for(
        lambda m: m.get("type") == "response"
        and m.get("command") == "configurationDone"
    )

    dap.wait_for(lambda m: m.get("event") == "stopped", timeout=10)
    variables = dap.request("variables", {"variablesReference": 1})
    values = {v["name"]: v["value"] for v in variables["body"]["variables"]}
    assert values["i"] == "1"

    dap.request("disconnect", {})


def test_hit_condition_breaks_after_n_hits(dap):
    dap.initialize()
    dap.send("launch", {
        "program": str(dap.program),
        "config": str(dap.config),
    })
    dap.wait_for(lambda m: m.get("type") == "response")
    dap.send("setBreakpoints", {
        "source": {"path": str(dap.program)},
        "breakpoints": [{"line": 4, "hitCondition": "2"}],
    })
    dap.wait_for(
        lambda m: m.get("type") == "response"
        and m.get("command") == "setBreakpoints"
    )
    dap.send("configurationDone")
    dap.wait_for(lambda m: m.get("event") == "stopped", timeout=10)

    # The trace fires before the body runs, so the second hit sees i == 1.
    variables = dap.request("variables", {"variablesReference": 1})
    values = {v["name"]: v["value"] for v in variables["body"]["variables"]}
    assert values["i"] == "1"
    dap.request("disconnect", {})


def test_watch_scope_and_container_expansion(dap):
    dap.initialize()
    dap.launch([2])  # stops on "x = 2 ;"

    dap.wait_for(lambda m: m.get("event") == "stopped")
    dap.request("evaluate", {
        "expression": "i + 10",
        "context": "watch",
        "frameId": 0,
    })

    watches = dap.request("variables", {"variablesReference": 2})
    entries = {v["name"]: v["value"] for v in watches["body"]["variables"]}
    assert entries == {"i + 10": "10"}

    dap.request("continue", {"threadId": 1})
    dap.request("disconnect", {})


def test_initialize_advertises_conditional_breakpoints(dap):
    dap.send("initialize", {"adapterID": "parsercraft"})
    response = dap.wait_for(lambda m: m.get("type") == "response")
    capabilities = response["body"]
    assert capabilities["supportsConditionalBreakpoints"] is True
    assert capabilities["supportsHitConditionalBreakpoints"] is True
