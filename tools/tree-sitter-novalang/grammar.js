/// <reference types="tree-sitter-cli/dsl" />
// Tree-sitter grammar for NovaLang (.nova files)
// v1.1: Fixed paren-optional control flow, try3/fail, maybe/else3 branches

module.exports = grammar({
  name: "novalang",

  extras: $ => [
    /\s/,
    $.comment,
  ],

  word: $ => $.identifier,

  conflicts: $ => [
    [$.call_expression, $.identifier],
  ],

  rules: {
    // ── Top-level ──────────────────────────────────────────
    source_file: $ => repeat($._statement),

    _statement: $ => choice(
      $.variable_declaration,
      $.constant_declaration,
      $.function_declaration,
      $.class_declaration,
      $.return_statement,
      $.if_statement,
      $.for_statement,
      $.while_statement,
      $.try_statement,
      $.match_statement,
      $.import_statement,
      $.break_statement,
      $.continue_statement,
      $.expression_statement,
    ),

    // ── Declarations ───────────────────────────────────────
    variable_declaration: $ => seq(
      "let",
      field("name", $.identifier),
      "=",
      field("value", $._expression),
      optional(";"),
    ),

    constant_declaration: $ => seq(
      "const",
      field("name", $.identifier),
      "=",
      field("value", $._expression),
      optional(";"),
    ),

    function_declaration: $ => seq(
      "fn",
      field("name", $.identifier),
      "(",
      optional($.parameter_list),
      ")",
      field("body", $.block),
    ),

    parameter_list: $ => seq(
      $.identifier,
      repeat(seq(",", $.identifier)),
    ),

    class_declaration: $ => seq(
      "class3",
      field("name", $.identifier),
      optional(seq("extends3", field("superclass", $.identifier))),
      field("body", $.block),
    ),

    // ── Control flow ───────────────────────────────────────
    // NovaLang: if3 EXPR { } — NO parens required (but optional)
    if_statement: $ => seq(
      choice("if3", "if"),
      field("condition", $._expression),
      field("consequence", $.block),
      repeat($.else_clause),
    ),

    else_clause: $ => choice(
      // maybe { } — ternary middle branch (MAYBE/0)
      seq("maybe", $.block),
      // else3 { } or else { }
      seq(choice("else3", "else"), $.block),
      // else3 if3 ... (chained)
      seq(choice("else3", "else"), $.if_statement),
    ),

    // for3 VAR in EXPR { } — NO parens required
    for_statement: $ => seq(
      choice("for3", "for"),
      field("variable", $.identifier),
      "in",
      field("iterable", $._expression),
      field("body", $.block),
    ),

    // while3 EXPR { } — NO parens required
    while_statement: $ => seq(
      choice("while3", "while"),
      field("condition", $._expression),
      field("body", $.block),
      optional(seq("maybe", field("maybe_body", $.block))),
      optional(seq("done3", field("done_body", $.block))),
    ),

    // try3 { } fail { } OR try3 { } uncertain { } fail { }
    try_statement: $ => seq(
      "try3",
      field("body", $.block),
      optional(seq("uncertain", field("uncertain_body", $.block))),
      choice(
        seq("fail", optional(seq("(", $.identifier, ")")), field("fail_body", $.block)),
        seq("catch3", optional(seq("(", $.identifier, ")")), field("fail_body", $.block)),
      ),
    ),

    match_statement: $ => seq(
      "match3",
      field("subject", $._expression),
      "{",
      repeat($.match_arm),
      "}",
    ),

    match_arm: $ => seq(
      field("pattern", $._expression),
      "=>",
      field("value", choice($.block, $._expression)),
      optional(","),
    ),

    import_statement: $ => seq(
      "import3",
      field("path", choice($.string, $.identifier)),
      optional(";"),
    ),

    return_statement: $ => seq(
      "return",
      optional($._expression),
      optional(";"),
    ),

    break_statement: $ => seq("break3", optional(";")),
    continue_statement: $ => seq("continue3", optional(";")),

    expression_statement: $ => seq(
      $._expression,
      optional(";"),
    ),

    // ── Expressions ────────────────────────────────────────
    _expression: $ => choice(
      $.binary_expression,
      $.unary_expression,
      $.assignment_expression,
      $.call_expression,
      $.member_expression,
      $.index_expression,
      $.new_expression,
      $.arrow_function,
      $.parenthesized_expression,
      $.array_literal,
      $.object_literal,
      $.identifier,
      $.number,
      $.string,
      $.ternary_constant,
      $.null_literal,
    ),

    binary_expression: $ => {
      const table = [
        [1, choice("or", "OR", "||")],
        [2, choice("and", "AND", "&&")],
        [3, choice("==", "!=")],
        [4, choice("<", ">", "<=", ">=")],
        [5, choice("+", "-")],
        [6, choice("*", "/", "%")],
      ];
      return choice(
        ...table.map(([precedence, operator]) =>
          prec.left(precedence, seq(
            field("left", $._expression),
            field("operator", operator),
            field("right", $._expression),
          ))
        )
      );
    },

    unary_expression: $ => prec(7, seq(
      field("operator", choice("-", "not", "NOT", "!")),
      field("operand", $._expression),
    )),

    assignment_expression: $ => prec.right(0, seq(
      field("left", choice($.identifier, $.member_expression, $.index_expression)),
      field("operator", choice("=", "+=", "-=", "*=", "/=")),
      field("right", $._expression),
    )),

    call_expression: $ => prec(8, seq(
      field("function", choice($.identifier, $.member_expression)),
      "(",
      optional($.argument_list),
      ")",
    )),

    argument_list: $ => seq(
      $._expression,
      repeat(seq(",", $._expression)),
    ),

    member_expression: $ => prec.left(9, seq(
      field("object", $._expression),
      ".",
      field("property", $.identifier),
    )),

    index_expression: $ => prec.left(9, seq(
      field("object", $._expression),
      "[",
      field("index", $._expression),
      "]",
    )),

    new_expression: $ => prec(8, seq(
      "new3",
      field("class", $.identifier),
      "(",
      optional($.argument_list),
      ")",
    )),

    arrow_function: $ => prec.right(0, seq(
      "(",
      optional($.parameter_list),
      ")",
      "=>",
      choice($.block, $._expression),
    )),

    parenthesized_expression: $ => seq("(", $._expression, ")"),

    array_literal: $ => seq(
      "[",
      optional(seq($._expression, repeat(seq(",", $._expression)), optional(","))),
      "]",
    ),

    object_literal: $ => seq(
      "{",
      optional(seq($.object_entry, repeat(seq(",", $.object_entry)), optional(","))),
      "}",
    ),

    object_entry: $ => seq(
      field("key", choice($.identifier, $.string)),
      ":",
      field("value", $._expression),
    ),

    block: $ => seq("{", repeat($._statement), "}"),

    // ── Literals & atoms ───────────────────────────────────
    ternary_constant: $ => choice(
      "true", "TRUE", "T_TRUE",
      "false", "FALSE_", "T_FALSE",
      "maybe", "MAYBE", "T_MAYBE",
    ),

    null_literal: $ => "null",

    number: $ => token(choice(
      // Float with optional underscore separators
      /\-?[0-9][0-9_]*\.[0-9][0-9_]*/,
      // Integer with optional underscore separators
      /\-?[0-9][0-9_]*/,
    )),

    string: $ => choice(
      // Double-quoted strings with escape sequences
      seq(
        '"',
        repeat(choice(
          token.immediate(/[^"\\]+/),
          $.escape_sequence,
        )),
        '"',
      ),
      // Single-quoted strings
      seq(
        "'",
        repeat(choice(
          token.immediate(/[^'\\]+/),
          $.escape_sequence,
        )),
        "'",
      ),
    ),

    escape_sequence: $ => token.immediate(
      /\\[ntr0\\"']/
    ),

    identifier: $ => /[a-zA-Z_][a-zA-Z0-9_]*/,

    // ── Comments ───────────────────────────────────────────
    comment: $ => token(choice(
      seq("//", /[^\n]*/),
      seq("#", /[^\n]*/),
    )),
  },
});
