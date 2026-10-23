//! `parsercraft-rs` — the Rust front end for the ParserCraft core.
//!
//! Commands that only need the grammar engine live here, so they run without a
//! Python interpreter: `validate`, `parse`, `rules`, `ast`, and `run` for the
//! grammar plus execution-free checks.

use std::path::Path;
use std::process::ExitCode;

use parsercraft_core::{
    generate_c, generate_python, generate_wasm, parse_document, parse_peg_text,
};

const USAGE: &str = "\
parsercraft-rs — Rust core front end

usage:
  parsercraft-rs validate <grammar.peg>
  parsercraft-rs rules <grammar.peg>
  parsercraft-rs ast <grammar.peg> <program>
  parsercraft-rs parse <grammar.peg> <program>
  parsercraft-rs codegen-c <grammar.peg> <program> [-o out.c] [--compile] [--run]
  parsercraft-rs codegen-py <grammar.peg> <program> [-o out.py] [--run]
  parsercraft-rs codegen-wasm <grammar.peg> <program> [-o out.wat]
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
        "codegen-c" => codegen_c(&args[1..]),
        "codegen-py" => codegen_py(&args[1..]),
        "codegen-wasm" => codegen_wasm(&args[1..]),
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


fn codegen_c(args: &[String]) -> Result<(), String> {
    let grammar_path = args.first().ok_or("missing grammar path")?;
    let program_path = args.get(1).ok_or("missing program path")?;
    let mut output = program_path.trim_end_matches(".aur").to_string() + ".c";
    let mut compile = false;
    let mut run = false;

    let mut index = 2;
    while index < args.len() {
        match args[index].as_str() {
            "-o" | "--output" => {
                index += 1;
                output = args
                    .get(index)
                    .ok_or("missing value for --output")?
                    .clone();
            }
            "--compile" => compile = true,
            "--run" => {
                compile = true;
                run = true;
            }
            other => return Err(format!("unknown option '{other}'")),
        }
        index += 1;
    }

    let grammar_text = std::fs::read_to_string(grammar_path)
        .map_err(|error| format!("cannot read {grammar_path}: {error}"))?;
    let source = std::fs::read_to_string(program_path)
        .map_err(|error| format!("cannot read {program_path}: {error}"))?;

    let code = generate_c(&grammar_text, &source)?;
    std::fs::write(&output, &code).map_err(|error| format!("cannot write {output}: {error}"))?;
    println!("wrote {output} ({} lines)", code.lines().count());

    if compile {
        let binary = output.trim_end_matches(".c").to_string() + ".out";
        let status = std::process::Command::new("cc")
            .args(["-std=c99", "-O1", "-o", &binary, &output])
            .status()
            .map_err(|error| format!("cannot run cc: {error}"))?;
        if !status.success() {
            return Err(format!("cc failed for {output}"));
        }
        println!("compiled {binary}");
        if run {
            let executable = if binary.contains('/') {
                binary.clone()
            } else {
                format!("./{binary}")
            };
            let status = std::process::Command::new(&executable)
                .status()
                .map_err(|error| format!("cannot run {binary}: {error}"))?;
            if !status.success() {
                return Err(format!("{binary} exited with {status}"));
            }
        }
    }
    Ok(())
}

fn codegen_py(args: &[String]) -> Result<(), String> {
    let grammar_path = args.first().ok_or("missing grammar path")?;
    let program_path = args.get(1).ok_or("missing program path")?;
    let mut output = program_path.trim_end_matches(".aur").to_string() + ".py";
    let mut run = false;

    let mut index = 2;
    while index < args.len() {
        match args[index].as_str() {
            "-o" | "--output" => {
                index += 1;
                output = args
                    .get(index)
                    .ok_or("missing value for --output")?
                    .clone();
            }
            "--run" => run = true,
            other => return Err(format!("unknown option '{other}'")),
        }
        index += 1;
    }

    let grammar_text = std::fs::read_to_string(grammar_path)
        .map_err(|error| format!("cannot read {grammar_path}: {error}"))?;
    let source = std::fs::read_to_string(program_path)
        .map_err(|error| format!("cannot read {program_path}: {error}"))?;

    let code = generate_python(&grammar_text, &source)?;
    std::fs::write(&output, &code).map_err(|error| format!("cannot write {output}: {error}"))?;
    println!("wrote {output} ({} lines)", code.lines().count());

    if run {
        let python = std::env::var("PYTHON").unwrap_or_else(|_| "python3".to_string());
        let status = std::process::Command::new(&python)
            .arg(&output)
            .status()
            .map_err(|error| format!("cannot run {python}: {error}"))?;
        if !status.success() {
            return Err(format!("{output} exited with {status}"));
        }
    }
    Ok(())
}

fn codegen_wasm(args: &[String]) -> Result<(), String> {
    let grammar_path = args.first().ok_or("missing grammar path")?;
    let program_path = args.get(1).ok_or("missing program path")?;
    let mut output = program_path.trim_end_matches(".aur").to_string() + ".wat";

    if let Some(flag) = args.get(2) {
        if flag == "-o" || flag == "--output" {
            output = args.get(3).ok_or("missing value for --output")?.clone();
        } else {
            return Err(format!("unknown option '{flag}'"));
        }
    }

    let grammar_text = std::fs::read_to_string(grammar_path)
        .map_err(|error| format!("cannot read {grammar_path}: {error}"))?;
    let source = std::fs::read_to_string(program_path)
        .map_err(|error| format!("cannot read {program_path}: {error}"))?;
    let wat = generate_wasm(&grammar_text, &source)?;
    std::fs::write(&output, &wat).map_err(|error| format!("cannot write {output}: {error}"))?;
    println!("wrote {output} ({} lines)", wat.lines().count());
    Ok(())
}
