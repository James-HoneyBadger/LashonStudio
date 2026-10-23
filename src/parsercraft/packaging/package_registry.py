#!/usr/bin/env python3
"""
Package Registry System for ParserCraft

Enables package management with version constraints and dependency resolution.

Features:
    - Package registry (local and remote)
    - Version constraint resolution (semver)
    - Dependency graph analysis
    - Package publishing
    - Lock file management
    - Integrity verification

Usage:
    from parsercraft.package_registry import PackageRegistry, Package
    
    registry = PackageRegistry()
    registry.register_local("./packages")
    
    pkg = registry.resolve("math-lib", "^1.0.0")
    deps = registry.resolve_all_dependencies("myapp")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class VersionOp(Enum):
    """Version constraint operators."""

    EXACT = "=="
    GREATER = ">"
    GREATER_EQUAL = ">="
    LESS = "<"
    LESS_EQUAL = "<="
    CARET = "^"  # Compatible with version (minor compatible)
    TILDE = "~"  # Approximately equivalent


@dataclass
class Version:
    """Semantic version representation."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    metadata: Optional[str] = None

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.metadata:
            version += f"+{self.metadata}"
        return version

    def _release(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    @staticmethod
    def _prerelease_key(prerelease: str) -> tuple:
        key = []
        for part in prerelease.split("."):
            key.append((0, int(part)) if part.isdigit() else (1, part))
        return tuple(key)

    def __lt__(self, other: Version) -> bool:
        if self._release() != other._release():
            return self._release() < other._release()
        # A release outranks any prerelease of the same version.
        if self.prerelease is None:
            return False
        if other.prerelease is None:
            return True
        return self._prerelease_key(self.prerelease) < self._prerelease_key(
            other.prerelease
        )

    def __le__(self, other: Version) -> bool:
        return self == other or self < other

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            return False
        return (
            self._release() == other._release()
            and self.prerelease == other.prerelease
        )

    def __hash__(self) -> int:
        return hash((*self._release(), self.prerelease))

    def __gt__(self, other: Version) -> bool:
        return other < self

    def __ge__(self, other: Version) -> bool:
        return not (self < other)

    @staticmethod
    def parse(version_str: str) -> Version:
        """Parse version string."""
        match = re.match(
            r"(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.]+))?(?:\+([a-zA-Z0-9.]+))?",
            version_str.strip(),
        )
        if not match:
            raise ValueError(f"Invalid version: {version_str}")

        major, minor, patch, prerelease, metadata = match.groups()
        return Version(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
            metadata=metadata,
        )


@dataclass
class VersionConstraint:
    """Represents a version constraint."""

    operator: VersionOp
    version: Version

    def __str__(self) -> str:
        return f"{self.operator.value}{self.version}"

    def satisfies(self, version: Version) -> bool:
        """Check if version satisfies constraint."""
        if self.operator == VersionOp.EXACT:
            return version == self.version
        elif self.operator == VersionOp.GREATER:
            return version > self.version
        elif self.operator == VersionOp.GREATER_EQUAL:
            return version >= self.version
        elif self.operator == VersionOp.LESS:
            return version < self.version
        elif self.operator == VersionOp.LESS_EQUAL:
            return version <= self.version
        elif self.operator == VersionOp.CARET:
            # ^1.2.3 means >=1.2.3 and <2.0.0
            return (
                version >= self.version
                and version.major == self.version.major
            )
        elif self.operator == VersionOp.TILDE:
            # ~1.2.3 means >=1.2.3 and <1.3.0
            return (
                version >= self.version
                and version.major == self.version.major
                and version.minor == self.version.minor
            )
        return False

    @staticmethod
    def parse(constraint_str: str) -> VersionConstraint:
        """Parse constraint string like ^1.0.0 or >=1.0.0."""
        constraint_str = constraint_str.strip()

        if constraint_str.startswith("^"):
            op = VersionOp.CARET
            version_str = constraint_str[1:]
        elif constraint_str.startswith("~"):
            op = VersionOp.TILDE
            version_str = constraint_str[1:]
        elif constraint_str.startswith(">="):
            op = VersionOp.GREATER_EQUAL
            version_str = constraint_str[2:]
        elif constraint_str.startswith(">"):
            op = VersionOp.GREATER
            version_str = constraint_str[1:]
        elif constraint_str.startswith("<="):
            op = VersionOp.LESS_EQUAL
            version_str = constraint_str[2:]
        elif constraint_str.startswith("<"):
            op = VersionOp.LESS
            version_str = constraint_str[1:]
        elif constraint_str.startswith("=="):
            op = VersionOp.EXACT
            version_str = constraint_str[2:]
        else:
            # Default to caret
            op = VersionOp.CARET
            version_str = constraint_str

        version = Version.parse(version_str)
        return VersionConstraint(op, version)


@dataclass
class Package:
    """Represents a package in the registry."""

    name: str
    version: Version
    description: str = ""
    author: str = ""
    license: str = "MIT"
    dependencies: Dict[str, str] = field(default_factory=dict)  # name -> constraint
    dev_dependencies: Dict[str, str] = field(default_factory=dict)
    path: Optional[Path] = None
    published_at: Optional[datetime] = None
    integrity: Optional[str] = None  # Hash for verification

    def __str__(self) -> str:
        return f"{self.name}@{self.version}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "version": str(self.version),
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "dependencies": self.dependencies,
            "devDependencies": self.dev_dependencies,
            "published": self.published_at.isoformat() if self.published_at else None,
            "integrity": self.integrity,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Package:
        """Create from dictionary representation."""
        return Package(
            name=data["name"],
            version=Version.parse(data["version"]),
            description=data.get("description", ""),
            author=data.get("author", ""),
            license=data.get("license", "MIT"),
            dependencies=data.get("dependencies", {}),
            dev_dependencies=data.get("devDependencies", {}),
            integrity=data.get("integrity"),
        )


class PackageRegistry:
    """Manages package registry and resolution."""

    def __init__(self):
        self.packages: Dict[str, List[Package]] = {}  # name -> versions
        self.local_paths: List[Path] = []

    def register_package(self, package: Package) -> None:
        """Register a package in the registry."""
        if package.name not in self.packages:
            self.packages[package.name] = []

        # Check if version already exists
        existing_versions = [p.version for p in self.packages[package.name]]
        if package.version not in existing_versions:
            self.packages[package.name].append(package)
            self.packages[package.name].sort(key=lambda p: p.version)

    def register_local(self, directory: Path | str) -> None:
        """Register local package directory."""
        local_path = Path(directory)
        if local_path.exists():
            self.local_paths.append(local_path)

    def resolve(self, name: str, constraint: str) -> Optional[Package]:
        """Resolve package to specific version."""
        if name not in self.packages:
            return None

        version_constraint = VersionConstraint.parse(constraint)
        candidates = [
            p for p in self.packages[name]
            if version_constraint.satisfies(p.version)
        ]

        # Return highest matching version
        return max(candidates, key=lambda p: p.version) if candidates else None

    def resolve_dependencies(
        self, package: Package, include_dev: bool = False
    ) -> Dict[str, Package]:
        """Resolve all dependencies of a package."""
        resolved: Dict[str, Package] = {}
        queue: List[Tuple[str, str]] = list(package.dependencies.items())

        if include_dev:
            queue.extend(package.dev_dependencies.items())

        visited: Set[str] = set()

        while queue:
            name, constraint = queue.pop(0)

            if name in visited:
                continue

            visited.add(name)
            dep_package = self.resolve(name, constraint)

            if not dep_package:
                raise ValueError(f"Cannot resolve {name}@{constraint}")

            resolved[name] = dep_package

            # Add transitive dependencies
            queue.extend(dep_package.dependencies.items())
            if include_dev:
                queue.extend(dep_package.dev_dependencies.items())

        return resolved

    def check_conflicts(self, resolved: Dict[str, Package]) -> List[str]:
        """Check for version conflicts in resolved dependencies."""
        errors: List[str] = []

        # Build dependency graph
        for pkg_name, pkg in resolved.items():
            for dep_name, dep_constraint in pkg.dependencies.items():
                if dep_name in resolved:
                    dep_version = resolved[dep_name].version
                    constraint = VersionConstraint.parse(dep_constraint)

                    if not constraint.satisfies(dep_version):
                        errors.append(
                            f"{pkg_name} requires {dep_name}{dep_constraint}, "
                            f"but {dep_name}@{dep_version} is installed"
                        )

        return errors

    def create_lock_file(self, resolved: Dict[str, Package]) -> Dict[str, Any]:
        """Create lock file from resolved dependencies."""
        return {
            "version": "1.0",
            "packages": {
                name: pkg.to_dict() for name, pkg in resolved.items()
            },
            "timestamp": datetime.now().isoformat(),
        }

    def load_lock_file(self, lock_file: Path | str) -> Dict[str, Package]:
        """Load packages from lock file."""
        with open(lock_file) as f:
            lock_data = json.load(f)

        packages = {}
        for name, pkg_data in lock_data.get("packages", {}).items():
            packages[name] = Package.from_dict(pkg_data)

        return packages
