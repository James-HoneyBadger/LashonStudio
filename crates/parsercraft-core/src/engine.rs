//! Packrat PEG matching engine.
//!
//! Ported from the Python reference implementation
//! (`parsercraft.parser.grammar.interpreter`); both engines are validated
//! against `tests/conformance/cases.json` so they stay interchangeable.

use std::collections::HashMap;

use crate::ast::{write_ast, Ast, Val};
use crate::grammar::{Grammar, Pattern};

#[derive(Clone)]
pub struct Match {
    ok: bool,
    pos: usize,
    node: Option<Val>,
    children: Vec<Val>,
}

impl Match {
    fn fail(pos: usize) -> Self {
        Match {
            ok: false,
            pos,
            node: None,
            children: vec![],
        }
    }
    fn pass(pos: usize) -> Self {
        Match {
            ok: true,
            pos,
            node: None,
            children: vec![],
        }
    }
    fn with_ok(mut self, ok: bool) -> Self {
        self.ok = ok;
        self
    }
}

pub struct Engine<'a> {
    chars: Vec<char>,
    line_starts: Vec<usize>,
    grammar: &'a Grammar,
    memo: HashMap<(String, usize), Match>,
    max_pos: usize,
    max_rule: String,
    skip_ws: bool,
    line_comments: bool,
    block_comments: bool,
}

impl<'a> Engine<'a> {
    pub fn new(grammar: &'a Grammar, source: &str) -> Result<Self, String> {
        let line_comments = grammar.comments.iter().any(|c| c.starts_with("//"));
        let block_comments = grammar.comments.iter().any(|c| c.starts_with("/\\*"));
        if grammar
            .comments
            .iter()
            .any(|c| !c.starts_with("//") && !c.starts_with("/\\*"))
        {
            return Err("unsupported comment pattern".to_string());
        }
        let chars: Vec<char> = source.chars().collect();
        let mut line_starts = vec![0usize];
        for (index, ch) in chars.iter().enumerate() {
            if *ch == '\n' {
                line_starts.push(index + 1);
            }
        }
        Ok(Engine {
            chars,
            line_starts,
            grammar,
            memo: HashMap::new(),
            max_pos: 0,
            max_rule: String::new(),
            skip_ws: grammar.skip_ws,
            line_comments,
            block_comments,
        })
    }

    pub fn line_col(&self, pos: usize) -> (usize, usize) {
        let line = match self.line_starts.binary_search(&pos) {
            Ok(index) => index,
            Err(index) => index.saturating_sub(1),
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
            } else if self.block_comments
                && pos + 1 < len
                && self.chars[pos] == '/'
                && self.chars[pos + 1] == '*'
            {
                pos += 2;
                while pos + 1 < len
                    && !(self.chars[pos] == '*' && self.chars[pos + 1] == '/')
                {
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
        self.chars[start.min(self.chars.len())..end.min(self.chars.len())]
            .iter()
            .collect()
    }

    fn match_rule(&mut self, name: &str, pos: usize) -> Match {
        if let Some(hit) = self.memo.get(&(name.to_string(), pos)) {
            return hit.clone();
        }
        if pos > self.max_pos || self.max_rule.is_empty() {
            self.max_pos = self.max_pos.max(pos);
            self.max_rule = name.to_string();
        }
        if crate::grammar::SUPPORTED_TOKENS.contains(&name) {
            let result = self.match_token(name, pos);
            self.memo.insert((name.to_string(), pos), result.clone());
            return result;
        }

        let (pattern, node_type, fragment) = match self.grammar.rule(name) {
            Some(rule) => (rule.pattern.clone(), rule.node_type.clone(), rule.fragment),
            None => {
                let result = Match::fail(pos);
                self.memo.insert((name.to_string(), pos), result.clone());
                return result;
            }
        };

        let start = self.skip_ignored(pos);
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
                Some(Val::Text(text)) => ast.value = Some(serde_json::Value::String(text)),
                None => {
                    for child in std::mem::take(&mut result.children) {
                        match child {
                            Val::Ast(node) => ast.children.push(node),
                            Val::Text(text) if !text.trim().is_empty() => {
                                ast.children.push(Ast {
                                    node_type: "Operator".to_string(),
                                    value: Some(serde_json::Value::String(text)),
                                    children: vec![],
                                    line,
                                    column,
                                    source_text: String::new(),
                                });
                            }
                            Val::Text(_) => {}
                        }
                    }
                }
            }
            result = Match {
                ok: true,
                pos: result.pos,
                node: Some(Val::Ast(ast)),
                children: vec![],
            };
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
                    Match {
                        ok: true,
                        pos: pos + 1,
                        node: Some(Val::Text(self.chars[pos].to_string())),
                        children: vec![],
                    }
                } else {
                    self.note_failure(pos);
                    Match::fail(pos)
                }
            }
            Pattern::Rule(name) => self.match_rule(name, pos),
            Pattern::Token(name) => self.match_token(name, pos),
            Pattern::Seq(items) => {
                let mut collected = vec![];
                let mut current = pos;
                for item in items {
                    let result = self.match_pattern(item, current);
                    if !result.ok {
                        return Match::fail(pos);
                    }
                    current = result.pos;
                    if let Some(node) = result.node {
                        collected.push(node);
                    }
                    collected.extend(result.children);
                }
                Match {
                    ok: true,
                    pos: current,
                    node: None,
                    children: collected,
                }
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
                if result.ok {
                    result
                } else {
                    Match::pass(pos)
                }
            }
            Pattern::And(inner) => {
                let ok = self.match_pattern(inner, pos).ok;
                Match::pass(pos).with_ok(ok)
            }
            Pattern::Not(inner) => {
                let ok = self.match_pattern(inner, pos).ok;
                Match::pass(pos).with_ok(!ok)
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
        Match {
            ok: true,
            pos: current,
            node: None,
            children: collected,
        }
    }

    fn match_literal(&mut self, text: &str, pos: usize) -> Match {
        let start = self.skip_ignored(pos);
        let literal: Vec<char> = text.chars().collect();
        let end = start + literal.len();
        if end <= self.chars.len() && self.chars[start..end] == literal[..] {
            let alphabetic = literal.iter().all(|ch| ch.is_alphabetic());
            if alphabetic && end < self.chars.len() {
                let next = self.chars[end];
                if next.is_alphanumeric() || next == '_' {
                    self.note_failure(start);
                    return Match::fail(start);
                }
            }
            return Match {
                ok: true,
                pos: end,
                node: Some(Val::Text(text.to_string())),
                children: vec![],
            };
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
            Match {
                ok: true,
                pos: pos + 1,
                node: Some(Val::Text(ch.to_string())),
                children: vec![],
            }
        } else {
            self.note_failure(pos);
            Match::fail(pos)
        }
    }

    fn token_ast(&self, node_type: &str, value: serde_json::Value, start: usize) -> Match {
        let (line, column) = self.line_col(start);
        Match {
            ok: true,
            pos: self.chars.len(),
            node: Some(Val::Ast(Ast {
                node_type: node_type.to_string(),
                value: Some(value),
                children: vec![],
                line,
                column,
                source_text: String::new(),
            })),
            children: vec![],
        }
    }

    fn match_token(&mut self, token: &str, pos: usize) -> Match {
        let pos = self.skip_ignored(pos);
        let len = self.chars.len();
        match token {
            "NUMBER" => {
                let start = pos;
                let mut index = pos;
                while index < len && self.chars[index].is_ascii_digit() {
                    index += 1;
                }
                let mut is_float = false;
                if index + 1 < len
                    && self.chars[index] == '.'
                    && self.chars[index + 1].is_ascii_digit()
                {
                    is_float = true;
                    index += 1;
                    while index < len && self.chars[index].is_ascii_digit() {
                        index += 1;
                    }
                }
                if index + 1 < len && (self.chars[index] == 'e' || self.chars[index] == 'E') {
                    let mut exponent = index + 1;
                    if exponent < len && (self.chars[exponent] == '+' || self.chars[exponent] == '-')
                    {
                        exponent += 1;
                    }
                    if exponent < len && self.chars[exponent].is_ascii_digit() {
                        is_float = true;
                        while exponent < len && self.chars[exponent].is_ascii_digit() {
                            exponent += 1;
                        }
                        index = exponent;
                    }
                }
                if index == start {
                    self.note_failure(pos);
                    return Match::fail(pos);
                }
                let text = self.slice(start, index);
                let value = if is_float {
                    serde_json::json!(text.parse::<f64>().unwrap_or(0.0))
                } else {
                    serde_json::json!(text.parse::<i64>().unwrap_or(0))
                };
                let mut result = self.token_ast("Number", value, start);
                result.pos = index;
                result
            }
            "STRING" => {
                if pos < len && (self.chars[pos] == '"' || self.chars[pos] == '\'') {
                    let quote = self.chars[pos];
                    let mut index = pos + 1;
                    while index < len {
                        if self.chars[index] == '\\' && index + 1 < len {
                            index += 2;
                        } else if self.chars[index] == quote {
                            let text = self.slice(pos + 1, index);
                            let mut result = self
                                .token_ast("String", serde_json::Value::String(text), pos);
                            result.pos = index + 1;
                            return result;
                        } else {
                            index += 1;
                        }
                    }
                }
                self.note_failure(pos);
                Match::fail(pos)
            }
            "IDENT" => {
                let mut index = pos;
                if index < len && (self.chars[index].is_alphabetic() || self.chars[index] == '_') {
                    index += 1;
                    while index < len
                        && (self.chars[index].is_alphanumeric() || self.chars[index] == '_')
                    {
                        index += 1;
                    }
                    let text = self.slice(pos, index);
                    let mut result = self
                        .token_ast("Identifier", serde_json::Value::String(text), pos);
                    result.pos = index;
                    return result;
                }
                self.note_failure(pos);
                Match::fail(pos)
            }
            "NEWLINE" => {
                if pos < len && self.chars[pos] == '\n' {
                    return Match::pass(pos + 1);
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
        let context = rest.split('\n').next().unwrap_or("");
        format!(
            "Parse error at line {line}, column {column} (in rule '{}'): unexpected '{context}'",
            self.max_rule
        )
    }
}

fn class_matches(class: &str, ch: char) -> bool {
    let chars: Vec<char> = class.chars().collect();
    let mut index = 0;
    let mut negate = false;
    if chars.first() == Some(&'^') {
        negate = true;
        index = 1;
    }
    let mut matched = false;
    while index < chars.len() {
        let current = chars[index];
        if current == '\\' && index + 1 < chars.len() {
            matched = match chars[index + 1] {
                'd' => ch.is_ascii_digit(),
                'w' => ch.is_alphanumeric() || ch == '_',
                's' => ch.is_whitespace(),
                other => ch == other,
            };
            if matched {
                break;
            }
            index += 2;
            continue;
        }
        if index + 2 < chars.len() && chars[index + 1] == '-' {
            if ch >= current && ch <= chars[index + 2] {
                matched = true;
                break;
            }
            index += 3;
            continue;
        }
        if ch == current {
            matched = true;
            break;
        }
        index += 1;
    }
    if negate {
        !matched
    } else {
        matched
    }
}

/// Outcome of a parse: either the JSON AST document or an error tuple.
pub type ParseOutcome = Result<String, (String, usize, String)>;

/// Parse and return the AST value (no JSON encoding).
pub fn parse_to_ast(grammar: &Grammar, source: &str) -> Result<Ast, (String, usize, String)> {
    let mut engine = Engine::new(grammar, source).map_err(|error| (error, 0, String::new()))?;
    let start = grammar.start.clone();
    let result = engine.match_rule(&start, 0);

    if !result.ok {
        let message = engine.error_message();
        return Err((message, engine.max_pos, engine.max_rule.clone()));
    }
    let trailing = engine.skip_ignored(result.pos);
    let rest: String = engine.chars[trailing.min(engine.chars.len())..]
        .iter()
        .collect();
    if !rest.trim().is_empty() {
        let (line, column) = engine.line_col(trailing);
        let context: String = rest.trim().chars().take(30).collect();
        return Err((
            format!("Unexpected input at line {line}, column {column}: '{context}'"),
            trailing,
            String::new(),
        ));
    }
    Ok(match result.node {
        Some(Val::Ast(ast)) => ast,
        _ => Ast { node_type: start, ..Default::default() },
    })
}

pub fn parse_document(grammar: &Grammar, source: &str) -> ParseOutcome {
    let mut engine = Engine::new(grammar, source).map_err(|error| (error, 0, String::new()))?;
    let start = grammar.start.clone();
    let result = engine.match_rule(&start, 0);

    if !result.ok {
        let message = engine.error_message();
        return Err((message, engine.max_pos, engine.max_rule.clone()));
    }

    let trailing = engine.skip_ignored(result.pos);
    let rest: String = engine.chars[trailing.min(engine.chars.len())..]
        .iter()
        .collect();
    if !rest.trim().is_empty() {
        let (line, column) = engine.line_col(trailing);
        let context: String = rest.trim().chars().take(30).collect();
        return Err((
            format!("Unexpected input at line {line}, column {column}: '{context}'"),
            trailing,
            String::new(),
        ));
    }

    let ast = match result.node {
        Some(Val::Ast(ast)) => ast,
        _ => Ast {
            node_type: start,
            ..Default::default()
        },
    };
    let mut document = String::with_capacity(1024);
    document.push_str("{\"ok\":true,\"ast\":");
    write_ast(&ast, &mut document);
    document.push('}');
    Ok(document)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::grammar::parse_peg_text;

    const GRAMMAR: &str = r#"
program   <- statement+
statement <- print_stmt / assignment
print_stmt <- 'print' expr ';'
assignment <- IDENT '=' expr ';'
expr      <- term (('+' / '-') term)*
term      <- NUMBER / IDENT
"#;

    fn parse(source: &str) -> Result<String, (String, usize, String)> {
        let grammar = parse_peg_text(GRAMMAR).expect("grammar should parse");
        parse_document(&grammar, source)
    }

    #[test]
    fn builds_an_ast() {
        let document = parse("x = 1 ;\n").expect("should parse");
        let value: serde_json::Value = serde_json::from_str(&document).unwrap();
        let ast = &value["ast"];
        assert_eq!(ast["type"], "program");
        assert_eq!(ast["children"][0]["type"], "statement");
        assert_eq!(ast["children"][0]["children"][0]["type"], "assignment");
        assert_eq!(
            ast["children"][0]["children"][0]["children"][0]["value"],
            "x"
        );
    }

    #[test]
    fn keeps_operator_nodes() {
        let document = parse("print x + 1 ;\n").expect("should parse");
        let value: serde_json::Value = serde_json::from_str(&document).unwrap();
        let rendered = value["ast"].to_string();
        assert!(rendered.contains("\"Operator\""));
        assert!(rendered.contains("\"print\""));
    }

    #[test]
    fn reports_the_furthest_error_position() {
        let error = parse("x = ;\n").unwrap_err();
        assert!(error.0.starts_with("Parse error at line 1, column 5"), "{}", error.0);
        assert_eq!(error.1, 4);
    }

    #[test]
    fn reports_trailing_input() {
        let error = parse("x = 1 ;\nnot-a-statement\n").unwrap_err();
        assert!(error.0.contains("line 2"), "{}", error.0);
    }

    #[test]
    fn numbers_keep_numeric_values() {
        let document = parse("x = 41 ;\n").expect("should parse");
        let value: serde_json::Value = serde_json::from_str(&document).unwrap();
        let rendered = value["ast"].to_string();
        assert!(rendered.contains("\"Number\""));
        assert!(rendered.contains("41"));
    }
}
