#!/usr/bin/env python3
"""
Debug Adapter Protocol (DAP) for Custom Languages

Enables debugging in IDEs by implementing the Debug Adapter Protocol.

Features:
    - Breakpoint management
    - Stack trace inspection
    - Variable inspection
    - Stepping (step in, step out, step over)
    - Expression evaluation
    - Pause/resume execution
    - Source mapping

Usage:
    from lashon.debug_adapter import DebugAdapter, Debugger
    
    debugger = Debugger(program_path)
    adapter = DebugAdapter(debugger)
    adapter.start()  # Start debug server

Protocol:
    Implements VSCode Debug Adapter Protocol v1.51
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StopReason(Enum):
    """Reason for stopping execution."""

    BREAKPOINT = "breakpoint"
    STEP = "step"
    PAUSE = "pause"
    EXCEPTION = "exception"
    ENTRY = "entry"
    GOTO = "goto"


@dataclass
class SourceReference:
    """Reference to source code."""

    path: str
    source_reference: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.path.split("/")[-1],
            "path": self.path,
            "sourceReference": self.source_reference,
        }


@dataclass
class Breakpoint:
    """Breakpoint in source code."""

    id: int
    source_path: str
    line: int
    column: int = 1
    condition: Optional[str] = None
    hit_condition: Optional[str] = None
    log_message: Optional[str] = None
    verified: bool = False
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": {"path": self.source_path},
            "line": self.line,
            "column": self.column,
            "verified": self.verified,
            "message": self.message,
        }


@dataclass
class StackFrame:
    """Stack frame in execution."""

    id: int
    name: str
    source_path: str
    line: int
    column: int = 1
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source": {"path": self.source_path},
            "line": self.line,
            "column": self.column,
            "endLine": self.end_line,
            "endColumn": self.end_column,
        }


@dataclass
class Variable:
    """Variable in scope."""

    name: str
    value: Any
    var_type: str
    indexed_variables: Optional[int] = None
    named_variables: Optional[int] = None
    memory_reference: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": str(self.value),
            "type": self.var_type,
            "indexedVariables": self.indexed_variables,
            "namedVariables": self.named_variables,
            "memoryReference": self.memory_reference,
        }


@dataclass
class Scope:
    """Variable scope."""

    name: str
    variables: List[Variable] = field(default_factory=list)
    indexed_variables: Optional[int] = None
    named_variables: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "variables": self.variables,
            "indexedVariables": self.indexed_variables,
            "namedVariables": self.named_variables,
        }


class ExecutionState(Enum):
    """Execution state of the debugged program."""

    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    TERMINATED = "terminated"


class Debugger:
    """Debugger for custom language programs."""

    def __init__(self, program_path: str):
        self.program_path = program_path
        self.state = ExecutionState.IDLE
        self.breakpoints: Dict[str, List[Breakpoint]] = {}
        self.call_stack: List[StackFrame] = []
        self.scopes: Dict[int, Scope] = {}
        self.current_frame = 0
        self.breakpoint_id = 0
        self.frame_id = 0
        self.variables: Dict[int, List[Variable]] = {}

    def set_breakpoint(
        self,
        source_path: str,
        line: int,
        column: int = 1,
        condition: Optional[str] = None,
    ) -> Breakpoint:
        """Set a breakpoint."""
        if source_path not in self.breakpoints:
            self.breakpoints[source_path] = []

        self.breakpoint_id += 1
        bp = Breakpoint(
            id=self.breakpoint_id,
            source_path=source_path,
            line=line,
            column=column,
            condition=condition,
            verified=True,
        )

        self.breakpoints[source_path].append(bp)
        return bp

    def remove_breakpoint(self, bp_id: int) -> bool:
        """Remove a breakpoint by ID."""
        for source_path, bps in self.breakpoints.items():
            for i, bp in enumerate(bps):
                if bp.id == bp_id:
                    bps.pop(i)
                    return True
        return False

    def get_breakpoints(self, source_path: str) -> List[Breakpoint]:
        """Get breakpoints for a source file."""
        return self.breakpoints.get(source_path, [])

    def start(self) -> None:
        """Start debugging."""
        self.state = ExecutionState.RUNNING

    def pause(self) -> None:
        """Pause execution."""
        self.state = ExecutionState.STOPPED

    def continue_execution(self) -> None:
        """Continue execution."""
        self.state = ExecutionState.RUNNING

    def step_in(self) -> None:
        """Step into function."""
        # Push new frame on call stack
        self.frame_id += 1
        frame = StackFrame(
            id=self.frame_id,
            name="function_call",
            source_path=self.program_path,
            line=1,
        )
        self.call_stack.append(frame)

    def step_out(self) -> None:
        """Step out of current function."""
        if self.call_stack:
            self.call_stack.pop()

    def step_over(self) -> None:
        """Step over current line."""
        if self.call_stack:
            self.call_stack[-1].line += 1

    def get_stack_trace(self) -> List[StackFrame]:
        """Get current call stack."""
        return self.call_stack

    def set_variable(self, frame_id: int, var_name: str, value: Any) -> bool:
        """Set variable value."""
        if frame_id in self.variables:
            for var in self.variables[frame_id]:
                if var.name == var_name:
                    var.value = value
                    return True
        return False

    def get_variables(self, frame_id: int) -> List[Variable]:
        """Get variables for a frame."""
        return self.variables.get(frame_id, [])

    def add_variable(self, frame_id: int, var: Variable) -> None:
        """Add variable to frame."""
        if frame_id not in self.variables:
            self.variables[frame_id] = []

        self.variables[frame_id].append(var)

    _BINARY_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _COMPARE_OPERATORS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: lambda left, right: left in right,
        ast.NotIn: lambda left, right: left not in right,
        ast.Is: operator.is_,
        ast.IsNot: operator.is_not,
    }

    def _frame_values(self, frame_id: int) -> Dict[str, Any]:
        """Return the variables of a frame as a name → value mapping."""
        return {var.name: var.value for var in self.get_variables(frame_id)}

    def _evaluate_ast(self, node: ast.AST, values: Dict[str, Any]) -> Any:
        """Evaluate a whitelisted expression node without executing code."""
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in values:
                return values[node.id]
            raise ValueError(f"Unknown variable '{node.id}'")

        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate_ast(node.operand, values)
            if isinstance(node.op, ast.Not):
                return not operand
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result: Any = True
                for value_node in node.values:
                    result = self._evaluate_ast(value_node, values)
                    if not result:
                        return result
                return result
            if isinstance(node.op, ast.Or):
                for value_node in node.values:
                    result = self._evaluate_ast(value_node, values)
                    if result:
                        return result
                return result
            raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

        if isinstance(node, ast.BinOp):
            func = self._BINARY_OPERATORS.get(type(node.op))
            if func is None:
                raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
            return func(
                self._evaluate_ast(node.left, values),
                self._evaluate_ast(node.right, values),
            )

        if isinstance(node, ast.Compare):
            left = self._evaluate_ast(node.left, values)
            for op, comparator in zip(node.ops, node.comparators):
                func = self._COMPARE_OPERATORS.get(type(op))
                if func is None:
                    raise ValueError(f"Unsupported comparison: {type(op).__name__}")
                right = self._evaluate_ast(comparator, values)
                if not func(left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.List):
            return [self._evaluate_ast(item, values) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._evaluate_ast(item, values) for item in node.elts)
        if isinstance(node, ast.Set):
            return {self._evaluate_ast(item, values) for item in node.elts}
        if isinstance(node, ast.Dict):
            return {
                self._evaluate_ast(key, values): self._evaluate_ast(value, values)
                for key, value in zip(node.keys, node.values)
            }
        if isinstance(node, ast.Subscript):
            return self._evaluate_ast(node.value, values)[
                self._evaluate_ast(node.slice, values)
            ]

        raise ValueError(f"Unsupported expression: {type(node).__name__}")

    def _evaluate_condition(self, condition: str, frame_id: int) -> bool:
        """Evaluate a breakpoint condition safely.

        Only literals, frame variables, arithmetic, boolean and comparison
        operators, collection literals, and subscripts are allowed.
        """
        tree = ast.parse(condition, mode="eval")
        return bool(self._evaluate_ast(tree.body, self._frame_values(frame_id)))

    def evaluate_expression(self, expression: str, frame_id: int) -> Optional[str]:
        """Evaluate expression in context of frame.

        Only allows safe expressions (literals, variables, arithmetic,
        boolean/comparison operators, collection literals, subscripts).
        Returns ``None`` when the expression is invalid.
        """
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._evaluate_ast(tree.body, self._frame_values(frame_id))
            return str(result)
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError,
                KeyError, IndexError, AttributeError):
            return None

    def hit_breakpoint(self, source_path: str, line: int) -> Optional[Breakpoint]:
        """Check if execution hit a breakpoint."""
        bps = self.get_breakpoints(source_path)

        for bp in bps:
            if bp.line == line:
                if bp.condition:
                    try:
                        if not self._evaluate_condition(
                                bp.condition, self.current_frame):
                            continue
                    except (ValueError, SyntaxError, TypeError,
                            ZeroDivisionError, KeyError, IndexError) as error:
                        bp.verified = False
                        bp.message = f"Invalid condition: {error}"
                        continue
                return bp

        return None


class DebugAdapter:
    """Debug Adapter Protocol handler."""

    def __init__(self, debugger: Debugger):
        self.debugger = debugger
        self.seq = 0
        self.thread_id = 1

    def _send_response(self, request_seq: int, success: bool, body: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format a response."""
        response = {
            "type": "response",
            "seq": self.seq,
            "request_seq": request_seq,
            "command": "",
            "success": success,
        }
        self.seq += 1

        if body:
            response["body"] = body

        return response

    def _send_event(self, event_type: str, body: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format an event."""
        event = {
            "type": "event",
            "seq": self.seq,
            "event": event_type,
        }
        self.seq += 1

        if body:
            event["body"] = body

        return event

    def handle_initialize(self) -> Dict[str, Any]:
        """Handle initialize request."""
        return self._send_response(
            0,
            True,
            {
                "capabilities": {
                    "supportsConfigurationDoneRequest": True,
                    "supportsFunctionBreakpoints": True,
                    "supportsConditionalBreakpoints": True,
                    "supportsHitConditionalBreakpoints": True,
                    "supportsEvaluateForHovers": True,
                    "supportsStepBack": False,
                    "supportsSetVariable": True,
                    "supportsGotoTargetsRequest": False,
                    "supportsStepInTargetsRequest": True,
                    "supportsLogPoints": True,
                    "supportsModulesRequest": False,
                }
            },
        )

    def handle_launch(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle launch request."""
        self.debugger.start()
        return self._send_response(1, True)

    def handle_set_breakpoints(
        self, source_path: str, lines: List[int]
    ) -> Dict[str, Any]:
        """Handle set breakpoints request."""
        bps = []

        # Clear existing breakpoints for this source
        if source_path in self.debugger.breakpoints:
            self.debugger.breakpoints[source_path].clear()

        # Add new breakpoints
        for line in lines:
            bp = self.debugger.set_breakpoint(source_path, line)
            bps.append(bp.to_dict())

        return self._send_response(2, True, {"breakpoints": bps})

    def handle_stack_trace(self, thread_id: int) -> Dict[str, Any]:
        """Handle stack trace request."""
        stack_frames = [sf.to_dict() for sf in self.debugger.get_stack_trace()]

        return self._send_response(3, True, {"stackFrames": stack_frames, "totalFrames": len(stack_frames)})

    def handle_scopes(self, frame_id: int) -> Dict[str, Any]:
        """Handle scopes request."""
        scopes = [
            {
                "name": "Local",
                "variablesReference": 1,
                "expensive": False,
            },
            {
                "name": "Global",
                "variablesReference": 2,
                "expensive": False,
            },
        ]

        return self._send_response(4, True, {"scopes": scopes})

    def handle_variables(self, variables_reference: int) -> Dict[str, Any]:
        """Handle variables request."""
        variables = self.debugger.get_variables(variables_reference)

        return self._send_response(5, True, {"variables": [v.to_dict() for v in variables]})

    def handle_continue(self, thread_id: int) -> Dict[str, Any]:
        """Handle continue request."""
        self.debugger.continue_execution()

        # Send continued event
        self._send_event("continued", {"threadId": thread_id})

        return self._send_response(6, True, {"allThreadsContinued": True})

    def handle_next(self, thread_id: int, frame_id: int) -> Dict[str, Any]:
        """Handle next (step over) request."""
        self.debugger.step_over()

        # Send stopped event
        self._send_event(
            "stopped",
            {"reason": StopReason.STEP.value, "threadId": thread_id, "allThreadsStopped": True},
        )

        return self._send_response(7, True)

    def handle_step_in(self, thread_id: int, frame_id: int) -> Dict[str, Any]:
        """Handle step in request."""
        self.debugger.step_in()

        # Send stopped event
        self._send_event(
            "stopped",
            {"reason": StopReason.STEP.value, "threadId": thread_id, "allThreadsStopped": True},
        )

        return self._send_response(8, True)

    def handle_step_out(self, thread_id: int, frame_id: int) -> Dict[str, Any]:
        """Handle step out request."""
        self.debugger.step_out()

        # Send stopped event
        self._send_event(
            "stopped",
            {"reason": StopReason.STEP.value, "threadId": thread_id, "allThreadsStopped": True},
        )

        return self._send_response(9, True)

    def handle_evaluate(self, expression: str, frame_id: int) -> Dict[str, Any]:
        """Handle evaluate request."""
        result = self.debugger.evaluate_expression(expression, frame_id)

        if result is None:
            return self._send_response(10, False, {"error": "Unable to evaluate expression"})

        return self._send_response(10, True, {"result": result, "type": "string", "variablesReference": 0})

    def handle_pause(self, thread_id: int) -> Dict[str, Any]:
        """Handle pause request."""
        self.debugger.pause()

        # Send stopped event
        self._send_event(
            "stopped",
            {"reason": StopReason.PAUSE.value, "threadId": thread_id, "allThreadsStopped": True},
        )

        return self._send_response(11, True)
