
//! Experimental PEG engine for ParserCraft.
//!
//! The Python interpreter in `parsercraft.parser.grammar` is the reference
//! implementation. This crate ports the same algorithm so we can measure how
//! much a native core buys, while `tests/conformance/cases.json` keeps both
//! implementations honest.
//!
//! Only the *matching* algorithm lives here: the grammar is parsed by the
//! Python front end and handed over as JSON, and the resulting AST is returned
//! as JSON for Python to wrap in `SourceAST` objects.

use pyo3::prelude::*;
use serde_json::{json, Value};
use std::collections::HashMap;

const SUPPORTED_TOKENS: [&str; 5] = ["NUMBER", "STRING", "IDENT", "NEWLINE", "EOF"];

#[derive(Clone, Debug)]
enum Pattern {
    Seq(Vec<Pattern>),
    Choice(Vec<Pattern>),
    Star(Box<Pattern>),
    Plus(Box<Pattern>),
    Opt(Box<Pattern>),
    And(Box<Pattern>),
    Not(Box<Pattern>),
    Lit(String),
    Class(String),
    Any,
    Rule(String),
    Token(String),
}

#[derive(Clone, Debug)]
enum Val {
    Ast(Ast),
    Text(String),
}

#[derive(Clone, Debug, Default)]
struct Ast {
    node_type: String,
    value: Option<Value>,
    children: Vec<Ast>,
    line: usize,
    column: usize,
    source_text: String,
}

#[derive(Clone, Debug)]
struct Match {
    ok: bool,
    pos: usize,
    node: Option<Val>,
    children: Vec<Val>,
}

impl Match {
    fn fail(pos: usize) -> Self {
        Match { ok: false, pos, node: None, children: vec![] }
    }
    fn pass(pos: usize) -> Self {
        Match { ok: true, pos, node: None, children: vec![] }
    }
}

struct Rule {
    name: String,
    pattern: Pattern,
    node_type: String,
    fragment: bool,
}

struct Engine<'a> {
    source: &'a str,
    chars: Vec<char>,
    line_starts: Vec<usize>,
    rules: HashMap<String, Rule>,
    start: String,
    skip_ws: bool,
    line_comments: bool,
    block_comments: bool,
    memo: HashMap<(String, usize), Match>,
    max_pos: usize,
    max_rule: String,
}

fn parse_pattern(value: &Value) -> Result<Pattern, String> {
    let kind = value.get("k").and_then(Value::as_str).unwrap_or("");
    let children = || -> Result<Vec<Pattern>, String> {
        value
            .get("c")
            .and_then(Value::as_array)
            .ok_or_else(|| "pattern child list missing".to_string())?
            .iter()
            .map(parse_pattern)
            .collect()
    };
    let first = || -> Result<Box<Pattern>, String> {
        Ok(Box::new(children()?.into_iter().next().ok_or("empty child list")?))
    };
    Ok(match kind {
        "seq" => Pattern::Seq(children()?),
        "choice" => Pattern::Choice(children()?),
        "star" => Pattern::Star(first()?),
        "plus" => Pattern::Plus(first()?),
        "opt" => Pattern::Opt(first()?),
        "and" => Pattern::And(first()?),
        "not" => Pattern::Not(first()?),
        "lit" => Pattern::Lit(value.get("v").and_then(Value::as_str).unwrap_or("").to_string()),
        "cls" => Pattern::Class(value.get("v").and_then(Value::as_str).unwrap_or("").to_string()),
        "any" => Pattern::Any,
        "ref" => Pattern::Rule(value.get("v").and_then(Value::as_str).unwrap_or("").to_string()),
        "tok" => Pattern::Token(value.get("v").and_then(Value::as_str).unwrap_or("").to_string()),
        other => return Err(format!("unsupported pattern kind: {other}")),
    })
}

impl<'a> Engine<'a> {
    fn new(source: &'a str, grammar: &Value) -> Result<Self, String> {
        let mut rules = HashMap::new();
        for entry in grammar.get("rules").and_then(Value::as_array).ok_or("rules missing")? {
            let name = entry.get("name").and_then(Value::as_str).ok_or("rule name")?.to_string();
            let pattern = parse_pattern(entry.get("pattern").ok_or("rule pattern")?)?;
            let node_type = entry
                .get("node_type")
                .and_then(Value::as_str)
                .unwrap_or(&name)
                .to_string();
            let fragment = entry.get("fragment").and_then(Value::as_bool).unwrap_or(false);
            rules.insert(name.clone(), Rule { name, pattern, node_type, fragment });
        }
        let comments: Vec<String> = grammar
            .get("comments")
            .and_then(Value::as_array)
            .map(|list| {
                list.iter()
                    .filter_map(|v| v.as_str().map(str::to_string))
                    .collect()
            })
            .unwrap_or_default();
        let line_comments = comments.iter().any(|c| c.starts_with("//"));
        let block_comments = comments.iter().any(|c| c.starts_with("/\\*"));
        if comments
            .iter()
            .any(|c| !c.starts_with("//") && !c.starts_with("/\\*"))
        {
            return Err("unsupported comment pattern".to_string());
        }

        let chars: Vec<char> = source.chars().collect();
        let mut line_starts = vec![0usize];
        for (i, ch) in chars.iter().enumerate() {
            if *ch == '\n' {
                line_starts.push(i + 1);
            }
        }
        Ok(Engine {
            source,
            chars,
            line_starts,
            rules,
            start: grammar
                .get("start")
                .and_then(Value::as_str)
                .unwrap_or("program")
                .to_string(),
            skip_ws: grammar.get("skip_ws").and_then(Value::as_bool).unwrap_or(true),
            line_comments,
            block_comments,
            memo: HashMap::new(),
            max_pos: 0,
            max_rule: String::new(),
        })
    }

    fn line_col(&self, pos: usize) -> (usize, usize) {
        let line = match self.line_starts.binary_search(&pos) {
            Ok(index) => index,
            Err(index) => index - 1,
        };
        (line + 1, pos - self.line_starts[line] + 1)
    }

    fn note_failure(&mut self, pos: usize) {
        if pos > self.max_pos {
            self.max_pos = pos;
        }
    }

    fn skip_ignored(&self, mut pos: usize) -> usize {
        if !self.skip_ws {
            return pos;
        }
        let len = self.chars.len();
        loop {
            let start = pos;
            while pos < len && matches!(self.chars[pos], ' ' | '\t' | '\r' | '\n') {
                pos += 1;
            }
            if self.line_comments
                && pos + 1 < len
                && self.chars[pos] == '/'
                && self.chars[pos + 1] == '/'
            {
                while pos < len && self.chars[pos] != '\n' {
                    pos += 1;
                }
            } else if self.block_comments && pos + 1 < len && self.chars[pos] == '/' && self.chars[pos + 1] == '*' {
                pos += 2;
                while pos + 1 < len && !(self.chars[pos] == '*' && self.chars[pos + 1] == '/') {
                    pos += 1;
                }
                pos = (pos + 2).min(len);
            }
            if pos == start {
                return pos;
            }
        }
    }

    fn slice(&self, start: usize, end: usize) -> String {
        self.chars[start..end].iter().collect()
    }

    fn match_rule(&mut self, name: &str, pos: usize) -> Match {
        if let Some(hit) = self.memo.get(&(name.to_string(), pos)) {
            return hit.clone();
        }
        if pos > self.max_pos || self.max_rule.is_empty() {
            self.max_pos = self.max_pos.max(pos);
            self.max_rule = name.to_string();
        }
        if SUPPORTED_TOKENS.contains(&name) {
            let result = self.match_token(name, pos);
            self.memo.insert((name.to_string(), pos), result.clone());
            return result;
        }
        let rule = match self.rules.get(name) {
            Some(rule) => rule,
            None => {
                let result = Match::fail(pos);
                self.memo.insert((name.to_string(), pos), result.clone());
                return result;
            }
        };
        let start = self.skip_ignored(pos);
        let node_type = rule.node_type.clone();
        let fragment = rule.fragment;
        let pattern = rule.pattern.clone();
        let mut result = self.match_pattern(&pattern, start);

        if result.ok && !fragment {
            let (line, column) = self.line_col(start);
            let mut ast = Ast {
                node_type,
                value: None,
                children: vec![],
                line,
                column,
                source_text: self.slice(start, result.pos),
            };
            match result.node.take() {
                Some(Val::Ast(child)) => ast.children = vec![child],
                Some(Val::Text(text)) => ast.value = Some(Value::String(text)),
                None => {
                    for child in std::mem::take(&mut result.children) {
                        match child {
                            Val::Ast(node) => ast.children.push(node),
                            Val::Text(text) => {
                                if !text.trim().is_empty() {
                                    ast.children.push(Ast {
                                        node_type: "Operator".to_string(),
                                        value: Some(Value::String(text)),
                                        children: vec![],
                                        line,
                                        column,
                                        source_text: String::new(),
                                    });
                                }
                            }
                        }
                    }
                }
            }
            result = Match { ok: true, pos: result.pos, node: Some(Val::Ast(ast)), children: vec![] };
        }
        self.memo.insert((name.to_string(), pos), result.clone());
        result
    }

    fn match_pattern(&mut self, pattern: &Pattern, pos: usize) -> Match {
        match pattern {
            Pattern::Lit(text) => self.match_literal(text, pos),
            Pattern::Class(class) => self.match_class(class, pos),
            Pattern::Any => {
                if pos < self.chars.len() {
                    Match { ok: true, pos: pos + 1, node: Some(Val::Text(self.chars[pos].to_string())), children: vec![] }
                } else {
                    self.note_failure(pos);
                    Match::fail(pos)
                }
            }
            Pattern::Rule(name) => self.match_rule(name, pos),
            Pattern::Token(name) => self.match_token(name, pos),
            Pattern::Seq(children) => {
                let mut collected = vec![];
                let mut current = pos;
                for child in children {
                    let result = self.match_pattern(child, current);
                    if !result.ok {
                        return Match::fail(pos);
                    }
                    current = result.pos;
                    if let Some(node) = result.node {
                        collected.push(node);
                    }
                    collected.extend(result.children);
                }
                Match { ok: true, pos: current, node: None, children: collected }
            }
            Pattern::Choice(alternatives) => {
                for alternative in alternatives {
                    let result = self.match_pattern(alternative, pos);
                    if result.ok {
                        return result;
                    }
                }
                Match::fail(pos)
            }
            Pattern::Star(inner) => self.match_repeat(inner, pos, 0),
            Pattern::Plus(inner) => self.match_repeat(inner, pos, 1),
            Pattern::Opt(inner) => {
                let result = self.match_pattern(inner, pos);
                if result.ok { result } else { Match::pass(pos) }
            }
            Pattern::And(inner) => {
                let result = self.match_pattern(inner, pos);
                Match::pass(pos).with_ok(result.ok)
            }
            Pattern::Not(inner) => {
                let result = self.match_pattern(inner, pos);
                Match::pass(pos).with_ok(!result.ok)
            }
        }
    }

    fn match_repeat(&mut self, pattern: &Pattern, pos: usize, min: usize) -> Match {
        let mut collected = vec![];
        let mut current = pos;
        let mut count = 0;
        loop {
            let result = self.match_pattern(pattern, current);
            if !result.ok || result.pos == current {
                break;
            }
            current = result.pos;
            count += 1;
            if let Some(node) = result.node {
                collected.push(node);
            }
            collected.extend(result.children);
        }
        if count < min {
            return Match::fail(pos);
        }
        Match { ok: true, pos: current, node: None, children: collected }
    }

    fn match_literal(&mut self, text: &str, pos: usize) -> Match {
        let start = self.skip_ignored(pos);
        let literal: Vec<char> = text.chars().collect();
        let end = start + literal.len();
        if end <= self.chars.len() && self.chars[start..end] == literal[..] {
            let alphabetic = literal.iter().all(|c| c.is_alphabetic());
            if alphabetic && end < self.chars.len() {
                let next = self.chars[end];
                if next.is_alphanumeric() || next == '_' {
                    self.note_failure(start);
                    return Match::fail(start);
                }
            }
            return Match { ok: true, pos: end, node: Some(Val::Text(text.to_string())), children: vec![] };
        }
        self.note_failure(start);
        Match::fail(start)
    }

    fn match_class(&mut self, class: &str, pos: usize) -> Match {
        if pos >= self.chars.len() {
            self.note_failure(pos);
            return Match::fail(pos);
        }
        let ch = self.chars[pos];
        if class_matches(class, ch) {
            Match { ok: true, pos: pos + 1, node: Some(Val::Text(ch.to_string())), children: vec![] }
        } else {
            self.note_failure(pos);
            Match::fail(pos)
        }
    }

    fn match_token(&mut self, token: &str, pos: usize) -> Match {
        let pos = self.skip_ignored(pos);
        let len = self.chars.len();
        match token {
            "NUMBER" => {
                let start = pos;
                let mut i = pos;
                while i < len && self.chars[i].is_ascii_digit() {
                    i += 1;
                }
                let mut is_float = false;
                if i + 1 < len && self.chars[i] == '.' && self.chars[i + 1].is_ascii_digit() {
                    is_float = true;
                    i += 1;
                    while i < len && self.chars[i].is_ascii_digit() {
                        i += 1;
                    }
                }
                if i + 1 < len && (self.chars[i] == 'e' || self.chars[i] == 'E') {
                    let mut j = i + 1;
                    if j < len && (self.chars[j] == '+' || self.chars[j] == '-') {
                        j += 1;
                    }
                    if j < len && self.chars[j].is_ascii_digit() {
                        is_float = true;
                        while j < len && self.chars[j].is_ascii_digit() {
                            j += 1;
                        }
                        i = j;
                    }
                }
                if i == start {
                    self.note_failure(pos);
                    return Match::fail(pos);
                }
                let text = self.slice(start, i);
                let value = if is_float {
                    json!(text.parse::<f64>().unwrap_or(0.0))
                } else {
                    json!(text.parse::<i64>().unwrap_or(0))
                };
                let (line, column) = self.line_col(start);
                Match {
                    ok: true,
                    pos: i,
                    node: Some(Val::Ast(Ast {
                        node_type: "Number".to_string(),
                        value: Some(value),
                        children: vec![],
                        line,
                        column,
                        source_text: String::new(),
                    })),
                    children: vec![],
                }
            }
            "STRING" => {
                if pos < len && (self.chars[pos] == '"' || self.chars[pos] == '\'') {
                    let quote = self.chars[pos];
                    let mut i = pos + 1;
                    while i < len {
                        if self.chars[i] == '\\' && i + 1 < len {
                            i += 2;
                        } else if self.chars[i] == quote {
                            let text = self.slice(pos + 1, i);
                            let (line, column) = self.line_col(pos);
                            return Match {
                                ok: true,
                                pos: i + 1,
                                node: Some(Val::Ast(Ast {
                                    node_type: "String".to_string(),
                                    value: Some(Value::String(text)),
                                    children: vec![],
                                    line,
                                    column,
                                    source_text: String::new(),
                                })),
                                children: vec![],
                            };
                        } else {
                            i += 1;
                        }
                    }
                }
                self.note_failure(pos);
                Match::fail(pos)
            }
            "IDENT" => {
                let mut i = pos;
                if i < len && (self.chars[i].is_alphabetic() || self.chars[i] == '_') {
                    i += 1;
                    while i < len && (self.chars[i].is_alphanumeric() || self.chars[i] == '_') {
                        i += 1;
                    }
                    let text = self.slice(pos, i);
                    let (line, column) = self.line_col(pos);
                    return Match {
                        ok: true,
                        pos: i,
                        node: Some(Val::Ast(Ast {
                            node_type: "Identifier".to_string(),
                            value: Some(Value::String(text)),
                            children: vec![],
                            line,
                            column,
                            source_text: String::new(),
                        })),
                        children: vec![],
                    };
                }
                self.note_failure(pos);
                Match::fail(pos)
            }
            "NEWLINE" => {
                if pos < len && self.chars[pos] == '\n' {
                    return Match::pass(pos + 1).with_node(None);
                }
                if pos + 1 < len && self.chars[pos] == '\r' && self.chars[pos + 1] == '\n' {
                    return Match::pass(pos + 2);
                }
                self.note_failure(pos);
                Match::fail(pos)
            }
            "EOF" => {
                let rest: String = self.chars[pos.min(len)..].iter().collect();
                if rest.trim().is_empty() {
                    return Match::pass(pos);
                }
                self.note_failure(pos);
                Match::fail(pos)
            }
            _ => {
                self.note_failure(pos);
                Match::fail(pos)
            }
        }
    }

    fn error_message(&self) -> String {
        let pos = self.max_pos.min(self.chars.len());
        let (line, column) = self.line_col(pos);
        let rest: String = self.chars[pos..].iter().take(30).collect();
        let context = rest.split('\n').next().unwrap_or("").to_string();
        format!(
            "Parse error at line {line}, column {column} (in rule '{}'): unexpected '{context}'",
            self.max_rule
        )
    }
}

impl Match {
    fn with_ok(mut self, ok: bool) -> Self {
        self.ok = ok;
        self
    }
    fn with_node(mut self, node: Option<Val>) -> Self {
        self.node = node;
        self
    }
}

fn class_matches(class: &str, ch: char) -> bool {
    let chars: Vec<char> = class.chars().collect();
    let mut i = 0;
    let mut negate = false;
    if !chars.is_empty() && chars[0] == '^' {
        negate = true;
        i = 1;
    }
    let mut matched = false;
    while i < chars.len() {
        let mut current = chars[i];
        if current == '\\' && i + 1 < chars.len() {
            let escape = chars[i + 1];
            matched = match escape {
                'd' => ch.is_ascii_digit(),
                'w' => ch.is_alphanumeric() || ch == '_',
                's' => ch.is_whitespace(),
                other => ch == other,
            };
            if matched {
                break;
            }
            i += 2;
            continue;
        }
        if i + 2 < chars.len() && chars[i + 1] == '-' {
            let low = current;
            let high = chars[i + 2];
            if ch >= low && ch <= high {
                matched = true;
                break;
            }
            i += 3;
            continue;
        }
        current = chars[i];
        if ch == current {
            matched = true;
            break;
        }
        i += 1;
    }
    if negate { !matched } else { matched }
}

fn write_ast(ast: &Ast, out: &mut String) {
    out.push_str("{\"type\":");
    out.push_str(&json_string(&ast.node_type));
    out.push_str(",\"value\":");
    match &ast.value {
        Some(value) => out.push_str(&value.to_string()),
        None => out.push_str("null"),
    }
    out.push_str(",\"children\":[");
    for (index, child) in ast.children.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        write_ast(child, out);
    }
    out.push_str("],\"line\":");
    out.push_str(&ast.line.to_string());
    out.push_str(",\"column\":");
    out.push_str(&ast.column.to_string());
    out.push('}');
}

fn json_string(text: &str) -> String {
    serde_json::to_string(text).unwrap_or_else(|_| "\"\"".to_string())
}

fn parse_document(grammar: &Value, source: &str) -> Result<String, (String, usize, String)> {
    let mut engine = Engine::new(source, grammar).map_err(|error| (error, 0, String::new()))?;
    let start = engine.start.clone();
    let result = engine.match_rule(&start, 0);
    if !result.ok {
        let message = engine.error_message();
        return Err((message, engine.max_pos, engine.max_rule.clone()));
    }
    let trailing = engine.skip_ignored(result.pos);
    let rest: String = engine.chars[trailing..].iter().collect();
    if !rest.trim().is_empty() {
        let (line, column) = engine.line_col(trailing);
        let context: String = rest.trim().chars().take(30).collect();
        let message = format!("Unexpected input at line {line}, column {column}: '{context}'");
        return Err((message, trailing, String::new()));
    }
    let ast = match result.node {
        Some(Val::Ast(ast)) => ast,
        _ => Ast { node_type: start, ..Default::default() },
    };
    let mut json = String::with_capacity(1024);
    json.push_str("{\"ok\":true,\"ast\":");
    write_ast(&ast, &mut json);
    json.push('}');
    Ok(json)
}

/// Parse ``source`` with ``grammar`` (both JSON) and return the AST as JSON.
#[pyfunction]
fn parse(grammar_json: &str, source: &str) -> PyResult<String> {
    let grammar: Value = serde_json::from_str(grammar_json)
        .map_err(|error| pyo3::exceptions::PyValueError::new_err(error.to_string()))?;
    match parse_document(&grammar, source) {
        Ok(ast) => Ok(ast),
        Err((message, pos, rule)) => Ok(json!({
            "ok": false,
            "error": message,
            "pos": pos,
            "rule": rule,
        })
        .to_string()),
    }
}

#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pymodule]
fn parsercraft_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(parse, module)?)?;
    module.add_function(wrap_pyfunction!(version, module)?)?;
    Ok(())
}
