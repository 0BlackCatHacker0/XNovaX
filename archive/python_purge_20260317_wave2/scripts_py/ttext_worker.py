#!/usr/bin/env python3
"""TText worker — handles text processing operations for the TText NovaLang service.
Called by nova_run() from ttext service. Each operation reads from temp files.
Returns JSON: {ok: bool, result: ..., ...}
"""
import json, re, sys, os

def cmd_sed(args):
    """sed: regex find/replace. args: input_path pattern replacement [count]"""
    path, pattern, replacement = args[0], args[1], args[2]
    count = int(args[3]) if len(args) > 3 and args[3] != '0' else 0
    text = open(path, 'r', encoding='utf-8').read()
    if count > 0:
        result = re.sub(pattern, replacement, text, count=count)
    else:
        result = re.sub(pattern, replacement, text)
    replacements = len(re.findall(pattern, text))
    return {"ok": True, "result": result, "replacements": replacements}

def cmd_awk(args):
    """awk: field extraction. args: input_path params_path"""
    path, params_path = args[0], args[1]
    params = json.load(open(params_path, 'r', encoding='utf-8'))
    text = open(path, 'r', encoding='utf-8').read()
    delim = params.get('delimiter', ' ')
    fields = params.get('fields', [])
    lines = text.strip().split('\n')
    out_lines = []
    for line in lines:
        parts = line.split(delim) if delim != ' ' else line.split()
        if not fields:
            out_lines.append(delim.join(parts))
        else:
            selected = []
            for f in fields:
                idx = int(f)
                if 0 <= idx < len(parts):
                    selected.append(parts[idx])
            out_lines.append(delim.join(selected))
    return {"ok": True, "result": '\n'.join(out_lines), "lines": len(out_lines)}

def cmd_jq(args):
    """jq: JSON path query. args: input_path path"""
    path, jq_path = args[0], args[1]
    data = json.load(open(path, 'r', encoding='utf-8'))
    # Simple path traversal: .key.subkey[0].field
    parts = []
    for seg in re.split(r'\.(?![^\[]*\])', jq_path.lstrip('.')):
        if not seg:
            continue
        # Handle array indexing: key[0]
        m = re.match(r'^(\w+)\[(\d+)\]$', seg)
        if m:
            parts.append(m.group(1))
            parts.append(int(m.group(2)))
        else:
            parts.append(seg)
    current = data
    for p in parts:
        if isinstance(p, int):
            if isinstance(current, list) and 0 <= p < len(current):
                current = current[p]
            else:
                return {"ok": False, "error": f"index {p} out of range"}
        elif isinstance(current, dict):
            if p in current:
                current = current[p]
            else:
                return {"ok": False, "error": f"key '{p}' not found"}
        else:
            return {"ok": False, "error": f"cannot traverse '{p}' on {type(current).__name__}"}
    return {"ok": True, "result": current}

def cmd_sort(args):
    """sort: sort lines. args: input_path [flags: r=reverse, n=numeric]"""
    path = args[0]
    flags = args[1] if len(args) > 1 else ''
    text = open(path, 'r', encoding='utf-8').read()
    lines = text.strip().split('\n')
    reverse = 'r' in flags
    numeric = 'n' in flags
    if numeric:
        def sort_key(x):
            try: return float(x.strip())
            except: return float('inf')
        lines.sort(key=sort_key, reverse=reverse)
    else:
        lines.sort(reverse=reverse)
    return {"ok": True, "result": '\n'.join(lines), "lines": len(lines)}

def cmd_uniq(args):
    """uniq: deduplicate lines. args: input_path [flags: c=count]"""
    path = args[0]
    flags = args[1] if len(args) > 1 else ''
    text = open(path, 'r', encoding='utf-8').read()
    lines = text.strip().split('\n')
    total = len(lines)
    if 'c' in flags:
        counts = {}
        for line in lines:
            counts[line] = counts.get(line, 0) + 1
        result_lines = [f"{v}\t{k}" for k, v in counts.items()]
        return {"ok": True, "result": '\n'.join(result_lines), "unique": len(counts), "total": total}
    else:
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        return {"ok": True, "result": '\n'.join(unique_lines), "unique": len(unique_lines), "total": total}

def cmd_count(args):
    """count: word/line/char count. args: input_path"""
    path = args[0]
    text = open(path, 'r', encoding='utf-8').read()
    lines = text.count('\n') + (1 if text and not text.endswith('\n') else 0)
    words = len(text.split())
    chars = len(text)
    return {"ok": True, "lines": lines, "words": words, "chars": chars}

def cmd_grep(args):
    """grep: regex search. args: input_path pattern"""
    path, pattern = args[0], args[1]
    text = open(path, 'r', encoding='utf-8').read()
    lines = text.split('\n')
    matched = []
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            matched.append({"line": i + 1, "text": line})
    return {"ok": True, "result": '\n'.join(m['text'] for m in matched),
            "matches": len(matched), "matched_lines": matched}

if __name__ == '__main__':
    op = sys.argv[1]
    args = sys.argv[2:]
    try:
        ops = {'sed': cmd_sed, 'awk': cmd_awk, 'jq': cmd_jq,
               'sort': cmd_sort, 'uniq': cmd_uniq, 'count': cmd_count, 'grep': cmd_grep}
        if op in ops:
            print(json.dumps(ops[op](args)))
        else:
            print(json.dumps({"ok": False, "error": f"unknown op: {op}"}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
