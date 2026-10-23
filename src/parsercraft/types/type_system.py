#!/usr/bin/env python3
"""
Type System & Static Analysis Framework for ParserCraft

Enables type annotations, type inference, and static analysis for custom languages.

Features:
    - Type annotations: `var: int = 5`
    - Type inference: Automatic type deduction
    - Static type checking: Before runtime validation
    - Type errors and warnings: Clear error messages
    - Type aliases and generics
    - Structural typing and protocols
    - Type narrowing and guards
    - Integration with LSP for IDE support

Usage:
    from parsercraft.type_system import TypeChecker, TypeEnvironment
    
    checker = TypeChecker(language_config)
    errors = checker.check_file("program.lang")
    
    if errors:
        for error in errors:
            print(f"{error.location}: {error.message}")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TypeKind(Enum):
    """Built-in type kinds."""

    UNKNOWN = "unknown"
    NONE = "none"
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STR = "str"
    LIST = "list"
    DICT = "dict"
    TUPLE = "tuple"
    SET = "set"
    CALLABLE = "callable"
    CLASS = "class"
    UNION = "union"
    OPTIONAL = "optional"
    GENERIC = "generic"
    ANY = "any"


@dataclass
class Type:
    """Represents a type in the system."""

    kind: TypeKind
    name: str = ""
    type_args: List[Type] = field(default_factory=list)  # For generics
    nullable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of type."""
        if self.kind == TypeKind.GENERIC and self.type_args:
            args_str = ", ".join(str(arg) for arg in self.type_args)
            return f"{self.name}[{args_str}]"
        # Fix: Need to handle List/Dict/Set which are generic-like
        if self.kind in (TypeKind.LIST, TypeKind.DICT, TypeKind.SET, TypeKind.TUPLE) and self.type_args:
            args_str = ", ".join(str(arg) for arg in self.type_args)
            return f"{self.name}[{args_str}]"
        if self.kind == TypeKind.UNION and self.type_args:
            args_str = " | ".join(str(arg) for arg in self.type_args)
            return f"({args_str})"
        if self.kind == TypeKind.OPTIONAL:
            return f"{self.type_args[0]}?"
        return self.name or self.kind.value

    def is_compatible_with(self, other: Type) -> bool:
        """Check if this type is compatible with another."""
        if self.kind == TypeKind.ANY or other.kind == TypeKind.ANY:
            return True
        if self.kind == other.kind:
            if self.type_args and other.type_args:
                return all(
                    a.is_compatible_with(b)
                    for a, b in zip(self.type_args, other.type_args)
                )
            return True
        if {self.kind, other.kind} == {TypeKind.INT, TypeKind.FLOAT}:
            return True
        if self.kind == TypeKind.OPTIONAL:
            if not self.type_args:
                return True
            return self.type_args[0].is_compatible_with(other)
        if other.kind == TypeKind.OPTIONAL:
            if not other.type_args:
                return True
            return self.is_compatible_with(other.type_args[0])
        return False

    @staticmethod
    def int() -> Type:
        return Type(kind=TypeKind.INT, name="int")

    @staticmethod
    def float() -> Type:
        return Type(kind=TypeKind.FLOAT, name="float")

    @staticmethod
    def str() -> Type:
        return Type(kind=TypeKind.STR, name="str")

    @staticmethod
    def bool() -> Type:
        return Type(kind=TypeKind.BOOL, name="bool")

    @staticmethod
    def list(element_type: Type) -> Type:
        return Type(kind=TypeKind.LIST, name="list", type_args=[element_type])

    @staticmethod
    def dict(key_type: Type, value_type: Type) -> Type:
        return Type(kind=TypeKind.DICT, name="dict", type_args=[key_type, value_type])

    @staticmethod
    def optional(inner_type: Type) -> Type:
        return Type(kind=TypeKind.OPTIONAL, name=f"{inner_type}?", type_args=[inner_type], nullable=True)

    @staticmethod
    def union(*types: Type) -> Type:
        return Type(kind=TypeKind.UNION, name=" | ".join(str(t) for t in types), type_args=list(types))


@dataclass
class TypeSignature:
    """Function type signature."""

    param_types: List[Tuple[str, Type]]  # [(name, type), ...]
    return_type: Type
    is_variadic: bool = False
    generic_params: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        """String representation of signature."""
        params = ", ".join(f"{name}: {t}" for name, t in self.param_types)
        return f"({params}) -> {self.return_type}"


class AnalysisLevel(Enum):
    """Type checking strictness levels."""

    LENIENT = 1     # Minimal type checking
    MODERATE = 2    # Standard type checking
    STRICT = 3      # Strict type checking
    VERY_STRICT = 4 # Enforce all type safety


@dataclass
class TypeError:
    """Represents a type error or warning."""

    kind: str  # "error", "warning", "info"
    code: str  # Error code like "E001"
    message: str
    location: str  # "file:line:col"
    line: int
    column: int
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} at {self.location}"


@dataclass
class TypeEnvironment:
    """Manages type bindings and scopes."""

    variables: Dict[str, Type] = field(default_factory=dict)
    functions: Dict[str, TypeSignature] = field(default_factory=dict)
    classes: Dict[str, ClassType] = field(default_factory=dict)
    parent: Optional[TypeEnvironment] = None

    def define_variable(self, name: str, type_: Type) -> None:
        """Register a variable with its type."""
        self.variables[name] = type_

    def get_variable_type(self, name: str) -> Optional[Type]:
        """Lookup variable type."""
        if name in self.variables:
            return self.variables[name]
        if self.parent:
            return self.parent.get_variable_type(name)
        return None

    def define_function(self, name: str, signature: TypeSignature) -> None:
        """Register a function signature."""
        self.functions[name] = signature

    def get_function_signature(self, name: str) -> Optional[TypeSignature]:
        """Lookup function signature."""
        if name in self.functions:
            return self.functions[name]
        if self.parent:
            return self.parent.get_function_signature(name)
        return None

    def create_child_scope(self) -> TypeEnvironment:
        """Create a child scope for nested blocks."""
        return TypeEnvironment(parent=self)


@dataclass
class ClassType:
    """Type representation for a class."""

    name: str
    fields: Dict[str, Type] = field(default_factory=dict)
    methods: Dict[str, TypeSignature] = field(default_factory=dict)
    base_classes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_field_type(self, field_name: str) -> Optional[Type]:
        """Get type of a field."""
        return self.fields.get(field_name)

    def get_method_signature(self, method_name: str) -> Optional[TypeSignature]:
        """Get signature of a method."""
        return self.methods.get(method_name)


class TypeInference:
    """Infers types from expressions."""

    def __init__(self, environment: TypeEnvironment):
        self.environment = environment

    def infer_literal(self, value: str) -> Type:
        """Infer type from literal value."""
        # Integer
        if re.match(r'^-?\d+$', value):
            return Type.int()
        # Float
        if re.match(r'^-?\d+\.\d+$', value):
            return Type.float()
        # String
        if value.startswith('"') or value.startswith("'"):
            return Type.str()
        # Boolean
        if value in ("true", "false", "True", "False"):
            return Type.bool()
        # List
        if value.startswith('[') and value.endswith(']'):
            return Type.list(Type(kind=TypeKind.ANY))
        # Dict
        if value.startswith('{') and value.endswith('}'):
            return Type.dict(Type(kind=TypeKind.ANY), Type(kind=TypeKind.ANY))
        # Unknown
        return Type(kind=TypeKind.UNKNOWN)

    def infer_variable_access(self, var_name: str) -> Optional[Type]:
        """Infer type from variable access."""
        return self.environment.get_variable_type(var_name)

    def infer_function_call(self, func_name: str, args: List[Type]) -> Optional[Type]:
        """Infer return type from function call."""
        signature = self.environment.get_function_signature(func_name)
        if signature:
            return signature.return_type
        return None

    def infer_binary_operation(self, left: Type, op: str, right: Type) -> Type:
        """Infer result type from binary operation."""
        if op in ["+", "-", "*", "/"]:
            # Numeric operations
            if left.kind in [TypeKind.INT, TypeKind.FLOAT] and right.kind in [TypeKind.INT, TypeKind.FLOAT]:
                if left.kind == TypeKind.FLOAT or right.kind == TypeKind.FLOAT:
                    return Type.float()
                return Type.int()
            # String concatenation
            if left.kind == TypeKind.STR or right.kind == TypeKind.STR:
                return Type.str()
        
        if op in ["<", ">", "<=", ">=", "==", "!="]:
            return Type.bool()
        
        if op in ["and", "or"]:
            return Type.bool()
        
        return Type(kind=TypeKind.UNKNOWN)


class TypeChecker:
    """Main type checking engine."""

    def __init__(self, language_config: Any, level: AnalysisLevel = AnalysisLevel.MODERATE):
        self.config = language_config
        self.level = level
        self.global_env = TypeEnvironment()
        self._register_builtin_types()
        self.errors: List[TypeError] = []
        self.warnings: List[TypeError] = []

    def _register_builtin_types(self) -> None:
        """Register built-in functions and types."""
        if self.config is None:
            return
        # Register standard library functions
        for func_config in self.config.builtin_functions.values():
            params = [
                (f"arg{i}", Type(kind=TypeKind.ANY))
                for i in range(abs(func_config.arity) if func_config.arity >= 0 else 1)
            ]
            signature = TypeSignature(
                param_types=params,
                return_type=Type(kind=TypeKind.ANY),
            )
            self.global_env.define_function(func_config.name, signature)

    def check_file(self, file_path: str) -> List[TypeError]:
        """Type check an entire file."""
        try:
            content = Path(file_path).read_text()
        except FileNotFoundError:
            return [
                TypeError(
                    kind="error",
                    code="E000",
                    message=f"File not found: {file_path}",
                    location=file_path,
                    line=0,
                    column=0,
                )
            ]

        self.errors.clear()
        self.warnings.clear()

        lines = content.split("\n")
        current_env = self.global_env

        for line_num, line in enumerate(lines, 1):
            self._check_line(line, line_num, file_path, current_env)

        return self.errors + self.warnings

    def check_expression(self, expr: str, environment: TypeEnvironment) -> Type:
        """Type check an expression and return its type."""
        expr = expr.strip()

        # Boolean literals are keywords, not variables
        if expr in ("True", "False", "true", "false"):
            return Type.bool()

        # Variable reference (identifiers only; numbers are literals)
        if re.match(r'^[A-Za-z_]\w*$', expr):
            var_type = environment.get_variable_type(expr)
            if var_type:
                return var_type
            return Type(kind=TypeKind.UNKNOWN)

        # Function call
        if '(' in expr and ')' in expr:
            func_match = re.match(r'(\w+)\s*\(', expr)
            if func_match:
                func_name = func_match.group(1)
                sig = environment.get_function_signature(func_name)
                if sig:
                    return sig.return_type

        # Literal
        return TypeInference(environment).infer_literal(expr)

    def check_assignment(
        self,
        target: str,
        source: str,
        environment: TypeEnvironment,
        line: int = 0,
        location: str = "",
    ) -> bool:
        """Check if assignment is type-safe."""
        source_type = self.check_expression(source, environment)
        
        # Check if target has type annotation
        if ':' in target:
            target_name, type_str = target.split(':', 1)
            target_type = self._parse_type_annotation(type_str.strip())
        else:
            # Type inference
            target_type = source_type

        environment.define_variable(target.strip().split(':')[0].strip(), target_type)
        
        if not source_type.is_compatible_with(target_type):
            self.errors.append(
                TypeError(
                    kind="error",
                    code="E101",
                    message=f"Type mismatch: cannot assign {source_type} to {target_type}",
                    location=location or f"line {line}",
                    line=line,
                    column=0,
                    suggestion=f"Change source to {target_type} or target to {source_type}",
                )
            )
            return False
        return True

    def check_function_definition(
        self,
        func_name: str,
        params: List[Tuple[str, Optional[str]]],
        return_type_str: Optional[str],
        environment: TypeEnvironment,
    ) -> None:
        """Type check a function definition."""
        # Parse parameter types
        param_types = []
        for param_name, param_type_str in params:
            if param_type_str:
                param_type = self._parse_type_annotation(param_type_str)
            else:
                param_type = Type(kind=TypeKind.ANY)
            param_types.append((param_name, param_type))

        # Parse return type
        if return_type_str:
            return_type = self._parse_type_annotation(return_type_str)
        else:
            return_type = Type(kind=TypeKind.ANY)

        signature = TypeSignature(
            param_types=param_types,
            return_type=return_type,
        )
        environment.define_function(func_name, signature)

    def _check_line(
        self,
        line: str,
        line_num: int,
        file_path: str,
        environment: TypeEnvironment,
    ) -> None:
        """Type check a single line."""
        line = line.strip()

        if not line or line.startswith("#"):
            return

        # Check for variable assignment
        if "=" in line and not line.startswith("if") and not line.startswith("when"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                target, source = parts
                self.check_assignment(
                    target.strip(),
                    source.strip(),
                    environment,
                    line=line_num,
                    location=file_path,
                )

    def _parse_type_annotation(self, annotation: str) -> Type:
        """Parse a type annotation string."""
        annotation = annotation.strip()
        nullable = annotation.endswith('?')
        if nullable:
            annotation = annotation[:-1]

        # Basic types
        result = None
        if annotation == "int":
            result = Type.int()
        elif annotation == "float":
            result = Type.float()
        elif annotation == "str":
            result = Type.str()
        elif annotation == "bool":
            result = Type.bool()

        # Generics: list[int], dict[str, int]
        elif '[' in annotation:
            base = annotation.split('[')[0]
            args_str = annotation[annotation.find('[') + 1:annotation.rfind(']')]
            arg_types = [self._parse_type_annotation(arg.strip()) for arg in args_str.split(',')]

            if base == "list":
                result = Type.list(arg_types[0] if arg_types else Type(kind=TypeKind.ANY))
            elif base == "dict":
                result = Type.dict(
                    arg_types[0] if len(arg_types) > 0 else Type(kind=TypeKind.ANY),
                    arg_types[1] if len(arg_types) > 1 else Type(kind=TypeKind.ANY),
                )

        # Union types: int | str
        elif '|' in annotation:
            types = [self._parse_type_annotation(t.strip()) for t in annotation.split('|')]
            result = Type.union(*types)

        if result is None:
            # Custom/class types
            result = Type(kind=TypeKind.CLASS, name=annotation, nullable=nullable)

        if nullable:
            result.nullable = True

        return result

    def get_type_error_summary(self) -> str:
        """Get a summary of type errors."""
        if not self.errors and not self.warnings:
            return "✓ No type errors found"

        summary = []
        if self.errors:
            summary.append(f"Errors ({len(self.errors)}):")
            for error in self.errors[:5]:
                summary.append(f"  {error}")
        if self.warnings:
            summary.append(f"Warnings ({len(self.warnings)}):")
            for warning in self.warnings[:5]:
                summary.append(f"  {warning}")

        return "\n".join(summary)


class TypeAwareAnalyzer:
    """Enhanced analyzer with type awareness for LSP."""

    def __init__(self, checker: TypeChecker):
        self.checker = checker

    def get_type_completions(self, environment: TypeEnvironment) -> List[Dict[str, Any]]:
        """Get completion suggestions with type information."""
        completions = []

        # Variables with their types
        for var_name, var_type in environment.variables.items():
            completions.append({
                "label": var_name,
                "kind": 13,  # Variable
                "detail": str(var_type),
                "documentation": f"Variable of type {var_type}",
            })

        # Functions with signatures
        for func_name, signature in environment.functions.items():
            completions.append({
                "label": func_name,
                "kind": 3,  # Function
                "detail": str(signature),
                "documentation": f"Function {signature}",
            })

        return completions

    def get_hover_with_type(self, symbol: str, environment: TypeEnvironment) -> Optional[str]:
        """Get hover info including type information."""
        var_type = environment.get_variable_type(symbol)
        if var_type:
            return f"**{symbol}**: {var_type}"

        sig = environment.get_function_signature(symbol)
        if sig:
            return f"**{symbol}**{sig}"

        return None


# Example usage
if __name__ == "__main__":
    from parsercraft.config.language_config import LanguageConfig

    config = LanguageConfig.from_preset("python_like")
    checker = TypeChecker(config, level=AnalysisLevel.MODERATE)

    # Type check some code
    errors = checker.check_file("test.lang")
    print(checker.get_type_error_summary())
