//! NovaX LLM Training Monitor — Rust HTTP server
//! Replaces train_monitor_server.py with a compiled binary that:
//! - Starts instantly (no Python interpreter boot)
//! - Never becomes a zombie process
//! - Uses <1 MB RAM vs Python's 30-50 MB
//! - Handles Windows signals properly

use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};

const LOG_PATH: &str = "C:/NovaX/web/nova_llm_training_log.json";
const PORT: u16 = 9802;
const TOTAL_STEPS: u64 = 50000;

#[derive(Debug, Deserialize, Clone)]
struct LogEntry {
    step: u64,
    loss: f64,
    #[serde(default)]
    perplexity: f64,
    #[serde(default)]
    steps_per_sec: f64,
    #[serde(default)]
    epoch: u64,
    #[serde(default)]
    lr: f64,
    #[serde(default)]
    elapsed_sec: f64,
}

#[derive(Serialize)]
struct StatusResponse {
    trit: u8,
    status: String,
    done: i8,
    step: u64,
    total_steps: u64,
    percent: f64,
    loss: f64,
    perplexity: f64,
    steps_per_sec: f64,
    tokens_per_sec: u64,
    epoch: u64,
    lr: f64,
    elapsed_sec: f64,
    eta_hours: u64,
    eta_minutes: u64,
    best_loss: f64,
    best_step: u64,
    trend: Vec<TrendPoint>,
    log_entries: usize,
}

#[derive(Serialize)]
struct TrendPoint {
    step: u64,
    loss: f64,
}

#[derive(Serialize)]
struct HistoryResponse {
    trit: u8,
    points: Vec<TrendPoint>,
    total: usize,
}

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    trit: u8,
    service: String,
    port: u16,
    log_entries: usize,
}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

/// Read the training log and return only the current run's entries
fn read_current_run() -> Vec<LogEntry> {
    let content = match fs::read_to_string(LOG_PATH) {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };

    let entries: Vec<LogEntry> = match serde_json::from_str(&content) {
        Ok(e) => e,
        Err(_) => return Vec::new(),
    };

    if entries.is_empty() {
        return Vec::new();
    }

    // Find the last step reset (where step decreases) — marks a new run
    let mut run_start = 0;
    for i in 1..entries.len() {
        if entries[i].step < entries[i - 1].step {
            run_start = i;
        }
    }

    entries[run_start..].to_vec()
}

fn build_status(log: &[LogEntry]) -> String {
    if log.is_empty() {
        return serde_json::to_string(&serde_json::json!({"trit": 0, "status": "waiting"}))
            .unwrap_or_default();
    }

    let last = &log[log.len() - 1];
    let step = last.step;
    let sps = last.steps_per_sec;
    let eta_sec = if sps > 0.001 {
        (TOTAL_STEPS.saturating_sub(step)) as f64 / sps
    } else {
        0.0
    };

    // Find best loss
    let best = log
        .iter()
        .min_by(|a, b| a.loss.partial_cmp(&b.loss).unwrap_or(std::cmp::Ordering::Equal))
        .unwrap();

    // Last 5 entries for trend
    let trend_start = if log.len() > 5 { log.len() - 5 } else { 0 };
    let trend: Vec<TrendPoint> = log[trend_start..]
        .iter()
        .map(|e| TrendPoint {
            step: e.step,
            loss: e.loss,
        })
        .collect();

    let status = StatusResponse {
        trit: 1,
        status: if step >= TOTAL_STEPS {
            "done".into()
        } else {
            "training".into()
        },
        done: if step >= TOTAL_STEPS { 1 } else { -1 },
        step,
        total_steps: TOTAL_STEPS,
        percent: (step as f64 / TOTAL_STEPS as f64 * 100.0 * 10.0).round() / 10.0,
        loss: last.loss,
        perplexity: last.perplexity,
        steps_per_sec: sps,
        tokens_per_sec: (sps * 4.0 * 512.0) as u64,
        epoch: last.epoch,
        lr: last.lr,
        elapsed_sec: last.elapsed_sec,
        eta_hours: (eta_sec / 3600.0) as u64,
        eta_minutes: ((eta_sec % 3600.0) / 60.0) as u64,
        best_loss: best.loss,
        best_step: best.step,
        trend,
        log_entries: log.len(),
    };

    serde_json::to_string(&status).unwrap_or_default()
}

fn build_history(log: &[LogEntry]) -> String {
    let points: Vec<TrendPoint> = log
        .iter()
        .map(|e| TrendPoint {
            step: e.step,
            loss: e.loss,
        })
        .collect();

    let resp = HistoryResponse {
        trit: 1,
        total: points.len(),
        points,
    };

    serde_json::to_string(&resp).unwrap_or_default()
}

fn build_health(log_len: usize) -> String {
    let resp = HealthResponse {
        status: "ok".into(),
        trit: 1,
        service: "nova-train-monitor".into(),
        port: PORT,
        log_entries: log_len,
    };
    serde_json::to_string(&resp).unwrap_or_default()
}

fn send_response(mut stream: TcpStream, status_code: u16, status_text: &str, body: &str) {
    let response = format!(
        "HTTP/1.1 {} {}\r\n\
         Content-Type: application/json\r\n\
         Access-Control-Allow-Origin: *\r\n\
         Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n\
         Access-Control-Allow-Headers: Content-Type, Accept, Origin\r\n\
         Access-Control-Max-Age: 3600\r\n\
         Cache-Control: no-cache, no-store\r\n\
         Content-Length: {}\r\n\
         Connection: close\r\n\
         \r\n\
         {}",
        status_code,
        status_text,
        body.len(),
        body
    );
    let _ = stream.write_all(response.as_bytes());
    let _ = stream.flush();
}

fn handle_connection(mut stream: TcpStream) {
    let mut buf = [0u8; 2048];
    let n = match stream.read(&mut buf) {
        Ok(n) => n,
        Err(_) => return,
    };

    let request = String::from_utf8_lossy(&buf[..n]);
    let first_line = request.lines().next().unwrap_or("");
    let parts: Vec<&str> = first_line.split_whitespace().collect();

    if parts.len() < 2 {
        return;
    }

    let method = parts[0];
    let path = parts[1];

    // Handle OPTIONS (CORS preflight)
    if method == "OPTIONS" {
        send_response(stream, 200, "OK", "");
        return;
    }

    let log = read_current_run();

    match path {
        "/health" | "/status" => {
            let body = build_health(log.len());
            send_response(stream, 200, "OK", &body);
        }
        "/train/status" => {
            let body = build_status(&log);
            send_response(stream, 200, "OK", &body);
        }
        "/train/history" => {
            let body = build_history(&log);
            send_response(stream, 200, "OK", &body);
        }
        _ => {
            let body =
                serde_json::to_string(&ErrorResponse {
                    error: "not found".into(),
                })
                .unwrap_or_default();
            send_response(stream, 404, "Not Found", &body);
        }
    }
}

fn main() {
    let addr = format!("0.0.0.0:{}", PORT);
    let listener = match TcpListener::bind(&addr) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("Failed to bind to {}: {}", addr, e);
            std::process::exit(1);
        }
    };

    println!("NovaX Training Monitor (Rust) on port {}", PORT);
    println!("  Log: {}", LOG_PATH);
    println!("  Total steps: {}", TOTAL_STEPS);

    // Handle Ctrl+C gracefully on Windows
    let _ = ctrlc_handler();

    for stream in listener.incoming() {
        match stream {
            Ok(s) => handle_connection(s),
            Err(e) => eprintln!("Connection error: {}", e),
        }
    }
}

/// Set up Ctrl+C handler so the process exits cleanly (no zombie)
fn ctrlc_handler() -> Result<(), Box<dyn std::error::Error>> {
    #[cfg(windows)]
    unsafe {
        use std::os::raw::c_int;
        extern "system" {
            fn SetConsoleCtrlHandler(
                handler: Option<unsafe extern "system" fn(u32) -> c_int>,
                add: c_int,
            ) -> c_int;
        }
        unsafe extern "system" fn handler(_: u32) -> c_int {
            std::process::exit(0);
        }
        SetConsoleCtrlHandler(Some(handler), 1);
    }
    Ok(())
}
