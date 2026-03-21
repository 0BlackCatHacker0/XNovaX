// NovaLang Parser — builds AST from tokens
// v1.4: null coalesce (??), range (..), spread (...), destructuring, default params, `in` operator
// Reports line:col for parse errors instead of silent failures

use crate::lexer::{Token, Span, SpannedToken};

#[derive(Debug, Clone)]
pub enum Expr {
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
    Null,
    Trit(i8),              // -1, 0, +1
    Ident(String),
    BinOp(Box<Expr>, Op, Box<Expr>),
    UnaryOp(Op, Box<Expr>),
    Call(String, Vec<Expr>),
    MethodCall(Box<Expr>, String, Vec<Expr>),
    Index(Box<Expr>, Box<Expr>),
    DotAccess(Box<Expr>, String),
    List(Vec<Expr>),
    Dict(Vec<(Expr, Expr)>),
    New3(String, Vec<Expr>),   // new3 ClassName(args)
    Lambda(Vec<String>, Vec<Stmt>),  // fn(params) { body }
    Range(Box<Expr>, Box<Expr>),     // start..end  → generates list
    Spread(Box<Expr>),               // ...expr  → unpack into list/dict
}

#[derive(Debug, Clone)]
pub enum Op {
    Add, Sub, Mul, Div, Mod,
    Eq, NotEq, Lt, Gt, LtEq, GtEq,
    And, Or, Not,
    Pipe,           // |>
    NullCoalesce,   // ??
    In,             // x in list
}

#[derive(Debug, Clone)]
pub enum Stmt {
    Let(String, Expr),
    Assign(String, Expr),
    CompoundAssign(String, Op, Expr),
    DotAssign(String, String, Expr),
    IndexAssign(String, Expr, Expr),
    Return(Option<Expr>),
    Print(Vec<Expr>),
    Expr(Expr),
    FnDef(String, Vec<String>, Vec<Stmt>),
    If3(Expr, Vec<Stmt>, Vec<(Expr, Vec<Stmt>)>, Option<Vec<Stmt>>, Option<Vec<Stmt>>), // cond, then, elifs, maybe, else
    For3(String, Expr, Vec<Stmt>),
    While3(Expr, Vec<Stmt>),
    Try3(Vec<Stmt>, Option<String>, Vec<Stmt>),  // try3 { body } catch3(err_var) { fallback }
    Match3(Expr, Vec<(i8, Vec<Stmt>)>),
    Break3,
    Continue3,
    Block(Vec<Stmt>),
    Class3(String, Option<String>, Vec<Stmt>),  // name, parent, body (FnDefs)
    Import3(String),                             // path
}

// Entry point: backward compatible (takes Vec<Token>)
pub fn parse(tokens: Vec<Token>) -> Vec<Stmt> {
    let spanned: Vec<SpannedToken> = tokens.into_iter()
        .map(|t| SpannedToken { token: t, span: Span::zero() })
        .collect();
    parse_spanned(spanned)
}

// New entry point: takes SpannedTokens for diagnostics
pub fn parse_spanned(tokens: Vec<SpannedToken>) -> Vec<Stmt> {
    let mut p = Parser {
        tokens,
        pos: 0,
        file_name: String::new(),
        diagnostics: Vec::new(),
    };
    let stmts = p.parse_program();
    // Print accumulated diagnostics
    for diag in &p.diagnostics {
        eprintln!("{}", diag);
    }
    stmts
}

// Set file name for diagnostics
pub fn parse_spanned_file(tokens: Vec<SpannedToken>, file_name: &str) -> Vec<Stmt> {
    let mut p = Parser {
        tokens,
        pos: 0,
        file_name: file_name.to_string(),
        diagnostics: Vec::new(),
    };
    let stmts = p.parse_program();
    for diag in &p.diagnostics {
        eprintln!("{}", diag);
    }
    stmts
}

struct Parser {
    tokens: Vec<SpannedToken>,
    pos: usize,
    file_name: String,
    diagnostics: Vec<String>,
}

impl Parser {
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

    fn advance_spanned(&mut self) -> SpannedToken {
        let st = self.tokens.get(self.pos)
            .cloned()
            .unwrap_or(SpannedToken { token: Token::Eof, span: Span::zero() });
        self.pos += 1;
        st
    }

    fn expect(&mut self, expected: &Token) -> bool {
        if self.peek() == expected {
            self.advance();
            true
        } else {
            false
        }
    }

    fn expect_or_warn(&mut self, expected: &Token, context: &str) -> bool {
        if self.peek() == expected {
            self.advance();
            true
        } else {
            let span = self.peek_span();
            let loc = if self.file_name.is_empty() {
                format!("{}", span)
            } else {
                format!("{} {}", self.file_name, span)
            };
            self.diagnostics.push(format!(
                "[parse] {}:{}: expected {:?} in {}, found {:?}",
                loc, span, expected, context, self.peek()
            ));
            false
        }
    }

    fn skip_newlines(&mut self) {
        while matches!(self.peek(), Token::Newline) {
            self.advance();
        }
    }

    fn parse_program(&mut self) -> Vec<Stmt> {
        let mut stmts = Vec::new();
        while !matches!(self.peek(), Token::Eof) {
            self.skip_newlines();
            if matches!(self.peek(), Token::Eof) { break; }
            if matches!(self.peek(), Token::RBrace) {
                let span = self.peek_span();
                self.diagnostics.push(format!(
                    "[parse] warning: stray '}}' at {} — skipping (may indicate mismatched braces above)",
                    span
                ));
                self.advance();
                continue;
            }
            let before_pos = self.pos;
            if let Some(stmt) = self.parse_stmt() {
                stmts.push(stmt);
            } else if self.pos == before_pos {
                let span = self.peek_span();
                let tok = self.peek().clone();
                self.diagnostics.push(format!(
                    "[parse] warning: skipping unparseable token {:?} at {}",
                    tok, span
                ));
                self.advance(); // avoid infinite loop on unparseable token
            }
        }
        stmts
    }

    fn parse_block(&mut self) -> Vec<Stmt> {
        let open_span = self.peek_span();
        if !self.expect(&Token::LBrace) {
            self.diagnostics.push(format!(
                "[parse] error: expected '{{' at {}, found {:?}",
                open_span, self.peek()
            ));
            return Vec::new();
        }
        let mut stmts = Vec::new();
        let mut depth_guard = 0;
        loop {
            self.skip_newlines();
            if matches!(self.peek(), Token::RBrace | Token::Eof) { break; }
            if let Some(stmt) = self.parse_stmt() {
                stmts.push(stmt);
            }
            depth_guard += 1;
            if depth_guard > 50000 {
                let span = self.peek_span();
                self.diagnostics.push(format!(
                    "[parse] error: block starting at {} exceeded 50000 statements — likely parser hang. Breaking.",
                    open_span
                ));
                break;
            }
        }
        if !self.expect(&Token::RBrace) {
            let span = self.peek_span();
            self.diagnostics.push(format!(
                "[parse] error: unterminated block starting at {} — expected '}}' at {}, found {:?}",
                open_span, span, self.peek()
            ));
        }
        stmts
    }

    fn parse_stmt(&mut self) -> Option<Stmt> {
        self.skip_newlines();
        match self.peek().clone() {
            Token::Let | Token::Const => self.parse_let(),
            Token::Fn => self.parse_fn_def(),
            Token::Return => self.parse_return(),
            Token::If3 => self.parse_if3(),
            Token::For3 => self.parse_for3(),
            Token::While3 => self.parse_while3(),
            Token::Try3 => self.parse_try3(),
            Token::Match3 => self.parse_match3(),
            Token::Class3 => self.parse_class3(),
            Token::Import3 => self.parse_import3(),
            Token::Break3 => { self.advance(); Some(Stmt::Break3) }
            Token::Continue3 => { self.advance(); Some(Stmt::Continue3) }
            Token::RBrace => None,
            Token::Eof => None,
            Token::Ident(ref name) => {
                let name = name.clone();
                // Could be: assignment, compound assign, dot assign, function call, or expression
                if name == "print" {
                    return self.parse_print();
                }
                // Look ahead for assignment operators
                let next = self.tokens.get(self.pos + 1)
                    .map(|st| st.token.clone())
                    .unwrap_or(Token::Eof);
                match next {
                    Token::Assign => {
                        self.advance(); // ident
                        self.advance(); // =
                        let expr = self.parse_expr();
                        Some(Stmt::Assign(name, expr))
                    }
                    Token::PlusAssign => {
                        self.advance(); self.advance();
                        let expr = self.parse_expr();
                        Some(Stmt::CompoundAssign(name, Op::Add, expr))
                    }
                    Token::MinusAssign => {
                        self.advance(); self.advance();
                        let expr = self.parse_expr();
                        Some(Stmt::CompoundAssign(name, Op::Sub, expr))
                    }
                    Token::StarAssign => {
                        self.advance(); self.advance();
                        let expr = self.parse_expr();
                        Some(Stmt::CompoundAssign(name, Op::Mul, expr))
                    }
                    Token::SlashAssign => {
                        self.advance(); self.advance();
                        let expr = self.parse_expr();
                        Some(Stmt::CompoundAssign(name, Op::Div, expr))
                    }
                    Token::PercentAssign => {
                        self.advance(); self.advance();
                        let expr = self.parse_expr();
                        Some(Stmt::CompoundAssign(name, Op::Mod, expr))
                    }
                    Token::LBracket => {
                        // Could be index assign: name[key] = value
                        let mut scan = self.pos + 2;
                        let mut depth = 1;
                        while scan < self.tokens.len() && depth > 0 {
                            match &self.tokens[scan].token {
                                Token::LBracket => depth += 1,
                                Token::RBracket => depth -= 1,
                                Token::Eof => break,
                                _ => {}
                            }
                            scan += 1;
                        }
                        let after_bracket = self.tokens.get(scan)
                            .map(|st| st.token.clone())
                            .unwrap_or(Token::Eof);
                        if matches!(after_bracket, Token::Assign) {
                            self.advance(); // ident
                            self.advance(); // [
                            let index_expr = self.parse_expr();
                            self.expect(&Token::RBracket);
                            self.advance(); // =
                            let val_expr = self.parse_expr();
                            return Some(Stmt::IndexAssign(name, index_expr, val_expr));
                        }
                        let expr = self.parse_expr();
                        Some(Stmt::Expr(expr))
                    }
                    Token::Dot => {
                        let third = self.tokens.get(self.pos + 2)
                            .map(|st| st.token.clone())
                            .unwrap_or(Token::Eof);
                        if let Token::Ident(field) = third {
                            let fourth = self.tokens.get(self.pos + 3)
                                .map(|st| st.token.clone())
                                .unwrap_or(Token::Eof);
                            if matches!(fourth, Token::Assign) {
                                self.advance(); // ident
                                self.advance(); // .
                                self.advance(); // field
                                self.advance(); // =
                                let expr = self.parse_expr();
                                return Some(Stmt::DotAssign(name, field, expr));
                            }
                        }
                        let expr = self.parse_expr();
                        Some(Stmt::Expr(expr))
                    }
                    _ => {
                        let expr = self.parse_expr();
                        Some(Stmt::Expr(expr))
                    }
                }
            }
            _ => {
                let expr = self.parse_expr();
                Some(Stmt::Expr(expr))
            }
        }
    }

    fn parse_let(&mut self) -> Option<Stmt> {
        self.advance(); // let/const

        // Destructuring: let [a, b, c] = expr → desugars to sequential lets
        if matches!(self.peek(), Token::LBracket) {
            self.advance(); // [
            let mut names = Vec::new();
            while !matches!(self.peek(), Token::RBracket | Token::Eof) {
                if let Token::Ident(n) = self.advance() {
                    names.push(n);
                }
                if !self.expect(&Token::Comma) { break; }
            }
            self.expect(&Token::RBracket);
            self.expect(&Token::Assign);
            let expr = self.parse_expr();

            // Desugar: let __destructure_tmp = expr; let a = __destructure_tmp[0]; ...
            let tmp = format!("__destructure_{}", self.pos);
            let mut stmts = vec![Stmt::Let(tmp.clone(), expr)];
            for (i, name) in names.iter().enumerate() {
                stmts.push(Stmt::Let(
                    name.clone(),
                    Expr::Index(Box::new(Expr::Ident(tmp.clone())), Box::new(Expr::Int(i as i64)))
                ));
            }
            return Some(Stmt::Block(stmts));
        }

        // Destructuring: let {a, b} = dict → desugars to dict_get calls
        if matches!(self.peek(), Token::LBrace) {
            self.advance(); // {
            let mut names = Vec::new();
            while !matches!(self.peek(), Token::RBrace | Token::Eof) {
                self.skip_newlines();
                if let Token::Ident(n) = self.advance() {
                    names.push(n);
                }
                self.skip_newlines();
                if !self.expect(&Token::Comma) { break; }
            }
            self.expect(&Token::RBrace);
            self.expect(&Token::Assign);
            let expr = self.parse_expr();

            let tmp = format!("__destructure_{}", self.pos);
            let mut stmts = vec![Stmt::Let(tmp.clone(), expr)];
            for name in &names {
                stmts.push(Stmt::Let(
                    name.clone(),
                    Expr::Call("dict_get".into(), vec![
                        Expr::Ident(tmp.clone()),
                        Expr::Str(name.clone()),
                    ])
                ));
            }
            return Some(Stmt::Block(stmts));
        }

        if let Token::Ident(name) = self.advance() {
            if !self.expect(&Token::Assign) {
                let span = self.peek_span();
                self.diagnostics.push(format!(
                    "[parse] warning: 'let {}' without '=' at {} — did you mean 'let {} = ...'?",
                    name, span, name
                ));
                return Some(Stmt::Let(name, Expr::Null));
            }

            // Special case: let x = try3 { body } { fallback }
            if matches!(self.peek(), Token::Try3) {
                self.advance(); // try3
                let try_body = self.parse_block();
                self.skip_newlines();
                let mut err_var = None;
                let fail_body = if matches!(self.peek(), Token::Fail | Token::Catch3) {
                    self.advance();
                    if matches!(self.peek(), Token::LParen) {
                        self.advance(); // (
                        if let Token::Ident(ev) = self.advance() {
                            err_var = Some(ev);
                        }
                        self.expect(&Token::RParen);
                    }
                    self.parse_block()
                } else if matches!(self.peek(), Token::LBrace) {
                    self.parse_block()
                } else {
                    vec![]
                };

                // Wrap: try body assigns last expr to variable
                let mut wrapped_try = Vec::new();
                for (i, s) in try_body.into_iter().enumerate() {
                    if i == 0 {
                        match s {
                            Stmt::Expr(e) => wrapped_try.push(Stmt::Assign(name.clone(), e)),
                            other => wrapped_try.push(other),
                        }
                    } else {
                        wrapped_try.push(s);
                    }
                }
                let mut wrapped_fail = Vec::new();
                for (i, s) in fail_body.into_iter().enumerate() {
                    if i == 0 {
                        match s {
                            Stmt::Expr(e) => wrapped_fail.push(Stmt::Assign(name.clone(), e)),
                            other => wrapped_fail.push(other),
                        }
                    } else {
                        wrapped_fail.push(s);
                    }
                }

                return Some(Stmt::Block(vec![
                    Stmt::Let(name.clone(), Expr::Null),
                    Stmt::Try3(wrapped_try, err_var, wrapped_fail),
                ]));
            }

            let expr = self.parse_expr();
            Some(Stmt::Let(name, expr))
        } else {
            let span = self.peek_span();
            self.diagnostics.push(format!(
                "[parse] error: expected identifier after 'let' at {}",
                span
            ));
            None
        }
    }

    fn parse_fn_def(&mut self) -> Option<Stmt> {
        let fn_span = self.peek_span();
        self.advance(); // fn
        let name = if let Token::Ident(n) = self.advance() { n } else {
            self.diagnostics.push(format!(
                "[parse] error: expected function name after 'fn' at {}",
                fn_span
            ));
            return None;
        };
        self.expect_or_warn(&Token::LParen, &format!("fn {} parameters", name));
        let mut params = Vec::new();
        let mut defaults: Vec<(String, Expr)> = Vec::new();
        while !matches!(self.peek(), Token::RParen | Token::Eof) {
            if let Token::Ident(p) = self.advance() {
                // Skip type annotations (: type)
                if matches!(self.peek(), Token::Colon) {
                    self.advance();
                    self.advance(); // skip type name
                }
                // Default parameter: param = expr
                if matches!(self.peek(), Token::Assign) {
                    self.advance(); // consume =
                    let default_expr = self.parse_expr();
                    defaults.push((p.clone(), default_expr));
                }
                params.push(p);
            }
            if !self.expect(&Token::Comma) { break; }
        }
        self.expect_or_warn(&Token::RParen, &format!("fn {} parameters", name));
        let mut body = self.parse_block();

        // Desugar defaults: prepend `if3 param == null { param = default }` for each default
        if !defaults.is_empty() {
            let mut preamble = Vec::new();
            for (param, default) in defaults.into_iter().rev() {
                preamble.push(Stmt::If3(
                    Expr::BinOp(
                        Box::new(Expr::Ident(param.clone())),
                        Op::Eq,
                        Box::new(Expr::Null),
                    ),
                    vec![Stmt::Assign(param, default)],
                    vec![],
                    None,
                    None,
                ));
            }
            preamble.reverse();
            preamble.append(&mut body);
            body = preamble;
        }

        Some(Stmt::FnDef(name, params, body))
    }

    fn parse_return(&mut self) -> Option<Stmt> {
        self.advance(); // return
        self.skip_newlines();
        if matches!(self.peek(), Token::RBrace | Token::Eof | Token::Newline) {
            Some(Stmt::Return(None))
        } else {
            let expr = self.parse_expr();
            Some(Stmt::Return(Some(expr)))
        }
    }

    fn parse_print(&mut self) -> Option<Stmt> {
        self.advance(); // print
        self.expect(&Token::LParen);
        let mut args = Vec::new();
        while !matches!(self.peek(), Token::RParen | Token::Eof) {
            args.push(self.parse_expr());
            if !self.expect(&Token::Comma) { break; }
        }
        self.expect(&Token::RParen);
        Some(Stmt::Print(args))
    }

    fn parse_if3(&mut self) -> Option<Stmt> {
        self.advance(); // if3
        let cond = self.parse_expr_until_brace();
        let body = self.parse_block();
        let mut elif_branches = Vec::new();
        let mut maybe_body = None;
        let mut else_body = None;

        loop {
            self.skip_newlines();
            if matches!(self.peek(), Token::Else3) {
                self.advance(); // else3
                self.skip_newlines();
                if matches!(self.peek(), Token::LBrace) {
                    else_body = Some(self.parse_block());
                    break;
                } else if matches!(self.peek(), Token::If3) {
                    if let Some(nested_if) = self.parse_if3() {
                        else_body = Some(vec![nested_if]);
                    }
                    break;
                } else {
                    let elif_cond = self.parse_expr_until_brace();
                    let elif_body = self.parse_block();
                    elif_branches.push((elif_cond, elif_body));
                }
            } else if matches!(self.peek(), Token::Maybe) {
                self.advance();
                self.skip_newlines();
                maybe_body = Some(self.parse_block());
            } else if matches!(self.peek(), Token::Else) {
                self.advance();
                self.skip_newlines();
                if matches!(self.peek(), Token::LBrace) {
                    else_body = Some(self.parse_block());
                    break;
                } else if matches!(self.peek(), Token::If3) {
                    if let Some(nested_if) = self.parse_if3() {
                        else_body = Some(vec![nested_if]);
                    }
                    break;
                } else {
                    let elif_cond = self.parse_expr_until_brace();
                    let elif_body = self.parse_block();
                    elif_branches.push((elif_cond, elif_body));
                }
            } else if matches!(self.peek(), Token::LBrace) {
                // Bare { } after if3 block = else block (NovaLang shorthand)
                else_body = Some(self.parse_block());
                break;
            } else {
                break;
            }
        }
        Some(Stmt::If3(cond, body, elif_branches, maybe_body, else_body))
    }

    fn parse_for3(&mut self) -> Option<Stmt> {
        self.advance(); // for3
        let var = if let Token::Ident(v) = self.advance() { v } else {
            let span = self.peek_span();
            self.diagnostics.push(format!(
                "[parse] error: expected variable name after 'for3' at {}",
                span
            ));
            return None;
        };
        self.expect(&Token::In);
        let iter = self.parse_expr_until_brace();
        let body = self.parse_block();
        Some(Stmt::For3(var, iter, body))
    }

    fn parse_while3(&mut self) -> Option<Stmt> {
        self.advance(); // while3
        let cond = self.parse_expr_until_brace();
        let body = self.parse_block();
        Some(Stmt::While3(cond, body))
    }

    fn parse_try3(&mut self) -> Option<Stmt> {
        let try_span = self.peek_span();
        self.advance(); // try3
        if !matches!(self.peek(), Token::LBrace) {
            self.diagnostics.push(format!(
                "[parse] warning: try3 at {} without '{{' — may swallow subsequent code. Found {:?}",
                try_span, self.peek()
            ));
        }
        let try_body = self.parse_block();
        self.skip_newlines();
        let mut err_var = None;
        let fail_body = if matches!(self.peek(), Token::Fail | Token::Catch3) {
            self.advance();
            if matches!(self.peek(), Token::LParen) {
                self.advance(); // (
                if let Token::Ident(name) = self.advance() {
                    err_var = Some(name);
                }
                self.expect(&Token::RParen);
            }
            self.parse_block()
        } else if matches!(self.peek(), Token::LBrace) {
            self.parse_block()
        } else {
            Vec::new()
        };
        Some(Stmt::Try3(try_body, err_var, fail_body))
    }

    fn parse_class3(&mut self) -> Option<Stmt> {
        self.advance(); // class3
        let name = if let Token::Ident(n) = self.advance() { n } else { return None; };
        let parent = if matches!(self.peek(), Token::Extends3) {
            self.advance();
            if let Token::Ident(p) = self.advance() { Some(p) } else { None }
        } else {
            None
        };
        self.expect(&Token::LBrace);
        let mut body = Vec::new();
        loop {
            self.skip_newlines();
            if matches!(self.peek(), Token::RBrace | Token::Eof) { break; }
            if let Some(stmt) = self.parse_stmt() {
                body.push(stmt);
            }
        }
        self.expect(&Token::RBrace);
        Some(Stmt::Class3(name, parent, body))
    }

    fn parse_import3(&mut self) -> Option<Stmt> {
        self.advance(); // import3
        let has_paren = matches!(self.peek(), Token::LParen);
        if has_paren { self.advance(); }
        let result = match self.advance() {
            Token::Str(path) => Some(Stmt::Import3(path)),
            Token::Ident(name) => Some(Stmt::Import3(format!("{}.nova", name))),
            _ => None,
        };
        if has_paren && matches!(self.peek(), Token::RParen) { self.advance(); }
        result
    }

    fn parse_match3(&mut self) -> Option<Stmt> {
        self.advance(); // match3
        let expr = self.parse_expr_until_brace();
        self.expect(&Token::LBrace);
        let mut arms = Vec::new();
        loop {
            self.skip_newlines();
            if matches!(self.peek(), Token::RBrace | Token::Eof) { break; }
            let trit = match self.peek() {
                Token::True => { self.advance(); 1i8 }
                Token::Maybe => { self.advance(); 0i8 }
                Token::False_ => { self.advance(); -1i8 }
                Token::Int(v) => { let v = *v as i8; self.advance(); v }
                Token::Plus => {
                    self.advance();
                    if let Token::Int(v) = self.advance() { v as i8 } else { 1 }
                }
                Token::Minus => {
                    self.advance();
                    if let Token::Int(v) = self.advance() { -(v as i8) } else { -1 }
                }
                _ => { self.advance(); 0 }
            };
            self.expect(&Token::Arrow);
            if matches!(self.peek(), Token::LBrace) {
                let body = self.parse_block();
                arms.push((trit, body));
            } else {
                let expr = self.parse_expr();
                arms.push((trit, vec![Stmt::Expr(expr)]));
            }
            self.skip_newlines();
        }
        self.expect(&Token::RBrace);
        Some(Stmt::Match3(expr, arms))
    }

    // Parse expression until we hit {
    fn parse_expr_until_brace(&mut self) -> Expr {
        let start = self.pos;
        let mut depth = 0;
        while self.pos < self.tokens.len() {
            match self.peek() {
                Token::LBrace if depth == 0 => break,
                Token::LParen | Token::LBracket => { depth += 1; self.pos += 1; }
                Token::RParen | Token::RBracket => {
                    if depth > 0 { depth -= 1; }
                    self.pos += 1;
                }
                Token::Eof => break,
                _ => { self.pos += 1; }
            }
        }
        let end = self.pos;
        self.pos = start;
        let expr = self.parse_expr();
        while self.pos < end { self.pos += 1; }
        expr
    }

    // Expression parsing with operator precedence
    fn parse_expr(&mut self) -> Expr {
        self.parse_pipe()
    }

    // Pipe operator: lowest precedence
    // x |> f       => Call("f", [x])
    // x |> f(a, b) => Call("f", [x, a, b])
    // Chains left-to-right: x |> f |> g => g(f(x))
    fn parse_pipe(&mut self) -> Expr {
        let mut left = self.parse_null_coalesce();
        while matches!(self.peek(), Token::Pipe) {
            self.advance(); // consume |>
            // Parse the right side as a postfix expression (could be ident or call)
            let right = self.parse_postfix();
            left = match right {
                Expr::Call(name, mut args) => {
                    // x |> f(a, b) => f(x, a, b) — prepend left as first arg
                    args.insert(0, left);
                    Expr::Call(name, args)
                }
                Expr::Ident(name) => {
                    // x |> f => f(x)
                    Expr::Call(name, vec![left])
                }
                _ => {
                    let span = self.peek_span();
                    self.diagnostics.push(format!(
                        "[parse] warning: right side of |> at {} must be a function name or call, got {:?}",
                        span, right
                    ));
                    Expr::Null
                }
            };
        }
        left
    }

    // Null coalescing: x ?? default — returns x if non-null, else default
    fn parse_null_coalesce(&mut self) -> Expr {
        let mut left = self.parse_or();
        while matches!(self.peek(), Token::NullCoalesce) {
            self.advance(); // consume ??
            let right = self.parse_or();
            left = Expr::BinOp(Box::new(left), Op::NullCoalesce, Box::new(right));
        }
        left
    }

    fn parse_or(&mut self) -> Expr {
        let mut left = self.parse_and();
        while matches!(self.peek(), Token::Or) {
            self.advance();
            let right = self.parse_and();
            left = Expr::BinOp(Box::new(left), Op::Or, Box::new(right));
        }
        left
    }

    fn parse_and(&mut self) -> Expr {
        let mut left = self.parse_comparison();
        while matches!(self.peek(), Token::And) {
            self.advance();
            let right = self.parse_comparison();
            left = Expr::BinOp(Box::new(left), Op::And, Box::new(right));
        }
        left
    }

    fn parse_comparison(&mut self) -> Expr {
        let mut left = self.parse_range();
        loop {
            let op = match self.peek() {
                Token::Eq => Op::Eq,
                Token::NotEq => Op::NotEq,
                Token::Lt => Op::Lt,
                Token::Gt => Op::Gt,
                Token::LtEq => Op::LtEq,
                Token::GtEq => Op::GtEq,
                Token::In => Op::In,    // x in [1,2,3]
                _ => break,
            };
            self.advance();
            let right = self.parse_range();
            left = Expr::BinOp(Box::new(left), op, Box::new(right));
        }
        left
    }

    // Range: start..end  → Expr::Range(start, end)
    fn parse_range(&mut self) -> Expr {
        let left = self.parse_add();
        if matches!(self.peek(), Token::DotDot) {
            self.advance(); // consume ..
            let right = self.parse_add();
            return Expr::Range(Box::new(left), Box::new(right));
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
            let right = self.parse_mul();
            left = Expr::BinOp(Box::new(left), op, Box::new(right));
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
            let right = self.parse_unary();
            left = Expr::BinOp(Box::new(left), op, Box::new(right));
        }
        left
    }

    fn parse_unary(&mut self) -> Expr {
        if matches!(self.peek(), Token::Not) {
            self.advance();
            let expr = self.parse_unary();
            return Expr::UnaryOp(Op::Not, Box::new(expr));
        }
        if matches!(self.peek(), Token::Minus) {
            self.advance();
            let expr = self.parse_postfix();
            return Expr::BinOp(Box::new(Expr::Int(0)), Op::Sub, Box::new(expr));
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
                        self.advance(); // (
                        let args = self.parse_args();
                        self.expect(&Token::RParen);
                        expr = Expr::Call(name, args);
                    } else {
                        break;
                    }
                }
                Token::LBracket => {
                    self.advance();
                    let index = self.parse_expr();
                    self.expect(&Token::RBracket);
                    expr = Expr::Index(Box::new(expr), Box::new(index));
                }
                Token::Dot => {
                    self.advance();
                    if let Token::Ident(field) = self.advance() {
                        if matches!(self.peek(), Token::LParen) {
                            self.advance(); // (
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
            Token::Bool(b) => { self.advance(); Expr::Bool(b) }
            Token::Null => { self.advance(); Expr::Null }
            Token::Ident(name) => { self.advance(); Expr::Ident(name) }
            Token::LParen => {
                self.advance();
                let expr = self.parse_expr();
                self.expect(&Token::RParen);
                expr
            }
            Token::LBracket => {
                self.advance();
                let mut items = Vec::new();
                loop {
                    self.skip_newlines();
                    if matches!(self.peek(), Token::RBracket | Token::Eof) { break; }
                    // Spread: [...other_list] → Expr::Spread(expr)
                    if matches!(self.peek(), Token::Spread) {
                        self.advance(); // consume ...
                        let expr = self.parse_expr();
                        items.push(Expr::Spread(Box::new(expr)));
                    } else {
                        items.push(self.parse_expr());
                    }
                    self.skip_newlines();
                    if !self.expect(&Token::Comma) { break; }
                }
                self.skip_newlines();
                self.expect(&Token::RBracket);
                Expr::List(items)
            }
            Token::LBrace => {
                self.advance();
                let mut pairs = Vec::new();
                while !matches!(self.peek(), Token::RBrace | Token::Eof) {
                    self.skip_newlines();
                    if matches!(self.peek(), Token::RBrace) { break; }
                    // Spread in dict: {...other_dict}
                    if matches!(self.peek(), Token::Spread) {
                        self.advance(); // consume ...
                        let expr = self.parse_expr();
                        // Use special key "__spread__" to mark spread entries
                        pairs.push((Expr::Str("__spread__".into()), expr));
                        self.expect(&Token::Comma);
                        self.skip_newlines();
                        continue;
                    }
                    let key = self.parse_expr();
                    self.expect(&Token::Colon);
                    let val = self.parse_expr();
                    pairs.push((key, val));
                    self.expect(&Token::Comma);
                    self.skip_newlines();
                }
                self.expect(&Token::RBrace);
                Expr::Dict(pairs)
            }
            Token::New3 => {
                self.advance();
                let class_name = if let Token::Ident(n) = self.advance() { n } else { return Expr::Null; };
                self.expect(&Token::LParen);
                let args = self.parse_args();
                self.expect(&Token::RParen);
                Expr::New3(class_name, args)
            }
            Token::Try3 => {
                self.advance();
                Expr::Null
            }
            Token::Fn => {
                self.advance();
                self.expect(&Token::LParen);
                let mut params = Vec::new();
                let mut defaults: Vec<(String, Expr)> = Vec::new();
                while !matches!(self.peek(), Token::RParen | Token::Eof) {
                    if let Token::Ident(p) = self.advance() {
                        // Skip type annotations (: type)
                        if matches!(self.peek(), Token::Colon) {
                            self.advance();
                            self.advance(); // skip type name
                        }
                        // Default parameter
                        if matches!(self.peek(), Token::Assign) {
                            self.advance();
                            let default_expr = self.parse_expr();
                            defaults.push((p.clone(), default_expr));
                        }
                        params.push(p);
                    }
                    if !self.expect(&Token::Comma) { break; }
                }
                self.expect(&Token::RParen);
                let mut body = self.parse_block();

                // Desugar defaults for lambdas
                if !defaults.is_empty() {
                    let mut preamble = Vec::new();
                    for (param, default) in defaults.into_iter().rev() {
                        preamble.push(Stmt::If3(
                            Expr::BinOp(
                                Box::new(Expr::Ident(param.clone())),
                                Op::Eq,
                                Box::new(Expr::Null),
                            ),
                            vec![Stmt::Assign(param, default)],
                            vec![],
                            None,
                            None,
                        ));
                    }
                    preamble.reverse();
                    preamble.append(&mut body);
                    body = preamble;
                }

                Expr::Lambda(params, body)
            }
            _ => {
                let span = self.peek_span();
                let tok = self.peek().clone();
                self.diagnostics.push(format!(
                    "[parse] warning: unexpected token {:?} at {} in expression",
                    tok, span
                ));
                self.advance();
                Expr::Null
            }
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
