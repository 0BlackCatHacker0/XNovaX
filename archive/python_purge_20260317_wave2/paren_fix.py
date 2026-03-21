"""
Fix unbalanced parentheses and brackets in .nova files.
Strategy: Track depth per-line, find lines that open without closing,
and append the missing closer at end of line.
"""
import re, sys

def strip_strings_comments(line):
    """Remove string contents and comments for structural analysis."""
    # Strip comments first
    result = line
    cp = -1
    in_str = False
    for ci, ch in enumerate(result):
        if ch == '"' and (ci == 0 or result[ci-1] != '\\'):
            in_str = not in_str
        elif ch == '/' and ci + 1 < len(result) and result[ci+1] == '/' and not in_str:
            cp = ci
            break
        elif ch == '#' and not in_str:
            cp = ci
            break
    if cp >= 0:
        result = result[:cp]
    # Strip string contents
    result = re.sub(r'"[^"]*"', '""', result)
    return result

def fix_parens(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    fixes = 0

    # Find lines with unclosed parens (opened but not closed on same line)
    # that contribute to overall imbalance
    total_delta_p = 0
    total_delta_b = 0
    for line in lines:
        clean = strip_strings_comments(line)
        total_delta_p += clean.count("(") - clean.count(")")
        total_delta_b += clean.count("[") - clean.count("]")

    if total_delta_p == 0 and total_delta_b == 0:
        return 0

    # For positive delta (more openers): find lines that open but don't close
    # and append closers
    if total_delta_p > 0:
        needed = total_delta_p
        for i in range(len(lines) - 1, -1, -1):
            if needed <= 0:
                break
            clean = strip_strings_comments(lines[i])
            line_delta = clean.count("(") - clean.count(")")
            if line_delta > 0:
                # This line has unclosed parens — add closers
                add = min(line_delta, needed)
                lines[i] = lines[i].rstrip("\n") + ")" * add + "\n"
                needed -= add
                fixes += add

    # For negative delta (more closers): find lines with extra closers
    # and remove them
    if total_delta_p < 0:
        needed = abs(total_delta_p)
        for i in range(len(lines) - 1, -1, -1):
            if needed <= 0:
                break
            clean = strip_strings_comments(lines[i])
            line_delta = clean.count("(") - clean.count(")")
            if line_delta < 0 and lines[i].rstrip().endswith(")"):
                remove = min(abs(line_delta), needed)
                stripped = lines[i].rstrip("\n")
                lines[i] = stripped[:-remove] + "\n"
                needed -= remove
                fixes += remove

    # Same for brackets
    if total_delta_b > 0:
        needed = total_delta_b
        for i in range(len(lines) - 1, -1, -1):
            if needed <= 0:
                break
            clean = strip_strings_comments(lines[i])
            line_delta = clean.count("[") - clean.count("]")
            if line_delta > 0:
                add = min(line_delta, needed)
                lines[i] = lines[i].rstrip("\n") + "]" * add + "\n"
                needed -= add
                fixes += add

    if total_delta_b < 0:
        needed = abs(total_delta_b)
        for i in range(len(lines) - 1, -1, -1):
            if needed <= 0:
                break
            clean = strip_strings_comments(lines[i])
            line_delta = clean.count("[") - clean.count("]")
            if line_delta < 0 and lines[i].rstrip().endswith("]"):
                remove = min(abs(line_delta), needed)
                stripped = lines[i].rstrip("\n")
                lines[i] = stripped[:-remove] + "\n"
                needed -= remove
                fixes += remove

    if fixes > 0:
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.writelines(lines)

    return fixes


if __name__ == "__main__":
    targets = [
        "nova_bridge_v3_service.nova",
        "nova_tbuild_service.nova",
        "nova_thealth_service.nova",
        "nova_tmapper_service.nova",
        "nova_tshell_service.nova",
        "nova_tsniffer_service.nova",
    ]

    for fname in targets:
        path = f"C:\\NovaX\\{fname}"
        fixed = fix_parens(path)
        # Verify
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        dp = sum(strip_strings_comments(l).count("(") - strip_strings_comments(l).count(")") for l in lines)
        db = sum(strip_strings_comments(l).count("[") - strip_strings_comments(l).count("]") for l in lines)
        status = "OK" if dp == 0 and db == 0 else f"parens={dp} brackets={db}"
        print(f"{fname}: {fixed} fixes [{status}]")
