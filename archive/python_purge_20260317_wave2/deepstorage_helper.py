"""DeepStorage Helper v3.2 -- Python bridge for nova_deepstorage_service.nova

Called via nova_run(HELPER, json_args) from NovaLang.
Receives JSON on stdin (first arg), outputs JSON to stdout.

Operations:
  quantize       -- compress a single file with TZip v3.2 stream mode
  quantize_dir   -- compress all files in a directory (up to max_files)
  restore        -- decompress a .tzip file back to original
  scan           -- scan directory and estimate savings without compressing
  block_hash     -- return hash of a file's contents for dedup

Uses TZip v3.2: stream mode (token+LZMA over full file) for max ratio.
"""
import sys
import os
import json
import time

# Add NovaX root to path
sys.path.insert(0, r"C:\NovaX")

try:
    from core.tzip import (
        tzip_compress_stream, tzip_decompress_stream,
        tzip_compress, tzip_decompress,
        fastcdc_chunk, vorticity_scan, block_hash,
        reynolds, classify_flow,
        BLOCK_SIZE
    )
    TZIP_OK = True
except Exception as e:
    TZIP_OK = False
    TZIP_ERR = str(e)

# Storage directory for .tzip files
STORE_DIR = r"C:\NovaX\data\deepstorage"
os.makedirs(STORE_DIR, exist_ok=True)

# Extensions to skip (already compressed or system binaries)
SKIP_EXTS = {
    ".exe", ".dll", ".sys", ".drv", ".msi", ".bat", ".cmd",
    ".zip", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tar",
    ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mp3", ".wav",
    ".pyc", ".pyd", ".so", ".deep", ".tzip"
}

MAX_FILE_BYTES = 512 * 1024 * 1024  # 500MB ceiling


def _store_path(original_path):
    """Map original file path to .tzip store path."""
    safe = original_path.replace("\\", "_").replace("/", "_").replace(":", "_")
    return os.path.join(STORE_DIR, safe + ".tzip")


def op_quantize(path):
    """Compress a single file using TZip v3.2 stream mode."""
    if not TZIP_OK:
        return {"ok": False, "error": f"TZip unavailable: {TZIP_ERR}"}

    if not os.path.isfile(path):
        return {"ok": False, "error": f"File not found: {path}"}

    ext = os.path.splitext(path)[1].lower()
    if ext in SKIP_EXTS:
        return {"ok": False, "error": f"Skipped extension: {ext}"}

    orig_size = os.path.getsize(path)
    if orig_size == 0:
        return {"ok": False, "error": "Empty file"}
    if orig_size > MAX_FILE_BYTES:
        return {"ok": False, "error": f"File too large: {orig_size} bytes"}

    t0 = time.time()
    try:
        with open(path, "rb") as f:
            raw = f.read()

        # N-S Reynolds classification
        re = reynolds(raw)
        regime = classify_flow(re)

        # Use stream mode for max ratio (full-file LZMA context)
        chunk_positions = fastcdc_chunk(raw)
        blocks = [raw[off:off + length] for off, length in chunk_positions]
        compressed = tzip_compress_stream(blocks)

        comp_size = len(compressed)

        # Only store if it actually saves space (at least 5% savings)
        if comp_size >= orig_size * 0.95:
            return {
                "ok": False,
                "error": "No meaningful compression gain",
                "original_size": orig_size,
                "compressed_size": comp_size,
                "regime": regime,
                "re": re
            }

        store = _store_path(path)
        with open(store, "wb") as f:
            f.write(compressed)

        elapsed = round((time.time() - t0) * 1000, 1)
        savings = round((1 - comp_size / orig_size) * 100, 1)

        return {
            "ok": True,
            "path": path,
            "store_path": store,
            "original_size": orig_size,
            "stored_size": comp_size,
            "savings_pct": savings,
            "ratio": f"{round(orig_size / max(1, comp_size), 2)}x",
            "regime": regime,
            "re": re,
            "chunks": len(blocks),
            "ms": elapsed
        }

    except Exception as e:
        return {"ok": False, "error": str(e), "path": path}


def op_quantize_dir(path, max_files=50):
    """Compress all eligible files in a directory."""
    if not os.path.isdir(path):
        return {"ok": False, "error": f"Directory not found: {path}"}

    results = []
    total_orig = 0
    total_stored = 0
    count = 0
    skipped = 0

    for root, dirs, files in os.walk(path):
        # Skip hidden/system dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                   {"__pycache__", "node_modules", ".git", "ai_env", "servers", "browser"}]

        for fname in files:
            if count >= max_files:
                break
            fpath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext in SKIP_EXTS:
                skipped += 1
                continue

            try:
                fsize = os.path.getsize(fpath)
            except OSError:
                continue
            if fsize < 256 or fsize > MAX_FILE_BYTES:
                skipped += 1
                continue

            result = op_quantize(fpath)
            if result.get("ok"):
                total_orig += result["original_size"]
                total_stored += result["stored_size"]
                count += 1
                results.append({
                    "path": fpath,
                    "savings_pct": result["savings_pct"],
                    "ratio": result["ratio"],
                    "regime": result["regime"]
                })

    overall_savings = round((1 - total_stored / max(1, total_orig)) * 100, 1)
    return {
        "ok": True,
        "files_quantized": count,
        "files_skipped": skipped,
        "total_original_bytes": total_orig,
        "total_stored_bytes": total_stored,
        "overall_savings_pct": overall_savings,
        "overall_ratio": f"{round(total_orig / max(1, total_stored), 2)}x",
        "results": results[:10]  # top 10 for response size
    }


def op_restore(path, output=None):
    """Decompress a .tzip store file back to original bytes."""
    if not TZIP_OK:
        return {"ok": False, "error": f"TZip unavailable: {TZIP_ERR}"}

    # Accept either original path (look up in store) or direct .tzip path
    if path.endswith(".tzip") and os.path.isfile(path):
        store = path
    else:
        store = _store_path(path)

    if not os.path.isfile(store):
        return {"ok": False, "error": f"No quantized version found: {store}"}

    try:
        with open(store, "rb") as f:
            compressed = f.read()

        # Decompress stream
        blocks = tzip_decompress_stream(compressed)
        raw = b"".join(blocks)

        if output:
            os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
            with open(output, "wb") as f:
                f.write(raw)

        return {
            "ok": True,
            "store_path": store,
            "output_path": output,
            "restored_size": len(raw),
            "compressed_size": len(compressed)
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def op_scan(path):
    """Scan directory and estimate savings without compressing."""
    if not os.path.isdir(path) and not os.path.isfile(path):
        return {"ok": False, "error": f"Path not found: {path}"}

    if os.path.isfile(path):
        files = [path]
    else:
        files = []
        for root, dirs, fnames in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                       {"__pycache__", "node_modules", ".git", "ai_env", "servers", "browser"}]
            for fname in fnames:
                files.append(os.path.join(root, fname))

    total_size = 0
    estimated_savings = 0
    file_count = 0
    skip_count = 0
    regimes = {"laminar": 0, "transitional": 0, "turbulent": 0, "hyperbolic": 0, "chaotic": 0}

    # Savings estimates by regime (from TZip v3.2 benchmarks with stream mode)
    REGIME_SAVINGS = {
        "laminar":      0.92,   # RLE: ~92% savings
        "transitional": 0.65,   # LZ77+LZMA: ~65%
        "turbulent":    0.55,   # LZMA: ~55%
        "hyperbolic":   0.40,   # Token+LZMA: ~40%
        "chaotic":      0.02,   # Near-incompressible: ~2%
    }

    for fpath in files[:1000]:  # cap at 1000 files for scan speed
        ext = os.path.splitext(fpath)[1].lower()
        if ext in SKIP_EXTS:
            skip_count += 1
            continue
        try:
            fsize = os.path.getsize(fpath)
        except OSError:
            continue
        if fsize < 64 or fsize > MAX_FILE_BYTES:
            skip_count += 1
            continue

        # Sample first 2187 bytes for Reynolds
        try:
            with open(fpath, "rb") as f:
                sample = f.read(BLOCK_SIZE)
            re = reynolds(sample)
            regime = classify_flow(re)
        except Exception:
            regime = "transitional"

        regimes[regime] = regimes.get(regime, 0) + 1
        total_size += fsize
        estimated_savings += fsize * REGIME_SAVINGS.get(regime, 0.4)
        file_count += 1

    est_pct = round(estimated_savings / max(1, total_size) * 100, 1)
    est_ratio = round(total_size / max(1, total_size - estimated_savings), 2)

    return {
        "ok": True,
        "path": path,
        "files_scannable": file_count,
        "files_skipped": skip_count,
        "total_size_bytes": total_size,
        "estimated_savings_bytes": int(estimated_savings),
        "estimated_savings_pct": est_pct,
        "estimated_ratio": f"{est_ratio}x",
        "regime_breakdown": regimes
    }


def op_block_hash(path):
    """Return SHA-256 hash of a file for dedup."""
    if not os.path.isfile(path):
        return {"ok": False, "error": f"File not found: {path}"}
    try:
        with open(path, "rb") as f:
            data = f.read()
        h = block_hash(data)
        return {"ok": True, "path": path, "hash": h, "size": len(data)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    # Read JSON args from command line (passed as first argument by nova_run)
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "No args provided"}))
        sys.exit(1)

    try:
        args = json.loads(sys.argv[1])
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"JSON parse error: {e}"}))
        sys.exit(1)

    op = args.get("op", "")

    if op == "quantize":
        result = op_quantize(args.get("path", ""))
    elif op == "quantize_dir":
        result = op_quantize_dir(args.get("path", ""), args.get("max_files", 50))
    elif op == "restore":
        result = op_restore(args.get("path", ""), args.get("output"))
    elif op == "scan":
        result = op_scan(args.get("path", ""))
    elif op == "block_hash":
        result = op_block_hash(args.get("path", ""))
    else:
        result = {"ok": False, "error": f"Unknown op: {op}"}

    print(json.dumps(result))
