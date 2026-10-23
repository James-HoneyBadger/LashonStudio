"""Named preset configurations.

Each preset starts from a fresh :class:`~.workbench.LanguageConfig` and adjusts
keywords, array indexing, terminators, and runtime flags. Kept separate from
the config model so presets can be reviewed as data rather than code.
"""

from __future__ import annotations


def apply_preset(cfg, preset_name: str) -> None:
    """Mutate ``cfg`` into the named preset.

    Raises:
        ValueError: when the preset name is unknown.
    """
    if preset_name == "python_like":
        cfg.name = "Python-like"
        # Remove 'function' since 'def' is the Python standard
        cfg.remove_keyword("function")
        cfg.set_array_indexing(0, False)
        cfg.syntax_options.statement_terminator = ""
        cfg.syntax_options.require_semicolons = False
        cfg.disable_satirical_keywords()

    elif preset_name == "js_like":
        cfg.name = "JavaScript-like"
        cfg.set_array_indexing(0, False)
        cfg.syntax_options.statement_terminator = ";"
        cfg.syntax_options.require_semicolons = True
        cfg.disable_satirical_keywords()

    elif preset_name == "minimal":
        cfg.name = "Minimal"
        cfg.description = "Minimal feature set"
        cfg.disable_satirical_keywords()
        essential = {"print", "Number", "String", "Boolean", "List"}
        for func_name in list(cfg.builtin_functions.keys()):
            if func_name not in essential:
                cfg.remove_function(func_name)

    elif preset_name == "ruby_like":
        cfg.name = "Ruby-like"
        cfg.description = (  # noqa: E501
            "Ruby-inspired syntax for educational purposes"
        )
        cfg.remove_keyword("function")
        cfg.rename_keyword("def", "define")
        cfg.rename_keyword("class", "blueprint")
        cfg.rename_keyword("if", "when")
        cfg.rename_keyword("else", "otherwise")
        cfg.rename_keyword("while", "loop_while")
        cfg.set_array_indexing(0, False)
        cfg.disable_satirical_keywords()

    elif preset_name == "golang_like":
        cfg.name = "Go-like"
        cfg.description = "Go/Golang-inspired syntax"
        cfg.remove_keyword("function")
        cfg.rename_keyword("def", "func")
        cfg.rename_keyword("class", "type")
        cfg.rename_keyword("return", "return")
        cfg.set_array_indexing(0, False)
        cfg.syntax_options.statement_terminator = ""
        cfg.disable_satirical_keywords()

    elif preset_name == "rust_like":
        cfg.name = "Rust-like"
        cfg.description = "Rust-inspired syntax for systems programming"
        cfg.remove_keyword("function")
        cfg.rename_keyword("def", "fn")
        cfg.rename_keyword("const", "const")
        cfg.rename_keyword("var", "let")
        cfg.rename_keyword("class", "struct")
        cfg.set_array_indexing(0, False)
        cfg.disable_satirical_keywords()

    elif preset_name == "clike":
        cfg.name = "C-like"
        cfg.description = "C/C++-inspired syntax"
        cfg.remove_keyword("function")
        cfg.rename_keyword("def", "void")
        cfg.rename_keyword("class", "struct")
        cfg.rename_keyword("if", "if")
        cfg.set_array_indexing(0, False)
        cfg.syntax_options.statement_terminator = ";"
        cfg.syntax_options.require_semicolons = True
        cfg.disable_satirical_keywords()

    elif preset_name == "functional":
        cfg.name = "Functional Lambda"
        cfg.description = (  # noqa: E501
            "A functional language based on lambda calculus"
        )
        cfg.rename_keyword("if", "cond")
        cfg.rename_keyword("def", "define")
        cfg.rename_keyword("lambda", "lambda")
        cfg.rename_keyword("let", "let")
        cfg.set_array_indexing(0, False)
        cfg.syntax_options.statement_terminator = ""
        cfg.disable_satirical_keywords()
        # Add functional-specific operators if needed, or rely on functions

    elif preset_name == "lisp_like":
        cfg.name = "Lisp-like"
        cfg.description = "Lisp-inspired parenthesized syntax"
        cfg.rename_keyword("if", "if")
        cfg.rename_keyword("def", "def")
        cfg.rename_keyword("lambda", "lambda")
        cfg.set_array_indexing(0, False)
        cfg.syntax_options.statement_terminator = ""
        cfg.parsing_config.function_call_start = "("
        cfg.parsing_config.function_call_end = ")"
        cfg.parsing_config.block_start = "("
        cfg.parsing_config.block_end = ")"
        cfg.disable_satirical_keywords()

    elif preset_name == "basic_like":
        cfg.name = "BASIC-like"
        cfg.description = "BASIC-inspired syntax"
        cfg.rename_keyword("if", "IF")
        cfg.rename_keyword("else", "ELSE")
        cfg.rename_keyword("for", "FOR")
        cfg.rename_keyword("while", "WHILE")
        # print is a function, not a keyword
        cfg.rename_function("print", "PRINT")
        cfg.rename_keyword("def", "DEF")
        cfg.rename_keyword("return", "RETURN")
        cfg.set_array_indexing(1, False)
        cfg.syntax_options.statement_terminator = ""
        cfg.disable_satirical_keywords()

    else:
        raise ValueError(f"Unknown preset: {preset_name}")
