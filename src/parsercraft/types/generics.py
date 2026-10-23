#!/usr/bin/env python3
"""
Generic Types System for ParserCraft

Extends the type system with support for generic types with constraints.

Features:
    - Generic type definitions: List[T], Dict[K, V]
    - Type constraints: T extends Number
    - Type bounds: Covariance and contravariance
    - Generic function signatures
    - Type parameter inference
    - Generic class definitions

Usage:
    from parsercraft.generics import GenericType, TypeParameter, GenericChecker
    
    # Define a generic type
    T = TypeParameter("T")
    list_type = GenericType("List", [T])
    
    # Use with constraints
    Number = TypeParameter("T", constraint="Number")
    
    # Check generic compatibility
    checker = GenericChecker()
    checker.check_generic_assignment(list_of_int, list_type)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class Variance(Enum):
    """Type parameter variance."""
    INVARIANT = "invariant"
    COVARIANT = "covariant"
    CONTRAVARIANT = "contravariant"


@dataclass
class TypeParameter:
    """Represents a generic type parameter."""

    name: str
    constraint: Optional[str] = None  # e.g., "Number", "Comparable"
    bound: Optional[str] = None  # Upper bound
    variance: Variance = Variance.INVARIANT
    default: Optional[str] = None  # Default type if not specified

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, TypeParameter):
            return self.name == other.name
        return False

    def __repr__(self) -> str:
        if self.constraint:
            return f"{self.name} extends {self.constraint}"
        return self.name


@dataclass
class GenericType:
    """Represents a generic type with type parameters."""

    name: str
    parameters: List[TypeParameter] = field(default_factory=list)
    arguments: List[str] = field(default_factory=list)  # Concrete type arguments

    def __repr__(self) -> str:
        if self.arguments:
            args = ", ".join(self.arguments)
            return f"{self.name}[{args}]"
        if self.parameters:
            params = ", ".join(str(p) for p in self.parameters)
            return f"{self.name}[{params}]"
        return self.name

    def is_generic(self) -> bool:
        """Check if this type has unbound parameters."""
        return len(self.parameters) > 0 and len(self.arguments) == 0

    def bind(self, type_args: Dict[str, str]) -> GenericType:
        """Bind type parameters to concrete types."""
        bound_args = [
            type_args.get(param.name, param.default or "Any")
            for param in self.parameters
        ]
        return GenericType(
            name=self.name,
            parameters=self.parameters,
            arguments=bound_args,
        )


@dataclass
class GenericFunction:
    """Represents a function with generic type parameters."""

    name: str
    type_parameters: List[TypeParameter]
    parameter_types: Dict[str, str]  # parameter name -> type
    return_type: str
    body: Optional[str] = None

    def __repr__(self) -> str:
        params = ", ".join(str(p) for p in self.type_parameters)
        sig = ", ".join(f"{k}: {v}" for k, v in self.parameter_types.items())
        return f"function {self.name}<{params}>({sig}) -> {self.return_type}"

    def instantiate(self, type_args: Dict[str, str]) -> "GenericFunction":
        """Create concrete function instance with bound types."""
        new_params = {
            k: type_args.get(v, v) for k, v in self.parameter_types.items()
        }
        new_return = type_args.get(self.return_type, self.return_type)
        return GenericFunction(
            name=self.name,
            type_parameters=self.type_parameters,
            parameter_types=new_params,
            return_type=new_return,
            body=self.body,
        )


@dataclass
class GenericClass:
    """Represents a class with generic type parameters."""

    name: str
    type_parameters: List[TypeParameter]
    fields: Dict[str, str] = field(default_factory=dict)  # field -> type
    methods: Dict[str, GenericFunction] = field(default_factory=dict)

    def __repr__(self) -> str:
        params = ", ".join(str(p) for p in self.type_parameters)
        return f"class {self.name}<{params}>"

    def instantiate(self, type_args: Dict[str, str]) -> "GenericClass":
        """Create concrete class instance with bound types."""
        new_fields = {k: type_args.get(v, v) for k, v in self.fields.items()}
        new_methods = {
            k: v.instantiate(type_args) for k, v in self.methods.items()
        }
        return GenericClass(
            name=self.name,
            type_parameters=self.type_parameters,
            fields=new_fields,
            methods=new_methods,
        )


class GenericChecker:
    """Validates generic type compatibility and constraints."""

    def __init__(self):
        self.constraints_map: Dict[str, Set[str]] = {
            "Number": {"int", "float"},
            "Comparable": {"int", "float", "str"},
            "Iterable": {"list", "tuple", "set", "dict"},
            "Serializable": {"int", "float", "str", "bool"},
        }

    def check_constraint(
        self, type_param: TypeParameter, concrete_type: str
    ) -> bool:
        """Check if concrete type satisfies parameter constraint."""
        if not type_param.constraint:
            return True

        allowed = self.constraints_map.get(type_param.constraint, set())
        return concrete_type in allowed or concrete_type == "Any"

    def check_generic_assignment(
        self, source: GenericType, target: GenericType
    ) -> bool:
        """Check if source generic type can be assigned to target."""
        if source.name != target.name:
            return False

        if len(source.arguments) != len(target.arguments):
            return False

        for i, (src_arg, tgt_arg) in enumerate(
            zip(source.arguments, target.arguments)
        ):
            param = target.parameters[i] if i < len(target.parameters) else None
            if param and not self.check_constraint(param, src_arg):
                return False

            # Check variance
            if param and param.variance == Variance.COVARIANT:
                if src_arg != tgt_arg and src_arg != "Any":
                    return False
            elif param and param.variance == Variance.CONTRAVARIANT:
                if src_arg != tgt_arg and tgt_arg != "Any":
                    return False
            elif param and param.variance == Variance.INVARIANT:
                if src_arg != tgt_arg and src_arg != "Any" and tgt_arg != "Any":
                    return False

        return True

    def infer_type_arguments(
        self, generic_func: GenericFunction, actual_args: Dict[str, str]
    ) -> Optional[Dict[str, str]]:
        """Infer type arguments from actual argument types."""
        inferred: Dict[str, str] = {}

        for param_name, expected_type in generic_func.parameter_types.items():
            if param_name not in actual_args:
                continue

            actual_type = actual_args[param_name]

            # Simple inference: if expected is T and actual is int, infer T=int
            for type_param in generic_func.type_parameters:
                if expected_type == type_param.name:
                    if type_param.name in inferred:
                        if inferred[type_param.name] != actual_type:
                            return None  # Conflicting inference
                    if not self.check_constraint(type_param, actual_type):
                        return None

                    inferred[type_param.name] = actual_type

        # Check all type parameters are bound
        for type_param in generic_func.type_parameters:
            if type_param.name not in inferred:
                if type_param.default:
                    inferred[type_param.name] = type_param.default
                else:
                    return None

        return inferred

    def validate_generic_class(self, generic_class: GenericClass) -> List[str]:
        """Validate generic class definition."""
        errors: List[str] = []

        # Check type parameters are used
        param_names = {p.name for p in generic_class.type_parameters}
        used_names: Set[str] = set()

        for field_type in generic_class.fields.values():
            used_names.update(p for p in param_names if p in field_type)

        for method in generic_class.methods.values():
            for param_type in method.parameter_types.values():
                used_names.update(p for p in param_names if p in param_type)
            used_names.update(p for p in param_names if p in method.return_type)

        unused = param_names - used_names
        if unused:
            errors.append(f"Unused type parameters: {unused}")

        # Check constraints are valid
        valid_constraints = set(self.constraints_map.keys()) | {"Any"}
        for type_param in generic_class.type_parameters:
            if type_param.constraint and type_param.constraint not in valid_constraints:
                errors.append(f"Unknown constraint: {type_param.constraint}")

        return errors
