//! AST value types and their JSON encoding.

use serde_json::Value;

#[derive(Clone, Debug)]
pub(crate) enum Val {
    Ast(Ast),
    Text(String),
}

#[derive(Clone, Debug, Default)]
pub(crate) struct Ast {
    // Kept for parity with the Python AST contract; the JSON form omits it.
    #[allow(dead_code)]
    pub node_type: String,
    pub value: Option<Value>,
    pub children: Vec<Ast>,
    pub line: usize,
    pub column: usize,
    pub source_text: String,
}

pub(crate) fn write_ast(ast: &Ast, out: &mut String) {
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
