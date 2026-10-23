"""Language configuration CLI commands."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from parsercraft.config import LanguageConfig, list_presets
from parsercraft.config.language_config import create_custom_config_interactive
from parsercraft.runtime import LanguageRuntime
from parsercraft.tooling.commands.common import CONFIG_LOAD_ERRORS

try:
    from yaml import safe_load
except ImportError:  # pragma: no cover
    safe_load = None  # type: ignore[assignment]


def cmd_create(args):
    """Create a new language configuration."""
    if args.preset:
        try:
            config = LanguageConfig.from_preset(args.preset)
            print(f"Created configuration from preset: {args.preset}")
        except ValueError as exc:
            print(f"Error: {exc}")
            print(f"Available presets: {', '.join(list_presets())}")
            return 1
    elif args.interactive:
        config = create_custom_config_interactive()
    else:
        config = LanguageConfig()
        print("Created default configuration")

    # Save to file
    output = args.output or "language_config.yaml"
    config.save(output)
    print(f"Saved to: {output}")
    return 0

def cmd_edit(args) -> int:
    """Edit an existing configuration (opens in text editor)."""

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return 1

    # Determine editor
    editor = os.environ.get("EDITOR", "nano")

    # Open in editor
    try:
        subprocess.run([editor, str(filepath)], check=False)
        print(f"Edited: {filepath}")

        # Validate after editing
        try:
            config = LanguageConfig.load(filepath)
            errors = config.validate()
            if errors:
                print("\nValidation errors:")
                for error in errors:
                    print(f"  ❌ {error}")
                return 1
            else:
                print("\n✓ Configuration is valid")
        except CONFIG_LOAD_ERRORS as error:
            print(f"\n❌ Error loading config: {error}")
            return 1
    except FileNotFoundError:
        print(f"Error: Editor '{editor}' not found")
        print("Set EDITOR environment variable to your preferred editor")
        return 1

    return 0

def cmd_validate(args):
    """Validate a configuration file."""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return 1

    try:
        config = LanguageConfig.load(filepath)
        errors = config.validate()
        warnings = config.validation_warnings()

        if errors:
            print(f"❌ Validation failed for: {filepath}")
            print("\nErrors:")
            for error in errors:
                print(f"  • {error}")
            return 1

        print("✓ Configuration is valid")
        print("\nSummary:")
        print(f"  Name: {config.name}")
        print(f"  Version: {config.version}")
        print(f"  Keywords: {len(config.keyword_mappings)}")
        print(f"  Functions: {len(config.builtin_functions)}")
        print(f"  Operators: {len(config.operators)}")
        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"  • {warning}")
        return 0
    except CONFIG_LOAD_ERRORS as error:
        print(f"❌ Error loading config: {error}")
        return 1

def cmd_info(args):
    """Show information about a configuration."""
    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"Error: File not found: {filepath}")
            return 1

        try:
            config = LanguageConfig.load(filepath)
        except CONFIG_LOAD_ERRORS as error:
            print(f"Error loading config: {error}")
            return 1
    else:
        # Show current runtime config
        LanguageRuntime.load_config()
        config = LanguageRuntime.get_config()
        if not config:
            print("No configuration loaded")
            return 1

    # Display detailed info
    print("=" * 70)
    print(f"Language Configuration: {config.name}")
    print("=" * 70)
    print("\nMetadata:")
    print(f"  Version: {config.version}")
    print(f"  Description: {config.description}")
    if config.author:
        print(f"  Author: {config.author}")

    print("\nComponents:")
    print(f"  Keywords: {len(config.keyword_mappings)}")
    print(f"  Functions: {len(config.builtin_functions)}")
    print(f"  Operators: {len(config.operators)}")

    # Show keyword categories
    categories = {}
    for mapping in config.keyword_mappings.values():
        categories[mapping.category] = categories.get(mapping.category, 0) + 1

    print("\nKeyword Categories:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Show enabled/disabled functions
    enabled = sum(1 for f in config.builtin_functions.values() if f.enabled)
    disabled = len(config.builtin_functions) - enabled
    print("\nFunctions:")
    print(f"  Enabled: {enabled}")
    if disabled > 0:
        print(f"  Disabled: {disabled}")

    # Show syntax options
    opts = config.syntax_options
    print("\nSyntax Options:")
    print(f"  Array indexing: starts at {opts.array_start_index}")
    frac_status = "enabled" if opts.allow_fractional_indexing else "disabled"
    print(f"  Fractional indexing: {frac_status}")
    print(f"  Comment style: {opts.single_line_comment}")
    print(f"  Statement terminator: '{opts.statement_terminator}'")

    # Show enabled features
    features = []
    if opts.enable_satirical_keywords:
        features.append("satirical")
    if opts.three_valued_logic:
        features.append("3-valued-logic")
    if opts.probabilistic_variables:
        features.append("probabilistic")
    if opts.temporal_variables:
        features.append("temporal")
    if opts.enable_quantum_features:
        features.append("quantum")

    if features:
        print(f"  Features: {', '.join(features)}")

    print("\nRuntime:")
    debug_status = "enabled" if config.debug_mode else "disabled"
    strict_status = "enabled" if config.strict_mode else "disabled"
    print(f"  Debug mode: {debug_status}")
    print(f"  Strict mode: {strict_status}")
    print(f"  Compatibility: {config.compatibility_mode}")

    print("=" * 70)

    return 0

def cmd_export(args):
    """Export configuration in different formats."""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return 1

    try:
        config = LanguageConfig.load(filepath)
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading config: {error}")
        return 1

    format_type = args.format or "markdown"
    output = args.output or f"{filepath.stem}_export"

    if format_type == "markdown":
        output_file = f"{output}.md"
        config.export_mapping_table(output_file)
        print(f"Exported mapping table to: {output_file}")

    elif format_type == "json":
        output_file = f"{output}.json"
        config.save(output_file, fmt="json")
        print(f"Exported to JSON: {output_file}")

    elif format_type == "yaml":
        output_file = f"{output}.yaml"
        config.save(output_file, fmt="yaml")
        print(f"Exported to YAML: {output_file}")

    else:
        print(f"Error: Unknown format: {format_type}")
        print("Supported formats: markdown, json, yaml")
        return 1

    return 0

def cmd_import(args):
    """Import a configuration for use.

    Loads the configuration into the runtime and optionally persists
    a reference in `.langconfig` (project) or `~/.langconfig` (user).
    """
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return 1

    try:
        # Load into runtime
        LanguageRuntime.load_config(config_file=str(filepath))
        print(f"✓ Imported configuration: {filepath}")

        scope = args.scope or "project"
        if scope == "runtime":
            # Do not persist
            return 0

        if scope == "project":
            target = Path(".langconfig")
        elif scope == "user":
            target = Path.home() / ".langconfig"
        else:
            print(f"Error: Unknown scope: {scope}")
            print("Supported scopes: runtime, project, user")
            return 1

        try:
            # Write a small pointer file with the absolute path
            target.write_text(str(filepath.resolve()), encoding="utf-8")
            print(f"✓ Persisted config reference to: {target}")
        except OSError as error:
            print(f"Warning: Failed to persist reference: {error}")
        return 0
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error importing config: {error}")
        return 1

def cmd_list_presets(_args):
    """List available presets."""
    presets = list_presets()

    print("Available Presets:")
    print("=" * 70)

    for preset in presets:
        try:
            config = LanguageConfig.from_preset(preset)
            print(f"\n{preset}:")
            print(f"  {config.description}")
        except CONFIG_LOAD_ERRORS as error:
            print(f"\n{preset}: (error loading: {error})")

    print("\nUsage:")
    print("  langconfig create --preset PRESET_NAME")

    return 0

def cmd_convert(args):
    """Convert configuration between formats."""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return 1

    try:
        config = LanguageConfig.load(filepath)
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading config: {error}")
        return 1

    from_format = args.from_format or (
        "yaml" if filepath.suffix in [".yaml", ".yml"] else "json"
    )
    to_format = args.to_format

    output = args.output or f"{filepath.stem}.{to_format}"

    config.save(output, fmt=to_format)
    print(f"Converted {filepath} ({from_format}) to {output} ({to_format})")

    return 0

def cmd_diff(args):
    """Show differences between two configurations."""
    file1 = Path(args.file1)
    file2 = Path(args.file2)

    if not file1.exists():
        print(f"Error: File not found: {file1}")
        return 1
    if not file2.exists():
        print(f"Error: File not found: {file2}")
        return 1

    try:
        config1 = LanguageConfig.load(file1)
        config2 = LanguageConfig.load(file2)
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading configs: {error}")
        return 1

    print(f"Comparing: {file1} vs {file2}")
    print("=" * 70)

    # Compare keywords
    keys1 = set(config1.keyword_mappings.keys())
    keys2 = set(config2.keyword_mappings.keys())

    if keys1 != keys2:
        print("\nKeyword Differences:")
        only_in_1 = keys1 - keys2
        only_in_2 = keys2 - keys1

        if only_in_1:
            print(f"  Only in {file1.name}: {', '.join(sorted(only_in_1))}")
        if only_in_2:
            print(f"  Only in {file2.name}: {', '.join(sorted(only_in_2))}")

        # Check for different mappings
        common = keys1 & keys2
        different_mappings = []
        for key in common:
            if (
                config1.keyword_mappings[key].custom
                != config2.keyword_mappings[key].custom
            ):
                different_mappings.append(
                    f"{key}: "
                    f"'{config1.keyword_mappings[key].custom}' vs "
                    f"'{config2.keyword_mappings[key].custom}'"
                )

        if different_mappings:
            print("  Different mappings:")
            for diff in different_mappings:
                print(f"    {diff}")
    else:
        print("\n✓ Keywords are identical")

    # Compare functions
    funcs1 = set(config1.builtin_functions.keys())
    funcs2 = set(config2.builtin_functions.keys())

    if funcs1 != funcs2:
        print("\nFunction Differences:")
        only_in_1 = funcs1 - funcs2
        only_in_2 = funcs2 - funcs1

        if only_in_1:
            print(f"  Only in {file1.name}: {', '.join(sorted(only_in_1))}")
        if only_in_2:
            print(f"  Only in {file2.name}: {', '.join(sorted(only_in_2))}")
    else:
        print("\n✓ Functions are identical")

    # Compare syntax options
    opts1 = config1.syntax_options
    opts2 = config2.syntax_options

    differences = []
    if opts1.array_start_index != opts2.array_start_index:
        differences.append(
            f"array_start_index: {opts1.array_start_index} -> "
            f"{opts2.array_start_index}"
        )
    if opts1.allow_fractional_indexing != opts2.allow_fractional_indexing:
        differences.append(
            f"fractional_indexing: {opts1.allow_fractional_indexing} -> "
            f"{opts2.allow_fractional_indexing}"
        )
    if opts1.enable_satirical_keywords != opts2.enable_satirical_keywords:
        differences.append(
            f"satirical_keywords: {opts1.enable_satirical_keywords} -> "
            f"{opts2.enable_satirical_keywords}"
        )

    if differences:
        print("\nSyntax Option Differences:")
        for diff in differences:
            print(f"  {diff}")
    else:
        print("\n✓ Syntax options are identical")

    return 0

def cmd_update(args) -> int:
    """Update a configuration file."""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return 1

    try:
        config = LanguageConfig.load(filepath)
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading config: {error}")
        return 1

    print(f"Loaded: {filepath}")

    if args.set:
        updates: dict[str, Any] = {}
        for key, value in args.set:
            # Parse nested keys like "metadata.author"
            parts = key.split(".")
            current: dict[str, Any] = updates
            for part in parts[:-1]:
                current = current.setdefault(part, {})

            # Try to parse value as JSON for complex types
            try:
                current[parts[-1]] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                current[parts[-1]] = value

        config.update(updates, merge=True)
        print(f"Applied {len(args.set)} update(s)")

    if args.merge:
        merge_path = Path(args.merge)
        if not merge_path.exists():
            print(f"Error: Merge file not found: {merge_path}")
            return 1

        try:
            merge_config = LanguageConfig.load(merge_path)
        except CONFIG_LOAD_ERRORS as error:
            print(f"Error loading merge config: {error}")
            return 1

        config.merge(merge_config, prefer_other=True)
        print(f"Merged with: {merge_path}")

    output = args.output or args.file
    try:
        config.save(output)
    except OSError as error:
        print(f"Error saving configuration: {error}")
        return 1

    print(f"✓ Updated configuration saved to: {output}")
    return 0

def cmd_delete(args):
    """Delete elements from configuration."""
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return 1

    try:
        config = LanguageConfig.load(filepath)
    except CONFIG_LOAD_ERRORS as error:
        print(f"Error loading config: {error}")
        return 1

    print(f"Loaded: {filepath}")

    deleted_count = 0

    # Delete keywords
    if args.keyword:
        for kw in args.keyword:
            if config.delete_keyword(kw):
                print(f"  ✓ Deleted keyword: {kw}")
                deleted_count += 1
            else:
                print(f"  ✗ Keyword not found: {kw}")

    # Delete functions
    if args.function:
        for func in args.function:
            if config.delete_function(func):
                print(f"  ✓ Deleted function: {func}")
                deleted_count += 1
            else:
                print(f"  ✗ Function not found: {func}")

    # Delete operators
    if args.operator:
        for op in args.operator:
            if config.delete_operator(op):
                print(f"  ✓ Deleted operator: {op}")
                deleted_count += 1
            else:
                print(f"  ✗ Operator not found: {op}")

    if deleted_count == 0:
        print("No elements deleted")
        return 0

    # Save result
    output = args.output or args.file
    try:
        config.save(output)
    except OSError as error:
        print(f"Error saving configuration: {error}")
        return 1

    msg = "".join(
        (
            f"\n✓ Saved config with {deleted_count} deletion(s) to:",
            f" {output}",
        )
    )
    print(msg)

    return 0

