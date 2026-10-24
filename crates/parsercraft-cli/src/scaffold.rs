//! `init` templates and the `demo` tour.
//!
//! These commands are grammar-first: they need only the Rust core, so a
//! project scaffolded here runs with `parsercraft-rs run`.

use std::path::{Path, PathBuf};

pub const AURORA: &str = include_str!("../../../projects/aurora/grammar.peg");

pub const CALCULATOR: &str = r#"// Expression calculator
program   <- statement+
statement <- print_stmt / assignment
print_stmt <- 'print' expr ';'
assignment <- IDENT '=' expr ';'
expr      <- term (('+' / '-') term)*
term      <- factor (('*' / '/' / '%') factor)*
factor    <- NUMBER / STRING / IDENT / '(' expr ')'
"#;

pub const MINIMAL: &str = r#"// Smallest useful grammar
program    <- statement+
statement  <- print_stmt / assignment
print_stmt <- 'print' expr ';'
assignment <- IDENT '=' expr ';'
expr       <- term (('+' / '-') term)*
term       <- factor (('*' / '/') factor)*
factor     <- NUMBER / STRING / IDENT / '(' expr ')'
"#;

const AURORA_SAMPLE: &str = r#"// Welcome!
print "Hello from your language!" ;
x = 6 * 7 ;
print x ;
"#;

const CALCULATOR_SAMPLE: &str = r#"// Try arithmetic
width = 12 ;
height = 7 ;
print width * height ;
print (width + height) * 2 ;
"#;

const MINIMAL_SAMPLE: &str = r#"print "hello" ;
answer = 6 * 7 ;
print answer ;
"#;

pub fn slug(name: &str) -> String {
    let slug: String = name
        .chars()
        .map(|ch| if ch.is_alphanumeric() { ch.to_ascii_lowercase() } else { '-' })
        .collect();
    let trimmed = slug.trim_matches('-').to_string();
    if trimmed.is_empty() {
        "my-language".to_string()
    } else {
        trimmed
    }
}

/// Create a grammar-first project. Returns the project root.
pub fn init(
    name: &str,
    directory: &Path,
    template: &str,
    force: bool,
) -> Result<PathBuf, String> {
    let (grammar, sample) = match template {
        "aurora" => (AURORA, AURORA_SAMPLE),
        "calculator" => (CALCULATOR, CALCULATOR_SAMPLE),
        "minimal" => (MINIMAL, MINIMAL_SAMPLE),
        other => {
            return Err(format!(
                "unknown template '{other}' (use aurora, calculator, or minimal)"
            ))
        }
    };

    let root = directory.join(slug(name));
    if root.exists() {
        let empty = std::fs::read_dir(&root)
            .map(|mut entries| entries.next().is_none())
            .unwrap_or(false);
        if !empty && !force {
            return Err(format!(
                "{} already exists and is not empty (use --force)",
                root.display()
            ));
        }
    }

    std::fs::create_dir_all(root.join("samples"))
        .map_err(|error| format!("cannot create {}: {error}", root.display()))?;
    std::fs::write(root.join("grammar.peg"), grammar)
        .map_err(|error| format!("cannot write grammar.peg: {error}"))?;
    std::fs::write(root.join("samples").join("hello.aur"), sample)
        .map_err(|error| format!("cannot write sample: {error}"))?;
    std::fs::write(
        root.join("README.md"),
        format!(
            "# {name}\n\nA {template} grammar scaffolded by `parsercraft-rs`.\n\n\
             - `grammar.peg` — PEG rules\n\
             - `samples/hello.aur` — runnable example\n\n\
             ```bash\n\
             parsercraft-rs run grammar.peg samples/hello.aur\n\
             parsercraft-rs codegen-c grammar.peg samples/hello.aur --run\n\
             ```\n"
        ),
    )
    .map_err(|error| format!("cannot write README.md: {error}"))?;

    Ok(root)
}

/// Print a guided tour of the whole pipeline using a built-in grammar.
pub fn demo() -> Result<(), String> {
    use parsercraft_core::backends::{c, llvm, python, wasm};
    use parsercraft_core::{eval::run_program, parse_peg_text, parse_to_ast};

    let source = "x = 6 * 7 ;\nprint x ;\nprint \"done\" ;\n";
    let grammar = parse_peg_text(CALCULATOR)?;
    println!("grammar   : {} rules, start '{}'", grammar.rules.len(), grammar.start);
    println!("source    : {} bytes", source.len());

    let ast = parse_to_ast(&grammar, source).map_err(|(message, _, _)| message)?;
    println!("ast       : {} top-level nodes", ast.children.len());

    for (label, rendered) in [
        ("python", python::generate_python(&ast)),
        ("c", c::generate_c(&ast)),
        ("wasm", wasm::generate_wasm(&ast)),
        ("llvm", llvm::generate_llvm(&ast)),
    ] {
        println!("{label:<9} : {} lines", rendered.lines().count());
    }

    let output = run_program(&ast).map_err(|error| error.to_string())?;
    println!("run       : {} lines of output", output.lines().count());
    for line in output.lines() {
        println!("  {line}");
    }
    Ok(())
}
