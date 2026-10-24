//! ParserCraft core: PEG grammars, the packrat engine, and the AST contract.
//!
//! Two front doors:
//!
//! * Rust callers use [`parse_text`] / [`parse_json_grammar`], which return the
//!   AST as a JSON document.
//! * Python callers get the same functions through the PyO3 bindings
//!   (`parsercraft_native`), which `parsercraft.parser.native` loads.

pub mod ast;
pub mod backends;
pub mod eval;
pub mod engine;
pub mod grammar;

pub use grammar::{parse_peg_text, Grammar, Pattern, Rule};
pub use ast::Ast;
pub use engine::{parse_document, parse_to_ast};
pub use eval::{run_program, Machine, Observer, Step, Value};

/// Generate C source for a program.
pub fn generate_c(grammar_text: &str, source: &str) -> Result<String, String> {
    let grammar = parse_peg_text(grammar_text)?;
    let ast = parse_to_ast(&grammar, source).map_err(|(message, _, _)| message)?;
    Ok(backends::c::generate_c(&ast))
}

/// Generate Python source for a program.
pub fn generate_python(grammar_text: &str, source: &str) -> Result<String, String> {
    let grammar = parse_peg_text(grammar_text)?;
    let ast = parse_to_ast(&grammar, source).map_err(|(message, _, _)| message)?;
    Ok(backends::python::generate_python(&ast))
}

/// Generate WebAssembly text for a program.
pub fn generate_wasm(grammar_text: &str, source: &str) -> Result<String, String> {
    let grammar = parse_peg_text(grammar_text)?;
    let ast = parse_to_ast(&grammar, source).map_err(|(message, _, _)| message)?;
    Ok(backends::wasm::generate_wasm(&ast))
}

/// Generate LLVM IR for a program.
pub fn generate_llvm(grammar_text: &str, source: &str) -> Result<String, String> {
    let grammar = parse_peg_text(grammar_text)?;
    let ast = parse_to_ast(&grammar, source).map_err(|(message, _, _)| message)?;
    Ok(backends::llvm::generate_llvm(&ast))
}

/// Parse ``source`` with PEG text notation, returning the JSON AST document.
pub fn parse_text(grammar_text: &str, source: &str) -> Result<String, String> {
    let grammar = parse_peg_text(grammar_text)?;
    match parse_document(&grammar, source) {
        Ok(document) => Ok(document),
        Err((message, _pos, _rule)) => Err(message),
    }
}

/// Parse ``source`` with a grammar supplied as JSON.
pub fn parse_json_grammar(grammar_json: &str, source: &str) -> Result<String, String> {
    let value: serde_json::Value =
        serde_json::from_str(grammar_json).map_err(|error| error.to_string())?;
    let grammar = grammar::grammar_from_json(&value).map_err(|(message, _, _)| message)?;
    match parse_document(&grammar, source) {
        Ok(document) => Ok(document),
        Err((message, _pos, _rule)) => Err(message),
    }
}

/// Rule names defined by a PEG text grammar.
pub fn rule_names(grammar_text: &str) -> Result<Vec<String>, String> {
    Ok(parse_peg_text(grammar_text)?
        .rules
        .iter()
        .map(|rule| rule.name.clone())
        .collect())
}

#[cfg(feature = "python")]
mod python {
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;

    /// Parse ``source`` with ``grammar_json`` (the Python serializer's format).
    ///
    /// Always returns the JSON envelope ``{"ok": ...}`` so the Python binding
    /// can raise its own ``NativeParseError`` with the engine's message.
    #[pyfunction]
    fn parse(grammar_json: &str, source: &str) -> PyResult<String> {
        match super::parse_json_grammar(grammar_json, source) {
            Ok(document) => Ok(document),
            Err(message) => Ok(serde_json::json!({
                "ok": false,
                "error": message,
            })
            .to_string()),
        }
    }

    /// Parse ``source`` with PEG text notation.
    #[pyfunction]
    fn parse_text(grammar_text: &str, source: &str) -> PyResult<String> {
        super::parse_text(grammar_text, source).map_err(PyValueError::new_err)
    }

    /// Return the rule names defined by ``grammar_text``.
    #[pyfunction]
    fn rules(grammar_text: &str) -> PyResult<Vec<String>> {
        super::rule_names(grammar_text).map_err(PyValueError::new_err)
    }

    #[pyfunction]
    fn version() -> &'static str {
        env!("CARGO_PKG_VERSION")
    }

    #[pymodule]
    fn parsercraft_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
        module.add_function(wrap_pyfunction!(parse, module)?)?;
        module.add_function(wrap_pyfunction!(parse_text, module)?)?;
        module.add_function(wrap_pyfunction!(rules, module)?)?;
        module.add_function(wrap_pyfunction!(version, module)?)?;
        Ok(())
    }
}
