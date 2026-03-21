; Tree-sitter highlight queries for NovaLang

; ── Comments ────────────────────────────────────────────
(comment) @comment

; ── Strings ─────────────────────────────────────────────
(string) @string
(escape_sequence) @string.escape

; ── Numbers ─────────────────────────────────────────────
(number) @number

; ── Ternary constants ───────────────────────────────────
(ternary_constant) @constant.builtin
(null_literal) @constant.builtin

; ── Keywords ────────────────────────────────────────────
"let" @keyword
"const" @keyword
"fn" @keyword.function
"return" @keyword.return
"if3" @keyword.conditional
"else3" @keyword.conditional
"else" @keyword.conditional
"for3" @keyword.repeat
"while3" @keyword.repeat
"try3" @keyword.exception
"catch3" @keyword.exception
"fail" @keyword.exception
"match3" @keyword.conditional
"break3" @keyword.repeat
"continue3" @keyword.repeat
"import3" @keyword.import
"class3" @keyword.type
"extends3" @keyword.type
"new3" @keyword.operator
"in" @keyword

; ── Logical operators ───────────────────────────────────
"and" @keyword.operator
"AND" @keyword.operator
"or" @keyword.operator
"OR" @keyword.operator
"not" @keyword.operator
"NOT" @keyword.operator

; ── Operators ───────────────────────────────────────────
(binary_expression operator: _ @operator)
(unary_expression operator: _ @operator)
(assignment_expression operator: _ @operator)
"=>" @operator

; ── Punctuation ─────────────────────────────────────────
"(" @punctuation.bracket
")" @punctuation.bracket
"{" @punctuation.bracket
"}" @punctuation.bracket
"[" @punctuation.bracket
"]" @punctuation.bracket
"," @punctuation.delimiter
";" @punctuation.delimiter
":" @punctuation.delimiter
"." @punctuation.delimiter

; ── Functions ───────────────────────────────────────────
(function_declaration name: (identifier) @function)
(call_expression function: (identifier) @function.call)
(call_expression function: (member_expression property: (identifier) @function.method))

; ── Classes ─────────────────────────────────────────────
(class_declaration name: (identifier) @type)
(class_declaration superclass: (identifier) @type)
(new_expression class: (identifier) @type)

; ── Parameters ──────────────────────────────────────────
(parameter_list (identifier) @variable.parameter)

; ── Variables ───────────────────────────────────────────
(variable_declaration name: (identifier) @variable)
(constant_declaration name: (identifier) @constant)
(member_expression property: (identifier) @property)

; ── Fallback identifier ─────────────────────────────────
(identifier) @variable
