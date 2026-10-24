//! Debug Adapter Protocol server over stdio.
//!
//! The program runs on the main thread with the evaluator's observer hook; a
//! second thread speaks DAP. Breakpoints and stepping are implemented by
//! pausing inside the observer until a `continue`/`next` request arrives.

use std::collections::HashSet;
use std::io::{BufRead, Write};
use std::sync::{mpsc, Arc, Condvar, Mutex};

use lashon_core::eval::{Frame, Machine, Observer, Step};
use lashon_core::grammar::parse_peg_text;
use lashon_core::parse_to_ast;
use serde_json::{json, Value};

type Shared = Arc<(Mutex<State>, Condvar)>;

struct State {
    breakpoints: HashSet<usize>,
    step: bool,
    paused: bool,
    stop_line: usize,
    stop_locals: Vec<(String, String)>,
    shutdown: bool,
}

impl State {
    fn new() -> Self {
        State {
            breakpoints: HashSet::new(),
            step: false,
            paused: false,
            stop_line: 0,
            stop_locals: vec![],
            shutdown: false,
        }
    }
}

struct DebugObserver {
    shared: Shared,
    writer: Arc<Mutex<Box<dyn Write + Send>>>,
}

impl Observer for DebugObserver {
    fn statement(&mut self, frame: &Frame<'_>) -> Step {
        let (lock, condvar) = &*self.shared;
        let mut state = lock.lock().unwrap();
        if state.shutdown {
            return Step::Continue;
        }
        let stop = state.breakpoints.contains(&frame.line) || state.step;
        if !stop {
            return Step::Continue;
        }

        state.paused = true;
        state.step = false;
        state.stop_line = frame.line;
        state.stop_locals = frame
            .locals
            .iter()
            .map(|(name, value)| (name.clone(), value.display()))
            .collect();

        drop(state);
        send(
            &self.writer,
            &json!({
                "type": "event",
                "event": "stopped",
                "body": { "reason": "breakpoint", "threadId": 1, "allThreadsStopped": true }
            }),
        );

        let mut state = lock.lock().unwrap();
        while state.paused && !state.shutdown {
            state = condvar.wait(state).unwrap();
        }
        Step::Continue
    }
}

fn send(writer: &Arc<Mutex<Box<dyn Write + Send>>>, message: &Value) {
    let body = message.to_string();
    let mut out = writer.lock().unwrap();
    let _ = write!(out, "Content-Length: {}\r\n\r\n{}", body.len(), body);
    let _ = out.flush();
}

fn read_message(reader: &mut impl BufRead) -> Option<Value> {
    let mut length = 0usize;
    loop {
        let mut header = String::new();
        if reader.read_line(&mut header).ok()? == 0 {
            return None;
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
    reader.read_exact(&mut body).ok()?;
    serde_json::from_slice(&body).ok()
}

/// Run the debug adapter for a program.
pub fn run(grammar_path: &String, program_path: &String) -> Result<(), String> {
    let grammar_text = std::fs::read_to_string(grammar_path)
        .map_err(|error| format!("cannot read {grammar_path}: {error}"))?;
    let source = std::fs::read_to_string(program_path)
        .map_err(|error| format!("cannot read {program_path}: {error}"))?;
    let grammar = parse_peg_text(&grammar_text)?;
    let ast = parse_to_ast(&grammar, &source).map_err(|(message, _, _)| message)?;

    let shared: Shared = Arc::new((Mutex::new(State::new()), Condvar::new()));
    let writer: Arc<Mutex<Box<dyn Write + Send>>> =
        Arc::new(Mutex::new(Box::new(std::io::stdout())));
    let (start_tx, start_rx) = mpsc::channel::<()>();

    let server_shared = Arc::clone(&shared);
    let server_writer = Arc::clone(&writer);
    let server = std::thread::spawn(move || {
        let stdin = std::io::stdin();
        let mut reader = stdin.lock();
        while let Some(message) = read_message(&mut reader) {
            let command = message.get("command").and_then(Value::as_str).unwrap_or("");
            let arguments = message.get("arguments").cloned().unwrap_or(Value::Null);
            let mut body = Value::Null;
            let mut stop = false;

            match command {
                "initialize" => {
                    body = json!({
                        "supportsConfigurationDoneRequest": true,
                        "supportsEvaluateForHovers": false,
                    });
                }
                "launch" | "attach" => {}
                "setBreakpoints" => {
                    let lines: Vec<usize> = arguments
                        .get("breakpoints")
                        .and_then(Value::as_array)
                        .map(|items| {
                            items
                                .iter()
                                .filter_map(|item| item.get("line").and_then(Value::as_u64))
                                .map(|line| line as usize)
                                .collect()
                        })
                        .unwrap_or_default();
                    let (lock, _) = &*server_shared;
                    let mut state = lock.lock().unwrap();
                    state.breakpoints = lines.iter().copied().collect();
                    body = json!({
                        "breakpoints": lines.iter().map(|line| json!({ "verified": true, "line": line })).collect::<Vec<_>>()
                    });
                }
                "configurationDone" => {
                    let _ = start_tx.send(());
                }
                "threads" => body = json!({ "threads": [{ "id": 1, "name": "main" }] }),
                "stackTrace" => {
                    let (lock, _) = &*server_shared;
                    let state = lock.lock().unwrap();
                    body = json!({
                        "stackFrames": [{
                            "id": 0,
                            "name": "main",
                            "line": state.stop_line.max(1),
                            "column": 1,
                        }],
                        "totalFrames": 1
                    });
                }
                "scopes" => {
                    body = json!({
                        "scopes": [{ "name": "Locals", "variablesReference": 1, "expensive": false }]
                    });
                }
                "variables" => {
                    let (lock, _) = &*server_shared;
                    let state = lock.lock().unwrap();
                    body = json!({
                        "variables": state
                            .stop_locals
                            .iter()
                            .map(|(name, value)| json!({
                                "name": name,
                                "value": value,
                                "type": "",
                                "variablesReference": 0
                            }))
                            .collect::<Vec<_>>()
                    });
                }
                "continue" => {
                    let (lock, condvar) = &*server_shared;
                    let mut state = lock.lock().unwrap();
                    state.paused = false;
                    condvar.notify_all();
                    body = json!({ "allThreadsContinued": true });
                }
                "next" | "stepIn" | "stepOut" => {
                    let (lock, condvar) = &*server_shared;
                    let mut state = lock.lock().unwrap();
                    state.step = true;
                    state.paused = false;
                    condvar.notify_all();
                }
                "disconnect" | "terminate" => {
                    let (lock, condvar) = &*server_shared;
                    let mut state = lock.lock().unwrap();
                    state.shutdown = true;
                    state.paused = false;
                    condvar.notify_all();
                    stop = true;
                }
                _ => {}
            }

            send(
                &server_writer,
                &json!({
                    "type": "response",
                    "request_seq": message.get("seq").cloned().unwrap_or(json!(0)),
                    "command": command,
                    "success": true,
                    "body": body,
                }),
            );
            if stop {
                break;
            }
        }
    });

    let _ = start_rx.recv();
    let observer = DebugObserver {
        shared: Arc::clone(&shared),
        writer: Arc::clone(&writer),
    };
    let mut machine = Machine::new(&ast).with_observer(Box::new(observer));
    let result = machine.run(&ast);
    let stdout = machine.output().to_string();

    if !stdout.is_empty() {
        send(
            &writer,
            &json!({
                "type": "event",
                "event": "output",
                "body": { "category": "stdout", "output": stdout }
            }),
        );
    }
    send(&writer, &json!({ "type": "event", "event": "terminated" }));
    send(
        &writer,
        &json!({ "type": "event", "event": "exited", "body": { "exitCode": if result.is_ok() { 0 } else { 1 } } }),
    );
    let _ = server.join();
    result.map(|_| ()).map_err(|error| error.to_string())
}
