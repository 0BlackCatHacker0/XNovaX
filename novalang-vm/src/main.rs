// NovaLang Native VM v1.2 — Ternary-first language runtime
// Replaces Python novalang.py with compiled Rust binary
// 3-5-7-13 harmonic constants baked in
// v1.2: Span-aware diagnostics (line:col in all errors)

mod lexer;
mod parser;
mod vm;
mod builtins;
pub mod tmatmul;
pub mod isa;

use std::env;
use std::fs;
use std::process;
use std::path::Path;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("NovaLang VM v1.1 (Rust)");
        eprintln!("Usage: novalang <file.nova>");
        eprintln!("       novalang -e 'code'");
        eprintln!("       novalang --transpile <file.py>");
        process::exit(0);
    }

    // --transpile mode: convert Python to NovaLang
    if args[1] == "--transpile" {
        let input = args.get(2).unwrap_or_else(|| {
            eprintln!("Error: --transpile requires a file argument");
            process::exit(1);
        });
        match fs::read_to_string(input) {
            Ok(code) => {
                let nova_code = transpile_py_to_nova(&code);
                print!("{}", nova_code);
            }
            Err(e) => {
                eprintln!("Error: cannot read {}: {}", input, e);
                process::exit(1);
            }
        }
        return;
    }

    // --parse-hunt mode: find syntax issues without executing
    let parse_hunt = args.iter().any(|a| a == "--parse-hunt");

    // Find the file argument (first arg that doesn't start with -)
    let file_arg = args.iter().skip(1).find(|a| !a.starts_with('-') && *a != "-e");

    let (code, base_dir) = if args[1] == "-e" {
        (args.get(2).cloned().unwrap_or_default(), String::new())
    } else if let Some(path) = file_arg {
        let dir = Path::new(path).parent()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default();
        match fs::read_to_string(path) {
            Ok(c) => (c, dir),
            Err(e) => {
                eprintln!("Error: cannot read {}: {}", path, e);
                process::exit(1);
            }
        }
    } else {
        eprintln!("Error: no file specified");
        process::exit(1);
    };

    // Use spanned tokenizer for file-based parsing (better diagnostics)
    let spanned_tokens = lexer::tokenize_spanned(&code);
    let tokens: Vec<lexer::Token> = spanned_tokens.iter().map(|st| st.token.clone()).collect();

    if parse_hunt {
        // Parse-hunt: report where parser gets stuck or swallows code
        let source_lines: Vec<&str> = code.lines().collect();
        let total_lines = source_lines.len();
        let token_count = tokens.len();

        // Map token positions to source line numbers
        let mut token_line_map: Vec<usize> = Vec::new();
        let mut line_num = 1usize;
        for tok in &tokens {
            token_line_map.push(line_num);
            if matches!(tok, lexer::Token::Newline) {
                line_num += 1;
            }
        }

        let ast = parser::parse(tokens.clone());
        eprintln!("[parse-hunt] File: {} lines, {} tokens, {} top-level statements",
                  total_lines, token_count, ast.len());

        // Find fn definitions in source and check they appear in AST
        let mut fn_lines: Vec<(usize, String)> = Vec::new();
        for (i, line) in source_lines.iter().enumerate() {
            let trimmed = line.trim();
            if trimmed.starts_with("fn ") {
                let name = trimmed.strip_prefix("fn ").unwrap_or("")
                    .split('(').next().unwrap_or("").trim().to_string();
                fn_lines.push((i + 1, name));
            }
        }

        // Check which functions appear in AST
        let mut found_fns: Vec<String> = Vec::new();
        for stmt in &ast {
            if let parser::Stmt::FnDef(name, _, _) = stmt {
                found_fns.push(name.clone());
            }
        }

        eprintln!("[parse-hunt] Source defines {} functions, AST has {} function defs",
                  fn_lines.len(), found_fns.len());

        for (line, name) in &fn_lines {
            if !found_fns.contains(name) {
                eprintln!("[parse-hunt] MISSING fn '{}' at line {} — likely swallowed by earlier function",
                         name, line);
            }
        }

        // Check for tstart/troute/tserve at end of file
        let has_tstart = source_lines.iter().any(|l| l.contains("tstart("));
        let has_tstart_ast = ast.iter().any(|s| {
            if let parser::Stmt::Expr(parser::Expr::Call(name, _)) = s {
                name == "tstart"
            } else { false }
        });
        if has_tstart && !has_tstart_ast {
            eprintln!("[parse-hunt] WARNING: tstart() in source but NOT in AST — server won't start!");
        }

        // Binary search to find the function that causes swallowing
        if fn_lines.len() > found_fns.len() {
            eprintln!("[parse-hunt] Performing binary search for problem function...");
            // Find first missing function
            for (line, name) in &fn_lines {
                if !found_fns.contains(name) {
                    // Check the previous function — it likely swallowed this one
                    let prev_fn = fn_lines.iter()
                        .filter(|(l, _)| *l < *line)
                        .last();
                    if let Some((prev_line, prev_name)) = prev_fn {
                        eprintln!("[parse-hunt] SUSPECT: fn '{}' starting at line {} likely swallows fn '{}' at line {}",
                                 prev_name, prev_line, name, line);
                        // Print the suspect function's source
                        let start = prev_line.saturating_sub(1);
                        let end = line.saturating_sub(1).min(source_lines.len());
                        for i in start..end {
                            if source_lines[i].trim().contains("else3")
                                || source_lines[i].trim().contains("maybe")
                                || source_lines[i].trim().contains("} else")
                                || source_lines[i].trim().starts_with("}")
                            {
                                eprintln!("[parse-hunt] >>> line {}: {}", i + 1, source_lines[i]);
                            }
                        }
                    }
                    break; // just report first problem
                }
            }
        }

        process::exit(0);
    }

    // Use spanned parser for line:col diagnostics
    let file_name = file_arg.cloned().unwrap_or_default();
    let ast = parser::parse_spanned_file(spanned_tokens, &file_name);
    let mut runtime = vm::Runtime::new();
    runtime.base_dir = base_dir;
    if let Err(e) = runtime.execute(&ast) {
        eprintln!("Runtime error: {}", e);
        process::exit(1);
    }
}

/// Simple Python-to-NovaLang transpiler (basic token substitution)
fn transpile_py_to_nova(py_code: &str) -> String {
    let mut output = String::new();
    for line in py_code.lines() {
        let trimmed = line.trim();
        // Skip empty lines and comments
        if trimmed.is_empty() {
            output.push('\n');
            continue;
        }
        if trimmed.starts_with('#') {
            output.push_str(&line.replace('#', "//"));
            output.push('\n');
            continue;
        }

        let mut nova_line = line.to_string();

        // Keywords
        nova_line = nova_line.replace("def ", "fn ");
        nova_line = nova_line.replace("elif ", "} else3 ");
        nova_line = nova_line.replace("if ", "if3 ");
        nova_line = nova_line.replace("for ", "for3 ");
        nova_line = nova_line.replace("while ", "while3 ");
        nova_line = nova_line.replace("class ", "class3 ");
        nova_line = nova_line.replace("import ", "import3 ");
        nova_line = nova_line.replace("True", "TRUE");
        nova_line = nova_line.replace("False", "FALSE_");
        nova_line = nova_line.replace("None", "null");
        nova_line = nova_line.replace("try:", "try3 {");
        nova_line = nova_line.replace("except ", "} fail ");
        nova_line = nova_line.replace("break", "break3");
        nova_line = nova_line.replace("continue", "continue3");

        // Colons at end of lines -> braces
        if nova_line.trim_end().ends_with(':') {
            nova_line = nova_line.trim_end().trim_end_matches(':').to_string();
            nova_line.push_str(" {");
        }

        output.push_str(&nova_line);
        output.push('\n');
    }
    output
}
