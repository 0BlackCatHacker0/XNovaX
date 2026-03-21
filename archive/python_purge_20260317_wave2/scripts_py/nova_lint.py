"""
NovaLang Linter — tokenize-only lint check for .nova files.
Uses novalang.py's Lexer to tokenize each file and report errors.
Also checks for common conversion artifacts from TPacman.
"""
import sys, os, glob, re

# Add NovaX to path so we can import novalang
sys.path.insert(0, r"C:\NovaX")

from novalang import Lexer

NOVA_KEYWORDS = {
    "let", "fn", "return", "if3", "else3", "else", "for3", "while3",
    "try3", "fail", "catch3", "match3", "break3", "continue3", "import3",
    "class3", "extends3", "new3", "in", "true", "false", "null",
    "TRUE", "FALSE_", "MAYBE", "T_TRUE", "T_FALSE", "T_MAYBE",
}

PYTHON_ARTIFACTS = [
    (r'\bdef\s+\w+\s*\(', "Python 'def' instead of 'fn'"),
    (r'\bself\.\w+', "Python 'self.' reference"),
    (r'\bNone\b', "Python 'None' (use null)"),
    (r'\bTrue\b(?!_)', "Python 'True' (use true or TRUE)"),
    (r'\bFalse\b(?!_)', "Python 'False' (use false or FALSE_)"),
    (r'\bexcept\s', "Python 'except' (use fail/catch3)"),
    (r'\belif\s', "Python 'elif' (use else3)"),
    (r'\bprint\s*\(.*f"', "Python f-string in print"),
    (r'^\s*@\w+', "Python decorator"),
    (r'\bimport\s+\w+', "Python import (use import3)"),
    (r'\bfrom\s+\w+\s+import', "Python from-import"),
    (r'\bclass\s+\w+[^3]', "Python class (use class3)"),
    (r'\bfor\s+\w+\s+in\b', "Python for-in (use for3)"),
    (r'\bwhile\s+', "Python while (use while3)"),
    (r'\bif\s+[^3]', "Python if (use if3)"),
    (r'\btry\s*:', "Python try: (use try3)"),
]

def lint_file(filepath):
    """Lint a single .nova file. Returns list of (line, severity, message)."""
    issues = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        code = f.read()
        lines = code.split("\n")

    # 1. Tokenization check
    try:
        lexer = Lexer(code)
        tokens = lexer.tokenize()
    except Exception as e:
        issues.append((0, "ERROR", f"Tokenization failed: {e}"))
        return issues

    # 2. Python artifact check (only outside strings and comments)
    for i, line in enumerate(lines):
        # Skip comments
        stripped = line.lstrip()
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        # Strip string content for checking
        clean = re.sub(r'"[^"]*"', '""', line)
        clean = re.sub(r"'[^']*'", "''", clean)

        for pattern, msg in PYTHON_ARTIFACTS:
            if re.search(pattern, clean):
                issues.append((i + 1, "WARN", msg))
                break  # One warning per line max

    # 3. Check for unclosed parens/brackets per line
    paren_depth = 0
    bracket_depth = 0
    for i, line in enumerate(lines):
        clean = re.sub(r'"[^"]*"', '""', line)
        # Strip comments
        cp = -1
        ins = False
        for ci, ch in enumerate(clean):
            if ch == '"' and (ci == 0 or clean[ci-1] != '\\'):
                ins = not ins
            elif ch == '/' and ci + 1 < len(clean) and clean[ci+1] == '/' and not ins:
                cp = ci
                break
            elif ch == '#' and not ins:
                cp = ci
                break
        if cp >= 0:
            clean = clean[:cp]

        paren_depth += clean.count("(") - clean.count(")")
        bracket_depth += clean.count("[") - clean.count("]")

    if paren_depth != 0:
        issues.append((0, "ERROR", f"Unbalanced parentheses: delta={paren_depth}"))
    if bracket_depth != 0:
        issues.append((0, "ERROR", f"Unbalanced brackets: delta={bracket_depth}"))

    # 4. Check for empty function bodies
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("fn ") and stripped.endswith("{"):
            if i + 1 < len(lines) and lines[i + 1].strip() == "}":
                issues.append((i + 1, "WARN", "Empty function body"))

    return issues


if __name__ == "__main__":
    skip = {"nova_bitnet_fleet_service.nova"}

    files = sorted(glob.glob(r"C:\NovaX\*.nova"))

    total_errors = 0
    total_warns = 0
    clean_files = 0
    error_files = []

    for fpath in files:
        fname = os.path.basename(fpath)
        if fname in skip:
            continue

        issues = lint_file(fpath)
        errors = [x for x in issues if x[1] == "ERROR"]
        warns = [x for x in issues if x[1] == "WARN"]

        if errors:
            print(f"FAIL {fname}: {len(errors)} errors, {len(warns)} warnings")
            for line, sev, msg in errors[:5]:
                print(f"  L{line}: [{sev}] {msg}")
            error_files.append(fname)
            total_errors += len(errors)
        elif warns:
            # Only show warning count, not details (too noisy)
            total_warns += len(warns)
        else:
            clean_files += 1

        total_warns += len(warns)

    print(f"\n{'='*60}")
    print(f"NovaLang Lint Results:")
    print(f"  Files scanned: {len(files) - len(skip)}")
    print(f"  Clean: {clean_files}")
    print(f"  With errors: {len(error_files)}")
    print(f"  Total errors: {total_errors}")
    print(f"  Total warnings: {total_warns}")
    if error_files:
        print(f"\nFiles with errors:")
        for f in error_files:
            print(f"  - {f}")
