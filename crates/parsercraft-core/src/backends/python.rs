//! Python backend: AST → Python source.
//!
//! Emit-only: the generated module is executed by a Python interpreter, which
//! keeps the Rust core free of an embedded runtime. Output shape matches
//! `parsercraft.codegen.python` so either backend can run a project.

use serde_json::Value;

use crate::ast::Ast;

fn is_operator(node: &Ast) -> bool {
    node.node_type == "Operator"
}

fn operator_text(node: &Ast) -> &str {
    node.value.as_deref_str().unwrap_or("")
}

trait ValueExt {
    fn as_deref_str(&self) -> Option<&str>;
}

impl ValueExt for Option<Value> {
    fn as_deref_str(&self) -> Option<&str> {
        self.as_ref().and_then(Value::as_str)
    }
}

fn text(node: &Ast) -> String {
    match &node.value {
        Some(Value::String(value)) => value.clone(),
        Some(Value::Number(number)) => number.to_string(),
        Some(Value::Bool(flag)) => flag.to_string(),
        _ => String::new(),
    }
}

fn non_operators(node: &Ast) -> Vec<&Ast> {
    node.children.iter().filter(|c| !is_operator(c)).collect()
}

fn python_string(value: &str) -> String {
    let escaped = value.replace('\\', "\\\\").replace('\'', "\\'");
    format!("'{escaped}'")
}

fn render(node: &Ast) -> String {
    let kind = node.node_type.as_str();
    match kind {
        "Number" => match &node.value {
            Some(Value::Number(number)) => match number.as_i64() {
                Some(value) => value.to_string(),
                None => number.to_string(),
            },
            other => other.as_ref().map(Value::to_string).unwrap_or_default(),
        },
        "String" => python_string(&text(node)),
        "Identifier" | "IDENT" | "boolean" | "Boolean" => text(node),
        "expr" | "Expr" | "comparison" | "addition" | "multiplication" | "term" => {
            let operands: Vec<&Ast> = node.children.iter().filter(|c| !is_operator(c)).collect();
            let operators: Vec<&Ast> = node.children.iter().filter(|c| is_operator(c)).collect();
            let mut parts = vec![];
            for (index, operand) in operands.iter().enumerate() {
                parts.push(render(operand));
                if let Some(operator) = operators.get(index) {
                    parts.push(operator_text(operator).to_string());
                }
            }
            parts.join(" ")
        }
        "factor" | "primary" => {
            let parens = node.children.iter().any(|child| {
                is_operator(child) && matches!(operator_text(child), "(" | ")")
            });
            match non_operators(node).first() {
                Some(inner) => {
                    let rendered = render(inner);
                    if parens {
                        format!("({rendered})")
                    } else {
                        rendered
                    }
                }
                None => "None".to_string(),
            }
        }
        "call" | "Call" | "FunctionCall" => {
            let children = non_operators(node);
            if children.is_empty() {
                return text(node);
            }
            let name = render(children[0]);
            let args: Vec<String> = children[1..].iter().map(|arg| render(arg)).collect();
            format!("{name}({})", args.join(", "))
        }
        "param_list" => non_operators(node)
            .iter()
            .map(|param| render(param))
            .collect::<Vec<_>>()
            .join(", "),
        "arg_list" => non_operators(node)
            .iter()
            .map(|arg| render(arg))
            .collect::<Vec<_>>()
            .join(", "),
        _ => {
            if node.value.is_some() {
                return text(node);
            }
            match non_operators(node).first() {
                Some(inner) => render(inner),
                None => "0".to_string(),
            }
        }
    }
}

#[derive(Default)]
struct Emitter {
    lines: Vec<String>,
    depth: usize,
}

impl Emitter {
    fn line(&mut self, text: String) {
        self.lines.push(format!("{}{}", "    ".repeat(self.depth), text));
    }

    fn block(&mut self, children: &[Ast]) {
        self.depth += 1;
        for child in children {
            self.emit(child);
        }
        self.depth -= 1;
    }

    fn emit(&mut self, ast: &Ast) {
        match ast.node_type.as_str() {
            "program" | "Program" | "Module" => {
                for child in &ast.children {
                    self.emit(child);
                }
            }
            "statement" | "Statement" => {
                for child in &ast.children {
                    self.emit(child);
                }
            }
            "block" | "Block" => self.block(&ast.children),
            "assignment" | "Assignment" => {
                let children = non_operators(ast);
                if children.len() >= 2 {
                    let name = render(children[0]);
                    let value = render(children[1]);
                    self.line(format!("{name} = {value}"));
                }
            }
            "print_stmt" | "PrintStmt" => {
                let args: Vec<&Ast> = ast
                    .children
                    .iter()
                    .filter(|child| {
                        !(is_operator(child)
                            && matches!(operator_text(child), "print" | "PRINT" | ";" | ","))
                    })
                    .collect();
                if args.is_empty() {
                    self.line("print()".to_string());
                } else {
                    let rendered: Vec<String> = args.iter().map(|arg| render(arg)).collect();
                    self.line(format!("print({})", rendered.join(", ")));
                }
            }
            "return_stmt" | "ReturnStmt" => {
                let children = non_operators(ast);
                match children.first() {
                    Some(value) => self.line(format!("return {}", render(value))),
                    None => self.line("return".to_string()),
                }
            }
            "expr_stmt" | "ExprStmt" => {
                if let Some(value) = non_operators(ast).first() {
                    self.line(render(value));
                }
            }
            "if_stmt" | "IfStmt" => {
                let children = non_operators(ast);
                if children.is_empty() {
                    return;
                }
                self.line(format!("if {}:", render(children[0])));
                let blocks: Vec<&Ast> = children[1..]
                    .iter()
                    .filter(|child| matches!(child.node_type.as_str(), "block" | "Block"))
                    .copied()
                    .collect();
                match blocks.first() {
                    Some(first) if !first.children.is_empty() => self.block(&first.children),
                    _ => self.line("    pass".to_string()),
                }
                for block in blocks.iter().skip(1) {
                    self.line("else:".to_string());
                    if block.children.is_empty() {
                        self.line("    pass".to_string());
                    } else {
                        self.block(&block.children);
                    }
                }
            }
            "while_stmt" | "WhileStmt" => {
                let children = non_operators(ast);
                if children.is_empty() {
                    return;
                }
                self.line(format!("while {}:", render(children[0])));
                let body: Vec<&Ast> = children[1..]
                    .iter()
                    .flat_map(|child| match child.node_type.as_str() {
                        "block" | "Block" => child.children.iter().collect::<Vec<_>>(),
                        _ => vec![*child],
                    })
                    .collect();
                if body.is_empty() {
                    self.line("    pass".to_string());
                } else {
                    self.depth += 1;
                    for child in body {
                        self.emit(child);
                    }
                    self.depth -= 1;
                }
            }
            "function_def" | "FunctionDef" => {
                let children = non_operators(ast);
                let mut name = String::new();
                let mut params: Vec<String> = vec![];
                let mut body: Vec<&Ast> = vec![];
                for child in children {
                    match child.node_type.as_str() {
                        "Identifier" | "IDENT" if name.is_empty() => name = text(child),
                        "param_list" => {
                            params = child
                                .children
                                .iter()
                                .filter(|param| !is_operator(param))
                                .map(|param| render(param))
                                .collect();
                        }
                        "block" | "Block" => body.extend(child.children.iter()),
                        other if other == "param_list" => {}
                        _ => body.push(child),
                    }
                }
                self.line(format!("def {name}({}):", params.join(", ")));
                if body.is_empty() {
                    self.line("    pass".to_string());
                } else {
                    self.depth += 1;
                    for statement in body {
                        self.emit(statement);
                    }
                    self.depth -= 1;
                }
            }
            _ => {
                for child in &ast.children {
                    self.emit(child);
                }
            }
        }
    }
}

/// Render a program AST as Python source.
pub fn generate_python(ast: &Ast) -> String {
    let mut emitter = Emitter::default();
    emitter.emit(ast);
    let mut source = emitter.lines.join("\n");
    source.push('\n');
    source
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::parse_to_ast;
    use crate::grammar::parse_peg_text;

    const GRAMMAR: &str = include_str!("../../../../projects/aurora/grammar.peg");

    fn generate(source: &str) -> String {
        let grammar = parse_peg_text(GRAMMAR).expect("grammar");
        let ast = parse_to_ast(&grammar, source).expect("parse");
        generate_python(&ast)
    }

    #[test]
    fn emits_assignment_and_print() {
        assert_eq!(generate("x = 1 ;\nprint x ;\n"), "x = 1\nprint(x)\n");
    }

    #[test]
    fn quotes_strings_and_keeps_arithmetic() {
        let code = generate("print \"hi\" ;\nprint 1 + 2 * 3 ;\n");
        assert_eq!(code, "print('hi')\nprint(1 + 2 * 3)\n");
    }

    #[test]
    fn emits_functions_and_calls() {
        let code = generate("fn twice(n) {\n  return n * 2 ;\n}\nprint twice(21) ;\n");
        assert_eq!(code, "def twice(n):\n    return n * 2\nprint(twice(21))\n");
    }

    #[test]
    fn emits_control_flow_with_indentation() {
        let code = generate(
            "i = 0 ;\nwhile i < 3 {\n  i = i + 1 ;\n}\n\
             if i == 3 {\n  print \"done\" ;\n} else {\n  print i ;\n}\n",
        );
        assert_eq!(
            code,
            "i = 0\n\
             while i < 3:\n    i = i + 1\n\
             if i == 3:\n    print('done')\nelse:\n    print(i)\n"
        );
    }

    #[test]
    fn parenthesised_expressions_keep_their_shape() {
        assert_eq!(generate("x = (1 + 2) * 3 ;\n"), "x = (1 + 2) * 3\n");
    }
}
