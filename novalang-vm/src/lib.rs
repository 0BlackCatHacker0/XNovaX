// NovaLang library crate — exposes lexer, parser, VM for tooling
// Used by: LSP server, formatter, test runner, REPL

pub mod lexer;
pub mod parser;
pub mod vm;
pub mod builtins;
// Internal implementation details — not part of the public LSP/tooling API.
pub(crate) mod tmatmul;
pub(crate) mod isa;
