"""Packaging — docs, registry, VS Code extension, distribution."""

from .documentation_generator import DocumentationGenerator
from .package_registry import Package, PackageRegistry

__all__ = [
    "PackageRegistry",
    "Package",
    "DocumentationGenerator",
]
