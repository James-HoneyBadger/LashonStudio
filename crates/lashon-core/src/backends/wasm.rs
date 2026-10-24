//! WebAssembly backend: AST → WAT.
//!
//! Mirrors `lashon.codegen.codegen_wasm`: integer locals, functions and
//! calls, `if`/`else`, `while`, returns, and prints. Strings live in a data
//! segment and are printed through the imported `console.__log_str`; integers
//! go through `console.__log_i32`.

use serde_json::Value;

use crate::ast::Ast;

fn is_operator(node: &Ast) -> bool {
    node.node_type == "Operator"
}

fn op_text(node: &Ast) -> &str {
    node.value.as_ref().and_then(Value::as_str).unwrap_or("")
}

fn text(node: &Ast) -> String {
    match &node.value {
        Some(Value::String(value)) => value.clone(),
        Some(Value::Number(number)) => number.to_string(),
        Some(Value::Bool(flag)) => flag.to_string(),
        _ => String::new(),
    }
}

fn int_of(node: &Ast) -> i64 {
    match &node.value {
        Some(Value::Number(number)) => number.as_i64().unwrap_or(0),
        Some(Value::String(value)) => value.parse().unwrap_or(0),
        _ => 0,
    }
}

fn children_without_operators(node: &Ast) -> Vec<&Ast> {
    node.children.iter().filter(|c| !is_operator(c)).collect()
}

fn binary_instruction(operator: &str) -> Option<&'static str> {
    Some(match operator {
        "+" => "i32.add",
        "-" => "i32.sub",
        "*" => "i32.mul",
        "/" => "i32.div_s",
        "%" => "i32.rem_s",
        "==" => "i32.eq",
        "!=" => "i32.ne",
        "<" => "i32.lt_s",
        "<=" => "i32.le_s",
        ">" => "i32.gt_s",
        ">=" => "i32.ge_s",
        _ => return None,
    })
}

struct Function {
    name: String,
    params: Vec<String>,
    locals: Vec<String>,
    body: Vec<String>,
    exported: bool,
}

impl Function {
    fn to_wat(&self) -> String {
        let mut lines = vec![];
        if self.exported {
            lines.push(format!("(export \"{}\" (func ${}))", self.name, self.name));
        }
        let mut signature = format!("(func ${}", self.name);
        for param in &self.params {
            signature.push_str(&format!(" (param ${param} i32)"));
        }
        if self.name != "main" {
            signature.push_str(" (result i32)");
        } else {
            signature.push_str(" (result i32)");
        }
        lines.push(signature);
        for local in &self.locals {
            lines.push(format!("  (local ${local} i32)"));
        }
        for instruction in &self.body {
            lines.push(format!("  {instruction}"));
        }
        lines.push(")".to_string());
        lines.join("\n")
    }
}

#[derive(Default)]
struct Compiler {
    functions: Vec<Function>,
    data: Vec<(i32, String)>,
    next_data: i32,
    labels: usize,
    // body under construction
    body: Vec<String>,
    locals: Vec<String>,
    params: Vec<String>,
}

impl Compiler {
    fn string_literal(node: &Ast) -> Option<String> {
        if node.node_type == "String" {
            return node.value.as_ref().and_then(Value::as_str).map(str::to_string);
        }
        // `print "hi"` nests the literal inside expr/term/factor wrappers.
        if matches!(
            node.node_type.as_str(),
            "expr" | "term" | "factor" | "primary" | "comparison"
        ) && node
            .children
            .iter()
            .filter(|child| !is_operator(child))
            .count()
            == 1
        {
            return node
                .children
                .iter()
                .find(|child| !is_operator(child))
                .and_then(Self::string_literal);
        }
        None
    }

    fn allocate_string(&mut self, value: &str) -> i32 {
        if let Some((address, _)) = self.data.iter().find(|(_, text)| text == value) {
            return *address;
        }
        let address = self.next_data;
        self.next_data += value.len() as i32;
        self.data.push((address, value.to_string()));
        address
    }

    fn ensure_local(&mut self, name: &str) {
        if self.params.iter().any(|param| param == name) {
            return;
        }
        if !self.locals.iter().any(|local| local == name) {
            self.locals.push(name.to_string());
        }
    }

    fn expression(&mut self, node: &Ast) -> Option<String> {
        match node.node_type.as_str() {
            "Number" => Some(format!("i32.const {}", int_of(node))),
            "Identifier" | "IDENT" => Some(format!("local.get ${}", text(node))),
            "expr" | "Expr" | "comparison" | "term" | "addition" | "multiplication" => {
                let operands: Vec<&Ast> =
                    node.children.iter().filter(|c| !is_operator(c)).collect();
                let operators: Vec<&Ast> =
                    node.children.iter().filter(|c| is_operator(c)).collect();
                if operands.is_empty() {
                    return None;
                }
                let mut current = self.expression(operands[0])?;
                for (index, operator) in operators.iter().enumerate() {
                    let next = match operands.get(index + 1) {
                        Some(operand) => self.expression(operand)?,
                        None => break,
                    };
                    let instruction = binary_instruction(op_text(operator))?;
                    current = format!("{current}\n  {next}\n  {instruction}");
                }
                Some(current)
            }
            "factor" | "primary" => {
                let children = children_without_operators(node);
                self.expression(children.first()?)
            }
            "call" | "Call" | "FunctionCall" => {
                let children = children_without_operators(node);
                let name = children.first().map(|child| text(child))?;
                let mut instructions = vec![];
                for arg in children.iter().skip(1) {
                    if arg.node_type == "arg_list" {
                        for item in children_without_operators(arg) {
                            instructions.push(self.expression(item)?);
                        }
                    } else {
                        instructions.push(self.expression(arg)?);
                    }
                }
                instructions.push(format!("call ${name}"));
                Some(instructions.join("\n  "))
            }
            "String" => None,
            _ => {
                if node.node_type == "Number" {
                    return Some(format!("i32.const {}", int_of(node)));
                }
                None
            }
        }
    }

    fn push_expression(&mut self, node: &Ast) -> bool {
        match self.expression(node) {
            Some(rendered) => {
                for line in rendered.lines() {
                    self.body.push(line.trim().to_string());
                }
                true
            }
            None => false,
        }
    }

    fn statement(&mut self, node: &Ast) {
        match node.node_type.as_str() {
            "program" | "Program" | "Module" | "block" | "Block" => {
                for child in &node.children {
                    self.statement(child);
                }
            }
            "statement" | "Statement" => {
                if let Some((target, value)) = inline_assignment(node) {
                    self.assign(target, value);
                } else {
                    for child in &node.children {
                        self.statement(child);
                    }
                }
            }
            "assignment" | "Assignment" => {
                let children = children_without_operators(node);
                if children.len() >= 2 {
                    self.assign(children[0], children[1]);
                }
            }
            "function_def" | "FunctionDef" => {}
            "print_stmt" | "PrintStmt" => {
                for child in children_without_operators(node) {
                    match Self::string_literal(child) {
                        Some(value) => {
                            let address = self.allocate_string(&value);
                            self.body.push(format!("i32.const {address}"));
                            self.body.push(format!("i32.const {}", value.len()));
                            self.body.push("call $__log_str".to_string());
                        }
                        None => {
                            if self.push_expression(child) {
                                self.body.push("call $__log_i32".to_string());
                            }
                        }
                    }
                }
            }
            "return_stmt" | "ReturnStmt" => {
                match children_without_operators(node).first() {
                    Some(value) => {
                        if !self.push_expression(value) {
                            self.body.push("i32.const 0".to_string());
                        }
                    }
                    None => self.body.push("i32.const 0".to_string()),
                }
                self.body.push("return".to_string());
            }
            "expr_stmt" | "ExprStmt" => {
                if let Some(value) = children_without_operators(node).first() {
                    if self.push_expression(value) {
                        self.body.push("drop".to_string());
                    }
                }
            }
            "if_stmt" | "IfStmt" => {
                let children: Vec<&Ast> =
                    node.children.iter().filter(|c| !is_operator(c)).collect();
                if children.is_empty() || !self.push_expression(children[0]) {
                    return;
                }
                self.body.push("if".to_string());
                let blocks: Vec<&Ast> = children[1..]
                    .iter()
                    .filter(|child| matches!(child.node_type.as_str(), "block" | "Block"))
                    .copied()
                    .collect();
                match blocks.first() {
                    Some(first) => {
                        for child in &first.children {
                            self.statement(child);
                        }
                    }
                    None => {
                        for child in children.iter().skip(1) {
                            self.statement(child);
                        }
                    }
                }
                if let Some(otherwise) = blocks.get(1) {
                    self.body.push("else".to_string());
                    for child in &otherwise.children {
                        self.statement(child);
                    }
                }
                self.body.push("end".to_string());
            }
            "while_stmt" | "WhileStmt" => {
                let children: Vec<&Ast> =
                    node.children.iter().filter(|c| !is_operator(c)).collect();
                if children.is_empty() {
                    return;
                }
                self.labels += 1;
                let exit = format!("while_exit_{}", self.labels);
                let loop_label = format!("while_loop_{}", self.labels);
                self.body.push(format!("block ${exit}"));
                self.body.push(format!("loop ${loop_label}"));
                if !self.push_expression(children[0]) {
                    return;
                }
                self.body.push("i32.eqz".to_string());
                self.body.push(format!("br_if ${exit}"));
                for child in children.iter().skip(1) {
                    self.statement(child);
                }
                self.body.push(format!("br ${loop_label}"));
                self.body.push("end".to_string());
                self.body.push("end".to_string());
            }
            _ => {
                for child in &node.children {
                    self.statement(child);
                }
            }
        }
    }

    fn assign(&mut self, target: &Ast, value: &Ast) {
        let name = text(target);
        self.ensure_local(&name);
        if self.push_expression(value) {
            self.body.push(format!("local.set ${name}"));
        }
    }

    fn compile_function(&mut self, node: &Ast) {
        let children = children_without_operators(node);
        let mut name = String::new();
        let mut params: Vec<String> = vec![];
        let mut body_nodes: Vec<&Ast> = vec![];
        for child in children {
            match child.node_type.as_str() {
                "Identifier" | "IDENT" if name.is_empty() => name = text(child),
                "param_list" => {
                    params = children_without_operators(child)
                        .iter()
                        .map(|param| text(param))
                        .collect();
                }
                "block" | "Block" => body_nodes.extend(child.children.iter()),
                _ => body_nodes.push(child),
            }
        }

        let saved_body = std::mem::take(&mut self.body);
        let saved_locals = std::mem::take(&mut self.locals);
        let saved_params = std::mem::replace(&mut self.params, params.clone());
        for node in body_nodes {
            self.statement(node);
        }
        self.body.push("i32.const 0".to_string());
        let body = std::mem::replace(&mut self.body, saved_body);
        let locals = std::mem::replace(&mut self.locals, saved_locals);
        self.params = saved_params;
        self.functions.push(Function {
            name,
            params,
            locals,
            body,
            exported: false,
        });
    }

    fn render(&self) -> String {
        let mut lines = vec!["(module $module".to_string()];
        lines.push(
            "  (import \"console\" \"__log_i32\" (func $__log_i32 (param $value i32)))"
                .to_string(),
        );
        lines.push(
            "  (import \"console\" \"__log_str\" (func $__log_str (param $ptr i32) (param $len i32)))"
                .to_string(),
        );
        lines.push(
            "  (import \"math\" \"__sqrt\" (func $__sqrt (param $value f64) (result f64)))"
                .to_string(),
        );
        lines.push("  (memory 256)".to_string());
        lines.push("  (export \"memory\" (memory 0))".to_string());
        for function in &self.functions {
            for line in function.to_wat().lines() {
                if line.starts_with("(export") {
                    lines.push(format!("  {line}"));
                } else {
                    lines.push(format!("  {line}"));
                }
            }
        }
        lines.push(
            "  (export \"main\" (func $main))".to_string(),
        );
        lines.push("  (func $main (result i32)".to_string());
        for instruction in &self.body {
            lines.push(format!("    {instruction}"));
        }
        lines.push("    i32.const 0".to_string());
        lines.push("  )".to_string());
        for (address, value) in &self.data {
            let escaped: String = value
                .bytes()
                .map(|byte| {
                    if (32..127).contains(&byte) && byte != b'"' && byte != b'\\' {
                        (byte as char).to_string()
                    } else {
                        format!("\\{byte:02x}")
                    }
                })
                .collect();
            lines.push(format!("  (data (i32.const {address}) \"{escaped}\")"));
        }
        lines.push(")".to_string());
        lines.join("\n")
    }
}

/// Return the `function_def` node, looking through a `statement` wrapper.
fn function_def(node: &Ast) -> Option<&Ast> {
    if node.node_type == "function_def" {
        return Some(node);
    }
    if matches!(node.node_type.as_str(), "statement" | "Statement") {
        return node
            .children
            .iter()
            .find(|child| child.node_type == "function_def");
    }
    None
}

fn inline_assignment(node: &Ast) -> Option<(&Ast, &Ast)> {
    let has_assign = node.children.iter().any(|child| {
        is_operator(child) && op_text(child) == "="
    });
    if !has_assign {
        return None;
    }
    let children = children_without_operators(node);
    if children.len() < 2 {
        return None;
    }
    Some((children[0], children[1]))
}

/// Render a program AST as a WebAssembly text module.
pub fn generate_wasm(ast: &Ast) -> String {
    let mut compiler = Compiler::default();
    let mut top_level: Vec<&Ast> = vec![];
    let mut functions: Vec<&Ast> = vec![];
    for child in &ast.children {
        if let Some(function) = function_def(child) {
            functions.push(function);
        } else {
            top_level.push(child);
        }
    }
    for function in functions {
        compiler.compile_function(function);
    }
    for statement in top_level {
        compiler.statement(statement);
    }
    compiler.render()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::parse_to_ast;
    use crate::grammar::parse_peg_text;

    const GRAMMAR: &str = include_str!("../../../../projects/aurora/grammar.peg");

    fn wat(source: &str) -> String {
        let grammar = parse_peg_text(GRAMMAR).expect("grammar");
        let ast = parse_to_ast(&grammar, source).expect("parse");
        generate_wasm(&ast)
    }

    #[test]
    fn emits_imports_memory_and_main() {
        let module = wat("x = 1 ;\nprint x ;\n");
        assert!(module.starts_with("(module $module"));
        assert!(module.contains("(import \"console\" \"__log_i32\""));
        assert!(module.contains("(export \"memory\" (memory 0))"));
        assert!(module.contains("(export \"main\" (func $main))"));
        assert!(module.contains("call $__log_i32"));
        assert!(module.trim_end().ends_with(')'));
    }

    #[test]
    fn strings_become_data_segments() {
        let module = wat("print \"hi\" ;\n");
        assert!(module.contains("call $__log_str"));
        assert!(module.contains("(data (i32.const 0) \"hi\")"));
    }

    #[test]
    fn emits_functions_and_calls() {
        let module = wat("fn twice(n) {\n  return n * 2 ;\n}\nprint twice(21) ;\n");
        assert!(module.contains("(func $twice (param $n i32) (result i32)"));
        assert!(module.contains("i32.mul"));
        assert!(module.contains("call $twice"));
    }

    #[test]
    fn control_flow_uses_block_and_loop() {
        let module = wat("i = 0 ;\nwhile i < 3 {\n  i = i + 1 ;\n}\n");
        assert!(module.contains("block $while_exit_1"));
        assert!(module.contains("loop $while_loop_1"));
        assert!(module.contains("br_if $while_exit_1"));
        assert!(module.contains("i32.lt_s"));
    }
}
