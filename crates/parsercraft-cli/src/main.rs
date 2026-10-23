//! `parsercraft-rs` — the Rust front end for the ParserCraft core.
//!
//! Commands that only need the grammar engine live here, so they run without a
//! Python interpreter: `validate`, `parse`, `rules`, `ast`, and `run` for the
//! grammar plus execution-free checks.

use std::path::Path;
use std::process::ExitCode;

use parsercraft_core::{parse_document, parse_peg_text};

const USAGE: &str = "\
parsercraft-rs — Rust core front end

usage:
  parsercraft-rs validate <grammar.peg>
  parsercraft-rs rules <grammar.peg>
  parsercraft-rs ast <grammar.peg> <program>
  parsercraft-rs parse <grammar.peg> <program>
  parsercraft-rs version
";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let command = args.first().map(String::as_str).unwrap_or("");

    let result = match command {
        "version" | "--version" => {
            println!("parsercraft-rs {}", env!("CARGO_PKG_VERSION"));
            Ok(())
        }
        "validate" => validate(args.get(1)),
        "rules" => rules(args.get(1)),
        "ast" => ast(args.get(1), args.get(2)),
        "parse" => parse(args.get(1), args.get(2)),
        "help" | "--help" | "-h" | "" => {
            print!("{USAGE}");
            Ok(())
        }
        other => Err(format!("unknown command '{other}'\n\n{USAGE}")),
    };

    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("{message}");
            ExitCode::FAILURE
        }
    }
}

fn read(path: Option<&String>, what: &str) -> Result<String, String> {
    let path = path.ok_or_else(|| format!("missing {what} path"))?;
    std::fs::read_to_string(Path::new(path))
        .map_err(|error| format!("cannot read {path}: {error}"))
}

fn validate(path: Option<&String>) -> Result<(), String> {
    let text = read(path, "grammar")?;
    let grammar = parse_peg_text(&text)?;
    let defined: Vec<&str> = grammar.rules.iter().map(|rule| rule.name.as_str()).collect();
    let mut warnings = vec![];
    for rule in &grammar.rules {
        collect_undefined(&rule.pattern, &defined, &rule.name, &mut warnings);
    }
    println!(
        "{}: {} rules, start rule '{}'",
        path.expect("checked"),
        defined.len(),
        grammar.start
    );
    for warning in &warnings {
        println!("warning: {warning}");
    }
    Ok(())
}

fn collect_undefined(
    pattern: &parsercraft_core::Pattern,
    defined: &[&str],
    owner: &str,
    out: &mut Vec<String>,
) {
    use parsercraft_core::Pattern::*;
    match pattern {
        Rule(name) => {
            if !defined.contains(&name.as_str())
                && !parsercraft_core::grammar::SUPPORTED_TOKENS.contains(&name.as_str())
            {
                out.push(format!(
                    "rule '{owner}' references undefined rule '{name}'"
                ));
            }
        }
        Seq(items) | Choice(items) => {
            for item in items {
                collect_undefined(item, defined, owner, out);
            }
        }
        Star(inner) | Plus(inner) | Opt(inner) | And(inner) | Not(inner) => {
            collect_undefined(inner, defined, owner, out)
        }
        Lit(_) | Class(_) | Any | Token(_) => {}
    }
}

fn rules(path: Option<&String>) -> Result<(), String> {
    let text = read(path, "grammar")?;
    let grammar = parse_peg_text(&text)?;
    for rule in &grammar.rules {
        println!("{}", rule.name);
    }
    Ok(())
}

fn ast(grammar_path: Option<&String>, program_path: Option<&String>) -> Result<(), String> {
    let grammar_text = read(grammar_path, "grammar")?;
    let source = read(program_path, "program")?;
    let grammar = parse_peg_text(&grammar_text)?;
    match parse_document(&grammar, &source) {
        Ok(document) => {
            let value: serde_json::Value =
                serde_json::from_str(&document).map_err(|error| error.to_string())?;
            let ast = value.get("ast").cloned().unwrap_or(serde_json::Value::Null);
            println!(
                "{}",
                serde_json::to_string_pretty(&ast).map_err(|error| error.to_string())?
            );
            Ok(())
        }
        Err((message, position, rule)) => Err(format!(
            "{message}\n  at byte {position}{}",
            if rule.is_empty() {
                String::new()
            } else {
                format!(", rule '{rule}'")
            }
        )),
    }
}

fn parse(grammar_path: Option<&String>, program_path: Option<&String>) -> Result<(), String> {
    let grammar_text = read(grammar_path, "grammar")?;
    let source = read(program_path, "program")?;
    let grammar = parse_peg_text(&grammar_text)?;
    match parse_document(&grammar, &source) {
        Ok(document) => {
            let value: serde_json::Value =
                serde_json::from_str(&document).map_err(|error| error.to_string())?;
            let ast = value.get("ast").cloned().unwrap_or(serde_json::Value::Null);
            let nodes = count_nodes(&ast);
            println!("ok: {} AST nodes", nodes);
            Ok(())
        }
        Err((message, _position, _rule)) => Err(message),
    }
}

fn count_nodes(value: &serde_json::Value) -> usize {
    1 + value
        .get("children")
        .and_then(serde_json::Value::as_array)
        .map(|children| children.iter().map(count_nodes).sum())
        .unwrap_or(0)
}
