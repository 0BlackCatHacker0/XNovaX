# super_archive.py — Super Archive: full-text search across NovaX knowledge
# Indexes memory files, docs, .nova services, and code for RAG retrieval.
# Orchestrator calls archive_search(text, limit=5) expecting {"results": [...]}

import os
import time
import json

_ROOT = r"C:\NovaX"
_INDEX = []  # In-memory index: list of {"source", "text", "path", "indexed_at"}
_INDEXED_AT = 0

# Directories to index for RAG
_INDEX_DIRS = [
    os.path.join(_ROOT, "memory"),
    os.path.join(_ROOT, "docs"),
    os.path.join(_ROOT, "skills"),
    os.path.join(_ROOT, "examples"),
]
_INDEX_EXTENSIONS = {".md", ".txt", ".nova", ".json", ".py"}


def _tokenize(text):
    """Simple word tokenizer for search matching."""
    return set(w.lower() for w in text.split() if len(w) > 2)


def build_index(**kwargs):
    """Build the in-memory search index from NovaX knowledge directories."""
    global _INDEX, _INDEXED_AT
    _INDEX.clear()
    count = 0
    for dir_path in _INDEX_DIRS:
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _INDEX_EXTENSIONS:
                continue
            full = os.path.join(dir_path, fname)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(10000)  # First 10KB per file
                _INDEX.append({
                    "source": fname,
                    "path": full,
                    "text": content,
                    "tokens": _tokenize(content),
                    "indexed_at": time.time(),
                })
                count += 1
            except Exception:
                pass
    _INDEXED_AT = time.time()
    return {"indexed": count, "status": "ok", "time": _INDEXED_AT}


def search(query=None, limit=5, **kwargs):
    """
    Full-text search across the archive.
    Returns {"results": [{"source", "snippet", "score"}, ...]}
    """
    if not query:
        return {"results": []}

    # Auto-build index if empty
    if not _INDEX:
        build_index()

    query_tokens = _tokenize(query)
    if not query_tokens:
        return {"results": []}

    scored = []
    for entry in _INDEX:
        # Simple token overlap scoring
        overlap = query_tokens & entry.get("tokens", set())
        if overlap:
            score = len(overlap) / max(len(query_tokens), 1)
            # Find best snippet containing query words
            text = entry.get("text", "")
            snippet = ""
            text_lower = text.lower()
            for word in sorted(overlap, key=lambda w: text_lower.find(w)):
                pos = text_lower.find(word)
                if pos >= 0:
                    start = max(0, pos - 50)
                    end = min(len(text), pos + 200)
                    snippet = text[start:end].replace("\n", " ").strip()
                    break
            if not snippet:
                snippet = text[:200].replace("\n", " ").strip()
            scored.append({
                "source": entry.get("source", "?"),
                "path": entry.get("path", ""),
                "snippet": snippet,
                "score": round(score, 3),
            })

    # Sort by score descending
    scored.sort(key=lambda x: -x["score"])
    return {"results": scored[:limit]}


def archive_status(**kwargs):
    """Get archive status."""
    return {
        "indexed_files": len(_INDEX),
        "last_indexed": _INDEXED_AT if _INDEXED_AT else None,
        "index_dirs": _INDEX_DIRS,
        "status": "ok" if _INDEX else "empty",
    }
