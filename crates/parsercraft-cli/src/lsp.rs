//! Minimal Language Server Protocol server over stdio.
//!
//! Implements the parts an editor needs to edit a grammar or a program:
//! diagnostics from the real engine, and — for `.peg` documents — rule hover,
//! completion, go-to-definition, references, rename, and document symbols.

use std::collections::HashMap;
use std::io::{BufRead, Read, Write};

use parsercraft_core::grammar::{parse_peg_text, Grammar};
use parsercraft_core::parse_to_ast;
use serde_json::{json, Value};

struct RuleEntry {
    name: String,
    line: usize,   // 1-based
    column: usize, // 1-based
    pattern: String,
}

struct Server {
    documents: HashMap<String, String>,
    grammar: Option<Grammar>,
    grammar_uri_suffix: Option<String>,
}

const SYNC_FULL: i64 = 1;

impl Server {
    fn new(grammar_path: Option<&String>) -> Result<Self, String> {
        let grammar = match grammar_path {
            Some(path) => {
                let text = std::fs::read_to_string(path)
                    .map_err(|error| format!("cannot read {path}: {error}"))?;
                Some(parse_peg_text(&text)?)
            }
            None => None,
        };
        Ok(Server {
            documents: HashMap::new(),
            grammar,
            grammar_uri_suffix: grammar_path.map(|path| {
                std::path::Path::new(path)
                    .file_name()
                    .map(|name| name.to_string_lossy().to_string())
                    .unwrap_or_default()
            }),
        })
    }

    fn is_grammar_document(&self, uri: &str) -> bool {
        match &self.grammar_uri_suffix {
            Some(suffix) => !suffix.is_empty() && uri.ends_with(suffix.as_str()),
            None => false,
        }
    }

    fn capabilities() -> Value {
        json!({
            "textDocumentSync": SYNC_FULL,
            "hoverProvider": true,
            "definitionProvider": true,
            "referencesProvider": true,
            "renameProvider": true,
            "documentSymbolProvider": true,
            "completionProvider": { "resolveProvider": false, "triggerCharacters": [] },
        })
    }

    /// Parse ``content`` against the grammar and return LSP diagnostics.
    fn diagnostics(&self, uri: &str) -> Vec<Value> {
        let content = match self.documents.get(uri) {
            Some(content) => content,
            None => return vec![],
        };

        if self.is_grammar_document(uri) {
            let grammar = match parse_peg_text(content) {
                Ok(grammar) => grammar,
                Err(message) => {
                    let (line, column) = position(&message);
                    return vec![diagnostic(
                        line,
                        column,
                        &message,
                        1,
                        "grammar-error",
                    )];
                }
            };
            return grammar
                .undefined_references()
                .into_iter()
                .map(|(owner, missing)| {
                    let line = find_rule_line(content, &owner).unwrap_or(1);
                    diagnostic(
                        line,
                        1,
                        &format!("rule '{owner}' references undefined rule '{missing}'"),
                        2,
                        "undefined-rule",
                    )
                })
                .collect();
        }

        match self.grammar.as_ref() {
            Some(grammar) => match parse_to_ast(grammar, content) {
                Ok(_) => vec![],
                Err((message, _, _)) => {
                    let (line, column) = position(&message);
                    vec![diagnostic(line, column, &message, 1, "parse-error")]
                }
            },
            None => vec![],
        }
    }

    fn index(&self, uri: &str) -> Vec<RuleEntry> {
        let content = match self.documents.get(uri) {
            Some(content) => content,
            None => return vec![],
        };
        if !self.is_grammar_document(uri) {
            return vec![];
        }
        let mut entries = vec![];
        for (index, raw) in content.lines().enumerate() {
            let line = raw.split("//").next().unwrap_or("");
            if let Some((name, pattern)) = line.split_once("<-") {
                let name = name.trim();
                if name.is_empty() || !name.chars().next().is_some_and(|c| c.is_alphabetic()) {
                    continue;
                }
                let column = line.find(name).map(|index| index + 1).unwrap_or(1);
                entries.push(RuleEntry {
                    name: name.to_string(),
                    line: index + 1,
                    column,
                    pattern: pattern.trim().to_string(),
                });
            }
        }
        entries
    }

    fn word_at(uri: &str, line: usize, character: usize, documents: &HashMap<String, String>) -> Option<String> {
        let content = documents.get(uri)?;
        let text: Vec<char> = content.lines().nth(line)?.chars().collect();
        if character >= text.len() {
            return None;
        }
        let is_word = |c: char| c.is_alphanumeric() || c == '_' || c == '-';
        if !is_word(text[character]) {
            return None;
        }
        let mut start = character;
        while start > 0 && is_word(text[start - 1]) {
            start -= 1;
        }
        let mut end = character;
        while end + 1 < text.len() && is_word(text[end + 1]) {
            end += 1;
        }
        Some(text[start..=end].iter().collect())
    }

    fn handle(&mut self, request: &Value) -> Option<Value> {
        let method = request.get("method").and_then(Value::as_str).unwrap_or("");
        let id = request.get("id").cloned();
        let params = request.get("params").cloned().unwrap_or(Value::Null);
        let uri = params
            .get("textDocument")
            .and_then(|doc| doc.get("uri"))
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();

        let result = match method {
            "initialize" => Some(json!({ "capabilities": Self::capabilities(), "serverInfo": { "name": "parsercraft-rs" } })),
            "shutdown" => Some(Value::Null),
            "textDocument/didOpen" => {
                let text = params
                    .get("textDocument")
                    .and_then(|doc| doc.get("text"))
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_string();
                self.documents.insert(uri.clone(), text);
                None
            }
            "textDocument/didChange" => {
                let text = params
                    .get("contentChanges")
                    .and_then(Value::as_array)
                    .and_then(|changes| changes.last())
                    .and_then(|change| change.get("text"))
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_string();
                self.documents.insert(uri.clone(), text);
                None
            }
            "textDocument/didClose" => {
                self.documents.remove(&uri);
                None
            }
            "textDocument/hover" => self.hover(&uri, &params),
            "textDocument/definition" => self.definition(&uri, &params),
            "textDocument/references" => self.references(&uri, &params),
            "textDocument/rename" => self.rename(&uri, &params),
            "textDocument/documentSymbol" => Some(json!(
                self.index(&uri)
                    .iter()
                    .map(|entry| json!({
                        "name": entry.name,
                        "kind": 12,
                        "detail": entry.pattern,
                        "range": range(entry.line, entry.column, entry.name.len()),
                        "selectionRange": range(entry.line, entry.column, entry.name.len()),
                    }))
                    .collect::<Vec<_>>()
            )),
            "textDocument/completion" => self.completions(&uri),
            _ => {
                if id.is_some() {
                    return Some(json!({
                        "jsonrpc": "2.0",
                        "id": id,
                        "error": { "code": -32601, "message": format!("method not found: {method}") }
                    }));
                }
                None
            }
        };

        match (method, id, result) {
            ("shutdown", id, _) => Some(response(id, Value::Null)),
            (_, Some(id), Some(result)) => Some(response(Some(id), result)),
            _ => None,
        }
    }

    fn hover(&self, uri: &str, params: &Value) -> Option<Value> {
        let word = Self::word_at(
            uri,
            params.get("position")?.get("line")?.as_u64()? as usize,
            params.get("position")?.get("character")?.as_u64()? as usize,
            &self.documents,
        )?;
        let entry = self.index(uri).into_iter().find(|entry| entry.name == word)?;
        Some(json!({
            "contents": {
                "kind": "markdown",
                "value": format!("**{}**\n\n```\n{} <- {}\n```\n\nDefined on line {}.", entry.name, entry.name, entry.pattern, entry.line)
            }
        }))
    }

    fn definition(&self, uri: &str, params: &Value) -> Option<Value> {
        let word = Self::word_at(
            uri,
            params.get("position")?.get("line")?.as_u64()? as usize,
            params.get("position")?.get("character")?.as_u64()? as usize,
            &self.documents,
        )?;
        let entry = self.index(uri).into_iter().find(|entry| entry.name == word)?;
        Some(json!({ "uri": uri, "range": range(entry.line, entry.column, entry.name.len()) }))
    }

    fn references(&self, uri: &str, params: &Value) -> Option<Value> {
        let word = Self::word_at(
            uri,
            params.get("position")?.get("line")?.as_u64()? as usize,
            params.get("position")?.get("character")?.as_u64()? as usize,
            &self.documents,
        )?;
        if !self.index(uri).iter().any(|entry| entry.name == word) {
            return Some(json!([]));
        }
        let content = self.documents.get(uri)?;
        let mut locations = vec![];
        for (index, line) in content.lines().enumerate() {
            let code = line.split("//").next().unwrap_or("");
            let mut start = 0;
            while let Some(found) = code[start..].find(&word) {
                let column = start + found;
                let before_ok = column == 0
                    || !code[..column]
                        .chars()
                        .next_back()
                        .is_some_and(|c| c.is_alphanumeric() || c == '_' || c == '-');
                let after = column + word.len();
                let after_ok = after >= code.len()
                    || !code[after..]
                        .chars()
                        .next()
                        .is_some_and(|c| c.is_alphanumeric() || c == '_' || c == '-');
                if before_ok && after_ok {
                    locations.push(json!({
                        "uri": uri,
                        "range": range(index + 1, column + 1, word.len())
                    }));
                }
                start = column + word.len();
            }
        }
        Some(json!(locations))
    }

    fn rename(&self, uri: &str, params: &Value) -> Option<Value> {
        let new_name = params.get("newName")?.as_str()?.to_string();
        if !new_name.chars().next().is_some_and(|c| c.is_alphabetic()) {
            return None;
        }
        let references = self.references(uri, params)?;
        let edits: Vec<Value> = references
            .as_array()?
            .iter()
            .map(|location| json!({ "range": location["range"], "newText": new_name }))
            .collect();
        let mut changes = serde_json::Map::new();
        changes.insert(uri.to_string(), Value::Array(edits));
        Some(json!({ "changes": changes }))
    }

    fn completions(&self, uri: &str) -> Option<Value> {
        let entries = self.index(uri);
        if entries.is_empty() {
            return Some(json!({ "isIncomplete": false, "items": [] }));
        }
        let mut items: Vec<Value> = entries
            .iter()
            .map(|entry| json!({ "label": entry.name, "kind": 3, "detail": "grammar rule" }))
            .collect();
        for token in ["IDENT", "NUMBER", "STRING", "NEWLINE", "EOF"] {
            items.push(json!({ "label": token, "kind": 3, "detail": "built-in token" }));
        }
        Some(json!({ "isIncomplete": false, "items": items }))
    }

}

fn position(message: &str) -> (usize, usize) {
    let mut line = 1;
    let mut column = 1;
    for (index, word) in message.split_whitespace().enumerate() {
        let cleaned = word.trim_end_matches(',');
        if index > 0 && message.contains("line") {
            let previous = message.split_whitespace().nth(index - 1).unwrap_or("");
            if previous == "line" {
                line = cleaned.parse().unwrap_or(1);
            } else if previous == "column" {
                column = cleaned.parse().unwrap_or(1);
            }
        }
    }
    (line, column)
}

fn find_rule_line(content: &str, name: &str) -> Option<usize> {
    content.lines().position(|line| {
        line.split("//").next().unwrap_or("").trim_start().starts_with(name)
            && line.contains("<-")
    }).map(|index| index + 1)
}

fn diagnostic(line: usize, column: usize, message: &str, severity: u8, code: &str) -> Value {
    json!({
        "range": range(line, column, 1),
        "message": message.lines().next().unwrap_or(message),
        "severity": severity,
        "code": code,
        "source": "ParserCraft",
    })
}

fn range(line: usize, column: usize, length: usize) -> Value {
    json!({
        "start": { "line": line.saturating_sub(1), "character": column.saturating_sub(1) },
        "end": { "line": line.saturating_sub(1), "character": column.saturating_sub(1) + length },
    })
}

fn response(id: Option<Value>, result: Value) -> Value {
    json!({ "jsonrpc": "2.0", "id": id, "result": result })
}

/// Run the language server on stdin/stdout until `exit`.
pub fn run(grammar_path: Option<&String>) -> Result<(), String> {
    let mut server = Server::new(grammar_path)?;
    let stdin = std::io::stdin();
    let mut reader = stdin.lock();
    let stdout = std::io::stdout();
    let mut writer = stdout.lock();

    loop {
        let mut length = 0usize;
        loop {
            let mut header = String::new();
            match reader.read_line(&mut header) {
                Ok(0) => return Ok(()),
                Ok(_) => {}
                Err(error) => return Err(error.to_string()),
            }
            let trimmed = header.trim();
            if trimmed.is_empty() {
                if length == 0 {
                    continue;
                }
                break;
            }
            if let Some(value) = trimmed.strip_prefix("Content-Length:") {
                length = value.trim().parse().unwrap_or(0);
            }
        }

        let mut body = vec![0u8; length];
        reader
            .read_exact(&mut body)
            .map_err(|error| error.to_string())?;
        let request: Value = match serde_json::from_slice(&body) {
            Ok(value) => value,
            Err(_) => continue,
        };

        let method = request.get("method").and_then(Value::as_str).unwrap_or("");
        if method == "exit" {
            return Ok(());
        }
        if method == "initialized" {
            continue;
        }

        let document = request
            .get("params")
            .and_then(|params| params.get("textDocument"))
            .and_then(|doc| doc.get("uri"))
            .and_then(Value::as_str)
            .map(str::to_string);

        let answer = server.handle(&request);
        if matches!(method, "textDocument/didOpen" | "textDocument/didChange") {
            if let Some(uri) = document {
                let payload = json!({
                    "jsonrpc": "2.0",
                    "method": "textDocument/publishDiagnostics",
                    "params": { "uri": uri, "diagnostics": server.diagnostics(&uri) },
                });
                write_message(&mut writer, &payload)?;
            }
        }
        if let Some(answer) = answer {
            write_message(&mut writer, &answer)?;
        }
    }
}

fn write_message(writer: &mut impl Write, message: &Value) -> Result<(), String> {
    let body = message.to_string();
    write!(writer, "Content-Length: {}\r\n\r\n{}", body.len(), body)
        .map_err(|error| error.to_string())?;
    writer.flush().map_err(|error| error.to_string())
}
