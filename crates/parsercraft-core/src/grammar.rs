//! Grammar model, JSON conversion, and the PEG text-notation parser.
//!
//! Keeping the text parser here means the Rust core is self-sufficient: the
//! CLI can read a `.peg` file without Python, while the Python bindings keep
//! using the reference grammar parser.

use serde_json::{json, Map, Value};

pub const SUPPORTED_TOKENS: [&str; 5] = ["NUMBER", "STRING", "IDENT", "NEWLINE", "EOF"];

#[derive(Clone, Debug, PartialEq)]
pub enum Pattern {
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
pub struct Rule {
    pub name: String,
    pub node_type: String,
    pub fragment: bool,
    pub pattern: Pattern,
}

#[derive(Clone, Debug)]
pub struct Grammar {
    pub name: String,
    pub start: String,
    pub skip_ws: bool,
    pub comments: Vec<String>,
    pub rules: Vec<Rule>,
}

impl Default for Grammar {
    fn default() -> Self {
        Grammar {
            name: "custom".to_string(),
            start: "program".to_string(),
            skip_ws: true,
            comments: vec!["//.*".to_string(), "/\\*[\\s\\S]*?\\*/".to_string()],
            rules: vec![],
        }
    }
}

impl Grammar {
    pub fn rule(&self, name: &str) -> Option<&Rule> {
        self.rules.iter().find(|rule| rule.name == name)
    }
}

// ---------------------------------------------------------------------------
// JSON bridge (shared with the Python bindings)
// ---------------------------------------------------------------------------

pub fn pattern_from_json(value: &Value) -> Result<Pattern, String> {
    let kind = value.get("k").and_then(Value::as_str).unwrap_or("");
    let children = || -> Result<Vec<Pattern>, String> {
        value
            .get("c")
            .and_then(Value::as_array)
            .ok_or_else(|| "pattern child list missing".to_string())?
            .iter()
            .map(pattern_from_json)
            .collect()
    };
    let first = || -> Result<Box<Pattern>, String> {
        Ok(Box::new(
            children()?.into_iter().next().ok_or("empty child list")?,
        ))
    };
    let text = || value.get("v").and_then(Value::as_str).unwrap_or("").to_string();
    Ok(match kind {
        "seq" => Pattern::Seq(children()?),
        "choice" => Pattern::Choice(children()?),
        "star" => Pattern::Star(first()?),
        "plus" => Pattern::Plus(first()?),
        "opt" => Pattern::Opt(first()?),
        "and" => Pattern::And(first()?),
        "not" => Pattern::Not(first()?),
        "lit" => Pattern::Lit(text()),
        "cls" => Pattern::Class(text()),
        "any" => Pattern::Any,
        "ref" => Pattern::Rule(text()),
        "tok" => Pattern::Token(text()),
        other => return Err(format!("unsupported pattern kind: {other}")),
    })
}

pub fn pattern_to_json(pattern: &Pattern) -> Value {
    match pattern {
        Pattern::Seq(children) => json!({
            "k": "seq",
            "c": children.iter().map(pattern_to_json).collect::<Vec<_>>()
        }),
        Pattern::Choice(children) => json!({
            "k": "choice",
            "c": children.iter().map(pattern_to_json).collect::<Vec<_>>()
        }),
        Pattern::Star(inner) => json!({"k": "star", "c": [pattern_to_json(inner)]}),
        Pattern::Plus(inner) => json!({"k": "plus", "c": [pattern_to_json(inner)]}),
        Pattern::Opt(inner) => json!({"k": "opt", "c": [pattern_to_json(inner)]}),
        Pattern::And(inner) => json!({"k": "and", "c": [pattern_to_json(inner)]}),
        Pattern::Not(inner) => json!({"k": "not", "c": [pattern_to_json(inner)]}),
        Pattern::Lit(text) => json!({"k": "lit", "v": text}),
        Pattern::Class(text) => json!({"k": "cls", "v": text}),
        Pattern::Any => json!({"k": "any"}),
        Pattern::Rule(name) => json!({"k": "ref", "v": name}),
        Pattern::Token(name) => json!({"k": "tok", "v": name}),
    }
}

pub fn grammar_from_json(value: &Value) -> Result<Grammar, (String, usize, String)> {
    let mut rules = vec![];
    for entry in value
        .get("rules")
        .and_then(Value::as_array)
        .ok_or(("rules missing".to_string(), 0, String::new()))?
    {
        let name = entry
            .get("name")
            .and_then(Value::as_str)
            .ok_or(("rule name missing".to_string(), 0, String::new()))?
            .to_string();
        let pattern = pattern_from_json(entry.get("pattern").unwrap_or(&Value::Null))
            .map_err(|error| (error, 0, String::new()))?;
        let node_type = entry
            .get("node_type")
            .and_then(Value::as_str)
            .unwrap_or(&name)
            .to_string();
        let fragment = entry
            .get("fragment")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        rules.push(Rule {
            name,
            node_type,
            fragment,
            pattern,
        });
    }
    let comments = value
        .get("comments")
        .and_then(Value::as_array)
        .map(|list| {
            list.iter()
                .filter_map(|item| item.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_else(|| Grammar::default().comments);
    Ok(Grammar {
        name: value
            .get("name")
            .and_then(Value::as_str)
            .unwrap_or("custom")
            .to_string(),
        start: value
            .get("start")
            .and_then(Value::as_str)
            .unwrap_or("program")
            .to_string(),
        skip_ws: value.get("skip_ws").and_then(Value::as_bool).unwrap_or(true),
        comments,
        rules,
    })
}

pub fn grammar_to_json(grammar: &Grammar) -> Value {
    let mut rules = vec![];
    for rule in &grammar.rules {
        let mut entry = Map::new();
        entry.insert("name".to_string(), json!(rule.name));
        entry.insert("node_type".to_string(), json!(rule.node_type));
        entry.insert("fragment".to_string(), json!(rule.fragment));
        entry.insert("pattern".to_string(), pattern_to_json(&rule.pattern));
        rules.push(Value::Object(entry));
    }
    json!({
        "name": grammar.name,
        "start": grammar.start,
        "skip_ws": grammar.skip_ws,
        "comments": grammar.comments,
        "rules": rules,
    })
}

// ---------------------------------------------------------------------------
// PEG text notation
// ---------------------------------------------------------------------------

/// Parse PEG text notation (`rule <- pattern`) into a grammar.
pub fn parse_peg_text(text: &str) -> Result<Grammar, String> {
    let mut grammar = Grammar::default();
    let mut current: Option<(String, Vec<String>)> = None;

    let flush = |current: &mut Option<(String, Vec<String>)>, grammar: &mut Grammar| -> Result<(), String> {
        if let Some((name, parts)) = current.take() {
            let pattern_text = parts.join(" ");
            let pattern = parse_pattern(&pattern_text)
                .map_err(|error| format!("in rule '{name}': {error}"))?;
            grammar.rules.push(Rule {
                node_type: name.clone(),
                name,
                fragment: false,
                pattern,
            });
        }
        Ok(())
    };

    for (number, raw) in text.lines().enumerate() {
        let line = strip_comment(raw);
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        if trimmed.starts_with('|') {
            let (_, parts) = current
                .as_mut()
                .ok_or_else(|| format!("line {}: alternative without a rule", number + 1))?;
            parts.push(trimmed.to_string());
            continue;
        }
        if let Some((name, body)) = trimmed.split_once("<-") {
            flush(&mut current, &mut grammar)?;
            current = Some((name.trim().to_string(), vec![body.trim().to_string()]));
            continue;
        }
        match current.as_mut() {
            Some((_, parts)) if line.starts_with(' ') || line.starts_with('\t') => {
                parts.push(trimmed.to_string());
            }
            _ => {
                return Err(format!(
                    "line {}: expected 'name <- pattern', found '{trimmed}'",
                    number + 1
                ))
            }
        }
    }
    flush(&mut current, &mut grammar)?;

    if grammar.rules.is_empty() {
        return Err("grammar defines no rules".to_string());
    }
    if grammar.rule(&grammar.start).is_none() {
        grammar.start = grammar.rules[0].name.clone();
    }
    Ok(grammar)
}

fn strip_comment(line: &str) -> String {
    let mut quote: Option<char> = None;
    let mut chars = line.chars().peekable();
    let mut out = String::new();
    while let Some(ch) = chars.next() {
        match quote {
            Some(active) => {
                out.push(ch);
                if ch == active {
                    quote = None;
                }
            }
            None => {
                if ch == '\'' || ch == '"' {
                    quote = Some(ch);
                    out.push(ch);
                } else if ch == '/' && chars.peek() == Some(&'/') {
                    break;
                } else {
                    out.push(ch);
                }
            }
        }
    }
    out
}

struct Cursor<'a> {
    chars: Vec<char>,
    pos: usize,
    _text: &'a str,
}

impl<'a> Cursor<'a> {
    fn new(text: &'a str) -> Self {
        Cursor {
            chars: text.chars().collect(),
            pos: 0,
            _text: text,
        }
    }

    fn peek(&self) -> Option<char> {
        self.chars.get(self.pos).copied()
    }

    fn bump(&mut self) -> Option<char> {
        let ch = self.peek()?;
        self.pos += 1;
        Some(ch)
    }

    fn skip_ws(&mut self) {
        while matches!(self.peek(), Some(ch) if ch.is_whitespace()) {
            self.pos += 1;
        }
    }

    fn eat(&mut self, expected: char) -> bool {
        if self.peek() == Some(expected) {
            self.pos += 1;
            true
        } else {
            false
        }
    }
}

fn parse_pattern(text: &str) -> Result<Pattern, String> {
    let mut cursor = Cursor::new(text);
    let pattern = parse_choice(&mut cursor)?;
    cursor.skip_ws();
    if cursor.peek().is_some() {
        return Err(format!(
            "unexpected trailing input at column {}",
            cursor.pos + 1
        ));
    }
    Ok(pattern)
}

fn parse_choice(cursor: &mut Cursor) -> Result<Pattern, String> {
    let mut alternatives = vec![parse_sequence(cursor)?];
    loop {
        cursor.skip_ws();
        if !cursor.eat('/') {
            break;
        }
        alternatives.push(parse_sequence(cursor)?);
    }
    Ok(if alternatives.len() == 1 {
        alternatives.remove(0)
    } else {
        Pattern::Choice(alternatives)
    })
}

fn parse_sequence(cursor: &mut Cursor) -> Result<Pattern, String> {
    let mut items = vec![];
    loop {
        cursor.skip_ws();
        match cursor.peek() {
            None | Some('/') | Some(')') => break,
            _ => items.push(parse_prefix(cursor)?),
        }
    }
    if items.is_empty() {
        return Err("empty pattern".to_string());
    }
    Ok(if items.len() == 1 {
        items.remove(0)
    } else {
        Pattern::Seq(items)
    })
}

fn parse_prefix(cursor: &mut Cursor) -> Result<Pattern, String> {
    cursor.skip_ws();
    match cursor.peek() {
        Some('&') => {
            cursor.bump();
            Ok(Pattern::And(Box::new(parse_prefix(cursor)?)))
        }
        Some('!') => {
            cursor.bump();
            Ok(Pattern::Not(Box::new(parse_prefix(cursor)?)))
        }
        _ => parse_suffix(cursor),
    }
}

fn parse_suffix(cursor: &mut Cursor) -> Result<Pattern, String> {
    let atom = parse_atom(cursor)?;
    cursor.skip_ws();
    Ok(match cursor.peek() {
        Some('*') => {
            cursor.bump();
            Pattern::Star(Box::new(atom))
        }
        Some('+') => {
            cursor.bump();
            Pattern::Plus(Box::new(atom))
        }
        Some('?') => {
            cursor.bump();
            Pattern::Opt(Box::new(atom))
        }
        _ => atom,
    })
}

fn parse_atom(cursor: &mut Cursor) -> Result<Pattern, String> {
    cursor.skip_ws();
    match cursor.bump() {
        Some('(') => {
            let inner = parse_choice(cursor)?;
            if !cursor.eat(')') {
                return Err("missing ')'".to_string());
            }
            Ok(inner)
        }
        Some('[') => {
            let mut class = String::new();
            loop {
                match cursor.bump() {
                    None => return Err("unterminated character class".to_string()),
                    Some(']') => break,
                    Some('\\') => {
                        class.push('\\');
                        class.push(cursor.bump().ok_or("dangling escape")?);
                    }
                    Some(ch) => class.push(ch),
                }
            }
            Ok(Pattern::Class(class))
        }
        Some('.') => Ok(Pattern::Any),
        Some(quote @ ('\'' | '"')) => {
            let mut literal = String::new();
            loop {
                match cursor.bump() {
                    None => return Err("unterminated literal".to_string()),
                    Some(ch) if ch == quote => break,
                    Some('\\') => literal.push(cursor.bump().ok_or("dangling escape")?),
                    Some(ch) => literal.push(ch),
                }
            }
            Ok(Pattern::Lit(literal))
        }
        Some(ch) if ch.is_alphabetic() || ch == '_' => {
            let mut word = String::from(ch);
            while let Some(next) = cursor.peek() {
                if next.is_alphanumeric() || next == '_' || next == '-' {
                    word.push(next);
                    cursor.bump();
                } else {
                    break;
                }
            }
            if SUPPORTED_TOKENS.contains(&word.as_str()) {
                Ok(Pattern::Token(word))
            } else {
                Ok(Pattern::Rule(word))
            }
        }
        Some(other) => Err(format!("unexpected character '{other}'")),
        None => Err("unexpected end of pattern".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const GRAMMAR: &str = r#"
program   <- statement+
statement <- print_stmt / assignment
print_stmt <- 'print' expr ';'
assignment <- IDENT '=' expr ';'
expr      <- term (('+' / '-') term)*
term      <- NUMBER / IDENT
"#;

    #[test]
    fn parses_rules_and_alternatives() {
        let grammar = parse_peg_text(GRAMMAR).expect("grammar should parse");
        let names: Vec<&str> = grammar.rules.iter().map(|r| r.name.as_str()).collect();
        assert_eq!(
            names,
            ["program", "statement", "print_stmt", "assignment", "expr", "term"]
        );
        assert_eq!(grammar.start, "program");
        assert!(matches!(grammar.rules[0].pattern, Pattern::Plus(_)));
        assert!(matches!(grammar.rules[1].pattern, Pattern::Choice(_)));
    }

    #[test]
    fn ignores_comments_and_blank_lines() {
        let text = "// leading\nprogram <- IDENT ';'  // trailing\n";
        let grammar = parse_peg_text(text).expect("grammar should parse");
        assert_eq!(grammar.rules.len(), 1);
    }

    #[test]
    fn rejects_lines_without_an_arrow() {
        let error = parse_peg_text("this is not a rule").unwrap_err();
        assert!(error.contains("expected 'name <- pattern'"), "{error}");
    }

    #[test]
    fn honours_quantifiers_predicates_and_classes() {
        let grammar = parse_peg_text(
            "program <- !'x' [a-zA-Z_][a-zA-Z0-9_]* &';' .?",
        )
        .expect("grammar should parse");
        assert!(matches!(grammar.rules[0].pattern, Pattern::Seq(_)));
    }

    #[test]
    fn json_round_trip_preserves_rules() {
        let grammar = parse_peg_text(GRAMMAR).expect("grammar should parse");
        let json = grammar_to_json(&grammar);
        let restored = grammar_from_json(&json).expect("json should parse");
        assert_eq!(restored.rules.len(), grammar.rules.len());
        assert_eq!(restored.start, grammar.start);
        assert_eq!(restored.rules[3].pattern, grammar.rules[3].pattern);
    }
}
