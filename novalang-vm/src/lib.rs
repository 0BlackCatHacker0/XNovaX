// NovaLang library crate — exposes lexer, parser, VM for tooling
// Used by: LSP server, formatter, test runner, REPL

pub mod lexer;
pub mod parser;
pub mod vm;
pub mod builtins;
pub mod tmatmul;
pub mod isa;
