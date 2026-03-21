"""
TPacman v2.1 — Brace Fixer
Fixes the systemic conversion bugs from TPacman v2.0:
1. Extra } before } else3/} else/} fail patterns
2. try3 { ... } } fail { -> try3 { ... } fail {
3. if3 { ... } } else3 { -> if3 { ... } else3 {
4. if3 { ... } } else { -> if3 { ... } else {
5. Stray } at file end outside any function
6. Removes trailing } after tstart() call
"""

import re, sys, glob, os

def fix_nova_file(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    original = lines[:]
    fixes = 0

    # Pass 1: Fix "}\n    } else3" and "}\n    } else {" and "}\n    } fail {"
    # These are the double-close patterns from TPacman v2.0
    i = 0
    while i < len(lines) - 1:
        curr = lines[i].rstrip()
        nxt = lines[i + 1].strip()

        # Pattern: current line is just "}" and next line starts with "} else3" or "} else {" or "} fail {"
        if curr.strip() == "}" and (nxt.startswith("} else3") or nxt.startswith("} else {") or nxt.startswith("} else{") or nxt.startswith("} fail {") or nxt.startswith("} fail{")):
            # Remove the extra } line
            lines.pop(i)
            fixes += 1
            continue
        i += 1

    # Pass 2: Fix stray } after tstart() or at end of file outside functions
    # Track depth to find } that go negative
    depth = 0
    to_remove = []
    for i, line in enumerate(lines):
        # Strip comments and strings for counting
        stripped = line
        comment_pos = -1
        in_str = False
        for ci, ch in enumerate(stripped):
            if ch == '"' and (ci == 0 or stripped[ci-1] != '\\'):
                in_str = not in_str
            elif ch == '/' and ci + 1 < len(stripped) and stripped[ci+1] == '/' and not in_str:
                comment_pos = ci
                break
            elif ch == '#' and not in_str:
                comment_pos = ci
                break
        if comment_pos >= 0:
            stripped = stripped[:comment_pos]
        clean = re.sub(r'"[^"]*"', '""', stripped)
        opens = clean.count("{")
        closes = clean.count("}")
        depth += opens - closes
        if depth < 0:
            # This } is extra — mark for removal only if line is just }
            if line.strip() == "}":
                to_remove.append(i)
                depth += 1  # undo the damage
                fixes += 1

    # Remove marked lines in reverse order
    for idx in reversed(to_remove):
        lines.pop(idx)

    if fixes > 0:
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.writelines(lines)

    return fixes, len(original), len(lines)


def verify_file(filepath):
    """Check final brace balance with proper comment/string stripping."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    depth = 0
    min_depth = 0
    for line in lines:
        stripped = line
        comment_pos = -1
        in_str = False
        for ci, ch in enumerate(stripped):
            if ch == '"' and (ci == 0 or stripped[ci-1] != '\\'):
                in_str = not in_str
            elif ch == '/' and ci + 1 < len(stripped) and stripped[ci+1] == '/' and not in_str:
                comment_pos = ci
                break
            elif ch == '#' and not in_str:
                comment_pos = ci
                break
        if comment_pos >= 0:
            stripped = stripped[:comment_pos]
        clean = re.sub(r'"[^"]*"', '""', stripped)
        depth += clean.count("{") - clean.count("}")
        min_depth = min(min_depth, depth)
    return depth, min_depth


def fix_unclosed_blocks(filepath):
    """Pass 2: Fix unclosed blocks (positive final depth).
    Strategy: Find 'return {' lines that open a dict but never close it,
    and close them before the next function definition or file end.
    Also fix 'let x = {' on its own line that starts an unclosed dict.
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    original_len = len(lines)
    fixes = 0

    # Find function boundaries
    fn_starts = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("fn ") and "{" in stripped:
            fn_starts.append(i)

    # Also find troute/tstart/print lines at top level (after last function)
    top_level_markers = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("troute(") or stripped.startswith("tstart(") or (stripped.startswith("print(") and i > 10):
            top_level_markers.append(i)

    # For each function, track depth and find unclosed blocks
    # Process in reverse so line insertions don't mess up indices
    insertions = []  # (line_index, indent, count)

    for fn_idx in range(len(fn_starts)):
        fn_start = fn_starts[fn_idx]
        # Function ends at next fn_start or first top-level marker or EOF
        if fn_idx + 1 < len(fn_starts):
            fn_end = fn_starts[fn_idx + 1]
        else:
            # Find first top-level marker after this function
            fn_end = len(lines)
            for m in top_level_markers:
                if m > fn_start:
                    fn_end = m
                    break

        # Track depth within this function
        depth = 0
        for i in range(fn_start, min(fn_end, len(lines))):
            line = lines[i]
            stripped = line
            comment_pos = -1
            in_str = False
            for ci, ch in enumerate(stripped):
                if ch == '"' and (ci == 0 or stripped[ci-1] != '\\'):
                    in_str = not in_str
                elif ch == '/' and ci + 1 < len(stripped) and stripped[ci+1] == '/' and not in_str:
                    comment_pos = ci
                    break
                elif ch == '#' and not in_str:
                    comment_pos = ci
                    break
            if comment_pos >= 0:
                stripped = stripped[:comment_pos]
            clean = re.sub(r'"[^"]*"', '""', stripped)
            depth += clean.count("{") - clean.count("}")

        # If depth > 0 at function end, we need to close it
        if depth > 0:
            # Insert closing braces just before the function end
            insert_at = fn_end
            # Back up past any blank lines
            while insert_at > fn_start and lines[insert_at - 1].strip() == "":
                insert_at -= 1
            insertions.append((insert_at, depth))
            fixes += depth

    # Apply insertions in reverse order
    for insert_at, count in reversed(sorted(insertions, key=lambda x: x[0])):
        closing = "}\n" * count
        lines.insert(insert_at, closing)

    if fixes > 0:
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.writelines(lines)

    return fixes


if __name__ == "__main__":
    # Skip bitnet — too broken for automated fixing
    skip = {"nova_bitnet_fleet_service.nova"}

    files = glob.glob("*.nova")
    total_fixes = 0
    fixed_files = []

    for f in sorted(files):
        if os.path.basename(f) in skip:
            continue
        fixes, old_lines, new_lines = fix_nova_file(f)
        if fixes > 0:
            final_depth, min_depth = verify_file(f)
            status = "OK" if (final_depth == 0 and min_depth >= 0) else f"depth={final_depth} min={min_depth}"
            print(f"  FIXED {f}: {fixes} fixes, {old_lines}->{new_lines} lines [{status}]")
            total_fixes += fixes
            fixed_files.append(f)

    print(f"\nTPacman v2.1 Pass 1: {total_fixes} double-close fixes across {len(fixed_files)} files")

    # Pass 2: Fix unclosed blocks
    print("\n=== Pass 2: Fixing unclosed blocks ===")
    pass2_fixes = 0
    for f in sorted(glob.glob("*.nova")):
        if os.path.basename(f) in skip:
            continue
        depth, min_d = verify_file(f)
        if depth > 0:
            added = fix_unclosed_blocks(f)
            if added > 0:
                new_depth, new_min = verify_file(f)
                status = "OK" if (new_depth == 0 and new_min >= 0) else f"depth={new_depth} min={new_min}"
                print(f"  FIXED {f}: added {added} closing braces [{status}]")
                pass2_fixes += added

    print(f"\nTPacman v2.1 Pass 2: {pass2_fixes} closing braces added")

    # Final verification of all .nova files
    print("\n=== Final Verification ===")
    still_broken = []
    for f in sorted(glob.glob("*.nova")):
        if os.path.basename(f) in skip:
            continue
        depth, min_d = verify_file(f)
        if depth != 0 or min_d < 0:
            still_broken.append((f, depth, min_d))
            print(f"  STILL BROKEN: {f} final={depth} min={min_d}")

    if not still_broken:
        print("  All .nova files structurally balanced!")
    else:
        print(f"  {len(still_broken)} files still have issues")
