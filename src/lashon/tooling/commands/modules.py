"""Module-system CLI commands."""

from __future__ import annotations

import traceback
from pathlib import Path

from lashon.config import LanguageConfig


def cmd_module_info(args):
    """Show information about a module."""
    from lashon.runtime.module_system import ModuleManager

    module_name = args.module
    module_dir = Path(args.module_dir) if args.module_dir else Path.cwd()

    try:
        config = LanguageConfig()
        manager = ModuleManager(
            config=config,
            search_paths=[str(module_dir)],
        )
        module = manager.load_module(module_name)

        print(f"Module: {module.name}")
        print(f"Version: {module.version}")
        if module.metadata.get("description"):
            print(f"Description: {module.metadata['description']}")
        if module.metadata.get("author"):
            print(f"Author: {module.metadata['author']}")

        print(f"\nExports ({len(module.exports)}):")
        for _, export in module.exports.items():
            visibility = export.visibility.name
            print(f"  {export.name} ({visibility})")

        if module.dependencies:
            print(f"\nDependencies ({len(module.dependencies)}):")
            for dep in module.dependencies:
                print(f"  {dep.module_name}")

        return 0

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error: {error}")
        if args.debug:
            traceback.print_exc()
        return 1

def cmd_module_deps(args):
    """Show module dependencies."""
    from lashon.runtime.module_system import ModuleManager

    module_name = args.module
    module_dir = Path(args.module_dir) if args.module_dir else Path.cwd()

    try:
        config = LanguageConfig()
        manager = ModuleManager(
            config=config,
            search_paths=[str(module_dir)],
        )
        deps = manager.resolve_dependencies(module_name)

        print(f"Dependencies for {module_name}:")
        print("=" * 70)

        if not deps:
            print("No dependencies")
            return 0

        module = manager.load_module(module_name)
        print(f"Direct dependencies ({len(module.dependencies)}):")
        for dep in module.dependencies:
            print(f"  • {dep.module_name}")

        all_deps = set(deps) - {module_name}
        if all_deps:
            print(f"\nTransitive dependencies ({len(all_deps)}):")
            for dep in sorted(all_deps):
                print(f"  • {dep}")

        return 0

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error: {error}")
        if args.debug:
            traceback.print_exc()
        return 1

def cmd_module_cycles(args):
    """Detect circular dependencies."""
    from lashon.runtime.module_system import CircularDependencyError, ModuleManager

    module_dir = Path(args.module_dir) if args.module_dir else Path.cwd()

    try:
        config = LanguageConfig()
        manager = ModuleManager(
            config=config,
            search_paths=[str(module_dir)],
        )

        # Try to load all modules and detect cycles
        cycles = []
        try:
            manager.load_with_dependencies("main")
        except CircularDependencyError as exc:
            cycles.append(str(exc))

        if not cycles:
            print("✓ No circular dependencies detected")
            return 0

        print(f"⚠ Found {len(cycles)} circular dependency cycle(s):\n")
        for cycle in cycles:
            print(f"  {cycle}")

        return 1

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error: {error}")
        if args.debug:
            traceback.print_exc()
        return 1

