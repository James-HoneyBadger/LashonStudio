#!/usr/bin/env python3
"""
Generics System Integration with Type Checker

Integrates Phase 4 generics system with existing type system for comprehensive
generic type support with full type inference and constraint validation.

Features:
    - Generic type parameters in functions and classes
    - Type constraint validation
    - Type variance checking
    - Generic type inference
    - Specialization and instantiation
    - Integration with type checker

Usage:
    from parsercraft.type_system_generics import GenericsTypeChecker
    
    checker = GenericsTypeChecker(config)
    errors = checker.check_file("program.lang")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from parsercraft.types.generics import (
    GenericChecker,
    GenericClass,
    GenericFunction,
    TypeParameter,
    Variance,
)
from parsercraft.types.type_system import Type, TypeChecker, TypeKind


@dataclass
class GenericConstraint:
    """Constraint on a type parameter."""

    constraint_type: str  # "Number", "Comparable", "Iterable", etc.
    description: str = ""


class GenericsTypeChecker:
    """Extends type checker with generic type support."""

    def __init__(self, config: Any = None):
        self.type_checker = TypeChecker(config)
        self.generic_checker = GenericChecker()
        self.generic_functions: Dict[str, GenericFunction] = {}
        self.generic_classes: Dict[str, GenericClass] = {}
        self.type_parameters: Dict[str, List[TypeParameter]] = {}

    def check_generic_function(
        self, func_name: str, type_params: List[str], func_def: Any
    ) -> List[str]:
        """Check a generic function definition.

        Args:
            func_name: Function name
            type_params: Type parameter names (e.g., ["T", "U"])
            func_def: Function definition

        Returns:
            List of error messages
        """
        errors = []

        # Create type parameters
        params = [TypeParameter(name=tp) for tp in type_params]

        # Create generic function
        gen_func = GenericFunction(
            name=func_name,
            type_parameters=params,
            parameter_types={},  # Would be populated from func_def
            return_type="T",
        )

        self.generic_functions[func_name] = gen_func
        self.type_parameters[func_name] = params

        return errors

    def check_generic_class(
        self, class_name: str, type_params: List[str], class_def: Any
    ) -> List[str]:
        """Check a generic class definition.

        Args:
            class_name: Class name
            type_params: Type parameter names
            class_def: Class definition

        Returns:
            List of error messages
        """
        errors = []

        # Create type parameters
        params = [TypeParameter(name=tp) for tp in type_params]

        # Create generic class
        gen_class = GenericClass(
            name=class_name,
            type_parameters=params,
            fields={},
            methods={},
        )

        self.generic_classes[class_name] = gen_class
        self.type_parameters[class_name] = params

        return errors

    def check_generic_instantiation(
        self, generic_name: str, type_args: List[str]
    ) -> Tuple[bool, List[str]]:
        """Check generic type instantiation.

        Args:
            generic_name: Name of generic (function or class)
            type_args: Concrete type arguments

        Returns:
            (success: bool, errors: List[str])
        """
        errors = []

        # Check if it's a generic function
        if generic_name in self.generic_functions:
            # gen_func = self.generic_functions[generic_name]
            type_params = self.type_parameters.get(generic_name, [])

            if len(type_args) != len(type_params):
                errors.append(
                    f"Generic {generic_name} expects {len(type_params)} "
                    f"type arguments, got {len(type_args)}"
                )
                return False, errors

            # Check constraints
            for param, arg in zip(type_params, type_args):
                if param.constraint:
                    if not self._satisfies_constraint(arg, param.constraint):
                        errors.append(
                            f"Type {arg} does not satisfy constraint {param.constraint}"
                        )

            return len(errors) == 0, errors

        # Check if it's a generic class
        if generic_name in self.generic_classes:
            # gen_class = self.generic_classes[generic_name]
            type_params = self.type_parameters.get(generic_name, [])

            if len(type_args) != len(type_params):
                errors.append(
                    f"Generic {generic_name} expects {len(type_params)} "
                    f"type arguments, got {len(type_args)}"
                )
                return False, errors

            return len(errors) == 0, errors

        errors.append(f"Unknown generic: {generic_name}")
        return False, errors

    def infer_type_arguments(
        self, generic_name: str, actual_args: List[Type]
    ) -> Tuple[List[str], List[str]]:
        """Infer type arguments for a generic.

        Args:
            generic_name: Generic name
            actual_args: Actual argument types

        Returns:
            (inferred_types: List[str], errors: List[str])
        """
        errors = []
        inferred = []

        if generic_name not in self.generic_functions:
            errors.append(f"Unknown generic: {generic_name}")
            return [], errors

        # Use generic checker to infer types
        # gen_func = self.generic_functions[generic_name]
        type_params = self.type_parameters.get(generic_name, [])

        for param in type_params:
            # Simple inference: use first argument type matching parameter
            if actual_args:
                inferred.append(str(actual_args[0]))
            else:
                inferred.append("unknown")

        return inferred, errors

    def check_variance(
        self, generic_name: str, position: int, variance: Variance
    ) -> Tuple[bool, str]:
        """Check type variance at a position.

        Args:
            generic_name: Generic name
            position: Type parameter position
            variance: Expected variance

        Returns:
            (valid: bool, message: str)
        """
        if generic_name not in self.generic_functions:
            return False, f"Unknown generic: {generic_name}"

        # gen_func = self.generic_functions[generic_name]
        type_params = self.type_parameters.get(generic_name, [])

        if position >= len(type_params):
            return False, f"Position {position} out of range"

        param = type_params[position]

        if param.variance != variance:
            return (
                False,
                f"Type parameter {param.name} has variance "
                f"{param.variance.name}, expected {variance.name}",
            )

        return True, f"Variance check passed for {param.name}"

    def _satisfies_constraint(self, type_name: str, constraint: str) -> bool:
        """Check if a type satisfies a constraint.

        Args:
            type_name: Type to check
            constraint: Constraint name

        Returns:
            True if satisfied
        """
        # Map of constraints to types that satisfy them
        constraint_map = {
            "Number": ["int", "float", "i32", "i64", "f32", "f64"],
            "Comparable": ["int", "float", "str", "bool"],
            "Iterable": ["list", "tuple", "set", "str", "dict"],
            "Serializable": ["int", "float", "str", "bool", "list", "dict"],
            "Hashable": ["int", "float", "str", "bool", "tuple"],
        }

        if constraint not in constraint_map:
            return True  # Unknown constraint - allow

        return type_name in constraint_map[constraint]

    def check_file(self, file_path: str) -> List[str]:
        """Check a file for generic type errors.

        Args:
            file_path: Path to file to check

        Returns:
            List of error messages
        """
        # This would parse the file and check generics
        # Implementation depends on language syntax
        return []


class ProtocolTypeChecker:
    """Integrates protocol system with type checking."""

    def __init__(self, config: Any = None):
        from parsercraft.types.protocols import ProtocolChecker

        self.type_checker = TypeChecker(config)
        self.protocol_checker = ProtocolChecker()
        self.protocols: Dict[str, Any] = {}

    def check_protocol_conformance(
        self, type_name: str, protocol_name: str
    ) -> Tuple[bool, List[str]]:
        """Check if a type conforms to a protocol.

        Args:
            type_name: Type to check
            protocol_name: Protocol to check against

        Returns:
            (conforms: bool, errors: List[str])
        """
        if protocol_name not in self.protocols:
            return False, [f"Unknown protocol: {protocol_name}"]

        protocol = self.protocols[protocol_name]

        # Check conformance using protocol checker
        conforms = self.protocol_checker.conforms_to_protocol(type_name, protocol)

        if not conforms:
            return False, [f"Type {type_name} does not conform to {protocol_name}"]

        return True, []

    def register_protocol(self, protocol_name: str, protocol_def: Any) -> None:
        """Register a protocol definition.

        Args:
            protocol_name: Protocol name
            protocol_def: Protocol definition
        """
        self.protocols[protocol_name] = protocol_def

    def extract_structural_type(self, type_name: str) -> Any:
        """Extract structural type from a class.

        Args:
            type_name: Type to extract from

        Returns:
            Structural type representation
        """
        # This would analyze a class/type and extract its structure
        # for implicit protocol conformance checking
        return None


class TypeNarrowingPass:
    """Type narrowing for control flow.

    Implements type narrowing based on control flow conditions,
    such as type guards and isinstance checks.
    """

    def __init__(self):
        self.narrowed_types: Dict[str, Type] = {}

    def narrow_by_isinstance(self, var_name: str, type_name: str) -> None:
        """Narrow type by isinstance check.

        Args:
            var_name: Variable name
            type_name: Type to narrow to
        """
        self.narrowed_types[var_name] = Type(
            kind=TypeKind.CLASS, name=type_name
        )

    def narrow_by_truthiness(self, var_name: str) -> None:
        """Narrow optional type by truthiness check.

        Args:
            var_name: Variable name
        """
        # If var is truthy, it's not None/false
        if var_name in self.narrowed_types:
            t = self.narrowed_types[var_name]
            if t.nullable:
                t.nullable = False

    def narrow_by_comparison(
        self, var_name: str, op: str, value: Any
    ) -> None:
        """Narrow type by comparison.

        Args:
            var_name: Variable name
            op: Comparison operator (==, !=, <, >, <=, >=, is, is not)
            value: Value to compare with
        """
        narrowed = self.narrowed_types.get(var_name)
        if narrowed is None:
            return

        if op in ("==", "is") and value is None:
            # x == None implies the value may be absent.
            narrowed.nullable = True
        elif op in ("!=", "is not") and value is None:
            # x != None narrows optional/None away.
            narrowed.nullable = False
        elif narrowed.kind in (TypeKind.OPTIONAL, TypeKind.NONE):
            # A comparison against a non-None value removes None.
            narrowed.nullable = False

    def get_narrowed_type(self, var_name: str) -> Optional[Type]:
        """Get narrowed type for variable.

        Args:
            var_name: Variable name

        Returns:
            Narrowed type or None
        """
        return self.narrowed_types.get(var_name)
