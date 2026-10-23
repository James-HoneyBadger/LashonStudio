#!/usr/bin/env python3
"""
Module and Package System for ParserCraft Languages

Enables custom languages to support:
    - Multi-file programs with `import` / `include` statements
    - Module namespaces and visibility
    - Circular dependency detection
    - Package repositories for code reuse
    - Version management for modules

Features:
    - Import statements: `import module`, `import module as alias`
    - Include statements: `include "relative/path.lang"`
    - Public/private exports
    - Namespace management
    - Dependency resolution and caching

Usage:
    from parsercraft.module_system import ModuleManager, ModuleLoader
    
    manager = ModuleManager(
        config=my_language_config,
        search_paths=["./modules", "./libs"]
    )
    
    module = manager.load_module("mymodule")
    exported = module.get_exports()
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class ModuleVisibility(Enum):
    """Module/symbol visibility levels."""

    PUBLIC = "public"       # Exported and importable
    PRIVATE = "private"     # Internal only
    PROTECTED = "protected" # Within package only


class DependencyType(Enum):
    """Types of module dependencies."""

    IMPORT = "import"           # Load and use module
    INCLUDE = "include"         # Inline module content
    EXTEND = "extend"           # Extend/inherit from module
    REQUIRE_VERSION = "require"  # Version constraint


@dataclass
class ModuleExport:
    """Represents an exported symbol from a module."""

    name: str
    kind: str  # "function", "class", "variable", "constant"
    visibility: ModuleVisibility = ModuleVisibility.PUBLIC
    type_hint: Optional[str] = None
    documentation: Optional[str] = None
    defined_at: Optional[str] = None  # Line number or file location
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_accessible_from(self, module: "Module") -> bool:
        """Check if this export is accessible from another module."""
        if self.visibility == ModuleVisibility.PUBLIC:
            return True
        if self.visibility == ModuleVisibility.PRIVATE:
            # Only accessible within the same module
            return module.name == self.metadata.get("source_module", self.defined_at)
        # PROTECTED: would check package membership
        return False


@dataclass
class ModuleImport:
    """Represents an import statement."""

    module_name: str
    alias: Optional[str] = None  # `import x as y`
    selected: Optional[List[str]] = None  # `import {foo, bar} from x`
    version_constraint: Optional[str] = None  # Semantic versioning
    optional: bool = False  # `try-import`

    def get_reference_name(self) -> str:
        """Get the name to reference this import by."""
        return self.alias or self.module_name


@dataclass
class Module:
    """Represents a language module/file."""

    name: str
    path: Path
    content: str
    language_config: Any  # LanguageConfig
    version: str = "0.0.1"
    author: Optional[str] = None
    description: Optional[str] = None
    dependencies: List[ModuleImport] = field(default_factory=list)
    exports: Dict[str, ModuleExport] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    parsed: bool = False
    hash: Optional[str] = None
    
    def __post_init__(self):
        """Calculate content hash."""
        if not self.hash:
            self.hash = hashlib.sha256(self.content.encode()).hexdigest()[:12]

    def get_exports(self, visibility: Optional[ModuleVisibility] = None) -> Dict[str, ModuleExport]:
        """Get exported symbols, optionally filtered by visibility."""
        if visibility is None:
            return self.exports
        return {name: exp for name, exp in self.exports.items() if exp.visibility == visibility}

    def add_export(self, export: ModuleExport) -> None:
        """Register an exported symbol."""
        self.exports[export.name] = export

    def add_dependency(self, import_stmt: ModuleImport) -> None:
        """Register a module dependency."""
        self.dependencies.append(import_stmt)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "path": str(self.path),
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "hash": self.hash,
            "dependencies": [
                {
                    "module": dep.module_name,
                    "alias": dep.alias,
                    "version": dep.version_constraint,
                }
                for dep in self.dependencies
            ],
            "exports": {
                name: {
                    "kind": exp.kind,
                    "visibility": exp.visibility.value,
                    "type": exp.type_hint,
                }
                for name, exp in self.exports.items()
            },
        }


@dataclass
class ModuleMetadata:
    """Metadata file for a module/package (like package.json, Cargo.toml)."""

    name: str
    version: str = "0.0.1"
    description: str = ""
    author: str = ""
    entry_point: str = "main"
    exports: Dict[str, str] = field(default_factory=dict)  # name -> path
    dependencies: Dict[str, str] = field(default_factory=dict)  # name -> version
    dev_dependencies: Dict[str, str] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)
    license: str = "MIT"

    @classmethod
    def from_file(cls, path: Path) -> Optional[ModuleMetadata]:
        """Load metadata from file (module.yaml, module.json)."""
        if not path.exists():
            return None

        try:
            content = path.read_text()
            if path.suffix in [".yaml", ".yml"]:
                try:
                    import yaml
                    data = yaml.safe_load(content)
                except ImportError:
                    # Fallback to json if yaml not available or just fail
                    # Since we are mocking, let's assume json if yaml missing
                    # But we use the global json import
                    data = json.loads(content)
            else:
                data = json.loads(content)

            return cls(
                name=data.get("name"),
                version=data.get("version", "0.0.1"),
                description=data.get("description", ""),
                author=data.get("author", ""),
                entry_point=data.get("entry_point", "main"),
                exports=data.get("exports", {}),
                dependencies=data.get("dependencies", {}),
                dev_dependencies=data.get("dev_dependencies", {}),
                keywords=data.get("keywords", []),
                license=data.get("license", "MIT"),
            )
        except Exception as e:
            print(f"Error loading module metadata: {e}")
            return None

    def to_file(self, path: Path) -> None:
        """Save metadata to file."""
        data = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "entry_point": self.entry_point,
            "exports": self.exports,
            "dependencies": self.dependencies,
            "dev_dependencies": self.dev_dependencies,
            "keywords": self.keywords,
            "license": self.license,
        }

        if path.suffix in [".yaml", ".yml"]:
            import yaml
            with open(path, "w") as f:
                yaml.dump(data, f)
        else:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)


class ModuleLoader:
    """Loads and parses module files."""

    def __init__(self, config: Any):  # LanguageConfig
        self.config = config
        self.cache: Dict[str, Module] = {}

    def load_file(self, path: Path, module_name: Optional[str] = None) -> Optional[Module]:
        """Load a module from file."""
        if not path.exists():
            raise FileNotFoundError(f"Module not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            raise IOError(f"Cannot read module file {path}: {e}")

        name = module_name or path.stem
        module = Module(
            name=name,
            path=path,
            content=content,
            language_config=self.config,
        )

        # Parse module metadata and imports
        self._parse_module(module)

        # Cache it
        self.cache[name] = module
        return module

    def _parse_module(self, module: Module) -> None:
        """Parse module content to extract imports, exports, metadata."""
        lines = module.content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip comments and empty lines
            if not stripped or stripped.startswith("#"):
                continue

            # Parse import statements
            if stripped.startswith("import "):
                import_stmt = self._parse_import_statement(stripped)
                if import_stmt:
                    module.add_dependency(import_stmt)

            # Parse export markers
            if "export " in stripped:
                export = self._parse_export_statement(stripped, i)
                if export:
                    module.add_export(export)

            # Parse module metadata comment
            if stripped.startswith("#@"):
                self._parse_metadata_comment(module, stripped)

        module.parsed = True

    def _parse_import_statement(self, line: str) -> Optional[ModuleImport]:
        """Parse import statement.

        Examples:
            import math
            import math as m
            import {sin, cos} from math
            import utils version "^1.0.0"
        """
        # Remove 'import' keyword
        line = line[7:].strip()

        # Check for destructuring: import {a, b, c} from module
        if line.startswith("{"):
            end_brace = line.find("}")
            if end_brace != -1:
                selected = [s.strip() for s in line[1:end_brace].split(",")]
                rest = line[end_brace + 1:].strip()
                if rest.startswith("from"):
                    module_name = rest[4:].strip()
                    return ModuleImport(module_name=module_name, selected=selected)

        # Simple import: import module [as alias] [version "constraint"]
        parts = line.split()
        if not parts:
            return None

        module_name = parts[0]
        alias = None
        version = None

        if len(parts) > 1 and parts[1] == "as":
            alias = parts[2] if len(parts) > 2 else None

        if "version" in parts:
            version_idx = parts.index("version")
            if version_idx + 1 < len(parts):
                version = parts[version_idx + 1].strip('"\'')

        return ModuleImport(
            module_name=module_name,
            alias=alias,
            version_constraint=version,
        )

    def _parse_export_statement(self, line: str, line_number: int) -> Optional[ModuleExport]:
        """Parse export statement.

        Examples:
            export function calculate(x, y)
            export const PI = 3.14159
            export class Point
        """
        # Extract what comes after 'export'
        match_idx = line.find("export ")
        if match_idx == -1:
            return None

        rest = line[match_idx + 7:].strip()

        # Determine kind and name
        if rest.startswith("function "):
            kind = "function"
            rest = rest[9:].strip()
        elif rest.startswith("const ") or rest.startswith("variable "):
            kind = "variable"
            rest = rest[6:].strip() if rest.startswith("const") else rest[9:].strip()
        elif rest.startswith("class "):
            kind = "class"
            rest = rest[6:].strip()
        else:
            kind = "symbol"

        # Extract name (everything before paren, equals, or space)
        name = rest.split("(")[0].split("=")[0].split()[0]

        if not name:
            return None

        return ModuleExport(
            name=name,
            kind=kind,
            visibility=ModuleVisibility.PUBLIC,
            defined_at=str(line_number),
        )

    def _parse_metadata_comment(self, module: Module, line: str) -> None:
        """Parse metadata in special comments.

        Examples:
            #@ version: 1.0.0
            #@ author: Jane Doe
            #@ description: Utility module
        """
        if not line.startswith("#@"):
            return

        key_val = line[2:].strip()
        if ":" not in key_val:
            return

        key, value = key_val.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key == "version":
            module.version = value
        elif key == "author":
            module.author = value
        elif key == "description":
            module.description = value
        else:
            module.metadata[key] = value


class ModuleManager:
    """Manages module loading, caching, and dependency resolution."""

    def __init__(
        self,
        config: Any,  # LanguageConfig
        search_paths: Optional[List[str]] = None,
        enable_caching: bool = True,
    ):
        self.config = config
        self.loader = ModuleLoader(config)
        self.search_paths = [Path(p) for p in (search_paths or [".", "./modules", "./lib"])]
        self.enable_caching = enable_caching
        self.loaded_modules: Dict[str, Module] = {}
        self.dependency_graph: Dict[str, Set[str]] = {}

    def load_module(
        self,
        module_name: str,
        search_relative_to: Optional[Path] = None,
    ) -> Optional[Module]:
        """Load a module by name."""
        # Check cache
        if self.enable_caching and module_name in self.loaded_modules:
            return self.loaded_modules[module_name]

        # Find module file
        module_path = self._find_module(module_name, search_relative_to)
        if not module_path:
            raise ParserCraftModuleNotFoundError(f"Cannot find module: {module_name}")

        # Load it
        try:
            module = self.loader.load_file(module_path, module_name)
            if module and self.enable_caching:
                self.loaded_modules[module_name] = module
            return module
        except (FileNotFoundError, IOError) as e:
            raise ModuleLoadError(f"Error loading module {module_name}: {e}")

    def load_with_dependencies(self, module_name: str) -> Dict[str, Module]:
        """Load module and all its dependencies."""
        modules = {}
        to_process = [module_name]
        processed = set()

        while to_process:
            current = to_process.pop(0)
            if current in processed:
                continue

            processed.add(current)

            try:
                module = self.load_module(current)
                if module:
                    modules[current] = module

                    # Add dependencies to processing queue
                    for dep in module.dependencies:
                        if dep.module_name not in processed:
                            to_process.append(dep.module_name)
            except (ParserCraftModuleNotFoundError, ModuleLoadError) as e:
                print(f"Warning: {e}")
                # Check if the dependency was optional in the parent module
                parent_module = modules.get(module_name)
                if parent_module and not any(
                    d.optional for d in parent_module.dependencies
                    if d.module_name == current
                ):
                    raise

        return modules

    def resolve_dependencies(self, module_name: str) -> List[str]:
        """Get ordered list of dependencies (for topological sort)."""
        if module_name in self.dependency_graph:
            return list(self.dependency_graph[module_name])

        try:
            module = self.load_module(module_name)
            deps = [dep.module_name for dep in module.dependencies]
            self.dependency_graph[module_name] = set(deps)
            return deps
        except (ParserCraftModuleNotFoundError, ModuleLoadError):
            return []

    def detect_circular_dependencies(self) -> List[Tuple[str, str]]:
        """Detect circular dependencies in loaded modules."""
        cycles = []

        def has_cycle(node: str, visited: Set[str], rec_stack: Set[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.dependency_graph.get(node, set()):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    cycles.append((node, neighbor))
                    return True

            rec_stack.remove(node)
            return False

        visited = set()
        for node in self.dependency_graph:
            if node not in visited:
                has_cycle(node, visited, set())

        return cycles

    def _find_module(
        self,
        module_name: str,
        search_relative_to: Optional[Path] = None,
    ) -> Optional[Path]:
        """Find module file in search paths."""
        search_dirs = []

        if search_relative_to and search_relative_to.is_dir():
            search_dirs.append(search_relative_to)

        search_dirs.extend(self.search_paths)

        # Try different file extensions
        for search_dir in search_dirs:
            for ext in [".teach", ".lang", ".script", ".txt", ""]:
                candidate = search_dir / f"{module_name}{ext}"
                if candidate.exists() and candidate.is_file():
                    return candidate

        return None

    def get_module_info(self, module_name: str) -> Dict[str, Any]:
        """Get information about a loaded module."""
        try:
            module = self.load_module(module_name)
            return {
                "name": module.name,
                "path": str(module.path),
                "version": module.version,
                "author": module.author,
                "description": module.description,
                "hash": module.hash,
                "exports": {
                    name: {
                        "kind": exp.kind,
                        "visibility": exp.visibility.value,
                    }
                    for name, exp in module.exports.items()
                },
                "dependencies": [
                    {
                        "module": dep.module_name,
                        "alias": dep.alias,
                    }
                    for dep in module.dependencies
                ],
            }
        except (ParserCraftModuleNotFoundError, ModuleLoadError) as e:
            return {"error": str(e)}

    def export_dependency_graph(self, output_file: str) -> None:
        """Export dependency graph as JSON."""
        graph_data = {
            "modules": {
                name: {
                    "dependencies": list(deps),
                    "info": self.get_module_info(name),
                }
                for name, deps in self.dependency_graph.items()
            },
            "cycles": [
                {"from": cycle[0], "to": cycle[1]}
                for cycle in self.detect_circular_dependencies()
            ],
        }

        with open(output_file, "w") as f:
            json.dump(graph_data, f, indent=2)

        print(f"Exported dependency graph to {output_file}")


class ParserCraftModuleNotFoundError(Exception):
    """Raised when a module cannot be found.

    Named to avoid shadowing the built-in ModuleNotFoundError.
    """


# Backward-compatible alias
ModuleNotFoundError = ParserCraftModuleNotFoundError  # noqa: A001


class ModuleLoadError(Exception):
    """Raised when a module cannot be loaded."""


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected."""


# Example usage and testing
if __name__ == "__main__":
    from parsercraft.config.language_config import LanguageConfig

    # Load a language config
    config = LanguageConfig.from_preset("python_like")

    # Create module manager
    manager = ModuleManager(
        config=config,
        search_paths=["./modules", "./libs", "."],
    )

    # Example: load a module
    try:
        math_module = manager.load_module("math")
        print(f"Loaded: {math_module.name}")
        print(f"Exports: {list(math_module.exports.keys())}")
    except (ParserCraftModuleNotFoundError, ModuleLoadError) as e:
        print(f"Error: {e}")
