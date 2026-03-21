import os

def find_matching_paren(text, start):
    depth = 1
    i = start + 1
    in_str = None
    while i < len(text) and depth > 0:
        c = text[i]
        if in_str:
            if c == in_str and (i == 0 or text[i-1] != chr(92)):
                in_str = None
        elif c in ('"', "'"):
            in_str = c
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        i += 1
    return i - 1 if depth == 0 else -1

def split_args(text):
    args = []
    depth = 0
    in_str = None
    start = 0
    for i, c in enumerate(text):
        if in_str:
            if c == in_str and (i == 0 or text[i-1] != chr(92)):
                in_str = None
        elif c in ('"', "'"):
            in_str = c
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == ',' and depth == 0:
            args.append(text[start:i].strip())
            start = i + 1
    args.append(text[start:].strip())
    return args

total = 0
for dirpath, dirs, files in os.walk(r'C:\NovaX'):
    skip = False
    for skip_dir in ['__pycache__', '.git', 'node_modules', 'ai_env']:
        if skip_dir in dirpath:
            skip = True
    if skip:
        continue
    for fname in sorted(files):
        if not fname.endswith('.nova'):
            continue
        fpath = os.path.join(dirpath, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        count = 0
        i = 0
        while True:
            idx = content.find('dict_get(', i)
            if idx == -1:
                break
            open_p = idx + 8
            close_p = find_matching_paren(content, open_p)
            if close_p == -1:
                i = idx + 9
                continue
            inner = content[open_p + 1:close_p]
            args = split_args(inner)
            if len(args) == 3:
                count += 1
            i = close_p + 1
        if count > 0:
            print(f'{fname}: {count}')
            total += count
print(f'\nTOTAL REAL 3-arg dict_get remaining: {total}')
