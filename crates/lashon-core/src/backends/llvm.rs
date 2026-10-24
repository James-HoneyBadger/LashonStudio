//! LLVM IR backend: AST → textual IR (opaque pointers, SSA temporaries).
//!
//! Mirrors `lashon.codegen.llvm_ir` for the constructs the PEG engine
//! produces: integer functions and calls, assignments, prints (integers and
//! strings), `if`/`else`, `while`, and returns.

use serde_json::Value;
use serde_json::Value as Json;

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
        _ => String::new(),
    }
}

fn children_without_operators(node: &Ast) -> Vec<&Ast> {
    node.children.iter().filter(|c| !is_operator(c)).collect()
}

fn escape_bytes(value: &str) -> String {
    let mut out = String::new();
    for byte in value.bytes() {
        if (32..127).contains(&byte) && byte != b'"' && byte != b'\\' {
            out.push(byte as char);
        } else {
            out.push_str(&format!("\\{byte:02X}"));
        }
    }
    out.push_str("\\00");
    out
}

fn binary_instruction(operator: &str) -> Option<&'static str> {
    Some(match operator {
        "+" => "add",
        "-" => "sub",
        "*" => "mul",
        "/" => "sdiv",
        "%" => "srem",
        _ => return None,
    })
}

fn comparison_instruction(operator: &str) -> Option<&'static str> {
    Some(match operator {
        "==" | "=" => "eq",
        "!=" | "<>" => "ne",
        "<" => "slt",
        "<=" => "sle",
        ">" => "sgt",
        ">=" => "sge",
        _ => return None,
    })
}

#[derive(Default)]
struct FunctionState {
    name: String,
    params: Vec<String>,
    slots: Vec<(String, String)>,
    body: Vec<String>,
    terminated: bool,
    labels: usize,
}

#[derive(Default)]
struct Compiler {
    functions: Vec<FunctionState>,
    globals: Vec<String>,
    formats: Vec<(String, String)>,
    strings: Vec<(String, String)>,
    counter: usize,
    current: FunctionState,
}

impl Compiler {
    fn temp(&mut self) -> String {
        self.counter += 1;
        format!("%{}", self.counter)
    }

    fn label(&mut self, prefix: &str) -> String {
        self.current.labels += 1;
        format!("{prefix}.{}", self.current.labels)
    }

    fn push(&mut self, line: impl Into<String>) {
        self.current.body.push(line.into());
    }

    fn format_global(&mut self, kind: &str) -> String {
        if let Some((name, _)) = self.formats.iter().find(|(_, k)| k == kind) {
            return name.clone();
        }
        let name = format!("@.fmt.{}", self.formats.len());
        let text = if kind == "d" { "%d\\0A\\00" } else { "%s\\0A\\00" };
        let width = if kind == "d" { 4 } else { 4 };
        self.globals.push(format!(
            "{name} = private unnamed_addr constant [{width} x i8] c\"{text}\""
        ));
        self.formats.push((name.clone(), kind.to_string()));
        name
    }

    fn string_global(&mut self, value: &str) -> String {
        if let Some((name, _)) = self.strings.iter().find(|(_, v)| v == value) {
            return name.clone();
        }
        let name = format!("@.str.{}", self.strings.len());
        let encoded = escape_bytes(value);
        let width = value.len() + 1;
        self.globals.push(format!(
            "{name} = private unnamed_addr constant [{width} x i8] c\"{encoded}\""
        ));
        self.strings.push((name.clone(), value.to_string()));
        name
    }

    fn slot(&mut self, name: &str) -> String {
        if let Some((_, location)) = self
            .current
            .slots
            .iter()
            .find(|(slot, _)| slot == name)
        {
            return location.clone();
        }
        let location = self.temp();
        self.push(format!("{location} = alloca i32"));
        if self.current.params.iter().any(|param| param == name) {
            self.push(format!("store i32 %{name}, ptr {location}"));
        } else {
            self.push(format!("store i32 0, ptr {location}"));
        }
        self.current.slots.push((name.to_string(), location.clone()));
        location
    }

    fn expression(&mut self, node: &Ast) -> Option<String> {
        match node.node_type.as_str() {
            "Number" => {
                let value = node.value.as_ref().and_then(Value::as_i64).unwrap_or(0);
                Some(value.to_string())
            }
            "Identifier" | "IDENT" => {
                let location = self.slot(&text(node));
                let result = self.temp();
                self.push(format!("{result} = load i32, ptr {location}"));
                Some(result)
            }
            "expr" | "Expr" | "term" | "comparison" | "addition" | "multiplication" => {
                let operands: Vec<&Ast> =
                    node.children.iter().filter(|c| !is_operator(c)).collect();
                let operators: Vec<&Ast> =
                    node.children.iter().filter(|c| is_operator(c)).collect();
                let mut current = self.expression(operands.first()?)?;
                for (index, operator) in operators.iter().enumerate() {
                    let next = self.expression(operands.get(index + 1)?)?;
                    let instruction = binary_instruction(op_text(operator))?;
                    let result = self.temp();
                    self.push(format!("{result} = {instruction} i32 {current}, {next}"));
                    current = result;
                }
                Some(current)
            }
            "factor" | "primary" => {
                let children = children_without_operators(node);
                self.expression(children.first()?)
            }
            "call" | "Call" | "FunctionCall" => {
                let children = children_without_operators(node);
                let name = text(children.first()?);
                let mut args = vec![];
                for arg in children.iter().skip(1) {
                    if arg.node_type == "arg_list" {
                        for item in children_without_operators(arg) {
                            args.push(self.expression(item)?);
                        }
                    } else {
                        args.push(self.expression(arg)?);
                    }
                }
                let rendered: Vec<String> =
                    args.iter().map(|arg| format!("i32 {arg}")).collect();
                let result = self.temp();
                self.push(format!(
                    "{result} = call i32 @{name}({})",
                    rendered.join(", ")
                ));
                Some(result)
            }
            _ => None,
        }
    }

    /// Render a value usable by `br i1` (comparisons become `icmp`).
    fn condition(&mut self, node: &Ast) -> Option<String> {
        if node.node_type == "comparison" {
            let operands: Vec<&Ast> =
                node.children.iter().filter(|c| !is_operator(c)).collect();
            let operator = node
                .children
                .iter()
                .find(|child| is_operator(child))
                .map(|child| op_text(child))
                .unwrap_or("");
            if let Some(instruction) = comparison_instruction(operator) {
                let left = self.expression(operands.first()?)?;
                let right = self.expression(operands.get(1)?)?;
                let result = self.temp();
                self.push(format!(
                    "{result} = icmp {instruction} i32 {left}, {right}"
                ));
                return Some(result);
            }
        }
        let value = self.expression(node)?;
        let result = self.temp();
        self.push(format!("{result} = icmp ne i32 {value}, 0"));
        Some(result)
    }

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

    fn statement(&mut self, node: &Ast) {
        match node.node_type.as_str() {
            "program" | "Program" | "Module" | "block" | "Block" => {
                for child in &node.children {
                    self.statement(child);
                }
            }
            "statement" | "Statement" => {
                if Self::function_def(node).is_some() {
                    return;
                }
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
            "rem_stmt" | "RemStmt" => {}
            "end_stmt" | "EndStmt" => {
                self.push("ret i32 0");
                self.current.terminated = true;
            }
            "goto_stmt" | "GotoStmt" => {
                if let Some(target) = node
                    .children
                    .iter()
                    .find(|child| child.node_type == "Number")
                    .and_then(|child| child.value.as_ref().and_then(Json::as_i64))
                {
                    self.push(format!("br label %L{target}"));
                    self.current.terminated = true;
                }
            }
            "let_stmt" | "LetStmt" | "assign_stmt" | "AssignStmt" => {
                let children: Vec<&Ast> =
                    node.children.iter().filter(|c| !is_operator(c)).collect();
                if children.len() >= 2 {
                    self.assign(children[0], children[1]);
                }
            }
            "print_stmt" | "PrintStmt" => {
                let args: Vec<&Ast> = node
                    .children
                    .iter()
                    .filter(|child| {
                        !(is_operator(child)
                            && matches!(
                                child.value.as_ref().and_then(Json::as_str),
                                Some("PRINT" | "print" | ";" | ",")
                            ))
                    })
                    .collect();
                if args.len() > 1 {
                    let mut specs: Vec<String> = vec![];
                    let mut values: Vec<String> = vec![];
                    for arg in &args {
                        if let Some(text) = string_leaf(arg) {
                            let global = self.string_global(&text);
                            specs.push("%s".to_string());
                            values.push(format!("ptr {global}"));
                        } else if let Some(value) = self.expression(arg) {
                            specs.push("%d".to_string());
                            values.push(format!("i32 {value}"));
                        }
                    }
                    if specs.is_empty() {
                        return;
                    }
                    let visible = specs.join(" ");
                    let width = visible.len() + 2;
                    let name = format!("@.fmt.{}", self.formats.len());
                    self.formats.push((name.clone(), "custom".to_string()));
                    self.globals.push(format!(
                        "{name} = private unnamed_addr constant [{width} x i8] c\"{visible}\\0A\\00\""
                    ));
                    let result = self.temp();
                    self.push(format!(
                        "{result} = call i32 (ptr, ...) @printf(ptr {name}, {})",
                        values.join(", ")
                    ));
                    return;
                }
                for arg in children_without_operators(node) {
                    if arg.node_type == "String"
                        || (matches!(arg.node_type.as_str(), "expr" | "factor" | "term")
                            && string_leaf(arg).is_some())
                    {
                        let value = string_leaf(arg).unwrap_or_default();
                        let global = self.string_global(&value);
                        let format = self.format_global("s");
                        let result = self.temp();
                        self.push(format!(
                            "{result} = call i32 (ptr, ...) @printf(ptr {format}, ptr {global})"
                        ));
                    } else if let Some(value) = self.expression(arg) {
                        let format = self.format_global("d");
                        let result = self.temp();
                        self.push(format!(
                            "{result} = call i32 (ptr, ...) @printf(ptr {format}, i32 {value})"
                        ));
                    }
                }
            }
            "return_stmt" | "ReturnStmt" => {
                let value = match children_without_operators(node).first() {
                    Some(value) => self.expression(value),
                    None => Some("0".to_string()),
                };
                self.push(format!("ret i32 {}", value.unwrap_or_else(|| "0".to_string())));
                self.current.terminated = true;
            }
            "expr_stmt" | "ExprStmt" => {
                if let Some(value) = children_without_operators(node).first() {
                    self.expression(value);
                }
            }
            "if_stmt" | "IfStmt" => {
                let children: Vec<&Ast> =
                    node.children.iter().filter(|c| !is_operator(c)).collect();
                let condition = match self.condition(children.first().copied().unwrap_or(&Ast::default())) {
                    Some(value) => value,
                    None => return,
                };
                let then_label = self.label("if.then");
                let end_label = self.label("if.end");
                let else_label = self.label("if.else");
                let blocks: Vec<&Ast> = children[1..]
                    .iter()
                    .filter(|child| matches!(child.node_type.as_str(), "block" | "Block"))
                    .copied()
                    .collect();
                let has_else = blocks.len() > 1;
                self.push(format!(
                    "br i1 {condition}, label %{then_label}, label %{}",
                    if has_else { else_label.clone() } else { end_label.clone() }
                ));
                if blocks.is_empty() {
                    self.push(format!("{then_label}:"));
                    if let Some(then_branch) = children.get(1) {
                        self.statement(then_branch);
                    }
                    if !self.current.terminated {
                        self.push(format!("br label %{end_label}"));
                    }
                    self.current.terminated = false;
                    if let Some(else_branch) = children.get(2) {
                        self.push(format!("{else_label}:"));
                        self.statement(else_branch);
                        if !self.current.terminated {
                            self.push(format!("br label %{end_label}"));
                        }
                        self.current.terminated = false;
                    }
                    self.push(format!("{end_label}:"));
                    return;
                }
                self.push(format!("{then_label}:"));
                if let Some(first) = blocks.first() {
                    for child in &first.children {
                        self.statement(child);
                    }
                }
                if !self.current.terminated {
                    self.push(format!("br label %{end_label}"));
                }
                self.current.terminated = false;
                if let Some(otherwise) = blocks.get(1) {
                    self.push(format!("{else_label}:"));
                    for child in &otherwise.children {
                        self.statement(child);
                    }
                    if !self.current.terminated {
                        self.push(format!("br label %{end_label}"));
                    }
                    self.current.terminated = false;
                }
                self.push(format!("{end_label}:"));
            }
            "while_stmt" | "WhileStmt" => {
                let children: Vec<&Ast> =
                    node.children.iter().filter(|c| !is_operator(c)).collect();
                if children.is_empty() {
                    return;
                }
                let cond_label = self.label("while.cond");
                let body_label = self.label("while.body");
                let end_label = self.label("while.end");
                self.push(format!("br label %{cond_label}"));
                self.push(format!("{cond_label}:"));
                let condition = match self.condition(children[0]) {
                    Some(value) => value,
                    None => return,
                };
                self.push(format!(
                    "br i1 {condition}, label %{body_label}, label %{end_label}"
                ));
                self.push(format!("{body_label}:"));
                for child in children.iter().skip(1) {
                    self.statement(child);
                }
                if !self.current.terminated {
                    self.push(format!("br label %{cond_label}"));
                }
                self.current.terminated = false;
                self.push(format!("{end_label}:"));
            }
            _ => {
                for child in &node.children {
                    self.statement(child);
                }
            }
        }
    }

    /// Emit `main`. Line-numbered programs become one basic block per line so
    /// `GOTO` can branch to the label; everything else runs sequentially.
    fn emit_main(&mut self, top_level: &[&Ast]) {
        let numbered: Vec<(i64, &Ast)> = top_level
            .iter()
            .filter(|node| node.node_type == "line")
            .filter_map(|node| {
                let label = node
                    .children
                    .iter()
                    .find(|child| child.node_type == "Number")
                    .and_then(|child| child.value.as_ref().and_then(Json::as_i64))?;
                let statement = node
                    .children
                    .iter()
                    .find(|child| child.node_type != "Number")?;
                Some((label, statement))
            })
            .collect();

        if numbered.is_empty() {
            for statement in top_level {
                self.statement(statement);
            }
            return;
        }

        let first = numbered[0].0;
        self.push(format!("br label %L{first}"));
        for (index, (label, statement)) in numbered.iter().enumerate() {
            self.push(format!("L{label}:"));
            self.current.terminated = false;
            self.statement(statement);
            if !self.current.terminated {
                match numbered.get(index + 1) {
                    Some((next, _)) => self.push(format!("br label %L{next}")),
                    None => self.push("ret i32 0".to_string()),
                }
            }
        }
        self.current.terminated = true;
    }

    fn assign(&mut self, target: &Ast, value: &Ast) {
        let name = text(target);
        let location = self.slot(&name);
        if let Some(rendered) = self.expression(value) {
            self.push(format!("store i32 {rendered}, ptr {location}"));
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

        self.current = FunctionState {
            name: name.clone(),
            params: params.clone(),
            ..Default::default()
        };
        for node in body_nodes {
            self.statement(node);
        }
        if !self.current.terminated {
            self.push("ret i32 0");
        }
        self.functions.push(std::mem::take(&mut self.current));
    }

    fn render(&self) -> String {
        let mut lines = vec![
            "; Auto-generated LLVM IR from Lashon".to_string(),
            "; Compile with: clang output.ll -o program".to_string(),
            String::new(),
            "declare i32 @printf(ptr, ...)".to_string(),
            String::new(),
        ];
        lines.extend(self.globals.iter().cloned());
        if !self.globals.is_empty() {
            lines.push(String::new());
        }
        for function in &self.functions {
            let rendered: Vec<String> = function
                .params
                .iter()
                .map(|param| format!("i32 %{param}"))
                .collect();
            lines.push(format!(
                "define i32 @{}({}) {{",
                function.name,
                rendered.join(", ")
            ));
            lines.push("entry:".to_string());
            lines.extend(function.body.iter().map(|line| format!("  {line}")));
            lines.push("}".to_string());
            lines.push(String::new());
        }
        lines.join("\n")
    }
}

fn string_leaf(node: &Ast) -> Option<String> {
    if node.node_type == "String" {
        return node.value.as_ref().and_then(Value::as_str).map(str::to_string);
    }
    if matches!(
        node.node_type.as_str(),
        "expr" | "term" | "factor" | "primary"
    ) {
        let children = children_without_operators(node);
        if children.len() == 1 {
            return string_leaf(children[0]);
        }
    }
    None
}

fn inline_assignment(node: &Ast) -> Option<(&Ast, &Ast)> {
    let has_assign = node
        .children
        .iter()
        .any(|child| is_operator(child) && op_text(child) == "=");
    if !has_assign {
        return None;
    }
    let children = children_without_operators(node);
    if children.len() < 2 {
        return None;
    }
    Some((children[0], children[1]))
}

/// Render a program AST as LLVM IR text.
pub fn generate_llvm(ast: &Ast) -> String {
    let mut compiler = Compiler::default();
    let mut top_level: Vec<&Ast> = vec![];
    let mut functions: Vec<&Ast> = vec![];
    for child in &ast.children {
        match Compiler::function_def(child) {
            Some(function) => functions.push(function),
            None => top_level.push(child),
        }
    }
    for function in functions {
        compiler.compile_function(function);
    }

    compiler.current = FunctionState {
        name: "main".to_string(),
        ..Default::default()
    };
    compiler.emit_main(&top_level);
    if !compiler.current.terminated {
        compiler.push("ret i32 0");
    }
    compiler.functions.push(std::mem::take(&mut compiler.current));
    compiler.render()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::parse_to_ast;
    use crate::grammar::parse_peg_text;

    const GRAMMAR: &str = include_str!("../../../../projects/aurora/grammar.peg");

    fn ir(source: &str) -> String {
        let grammar = parse_peg_text(GRAMMAR).expect("grammar");
        let ast = parse_to_ast(&grammar, source).expect("parse");
        generate_llvm(&ast)
    }

    #[test]
    fn declares_printf_and_main() {
        let module = ir("x = 1 ;\nprint x ;\n");
        assert!(module.contains("declare i32 @printf(ptr, ...)"));
        assert!(module.contains("define i32 @main()"));
        assert!(module.contains("ret i32 0"));
    }

    #[test]
    fn strings_become_globals() {
        let module = ir("print \"hi\" ;\n");
        assert!(module.contains("private unnamed_addr constant [3 x i8] c\"hi\\00\""));
        assert!(module.contains("ptr @.str.0"));
    }

    #[test]
    fn arithmetic_uses_ssa_temporaries() {
        let module = ir("x = 1 + 2 * 3 ;\n");
        assert!(module.contains("= mul i32"));
        assert!(module.contains("= add i32"));
    }

    #[test]
    fn functions_and_calls() {
        let module = ir("fn twice(n) {\n  return n * 2 ;\n}\nprint twice(21) ;\n");
        assert!(module.contains("define i32 @twice(i32 %n)"));
        assert!(module.contains("call i32 @twice(i32 21)"));
    }

    #[test]
    fn control_flow_uses_basic_blocks() {
        let module = ir("i = 0 ;\nwhile i < 3 {\n  i = i + 1 ;\n}\n");
        assert!(module.contains("br label %while.cond.1"));
        assert!(module.contains("= icmp slt i32"));
        assert!(module.contains("while.end.3:"));
    }
}
