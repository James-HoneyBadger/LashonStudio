#!/usr/bin/env python3
"""
Documentation Generator for Language Configurations

Automatically generates comprehensive documentation from language configurations.
"""

from datetime import datetime
from pathlib import Path

from lashon.config.language_config import LanguageConfig


class DocumentationGenerator:
    """Generates documentation for language configurations."""

    @staticmethod
    def generate_markdown(config: LanguageConfig) -> str:
        """Generate Markdown documentation for a configuration."""
        lines = []

        # Header
        lines.append(f"# {config.name} - Language Reference")
        lines.append(f"**Version**: {config.version}")
        if config.description:
            lines.append(f"**Description**: {config.description}")
        if config.author:
            lines.append(f"**Author**: {config.author}")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Table of Contents
        lines.append("## Table of Contents")
        lines.append("1. [Keywords](#keywords)")
        lines.append("2. [Built-in Functions](#built-in-functions)")
        lines.append("3. [Operators](#operators)")
        lines.append("4. [Syntax Options](#syntax-options)")
        lines.append("5. [Examples](#examples)")
        lines.append("")

        # Keywords
        lines.append("## Keywords")
        lines.append("")
        lines.append("| Original | Custom | Category | Description |")
        lines.append("|----------|--------|----------|-------------|")

        for mapping in sorted(config.keyword_mappings.values(), key=lambda m: m.custom):
            orig = mapping.original
            custom = mapping.custom
            cat = mapping.category
            desc = mapping.description or "-"
            lines.append(f"| `{orig}` | `{custom}` | {cat} | {desc} |")

        lines.append("")

        # Functions
        lines.append("## Built-in Functions")
        lines.append("")
        lines.append("| Function | Arity | Status | Description |")
        lines.append("|----------|-------|--------|-------------|")

        for func in sorted(config.builtin_functions.values(), key=lambda f: f.name):
            name = func.name
            arity = "Variadic" if func.arity == -1 else str(func.arity)
            status = "✓ Enabled" if func.enabled else "✗ Disabled"
            desc = func.description or "-"
            lines.append(f"| `{name}` | {arity} | {status} | {desc} |")

        lines.append("")

        # Operators
        lines.append("## Operators")
        lines.append("")
        lines.append("| Symbol | Precedence | Associativity | Enabled |")
        lines.append("|--------|------------|---------------|---------|")

        for op in sorted(
            config.operators.values(), key=lambda o: (-o.precedence, o.symbol)
        ):
            symbol = op.symbol
            prec = op.precedence
            assoc = op.associativity
            enabled = "✓" if op.enabled else "✗"
            lines.append(f"| `{symbol}` | {prec} | {assoc} | {enabled} |")

        lines.append("")

        # Syntax Options
        lines.append("## Syntax Options")
        lines.append("")

        opts = config.syntax_options
        lines.append(f"- **Array Start Index**: {opts.array_start_index}")
        lines.append(
            f"- **Fractional Indexing**: "
            f"{'Enabled' if opts.allow_fractional_indexing else 'Disabled'}"
        )
        lines.append(f"- **Comment Style**: `{opts.single_line_comment}`")
        if opts.multi_line_comment_start:
            start_str = opts.multi_line_comment_start
            end_str = opts.multi_line_comment_end
            lines.append(f"- **Multi-line Comments**: `{start_str}...{end_str}`")
        term = opts.statement_terminator or "None"
        lines.append(f"- **Statement Terminator**: `{term}`")
        lines.append(
            f"- **Require Semicolons**: {'Yes' if opts.require_semicolons else 'No'}"
        )
        lines.append("")

        # Features
        features = []
        if opts.enable_satirical_keywords:
            features.append("Satirical Keywords")
        if opts.three_valued_logic:
            features.append("3-Valued Logic")
        if opts.probabilistic_variables:
            features.append("Probabilistic Variables")
        if opts.temporal_variables:
            features.append("Temporal Variables")
        if opts.enable_quantum_features:
            features.append("Quantum Features")

        if features:
            lines.append("## Special Features")
            lines.append("")
            for feature in features:
                lines.append(f"- {feature}")
            lines.append("")

        # Examples
        lines.append("## Examples")
        lines.append("")
        lines.append("### Basic Variable Declaration")
        lines.append("")
        lines.append("```")
        var_kw = config.keyword_mappings.get("var")
        if var_kw:
            lines.append(f"{var_kw.custom} x = 10")
        lines.append("```")
        lines.append("")

        lines.append("### Conditional Statement")
        lines.append("")
        lines.append("```")
        if_kw = config.keyword_mappings.get("if")
        then_sep = config.parsing_config.if_then_separator or ":"
        if if_kw:
            lines.append(f"{if_kw.custom} x > 5{then_sep}")
            lines.append("    // Do something")
        lines.append("```")
        lines.append("")

        lines.append("### Function Definition")
        lines.append("")
        lines.append("```")
        def_kw = config.keyword_mappings.get("def") or config.keyword_mappings.get(
            "function"
        )
        ret_kw = config.keyword_mappings.get("return")
        if def_kw:
            lines.append(f"{def_kw.custom} greet(name){then_sep}")
            if ret_kw:
                lines.append(f'    {ret_kw.custom} "Hello, " + name')
        lines.append("```")
        lines.append("")

        lines.append("---")
        lines.append(
            f"*Documentation auto-generated for {config.name} v{config.version}*"
        )

        return "\n".join(lines)

    @staticmethod
    def generate_html(config: LanguageConfig) -> str:
        """Generate HTML documentation for a configuration."""
        markdown = DocumentationGenerator.generate_markdown(config)

        # Simple markdown to HTML conversion
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config.name} - Language Reference</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1, h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        h2 {{
            font-size: 1.8em;
            margin-top: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f9f9f9;
        }}
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background-color: #2c3e50;
            color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        ul li {{
            padding: 8px 0;
            padding-left: 20px;
            position: relative;
        }}
        ul li:before {{
            content: "▸";
            position: absolute;
            left: 0;
            color: #3498db;
        }}
        .metadata {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .metadata p {{
            margin: 5px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #7f8c8d;
        }}
    </style>
</head>
<body>
    <h1>{config.name}</h1>
    <div class="metadata">
        <p><strong>Version:</strong> {config.version}</p>
        <p><strong>Description:</strong> {config.description or 'N/A'}</p>
        <p><strong>Author:</strong> {config.author or 'N/A'}</p>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
"""

        # Convert markdown table to HTML table (simplified)
        in_table = False
        for line in markdown.split("\n"):
            if line.startswith("|"):
                if not in_table:
                    html += "<table>\n"
                    in_table = True

                if "---" in line:
                    continue

                html += "<tr>"
                for cell in line.split("|")[1:-1]:
                    html += f"<td>{cell.strip()}</td>"
                html += "</tr>\n"
            else:
                if in_table:
                    html += "</table>\n"
                    in_table = False

                if line.startswith("# "):
                    html += f"<h1>{line[2:]}</h1>\n"
                elif line.startswith("## "):
                    html += f"<h2>{line[3:]}</h2>\n"
                elif line.startswith("- "):
                    html += f"<ul><li>{line[2:]}</li></ul>\n"
                elif line.strip():
                    html += f"<p>{line}</p>\n"

        html += """
    <div class="footer">
        <p>Language reference documentation - auto-generated</p>
    </div>
</body>
</html>
"""
        return html

    @staticmethod
    def save_markdown(config: LanguageConfig, filepath: str) -> None:
        """Save documentation as Markdown file."""
        doc = DocumentationGenerator.generate_markdown(config)
        Path(filepath).write_text(doc, encoding="utf-8")

    @staticmethod
    def save_html(config: LanguageConfig, filepath: str) -> None:
        """Save documentation as HTML file."""
        doc = DocumentationGenerator.generate_html(config)
        Path(filepath).write_text(doc, encoding="utf-8")
