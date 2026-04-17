"""
AGGRESSIVE CODE MINER - Extract training pairs from ALL source files.
Goes deeper than previous miner: docstrings, comments, imports, patterns.
Target: 5,000+ pairs from the codebase.
Writes to: C:/NovaX/data/llm_training/pairs_codemined.json
"""
import json
import os
import re
import random

random.seed(456)
OUTPUT = "C:/NovaX/data/llm_training/pairs_codemined.json"
NOVAX_ROOT = "C:/NovaX"
pairs = []
seen_prompts = set()

def add(prompt, response, domain):
    key = prompt.strip().lower()[:200]
    if key in seen_prompts:
        return
    if len(prompt.strip()) < 15 or len(response.strip()) < 30:
        return
    seen_prompts.add(key)
    pairs.append({
        "prompt": prompt.strip(),
        "response": response.strip(),
        "domain": f"codemined_{domain}",
        "provider": "code_miner_v2",
        "model": "miner_v2"
    })

def find_files(root, extensions):
    """Walk directory and find source files."""
    results = []
    skip_dirs = {'node_modules', '.git', 'ai_env', '__pycache__', 'target',
                 'checkpoints', 'checkpoints_v1_backup', '.claude', 'dist', 'build'}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for f in filenames:
            if any(f.endswith(ext) for ext in extensions):
                results.append(os.path.join(dirpath, f))
    return results

# ============================================================
# 1. PYTHON FILES
# ============================================================
print("[1/4] Mining Python files...")

py_files = find_files(NOVAX_ROOT, ['.py'])
print(f"  Found {len(py_files)} Python files")

for filepath in py_files:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        continue

    rel_path = os.path.relpath(filepath, NOVAX_ROOT).replace('\\', '/')
    lines = content.split('\n')

    # Extract functions with docstrings
    func_pattern = re.compile(r'^((?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)):', re.MULTILINE)
    for match in func_pattern.finditer(content):
        signature = match.group(1)
        func_name = match.group(2)
        params = match.group(3)

        if func_name.startswith('_') and not func_name.startswith('__'):
            continue  # Skip private helpers

        # Get function body (next 30 lines max)
        start_pos = match.end()
        body_lines = content[start_pos:start_pos+2000].split('\n')[:30]
        body = '\n'.join(body_lines)

        # Check for docstring
        docstring = ""
        ds_match = re.match(r'\s*"""(.*?)"""', body, re.DOTALL)
        if not ds_match:
            ds_match = re.match(r"\s*'''(.*?)'''", body, re.DOTALL)
        if ds_match:
            docstring = ds_match.group(1).strip()

        # Generate pairs
        add(f"What does the function `{func_name}` in {rel_path} do?",
            f"The function `{func_name}({params})` in `{rel_path}`{': ' + docstring if docstring else ''}.\n\nSignature: `{signature}`\n\nImplementation:\n```python\n{signature}:\n{chr(10).join(body_lines[:15])}\n```",
            "python_func")

        if params and params.strip():
            param_list = [p.strip().split(':')[0].split('=')[0].strip()
                         for p in params.split(',') if p.strip()]
            param_list = [p for p in param_list if p not in ('self', 'cls')]
            if param_list:
                add(f"What parameters does `{func_name}` accept?",
                    f"The function `{func_name}` in `{rel_path}` accepts these parameters: {', '.join(param_list)}.\n\nFull signature: `{signature}`",
                    "python_params")

    # Extract class definitions
    class_pattern = re.compile(r'^class\s+(\w+)\s*(?:\(([^)]*)\))?\s*:', re.MULTILINE)
    for match in class_pattern.finditer(content):
        class_name = match.group(1)
        parents = match.group(2) or ""

        # Get class body first 20 lines
        start_pos = match.end()
        body = content[start_pos:start_pos+1500].split('\n')[:20]
        body_text = '\n'.join(body)

        # Check for class docstring
        docstring = ""
        ds_match = re.match(r'\s*"""(.*?)"""', body_text, re.DOTALL)
        if ds_match:
            docstring = ds_match.group(1).strip()

        # Find methods
        methods = re.findall(r'def\s+(\w+)\s*\(', body_text)

        add(f"Describe the class `{class_name}` in {rel_path}.",
            f"The class `{class_name}`{f' (inherits from {parents})' if parents else ''} in `{rel_path}`{': ' + docstring if docstring else ''}.\n\nMethods: {', '.join(methods) if methods else 'see implementation'}.\n\n```python\nclass {class_name}({parents}):\n{chr(10).join(body[:10])}\n```",
            "python_class")

    # Extract imports as dependency knowledge
    imports = re.findall(r'^(?:from\s+([\w.]+)\s+)?import\s+([\w., ]+)', content, re.MULTILINE)
    if imports:
        import_list = []
        for from_mod, imp in imports:
            if from_mod:
                import_list.append(f"from {from_mod} import {imp}")
            else:
                import_list.append(f"import {imp}")
        if len(import_list) >= 3:
            add(f"What dependencies does {rel_path} use?",
                f"The file `{rel_path}` uses these imports:\n" + '\n'.join(f"- `{i}`" for i in import_list[:15]),
                "python_deps")

    # Extract constants and config
    const_pattern = re.compile(r'^([A-Z][A-Z_0-9]+)\s*=\s*(.+)$', re.MULTILINE)
    consts = const_pattern.findall(content)
    if consts:
        for name, value in consts[:5]:
            value = value.strip()[:200]
            add(f"What is the constant `{name}` in {rel_path}?",
                f"In `{rel_path}`, `{name}` is defined as: `{name} = {value}`",
                "python_const")

    # Extract error handling patterns
    try_blocks = re.findall(r'try:\s*\n(.*?)except\s+(\w+)', content, re.DOTALL)
    for body_block, exc_type in try_blocks[:3]:
        body_short = body_block.strip()[:200]
        add(f"How does {rel_path} handle {exc_type} errors?",
            f"In `{rel_path}`, the code handles `{exc_type}` exceptions:\n```python\ntry:\n{body_short}\nexcept {exc_type}:\n    ...\n```",
            "python_errors")

py_count = len(pairs)
print(f"  Python pairs: {py_count}")

# ============================================================
# 2. JAVASCRIPT FILES
# ============================================================
print("[2/4] Mining JavaScript files...")

js_files = find_files(NOVAX_ROOT, ['.js'])
print(f"  Found {len(js_files)} JavaScript files")

for filepath in js_files:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        continue

    rel_path = os.path.relpath(filepath, NOVAX_ROOT).replace('\\', '/')
    if len(content) < 100:
        continue

    # Extract functions
    func_patterns = [
        re.compile(r'(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)'),
        re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>'),
        re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function\s*\(([^)]*)\)'),
    ]

    for pattern in func_patterns:
        for match in pattern.finditer(content):
            func_name = match.group(1)
            params = match.group(2)

            if func_name.startswith('_'):
                continue

            # Get context (next 15 lines)
            start = match.end()
            body_lines = content[start:start+1000].split('\n')[:15]

            add(f"What does the JavaScript function `{func_name}` in {rel_path} do?",
                f"The function `{func_name}({params})` in `{rel_path}`.\n\n```javascript\nfunction {func_name}({params}) {{\n{chr(10).join(body_lines[:10])}\n```",
                "js_func")

    # Extract Express/Fastify routes
    route_pattern = re.compile(r"(?:app|router|server)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]")
    for match in route_pattern.finditer(content):
        method = match.group(1).upper()
        path = match.group(2)
        add(f"What does the {method} {path} endpoint in {rel_path} do?",
            f"In `{rel_path}`, there is a {method} endpoint at `{path}`. This handles {method} requests to the {path} route.",
            "js_routes")

    # Extract JSDoc comments
    jsdoc_pattern = re.compile(r'/\*\*\s*\n(.*?)\*/\s*\n\s*(?:async\s+)?(?:function\s+)?(\w+)', re.DOTALL)
    for match in jsdoc_pattern.finditer(content):
        doc = match.group(1).strip()
        func = match.group(2)
        doc_clean = re.sub(r'\s*\*\s*', ' ', doc).strip()[:300]
        add(f"What is the documentation for `{func}` in {rel_path}?",
            f"JSDoc for `{func}` in `{rel_path}`: {doc_clean}",
            "js_docs")

js_count = len(pairs) - py_count
print(f"  JavaScript pairs: {js_count}")

# ============================================================
# 3. NOVA FILES
# ============================================================
print("[3/4] Mining NovaLang files...")

nova_files = find_files(NOVAX_ROOT, ['.nova'])
print(f"  Found {len(nova_files)} NovaLang files")

for filepath in nova_files:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        continue

    rel_path = os.path.relpath(filepath, NOVAX_ROOT).replace('\\', '/')
    lines = content.split('\n')

    # Extract fn definitions
    fn_pattern = re.compile(r'fn\s+(\w+)\s*\(([^)]*)\)\s*\{')
    for match in fn_pattern.finditer(content):
        func_name = match.group(1)
        params = match.group(2)

        # Get body
        start = match.end()
        brace_count = 1
        end = start
        while end < len(content) and brace_count > 0:
            if content[end] == '{': brace_count += 1
            elif content[end] == '}': brace_count -= 1
            end += 1
        body = content[start:end-1][:500]

        add(f"What does the NovaLang function `{func_name}({params})` in {rel_path} do?",
            f"In NovaLang file `{rel_path}`, the function `{func_name}` takes parameters ({params}).\n\n```novalang\nfn {func_name}({params}) {{\n{body[:300]}\n}}\n```",
            "novalang_func")

    # Extract let declarations (service configs etc)
    let_pattern = re.compile(r'let\s+(\w+)\s*=\s*(.+)')
    for match in let_pattern.finditer(content):
        var_name = match.group(1)
        value = match.group(2).strip()[:200]
        if len(value) > 20:
            add(f"What is `{var_name}` defined as in {rel_path}?",
                f"In `{rel_path}`, the variable `{var_name}` is defined as:\n```novalang\nlet {var_name} = {value}\n```",
                "novalang_vars")

    # Extract if3/match3/try3 patterns
    for construct in ['if3', 'match3', 'try3', 'while3', 'for3']:
        if construct in content:
            # Find usage
            pattern = re.compile(rf'{construct}\s*\(([^)]*)\)\s*\{{')
            for match in pattern.finditer(content):
                arg = match.group(1)
                start = match.end()
                body = content[start:start+300]
                add(f"How is `{construct}` used in {rel_path}?",
                    f"In `{rel_path}`, `{construct}({arg})` is used:\n```novalang\n{construct}({arg}) {{\n{body[:200]}\n```\n\n{construct} is a core ternary control flow construct in NovaLang.",
                    "novalang_ternary")

    # File-level description
    if len(lines) > 10:
        first_comment = ""
        for line in lines[:5]:
            if line.strip().startswith('//') or line.strip().startswith('#'):
                first_comment += line.strip().lstrip('/#').strip() + " "
        if not first_comment:
            first_comment = f"NovaLang service/module"

        add(f"What does the NovaLang file {rel_path} do?",
            f"The file `{rel_path}` is a NovaLang source file ({len(lines)} lines). {first_comment.strip()}",
            "novalang_files")

nova_count = len(pairs) - py_count - js_count
print(f"  NovaLang pairs: {nova_count}")

# ============================================================
# 4. CONFIG/JSON FILES
# ============================================================
print("[4/4] Mining config files...")

config_files = find_files(NOVAX_ROOT, ['.json', '.toml', '.yaml', '.yml', '.ini', '.cfg'])
# Filter to just config-like files
config_files = [f for f in config_files if not any(x in f for x in
    ['package-lock', 'node_modules', 'training_pairs', 'factory_output',
     'target', '.git', 'checkpoint'])]

print(f"  Found {len(config_files)} config files")

for filepath in config_files[:100]:  # Limit
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()[:3000]
    except:
        continue

    rel_path = os.path.relpath(filepath, NOVAX_ROOT).replace('\\', '/')

    if filepath.endswith('.json'):
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                keys = list(data.keys())[:15]
                add(f"What configuration is in {rel_path}?",
                    f"The config file `{rel_path}` contains: {', '.join(keys)}.\n\nTop-level structure:\n```json\n{json.dumps({k: type(v).__name__ for k,v in list(data.items())[:10]}, indent=2)}\n```",
                    "config")
        except:
            pass

config_count = len(pairs) - py_count - js_count - nova_count
print(f"  Config pairs: {config_count}")

# ============================================================
# SAVE
# ============================================================
print(f"\n=== TOTAL CODE-MINED PAIRS: {len(pairs)} ===")

with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(pairs, f, ensure_ascii=False, indent=1)

print(f"Saved to {OUTPUT}")
