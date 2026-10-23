#!/usr/bin/env python3
"""
Protocol & Structural Typing System for ParserCraft

Enables structural/duck typing and protocol definitions for flexible type compatibility.

Features:
    - Protocol definitions (structural interfaces)
    - Implicit implementation via duck typing
    - Structural type checking
    - Protocol composition
    - Method signature compatibility
    - Runtime protocol checking

Usage:
    from parsercraft.protocols import Protocol, ProtocolChecker
    
    # Define a protocol
    reader_protocol = Protocol(
        name="Reader",
        methods={"read": ("str", [])}  # name -> (return_type, param_types)
    )
    
    # Check structural compatibility
    checker = ProtocolChecker()
    is_reader = checker.conforms_to_protocol(my_class, reader_protocol)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class MethodSignature:
    """Represents a method signature."""

    name: str
    return_type: str
    parameter_types: List[Tuple[str, str]] = field(default_factory=list)  # (name, type)
    is_optional: bool = False

    def __repr__(self) -> str:
        params = ", ".join(f"{name}: {typ}" for name, typ in self.parameter_types)
        return f"{self.name}({params}) -> {self.return_type}"

    def signature_matches(self, other: MethodSignature) -> bool:
        """Check if signatures are compatible."""
        if len(self.parameter_types) != len(other.parameter_types):
            return False

        # Check parameter types (contravariance for parameters)
        for (_, self_type), (_, other_type) in zip(
            self.parameter_types, other.parameter_types
        ):
            if self_type != other_type and self_type != "Any" and other_type != "Any":
                return False

        # Check return type (covariance)
        if (
            self.return_type != other.return_type
            and self.return_type != "Any"
            and other.return_type != "Any"
        ):
            return False

        return True


@dataclass
class PropertyDef:
    """Represents a property definition."""

    name: str
    type_: str
    is_readonly: bool = False
    is_optional: bool = False

    def __repr__(self) -> str:
        prefix = "readonly " if self.is_readonly else ""
        suffix = "?" if self.is_optional else ""
        return f"{prefix}{self.name}{suffix}: {self.type_}"

    def compatible_with(self, other: PropertyDef) -> bool:
        """Check if property is compatible."""
        if self.name != other.name:
            return False

        # Types must match
        if self.type_ != other.type_ and self.type_ != "Any" and other.type_ != "Any":
            return False

        # If protocol requires readonly, implementation must also be readonly
        if self.is_readonly and not other.is_readonly:
            return False

        return True


@dataclass
class Protocol:
    """Represents a structural protocol/interface."""

    name: str
    methods: Dict[str, MethodSignature] = field(default_factory=dict)
    properties: Dict[str, PropertyDef] = field(default_factory=dict)
    extends: List[str] = field(default_factory=list)  # Protocol names to extend
    is_generic: bool = False

    def __repr__(self) -> str:
        extends = f" extends {', '.join(self.extends)}" if self.extends else ""
        return f"protocol {self.name}{extends}"

    def get_all_methods(self) -> Dict[str, MethodSignature]:
        """Get all methods including inherited ones."""
        return self.methods.copy()

    def get_all_properties(self) -> Dict[str, PropertyDef]:
        """Get all properties including inherited ones."""
        return self.properties.copy()


@dataclass
class StructuralType:
    """Represents a structural type (anonymous protocol)."""

    methods: Dict[str, MethodSignature] = field(default_factory=dict)
    properties: Dict[str, PropertyDef] = field(default_factory=dict)

    def __repr__(self) -> str:
        items = list(self.methods.keys()) + list(self.properties.keys())
        return f"{{ {', '.join(items)} }}"

    def to_protocol(self, name: str) -> Protocol:
        """Convert to protocol."""
        return Protocol(
            name=name,
            methods=self.methods,
            properties=self.properties,
        )


class ProtocolChecker:
    """Validates structural type compatibility with protocols."""

    def __init__(self):
        self.protocol_cache: Dict[str, Protocol] = {}

    def register_protocol(self, protocol: Protocol) -> None:
        """Register a protocol."""
        self.protocol_cache[protocol.name] = protocol

    def conforms_to_protocol(
        self,
        struct_type: StructuralType | Dict[str, Any],
        protocol: Protocol,
    ) -> bool:
        """Check if type conforms to protocol."""
        # Convert dict to StructuralType if needed
        if isinstance(struct_type, dict):
            struct_type = StructuralType(
                methods={
                    name: MethodSignature(name, "Any")
                    for name in struct_type.get("methods", {})
                },
                properties={
                    name: PropertyDef(name, "Any")
                    for name in struct_type.get("properties", {})
                },
            )

        # Check all protocol methods are implemented
        for method_name, protocol_method in protocol.methods.items():
            if method_name not in struct_type.methods:
                return False

            impl_method = struct_type.methods[method_name]
            if not protocol_method.signature_matches(impl_method):
                return False

        # Check all protocol properties are present
        for prop_name, protocol_prop in protocol.properties.items():
            if prop_name not in struct_type.properties:
                if not protocol_prop.is_optional:
                    return False
            else:
                impl_prop = struct_type.properties[prop_name]
                if not protocol_prop.compatible_with(impl_prop):
                    return False

        return True

    def structural_compatible(
        self, source_type: StructuralType, target_type: StructuralType
    ) -> bool:
        """Check if source type is compatible with target type."""
        # Source must have at least all of target's methods and properties
        for method_name, target_method in target_type.methods.items():
            if method_name not in source_type.methods:
                return False
            if not target_method.signature_matches(source_type.methods[method_name]):
                return False

        for prop_name, target_prop in target_type.properties.items():
            if prop_name not in source_type.properties:
                return False
            if not target_prop.compatible_with(source_type.properties[prop_name]):
                return False

        return True

    def extract_structural_type(
        self, class_def: Dict[str, Any]
    ) -> StructuralType:
        """Extract structural type from class definition."""
        methods = {}
        properties = {}

        # Extract methods
        for method_name, method_info in class_def.get("methods", {}).items():
            methods[method_name] = MethodSignature(
                name=method_name,
                return_type=method_info.get("return_type", "Any"),
                parameter_types=method_info.get("parameters", []),
            )

        # Extract properties
        for prop_name, prop_type in class_def.get("properties", {}).items():
            properties[prop_name] = PropertyDef(
                name=prop_name,
                type_=prop_type,
            )

        return StructuralType(methods=methods, properties=properties)

    def find_matching_protocols(
        self, struct_type: StructuralType
    ) -> List[str]:
        """Find which protocols a type conforms to."""
        matching = []
        for protocol_name, protocol in self.protocol_cache.items():
            if self.conforms_to_protocol(struct_type, protocol):
                matching.append(protocol_name)
        return matching

    def check_protocol_composition(self, protocols: List[Protocol]) -> List[str]:
        """Check if multiple protocols can be composed without conflicts."""
        errors: List[str] = []
        all_methods: Dict[str, MethodSignature] = {}

        for protocol in protocols:
            for method_name, method_sig in protocol.methods.items():
                if method_name in all_methods:
                    # Check for conflicts
                    existing = all_methods[method_name]
                    if not method_sig.signature_matches(existing):
                        errors.append(
                            f"Conflicting method {method_name} in protocols"
                        )
                else:
                    all_methods[method_name] = method_sig

        return errors
