import re, sys, os

def find_matching_paren(text, start):
    depth = 1
    i = start + 1
    in_str = None
    while i < len(text) and depth > 0:
        c = text[i]
        if in_str:
            if c == in_str and (i == 0 or text[i-1] != '\\'):
                in_str = None
        elif c in ('"', "'"):
            in_str = c
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1

def split_args(text):
    args = []
    depth = 0
    in_str = None
    start = 0
    for i, c in enumerate(text):
        if in_str:
            if c == in_str and (i == 0 or text[i-1] != '\\'):
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

def is_in_string(text, pos):
    in_str = None
    for i in range(pos):
        c = text[i]
        if in_str:
            if c == in_str and (i == 0 or text[i-1] != '\\'):
                in_str = None
        elif c in ('"', "'"):
            in_str = c
    return in_str is not None

def convert_dict_get_line(line):
    result = []
    i = 0
    changes = 0
    while i < len(line):
        idx = line.find('dict_get(', i)
        if idx == -1:
            result.append(line[i:])
            break
        if is_in_string(line, idx):
            result.append(line[i:idx + 9])
            i = idx + 9
            continue
        result.append(line[i:idx])
        open_paren = idx + 8
        close_paren = find_matching_paren(line, open_paren)
        if close_paren == -1:
            result.append(line[idx:])
            break
        inner = line[open_paren + 1:close_paren]
        args = split_args(inner)
        if len(args) == 3:
            default_val = args[2]
            new_expr = 'dict_get(' + args[0] + ', ' + args[1] + ') ?? ' + default_val
            result.append(new_expr)
            changes += 1
        else:
            result.append(line[idx:close_paren + 1])
        i = close_paren + 1
    return ''.join(result), changes

def convert_control_flow(line):
    changes = 0
    stripped = line.lstrip()
    indent = line[:len(line) - len(stripped)]
    if stripped.startswith('#') or stripped.startswith('//'):
        return line, 0
    # bare if -> if3
    if re.match(r'^if\s+', stripped) and not stripped.startswith('if3'):
        line = indent + 'if3' + stripped[2:]
        changes += 1
        stripped = line.lstrip()
    # else if -> else3 if3
    m = re.match(r'^else\s+if\s+', stripped)
    if m and 'else3' not in stripped:
        line = indent + 'else3 if3' + stripped[len(m.group()):]
        changes += 1
        stripped = line.lstrip()
    # bare else { -> else3 {
    if re.match(r'^else\s*\{', stripped) and not stripped.startswith('else3'):
        line = indent + 'else3' + stripped[4:]
        changes += 1
        stripped = line.lstrip()
    # bare while -> while3
    if re.match(r'^while\s+', stripped) and not stripped.startswith('while3'):
        line = indent + 'while3' + stripped[5:]
        changes += 1
    # bare try -> try3
    if re.match(r'^try\s*\{', stripped) and not stripped.startswith('try3'):
        line = indent + 'try3' + stripped[3:]
        changes += 1
    # bare catch -> catch3
    if re.match(r'^catch\s', stripped) and not stripped.startswith('catch3'):
        line = indent + 'catch3' + stripped[5:]
        changes += 1
    # bare break
    if (re.match(r'^break\s*$', stripped) or re.match(r'^break\s*[#/]', stripped)):
        if not stripped.startswith('break3'):
            line = indent + 'break3' + stripped[5:]
            changes += 1
    # bare continue
    if (re.match(r'^continue\s*$', stripped) or re.match(r'^continue\s*[#/]', stripped)):
        if not stripped.startswith('continue3'):
            line = indent + 'continue3' + stripped[8:]
            changes += 1
    # bare for -> for3
    if re.match(r'^for\s+', stripped) and not stripped.startswith('for3'):
        line = indent + 'for3' + stripped[3:]
        changes += 1
    return line, changes

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    new_lines = []
    total_dg = 0
    total_cf = 0
    for line in lines:
        current = line.rstrip('\n')
        prev = None
        line_dg = 0
        while current != prev:
            prev = current
            current, changes = convert_dict_get_line(current)
            line_dg += changes
        total_dg += line_dg
        current, cf_changes = convert_control_flow(current)
        total_cf += cf_changes
        new_lines.append(current + '\n')
    if total_dg > 0 or total_cf > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
    return total_dg, total_cf

root = r'C:\NovaX'
total_files = 0
total_dg_all = 0
total_cf_all = 0

for dirpath, dirs, files in os.walk(root):
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
        try:
            dg, cf = process_file(fpath)
            if dg > 0 or cf > 0:
                print(f'{fname}: {dg} dict_get + {cf} control_flow')
                total_files += 1
                total_dg_all += dg
                total_cf_all += cf
        except Exception as e:
            print(f'ERROR {fname}: {e}')

print(f'\n=== TOTAL: {total_files} files, {total_dg_all} dict_get, {total_cf_all} control_flow ===')
