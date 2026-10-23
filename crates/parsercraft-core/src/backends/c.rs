//! C backend: AST → ANSI C.
//!
//! Mirrors `parsercraft.codegen.codegen_c` for the constructs the PEG grammar
//! engine produces: assignments, prints, functions, returns, `if`/`while`, and
//! arithmetic. Output is accepted by `cc` and produces the same program output
//! as the Python backend, which the conformance tests check end to end.

use serde_json::Value;

use crate::ast::Ast;

const STRUCTURAL: [&str; 12] = ["=", ";", ":", ",", "(", ")", "{", "}", "[", "]", "->", "<-"];

fn is_operator(node: &Ast) -> bool {
    node.node_type == "Operator"
}

fn meaningful(node: &Ast) -> Vec<&Ast> {
    node.children
        .iter()
        .filter(|child| {
            !(is_operator(child)
                && child
                    .value
                    .as_ref()
                    .and_then(Value::as_str)
                    .is_some_and(|text| STRUCTURAL.contains(&text)))
        })
        .collect()
}

fn value_text(node: &Ast) -> String {
    match &node.value {
        Some(Value::String(text)) => text.clone(),
        Some(Value::Number(number)) => number.to_string(),
        Some(Value::Bool(flag)) => flag.to_string(),
        _ => String::new(),
    }
}

fn render(node: &Ast) -> String {
    let kind = node.node_type.as_str();
    match kind {
        "Number" => match &node.value {
            Some(Value::Number(number)) => {
                if let Some(value) = number.as_i64() {
                    value.to_string()
                } else {
                    number.to_string()
                }
            }
            value => value
                .as_ref()
                .map(|inner| inner.to_string())
                .unwrap_or_default(),
        },
        "String" => format!("\"{}\"", value_text(node)),
        "Identifier" | "IDENT" | "Operator" => value_text(node),
        "expr" | "Expr" | "comparison" | "addition" | "multiplication" | "term" => {
            let operands: Vec<&Ast> = node
                .children
                .iter()
                .filter(|child| !is_operator(child))
                .collect();
            let operators: Vec<&Ast> = node
                .children
                .iter()
                .filter(|child| is_operator(child))
                .collect();
            let mut parts = vec![];
            for (index, operand) in operands.iter().enumerate() {
                parts.push(render(operand));
                if let Some(operator) = operators.get(index) {
                    parts.push(value_text(operator));
                }
            }
            parts.join(" ")
        }
        "factor" | "primary" | "call" | "Call" | "FunctionCall" => {
            let children = meaningful(node);
            if children.is_empty() {
                return value_text(node);
            }
            if kind == "factor" || kind == "primary" {
                return render(children[0]);
            }
            let name = render(children[0]);
            let args: Vec<String> = children[1..].iter().map(|child| render(child)).collect();
            format!("{}({})", name, args.join(", "))
        }
        _ => {
            if node.value.is_some() {
                return value_text(node);
            }
            let children = meaningful(node);
            if let Some(first) = children.first() {
                return render(first);
            }
            "0".to_string()
        }
    }
}

fn infer_type(node: &Ast) -> &'static str {
    match node.node_type.as_str() {
        "Number" => {
            if node.value.as_ref().is_some_and(Value::is_f64) {
                "double"
            } else {
                "int"
            }
        }
        "String" => "const char*",
        _ => "int",
    }
}

#[derive(Default)]
struct Generator {
    body: Vec<String>,
    functions: Vec<(String, Vec<(String, String)>, Vec<String>)>,
    declared: Vec<String>,
}

impl Generator {
    fn emit(&mut self, ast: &Ast) {
        match ast.node_type.as_str() {
            "program" | "Program" | "Module" => {
                for child in &ast.children {
                    self.emit(child);
                }
            }
            "statement" | "Statement" => {
                if let Some((target, value)) = inline_assignment(ast) {
                    let name = render(target);
                    let rendered = render(value);
                    let c_type = infer_type(value);
                    self.body.push(format!("{} {} = {};", c_type, name, rendered));
                    self.declared.push(name);
                } else {
                    for child in &ast.children {
                        self.emit(child);
                    }
                }
            }
            "block" | "Block" => {
                for child in &ast.children {
                    self.emit(child);
                }
            }
            "assignment" | "Assignment" => {
                let children = meaningful(ast);
                if children.len() >= 2 {
                    let name = render(children[0]);
                    let value = render(children[1]);
                    if self.declared.contains(&name) {
                        self.body.push(format!("{} = {};", name, value));
                    } else {
                        let c_type = infer_type(children[1]);
                        self.body.push(format!("{} {} = {};", c_type, name, value));
                        self.declared.push(name);
                    }
                }
            }
            "print_stmt" | "PrintStmt" => {
                let args: Vec<&Ast> =
                    ast.children.iter().filter(|c| !is_operator(c)).collect();
                if let Some(arg) = args.first() {
                    let value = render(arg);
                    let format = if value.starts_with('"') { "%s" } else { "%d" };
                    self.body.push(format!("printf(\"{}\\n\", {});", format, value));
                }
            }
            "return_stmt" | "ReturnStmt" => {
                let args: Vec<&Ast> =
                    ast.children.iter().filter(|c| !is_operator(c)).collect();
                match args.first() {
                    Some(arg) => self.body.push(format!("return {};", render(arg))),
                    None => self.body.push("return;".to_string()),
                }
            }
            "expr_stmt" | "ExprStmt" => {
                let args: Vec<&Ast> =
                    ast.children.iter().filter(|c| !is_operator(c)).collect();
                if let Some(arg) = args.first() {
                    self.body.push(format!("{};", render(arg)));
                }
            }
            "if_stmt" | "IfStmt" => {
                let children: Vec<&Ast> =
                    ast.children.iter().filter(|c| !is_operator(c)).collect();
                if children.is_empty() {
                    return;
                }
                let condition = render(children[0]);
                let blocks: Vec<&Ast> = children[1..]
                    .iter()
                    .filter(|child| matches!(child.node_type.as_str(), "block" | "Block"))
                    .copied()
                    .collect();
                self.body.push(format!("if ({}) {{", condition));
                if let Some(first) = blocks.first() {
                    for stmt in &first.children {
                        self.emit(stmt);
                    }
                }
                for block in blocks.iter().skip(1) {
                    self.body.push("} else {".to_string());
                    for stmt in &block.children {
                        self.emit(stmt);
                    }
                }
                self.body.push("}".to_string());
            }
            "while_stmt" | "WhileStmt" => {
                let children: Vec<&Ast> =
                    ast.children.iter().filter(|c| !is_operator(c)).collect();
                if children.is_empty() {
                    return;
                }
                self.body.push(format!("while ({}) {{", render(children[0])));
                for child in children.iter().skip(1) {
                    self.emit(child);
                }
                self.body.push("}".to_string());
            }
            "function_def" | "FunctionDef" => self.emit_function(ast),
            _ => {
                for child in &ast.children {
                    self.emit(child);
                }
            }
        }
    }

    fn emit_function(&mut self, ast: &Ast) {
        let children = meaningful(ast);
        let mut name = String::new();
        let mut params: Vec<(String, String)> = vec![];
        let mut body_nodes: Vec<&Ast> = vec![];
        for child in children {
            match child.node_type.as_str() {
                "Identifier" | "IDENT" if name.is_empty() => name = value_text(child),
                "param_list" => {
                    for param in &child.children {
                        let rendered = render(param);
                        params.push(("int".to_string(), rendered));
                    }
                }
                "block" | "Block" => body_nodes.extend(child.children.iter()),
                _ => body_nodes.push(child),
            }
        }

        let saved_body = std::mem::take(&mut self.body);
        let saved_declared = std::mem::take(&mut self.declared);
        self.declared = params.iter().map(|(_, name)| name.clone()).collect();
        for node in body_nodes {
            self.emit(node);
        }
        let body = std::mem::replace(&mut self.body, saved_body);
        self.declared = saved_declared;
        self.functions.push((name, params, body));
    }

    fn render_program(&self) -> String {
        let mut lines = vec![
            "// Auto-generated C code from ParserCraft".to_string(),
            String::new(),
            "#include <stdio.h>".to_string(),
            "#include <stdlib.h>".to_string(),
            "#include <string.h>".to_string(),
            String::new(),
            "// Forward declarations".to_string(),
        ];
        for (name, params, _) in &self.functions {
            let rendered: Vec<String> = params
                .iter()
                .map(|(kind, name)| format!("{} {}", kind, name))
                .collect();
            lines.push(format!("int {}({});", name, rendered.join(", ")));
        }
        lines.push(String::new());
        lines.push("// Global variables".to_string());
        lines.push(String::new());

        for (name, params, body) in &self.functions {
            let rendered: Vec<String> = params
                .iter()
                .map(|(kind, name)| format!("{} {}", kind, name))
                .collect();
            lines.push(format!("int {}({}) {{", name, rendered.join(", ")));
            for line in body {
                lines.push(format!("    {}", line));
            }
            lines.push("}".to_string());
            lines.push(String::new());
        }

        lines.push("int main(int argc, char** argv) {".to_string());
        for line in &self.body {
            lines.push(format!("    {}", line));
        }
        lines.push("    return 0;".to_string());
        lines.push("}".to_string());
        lines.join("\n")
    }
}

fn inline_assignment(ast: &Ast) -> Option<(&Ast, &Ast)> {
    let has_assign = ast.children.iter().any(|child| {
        child.node_type == "Operator" && child.value.as_ref().and_then(Value::as_str) == Some("=")
    });
    if !has_assign {
        return None;
    }
    let children = meaningful(ast);
    if children.len() < 2 {
        return None;
    }
    Some((children[0], children[1]))
}

/// Render a program AST as C source.
pub fn generate_c(ast: &Ast) -> String {
    let mut generator = Generator::default();
    generator.emit(ast);
    generator.render_program()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::parse_to_ast;
    use crate::grammar::parse_peg_text;

    const GRAMMAR: &str =
        include_str!("../../../../projects/aurora/grammar.peg");

    fn generate(source: &str) -> String {
        let grammar = parse_peg_text(GRAMMAR).expect("grammar");
        let ast = parse_to_ast(&grammar, source).expect("parse");
        generate_c(&ast)
    }

    #[test]
    fn emits_a_main_with_printf() {
        let code = generate("x = 1 ;\nprint x ;\n");
        assert!(code.contains("int main(int argc, char** argv)"));
        assert!(code.contains("int x = 1;"));
        assert!(code.contains("printf(\"%d\\n\", x);"));
        assert!(code.trim_end().ends_with('}'));
    }

    #[test]
    fn emits_functions_and_calls() {
        let code = generate(
            "fn twice(n) {\n  return n * 2 ;\n}\nprint twice(21) ;\n",
        );
        assert!(code.contains("int twice(int n);"));
        assert!(code.contains("int twice(int n) {"));
        assert!(code.contains("return n * 2;"));
        assert!(code.contains("printf(\"%d\\n\", twice(21));"));
    }

    #[test]
    fn emits_control_flow() {
        let code = generate(
            "i = 0 ;\nwhile i < 3 {\n  i = i + 1 ;\n}\n\
             if i == 3 {\n  print \"done\" ;\n} else {\n  print i ;\n}\n",
        );
        assert!(code.contains("while (i < 3) {"));
        assert!(code.contains("if (i == 3) {"));
        assert!(code.contains("} else {"));
        assert!(code.contains("printf(\"%s\\n\", \"done\");"));
    }

    #[test]
    fn the_whole_sample_compiles_into_a_program() {
        let code = generate(include_str!("../../../../projects/aurora/samples/hello.aur"));
        assert!(code.contains("printf(\"%s\\n\""));
        assert!(code.contains("return 0;"));
    }
}
