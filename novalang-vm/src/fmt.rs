// NovaLang Formatter (nova-fmt) v1.0
// Reads .nova source, parses to AST, emits canonical formatted output
// Usage: nova-fmt file.nova [--write]

use std::env;
use std::fs;
use novalang::parser::{self, Stmt, Expr, Op};
use novalang::lexer::{self, tokenize_spanned};

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("nova-fmt v1.0 — NovaLang code formatter");
        eprintln!("Usage: nova-fmt <file.nova> [--write]");
        eprintln!("  Without --write: prints formatted output to stdout");
        eprintln!("  With --write: overwrites the file in place");
        std::process::exit(0);
    }

    let file_path = &args[1];
    let write_mode = args.iter().any(|a| a == "--write" || a == "-w");

    let source = match fs::read_to_string(file_path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("Error: cannot read {}: {}", file_path, e);
            std::process::exit(1);
        }
    };

    let spanned = tokenize_spanned(&source);
    let tokens: Vec<lexer::Token> = spanned.iter().map(|st| st.token.clone()).collect();
    let ast = parser::parse(tokens);

    let formatted = format_program(&ast);

    if write_mode {
        if formatted == source {
            eprintln!("{}: already formatted", file_path);
        } else {
            fs::write(file_path, &formatted).unwrap_or_else(|e| {
                eprintln!("Error writing {}: {}", file_path, e);
                std::process::exit(1);
            });
            eprintln!("{}: formatted", file_path);
        }
    } else {
        print!("{}", formatted);
    }
}

// ── Program Formatter ────────────────────────────────────

fn format_program(stmts: &[Stmt]) -> String {
    let mut out = String::new();
    let mut prev_was_fn = false;

    for stmt in stmts {
        let is_fn = matches!(stmt, Stmt::FnDef(..));
        let is_class = matches!(stmt, Stmt::Class3(..));

        // Blank line before function/class definitions
        if (is_fn || is_class) && !out.is_empty() {
            if !out.ends_with("\n\n") {
                out.push('\n');
            }
        }
        // Blank line after function definitions
        if prev_was_fn && !is_fn && !is_class {
            if !out.ends_with("\n\n") {
                out.push('\n');
            }
        }

        format_stmt(&mut out, stmt, 0);
        out.push('\n');
        prev_was_fn = is_fn;
    }

    // Ensure trailing newline
    if !out.ends_with('\n') {
        out.push('\n');
    }
    out
}

fn format_stmt(out: &mut String, stmt: &Stmt, indent: usize) {
    let pad = "    ".repeat(indent);

    match stmt {
        Stmt::Let(name, expr) => {
            out.push_str(&pad);
            out.push_str("let ");
            out.push_str(name);
            out.push_str(" = ");
            format_expr(out, expr);
        }

        Stmt::Assign(name, expr) => {
            out.push_str(&pad);
            out.push_str(name);
            out.push_str(" = ");
            format_expr(out, expr);
        }

        Stmt::CompoundAssign(name, op, expr) => {
            out.push_str(&pad);
            out.push_str(name);
            out.push_str(match op {
                Op::Add => " += ",
                Op::Sub => " -= ",
                Op::Mul => " *= ",
                Op::Div => " /= ",
                Op::Mod => " %= ",
                _ => " = ",
            });
            format_expr(out, expr);
        }

        Stmt::DotAssign(obj, field, expr) => {
            out.push_str(&pad);
            out.push_str(obj);
            out.push('.');
            out.push_str(field);
            out.push_str(" = ");
            format_expr(out, expr);
        }

        Stmt::IndexAssign(name, index, val) => {
            out.push_str(&pad);
            out.push_str(name);
            out.push('[');
            format_expr(out, index);
            out.push_str("] = ");
            format_expr(out, val);
        }

        Stmt::Return(None) => {
            out.push_str(&pad);
            out.push_str("return");
        }

        Stmt::Return(Some(expr)) => {
            out.push_str(&pad);
            out.push_str("return ");
            format_expr(out, expr);
        }

        Stmt::Print(args) => {
            out.push_str(&pad);
            out.push_str("print(");
            for (i, arg) in args.iter().enumerate() {
                if i > 0 { out.push_str(", "); }
                format_expr(out, arg);
            }
            out.push(')');
        }

        Stmt::Expr(expr) => {
            out.push_str(&pad);
            format_expr(out, expr);
        }

        Stmt::FnDef(name, params, body) => {
            out.push_str(&pad);
            out.push_str("fn ");
            out.push_str(name);
            out.push('(');
            out.push_str(&params.join(", "));
            out.push_str(") {\n");
            format_body(out, body, indent + 1);
            out.push_str(&pad);
            out.push('}');
        }

        Stmt::If3(cond, then_body, elifs, maybe_body, else_body) => {
            out.push_str(&pad);
            out.push_str("if3 ");
            format_expr(out, cond);
            out.push_str(" {\n");
            format_body(out, then_body, indent + 1);
            out.push_str(&pad);
            out.push('}');

            for (elif_cond, elif_body) in elifs {
                out.push_str(" else3 ");
                format_expr(out, elif_cond);
                out.push_str(" {\n");
                format_body(out, elif_body, indent + 1);
                out.push_str(&pad);
                out.push('}');
            }

            if let Some(mb) = maybe_body {
                out.push_str(" maybe {\n");
                format_body(out, mb, indent + 1);
                out.push_str(&pad);
                out.push('}');
            }

            if let Some(eb) = else_body {
                // Check if it's an else-if chain
                if eb.len() == 1 {
                    if let Stmt::If3(..) = &eb[0] {
                        out.push_str(" else3 ");
                        format_stmt(out, &eb[0], indent);
                        return;
                    }
                }
                out.push_str(" else {\n");
                format_body(out, eb, indent + 1);
                out.push_str(&pad);
                out.push('}');
            }
        }

        Stmt::For3(var, iter, body) => {
            out.push_str(&pad);
            out.push_str("for3 ");
            out.push_str(var);
            out.push_str(" in ");
            format_expr(out, iter);
            out.push_str(" {\n");
            format_body(out, body, indent + 1);
            out.push_str(&pad);
            out.push('}');
        }

        Stmt::While3(cond, body) => {
            out.push_str(&pad);
            out.push_str("while3 ");
            format_expr(out, cond);
            out.push_str(" {\n");
            format_body(out, body, indent + 1);
            out.push_str(&pad);
            out.push('}');
        }

        Stmt::Try3(try_body, err_var, fail_body) => {
            out.push_str(&pad);
            out.push_str("try3 {\n");
            format_body(out, try_body, indent + 1);
            out.push_str(&pad);
            if let Some(var) = err_var {
                out.push_str(&format!("}} catch3({}) {{\n", var));
            } else {
                out.push_str("} catch3 {\n");
            }
            format_body(out, fail_body, indent + 1);
            out.push_str(&pad);
            out.push('}');
        }

        Stmt::Match3(expr, arms) => {
            out.push_str(&pad);
            out.push_str("match3 ");
            format_expr(out, expr);
            out.push_str(" {\n");
            for (trit, body) in arms {
                let label = match trit {
                    1 => "TRUE",
                    0 => "MAYBE",
                    -1 => "FALSE_",
                    v => {
                        out.push_str(&format!("{}    {} => {{\n", pad, v));
                        format_body(out, body, indent + 2);
                        out.push_str(&format!("{}    }}\n", pad));
                        continue;
                    }
                };
                out.push_str(&pad);
                out.push_str("    ");
                out.push_str(label);
                out.push_str(" => {\n");
                format_body(out, body, indent + 2);
                out.push_str(&pad);
                out.push_str("    }\n");
            }
            out.push_str(&pad);
            out.push('}');
        }

        Stmt::Break3 => {
            out.push_str(&pad);
            out.push_str("break3");
        }

        Stmt::Continue3 => {
            out.push_str(&pad);
            out.push_str("continue3");
        }

        Stmt::Block(stmts) => {
            for s in stmts {
                format_stmt(out, s, indent);
                out.push('\n');
            }
        }

        Stmt::Class3(name, parent, body) => {
            out.push_str(&pad);
            out.push_str("class3 ");
            out.push_str(name);
            if let Some(p) = parent {
                out.push_str(" extends3 ");
                out.push_str(p);
            }
            out.push_str(" {\n");
            format_body(out, body, indent + 1);
            out.push_str(&pad);
            out.push('}');
        }

        Stmt::Import3(path) => {
            out.push_str(&pad);
            out.push_str("import3 \"");
            out.push_str(path);
            out.push('"');
        }
    }
}

fn format_body(out: &mut String, stmts: &[Stmt], indent: usize) {
    for stmt in stmts {
        format_stmt(out, stmt, indent);
        out.push('\n');
    }
}

fn format_expr(out: &mut String, expr: &Expr) {
    match expr {
        Expr::Int(v) => out.push_str(&v.to_string()),
        Expr::Float(v) => out.push_str(&format!("{}", v)),
        Expr::Str(s) => {
            out.push('"');
            for ch in s.chars() {
                match ch {
                    '"' => out.push_str("\\\""),
                    '\\' => out.push_str("\\\\"),
                    '\n' => out.push_str("\\n"),
                    '\t' => out.push_str("\\t"),
                    '\r' => out.push_str("\\r"),
                    '\0' => out.push_str("\\0"),
                    c => out.push(c),
                }
            }
            out.push('"');
        }
        Expr::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Expr::Null => out.push_str("null"),
        Expr::Trit(t) => out.push_str(match t {
            1 => "TRUE",
            0 => "MAYBE",
            -1 => "FALSE_",
            _ => "MAYBE",
        }),
        Expr::Ident(name) => out.push_str(name),
        Expr::BinOp(left, op, right) => {
            let needs_parens_left = matches!(**left, Expr::BinOp(..));
            if needs_parens_left { out.push('('); }
            format_expr(out, left);
            if needs_parens_left { out.push(')'); }

            out.push_str(match op {
                Op::Add => " + ",
                Op::Sub => " - ",
                Op::Mul => " * ",
                Op::Div => " / ",
                Op::Mod => " % ",
                Op::Eq => " == ",
                Op::NotEq => " != ",
                Op::Lt => " < ",
                Op::Gt => " > ",
                Op::LtEq => " <= ",
                Op::GtEq => " >= ",
                Op::And => " and ",
                Op::Or => " or ",
                Op::Not => " not ",
                Op::Pipe => " |> ",
                Op::NullCoalesce => " ?? ",
                Op::In => " in ",
            });

            let needs_parens_right = matches!(**right, Expr::BinOp(..));
            if needs_parens_right { out.push('('); }
            format_expr(out, right);
            if needs_parens_right { out.push(')'); }
        }
        Expr::UnaryOp(op, operand) => {
            match op {
                Op::Not => out.push_str("not "),
                Op::Sub => out.push('-'),
                _ => {}
            }
            format_expr(out, operand);
        }
        Expr::Call(name, args) => {
            out.push_str(name);
            out.push('(');
            for (i, arg) in args.iter().enumerate() {
                if i > 0 { out.push_str(", "); }
                format_expr(out, arg);
            }
            out.push(')');
        }
        Expr::MethodCall(obj, method, args) => {
            format_expr(out, obj);
            out.push('.');
            out.push_str(method);
            out.push('(');
            for (i, arg) in args.iter().enumerate() {
                if i > 0 { out.push_str(", "); }
                format_expr(out, arg);
            }
            out.push(')');
        }
        Expr::Index(obj, index) => {
            format_expr(out, obj);
            out.push('[');
            format_expr(out, index);
            out.push(']');
        }
        Expr::DotAccess(obj, field) => {
            format_expr(out, obj);
            out.push('.');
            out.push_str(field);
        }
        Expr::List(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 { out.push_str(", "); }
                format_expr(out, item);
            }
            out.push(']');
        }
        Expr::Dict(pairs) => {
            out.push('{');
            for (i, (k, v)) in pairs.iter().enumerate() {
                if i > 0 { out.push_str(", "); }
                format_expr(out, k);
                out.push_str(": ");
                format_expr(out, v);
            }
            out.push('}');
        }
        Expr::New3(class_name, args) => {
            out.push_str("new3 ");
            out.push_str(class_name);
            out.push('(');
            for (i, arg) in args.iter().enumerate() {
                if i > 0 { out.push_str(", "); }
                format_expr(out, arg);
            }
            out.push(')');
        }
        Expr::Lambda(params, body) => {
            out.push_str("fn(");
            out.push_str(&params.join(", "));
            out.push_str(") { ");
            for stmt in body {
                format_stmt(out, stmt, 0);
            }
            out.push('}');
        }
        Expr::Range(start, end) => {
            format_expr(out, start);
            out.push_str("..");
            format_expr(out, end);
        }
        Expr::Spread(inner) => {
            out.push_str("...");
            format_expr(out, inner);
        }
    }
}
