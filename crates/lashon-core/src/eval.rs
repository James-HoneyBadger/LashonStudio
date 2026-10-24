//! Tree-walking evaluator.
//!
//! Executes the AST directly so programs run without a Python interpreter. The
//! observer hook is called before every statement, which is what the debugger
//! uses to implement breakpoints and stepping.

use std::collections::HashMap;
use std::fmt;

use serde_json::Value as Json;

use crate::ast::Ast;

#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
}

impl Value {
    pub fn display(&self) -> String {
        match self {
            Value::Int(value) => value.to_string(),
            Value::Float(value) => {
                if value.fract() == 0.0 {
                    format!("{value:.1}")
                } else {
                    value.to_string()
                }
            }
            Value::Str(text) => text.clone(),
            Value::Bool(flag) => flag.to_string(),
        }
    }

    fn truthy(&self) -> bool {
        match self {
            Value::Int(value) => *value != 0,
            Value::Float(value) => *value != 0.0,
            Value::Str(text) => !text.is_empty(),
            Value::Bool(flag) => *flag,
        }
    }

    fn as_number(&self) -> Result<f64, RuntimeError> {
        match self {
            Value::Int(value) => Ok(*value as f64),
            Value::Float(value) => Ok(*value),
            other => Err(RuntimeError::Type(format!(
                "expected a number, found {}",
                other.kind()
            ))),
        }
    }

    fn kind(&self) -> &'static str {
        match self {
            Value::Int(_) => "int",
            Value::Float(_) => "float",
            Value::Str(_) => "string",
            Value::Bool(_) => "bool",
        }
    }
}

#[derive(Debug)]
pub enum RuntimeError {
    Type(String),
    Name(String),
    Message(String),
}

impl fmt::Display for RuntimeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RuntimeError::Type(message) => write!(formatter, "type error: {message}"),
            RuntimeError::Name(name) => write!(formatter, "undefined name '{name}'"),
            RuntimeError::Message(message) => write!(formatter, "{message}"),
        }
    }
}

/// What the observer wants to happen after being shown a statement.
pub enum Step {
    Continue,
    Pause,
}

/// A snapshot handed to the observer before a statement runs.
pub struct Frame<'a> {
    pub function: &'a str,
    pub line: usize,
    pub locals: &'a HashMap<String, Value>,
}

pub trait Observer {
    fn statement(&mut self, frame: &Frame<'_>) -> Step;
}

enum Flow {
    Normal,
    Return(Value),
    Break,
    Continue,
    Goto(i64),
}

pub struct Machine<'a> {
    functions: HashMap<String, &'a Ast>,
    globals: HashMap<String, Value>,
    output: String,
    observer: Option<Box<dyn Observer + 'a>>,
    call_depth: usize,
    /// Guard against runaway loops in tests and the CLI.
    max_steps: usize,
    steps: usize,
}

impl<'a> Machine<'a> {
    pub fn new(ast: &'a Ast) -> Self {
        let mut functions = HashMap::new();
        for child in &ast.children {
            if let Some(function) = function_node(child) {
                if let Some(name) = function_name(function) {
                    functions.insert(name, function);
                }
            }
        }
        Machine {
            functions,
            globals: HashMap::new(),
            output: String::new(),
            observer: None,
            call_depth: 0,
            max_steps: 5_000_000,
            steps: 0,
        }
    }

    pub fn with_observer(mut self, observer: Box<dyn Observer + 'a>) -> Self {
        self.observer = Some(observer);
        self
    }

    pub fn globals(&self) -> &HashMap<String, Value> {
        &self.globals
    }

    pub fn output(&self) -> &str {
        &self.output
    }

    pub fn run(&mut self, ast: &'a Ast) -> Result<(), RuntimeError> {
        if ast.children.iter().any(|child| child.node_type == "line") {
            return self.run_numbered(ast);
        }
        let mut locals = std::mem::take(&mut self.globals);
        match self.execute_children(&ast.children, &mut locals)? {
            Flow::Normal | Flow::Return(_) => {}
            Flow::Break | Flow::Continue => {
                return Err(RuntimeError::Message(
                    "break/continue outside a loop".to_string(),
                ))
            }
            Flow::Goto(_) => {
                return Err(RuntimeError::Message(
                    "GOTO outside a line-numbered program".to_string(),
                ))
            }
        }
        self.globals = locals;
        Ok(())
    }

    /// Execute a line-numbered program: line numbers double as GOTO labels.
    fn run_numbered(&mut self, ast: &'a Ast) -> Result<(), RuntimeError> {
        let mut labels: HashMap<i64, usize> = HashMap::new();
        for (index, child) in ast.children.iter().enumerate() {
            if child.node_type != "line" {
                continue;
            }
            if let Some(label) = child
                .children
                .iter()
                .find(|node| node.node_type == "Number")
                .and_then(|node| node.value.as_ref().and_then(Json::as_i64))
            {
                labels.insert(label, index);
            }
        }

        let mut locals = std::mem::take(&mut self.globals);
        let mut pc = 0usize;
        while pc < ast.children.len() {
            let node = &ast.children[pc];
            let statement = if node.node_type == "line" {
                node.children
                    .iter()
                    .find(|child| child.node_type != "Number")
            } else {
                Some(node)
            };
            let flow = match statement {
                Some(statement) => self.execute(statement, &mut locals)?,
                None => Flow::Normal,
            };
            self.globals = locals.clone();
            match flow {
                Flow::Normal | Flow::Break | Flow::Continue => pc += 1,
                Flow::Return(_) => break,
                Flow::Goto(target) => match labels.get(&target) {
                    Some(index) => pc = *index,
                    None => {
                        return Err(RuntimeError::Message(format!(
                            "GOTO to undefined line {target}"
                        )))
                    }
                },
            }
        }
        self.globals = locals;
        Ok(())
    }

    fn tick(&mut self) -> Result<(), RuntimeError> {
        self.steps += 1;
        if self.steps > self.max_steps {
            return Err(RuntimeError::Message(
                "execution limit exceeded (possible infinite loop)".to_string(),
            ));
        }
        Ok(())
    }

    fn execute_children(
        &mut self,
        children: &'a [Ast],
        locals: &mut HashMap<String, Value>,
    ) -> Result<Flow, RuntimeError> {
        let refs: Vec<&'a Ast> = children.iter().collect();
        self.execute_list(&refs, locals)
    }

    fn execute_list(
        &mut self,
        children: &[&'a Ast],
        locals: &mut HashMap<String, Value>,
    ) -> Result<Flow, RuntimeError> {
        for child in children {
            match self.execute(child, locals)? {
                Flow::Normal => {}
                other => return Ok(other),
            }
        }
        Ok(Flow::Normal)
    }

    fn execute(
        &mut self,
        node: &'a Ast,
        locals: &mut HashMap<String, Value>,
    ) -> Result<Flow, RuntimeError> {
        self.tick()?;
        // One stop per source statement: the `statement` rule node is the
        // outermost wrapper, so notifying only there avoids duplicate pauses
        // when its children share the same line.
        if matches!(node.node_type.as_str(), "statement" | "Statement") && node.line > 0 {
            if let Some(observer) = self.observer.as_mut() {
                let frame = Frame {
                    function: "main",
                    line: node.line,
                    locals,
                };
                observer.statement(&frame);
            }
        }
        match node.node_type.as_str() {
            "program" | "Program" | "Module" | "block" | "Block" => {
                self.execute_children(&node.children, locals)
            }
            "statement" | "Statement" => {
                if let Some((target, value)) = inline_assignment(node) {
                    self.assign(target, value, locals)?;
                    return Ok(Flow::Normal);
                }
                self.execute_children(&node.children, locals)
            }
            "assignment" | "Assignment" => {
                let children: Vec<&Ast> = node
                    .children
                    .iter()
                    .filter(|child| !is_operator(child))
                    .collect();
                if children.len() >= 2 {
                    self.assign(children[0], children[1], locals)?;
                }
                Ok(Flow::Normal)
            }
            "print_stmt" | "PrintStmt" => {
                let mut parts = vec![];
                for arg in node.children.iter().filter(|child| !is_operator(child)) {
                    parts.push(self.evaluate(arg, locals)?.display());
                }
                if !parts.is_empty() {
                    self.output.push_str(&parts.join(" "));
                    self.output.push('\n');
                }
                Ok(Flow::Normal)
            }
            "break_stmt" | "BreakStmt" => Ok(Flow::Break),
            "continue_stmt" | "ContinueStmt" => Ok(Flow::Continue),
            "return_stmt" | "ReturnStmt" => {
                let value = match node
                    .children
                    .iter()
                    .find(|child| !is_operator(child))
                {
                    Some(value) => self.evaluate(value, locals)?,
                    None => Value::Int(0),
                };
                Ok(Flow::Return(value))
            }
            "if_stmt" | "IfStmt" => {
                let children: Vec<&Ast> = node
                    .children
                    .iter()
                    .filter(|child| !is_operator(child))
                    .collect();
                let condition = match children.first() {
                    Some(condition) => self.evaluate(condition, locals)?.truthy(),
                    None => false,
                };
                let blocks: Vec<&Ast> = children[1..]
                    .iter()
                    .filter(|child| matches!(child.node_type.as_str(), "block" | "Block"))
                    .copied()
                    .collect();
                if blocks.is_empty() {
                    let branch = if condition {
                        children.get(1)
                    } else {
                        children.get(2)
                    };
                    if let Some(statement) = branch {
                        return self.execute(statement, locals);
                    }
                    return Ok(Flow::Normal);
                }
                if condition {
                    if let Some(block) = blocks.first() {
                        return self.execute_children(&block.children, locals);
                    }
                } else if let Some(block) = blocks.get(1) {
                    return self.execute_children(&block.children, locals);
                }
                Ok(Flow::Normal)
            }
            "while_stmt" | "WhileStmt" => {
                let children: Vec<&Ast> = node
                    .children
                    .iter()
                    .filter(|child| !is_operator(child))
                    .collect();
                let (Some(condition), body) = (children.first(), &children[1..]) else {
                    return Ok(Flow::Normal);
                };
                loop {
                    self.tick()?;
                    if !self.evaluate(condition, locals)?.truthy() {
                        break;
                    }
                    match self.execute_list(body, locals)? {
                        Flow::Normal | Flow::Continue => {}
                        Flow::Break => break,
                        Flow::Return(value) => return Ok(Flow::Return(value)),
                        flow @ Flow::Goto(_) => return Ok(flow),
                    }
                }
                Ok(Flow::Normal)
            }
            "function_def" | "FunctionDef" => Ok(Flow::Normal),
            "line" => match node.children.iter().find(|child| child.node_type != "Number") {
                Some(statement) => self.execute(statement, locals),
                None => Ok(Flow::Normal),
            },
            "rem_stmt" | "RemStmt" => Ok(Flow::Normal),
            "end_stmt" | "EndStmt" => Ok(Flow::Return(Value::Int(0))),
            "goto_stmt" | "GotoStmt" => {
                let target = node
                    .children
                    .iter()
                    .find(|child| child.node_type == "Number")
                    .and_then(|child| child.value.as_ref().and_then(Json::as_i64))
                    .ok_or_else(|| RuntimeError::Message("GOTO without a line".to_string()))?;
                Ok(Flow::Goto(target))
            }
            "let_stmt" | "LetStmt" | "assign_stmt" | "AssignStmt" => {
                let children: Vec<&Ast> = node
                    .children
                    .iter()
                    .filter(|child| !is_operator(child))
                    .collect();
                if children.len() >= 2 {
                    self.assign(children[0], children[1], locals)?;
                }
                Ok(Flow::Normal)
            }
            "expr_stmt" | "ExprStmt" => {
                if let Some(expression) = node
                    .children
                    .iter()
                    .find(|child| !is_operator(child))
                {
                    self.evaluate(expression, locals)?;
                }
                Ok(Flow::Normal)
            }
            _ => Ok(Flow::Normal),
        }
    }

    fn assign(
        &mut self,
        target: &Ast,
        value: &'a Ast,
        locals: &mut HashMap<String, Value>,
    ) -> Result<(), RuntimeError> {
        let name = text(target);
        let evaluated = self.evaluate(value, locals)?;
        locals.insert(name, evaluated);
        Ok(())
    }

    fn evaluate(
        &mut self,
        node: &'a Ast,
        locals: &mut HashMap<String, Value>,
    ) -> Result<Value, RuntimeError> {
        match node.node_type.as_str() {
            "Number" => Ok(number_value(node)),
            "String" => Ok(Value::Str(text(node))),
            "boolean" | "Boolean" => Ok(Value::Bool(text(node) == "true")),
            "Identifier" | "IDENT" => {
                let name = text(node);
                locals
                    .get(&name)
                    .or_else(|| self.globals.get(&name))
                    .cloned()
                    .ok_or(RuntimeError::Name(name))
            }
            "expr" | "Expr" | "term" | "comparison" | "addition" | "multiplication" => {
                self.evaluate_chain(node, locals)
            }
            "factor" | "primary" => {
                let inner = node
                    .children
                    .iter()
                    .find(|child| !is_operator(child))
                    .ok_or_else(|| RuntimeError::Message("empty expression".to_string()))?;
                self.evaluate(inner, locals)
            }
            "call" | "Call" | "FunctionCall" => self.call(node, locals),
            _ => match node.value.as_ref() {
                Some(Json::Number(_)) => Ok(number_value(node)),
                Some(Json::String(text)) => Ok(Value::Str(text.clone())),
                _ => Ok(Value::Int(0)),
            },
        }
    }

    fn evaluate_chain(
        &mut self,
        node: &'a Ast,
        locals: &mut HashMap<String, Value>,
    ) -> Result<Value, RuntimeError> {
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

        let mut current = match operands.first() {
            Some(first) => self.evaluate(first, locals)?,
            None => return Ok(Value::Int(0)),
        };
        for (index, operator) in operators.iter().enumerate() {
            let Some(right_node) = operands.get(index + 1) else {
                break;
            };
            let right = self.evaluate(right_node, locals)?;
            current = apply(operator_text(operator), &current, &right)?;
        }
        Ok(current)
    }

    fn call(
        &mut self,
        node: &'a Ast,
        locals: &mut HashMap<String, Value>,
    ) -> Result<Value, RuntimeError> {
        let children: Vec<&Ast> = node
            .children
            .iter()
            .filter(|child| !is_operator(child))
            .collect();
        let name = text(
            children
                .first()
                .ok_or_else(|| RuntimeError::Message("call without a name".to_string()))?,
        );

        let mut arguments = vec![];
        for argument in children.iter().skip(1) {
            if argument.node_type == "arg_list" {
                for item in argument.children.iter().filter(|child| !is_operator(child)) {
                    arguments.push(self.evaluate(item, locals)?);
                }
            } else {
                arguments.push(self.evaluate(argument, locals)?);
            }
        }

        let Some(function) = self.functions.get(&name).copied() else {
            return Err(RuntimeError::Name(name));
        };
        if self.call_depth > 200 {
            return Err(RuntimeError::Message(format!(
                "call depth exceeded in '{name}'"
            )));
        }

        let parameters: Vec<String> = function
            .children
            .iter()
            .find(|child| child.node_type == "param_list")
            .map(|list| {
                list.children
                    .iter()
                    .filter(|child| !is_operator(child))
                    .map(text)
                    .collect()
            })
            .unwrap_or_default();

        let mut frame_locals: HashMap<String, Value> = HashMap::new();
        for (index, parameter) in parameters.iter().enumerate() {
            frame_locals.insert(
                parameter.clone(),
                arguments.get(index).cloned().unwrap_or(Value::Int(0)),
            );
        }

        let body: Vec<&'a Ast> = function
            .children
            .iter()
            .find(|child| matches!(child.node_type.as_str(), "block" | "Block"))
            .map(|block| block.children.iter().collect())
            .unwrap_or_default();

        self.call_depth += 1;
        let result = self.execute_list(&body, &mut frame_locals);
        self.call_depth -= 1;

        match result? {
            Flow::Return(value) => Ok(value),
            _ => Ok(Value::Int(0)),
        }
    }
}

fn apply(operator: &str, left: &Value, right: &Value) -> Result<Value, RuntimeError> {
    if operator == "+" && matches!(left, Value::Str(_)) {
        return Ok(Value::Str(format!("{}{}", left.display(), right.display())));
    }
    let (a, b) = (left.as_number()?, right.as_number()?);
    let integral = matches!(left, Value::Int(_)) && matches!(right, Value::Int(_));
    Ok(match operator {
        "+" => numeric(if integral { a + b } else { a + b }, integral),
        "-" => numeric(a - b, integral),
        "*" => numeric(a * b, integral),
        "/" => {
            if b == 0.0 {
                return Err(RuntimeError::Message("division by zero".to_string()));
            }
            numeric(a / b, integral && b != 0.0 && (a as i64) % (b as i64) == 0)
        }
        "%" => {
            if b as i64 == 0 {
                return Err(RuntimeError::Message("division by zero".to_string()));
            }
            Value::Int(a as i64 % b as i64)
        }
        "==" | "=" => Value::Bool(a == b),
        "!=" | "<>" => Value::Bool(a != b),
        "<" => Value::Bool(a < b),
        "<=" => Value::Bool(a <= b),
        ">" => Value::Bool(a > b),
        ">=" => Value::Bool(a >= b),
        other => {
            return Err(RuntimeError::Message(format!(
                "unsupported operator '{other}'"
            )))
        }
    })
}

fn numeric(value: f64, integral: bool) -> Value {
    if integral && value.fract() == 0.0 {
        Value::Int(value as i64)
    } else {
        Value::Float(value)
    }
}

fn number_value(node: &Ast) -> Value {
    match node.value.as_ref() {
        Some(Json::Number(number)) => match number.as_i64() {
            Some(value) => Value::Int(value),
            None => Value::Float(number.as_f64().unwrap_or(0.0)),
        },
        Some(Json::String(text)) => text
            .parse::<i64>()
            .map(Value::Int)
            .unwrap_or(Value::Int(0)),
        _ => Value::Int(0),
    }
}

fn is_operator(node: &Ast) -> bool {
    node.node_type == "Operator"
}

fn operator_text(node: &Ast) -> &str {
    node.value.as_ref().and_then(Json::as_str).unwrap_or("")
}

fn text(node: &Ast) -> String {
    match &node.value {
        Some(Json::String(value)) => value.clone(),
        Some(Json::Number(number)) => number.to_string(),
        _ => String::new(),
    }
}

fn function_node(node: &Ast) -> Option<&Ast> {
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

fn function_name(node: &Ast) -> Option<String> {
    node.children
        .iter()
        .find(|child| matches!(child.node_type.as_str(), "Identifier" | "IDENT"))
        .map(text)
}

fn inline_assignment<'a>(node: &'a Ast) -> Option<(&'a Ast, &'a Ast)> {
    let has_assign = node
        .children
        .iter()
        .any(|child| is_operator(child) && operator_text(child) == "=");
    if !has_assign {
        return None;
    }
    let children: Vec<&Ast> = node
        .children
        .iter()
        .filter(|child| !is_operator(child))
        .collect();
    if children.len() < 2 {
        return None;
    }
    Some((children[0], children[1]))
}

/// Run a program and return everything it printed.
pub fn run_program(ast: &Ast) -> Result<String, RuntimeError> {
    let mut machine = Machine::new(ast);
    machine.run(ast)?;
    Ok(machine.output().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::parse_to_ast;
    use crate::grammar::parse_peg_text;

    const GRAMMAR: &str = include_str!("../../../projects/aurora/grammar.peg");

    fn run(source: &str) -> String {
        let grammar = parse_peg_text(GRAMMAR).expect("grammar");
        let ast = parse_to_ast(&grammar, source).expect("parse");
        run_program(&ast).expect("run")
    }

    #[test]
    fn prints_arithmetic() {
        assert_eq!(run("print 1 + 2 * 3 ;\n"), "7\n");
    }

    #[test]
    fn variables_and_loops() {
        assert_eq!(
            run("i = 0 ;\nwhile i < 3 {\n  i = i + 1 ;\n}\nprint i ;\n"),
            "3\n"
        );
    }

    const LOOP_GRAMMAR: &str = "program <- statement+
statement <- while_stmt / break_stmt / continue_stmt / assignment / print_stmt
while_stmt <- 'while' comparison block
block <- '{' statement* '}'
break_stmt <- 'break' ';'
continue_stmt <- 'continue' ';'
assignment <- IDENT '=' expr ';'
print_stmt <- 'print' expr ';'
comparison <- expr ('<' / '>' / '==') expr
expr <- NUMBER / IDENT
";

    fn run_with(grammar: &str, source: &str) -> String {
        let grammar = parse_peg_text(grammar).expect("grammar");
        let ast = parse_to_ast(&grammar, source).expect("parse");
        run_program(&ast).expect("run")
    }

    #[test]
    fn break_leaves_the_loop_body_early() {
        let source = "i = 1 ;\nn = 0 ;\nwhile i < 2 {\n  n = 7 ;\n  break ;\n}\nprint n ;\n";
        assert_eq!(run_with(LOOP_GRAMMAR, source), "7\n");
    }

    #[test]
    fn continue_skips_the_rest_of_the_body() {
        let source = "i = 0 ;\nwhile i < 3 {\n  i = 3 ;\n  continue ;\n  i = 9 ;\n}\nprint i ;\n";
        assert_eq!(run_with(LOOP_GRAMMAR, source), "3\n");
    }

    #[test]
    fn functions_and_returns() {
        assert_eq!(
            run("fn twice(n) {\n  return n * 2 ;\n}\nprint twice(21) ;\n"),
            "42\n"
        );
    }

    #[test]
    fn strings_and_conditionals() {
        assert_eq!(
            run("x = 2 ;\nif x == 2 {\n  print \"even\" ;\n} else {\n  print \"odd\" ;\n}\n"),
            "even\n"
        );
    }

    #[test]
    fn division_by_zero_is_an_error() {
        let grammar = parse_peg_text(GRAMMAR).expect("grammar");
        let ast = parse_to_ast(&grammar, "print 1 / 0 ;\n").expect("parse");
        assert!(run_program(&ast).is_err());
    }
}
