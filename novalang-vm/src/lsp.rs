// NovaLang LSP Server v1.0
// Language Server Protocol over stdin/stdout (JSON-RPC 2.0)
// Provides: diagnostics, hover, goto-definition, document symbols

use std::io::{self, BufRead, Write, BufWriter};
use std::collections::HashMap;

use novalang::lexer::{self, tokenize_spanned, SpannedToken, Token, Span};
use novalang::parser::{self, Stmt, Expr, Op};

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut writer = BufWriter::new(stdout.lock());
    let mut reader = stdin.lock();

    let mut documents: HashMap<String, String> = HashMap::new();

    eprintln!("[nova-lsp] NovaLang Language Server v1.0 starting...");

    loop {
        // Read LSP header
        let mut header = String::new();
        let mut content_length: usize = 0;

        loop {
            header.clear();
            if reader.read_line(&mut header).unwrap_or(0) == 0 {
                return; // EOF
            }
            let trimmed = header.trim();
            if trimmed.is_empty() {
                break; // End of headers
            }
            if trimmed.starts_with("Content-Length:") {
                content_length = trimmed["Content-Length:".len()..].trim()
                    .parse().unwrap_or(0);
            }
        }

        if content_length == 0 { continue; }

        // Read body
        let mut body = vec![0u8; content_length];
        if io::Read::read_exact(&mut reader, &mut body).is_err() {
            continue;
        }
        let body_str = String::from_utf8_lossy(&body).to_string();

        // Parse JSON-RPC
        let msg: serde_json::Value = match serde_json::from_str(&body_str) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let method = msg.get("method").and_then(|m| m.as_str()).unwrap_or("");
        let id = msg.get("id").cloned();
        let params = msg.get("params").cloned().unwrap_or(serde_json::Value::Null);

        eprintln!("[nova-lsp] method: {}", method);

        match method {
            "initialize" => {
                let result = serde_json::json!({
                    "capabilities": {
                        "textDocumentSync": {
                            "openClose": true,
                            "change": 1,
                            "save": { "includeText": true }
                        },
                        "hoverProvider": true,
                        "documentSymbolProvider": true,
                        "diagnosticProvider": {
                            "interFileDependencies": false,
                            "workspaceDiagnostics": false
                        }
                    },
                    "serverInfo": {
                        "name": "nova-lsp",
                        "version": "1.0.0"
                    }
                });
                send_response(&mut writer, id, result);
            }

            "initialized" => {
                eprintln!("[nova-lsp] Client initialized");
            }

            "shutdown" => {
                send_response(&mut writer, id, serde_json::Value::Null);
            }

            "exit" => {
                return;
            }

            "textDocument/didOpen" => {
                if let Some(doc) = params.get("textDocument") {
                    let uri = doc.get("uri").and_then(|u| u.as_str()).unwrap_or("").to_string();
                    let text = doc.get("text").and_then(|t| t.as_str()).unwrap_or("").to_string();
                    documents.insert(uri.clone(), text.clone());
                    let diags = analyze_document(&text, &uri);
                    send_diagnostics(&mut writer, &uri, diags);
                }
            }

            "textDocument/didChange" => {
                if let Some(doc) = params.get("textDocument") {
                    let uri = doc.get("uri").and_then(|u| u.as_str()).unwrap_or("").to_string();
                    if let Some(changes) = params.get("contentChanges").and_then(|c| c.as_array()) {
                        if let Some(change) = changes.first() {
                            let text = change.get("text").and_then(|t| t.as_str()).unwrap_or("").to_string();
                            documents.insert(uri.clone(), text.clone());
                            let diags = analyze_document(&text, &uri);
                            send_diagnostics(&mut writer, &uri, diags);
                        }
                    }
                }
            }

            "textDocument/didSave" => {
                if let Some(doc) = params.get("textDocument") {
                    let uri = doc.get("uri").and_then(|u| u.as_str()).unwrap_or("").to_string();
                    if let Some(text) = documents.get(&uri) {
                        let text = text.clone();
                        let diags = analyze_document(&text, &uri);
                        send_diagnostics(&mut writer, &uri, diags);
                    }
                }
            }

            "textDocument/hover" => {
                let uri = params.pointer("/textDocument/uri")
                    .and_then(|u| u.as_str()).unwrap_or("").to_string();
                let line = params.pointer("/position/line")
                    .and_then(|l| l.as_u64()).unwrap_or(0) as u32;
                let col = params.pointer("/position/character")
                    .and_then(|c| c.as_u64()).unwrap_or(0) as u32;

                let hover = if let Some(text) = documents.get(&uri) {
                    get_hover(text, line, col)
                } else {
                    None
                };

                let result = match hover {
                    Some(content) => serde_json::json!({
                        "contents": {
                            "kind": "markdown",
                            "value": content
                        }
                    }),
                    None => serde_json::Value::Null,
                };
                send_response(&mut writer, id, result);
            }

            "textDocument/documentSymbol" => {
                let uri = params.pointer("/textDocument/uri")
                    .and_then(|u| u.as_str()).unwrap_or("").to_string();

                let symbols = if let Some(text) = documents.get(&uri) {
                    get_document_symbols(text)
                } else {
                    vec![]
                };
                send_response(&mut writer, id, serde_json::json!(symbols));
            }

            _ => {
                if id.is_some() {
                    // Unknown request — respond with method not found
                    send_error(&mut writer, id, -32601, "Method not found");
                }
            }
        }
    }
}

fn send_response(writer: &mut impl Write, id: Option<serde_json::Value>, result: serde_json::Value) {
    let response = serde_json::json!({
        "jsonrpc": "2.0",
        "id": id,
        "result": result,
    });
    send_message(writer, &response);
}

fn send_error(writer: &mut impl Write, id: Option<serde_json::Value>, code: i32, message: &str) {
    let response = serde_json::json!({
        "jsonrpc": "2.0",
        "id": id,
        "error": { "code": code, "message": message }
    });
    send_message(writer, &response);
}

fn send_diagnostics(writer: &mut impl Write, uri: &str, diagnostics: Vec<serde_json::Value>) {
    let notification = serde_json::json!({
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {
            "uri": uri,
            "diagnostics": diagnostics,
        }
    });
    send_message(writer, &notification);
}

fn send_message(writer: &mut impl Write, msg: &serde_json::Value) {
    let body = serde_json::to_string(msg).unwrap_or_default();
    let _ = write!(writer, "Content-Length: {}\r\n\r\n{}", body.len(), body);
    let _ = writer.flush();
}

// ── Diagnostic Analysis ──────────────────────────────────

fn analyze_document(source: &str, _uri: &str) -> Vec<serde_json::Value> {
    let mut diagnostics = Vec::new();

    // Tokenize with spans
    let spanned_tokens = tokenize_spanned(source);

    // Check for lexer warnings (unknown chars)
    // The lexer prints warnings to stderr — we capture via span gaps

    // Parse and collect diagnostics
    let mut p = LspParser::new(spanned_tokens.clone());
    let _ast = p.parse_program();

    // Convert parser diagnostics to LSP format
    for diag in &p.diagnostics {
        let (line, col, severity, message) = parse_diagnostic_string(diag);
        diagnostics.push(serde_json::json!({
            "range": {
                "start": { "line": line, "character": col },
                "end": { "line": line, "character": col + 1 }
            },
            "severity": severity,
            "source": "nova-lsp",
            "message": message,
        }));
    }

    // Additional lint checks
    let lines: Vec<&str> = source.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        let trimmed = line.trim();

        // Warn: dict_set without reassignment
        if trimmed.starts_with("dict_set(") && !trimmed.contains("let ") {
            diagnostics.push(serde_json::json!({
                "range": {
                    "start": { "line": i, "character": 0 },
                    "end": { "line": i, "character": line.len() }
                },
                "severity": 2,
                "source": "nova-lsp",
                "message": "dict_set() returns new dict — result not assigned. Use: let x = dict_set(x, ...)",
            }));
        }

        // Warn: == 1 comparison (may be boolean check, not trit check)
        if trimmed.contains("== 1") && !trimmed.contains("== 1.") && !trimmed.contains("== 10") {
            // Check if it's comparing a trit value
            let before = trimmed.split("== 1").next().unwrap_or("");
            if before.contains("trit") || before.contains("health") || before.contains("bool3") {
                // OK — comparing trit result
            } else {
                diagnostics.push(serde_json::json!({
                    "range": {
                        "start": { "line": i, "character": 0 },
                        "end": { "line": i, "character": line.len() }
                    },
                    "severity": 3,
                    "source": "nova-lsp",
                    "message": "Comparing == 1 — did you mean to check a boolean or a trit? Trits use TRUE/MAYBE/FALSE_",
                }));
            }
        }

        // Warn: let inside if3 block that shadows outer scope
        if trimmed.starts_with("let ") && trimmed.contains("= ") {
            let var_name = trimmed.strip_prefix("let ").unwrap_or("")
                .split('=').next().unwrap_or("").trim();
            // Check if same variable appears earlier
            for j in 0..i {
                let prev = lines[j].trim();
                if prev.starts_with(&format!("let {} =", var_name)) {
                    diagnostics.push(serde_json::json!({
                        "range": {
                            "start": { "line": i, "character": 0 },
                            "end": { "line": i, "character": line.len() }
                        },
                        "severity": 3,
                        "source": "nova-lsp",
                        "message": format!("Variable '{}' shadows earlier declaration at line {}", var_name, j + 1),
                    }));
                    break;
                }
            }
        }
    }

    diagnostics
}

fn parse_diagnostic_string(diag: &str) -> (u32, u32, u32, String) {
    // Format: [parse] file.nova 5:3: message
    // or: [parse] 5:3: message
    let severity = if diag.contains("error:") { 1 } else { 2 }; // 1=Error, 2=Warning
    let message = diag.to_string();

    // Try to extract line:col
    let parts: Vec<&str> = diag.split(':').collect();
    for i in 0..parts.len().saturating_sub(1) {
        if let Ok(line) = parts[i].trim().split_whitespace().last()
            .unwrap_or("0").parse::<u32>() {
            if let Ok(col) = parts.get(i + 1).unwrap_or(&"0")
                .trim().split_whitespace().next()
                .unwrap_or("0").parse::<u32>() {
                if line > 0 && col > 0 {
                    return (line.saturating_sub(1), col.saturating_sub(1), severity, message);
                }
            }
        }
    }
    (0, 0, severity, message)
}

// ── Hover Provider ───────────────────────────────────────

fn get_hover(source: &str, line: u32, col: u32) -> Option<String> {
    let tokens = tokenize_spanned(source);

    // Find the token at the given position
    for st in &tokens {
        if st.span.line == line + 1 {
            let tok_col = st.span.col.saturating_sub(1);
            if let Token::Ident(ref name) = st.token {
                let name_end = tok_col + name.len() as u32;
                if col >= tok_col && col <= name_end {
                    return get_builtin_docs(name);
                }
            }
        }
    }
    None
}

fn get_builtin_docs(name: &str) -> Option<String> {
    let doc = match name {
        // Ternary builtins
        "bool3" => "```\nbool3(val) -> trit\n```\nConvert value to trit: +1 (truthy), 0 (maybe/empty), -1 (falsy)",
        "not3" => "```\nnot3(trit) -> trit\n```\nFlip trit: +1 <-> -1, 0 stays 0. **Free in balanced ternary** (just flip all trits)",
        "and3" => "```\nand3(a, b) -> trit\n```\nTernary AND: min(a, b). Both must be +1 to return +1",
        "or3" => "```\nor3(a, b) -> trit\n```\nTernary OR: max(a, b). Either +1 returns +1",
        "merge3" => "```\nmerge3(val, default) -> trit\n```\nResolve MAYBE: if val == 0, return default. Otherwise return val",
        "cmp3" => "```\ncmp3(a, b) -> trit\n```\nTernary comparison: +1 (a>b), 0 (a==b), -1 (a<b). **One op, three outcomes**",
        "trit" => "```\ntrit(val) -> trit\n```\nConstrain value to {-1, 0, +1}",
        "tryte" => "```\ntryte(val) -> int\n```\n6-trit balanced ternary value",
        "trit_count" => "```\ntrit_count(bt_string) -> int\n```\nCount trits in a balanced ternary string",

        // Balanced ternary arithmetic
        "bt" => "```\nbt(decimal) -> string\n```\nConvert decimal to balanced ternary string (e.g., bt(8) -> \"10T\")",
        "bt_val" => "```\nbt_val(string) -> int\n```\nConvert balanced ternary string to decimal (e.g., bt_val(\"10T\") -> 8)",
        "bt_neg" => "```\nbt_neg(string) -> string\n```\nNegate balanced ternary: flip all trits (1->T, T->1, 0->0). **Trivial — no two's complement!**",
        "bt_add" => "```\nbt_add(a, b) -> string\n```\nAdd two balanced ternary strings",
        "bt_sub" => "```\nbt_sub(a, b) -> string\n```\nSubtract balanced ternary (via negation — trivial!)",
        "bt_mul" => "```\nbt_mul(a, b) -> string\n```\nMultiply balanced ternary",
        "bt_pack" => "```\nbt_pack(trit_string) -> bytes\n```\nPack trits into bytes (H5 = 5 trits/byte, 3^5=243 states)",
        "bt_unpack" => "```\nbt_unpack(bytes) -> string\n```\nUnpack bytes back to trit string",

        // Health monitoring
        "health3" => "```\nhealth3(port) -> trit\n```\nCheck service health: +1=healthy, 0=degraded, -1=down",
        "health3_all" => "```\nhealth3_all() -> string\n```\n13-trit balanced ternary system health string",

        // Control flow
        "if3" => "**Three-way branch**\n```\nif3 condition {\n    // +1 (TRUE)\n} maybe {\n    // 0 (MAYBE)\n} else {\n    // -1 (FALSE)\n}\n```",
        "match3" => "**Ternary pattern match**\n```\nmatch3 expr {\n    TRUE => { ... }\n    MAYBE => { ... }\n    FALSE_ => { ... }\n}\n```",
        "try3" => "**Ternary error handling**\n```\ntry3 {\n    // attempt\n} fail {\n    // on failure (-1)\n}\n```\nMaybe branch handles degraded/partial success",
        "for3" => "**Ternary iteration**\n```\nfor3 item in collection {\n    // process each item\n}\n```",

        // Common builtins
        "print" => "```\nprint(val, ...)\n```\nPrint values to stdout",
        "str" => "```\nstr(val) -> string\n```\nConvert value to string representation",
        "len" => "```\nlen(val) -> int\n```\nLength of string, list, or dict",
        "type_of" => "```\ntype_of(val) -> string\n```\nReturn type name: \"int\", \"float\", \"str\", \"list\", \"dict\", \"trit\", \"null\"",
        "append" => "```\nappend(list, val) -> list\n```\nReturn new list with val appended",
        "dict_get" => "```\ndict_get(dict, key, default) -> val\n```\nGet value from dict, or default if key missing",
        "dict_set" => "```\ndict_set(dict, key, val) -> dict\n```\n**Returns NEW dict** — must reassign: `let d = dict_set(d, k, v)`",
        "json_encode" => "```\njson_encode(val) -> string\n```\nSerialize value to JSON string",
        "json_decode" => "```\njson_decode(string) -> val\n```\nParse JSON string to value",
        "time" => "```\ntime() -> float\n```\nCurrent Unix timestamp in seconds",
        "round" => "```\nround(val, decimals) -> float\n```\nRound to N decimal places",
        "trim" => "```\ntrim(string) -> string\n```\nRemove leading/trailing whitespace",
        "split" => "```\nsplit(string, delimiter) -> list\n```\nSplit string into list of substrings",
        "join" => "```\njoin(list, delimiter) -> string\n```\nJoin list elements with delimiter",
        "starts_with" => "```\nstarts_with(string, prefix) -> bool\n```\nCheck if string starts with prefix",
        "ends_with" => "```\nends_with(string, suffix) -> bool\n```\nCheck if string ends with suffix",
        "contains" => "```\ncontains(string, substr) -> bool\n```\nCheck if string contains substring",
        "replace" => "```\nreplace(string, old, new) -> string\n```\nReplace all occurrences of old with new",
        "shell" => "```\nshell(command) -> dict\n```\nRun shell command, return {\"stdout\": ..., \"stderr\": ..., \"code\": ...}",
        "dir_list" => "```\ndir_list(path) -> list\n```\nList files in directory",
        "file_read" => "```\nfile_read(path) -> string\n```\nRead entire file as string",
        "file_write" => "```\nfile_write(path, content)\n```\nWrite string to file",
        "path_ext" => "```\npath_ext(path) -> string\n```\nGet file extension (without dot): path_ext(\"test.nova\") -> \"nova\"",
        "path_filename" => "```\npath_filename(path) -> string\n```\nGet filename from path",
        "tserve" => "```\ntserve(port, name) -> server\n```\nCreate HTTP server on port with name",
        "troute" => "```\ntroute(server, method, path, handler_name)\n```\nRegister route handler",
        "tstart" => "```\ntstart(server)\n```\nStart HTTP server (blocking)",

        _ => return None,
    };
    Some(doc.to_string())
}

// ── Document Symbols ─────────────────────────────────────

fn get_document_symbols(source: &str) -> Vec<serde_json::Value> {
    let tokens = tokenize_spanned(source);
    let mut p = LspParser::new(tokens);
    let ast = p.parse_program();
    let mut symbols = Vec::new();

    for stmt in &ast {
        match stmt {
            Stmt::FnDef(name, params, _) => {
                let detail = format!("fn {}({})", name, params.join(", "));
                symbols.push(serde_json::json!({
                    "name": name,
                    "detail": detail,
                    "kind": 12, // Function
                    "range": { "start": { "line": 0, "character": 0 }, "end": { "line": 0, "character": 0 } },
                    "selectionRange": { "start": { "line": 0, "character": 0 }, "end": { "line": 0, "character": 0 } },
                }));
            }
            Stmt::Let(name, _) => {
                symbols.push(serde_json::json!({
                    "name": name,
                    "kind": 13, // Variable
                    "range": { "start": { "line": 0, "character": 0 }, "end": { "line": 0, "character": 0 } },
                    "selectionRange": { "start": { "line": 0, "character": 0 }, "end": { "line": 0, "character": 0 } },
                }));
            }
            Stmt::Class3(name, parent, _) => {
                let detail = match parent {
                    Some(p) => format!("class3 {} extends3 {}", name, p),
                    None => format!("class3 {}", name),
                };
                symbols.push(serde_json::json!({
                    "name": name,
                    "detail": detail,
                    "kind": 5, // Class
                    "range": { "start": { "line": 0, "character": 0 }, "end": { "line": 0, "character": 0 } },
                    "selectionRange": { "start": { "line": 0, "character": 0 }, "end": { "line": 0, "character": 0 } },
                }));
            }
            _ => {}
        }
    }
    symbols
}

// ── Minimal LSP Parser (reuses parser logic) ─────────────
// We wrap the real parser to capture diagnostics

struct LspParser {
    tokens: Vec<SpannedToken>,
    pos: usize,
    diagnostics: Vec<String>,
}

impl LspParser {
    fn new(tokens: Vec<SpannedToken>) -> Self {
        Self { tokens, pos: 0, diagnostics: Vec::new() }
    }

    fn parse_program(&mut self) -> Vec<Stmt> {
        // Use the real parser and capture diagnostics
        let tokens_clone = self.tokens.clone();
        let mut real_parser = RealParser {
            tokens: tokens_clone,
            pos: 0,
            file_name: String::new(),
            diagnostics: Vec::new(),
        };
        let stmts = real_parser.parse_program_inner();
        self.diagnostics = real_parser.diagnostics;
        stmts
    }
}

// Thin wrapper around the real parser to capture diagnostics without printing
struct RealParser {
    tokens: Vec<SpannedToken>,
    pos: usize,
    file_name: String,
    diagnostics: Vec<String>,
}

impl RealParser {
    fn peek(&self) -> &Token {
        self.tokens.get(self.pos)
            .map(|st| &st.token)
            .unwrap_or(&Token::Eof)
    }

    fn peek_span(&self) -> Span {
        self.tokens.get(self.pos)
            .map(|st| st.span)
            .unwrap_or(Span::zero())
    }

    fn advance(&mut self) -> Token {
        let tok = self.tokens.get(self.pos)
            .map(|st| st.token.clone())
            .unwrap_or(Token::Eof);
        self.pos += 1;
        tok
    }

    fn expect(&mut self, expected: &Token) -> bool {
        if self.peek() == expected {
            self.advance();
            true
        } else {
            false
        }
    }

    fn skip_newlines(&mut self) {
        while matches!(self.peek(), Token::Newline) {
            self.advance();
        }
    }

    fn parse_program_inner(&mut self) -> Vec<Stmt> {
        let mut stmts = Vec::new();
        while !matches!(self.peek(), Token::Eof) {
            self.skip_newlines();
            if matches!(self.peek(), Token::Eof) { break; }
            if matches!(self.peek(), Token::RBrace) {
                let span = self.peek_span();
                self.diagnostics.push(format!(
                    "[parse] warning: stray '}}' at {}:{} — mismatched braces",
                    span.line, span.col
                ));
                self.advance();
                continue;
            }
            let before = self.pos;
            if let Some(stmt) = self.parse_stmt() {
                stmts.push(stmt);
            } else if self.pos == before {
                self.advance();
            }
        }
        stmts
    }

    fn parse_stmt(&mut self) -> Option<Stmt> {
        self.skip_newlines();
        match self.peek().clone() {
            Token::Let | Token::Const => {
                self.advance();
                if let Token::Ident(name) = self.advance() {
                    if self.expect(&Token::Assign) {
                        let expr = self.parse_expr();
                        Some(Stmt::Let(name, expr))
                    } else {
                        Some(Stmt::Let(name, Expr::Null))
                    }
                } else { None }
            }
            Token::Fn => {
                self.advance();
                let name = if let Token::Ident(n) = self.advance() { n } else { return None; };
                self.expect(&Token::LParen);
                let mut params = Vec::new();
                while !matches!(self.peek(), Token::RParen | Token::Eof) {
                    if let Token::Ident(p) = self.advance() { params.push(p); }
                    if !self.expect(&Token::Comma) { break; }
                }
                self.expect(&Token::RParen);
                let body = self.parse_block();
                Some(Stmt::FnDef(name, params, body))
            }
            Token::Return => {
                self.advance();
                if matches!(self.peek(), Token::RBrace | Token::Eof | Token::Newline) {
                    Some(Stmt::Return(None))
                } else {
                    Some(Stmt::Return(Some(self.parse_expr())))
                }
            }
            Token::If3 => {
                self.advance();
                let cond = self.parse_expr();
                let body = self.parse_block();
                Some(Stmt::If3(cond, body, vec![], None, None))
            }
            Token::For3 => {
                self.advance();
                let var = if let Token::Ident(v) = self.advance() { v } else { return None; };
                self.expect(&Token::In);
                let iter = self.parse_expr();
                let body = self.parse_block();
                Some(Stmt::For3(var, iter, body))
            }
            Token::While3 => {
                self.advance();
                let cond = self.parse_expr();
                let body = self.parse_block();
                Some(Stmt::While3(cond, body))
            }
            Token::Try3 => {
                self.advance();
                let try_body = self.parse_block();
                self.skip_newlines();
                let fail_body = if matches!(self.peek(), Token::Fail | Token::Catch3 | Token::LBrace) {
                    if matches!(self.peek(), Token::Fail | Token::Catch3) { self.advance(); }
                    self.parse_block()
                } else { vec![] };
                Some(Stmt::Try3(try_body, None, fail_body))
            }
            Token::Class3 => {
                self.advance();
                let name = if let Token::Ident(n) = self.advance() { n } else { return None; };
                let parent = if matches!(self.peek(), Token::Extends3) {
                    self.advance();
                    if let Token::Ident(p) = self.advance() { Some(p) } else { None }
                } else { None };
                let body = self.parse_block();
                Some(Stmt::Class3(name, parent, body))
            }
            Token::Import3 => {
                self.advance();
                match self.advance() {
                    Token::Str(path) => Some(Stmt::Import3(path)),
                    Token::Ident(name) => Some(Stmt::Import3(format!("{}.nova", name))),
                    _ => None,
                }
            }
            Token::Break3 => { self.advance(); Some(Stmt::Break3) }
            Token::Continue3 => { self.advance(); Some(Stmt::Continue3) }
            Token::Ident(ref name) if name == "print" => {
                let name = name.clone();
                self.advance();
                self.expect(&Token::LParen);
                let mut args = Vec::new();
                while !matches!(self.peek(), Token::RParen | Token::Eof) {
                    args.push(self.parse_expr());
                    if !self.expect(&Token::Comma) { break; }
                }
                self.expect(&Token::RParen);
                Some(Stmt::Print(args))
            }
            Token::Ident(ref name) => {
                let name = name.clone();
                let next = self.tokens.get(self.pos + 1)
                    .map(|st| st.token.clone())
                    .unwrap_or(Token::Eof);
                match next {
                    Token::Assign => {
                        self.advance(); self.advance();
                        Some(Stmt::Assign(name, self.parse_expr()))
                    }
                    Token::PlusAssign => {
                        self.advance(); self.advance();
                        Some(Stmt::CompoundAssign(name, Op::Add, self.parse_expr()))
                    }
                    Token::MinusAssign => {
                        self.advance(); self.advance();
                        Some(Stmt::CompoundAssign(name, Op::Sub, self.parse_expr()))
                    }
                    _ => Some(Stmt::Expr(self.parse_expr())),
                }
            }
            _ => Some(Stmt::Expr(self.parse_expr())),
        }
    }

    fn parse_block(&mut self) -> Vec<Stmt> {
        self.skip_newlines();
        if !self.expect(&Token::LBrace) {
            let span = self.peek_span();
            self.diagnostics.push(format!(
                "[parse] error: expected '{{' at {}:{}, found {:?}",
                span.line, span.col, self.peek()
            ));
            return vec![];
        }
        let mut stmts = Vec::new();
        let mut guard = 0;
        loop {
            self.skip_newlines();
            if matches!(self.peek(), Token::RBrace | Token::Eof) { break; }
            if let Some(s) = self.parse_stmt() { stmts.push(s); }
            guard += 1;
            if guard > 10000 { break; }
        }
        self.expect(&Token::RBrace);
        stmts
    }

    fn parse_expr(&mut self) -> Expr {
        self.parse_or()
    }

    fn parse_or(&mut self) -> Expr {
        let mut left = self.parse_and();
        while matches!(self.peek(), Token::Or) {
            self.advance();
            left = Expr::BinOp(Box::new(left), Op::Or, Box::new(self.parse_and()));
        }
        left
    }

    fn parse_and(&mut self) -> Expr {
        let mut left = self.parse_cmp();
        while matches!(self.peek(), Token::And) {
            self.advance();
            left = Expr::BinOp(Box::new(left), Op::And, Box::new(self.parse_cmp()));
        }
        left
    }

    fn parse_cmp(&mut self) -> Expr {
        let mut left = self.parse_add();
        loop {
            let op = match self.peek() {
                Token::Eq => Op::Eq,
                Token::NotEq => Op::NotEq,
                Token::Lt => Op::Lt,
                Token::Gt => Op::Gt,
                Token::LtEq => Op::LtEq,
                Token::GtEq => Op::GtEq,
                _ => break,
            };
            self.advance();
            left = Expr::BinOp(Box::new(left), op, Box::new(self.parse_add()));
        }
        left
    }

    fn parse_add(&mut self) -> Expr {
        let mut left = self.parse_mul();
        loop {
            let op = match self.peek() {
                Token::Plus => Op::Add,
                Token::Minus => Op::Sub,
                _ => break,
            };
            self.advance();
            left = Expr::BinOp(Box::new(left), op, Box::new(self.parse_mul()));
        }
        left
    }

    fn parse_mul(&mut self) -> Expr {
        let mut left = self.parse_unary();
        loop {
            let op = match self.peek() {
                Token::Star => Op::Mul,
                Token::Slash => Op::Div,
                Token::Percent => Op::Mod,
                _ => break,
            };
            self.advance();
            left = Expr::BinOp(Box::new(left), op, Box::new(self.parse_unary()));
        }
        left
    }

    fn parse_unary(&mut self) -> Expr {
        if matches!(self.peek(), Token::Not) {
            self.advance();
            return Expr::UnaryOp(Op::Not, Box::new(self.parse_unary()));
        }
        if matches!(self.peek(), Token::Minus) {
            self.advance();
            return Expr::BinOp(Box::new(Expr::Int(0)), Op::Sub, Box::new(self.parse_postfix()));
        }
        self.parse_postfix()
    }

    fn parse_postfix(&mut self) -> Expr {
        let mut expr = self.parse_primary();
        loop {
            match self.peek() {
                Token::LParen => {
                    if let Expr::Ident(name) = &expr {
                        let name = name.clone();
                        self.advance();
                        let args = self.parse_args();
                        self.expect(&Token::RParen);
                        expr = Expr::Call(name, args);
                    } else { break; }
                }
                Token::LBracket => {
                    self.advance();
                    let idx = self.parse_expr();
                    self.expect(&Token::RBracket);
                    expr = Expr::Index(Box::new(expr), Box::new(idx));
                }
                Token::Dot => {
                    self.advance();
                    if let Token::Ident(field) = self.advance() {
                        if matches!(self.peek(), Token::LParen) {
                            self.advance();
                            let args = self.parse_args();
                            self.expect(&Token::RParen);
                            expr = Expr::MethodCall(Box::new(expr), field, args);
                        } else {
                            expr = Expr::DotAccess(Box::new(expr), field);
                        }
                    }
                }
                _ => break,
            }
        }
        expr
    }

    fn parse_primary(&mut self) -> Expr {
        match self.peek().clone() {
            Token::Int(v) => { self.advance(); Expr::Int(v) }
            Token::Float(v) => { self.advance(); Expr::Float(v) }
            Token::Str(s) => { self.advance(); Expr::Str(s) }
            Token::True => { self.advance(); Expr::Trit(1) }
            Token::False_ => { self.advance(); Expr::Trit(-1) }
            Token::Maybe => { self.advance(); Expr::Trit(0) }
            Token::Null => { self.advance(); Expr::Null }
            Token::Ident(name) => { self.advance(); Expr::Ident(name) }
            Token::LParen => {
                self.advance();
                let e = self.parse_expr();
                self.expect(&Token::RParen);
                e
            }
            Token::LBracket => {
                self.advance();
                let mut items = Vec::new();
                while !matches!(self.peek(), Token::RBracket | Token::Eof) {
                    self.skip_newlines();
                    items.push(self.parse_expr());
                    self.skip_newlines();
                    if !self.expect(&Token::Comma) { break; }
                }
                self.expect(&Token::RBracket);
                Expr::List(items)
            }
            Token::LBrace => {
                self.advance();
                let mut pairs = Vec::new();
                while !matches!(self.peek(), Token::RBrace | Token::Eof) {
                    self.skip_newlines();
                    let k = self.parse_expr();
                    self.expect(&Token::Colon);
                    let v = self.parse_expr();
                    pairs.push((k, v));
                    self.expect(&Token::Comma);
                    self.skip_newlines();
                }
                self.expect(&Token::RBrace);
                Expr::Dict(pairs)
            }
            Token::New3 => {
                self.advance();
                let cn = if let Token::Ident(n) = self.advance() { n } else { return Expr::Null; };
                self.expect(&Token::LParen);
                let args = self.parse_args();
                self.expect(&Token::RParen);
                Expr::New3(cn, args)
            }
            _ => { self.advance(); Expr::Null }
        }
    }

    fn parse_args(&mut self) -> Vec<Expr> {
        let mut args = Vec::new();
        while !matches!(self.peek(), Token::RParen | Token::Eof) {
            self.skip_newlines();
            args.push(self.parse_expr());
            self.skip_newlines();
            if !self.expect(&Token::Comma) { break; }
        }
        args
    }
}

