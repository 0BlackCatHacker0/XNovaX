#!/usr/bin/env python3
"""
NovaLang Purification Swarm
============================
Sends a comprehensive NovaLang purification task to 20+ cloud AI models.
Each model receives the full Python dependency map + NovaLang builtin inventory
and generates pure NovaLang replacements for Python bridges.

Priority order:
  Phase 1: NovaLang core builtins (novalang.nova itself)
  Phase 2: Service helpers (thttp, tmedia, tmarkdown, tools, tspin, etc.)
  Phase 3: Microsoft Engine conversion (LAST — only after everything else is pure)

Usage:
  python scripts/novalang_purify_swarm.py [--phase 1|2|3] [--dry-run]
"""

import json, time, sys, os, re, argparse, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import urllib.request, urllib.error

# ── Config ──────────────────────────────────────────────────────────
ROOT = Path(r"C:\NovaX")
CLOUD_CFG = ROOT / "cloud_config.json"
RESULTS_DIR = ROOT / "swarm_results" / "purify"
TIMEOUT = 120  # seconds per model

# ── Cloud Models (confirmed live from Big Tripple Test) ─────────────
# We use Cloud Router direct calls, not Hivemind, so each model works
# independently on the full task without scatter-gather competition.
SWARM_MODELS = {
    # ── OpenAI (direct API) ──
    "openai": {
        "url": None,  # filled from cloud_config
        "key": None,
        "models": [
            "gpt-4o",
            "gpt-4.1",
            "gpt-4.1-mini",
            "o3-mini",
        ]
    },
    # ── Anthropic (direct API) ──
    "anthropic": {
        "url": None,
        "key": None,
        "models": [
            "claude-sonnet-4-20250514",
        ]
    },
    # ── OpenRouter (free + paid models) ──
    "openrouter": {
        "url": "https://openrouter.ai/api/v1",
        "key": None,
        "models": [
            "deepseek/deepseek-chat-v3.1",
            "deepseek/deepseek-r1-0528",
            "qwen/qwen3-235b-a22b-thinking-2507",
            "qwen/qwen3-coder:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "nousresearch/hermes-3-llama-3.1-405b:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "google/gemma-3-27b-it:free",
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "arcee-ai/trinity-large-preview:free",
            "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
            "stepfun/step-3.5-flash:free",
            "upstage/solar-pro-3:free",
            "openai/gpt-oss-120b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
        ]
    },
}

# ── NovaLang Builtin Inventory ──────────────────────────────────────
# This is what the models have to work WITH — native NovaLang capabilities
NOVALANG_BUILTINS = """
=== NovaLang Native Builtins (available without Python) ===

NETWORKING:
  http_get(url) -> string response body
  http_post(url, body) -> string response body
  http_put(url, body) -> string response body
  http_delete(url) -> string response body

JSON:
  json_decode(string) -> dict/list
  json_encode(value) -> string

FILE I/O:
  file_read(path) -> string contents
  file_write(path, content) -> bool
  file_exists(path) -> bool
  file_delete(path) -> bool

SHELL:
  shell(command) -> string stdout

STRINGS:
  len(s), contains(s, sub), split(s, delim), join(arr, delim)
  replace(s, old, new), trim(s), upper(s), lower(s)
  substr(s, start, length), starts_with(s, prefix), ends_with(s, suffix)
  format(template, ...args)

COLLECTIONS:
  append(arr, item), len(arr), dict_get(d, key, default)
  dict_set(d, key, val), dict_keys(d), dict_values(d), dict_has(d, key)
  range(start, end), slice(arr, start, end)

TYPE CONVERSION:
  to_string(val), to_int(val), to_float(val), type_of(val)

MATH:
  math_abs(n), math_floor(n), math_ceil(n), math_round(n)
  math_sqrt(n), math_pow(base, exp), math_min(a, b), math_max(a, b)
  math_random() -> float 0-1

SYSTEM:
  time() -> epoch ms, sleep(ms), env_get(name), env_set(name, val)
  print(msg), println(msg)

SERVER (tserve framework):
  tserve(port) -> server handle
  troute(server, method, path, handler_fn)
  tresp(body, status_code) -> response

TERNARY (unique to NovaLang):
  bool3(val), not3(a), and3(a,b), or3(a,b), merge3(a, default)
  cmp3(a,b), trit(val), tryte(val), trit_count(s)
  bt(decimal), bt_val(bt_string), bt_neg(bt_string)
  bt_add(a,b), bt_sub(a,b), bt_mul(a,b), bt_pack(s), bt_unpack(bytes)
  health3(port), health3_all(), health3_bt()

CONTROL FLOW:
  if3 cond { } maybe { } else { }
  match3 expr { TRUE => ... MAYBE => ... FALSE => ... }
  try3 { } uncertain { } fail3 { }
  while3 cond { } maybe { } done3 { }
  for item in collection { }
  for3 item in collection { } maybe { } done3 { }
  break3, continue3, return
"""

# ── Python Dependency Map ───────────────────────────────────────────
# Which .nova services call Python and what they use it for
PYTHON_DEPS = {
    "phase1_core": {
        "description": "NovaLang core — the interpreter itself calls Python for these",
        "priority": "HIGHEST — must be pure first",
        "files": {
            "novalang.nova": {
                "python_calls": 26,
                "what_for": "Advanced string ops, regex, datetime, base64, crypto hashing, "
                            "URL parsing, file glob, directory ops, temp files, subprocess, "
                            "environment variables, platform detection"
            }
        }
    },
    "phase2_services": {
        "description": "Service helpers — .nova services that bridge to Python helpers",
        "priority": "HIGH — convert after core is pure",
        "files": {
            "nova_thttp_service.nova": {"python_calls": 38, "what_for": "HTTP client ops, URL parsing, headers, cookies, SSL, multipart"},
            "nova_tmedia_service.nova": {"python_calls": 37, "what_for": "Audio/video processing, FFmpeg commands, media metadata"},
            "nova_tmarkdown_service.nova": {"python_calls": 34, "what_for": "Markdown parsing, HTML conversion, syntax highlighting"},
            "nova_tools_service.nova": {"python_calls": 32, "what_for": "File ops, process management, system info, archive handling"},
            "nova_tspin_service.nova": {"python_calls": 31, "what_for": "Text spinning, synonym replacement, NLP operations"},
            "nova_tnet_service.nova": {"python_calls": 29, "what_for": "Network ops, DNS, ping, port scanning, socket ops"},
            "nova_tyaml_service.nova": {"python_calls": 26, "what_for": "YAML parsing, dumping, validation, schema checking"},
            "nova_tsqlite_service.nova": {"python_calls": 23, "what_for": "SQLite database operations, queries, schema management"},
            "nova_timage_service.nova": {"python_calls": 21, "what_for": "Image processing, resize, convert, metadata, thumbnails"},
            "nova_tcsv_service.nova": {"python_calls": 18, "what_for": "CSV parsing, writing, filtering, column ops"},
            "nova_tjson_service.nova": {"python_calls": 15, "what_for": "JSON schema validation, JSONPath queries, diff/patch"},
            "nova_tregex_service.nova": {"python_calls": 14, "what_for": "Regex matching, replace, capture groups, named groups"},
            "nova_tbase64_service.nova": {"python_calls": 12, "what_for": "Base64 encode/decode, URL-safe variants"},
            "nova_thash_service.nova": {"python_calls": 11, "what_for": "SHA256, MD5, HMAC, bcrypt password hashing"},
        }
    },
    "phase3_microsoft": {
        "description": "Microsoft Engine — Win32 API bridge (LAST — only after everything else is pure)",
        "priority": "LAST — requires pure NovaLang + pure services first",
        "files": {
            "nova_microsoft_engine.nova": {
                "python_calls": 1,
                "what_for": "Calls microsoft_api_call.py which uses ctypes/win32gui/win32api "
                            "for: window management, registry ops, process control, theme switching, "
                            "clipboard ops, toast notifications, system info"
            }
        }
    }
}

# ── Python Helper Files ─────────────────────────────────────────────
PYTHON_HELPERS = [
    "ability_sync.py", "appcontrol_helper.py", "cloud_api_call.py",
    "cortex_helper.py", "deepstorage_helper.py", "go_best.py",
    "hivemind_batch_merge.py", "hivemind_helper.py", "hivemind_model_inject.py",
    "microsoft_api_call.py", "pacman_mega_discover.py", "pacman_stats.py",
    "stt_helper.py", "talchemy_helper.py", "tcompress_helper.py",
    "tdigest_helper.py", "tfetch_helper.py", "uia_helper.py",
    "vault_helper.py", "vpn_helper.py"
]


def build_prompt(phase: int) -> str:
    """Build the mega-prompt for the swarm task."""

    phase_info = {
        1: ("Phase 1: NovaLang Core Purification", PYTHON_DEPS["phase1_core"]),
        2: ("Phase 2: Service Helper Purification", PYTHON_DEPS["phase2_services"]),
        3: ("Phase 3: Microsoft Engine Conversion", PYTHON_DEPS["phase3_microsoft"]),
    }

    title, deps = phase_info[phase]

    files_desc = ""
    for fname, info in deps["files"].items():
        files_desc += f"\n  - {fname}: {info['python_calls']} Python calls — {info['what_for']}"

    prompt = f"""You are a NovaLang compiler engineer. NovaLang is a custom programming language with
ternary logic (TRUE/MAYBE/FALSE = +1/0/-1) and its own runtime builtins.

YOUR TASK: {title}
Priority: {deps['priority']}

GOAL: Generate pure NovaLang code that replaces ALL Python bridge calls in these files:
{files_desc}

{NOVALANG_BUILTINS}

=== NovaLang Syntax Reference ===

Variables:     let x = 42
Functions:     fn name(arg1, arg2) {{ ... return value }}
Strings:       let s = "hello"
F-strings:     let s = f"value is {{x}}"  (NOTE: cannot call functions inside f-strings, assign to var first)
Dicts:         let d = {{"key": "val"}}
Arrays:        let a = [1, 2, 3]
Comments:      // single line
Ternary if:    if3 cond {{ ... }} maybe {{ ... }} else {{ ... }}
Ternary try:   try3 {{ ... }} uncertain {{ ... }} fail3 {{ ... }}
Loop:          for item in collection {{ ... }}
While:         while3 cond {{ ... }} maybe {{ ... }} done3 {{ ... }}
Match:         match3 expr {{ TRUE => ... MAYBE => ... FALSE => ... }}
Server:        let srv = tserve(9999)
               troute(srv, "GET", "/path", handler_fn)
               fn handler_fn(req) {{ return tresp("{{}}", 200) }}
Shell exec:    let result = shell("command here")

=== CRITICAL RULES ===

1. NO Python calls. No shell("python ..."). No py_call(). No run_python().
2. Use ONLY the builtins listed above. If a builtin doesn't exist, use shell() to call
   a system command (curl, powershell, wmic, etc.) — but NEVER call Python.
3. For HTTP operations, use http_get/http_post/http_put/http_delete directly.
4. For file operations, use file_read/file_write/file_exists/file_delete.
5. For JSON, use json_decode/json_encode.
6. For complex operations that NovaLang can't do natively (e.g., image processing,
   audio transcoding), use shell() with system binaries (ffmpeg, magick, curl, etc.)
7. For Win32 API calls (Phase 3 only), use shell("powershell -Command ...") to call
   PowerShell cmdlets or .NET methods — NOT Python ctypes.
8. Every function must return a ternary result where appropriate: +1 (success), 0 (partial), -1 (failure).
9. Preserve the exact same API endpoints and response formats.
10. Use try3 {{ }} uncertain {{ }} fail3 {{ }} for error handling.

=== OUTPUT FORMAT ===

For EACH file that needs conversion, output:

```novalang
// === PURE NOVALANG REPLACEMENT: filename.nova ===
// Replaces: [what Python bridge it replaces]
// Builtins used: [list the NovaLang builtins this uses]

[full pure NovaLang code]
```

Generate the COMPLETE replacement code, not snippets. I need drop-in replacements.
If a service has 30+ Python calls, you may need to generate significant code — that's expected.

=== WHAT PYTHON HELPERS DO (so you know what to replace) ===

The 20 Python helper files provide these capabilities:
- HTTP client with cookies/SSL/multipart (thttp) -> replace with http_get/http_post + shell("curl ...")
- Media processing (tmedia) -> replace with shell("ffmpeg ...") / shell("ffprobe ...")
- Markdown parsing (tmarkdown) -> implement in pure NovaLang string ops
- File/process management (tools) -> shell() + file_read/file_write
- Text spinning/NLP (tspin) -> pure NovaLang string manipulation
- Network ops (tnet) -> shell("ping")/shell("nslookup")/http_get
- YAML parsing (tyaml) -> implement basic YAML parser in NovaLang (or shell("powershell ConvertFrom-Yaml"))
- SQLite (tsqlite) -> shell("sqlite3 ...") commands
- Image processing (timage) -> shell("magick ...") ImageMagick commands
- CSV parsing (tcsv) -> pure NovaLang split/join string ops
- Regex (tregex) -> shell("powershell [regex]::Match(...)") or simple NovaLang contains/replace
- Base64 (tbase64) -> shell("powershell [Convert]::ToBase64String(...)") or shell("certutil")
- Hashing (thash) -> shell("powershell Get-FileHash") or shell("certutil -hashfile")
- Win32 API (microsoft) -> shell("powershell ...") with .NET/COM interop

START GENERATING NOW. Be thorough and complete.
"""
    return prompt


def load_cloud_config():
    """Load API keys and URLs from cloud_config.json."""
    with open(CLOUD_CFG, "r") as f:
        cfg = json.load(f)

    # Fill in keys/URLs from config
    if "openai" in cfg:
        SWARM_MODELS["openai"]["url"] = cfg["openai"]["url"]
        SWARM_MODELS["openai"]["key"] = cfg["openai"]["key"]
    if "anthropic" in cfg:
        SWARM_MODELS["anthropic"]["url"] = cfg["anthropic"]["url"]
        SWARM_MODELS["anthropic"]["key"] = cfg["anthropic"]["key"]
    if "openrouter" in cfg:
        SWARM_MODELS["openrouter"]["url"] = cfg["openrouter"]["url"]
        SWARM_MODELS["openrouter"]["key"] = cfg["openrouter"]["key"]

    # Also check env vars
    env_oai = os.environ.get("OPENAI_API_KEY")
    if env_oai and not SWARM_MODELS["openai"]["key"]:
        SWARM_MODELS["openai"]["key"] = env_oai

    return cfg


def query_openai(url, key, model, prompt, timeout=TIMEOUT):
    """Send prompt to OpenAI-compatible API."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    # For OpenRouter, add HTTP-Referer
    if "openrouter" in url:
        headers["HTTP-Referer"] = "https://novax.local"
        headers["X-Title"] = "NovaX Purification Swarm"

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a NovaLang compiler engineer. Generate pure NovaLang code only."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 16384,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(url + "/chat/completions", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"ok": True, "response": content, "model": model, "tokens": data.get("usage", {})}
    except Exception as e:
        return {"ok": False, "error": str(e), "model": model}


def query_anthropic(url, key, model, prompt, timeout=TIMEOUT):
    """Send prompt to Anthropic API."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    }
    body = json.dumps({
        "model": model,
        "max_tokens": 16384,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "system": "You are a NovaLang compiler engineer. Generate pure NovaLang code only.",
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(url + "/v1/messages", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            return {"ok": True, "response": content, "model": model,
                    "tokens": data.get("usage", {})}
    except Exception as e:
        return {"ok": False, "error": str(e), "model": model}


def dispatch_model(provider, model, prompt):
    """Route a single model query to the right API."""
    cfg = SWARM_MODELS[provider]
    url = cfg["url"]
    key = cfg["key"]

    if not key:
        return {"ok": False, "error": "no_api_key", "model": model, "provider": provider}

    t0 = time.time()

    if provider == "anthropic":
        result = query_anthropic(url, key, model, prompt)
    else:
        result = query_openai(url, key, model, prompt)

    result["time_s"] = round(time.time() - t0, 1)
    result["provider"] = provider
    return result


def save_result(result, phase, results_dir):
    """Save individual model result to file."""
    model_safe = result["model"].replace("/", "_").replace(":", "_")
    fname = results_dir / f"phase{phase}_{model_safe}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Also save just the code if successful
    if result.get("ok") and result.get("response"):
        code_fname = results_dir / f"phase{phase}_{model_safe}.nova"
        with open(code_fname, "w", encoding="utf-8") as f:
            f.write(f"// Generated by {result['model']} at {datetime.now().isoformat()}\n")
            f.write(f"// Phase {phase} NovaLang Purification\n\n")
            f.write(result["response"])

    return fname


def run_swarm(phase: int, dry_run: bool = False):
    """Execute the purification swarm across all models."""
    print(f"\n{'='*60}")
    print(f"  NovaLang Purification Swarm — Phase {phase}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # Load config
    load_cloud_config()

    # Build prompt
    prompt = build_prompt(phase)
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
    print(f"  Prompt length: {len(prompt)} chars (hash: {prompt_hash})")

    # Count models
    total_models = sum(len(cfg["models"]) for cfg in SWARM_MODELS.values())
    print(f"  Models to query: {total_models}")

    # Build task list
    tasks = []
    for provider, cfg in SWARM_MODELS.items():
        if not cfg.get("key") and not cfg.get("url"):
            continue
        for model in cfg["models"]:
            tasks.append((provider, model))

    print(f"  Tasks queued: {len(tasks)}")

    if dry_run:
        print("\n  [DRY RUN] Would query these models:")
        for provider, model in tasks:
            has_key = bool(SWARM_MODELS[provider].get("key"))
            status = "OK" if has_key else "NO KEY"
            print(f"    [{status}] {provider}/{model}")
        print(f"\n  Prompt preview (first 500 chars):")
        print(f"  {prompt[:500]}...")
        return None

    # Create results directory
    results_dir = RESULTS_DIR / f"phase{phase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Save prompt for reference
    with open(results_dir / "prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)

    # Fire the swarm
    print(f"\n  Launching swarm... (timeout: {TIMEOUT}s per model)")
    print(f"  Results dir: {results_dir}\n")

    results = []
    success = 0
    failed = 0

    # Use ThreadPoolExecutor for parallel queries
    # Limit concurrency to avoid rate limits
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for provider, model in tasks:
            future = executor.submit(dispatch_model, provider, model, prompt)
            futures[future] = (provider, model)

        for future in as_completed(futures):
            provider, model = futures[future]
            try:
                result = future.result()
                if result.get("ok"):
                    resp_len = len(result.get("response", ""))
                    print(f"  [+1] {provider}/{model} — {result.get('time_s', '?')}s, {resp_len} chars")
                    success += 1
                else:
                    print(f"  [-1] {provider}/{model} — {result.get('error', 'unknown')[:80]}")
                    failed += 1

                save_result(result, phase, results_dir)
                results.append(result)

            except Exception as e:
                print(f"  [-1] {provider}/{model} — EXCEPTION: {str(e)[:80]}")
                failed += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  SWARM COMPLETE — Phase {phase}")
    print(f"  Success: {success}/{len(tasks)} | Failed: {failed}/{len(tasks)}")
    print(f"  Results: {results_dir}")
    print(f"{'='*60}\n")

    # Save summary
    summary = {
        "phase": phase,
        "timestamp": datetime.now().isoformat(),
        "total_models": len(tasks),
        "success": success,
        "failed": failed,
        "prompt_hash": prompt_hash,
        "prompt_length": len(prompt),
        "results": [
            {
                "model": r["model"],
                "provider": r.get("provider"),
                "ok": r.get("ok"),
                "time_s": r.get("time_s"),
                "response_length": len(r.get("response", "")),
                "error": r.get("error"),
            }
            for r in results
        ]
    }

    with open(results_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Print top responses by length (longer = more code generated)
    if success > 0:
        print("  Top responses by code volume:")
        sorted_results = sorted(
            [r for r in results if r.get("ok")],
            key=lambda r: len(r.get("response", "")),
            reverse=True
        )
        for i, r in enumerate(sorted_results[:5]):
            resp_len = len(r.get("response", ""))
            print(f"    {i+1}. {r['model']} — {resp_len:,} chars, {r.get('time_s', '?')}s")

    return results_dir, results


def merge_results(results_dir: Path):
    """Merge all successful results into a single ranked file."""
    nova_files = sorted(results_dir.glob("*.nova"))
    if not nova_files:
        print("  No .nova results to merge.")
        return

    print(f"\n  Merging {len(nova_files)} results...")

    merged_path = results_dir / "_MERGED_PURIFICATION.nova"
    with open(merged_path, "w", encoding="utf-8") as out:
        out.write("// ════════════════════════════════════════════════════════\n")
        out.write("// NovaLang Purification — Merged Swarm Results\n")
        out.write(f"// Generated: {datetime.now().isoformat()}\n")
        out.write(f"// Models: {len(nova_files)}\n")
        out.write("// ════════════════════════════════════════════════════════\n\n")

        for nf in nova_files:
            content = nf.read_text(encoding="utf-8", errors="replace")
            model_name = nf.stem.split("_", 1)[-1] if "_" in nf.stem else nf.stem
            out.write(f"\n// ── MODEL: {model_name} ──────────────────────────────\n")
            out.write(content)
            out.write("\n\n")

    print(f"  Merged file: {merged_path}")
    print(f"  Size: {merged_path.stat().st_size:,} bytes")
    return merged_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NovaLang Purification Swarm")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2, 3],
                        help="Which phase to run (1=core, 2=services, 3=microsoft)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without actually querying")
    parser.add_argument("--merge-only", type=str, default=None,
                        help="Path to results dir to merge without running swarm")
    args = parser.parse_args()

    if args.merge_only:
        merge_results(Path(args.merge_only))
    else:
        result = run_swarm(args.phase, dry_run=args.dry_run)
        if result and not args.dry_run:
            results_dir, results = result
            merge_results(results_dir)
