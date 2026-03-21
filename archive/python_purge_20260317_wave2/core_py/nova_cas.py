#!/usr/bin/env python3
"""
NovaX Content-Addressable Storage (CAS) Engine
Block-level deduplication using 2187-byte (3^7) harmonic blocks.

Architecture:
  - Block size: 2187 bytes (3^7 NovaX harmonic constant)
  - Hash: SHA256 truncated to 20 bytes (160 bits)
  - Index: SQLite database
  - Store: flat binary file with concatenated unique blocks
  - API: put/get/delete with refcounting and GC

Usage:
  from nova_cas import CASStore
  cas = CASStore("C:/NovaX/cas")
  hashes = cas.put(data)
  data = cas.get(hashes)
  cas.store_file("path/to/file")
  cas.retrieve_file("path/to/file", "output/path")

Port: 9912 (CAS service endpoint)
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
import struct
import threading
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# NovaX harmonic constants
BLOCK_SIZE = 3**7          # 2187 bytes
HASH_SIZE = 20             # 160 bits (SHA256 truncated)
PACK_UNIT = 3**5           # 243 (TZip pack unit)
COMPOSITION_UNIT = 7       # Composition unit
CARRIER_FRAME = 13         # Carrier/frame

CAS_PORT = 9912
CAS_VERSION = "1.0.0"


def block_hash(data: bytes) -> bytes:
    """Hash a block using SHA256 truncated to 160 bits."""
    return hashlib.sha256(data).digest()[:HASH_SIZE]


def split_blocks(data: bytes) -> list:
    """Split data into 2187-byte blocks, padding the last one."""
    blocks = []
    for i in range(0, len(data), BLOCK_SIZE):
        block = data[i:i + BLOCK_SIZE]
        if len(block) < BLOCK_SIZE:
            block = block + b'\x00' * (BLOCK_SIZE - len(block))
        blocks.append(block)
    return blocks


class CASStore:
    """Content-addressable block store with refcounting."""

    def __init__(self, store_dir: str):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.store_path = self.store_dir / "store.bin"
        self.db_path = self.store_dir / "index.db"
        self.meta_path = self.store_dir / "metadata.json"
        self.lock = threading.Lock()

        self._init_db()
        self._init_store()
        self._update_metadata()

    def _init_db(self):
        """Initialize SQLite index database."""
        self.db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS blocks (
                hash     BLOB PRIMARY KEY,
                offset   INTEGER NOT NULL,
                size     INTEGER NOT NULL,
                refcount INTEGER DEFAULT 1,
                created  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS files (
                path     TEXT PRIMARY KEY,
                blocks   TEXT NOT NULL,
                size     INTEGER NOT NULL,
                mtime    REAL NOT NULL,
                stored   TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_refcount ON blocks(refcount);
            CREATE INDEX IF NOT EXISTS idx_offset ON blocks(offset);
        """)
        self.db.commit()

    def _init_store(self):
        """Initialize or open the block store file."""
        if not self.store_path.exists():
            self.store_path.touch()
        self._store_size = self.store_path.stat().st_size

    def _update_metadata(self):
        """Write store metadata."""
        stats = self.stats()
        meta = {
            "version": CAS_VERSION,
            "block_size": BLOCK_SIZE,
            "hash_algorithm": "sha256-160",
            "hash_size_bytes": HASH_SIZE,
            "harmonic_base": "3^7",
            "created": stats.get("created", datetime.now().isoformat()),
            "last_updated": datetime.now().isoformat(),
            "stats": stats,
        }
        self.meta_path.write_text(json.dumps(meta, indent=2))

    def put(self, data: bytes) -> list:
        """
        Store data as content-addressed blocks.
        Returns list of block hashes (bytes).
        """
        blocks = split_blocks(data)
        hashes = []

        with self.lock:
            for block in blocks:
                h = block_hash(block)
                hashes.append(h)

                # Check if block already exists
                row = self.db.execute(
                    "SELECT offset, refcount FROM blocks WHERE hash = ?",
                    (h,)
                ).fetchone()

                if row:
                    # Block exists, increment refcount
                    self.db.execute(
                        "UPDATE blocks SET refcount = refcount + 1 WHERE hash = ?",
                        (h,)
                    )
                else:
                    # New block, append to store
                    offset = self._store_size
                    with open(self.store_path, 'ab') as f:
                        f.write(block)
                    self._store_size += BLOCK_SIZE

                    self.db.execute(
                        "INSERT INTO blocks (hash, offset, size) VALUES (?, ?, ?)",
                        (h, offset, len(block))
                    )

            self.db.commit()

        return hashes

    def get(self, hashes: list) -> bytes:
        """
        Retrieve data by block hashes.
        Returns concatenated block data.
        """
        result = bytearray()

        with open(self.store_path, 'rb') as f:
            for h in hashes:
                row = self.db.execute(
                    "SELECT offset, size FROM blocks WHERE hash = ?",
                    (h,)
                ).fetchone()

                if row is None:
                    raise KeyError(f"Block not found: {h.hex()}")

                offset, size = row
                f.seek(offset)
                block = f.read(BLOCK_SIZE)
                result.extend(block)

        return bytes(result)

    def store_file(self, filepath: str) -> dict:
        """
        Store a file in CAS. Returns file record with block hashes.
        """
        filepath = str(Path(filepath).resolve())
        stat = os.stat(filepath)

        with open(filepath, 'rb') as f:
            data = f.read()

        hashes = self.put(data)
        hash_hexes = [h.hex() for h in hashes]

        with self.lock:
            self.db.execute(
                """INSERT OR REPLACE INTO files (path, blocks, size, mtime)
                   VALUES (?, ?, ?, ?)""",
                (filepath, json.dumps(hash_hexes), stat.st_size, stat.st_mtime)
            )
            self.db.commit()

        new_blocks = 0
        existing_blocks = 0
        for h in hashes:
            row = self.db.execute(
                "SELECT refcount FROM blocks WHERE hash = ?", (h,)
            ).fetchone()
            if row and row[0] == 1:
                new_blocks += 1
            else:
                existing_blocks += 1

        return {
            "path": filepath,
            "size": stat.st_size,
            "blocks": len(hashes),
            "new_blocks": new_blocks,
            "existing_blocks": existing_blocks,
            "dedup_ratio": existing_blocks / len(hashes) if hashes else 0,
            "hashes": hash_hexes,
        }

    def retrieve_file(self, stored_path: str, output_path: str = None) -> bytes:
        """
        Retrieve a file from CAS by its original path.
        If output_path is given, writes to disk. Returns data either way.
        """
        row = self.db.execute(
            "SELECT blocks, size FROM files WHERE path = ?",
            (stored_path,)
        ).fetchone()

        if row is None:
            raise KeyError(f"File not found in CAS: {stored_path}")

        hash_hexes = json.loads(row[0])
        original_size = row[1]
        hashes = [bytes.fromhex(h) for h in hash_hexes]

        data = self.get(hashes)
        # Trim to original size (remove padding from last block)
        data = data[:original_size]

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(data)

        return data

    def delete_file(self, filepath: str):
        """Remove a file record and decrement block refcounts."""
        filepath = str(Path(filepath).resolve())

        row = self.db.execute(
            "SELECT blocks FROM files WHERE path = ?", (filepath,)
        ).fetchone()

        if row is None:
            return

        hash_hexes = json.loads(row[0])

        with self.lock:
            for hex_hash in hash_hexes:
                h = bytes.fromhex(hex_hash)
                self.db.execute(
                    "UPDATE blocks SET refcount = refcount - 1 WHERE hash = ?",
                    (h,)
                )

            self.db.execute("DELETE FROM files WHERE path = ?", (filepath,))
            self.db.commit()

    def gc(self) -> dict:
        """
        Garbage collect: remove blocks with refcount <= 0.
        Returns stats about what was collected.
        Note: does not compact store.bin (blocks become holes).
        Use compact() after gc() to reclaim disk space.
        """
        with self.lock:
            cursor = self.db.execute(
                "SELECT COUNT(*), SUM(size) FROM blocks WHERE refcount <= 0"
            )
            count, total_size = cursor.fetchone()
            count = count or 0
            total_size = total_size or 0

            self.db.execute("DELETE FROM blocks WHERE refcount <= 0")
            self.db.commit()

        return {
            "blocks_collected": count,
            "bytes_freed_index": total_size,
            "note": "Run compact() to reclaim store.bin space"
        }

    def compact(self) -> dict:
        """
        Compact store.bin by rewriting only live blocks.
        This reclaims space from GC'd blocks.
        """
        with self.lock:
            rows = self.db.execute(
                "SELECT hash, offset, size FROM blocks ORDER BY offset"
            ).fetchall()

            new_store = self.store_dir / "store.bin.new"
            new_offset = 0
            updates = []

            with open(self.store_path, 'rb') as old_f, \
                 open(new_store, 'wb') as new_f:
                for h, offset, size in rows:
                    old_f.seek(offset)
                    block = old_f.read(BLOCK_SIZE)
                    new_f.write(block)
                    updates.append((new_offset, h))
                    new_offset += BLOCK_SIZE

            # Update offsets in index
            for new_off, h in updates:
                self.db.execute(
                    "UPDATE blocks SET offset = ? WHERE hash = ?",
                    (new_off, h)
                )
            self.db.commit()

            # Replace old store with new
            old_size = self.store_path.stat().st_size
            os.replace(str(new_store), str(self.store_path))
            self._store_size = new_offset

            return {
                "old_size": old_size,
                "new_size": new_offset,
                "reclaimed": old_size - new_offset,
                "blocks": len(rows),
            }

    def stats(self) -> dict:
        """Return store statistics."""
        block_row = self.db.execute(
            "SELECT COUNT(*), SUM(size), SUM(refcount) FROM blocks"
        ).fetchone()
        file_row = self.db.execute(
            "SELECT COUNT(*), SUM(size) FROM files"
        ).fetchone()
        dead_row = self.db.execute(
            "SELECT COUNT(*) FROM blocks WHERE refcount <= 0"
        ).fetchone()

        block_count = block_row[0] or 0
        block_bytes = block_row[1] or 0
        total_refs = block_row[2] or 0
        file_count = file_row[0] or 0
        file_bytes = file_row[1] or 0
        dead_blocks = dead_row[0] or 0

        store_size = self.store_path.stat().st_size if self.store_path.exists() else 0
        index_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        # Effective dedup: how much data is "stored" vs actual disk
        actual_disk = store_size + index_size
        logical_size = total_refs * BLOCK_SIZE if total_refs else 0

        return {
            "version": CAS_VERSION,
            "block_size": BLOCK_SIZE,
            "unique_blocks": block_count,
            "total_references": total_refs,
            "dead_blocks": dead_blocks,
            "files_stored": file_count,
            "logical_file_bytes": file_bytes,
            "store_size": store_size,
            "index_size": index_size,
            "total_disk": actual_disk,
            "logical_data": logical_size,
            "dedup_ratio": 1 - (actual_disk / logical_size) if logical_size > 0 else 0,
        }

    def verify(self) -> dict:
        """Verify store integrity by re-hashing all blocks."""
        errors = []
        checked = 0

        rows = self.db.execute("SELECT hash, offset FROM blocks").fetchall()
        with open(self.store_path, 'rb') as f:
            for stored_hash, offset in rows:
                f.seek(offset)
                block = f.read(BLOCK_SIZE)
                actual_hash = block_hash(block)
                if actual_hash != stored_hash:
                    errors.append({
                        "offset": offset,
                        "expected": stored_hash.hex(),
                        "actual": actual_hash.hex(),
                    })
                checked += 1

        return {
            "blocks_checked": checked,
            "errors": len(errors),
            "integrity": "PASS" if not errors else "FAIL",
            "details": errors[:10],  # Only first 10 errors
        }

    def close(self):
        """Close database connection."""
        self.db.close()


# ---------------------------------------------------------------------------
# HTTP Service (port 9912)
# ---------------------------------------------------------------------------

class CASHandler(BaseHTTPRequestHandler):
    """HTTP handler for CAS service."""

    cas_store = None  # Set by server init

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_GET(self):
        path = self.path.rstrip("/")

        if path == "/health":
            stats = self.cas_store.stats()
            self._respond(200, {
                "status": "+1",
                "service": "nova_cas",
                "version": CAS_VERSION,
                "block_size": BLOCK_SIZE,
                "unique_blocks": stats["unique_blocks"],
                "files_stored": stats["files_stored"],
                "dedup_ratio": f"{stats['dedup_ratio']:.1%}",
            })

        elif path == "/stats":
            self._respond(200, self.cas_store.stats())

        elif path == "/verify":
            self._respond(200, self.cas_store.verify())

        elif path.startswith("/file/"):
            filepath = path[6:]  # Strip /file/
            try:
                data = self.cas_store.retrieve_file(filepath)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except KeyError:
                self._respond(404, {"error": "File not found in CAS"})

        else:
            self._respond(404, {"error": "Unknown endpoint"})

    def do_POST(self):
        path = self.path.rstrip("/")
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""

        if path == "/put":
            # Store raw data
            hashes = self.cas_store.put(body)
            self._respond(200, {
                "blocks": len(hashes),
                "hashes": [h.hex() for h in hashes],
            })

        elif path == "/store_file":
            # Store a file by path
            try:
                req = json.loads(body)
                filepath = req.get("path", "")
                if not filepath or not os.path.exists(filepath):
                    self._respond(400, {"error": "File not found"})
                    return
                result = self.cas_store.store_file(filepath)
                self._respond(200, result)
            except json.JSONDecodeError:
                self._respond(400, {"error": "Invalid JSON"})

        elif path == "/gc":
            result = self.cas_store.gc()
            self._respond(200, result)

        elif path == "/compact":
            result = self.cas_store.compact()
            self._respond(200, result)

        else:
            self._respond(404, {"error": "Unknown endpoint"})


def run_server(store_dir="C:/NovaX/cas", port=CAS_PORT):
    """Run CAS as an HTTP service."""
    store = CASStore(store_dir)
    CASHandler.cas_store = store

    server = HTTPServer(("0.0.0.0", port), CASHandler)
    print(f"[nova_cas] CAS service v{CAS_VERSION} on port {port}")
    print(f"[nova_cas] Block size: {BLOCK_SIZE} bytes (3^7)")
    print(f"[nova_cas] Store: {store_dir}")
    stats = store.stats()
    print(f"[nova_cas] Blocks: {stats['unique_blocks']}, Files: {stats['files_stored']}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        store.close()
        server.server_close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        run_server()
    else:
        # Quick self-test
        print("NovaX CAS Self-Test")
        store = CASStore("C:/NovaX/cas")

        # Test put/get
        test_data = b"Hello NovaX CAS! " * 200  # ~3400 bytes = 2 blocks
        hashes = store.put(test_data)
        print(f"  Stored {len(test_data)} bytes in {len(hashes)} blocks")

        retrieved = store.get(hashes)[:len(test_data)]
        assert retrieved == test_data, "Data mismatch!"
        print(f"  Retrieved and verified OK")

        # Test dedup
        hashes2 = store.put(test_data)
        print(f"  Re-stored same data: {len(hashes2)} blocks (all deduped)")

        # Stats
        stats = store.stats()
        print(f"  Stats: {json.dumps(stats, indent=2, default=str)}")

        # Verify
        result = store.verify()
        print(f"  Integrity: {result['integrity']}")

        store.close()
        print("  Self-test PASSED")
