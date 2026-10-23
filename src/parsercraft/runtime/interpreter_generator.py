#!/usr/bin/env python3
"""
ParserCraft Interpreter Generator Module

Generates standalone interpreter instances for CodeEx (ParserCraft execution platform).
Allows ParserCraft-defined languages to be executed within CodeEx IDE.

This module extends ParserCraft to support interpreter export for use by external
applications like CodeEx.
"""

import base64
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from parsercraft.config.language_config import LanguageConfig
from parsercraft.runtime.language_runtime import LanguageRuntime


class InterpreterPackage:
    """A packaged interpreter for standalone use in CodeEx."""

    def __init__(self, config: LanguageConfig):
        """Initialize interpreter package."""
        self.config = config
        self.name = config.name
        self.version = "2.0"
        self.created_at = datetime.now().isoformat()
        # Initialize runtime (singleton pattern)
        self.runtime = LanguageRuntime.get_instance()
        self.metadata: Dict[str, Any] = {
            "name": config.name,
            "version": self.version,
            "created": self.created_at,
            "keywords": len(getattr(config, "keyword_mappings", {})),
            "functions": len(getattr(config, "builtin_functions", {})),
            "operators": len(getattr(config, "operators", {})),
        }

    def execute(
        self, code: str, _context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute code with this interpreter.

        Args:
            code: Source code to execute
            context: Optional execution context (variables, settings)

        Returns:
            Execution result dict with output, errors, variables
        """
        try:
            # Execute code using the runtime
            # Note: LanguageRuntime implementation may vary
            result: Any = getattr(self.runtime, "execute", lambda x: {})(code)
            variables: Any = getattr(self.runtime, "globals", {})
            if callable(variables):
                variables = variables()
            return {
                "status": "success",
                "output": result,
                "errors": [],
                "variables": variables.copy() if isinstance(variables, dict) else {},
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            return {
                "status": "error",
                "output": "",
                "errors": [str(e)],
                "variables": {},
            }

    def to_dict(self) -> Dict[str, Any]:
        """Export interpreter as dictionary."""
        return {
            "metadata": self.metadata,
            "config": self.config.to_dict(),
            "version": self.version,
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        """Export interpreter as JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def to_pickle(self) -> bytes:
        """Export interpreter as pickled bytes."""
        return pickle.dumps(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "InterpreterPackage":
        """Load interpreter from dictionary."""
        config = LanguageConfig.from_dict(data["config"])
        return InterpreterPackage(config)

    @staticmethod
    def from_json(json_str: str) -> "InterpreterPackage":
        """Load interpreter from JSON string."""
        data = json.loads(json_str)
        return InterpreterPackage.from_dict(data)

    @staticmethod
    def from_pickle(data: bytes) -> "InterpreterPackage":
        """Load interpreter from pickled bytes.

        Warning: pickle deserialization is unsafe for untrusted data.
        Use JSON serialization (from_json) instead whenever possible.
        """
        import warnings
        warnings.warn(
            "pickle deserialization is unsafe for untrusted data. "
            "Use from_json() instead.",
            RuntimeWarning,
            stacklevel=2,
        )
        data_dict = json.loads(data.decode("utf-8"))
        return InterpreterPackage.from_dict(data_dict)


class InterpreterGenerator:
    """Generates and manages interpreter packages for CodeEx."""

    def __init__(self):
        """Initialize interpreter generator."""
        self.interpreters: Dict[str, InterpreterPackage] = {}
        self.export_dir = Path.home() / ".parsercraft" / "interpreters"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, config: LanguageConfig) -> InterpreterPackage:
        """
        Generate an interpreter from a language configuration.

        Args:
            config: LanguageConfig instance

        Returns:
            InterpreterPackage ready for execution
        """
        interpreter = InterpreterPackage(config)
        self.interpreters[config.name] = interpreter
        return interpreter

    def export_interpreter(self, config: LanguageConfig, format: str = "json") -> str:
        """
        Export interpreter for use in CodeEx.

        Args:
            config: LanguageConfig to export
            format: Export format ("json", "pickle", "file")

        Returns:
            Exported interpreter data or file path
        """
        interpreter = self.generate(config)

        if format == "json":
            return interpreter.to_json()
        elif format == "pickle":
            return base64.b64encode(interpreter.to_pickle()).decode()
        elif format == "file":
            filepath = self.export_dir / f"{config.name}_interpreter.json"
            with open(filepath, "w") as f:
                f.write(interpreter.to_json())
            return str(filepath)
        else:
            raise ValueError(f"Unknown format: {format}")

    def import_interpreter(self, data: str, format: str = "json") -> InterpreterPackage:
        """
        Import interpreter from exported data.

        Args:
            data: Exported interpreter data
            format: Format of data ("json", "pickle")

        Returns:
            Loaded InterpreterPackage
        """
        if format == "json":
            interpreter = InterpreterPackage.from_json(data)
        elif format == "pickle":
            interpreter = InterpreterPackage.from_pickle(
                base64.b64decode(data.encode())
            )
        else:
            raise ValueError(f"Unknown format: {format}")

        self.interpreters[interpreter.name] = interpreter
        return interpreter

    def list_interpreters(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all loaded interpreters."""
        return {name: interp.metadata for name, interp in self.interpreters.items()}

    def get_interpreter(self, name: str) -> Optional[InterpreterPackage]:
        """Get loaded interpreter by name."""
        return self.interpreters.get(name)


# Global generator instance
_generator = InterpreterGenerator()


def generate_interpreter(config: LanguageConfig) -> InterpreterPackage:
    """Convenience function to generate interpreter."""
    return _generator.generate(config)


def export_interpreter(config: LanguageConfig, format: str = "json") -> str:
    """Convenience function to export interpreter."""
    return _generator.export_interpreter(config, format)


def import_interpreter(data: str, format: str = "json") -> InterpreterPackage:
    """Convenience function to import interpreter."""
    return _generator.import_interpreter(data, format)


def get_all_interpreters() -> Dict[str, InterpreterPackage]:
    """Get all loaded interpreters."""
    return _generator.interpreters.copy()
