#!/usr/bin/env python3
"""
NovaX CAS Deduplication Analysis Tool
Analyzes Ollama blob storage to measure content-addressed dedup ratio,
then projects savings for a NovaX-wide CAS system.

Usage: python cas_dedup_analysis.py
"""

import os
import json
import hashlib
from pathlib import Path
from collections import defaultdict

OLLAMA_BASE = Path(os.path.expanduser("~")) / ".ollama" / "models"
BLOB_DIR = OLLAMA_BASE / "blobs"
MANIFEST_DIR = OLLAMA_BASE / "manifests"
BLOCK_SIZE = 3**7  # 2187 bytes - NovaX harmonic block size


def format_size(size_bytes):
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def analyze_ollama_cas():
    """Analyze Ollama's existing content-addressed storage."""
    print("=" * 70)
    print(" OLLAMA CAS DEDUPLICATION ANALYSIS")
    print("=" * 70)

    # Count and size blobs
    blob_sizes = {}
    total_blob_size = 0
    blob_count = 0

    if not BLOB_DIR.exists():
        print(f"  ERROR: Blob directory not found: {BLOB_DIR}")
        return {}

    for blob in BLOB_DIR.iterdir():
        if blob.is_file():
            size = blob.stat().st_size
            blob_sizes[blob.name] = size
            total_blob_size += size
            blob_count += 1

    print(f"\n  BLOB STORE:")
    print(f"    Total blobs:      {blob_count}")
    print(f"    Total blob size:  {format_size(total_blob_size)}")

    # Parse all manifests to count references
    manifest_count = 0
    total_referenced_size = 0
    blob_references = defaultdict(int)  # hash -> reference count
    blob_declared_size = {}  # hash -> size from manifest
    model_layers = defaultdict(list)  # model_name -> [layer_hashes]
    shared_layers = defaultdict(set)  # layer_hash -> set of models using it

    manifest_root = MANIFEST_DIR / "registry.ollama.ai" / "library"
    if manifest_root.exists():
        for model_dir in manifest_root.iterdir():
            if model_dir.is_dir():
                for tag_file in model_dir.rglob("*"):
                    if tag_file.is_file():
                        manifest_count += 1
                        try:
                            data = json.loads(tag_file.read_text())
                            layers = data.get("layers", [])
                            # Include config as a layer too
                            config = data.get("config", {})
                            if config:
                                layers = [config] + layers

                            for layer in layers:
                                digest = layer.get("digest", "")
                                size = layer.get("size", 0)
                                if digest:
                                    blob_references[digest] += 1
                                    blob_declared_size[digest] = size
                                    total_referenced_size += size
                                    model_layers[model_dir.name].append(digest)
                                    shared_layers[digest].add(model_dir.name)
                        except (json.JSONDecodeError, KeyError):
                            pass

    print(f"\n  MANIFESTS:")
    print(f"    Total manifests:  {manifest_count}")
    print(f"    Total models:     {len(model_layers)}")

    # Dedup analysis
    unique_layers = len(blob_declared_size)
    total_layer_refs = sum(blob_references.values())
    actual_storage = sum(blob_declared_size.values())

    print(f"\n  DEDUPLICATION METRICS:")
    print(f"    Total layer references:  {total_layer_refs}")
    print(f"    Unique layers (blobs):   {unique_layers}")
    print(f"    Total referenced size:   {format_size(total_referenced_size)}")
    print(f"    Actual blob storage:     {format_size(total_blob_size)}")
    print(f"    Space saved by CAS:      {format_size(total_referenced_size - total_blob_size)}")

    if total_referenced_size > 0:
        dedup_ratio = 1 - (total_blob_size / total_referenced_size)
        print(f"    Dedup ratio:             {dedup_ratio:.1%}")
        print(f"    Effective multiplier:    {total_referenced_size / total_blob_size:.2f}x")

    # Find most shared layers
    shared = {k: v for k, v in shared_layers.items() if len(v) > 1}
    if shared:
        print(f"\n  TOP SHARED LAYERS (used by multiple models):")
        sorted_shared = sorted(shared.items(), key=lambda x: len(x[1]), reverse=True)
        for digest, models in sorted_shared[:10]:
            size = blob_declared_size.get(digest, 0)
            short_hash = digest.split(":")[-1][:16] if ":" in digest else digest[:16]
            print(f"    {short_hash}...  {len(models):3d} models  {format_size(size):>10s}")
            if len(models) <= 5:
                print(f"      -> {', '.join(sorted(models))}")

    # Size distribution of blobs
    ranges = [
        ("< 1 KB", 0, 1024),
        ("1 KB - 1 MB", 1024, 1024**2),
        ("1 MB - 100 MB", 1024**2, 100 * 1024**2),
        ("100 MB - 1 GB", 100 * 1024**2, 1024**3),
        ("1 GB - 5 GB", 1024**3, 5 * 1024**3),
        ("> 5 GB", 5 * 1024**3, float('inf')),
    ]
    print(f"\n  BLOB SIZE DISTRIBUTION:")
    for label, lo, hi in ranges:
        blobs_in = [(n, s) for n, s in blob_sizes.items() if lo <= s < hi]
        if blobs_in:
            total = sum(s for _, s in blobs_in)
            print(f"    {label:>15s}:  {len(blobs_in):4d} blobs  {format_size(total):>10s}")

    return {
        "blob_count": blob_count,
        "manifest_count": manifest_count,
        "total_blob_size": total_blob_size,
        "total_referenced_size": total_referenced_size,
        "unique_layers": unique_layers,
        "total_refs": total_layer_refs,
        "shared_layers": len(shared),
    }


def project_novax_cas_savings():
    """Project savings from extending CAS to all NovaX data."""
    print("\n" + "=" * 70)
    print(" NOVAX CAS PROJECTION")
    print("=" * 70)

    novax_dir = Path("C:/NovaX")
    scan_dirs = {
        "core": novax_dir / "core",
        "data": novax_dir / "data",
        "web": novax_dir / "web",
        "tools": novax_dir / "tools",
    }

    print(f"\n  BLOCK SIZE: {BLOCK_SIZE} bytes (3^7 = 2187, NovaX harmonic)")
    print(f"  HASH: SHA256 truncated to 160 bits (20 bytes)")
    print(f"  INDEX OVERHEAD: ~40 bytes per block (hash + offset + metadata)")

    total_files = 0
    total_size = 0
    total_blocks = 0
    block_hashes = set()
    duplicate_blocks = 0
    files_by_ext = defaultdict(lambda: {"count": 0, "size": 0})

    for label, scan_dir in scan_dirs.items():
        if not scan_dir.exists():
            continue
        for root, dirs, files in os.walk(scan_dir):
            # Skip __pycache__ and .git
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', 'node_modules')]
            for fname in files:
                fpath = Path(root) / fname
                try:
                    fsize = fpath.stat().st_size
                except OSError:
                    continue

                total_files += 1
                total_size += fsize
                ext = fpath.suffix.lower()
                files_by_ext[ext]["count"] += 1
                files_by_ext[ext]["size"] += fsize

                # Hash blocks for files under 50MB (skip huge binaries for speed)
                if fsize < 50 * 1024 * 1024:
                    try:
                        with open(fpath, 'rb') as f:
                            while True:
                                block = f.read(BLOCK_SIZE)
                                if not block:
                                    break
                                # Pad last block to full size
                                if len(block) < BLOCK_SIZE:
                                    block = block + b'\x00' * (BLOCK_SIZE - len(block))
                                total_blocks += 1
                                h = hashlib.sha256(block).digest()[:20]  # 160-bit truncation
                                if h in block_hashes:
                                    duplicate_blocks += 1
                                else:
                                    block_hashes.add(h)
                    except (PermissionError, OSError):
                        pass

    unique_blocks = len(block_hashes)

    print(f"\n  SCAN RESULTS ({', '.join(scan_dirs.keys())}):")
    print(f"    Files scanned:       {total_files}")
    print(f"    Total data:          {format_size(total_size)}")
    print(f"    Total 2187B blocks:  {total_blocks}")
    print(f"    Unique blocks:       {unique_blocks}")
    print(f"    Duplicate blocks:    {duplicate_blocks}")

    if total_blocks > 0:
        dedup_pct = duplicate_blocks / total_blocks * 100
        saved = duplicate_blocks * BLOCK_SIZE
        index_overhead = unique_blocks * 40  # 40 bytes per index entry
        net_saved = saved - index_overhead
        print(f"    Block dedup ratio:   {dedup_pct:.1f}%")
        print(f"    Gross space saved:   {format_size(saved)}")
        print(f"    Index overhead:      {format_size(index_overhead)}")
        print(f"    Net space saved:     {format_size(net_saved)}")

    # Top file types by size
    print(f"\n  FILE TYPES BY SIZE:")
    sorted_exts = sorted(files_by_ext.items(), key=lambda x: x[1]["size"], reverse=True)
    for ext, info in sorted_exts[:15]:
        ext_label = ext if ext else "(no ext)"
        print(f"    {ext_label:>10s}:  {info['count']:5d} files  {format_size(info['size']):>10s}")


def print_cas_architecture():
    """Print the NovaX CAS architecture design."""
    print("\n" + "=" * 70)
    print(" NOVAX CONTENT-ADDRESSABLE STORAGE (CAS) ARCHITECTURE")
    print("=" * 70)

    print("""
  LAYER 1: OLLAMA CAS (EXISTING)
  --------------------------------
  Already operational. 102 models share 274 blobs via SHA256.
  Each manifest references blobs by digest. No changes needed.

  LAYER 2: NOVAX BLOCK-LEVEL CAS (NEW)
  --------------------------------
  Block size:    2187 bytes (3^7 harmonic)
  Hash:          SHA256 truncated to 160 bits (20 bytes)
  Collision:     ~2^80 birthday attack = infeasible
  Index:         SQLite (hash BLOB PRIMARY KEY, offset INTEGER, refcount INTEGER)
  Store:         Flat binary file with concatenated unique blocks

  API:
    put(data: bytes) -> hash: bytes
      - Split into 2187-byte blocks
      - Hash each block
      - Store only new blocks
      - Return list of hashes

    get(hashes: list[bytes]) -> data: bytes
      - Look up each hash in index
      - Read blocks from store
      - Concatenate and return

    delete(hashes: list[bytes]) -> None
      - Decrement refcount
      - Mark block as free when refcount = 0
      - Periodic compaction reclaims space

  LAYER 3: TERNARY CAS (FUTURE)
  --------------------------------
  Convert blocks to balanced ternary (-1, 0, +1) before hashing.
  Benefits:
    - Zero-heavy blocks (sparse data) compress dramatically
    - Ternary alignment matches NovaX 3-5-7-13 harmonic constants
    - Natural quantization for AI model weights
    - Blocks that differ only in magnitude map to same trit pattern

  Ternary encoding:
    Each byte (256 values) -> 6 trits (729 values, 2.84x expansion)
    Block: 2187 bytes -> 13122 trits (but stored as 2187 trit-pairs = 4374 bits)
    Ternary hash: hash the trit representation

  STORAGE LAYOUT:
  --------------------------------
  C:\\NovaX\\cas\\
    store.bin          # Concatenated unique blocks
    index.db           # SQLite: hash -> offset, refcount, size, created
    metadata.json      # Store stats, version, block size
    gc.log             # Garbage collection log

  SCHEMA (SQLite):
    CREATE TABLE blocks (
      hash     BLOB(20) PRIMARY KEY,   -- SHA256[:20]
      offset   INTEGER NOT NULL,        -- Byte offset in store.bin
      size     INTEGER NOT NULL,        -- Original data size (before padding)
      refcount INTEGER DEFAULT 1,       -- Number of references
      created  TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE files (
      path     TEXT PRIMARY KEY,         -- Original file path
      blocks   TEXT NOT NULL,            -- JSON array of block hashes (hex)
      size     INTEGER NOT NULL,         -- Original file size
      mtime    TEXT NOT NULL,            -- Last modified time
      stored   TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX idx_refcount ON blocks(refcount);

  CAPACITY PROJECTIONS (2TB drive):
  --------------------------------
  Current Ollama CAS dedup:         ~40% on 163GB = 65GB saved
  NovaX code/data block CAS:        ~20% on remaining data
  NTFS compression (complementary): ~35% on code, logs, text
  Ternary CAS (sparse blocks):      ~10-30% additional

  Conservative total:  80-100GB additional effective capacity
  Optimistic total:    150-200GB with NTFS compression stacking
""")


def print_analysis_commands():
    """Print PowerShell commands for manual Ollama dedup analysis."""
    print("\n" + "=" * 70)
    print(" POWERSHELL COMMANDS FOR OLLAMA DEDUP ANALYSIS")
    print("=" * 70)

    print(r"""
  # 1. Count blobs and total size
  $blobs = Get-ChildItem "$env:USERPROFILE\.ollama\models\blobs" -File
  $blobTotal = ($blobs | Measure-Object Length -Sum).Sum
  Write-Host "Blobs: $($blobs.Count), Size: $([math]::Round($blobTotal/1GB,2)) GB"

  # 2. Count manifests and calculate total referenced size
  $manifests = Get-ChildItem "$env:USERPROFILE\.ollama\models\manifests" -Recurse -File
  $totalRef = 0
  $layerRefs = @{}
  foreach ($m in $manifests) {
      $data = Get-Content $m.FullName | ConvertFrom-Json
      foreach ($layer in $data.layers) {
          $totalRef += $layer.size
          if ($layerRefs.ContainsKey($layer.digest)) {
              $layerRefs[$layer.digest] += 1
          } else {
              $layerRefs[$layer.digest] = 1
          }
      }
      if ($data.config) {
          $totalRef += $data.config.size
          $d = $data.config.digest
          if ($layerRefs.ContainsKey($d)) { $layerRefs[$d] += 1 }
          else { $layerRefs[$d] = 1 }
      }
  }
  Write-Host "Manifests: $($manifests.Count)"
  Write-Host "Total referenced: $([math]::Round($totalRef/1GB,2)) GB"
  Write-Host "Actual blob storage: $([math]::Round($blobTotal/1GB,2)) GB"
  Write-Host "Space saved by CAS: $([math]::Round(($totalRef-$blobTotal)/1GB,2)) GB"
  $ratio = 1 - ($blobTotal / $totalRef)
  Write-Host "Dedup ratio: $([math]::Round($ratio*100,1))%"

  # 3. Find most-shared layers
  Write-Host "`nTop shared layers:"
  $layerRefs.GetEnumerator() | Sort-Object Value -Descending |
      Select-Object -First 10 | ForEach-Object {
          $short = $_.Key.Substring(7, 16)
          Write-Host "  $short... referenced $($_.Value) times"
      }

  # 4. Blob size distribution
  Write-Host "`nBlob size distribution:"
  $blobs | Group-Object {
      if ($_.Length -lt 1KB) { "< 1KB" }
      elseif ($_.Length -lt 1MB) { "1KB-1MB" }
      elseif ($_.Length -lt 100MB) { "1MB-100MB" }
      elseif ($_.Length -lt 1GB) { "100MB-1GB" }
      elseif ($_.Length -lt 5GB) { "1GB-5GB" }
      else { "> 5GB" }
  } | ForEach-Object {
      $sz = ($_.Group | Measure-Object Length -Sum).Sum
      Write-Host ("  {0,-12} {1,4} blobs  {2,10}" -f $_.Name, $_.Count,
          "$([math]::Round($sz/1GB,2)) GB")
  }
""")


if __name__ == "__main__":
    # Run analysis
    ollama_stats = analyze_ollama_cas()
    project_novax_cas_savings()
    print_cas_architecture()
    print_analysis_commands()
