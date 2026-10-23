"""Code-generation CLI commands (C, WebAssembly, LLVM IR)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def _load_grammar_from_config(config_path: Optional[str]):
    """Build a Grammar from a raw language config file."""
    from parsercraft.tooling.commands.common import load_grammar

    return load_grammar(config_path=config_path, require_rules=bool(config_path))


def _parse_source_file(source_path: Path, config_path: Optional[str]):
    """Parse ``source_path`` using the grammar from ``config_path``."""
    from parsercraft.parser.grammar import PEGInterpreter

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    grammar = _load_grammar_from_config(config_path)
    return PEGInterpreter(grammar).parse(
        source_path.read_text(encoding="utf-8")
    )


def cmd_codegen_c(args):
    """Generate C code from source."""
    from parsercraft.codegen.codegen_c import CCodeGenerator

    try:
        source_path = Path(args.file)
        ast = _parse_source_file(source_path, args.config)
        generator = CCodeGenerator(
            source_map=getattr(args, "source_map", False),
            source_file=source_path.name,
        )
        c_code = generator.translate_source_ast(ast)

        output_file = (
            Path(args.output) if args.output else source_path.with_suffix(".c")
        )

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(c_code)

        print(f"✓ Generated C code: {output_file}")
        print(f"  Lines: {len(c_code.split(chr(10)))}")

        return 0

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error: {error}")
        return 1


def cmd_codegen_wasm(args):
    """Generate WebAssembly from source."""
    from parsercraft.codegen.codegen_wasm import WasmGenerator

    try:
        source_path = Path(args.file)
        ast = _parse_source_file(source_path, args.config)
        module = WasmGenerator().translate_source_ast(ast)

        output_file = (
            Path(args.output) if args.output else source_path.with_suffix(".wat")
        )

        wat_text = module.to_wat()
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(wat_text)

        print(f"✓ Generated WebAssembly: {output_file}")
        print(f"  Lines: {len(wat_text.split(chr(10)))}")

        return 0

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error: {error}")
        return 1


def cmd_codegen_llvm(args):
    """Generate LLVM IR from source."""
    from parsercraft.codegen.llvm_ir import LLVMIRGenerator

    try:
        source_path = Path(args.file)
        ast = _parse_source_file(source_path, args.config)
        llvm_ir = LLVMIRGenerator().translate_source_ast(ast)

        output_file = (
            Path(args.output) if args.output else source_path.with_suffix(".ll")
        )

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(llvm_ir)

        print(f"✓ Generated LLVM IR: {output_file}")
        print(f"  Lines: {len(llvm_ir.split(chr(10)))}")

        return 0

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Error: {error}")
        return 1
