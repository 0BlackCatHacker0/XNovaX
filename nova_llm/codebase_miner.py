"""
NovaX Codebase Miner — Extract training pairs from 355K lines of source code.
Runs on CPU only. Does not interfere with GPU tasks.

Extracts:
  1. Function signature -> "What does this function do?" pairs
  2. Error handling blocks -> "What could go wrong?" pairs
  3. Config files -> "What does this setting do?" pairs
  4. Comments -> "Explain this code" pairs
  5. Class definitions -> "Describe this class" pairs
  6. Import blocks -> "What dependencies does this use?" pairs
  7. Contrastive pairs -> good code + deliberately broken version

Output: Appends to training_pairs_mega.json
"""

import os
import re
import ast
import json
import hashlib
import time
from pathlib import Path

NOVAX_ROOT = Path("C:/NovaX")
OUTPUT = NOVAX_ROOT / "data" / "llm_training" / "training_pairs_mega.json"
NOVA_FILES_DIR = NOVAX_ROOT

# Directories to skip
SKIP_DIRS = {
    "ai_env", "node_modules", ".git", "target", "browser",
    "tools", "data", "__pycache__", "checkpoints", "checkpoints_v1_backup",
    "super_archive", "archive", "site-packages"
}

# Load existing hashes for dedup
def load_existing_hashes():
    if OUTPUT.exists():
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        return {hashlib.md5((p.get("prompt","") + p.get("response","")).encode()).hexdigest() for p in data}
    return set()

def save_pairs(pairs):
    """Append pairs to the mega training file."""
    if not pairs:
        return 0
    existing = []
    if OUTPUT.exists():
        existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
    existing.extend(pairs)
    tmp = str(OUTPUT) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=True, indent=None)
    os.replace(tmp, str(OUTPUT))
    return len(pairs)

def hash_pair(prompt, response):
    return hashlib.md5((prompt + response).encode()).hexdigest()


# ============================================================
# PYTHON FILE MINERS
# ============================================================

def mine_python_functions(filepath, existing_hashes):
    """Extract function definitions with docstrings."""
    pairs = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except Exception:
        return pairs

    rel_path = str(Path(filepath).relative_to(NOVAX_ROOT))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if name.startswith("_") and name != "__init__":
                continue

            # Get function signature
            args = []
            for arg in node.args.args:
                args.append(arg.arg)
            sig = f"{name}({', '.join(args)})"

            # Get docstring if exists
            docstring = ast.get_docstring(node) or ""

            # Get the source lines for this function
            try:
                func_lines = source.split("\n")[node.lineno-1:node.end_lineno]
                func_source = "\n".join(func_lines)
            except Exception:
                func_source = f"def {sig}: ..."

            # Pair 1: What does this function do?
            prompt = f"What does the function `{sig}` in {rel_path} do?"
            if docstring:
                response = f"The function `{name}` {docstring}"
            else:
                response = f"The function `{name}` is defined in {rel_path}. Here is the implementation:\n\n```python\n{func_source[:800]}\n```"

            h = hash_pair(prompt, response)
            if h not in existing_hashes and len(response) > 50:
                pairs.append({
                    "prompt": prompt,
                    "response": response,
                    "domain": "codebase_function",
                    "source_file": rel_path,
                    "model": "codebase_miner"
                })
                existing_hashes.add(h)

            # Pair 2: How would you implement X?
            if len(func_source) > 100 and len(func_source) < 2000:
                prompt2 = f"Write a Python function called `{name}` that takes parameters ({', '.join(args)}). "
                if docstring:
                    prompt2 += docstring.split(".")[0] + "."
                response2 = f"```python\n{func_source}\n```"
                h2 = hash_pair(prompt2, response2)
                if h2 not in existing_hashes:
                    pairs.append({
                        "prompt": prompt2,
                        "response": response2,
                        "domain": "codebase_implementation",
                        "source_file": rel_path,
                        "model": "codebase_miner"
                    })
                    existing_hashes.add(h2)

    return pairs


def mine_python_classes(filepath, existing_hashes):
    """Extract class definitions."""
    pairs = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except Exception:
        return pairs

    rel_path = str(Path(filepath).relative_to(NOVAX_ROOT))

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            name = node.name
            docstring = ast.get_docstring(node) or ""
            bases = [getattr(b, 'id', getattr(b, 'attr', '?')) for b in node.bases]
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

            prompt = f"Describe the class `{name}` in {rel_path}."
            response = f"`{name}` is a class"
            if bases:
                response += f" inheriting from {', '.join(bases)}"
            response += f" defined in {rel_path}."
            if docstring:
                response += f" {docstring}"
            if methods:
                response += f" It has methods: {', '.join(methods[:10])}."

            h = hash_pair(prompt, response)
            if h not in existing_hashes and len(response) > 60:
                pairs.append({
                    "prompt": prompt,
                    "response": response,
                    "domain": "codebase_class",
                    "source_file": rel_path,
                    "model": "codebase_miner"
                })
                existing_hashes.add(h)

    return pairs


def mine_python_imports(filepath, existing_hashes):
    """Extract import patterns."""
    pairs = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except Exception:
        return pairs

    rel_path = str(Path(filepath).relative_to(NOVAX_ROOT))
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    if imports and len(imports) >= 3:
        prompt = f"What dependencies does {rel_path} use?"
        response = f"The file {rel_path} imports: {', '.join(sorted(set(imports)))}."
        h = hash_pair(prompt, response)
        if h not in existing_hashes:
            pairs.append({
                "prompt": prompt,
                "response": response,
                "domain": "codebase_imports",
                "source_file": rel_path,
                "model": "codebase_miner"
            })
            existing_hashes.add(h)

    return pairs


def mine_python_error_handling(filepath, existing_hashes):
    """Extract try/except patterns."""
    pairs = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except Exception:
        return pairs

    rel_path = str(Path(filepath).relative_to(NOVAX_ROOT))

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            try:
                try_lines = source.split("\n")[node.lineno-1:node.end_lineno]
                try_source = "\n".join(try_lines)
            except Exception:
                continue

            if len(try_source) < 50 or len(try_source) > 1500:
                continue

            # Extract exception types
            exceptions = []
            for handler in node.handlers:
                if handler.type:
                    exc_name = getattr(handler.type, 'id', getattr(handler.type, 'attr', 'Exception'))
                    exceptions.append(exc_name)

            prompt = f"What errors can occur in this code from {rel_path} and how are they handled?\n\n```python\n{try_source}\n```"
            response = f"This code handles the following errors: {', '.join(exceptions) if exceptions else 'general exceptions'}. "
            response += "The try block attempts the main operation, and the except block provides error recovery."

            h = hash_pair(prompt, response)
            if h not in existing_hashes:
                pairs.append({
                    "prompt": prompt,
                    "response": response,
                    "domain": "codebase_error_handling",
                    "source_file": rel_path,
                    "model": "codebase_miner"
                })
                existing_hashes.add(h)

    return pairs


# ============================================================
# NOVALANG FILE MINERS
# ============================================================

def mine_nova_functions(filepath, existing_hashes):
    """Extract NovaLang function definitions."""
    pairs = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return pairs

    rel_path = str(Path(filepath).relative_to(NOVAX_ROOT))

    # Match fn name(args) { ... }
    fn_pattern = re.compile(r'fn\s+(\w+)\s*\(([^)]*)\)\s*\{', re.MULTILINE)

    for match in fn_pattern.finditer(source):
        name = match.group(1)
        args = match.group(2).strip()
        pos = match.start()

        # Get surrounding context (up to 500 chars after the match)
        context = source[pos:pos+500]

        prompt = f"What does the NovaLang function `{name}({args})` in {rel_path} do?"
        response = f"The NovaLang function `{name}` takes parameters ({args}). Here is the implementation:\n\n```novalang\n{context[:400]}\n```"

        h = hash_pair(prompt, response)
        if h not in existing_hashes and len(response) > 60:
            pairs.append({
                "prompt": prompt,
                "response": response,
                "domain": "codebase_novalang",
                "source_file": rel_path,
                "model": "codebase_miner"
            })
            existing_hashes.add(h)

    return pairs


def mine_nova_routes(filepath, existing_hashes):
    """Extract NovaLang HTTP route definitions."""
    pairs = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return pairs

    rel_path = str(Path(filepath).relative_to(NOVAX_ROOT))

    # Match troute("METHOD", "/path", handler)
    route_pattern = re.compile(r'troute\s*\(\s*"(\w+)"\s*,\s*"([^"]+)"\s*,', re.MULTILINE)

    routes = []
    for match in route_pattern.finditer(source):
        method = match.group(1)
        path = match.group(2)
        routes.append(f"{method} {path}")

    if routes and len(routes) >= 2:
        prompt = f"What API endpoints does the NovaLang service in {rel_path} expose?"
        response = f"The service at {rel_path} exposes the following endpoints:\n" + "\n".join(f"- {r}" for r in routes)

        h = hash_pair(prompt, response)
        if h not in existing_hashes:
            pairs.append({
                "prompt": prompt,
                "response": response,
                "domain": "codebase_nova_routes",
                "source_file": rel_path,
                "model": "codebase_miner"
            })
            existing_hashes.add(h)

    return pairs


# ============================================================
# CONFIG FILE MINERS
# ============================================================

def mine_json_configs(filepath, existing_hashes):
    """Extract settings from JSON config files."""
    pairs = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        data = json.loads(source)
    except Exception:
        return pairs

    rel_path = str(Path(filepath).relative_to(NOVAX_ROOT))

    if not isinstance(data, dict):
        return pairs

    def flatten(d, prefix=""):
        items = []
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.extend(flatten(v, key))
            else:
                items.append((key, v))
        return items

    settings = flatten(data)
    if len(settings) < 2:
        return pairs

    prompt = f"What configuration settings are defined in {rel_path}?"
    response = f"The config file {rel_path} defines the following settings:\n"
    for key, val in settings[:20]:
        response += f"- `{key}`: {val}\n"

    h = hash_pair(prompt, response)
    if h not in existing_hashes and len(response) > 80:
        pairs.append({
            "prompt": prompt,
            "response": response,
            "domain": "codebase_config",
            "source_file": rel_path,
            "model": "codebase_miner"
        })
        existing_hashes.add(h)

    return pairs


# ============================================================
# RUST FILE MINERS
# ============================================================

def mine_rust_functions(filepath, existing_hashes):
    """Extract Rust function definitions."""
    pairs = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return pairs

    rel_path = str(Path(filepath).relative_to(NOVAX_ROOT))

    # Match pub fn name(...) -> RetType {
    fn_pattern = re.compile(r'(pub\s+)?fn\s+(\w+)\s*(<[^>]*>)?\s*\(([^)]*)\)(\s*->\s*[^{]+)?\s*\{', re.MULTILINE)

    for match in fn_pattern.finditer(source):
        is_pub = match.group(1) is not None
        name = match.group(2)
        args = match.group(4).strip()
        ret = (match.group(5) or "").strip()
        pos = match.start()

        if name.startswith("test_"):
            continue

        context = source[pos:pos+600]

        prompt = f"What does the Rust function `{name}` in {rel_path} do?"
        response = f"The {'public ' if is_pub else ''}Rust function `{name}({args}){ret}` is defined in {rel_path}:\n\n```rust\n{context[:500]}\n```"

        h = hash_pair(prompt, response)
        if h not in existing_hashes and len(response) > 80:
            pairs.append({
                "prompt": prompt,
                "response": response,
                "domain": "codebase_rust",
                "source_file": rel_path,
                "model": "codebase_miner"
            })
            existing_hashes.add(h)

    return pairs


# ============================================================
# CONTRASTIVE PAIR GENERATOR
# ============================================================

def generate_contrastive_pairs(existing_pairs, existing_hashes, max_pairs=3000):
    """Generate wrong-answer variants of existing pairs for DPO-style training."""
    pairs = []
    corruption_methods = [
        ("reversed_logic", lambda s: s.replace(" is ", " is not ").replace(" can ", " cannot ").replace(" will ", " will not ")),
        ("wrong_numbers", lambda s: re.sub(r'\b(\d+)\b', lambda m: str(int(m.group(1)) * 2 + 1), s[:500]) + s[500:]),
        ("truncated", lambda s: s[:len(s)//3] + "..."),
        ("hallucinated", lambda s: s.replace(".", ". Additionally, this uses quantum entanglement for faster processing.", 1)),
        ("wrong_language", lambda s: s.replace("Python", "COBOL").replace("Rust", "Fortran").replace("NovaLang", "Assembly")),
    ]

    for pair in existing_pairs[:max_pairs]:
        if len(pairs) >= max_pairs:
            break

        prompt = pair.get("prompt", "")
        good_response = pair.get("response", "")

        if len(good_response) < 50:
            continue

        # Pick a random corruption
        method_name, corrupt_fn = corruption_methods[len(pairs) % len(corruption_methods)]
        try:
            bad_response = corrupt_fn(good_response)
        except Exception:
            continue

        if bad_response == good_response:
            continue

        contrastive_prompt = f"Which response is better for the question: {prompt}\n\nResponse A: {bad_response[:300]}\n\nResponse B: {good_response[:300]}"
        contrastive_response = f"Response B is better. Response A is incorrect because it {method_name.replace('_', ' ')}."

        h = hash_pair(contrastive_prompt, contrastive_response)
        if h not in existing_hashes:
            pairs.append({
                "prompt": contrastive_prompt,
                "response": contrastive_response,
                "domain": "contrastive_" + method_name,
                "model": "codebase_miner"
            })
            existing_hashes.add(h)

    return pairs


# ============================================================
# MAIN
# ============================================================

def find_files(root, extensions, skip_dirs):
    """Walk directory tree and find files by extension."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip excluded directories
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for f in filenames:
            if any(f.endswith(ext) for ext in extensions):
                files.append(os.path.join(dirpath, f))
    return files


def main():
    print("=" * 60)
    print("  NovaX Codebase Miner v1.0")
    print("  Extracting training pairs from 355K lines of source")
    print("  Runs on CPU only - does not interfere with GPU tasks")
    print("=" * 60)

    existing_hashes = load_existing_hashes()
    print(f"Existing pairs: {len(existing_hashes)} unique hashes")

    all_pairs = []
    t0 = time.time()

    # ── Python files ──
    py_files = find_files(NOVAX_ROOT, [".py"], SKIP_DIRS)
    print(f"\nFound {len(py_files)} Python files")
    py_func_count = 0
    py_class_count = 0
    py_import_count = 0
    py_error_count = 0

    for f in py_files:
        pairs = mine_python_functions(f, existing_hashes)
        py_func_count += len(pairs)
        all_pairs.extend(pairs)

        pairs = mine_python_classes(f, existing_hashes)
        py_class_count += len(pairs)
        all_pairs.extend(pairs)

        pairs = mine_python_imports(f, existing_hashes)
        py_import_count += len(pairs)
        all_pairs.extend(pairs)

        pairs = mine_python_error_handling(f, existing_hashes)
        py_error_count += len(pairs)
        all_pairs.extend(pairs)

    print(f"  Functions: {py_func_count}")
    print(f"  Classes:   {py_class_count}")
    print(f"  Imports:   {py_import_count}")
    print(f"  Errors:    {py_error_count}")

    # ── NovaLang files ──
    nova_files = find_files(NOVAX_ROOT, [".nova"], SKIP_DIRS)
    print(f"\nFound {len(nova_files)} NovaLang files")
    nova_func_count = 0
    nova_route_count = 0

    for f in nova_files:
        pairs = mine_nova_functions(f, existing_hashes)
        nova_func_count += len(pairs)
        all_pairs.extend(pairs)

        pairs = mine_nova_routes(f, existing_hashes)
        nova_route_count += len(pairs)
        all_pairs.extend(pairs)

    print(f"  Functions: {nova_func_count}")
    print(f"  Routes:    {nova_route_count}")

    # ── Rust files ──
    rs_files = find_files(NOVAX_ROOT / "nova_llm" / "trit_engine", [".rs"], {"target", "debug"})
    rs_files += find_files(NOVAX_ROOT / "novalang-vm", [".rs"], {"target", "debug"})
    print(f"\nFound {len(rs_files)} Rust files")
    rs_count = 0

    for f in rs_files:
        pairs = mine_rust_functions(f, existing_hashes)
        rs_count += len(pairs)
        all_pairs.extend(pairs)

    print(f"  Functions: {rs_count}")

    # ── Config files ──
    config_files = find_files(NOVAX_ROOT, [".json"], SKIP_DIRS)
    # Filter to actual config files (not training data)
    config_files = [f for f in config_files if "training_pairs" not in f
                    and "package-lock" not in f
                    and "node_modules" not in f
                    and os.path.getsize(f) < 50000]
    print(f"\nFound {len(config_files)} config JSON files")
    config_count = 0

    for f in config_files:
        pairs = mine_json_configs(f, existing_hashes)
        config_count += len(pairs)
        all_pairs.extend(pairs)

    print(f"  Configs:   {config_count}")

    # ── Contrastive pairs ──
    print(f"\nGenerating contrastive pairs from existing data...")
    if OUTPUT.exists():
        existing_data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        contrastive = generate_contrastive_pairs(existing_data, existing_hashes, max_pairs=2000)
        all_pairs.extend(contrastive)
        print(f"  Contrastive: {len(contrastive)}")

    # ── Save ──
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  TOTAL NEW PAIRS: {len(all_pairs)}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Rate: {len(all_pairs)/max(elapsed,1):.0f} pairs/sec (CPU only)")
    print(f"{'=' * 60}")

    if all_pairs:
        saved = save_pairs(all_pairs)
        print(f"\nSaved {saved} pairs to {OUTPUT}")
        final = json.loads(OUTPUT.read_text(encoding="utf-8"))
        print(f"Total dataset: {len(final)} pairs")
    else:
        print("\nNo new pairs to save.")


if __name__ == "__main__":
    main()
