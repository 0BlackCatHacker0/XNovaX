// NovaLang Lexer — tokenizes .nova source into tokens
// v1.4: null coalesce (??), range (..), spread (...), plus v1.3 features
// "Good diagnostics depend on accurate span tracking from the lexer onward."

#[derive(Debug, Clone, PartialEq)]
pub enum Token {
    // Literals
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
    Null,

    // Identifiers and keywords
    Ident(String),
    Let,
    Const,
    Fn,
    Return,
    If3,
    Else3,
    Else,
    For3,
    While3,
    Try3,
    Fail,
    Catch3,
    Match3,
    Break3,
    Continue3,
    Import3,
    Class3,
    Extends3,
    New3,
    In,

    // Ternary constants
    True,      // TRUE = +1
    False_,    // FALSE_ = -1
    Maybe,     // MAYBE = 0

    // Operators
    Plus, Minus, Star, Slash, Percent,
    Eq, NotEq, Lt, Gt, LtEq, GtEq,
    Assign, PlusAssign, MinusAssign, StarAssign, SlashAssign, PercentAssign,
    And, Or, Not,
    Dot, Comma, Colon, Semicolon,

    // Delimiters
    LParen, RParen,
    LBrace, RBrace,
    LBracket, RBracket,

    // Special
    Arrow,     // =>
    Pipe,      // |>
    DotDot,    // ..  (range)
    Spread,    // ... (spread/unpack)
    NullCoalesce, // ?? (null coalescing)
    Newline,
    Eof,
}

// Span: source location for diagnostics (masterfile Section 8, 16)
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Span {
    pub line: u32,
    pub col: u32,
    pub offset: u32,
}

impl Span {
    pub fn new(line: u32, col: u32, offset: u32) -> Self {
        Self { line, col, offset }
    }
    pub fn zero() -> Self {
        Self { line: 0, col: 0, offset: 0 }
    }
}

impl std::fmt::Display for Span {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}:{}", self.line, self.col)
    }
}

// Spanned token: token + its source location
#[derive(Debug, Clone)]
pub struct SpannedToken {
    pub token: Token,
    pub span: Span,
}

// Main entry: returns (tokens, spans) for backward compat + new diagnostics
pub fn tokenize(source: &str) -> Vec<Token> {
    tokenize_spanned(source).into_iter().map(|st| st.token).collect()
}

// New entry: returns SpannedTokens with full location data
pub fn tokenize_spanned(source: &str) -> Vec<SpannedToken> {
    let mut tokens = Vec::new();
    let chars: Vec<char> = source.chars().collect();
    let len = chars.len();
    let mut i = 0;
    let mut line: u32 = 1;
    let mut col: u32 = 1;

    while i < len {
        let ch = chars[i];
        let tok_start_line = line;
        let tok_start_col = col;
        let tok_start_offset = i as u32;

        // Skip whitespace (except newlines)
        if ch == ' ' || ch == '\t' || ch == '\r' {
            i += 1;
            col += 1;
            continue;
        }

        // Newlines
        if ch == '\n' {
            tokens.push(SpannedToken {
                token: Token::Newline,
                span: Span::new(line, col, i as u32),
            });
            i += 1;
            line += 1;
            col = 1;
            continue;
        }

        // Comments: // or /* ... */ or #
        if ch == '/' && i + 1 < len && chars[i + 1] == '/' {
            while i < len && chars[i] != '\n' { i += 1; col += 1; }
            continue;
        }
        // Block comments: /* ... */
        if ch == '/' && i + 1 < len && chars[i + 1] == '*' {
            i += 2; col += 2;
            while i + 1 < len {
                if chars[i] == '*' && chars[i + 1] == '/' {
                    i += 2; col += 2;
                    break;
                }
                if chars[i] == '\n' {
                    line += 1;
                    col = 1;
                } else {
                    col += 1;
                }
                i += 1;
            }
            continue;
        }
        if ch == '#' {
            while i < len && chars[i] != '\n' { i += 1; col += 1; }
            continue;
        }

        // String literals
        if ch == '"' {
            i += 1;
            col += 1;
            let mut s = String::new();
            while i < len && chars[i] != '"' {
                if chars[i] == '\\' && i + 1 < len {
                    i += 1;
                    col += 1;
                    match chars[i] {
                        'n' => s.push('\n'),
                        't' => s.push('\t'),
                        '\\' => s.push('\\'),
                        '"' => s.push('"'),
                        'r' => s.push('\r'),
                        '0' => s.push('\0'),
                        _ => { s.push('\\'); s.push(chars[i]); }
                    }
                } else {
                    s.push(chars[i]);
                }
                i += 1;
                col += 1;
            }
            i += 1; // skip closing quote
            col += 1;
            tokens.push(SpannedToken {
                token: Token::Str(s),
                span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
            });
            continue;
        }

        // Single-quoted strings (same as double-quoted)
        if ch == '\'' {
            i += 1;
            col += 1;
            let mut s = String::new();
            while i < len && chars[i] != '\'' {
                if chars[i] == '\\' && i + 1 < len {
                    i += 1;
                    col += 1;
                    match chars[i] {
                        'n' => s.push('\n'),
                        't' => s.push('\t'),
                        '\\' => s.push('\\'),
                        '\'' => s.push('\''),
                        _ => { s.push('\\'); s.push(chars[i]); }
                    }
                } else {
                    s.push(chars[i]);
                }
                i += 1;
                col += 1;
            }
            if i < len { i += 1; col += 1; } // skip closing quote
            tokens.push(SpannedToken {
                token: Token::Str(s),
                span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
            });
            continue;
        }

        // F-string interpolation: f"hello {name} you are {age}"
        if ch == 'f' && i + 1 < len && chars[i + 1] == '"' {
            i += 2; // skip f"
            col += 2;
            let mut template = String::new();
            let mut expressions: Vec<String> = Vec::new();

            while i < len && chars[i] != '"' {
                if chars[i] == '\\' && i + 1 < len {
                    i += 1; col += 1;
                    match chars[i] {
                        'n' => template.push('\n'),
                        't' => template.push('\t'),
                        '\\' => template.push('\\'),
                        '"' => template.push('"'),
                        '{' => template.push('{'),
                        '}' => template.push('}'),
                        _ => { template.push('\\'); template.push(chars[i]); }
                    }
                    i += 1; col += 1;
                    continue;
                }
                if chars[i] == '{' {
                    template.push_str("{}");
                    i += 1; col += 1;
                    let mut expr_str = String::new();
                    let mut brace_depth = 1;
                    while i < len && brace_depth > 0 {
                        if chars[i] == '{' { brace_depth += 1; }
                        if chars[i] == '}' { brace_depth -= 1; if brace_depth == 0 { break; } }
                        expr_str.push(chars[i]);
                        i += 1; col += 1;
                    }
                    if i < len { i += 1; col += 1; } // skip closing }
                    expressions.push(expr_str);
                    continue;
                }
                template.push(chars[i]);
                i += 1; col += 1;
            }
            if i < len { i += 1; col += 1; } // skip closing "

            // Emit: format("template {}", expr1, expr2, ...)
            tokens.push(SpannedToken {
                token: Token::Ident("format".into()),
                span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
            });
            tokens.push(SpannedToken {
                token: Token::LParen,
                span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
            });
            tokens.push(SpannedToken {
                token: Token::Str(template),
                span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
            });
            for expr_str in &expressions {
                tokens.push(SpannedToken {
                    token: Token::Comma,
                    span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
                });
                // Recursively tokenize the expression
                let expr_tokens = tokenize_spanned(expr_str);
                for et in expr_tokens {
                    if !matches!(et.token, Token::Eof | Token::Newline) {
                        tokens.push(SpannedToken {
                            token: et.token,
                            span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
                        });
                    }
                }
            }
            tokens.push(SpannedToken {
                token: Token::RParen,
                span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
            });
            continue;
        }

        // Ternary literals: 0t+-0+ (balanced ternary → decimal)
        if ch == '0' && i + 1 < len && chars[i + 1] == 't' && i + 2 < len && (chars[i + 2] == '+' || chars[i + 2] == '-' || chars[i + 2] == '0') {
            i += 2; col += 2; // skip 0t
            let mut tval: i64 = 0;
            while i < len && (chars[i] == '+' || chars[i] == '-' || chars[i] == '0') {
                tval = tval * 3 + match chars[i] {
                    '+' => 1,
                    '-' => -1,
                    _ => 0,
                };
                i += 1; col += 1;
            }
            tokens.push(SpannedToken {
                token: Token::Int(tval),
                span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
            });
            continue;
        }

        // Numbers (with underscore separators: 1_000_000)
        if ch.is_ascii_digit() || (ch == '-' && i + 1 < len && chars[i + 1].is_ascii_digit() && needs_unary_spanned(&tokens)) {
            let start = i;
            if ch == '-' { i += 1; col += 1; }
            while i < len && (chars[i].is_ascii_digit() || chars[i] == '_') { i += 1; col += 1; }
            if i < len && chars[i] == '.' && i + 1 < len && chars[i + 1].is_ascii_digit() {
                i += 1; col += 1;
                while i < len && (chars[i].is_ascii_digit() || chars[i] == '_') { i += 1; col += 1; }
                let s: String = chars[start..i].iter().filter(|c| **c != '_').collect();
                tokens.push(SpannedToken {
                    token: Token::Float(s.parse().unwrap_or(0.0)),
                    span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
                });
            } else {
                let s: String = chars[start..i].iter().filter(|c| **c != '_').collect();
                tokens.push(SpannedToken {
                    token: Token::Int(s.parse().unwrap_or(0)),
                    span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
                });
            }
            continue;
        }

        // Identifiers and keywords
        if ch.is_ascii_alphabetic() || ch == '_' {
            let start = i;
            while i < len && (chars[i].is_ascii_alphanumeric() || chars[i] == '_') { i += 1; col += 1; }
            let word: String = chars[start..i].iter().collect();
            let tok = match word.as_str() {
                "let" => Token::Let,
                "const" => Token::Const,
                "fn" => Token::Fn,
                "return" => Token::Return,
                "if" | "if3" => Token::If3,
                "else3" => Token::Else3,
                "else" => Token::Else,
                "for" | "for3" => Token::For3,
                "while" | "while3" => Token::While3,
                "try3" => Token::Try3,
                "fail" => Token::Fail,
                "catch3" => Token::Catch3,
                "match3" => Token::Match3,
                "break3" => Token::Break3,
                "continue3" => Token::Continue3,
                "import3" => Token::Import3,
                "class3" => Token::Class3,
                "extends3" => Token::Extends3,
                "new3" => Token::New3,
                "in" => Token::In,
                "true" | "TRUE" => Token::True,
                "false" | "FALSE" => Token::False_,
                "null" => Token::Null,
                "maybe" | "MAYBE" => Token::Maybe,
                "and" | "AND" => Token::And,
                "or" | "OR" => Token::Or,
                "not" | "NOT" => Token::Not,
                _ => Token::Ident(word),
            };
            tokens.push(SpannedToken {
                token: tok,
                span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
            });
            continue;
        }

        // Three-char operators (must check before two-char)
        if i + 2 < len {
            let three: String = chars[i..i+3].iter().collect();
            if three == "..." {
                tokens.push(SpannedToken {
                    token: Token::Spread,
                    span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
                });
                i += 3;
                col += 3;
                continue;
            }
        }

        // Two-char operators
        if i + 1 < len {
            let two: String = chars[i..i+2].iter().collect();
            let tok = match two.as_str() {
                "==" => Some(Token::Eq),
                "!=" => Some(Token::NotEq),
                "<=" => Some(Token::LtEq),
                ">=" => Some(Token::GtEq),
                "+=" => Some(Token::PlusAssign),
                "-=" => Some(Token::MinusAssign),
                "*=" => Some(Token::StarAssign),
                "/=" => Some(Token::SlashAssign),
                "=>" => Some(Token::Arrow),
                "|>" => Some(Token::Pipe),
                "%=" => Some(Token::PercentAssign),
                "&&" => Some(Token::And),
                "||" => Some(Token::Or),
                "??" => Some(Token::NullCoalesce),
                ".." => Some(Token::DotDot),
                _ => None,
            };
            if let Some(t) = tok {
                tokens.push(SpannedToken {
                    token: t,
                    span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
                });
                i += 2;
                col += 2;
                continue;
            }
        }

        // Single-char operators
        let tok = match ch {
            '+' => Token::Plus,
            '-' => Token::Minus,
            '*' => Token::Star,
            '/' => Token::Slash,
            '%' => Token::Percent,
            '=' => Token::Assign,
            '<' => Token::Lt,
            '>' => Token::Gt,
            '!' => Token::Not,
            '.' => Token::Dot,
            ',' => Token::Comma,
            ':' => Token::Colon,
            ';' => Token::Semicolon,
            '(' => Token::LParen,
            ')' => Token::RParen,
            '{' => Token::LBrace,
            '}' => Token::RBrace,
            '[' => Token::LBracket,
            ']' => Token::RBracket,
            _ => {
                // Unknown character — emit warning with position
                eprintln!("[lexer] warning: unknown character '{}' at {}:{}", ch, line, col);
                i += 1;
                col += 1;
                continue;
            }
        };
        tokens.push(SpannedToken {
            token: tok,
            span: Span::new(tok_start_line, tok_start_col, tok_start_offset),
        });
        i += 1;
        col += 1;
    }

    tokens.push(SpannedToken {
        token: Token::Eof,
        span: Span::new(line, col, len as u32),
    });
    tokens
}

fn needs_unary_spanned(tokens: &[SpannedToken]) -> bool {
    match tokens.last().map(|st| &st.token) {
        None => true,
        Some(Token::LParen) | Some(Token::LBracket) | Some(Token::Comma)
        | Some(Token::Assign) | Some(Token::PlusAssign) | Some(Token::MinusAssign)
        | Some(Token::StarAssign) | Some(Token::SlashAssign) | Some(Token::PercentAssign)
        | Some(Token::Newline) | Some(Token::LBrace)
        | Some(Token::Return) | Some(Token::NullCoalesce) | Some(Token::Spread) => true,
        _ => false,
    }
}

fn needs_unary(tokens: &[Token]) -> bool {
    match tokens.last() {
        None => true,
        Some(Token::LParen) | Some(Token::LBracket) | Some(Token::Comma)
        | Some(Token::Assign) | Some(Token::PlusAssign) | Some(Token::MinusAssign)
        | Some(Token::StarAssign) | Some(Token::SlashAssign) | Some(Token::PercentAssign)
        | Some(Token::Newline) | Some(Token::LBrace)
        | Some(Token::Return) | Some(Token::NullCoalesce) | Some(Token::Spread) => true,
        _ => false,
    }
}
