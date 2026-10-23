"""Type system — types, generics, protocols, type checking.

Layering:
    type_system.py              canonical Type/TypeChecker/TypeEnvironment
    generics.py, protocols.py   shared generic/protocol primitives
    type_system_generics.py     integration layer (generics + protocols + narrowing)
    protocol_type_integration.py structural-typing bridge
"""

from .generics import GenericChecker, GenericType, TypeParameter
from .protocol_type_integration import (
    ProtocolBinding,
    ProtocolTypeIntegration,
    TypeCompatibilityResult,
)
from .protocols import Protocol, ProtocolChecker
from .type_system import Type, TypeChecker, TypeEnvironment, TypeKind
from .type_system_generics import (
    GenericsTypeChecker,
    ProtocolTypeChecker,
    TypeNarrowingPass,
)

__all__ = [
    "Type",
    "TypeKind",
    "TypeChecker",
    "TypeEnvironment",
    "Protocol",
    "ProtocolChecker",
    "GenericType",
    "TypeParameter",
    "GenericChecker",
    "GenericsTypeChecker",
    "ProtocolTypeChecker",
    "TypeNarrowingPass",
    "ProtocolBinding",
    "ProtocolTypeIntegration",
    "TypeCompatibilityResult",
]
