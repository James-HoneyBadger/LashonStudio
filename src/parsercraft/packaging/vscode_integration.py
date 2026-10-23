#!/usr/bin/env python3
"""
VS Code Extension Support for ParserCraft

Provides utilities to generate VS Code extension configuration and
launch LSP servers for custom languages.

Usage:
    from parsercraft.vscode_integration import generate_vscode_extension
    
    generate_vscode_extension(
        config_path="my_lang.yaml",
        output_dir="./.vscode_ext"
    )
"""

from __future__ import annotations

import json
from pathlib import Path

from parsercraft.config.language_config import LanguageConfig


def generate_vscode_extension(
    config: LanguageConfig,
    output_dir: str = ".vscode-ext",
    publisher: str = "parsercraft",
    version: str = "0.0.1",
) -> None:
    """Generate VS Code extension files for a ParserCraft language.

    Args:
        config: Language configuration
        output_dir: Output directory for extension
        publisher: Extension publisher name
        version: Extension version
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate package.json
    package_json = {
        "name": config.name.lower().replace(" ", "-"),
        "displayName": config.name,
        "description": f"Support for {config.name} language",
        "version": version,
        "publisher": publisher,
        "engines": {
            "vscode": "^1.75.0",
        },
        "categories": ["Programming Languages", "Linters"],
        "activationEvents": [
            f"onLanguage:{config.name.lower()}",
            "onCommand:parsercraft.start",
        ],
        "main": "./out/extension.js",
        "scripts": {
            "vscode:prepublish": "npm run compile",
            "compile": "tsc -p ./",
            "watch": "tsc -watch -p ./",
        },
        "devDependencies": {
            "@types/node": "^20.0.0",
            "@types/vscode": "^1.75.0",
            "typescript": "^5.4.0",
            "vscode-languageclient": "^9.0.1",
        },
        "contributes": {
            "languages": [
                {
                    "id": config.name.lower(),
                    "aliases": [config.name],
                    "extensions": [f".{config.name.lower()[:3]}"],
                    "configuration": "./language-configuration.json",
                }
            ],
            "grammars": [
                {
                    "language": config.name.lower(),
                    "scopeName": f"source.{config.name.lower()}",
                    "path": "./syntaxes/language.tmLanguage.json",
                }
            ],
            "commands": [
                {
                    "command": "parsercraft.start",
                    "title": f"Start {config.name} Language Server",
                }
            ],
        },
    }

    with open(output_path / "package.json", "w") as f:
        json.dump(package_json, f, indent=2)

    # Generate language-configuration.json
    lang_config = {
        "comments": {
            "lineComment": config.syntax_options.single_line_comment or "//",
            "blockComment": [
                config.syntax_options.multi_line_comment_start or "/*",
                config.syntax_options.multi_line_comment_end or "*/",
            ],
        },
        "brackets": [
            ["[", "]"],
            ["(", ")"],
            ["{", "}"],
        ],
        "autoClosingPairs": [
            ["[", "]"],
            ["(", ")"],
            ["{", "}"],
            ['"', '"'],
            ["'", "'"],
        ],
        "surroundingPairs": [
            ["[", "]"],
            ["(", ")"],
            ["{", "}"],
            ['"', '"'],
            ["'", "'"],
        ],
    }

    with open(output_path / "language-configuration.json", "w") as f:
        json.dump(lang_config, f, indent=2)

    # Generate TextMate grammar for syntax highlighting
    grammar = _generate_textmate_grammar(config)
    syntaxes_dir = output_path / "syntaxes"
    syntaxes_dir.mkdir(exist_ok=True)

    with open(syntaxes_dir / "language.tmLanguage.json", "w") as f:
        json.dump(grammar, f, indent=2)

    # Generate extension.ts template
    extension_ts = _generate_extension_template(config)
    with open(output_path / "extension.ts", "w") as f:
        f.write(extension_ts)

    # TypeScript build configuration for the generated extension
    with open(output_path / "tsconfig.json", "w") as f:
        json.dump(
            {
                "compilerOptions": {
                    "module": "commonjs",
                    "target": "ES2020",
                    "outDir": "out",
                    "lib": ["ES2020"],
                    "sourceMap": True,
                    "rootDir": ".",
                    "strict": True,
                },
                "include": ["extension.ts"],
                "exclude": ["node_modules"],
            },
            f,
            indent=2,
        )

    # Ship the language definition with the extension so the server can run
    try:
        import yaml

        with open(output_path / "language.yaml", "w") as f:
            yaml.safe_dump(config.to_dict(), f, sort_keys=False)
    except (ImportError, AttributeError):  # pragma: no cover - optional
        pass

    with open(output_path / ".vscodeignore", "w") as f:
        f.write(
            "extension.ts\ntsconfig.json\nnode_modules/**\n"
            ".vscode-test/**\n**/*.map\n"
        )

    # Generate .gitignore
    with open(output_path / ".gitignore", "w") as f:
        f.write("node_modules/\nout/\n.vscode-test/\n")

    # Generate README
    readme = _generate_extension_readme(config)
    with open(output_path / "README.md", "w") as f:
        f.write(readme)

    print(f"✓ Generated VS Code extension in {output_path}")
    print(f"  Package it with: (cd {output_path} && npm install && npx vsce package)")


def _generate_textmate_grammar(config: LanguageConfig) -> dict:
    """Generate TextMate syntax highlighting grammar."""
    keywords = "|".join(kw.custom for kw in config.keyword_mappings.values())
    functions = "|".join(fn.name for fn in config.builtin_functions.values())

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": config.name,
        "scopeName": f"source.{config.name.lower()}",
        "patterns": [
            {"include": "#comments"},
            {"include": "#strings"},
            {"include": "#numbers"},
            {"include": "#keywords"},
            {"include": "#functions"},
            {"include": "#variables"},
        ],
        "repository": {
            "comments": {
                "patterns": [
                    {
                        "name": "comment.line",
                        "match": f"{config.syntax_options.single_line_comment}.*$",
                    },
                    {
                        "name": "comment.block",
                        "begin": config.syntax_options.multi_line_comment_start,
                        "end": config.syntax_options.multi_line_comment_end,
                    },
                ]
            },
            "strings": {
                "patterns": [
                    {
                        "name": "string.quoted.double",
                        "begin": '"',
                        "end": '"',
                        "patterns": [
                            {"name": "constant.character.escape", "match": r"\\."}
                        ],
                    },
                    {
                        "name": "string.quoted.single",
                        "begin": "'",
                        "end": "'",
                        "patterns": [
                            {"name": "constant.character.escape", "match": r"\\."}
                        ],
                    },
                ]
            },
            "numbers": {
                "patterns": [
                    {
                        "name": "constant.numeric",
                        "match": r"\b\d+(\.\d+)?\b",
                    }
                ]
            },
            "keywords": {
                "patterns": [
                    {
                        "name": "keyword.control",
                        "match": rf"\b({keywords})\b",
                    }
                ]
            },
            "functions": {
                "patterns": [
                    {
                        "name": "entity.name.function",
                        "match": rf"\b({functions})\s*(?=\()",
                    }
                ]
            },
            "variables": {
                "patterns": [
                    {
                        "name": "variable.other",
                        "match": r"\b[a-zA-Z_]\w*\b",
                    }
                ]
            },
        },
    }


def _generate_extension_template(config: LanguageConfig) -> str:
    """Generate TypeScript extension template."""
    lang_id = config.name.lower()
    return f'''import * as vscode from 'vscode';
import {{ LanguageClient, LanguageClientOptions, ServerOptions, TransportKind }} from 'vscode-languageclient/node';

let client: LanguageClient;

export function activate(context: vscode.ExtensionContext) {{
    console.log('{config.name} language extension activated');

    // The ParserCraft CLI hosts the language server; the extension just
    // launches it over stdio so no Node runtime shim is required.
    const configPath = context.asAbsolutePath('language.yaml');
    const serverOptions: ServerOptions = {{
        run: {{
            command: 'parsercraft',
            args: ['lsp', '--config', configPath, '--stdio'],
            transport: TransportKind.stdio,
        }},
        debug: {{
            command: 'parsercraft',
            args: ['lsp', '--config', configPath, '--stdio'],
            transport: TransportKind.stdio,
        }},
    }};

    const clientOptions: LanguageClientOptions = {{
        documentSelector: [{{ scheme: 'file', language: '{lang_id}' }}],
        synchronize: {{
            fileEvents: vscode.workspace.createFileSystemWatcher('**/.clientrc')
        }}
    }};

    client = new LanguageClient('{lang_id}-server', '{config.name} Language Server', serverOptions, clientOptions);
    client.start();
}}

export function deactivate(): Thenable<void> | undefined {{
    if (!client) {{
        return undefined;
    }}
    return client.stop();
}}
'''


def _generate_extension_readme(config: LanguageConfig) -> str:
    """Generate extension README."""
    return f"""# {config.name} Language Support

VS Code extension providing language support for {config.name}.

## Features

- **Syntax Highlighting** - Colorized code for all {config.name} keywords
- **IntelliSense** - Code completion for keywords and built-in functions
- **Diagnostics** - Real-time error detection
- **Hover Hints** - Documentation on hover over keywords/functions
- **Language Server** - Full LSP support for advanced features

## Installation

1. Build the extension:
   ```bash
   npm install
   npm run compile
   ```

2. Package for distribution:
   ```bash
   vsce package
   ```

3. Install locally:
   ```bash
   code --install-extension {config.name.lower()}-{config.name.lower()}-0.0.1.vsix
   ```

## Usage

Create a file with extension `.{config.name[:3].lower()}`:
```{config.name.lower()}
    // Your {config.name} code here
    print("Hello, world!")
## Keyboard Shortcuts

- `Ctrl+Space` - Trigger code completion
- `Ctrl+Shift+Space` - Trigger signature help
- `F12` - Go to definition

## Configuration

Language settings can be customized in `.vscode/settings.json`:
```json
{{
    "[{config.name.lower()}]": {{
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "parsercraft.{config.name.lower()}"
    }}
}}
```

## Support

For issues or feature requests, visit:
https://github.com/James-HoneyBadger/ParserCraft/issues
"""


def generate_simple_grammar(
    config: LanguageConfig,
    output_file: str = "grammar.txt",
) -> None:
    """Generate a simple EBNF-like grammar reference.

    Args:
        config: Language configuration
        output_file: Output file path
    """
    lines = [
        f"# {config.name} Grammar Reference",
        "",
        "## Keywords",
    ]

    for kw_map in config.keyword_mappings.values():
        lines.append(f"  {kw_map.custom:20} -> {kw_map.original}")

    lines.extend(["", "## Built-in Functions"])
    for func in config.builtin_functions.values():
        arity_str = f"/{func.arity}" if func.arity >= 0 else "/*"
        lines.append(f"  {func.name}{arity_str:15} : {func.description or ''}")

    lines.extend(["", "## Operators"])
    for op_name, op in config.operators.items():
        lines.append(f"  {op.symbol:10} (precedence: {op.precedence})")

    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    print(f"✓ Generated grammar reference: {output_file}")
