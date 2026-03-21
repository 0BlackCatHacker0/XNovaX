import re, sys, glob

files = sys.argv[1:] if len(sys.argv) > 1 else glob.glob("*.nova")

for fname in sorted(files):
    with open(fname, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    depth = 0
    min_depth = 0
    problems = []
    for i, line in enumerate(lines):
        # Strip comments first
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
        # Strip string contents
        clean = re.sub(r'"[^"]*"', '""', stripped)
        opens = clean.count("{")
        closes = clean.count("}")
        depth += opens - closes
        if depth < min_depth:
            min_depth = depth
            problems.append(f"  LINE {i+1}: depth={depth} | {line.rstrip()[:80]}")

    if depth != 0 or min_depth < 0:
        print(f"{fname}: final={depth} min={min_depth}")
        for p in problems[:3]:
            print(p)
        print()
