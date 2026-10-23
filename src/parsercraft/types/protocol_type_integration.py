#!/usr/bin/env python3
"""
Protocol Type System Integration for ParserCraft

Integrates Phase 4 protocols system with existing type system for structural typing
and protocol conformance checking throughout the type checking process.

Features:
    - Protocol registration and validation
    - Structural type compatibility checking
    - Protocol conformance in type assignments
    - Protocol composition validation
    - Implicit implementation via duck typing
    - Integration with type inference engine

Usage:
    from parsercraft.protocol_type_integration import ProtocolTypeIntegration
    
    integration = ProtocolTypeIntegration(type_checker)
    
    # Register protocols
    reader_protocol = Protocol(
        name="Reader",
        methods={"read": MethodSignature("read", "str")}
    )
    integration.register_protocol(reader_protocol)
    
    # Check type compatibility with protocols
    is_compatible = integration.check_type_compatibility(
        type1, type2, check_protocols=True
    )
    
    # Get protocol conformance for a type
    protocols = integration.get_type_protocols(my_class_type)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from parsercraft.types.protocols import (
    MethodSignature,
    PropertyDef,
    Protocol,
    ProtocolChecker,
    StructuralType,
)
from parsercraft.types.type_system import Type, TypeChecker, TypeEnvironment, TypeKind


@dataclass
class ProtocolBinding:
    """Represents a type bound to one or more protocols."""

    type_: Type
    protocols: List[str] = field(default_factory=list)  # Protocol names
    explicit: bool = False  # Explicitly declared vs inferred


@dataclass
class TypeCompatibilityResult:
    """Result of type compatibility check."""

    compatible: bool
    reason: str = ""
    missing_features: List[str] = field(default_factory=list)  # For protocol mismatches
    protocol_violations: List[str] = field(default_factory=list)


class ProtocolTypeIntegration:
    """Integrates protocol system with type checker for structural typing."""

    def __init__(self, type_checker: TypeChecker):
        """Initialize protocol-type integration.

        Args:
            type_checker: The main type checker instance
        """
        self.type_checker = type_checker
        self.protocol_checker = ProtocolChecker()

        # Registry of protocols
        self.protocols: Dict[str, Protocol] = {}

        # Mapping of types to their conforming protocols
        self.type_protocol_bindings: Dict[str, List[str]] = {}

        # Structural type cache (for faster lookups)
        self.structural_types: Dict[str, StructuralType] = {}

    def register_protocol(self, protocol: Protocol) -> None:
        """Register a protocol definition.

        Args:
            protocol: The protocol to register
        """
        self.protocols[protocol.name] = protocol
        self.protocol_checker.register_protocol(protocol)

    def register_protocols_from_config(self, config: Any) -> None:
        """Register protocols from language configuration.

        Args:
            config: Language configuration with protocol definitions
        """
        if not hasattr(config, "protocols"):
            return

        for protocol_def in config.protocols:
            protocol = self._create_protocol_from_def(protocol_def)
            self.register_protocol(protocol)

    def _create_protocol_from_def(self, protocol_def: Dict[str, Any]) -> Protocol:
        """Create a Protocol object from definition.

        Args:
            protocol_def: Dictionary with protocol definition

        Returns:
            Created Protocol instance
        """
        methods = {}
        for method_name, method_info in protocol_def.get("methods", {}).items():
            methods[method_name] = MethodSignature(
                name=method_name,
                return_type=method_info.get("return_type", "Any"),
                parameter_types=method_info.get("parameters", []),
                is_optional=method_info.get("optional", False),
            )

        properties = {}
        for prop_name, prop_info in protocol_def.get("properties", {}).items():
            properties[prop_name] = PropertyDef(
                name=prop_name,
                type_=prop_info.get("type", "Any"),
                is_readonly=prop_info.get("readonly", False),
                is_optional=prop_info.get("optional", False),
            )

        return Protocol(
            name=protocol_def.get("name", ""),
            methods=methods,
            properties=properties,
            extends=protocol_def.get("extends", []),
            is_generic=protocol_def.get("generic", False),
        )

    def check_type_compatibility(
        self,
        source_type: Type,
        target_type: Type,
        check_protocols: bool = True,
        environment: Optional[TypeEnvironment] = None,
    ) -> TypeCompatibilityResult:
        """Check if source type is compatible with target type, including protocols.

        Args:
            source_type: The source type
            target_type: The target type
            check_protocols: Whether to check protocol conformance
            environment: Type environment for context

        Returns:
            TypeCompatibilityResult indicating compatibility and reasons
        """
        # First check basic type compatibility. For classes, require matching names
        # before treating them as compatible so protocol targets can be validated.
        if source_type.kind == target_type.kind == TypeKind.CLASS:
            if source_type.name == target_type.name:
                return TypeCompatibilityResult(compatible=True)
        else:
            if source_type.is_compatible_with(target_type):
                return TypeCompatibilityResult(compatible=True)

        if not check_protocols:
            return TypeCompatibilityResult(
                compatible=False, reason="Type kinds do not match"
            )

        # Check if target is a protocol
        if target_type.name in self.protocols:
            target_protocol = self.protocols[target_type.name]
            return self.check_protocol_conformance(source_type, target_protocol, environment)

        return TypeCompatibilityResult(
            compatible=False, reason="Type kinds do not match"
        )

    def check_protocol_conformance(
        self,
        type_: Type,
        protocol: Protocol,
        environment: Optional[TypeEnvironment] = None,
    ) -> TypeCompatibilityResult:
        """Check if a type conforms to a protocol.

        Args:
            type_: The type to check
            protocol: The protocol to check against
            environment: Type environment for context

        Returns:
            TypeCompatibilityResult indicating conformance and missing features
        """
        # Extract structural type from the type
        struct_type = self.extract_type_structure(type_, environment)

        if not struct_type:
            return TypeCompatibilityResult(
                compatible=False, reason=f"Cannot extract structure from type {type_.name}"
            )

        # Check conformance
        missing = []

        # Check methods
        for method_name, protocol_method in protocol.methods.items():
            if method_name not in struct_type.methods:
                if not protocol_method.is_optional:
                    missing.append(f"method {method_name}")
            else:
                impl_method = struct_type.methods[method_name]
                if not protocol_method.signature_matches(impl_method):
                    missing.append(
                        f"method {method_name} has incompatible signature"
                    )

        # Check properties
        for prop_name, protocol_prop in protocol.properties.items():
            if prop_name not in struct_type.properties:
                if not protocol_prop.is_optional:
                    missing.append(f"property {prop_name}")
            else:
                impl_prop = struct_type.properties[prop_name]
                if not protocol_prop.compatible_with(impl_prop):
                    missing.append(f"property {prop_name} has incompatible type")

        if missing:
            return TypeCompatibilityResult(
                compatible=False,
                reason=f"Type does not conform to protocol {protocol.name}",
                missing_features=missing,
                protocol_violations=[protocol.name],
            )

        return TypeCompatibilityResult(
            compatible=True,
            reason=f"Type conforms to protocol {protocol.name}",
        )

    def extract_type_structure(
        self, type_: Type, environment: Optional[TypeEnvironment] = None
    ) -> Optional[StructuralType]:
        """Extract structural type information from a type.

        Args:
            type_: The type to extract structure from
            environment: Type environment for context

        Returns:
            StructuralType if structure can be extracted, None otherwise
        """
        # Check cache first
        if type_.name in self.structural_types:
            return self.structural_types[type_.name]

        # Try to get class info from environment
        if environment:
            # Look up class definition in environment
            class_info = environment.classes.get(type_.name)
            if class_info:
                struct_type = self.protocol_checker.extract_structural_type(
                    class_info
                )
                self.structural_types[type_.name] = struct_type
                return struct_type

        # For built-in types, return empty structural type
        # (built-in types implicitly satisfy many protocols)
        return StructuralType()

    def get_type_protocols(self, type_: Type) -> List[str]:
        """Get all protocols that a type conforms to.

        Args:
            type_: The type to check

        Returns:
            List of protocol names
        """
        if type_.name in self.type_protocol_bindings:
            return self.type_protocol_bindings[type_.name]

        # Infer protocols from structure
        struct_type = self.extract_type_structure(type_)
        if not struct_type:
            return []

        matching_protocols = self.protocol_checker.find_matching_protocols(struct_type)
        self.type_protocol_bindings[type_.name] = matching_protocols

        return matching_protocols

    def bind_type_to_protocol(
        self, type_: Type, protocol_name: str, explicit: bool = True
    ) -> bool:
        """Bind a type to a protocol (explicit protocol implementation).

        Args:
            type_: The type to bind
            protocol_name: The protocol name
            explicit: Whether this is an explicit binding

        Returns:
            True if binding succeeded, False otherwise
        """
        if protocol_name not in self.protocols:
            return False

        if type_.name not in self.type_protocol_bindings:
            self.type_protocol_bindings[type_.name] = []

        if protocol_name not in self.type_protocol_bindings[type_.name]:
            self.type_protocol_bindings[type_.name].append(protocol_name)

        return True

    def check_protocol_composition(
        self, protocol_names: List[str]
    ) -> Tuple[bool, List[str]]:
        """Check if multiple protocols can be composed without conflicts.

        Args:
            protocol_names: List of protocol names to compose

        Returns:
            Tuple of (success, conflict_list)
        """
        protocols = [self.protocols[name] for name in protocol_names if name in self.protocols]
        errors = self.protocol_checker.check_protocol_composition(protocols)
        return len(errors) == 0, errors

    def check_variable_assignment(
        self,
        var_type: Type,
        value_type: Type,
        environment: Optional[TypeEnvironment] = None,
    ) -> TypeCompatibilityResult:
        """Check if value can be assigned to variable (considering protocols).

        Args:
            var_type: The variable's declared type
            value_type: The value's type
            environment: Type environment for context

        Returns:
            TypeCompatibilityResult
        """
        # Direct compatibility check
        if var_type.is_compatible_with(value_type):
            return TypeCompatibilityResult(compatible=True)

        # Check protocol conformance
        return self.check_type_compatibility(value_type, var_type, True, environment)

    def check_function_argument(
        self,
        param_type: Type,
        arg_type: Type,
        param_name: str = "",
        environment: Optional[TypeEnvironment] = None,
    ) -> TypeCompatibilityResult:
        """Check if argument can satisfy parameter type (considering protocols).

        Args:
            param_type: Parameter's declared type
            arg_type: Argument's type
            param_name: Parameter name for error messages
            environment: Type environment for context

        Returns:
            TypeCompatibilityResult
        """
        result = self.check_type_compatibility(arg_type, param_type, True, environment)

        if not result.compatible and param_name:
            result.reason = f"Argument type incompatible with parameter '{param_name}'"

        return result

    def validate_protocol_methods(self, protocol: Protocol) -> List[str]:
        """Validate a protocol's method signatures for consistency.

        Args:
            protocol: The protocol to validate

        Returns:
            List of validation errors
        """
        errors = []

        # Check for duplicate method names
        method_names = set()
        for method_name in protocol.methods.keys():
            if method_name in method_names:
                errors.append(f"Duplicate method {method_name} in protocol")
            method_names.add(method_name)

        # Check for duplicate property names
        prop_names = set()
        for prop_name in protocol.properties.keys():
            if prop_name in prop_names:
                errors.append(f"Duplicate property {prop_name} in protocol")
            prop_names.add(prop_name)

        # Check for conflicting names between methods and properties
        conflicts = method_names & set(protocol.properties.keys())
        for name in conflicts:
            errors.append(f"Conflicting method and property name: {name}")

        return errors

    def get_protocol_satisfaction_report(
        self, type_: Type, environment: Optional[TypeEnvironment] = None
    ) -> Dict[str, Any]:
        """Get detailed report of which protocols a type satisfies.

        Args:
            type_: The type to analyze
            environment: Type environment for context

        Returns:
            Dictionary with satisfaction details
        """
        report = {
            "type": str(type_),
            "conforming_protocols": [],
            "non_conforming_protocols": [],
            "missing_by_protocol": {},
        }

        struct_type = self.extract_type_structure(type_, environment)
        if not struct_type:
            return report

        # Check each protocol
        for protocol_name, protocol in self.protocols.items():
            result = self.protocol_checker.conforms_to_protocol(struct_type, protocol)

            if result:
                report["conforming_protocols"].append(protocol_name)
            else:
                report["non_conforming_protocols"].append(protocol_name)

                # Find missing features
                missing = []
                for method_name in protocol.methods:
                    if method_name not in struct_type.methods:
                        missing.append(f"method: {method_name}")

                for prop_name in protocol.properties:
                    if prop_name not in struct_type.properties:
                        missing.append(f"property: {prop_name}")

                report["missing_by_protocol"][protocol_name] = missing

        return report

    def enable_protocol_checking(self) -> None:
        """Enable protocol checking in type checker.

        This hooks the protocol checking into the type checker's
        type compatibility checks.
        """
        # Store original method
        original_is_compatible = Type.is_compatible_with

        # Create wrapper that checks protocols
        def is_compatible_with_protocols(self: Type, other: Type) -> bool:
            """Extended compatibility check including protocols."""
            # First try original check
            if original_is_compatible(self, other):
                return True

            # Protocol checking would go here if we have access to integration
            # This is a hook point for future extension
            return False

        # Patch Type class (for demonstration)
        # In production, would modify TypeChecker.check_expression instead
        Type.is_compatible_with = is_compatible_with_protocols

    def generate_protocol_docs(self) -> str:
        """Generate documentation for all registered protocols.

        Returns:
            Markdown documentation string
        """
        docs = "# Registered Protocols\n\n"

        for protocol_name, protocol in self.protocols.items():
            docs += f"## {protocol.name}\n\n"

            if protocol.extends:
                docs += f"**Extends:** {', '.join(protocol.extends)}\n\n"

            if protocol.methods:
                docs += "### Methods\n\n"
                for method_name, method in protocol.methods.items():
                    optional = " (optional)" if method.is_optional else ""
                    docs += f"- `{method}`{optional}\n"
                docs += "\n"

            if protocol.properties:
                docs += "### Properties\n\n"
                for prop_name, prop in protocol.properties.items():
                    docs += f"- `{prop}`\n"
                docs += "\n"

        return docs
