"""NovaX Multi-Modal Memory Service
Unified memory system: text, URLs, screenshots, files, voice, conversations.
Port 9947 -- searchable persistent memory store.
"""
import http.server, json, os, time, threading, uuid, re, math
from urllib.parse import urlparse, parse_qs, unquote
from difflib import SequenceMatcher
from datetime import datetime

PORT = 9947
DATA_DIR = os.path.join("C:\\NovaX", "data", "memories")
INDEX_FILE = os.path.join(DATA_DIR, "index.json")
CONTENT_DIR = os.path.join(DATA_DIR, "content")
VALID_TYPES = {"text", "url", "screenshot", "file", "voice", "conversation"}
MAX_FILE_PREVIEW = 500
start_time = time.time()

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CONTENT_DIR, exist_ok=True)

# ---------- thread-safe index ----------
_lock = threading.Lock()
_index = []  # list of metadata dicts (no heavy content in RAM)
_dirty = False


def _load_index():
    global _index
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            _index = json.load(f)
    else:
        _index = []


def _save_index():
    global _dirty
    tmp = INDEX_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_index, f, indent=1, ensure_ascii=True)
    os.replace(tmp, INDEX_FILE)
    _dirty = False


def _schedule_save():
    """Mark dirty; a background flush happens periodically."""
    global _dirty
    _dirty = True


def _flush_loop():
    while True:
        time.sleep(5)
        with _lock:
            if _dirty:
                _save_index()

# ---------- content on disk ----------

def _content_path(mem_id):
    return os.path.join(CONTENT_DIR, mem_id + ".json")


def _write_content(mem_id, blob):
    with open(_content_path(mem_id), "w", encoding="utf-8") as f:
        json.dump(blob, f, ensure_ascii=True)


def _read_content(mem_id):
    p = _content_path(mem_id)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _delete_content(mem_id):
    p = _content_path(mem_id)
    if os.path.exists(p):
        os.remove(p)

# ---------- search helpers ----------

def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _fuzzy_match(query_tok, text_tok, threshold=0.75):
    """Check if query token fuzzy-matches any text token."""
    for tt in text_tok:
        if SequenceMatcher(None, query_tok, tt).ratio() >= threshold:
            return True
    return False


def _score_memory(entry, query_tokens, type_filter=None, date_from=None, date_to=None):
    """Return relevance score or -1 if filtered out."""
    if type_filter and entry.get("type") != type_filter:
        return -1
    ts = entry.get("timestamp", 0)
    if date_from and ts < date_from:
        return -1
    if date_to and ts > date_to:
        return -1

    searchable = " ".join([
        entry.get("summary", ""),
        " ".join(entry.get("tags", [])),
        entry.get("type", ""),
        entry.get("source", ""),
    ]).lower()
    tokens = _tokenize(searchable)

    score = 0.0
    for qt in query_tokens:
        # exact
        exact = tokens.count(qt)
        if exact:
            score += exact * 2.0
        elif _fuzzy_match(qt, tokens):
            score += 0.5

    if score <= 0:
        return -1

    # recency boost: memories from last 24h get up to +1
    age_hours = (time.time() - ts) / 3600.0 if ts else 9999
    recency = max(0.0, 1.0 - age_hours / 24.0)
    score += recency
    return score

# ---------- API helpers ----------

def _make_id():
    return uuid.uuid4().hex[:12]


def _now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _auto_summary(content, max_len=200):
    if not content:
        return ""
    text = str(content).replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _add_memory(mem_type, content, tags=None, summary=None, source="", extra=None):
    mem_id = _make_id()
    ts = time.time()
    entry = {
        "id": mem_id,
        "type": mem_type,
        "summary": summary or _auto_summary(content),
        "tags": tags or [],
        "timestamp": ts,
        "created": _now_iso(),
        "source": source,
    }
    blob = {"content": content}
    if extra:
        blob.update(extra)
    with _lock:
        _index.append(entry)
        _write_content(mem_id, blob)
        _schedule_save()
    return entry


def _get_full(entry):
    """Return entry dict merged with on-disk content."""
    blob = _read_content(entry["id"]) or {}
    merged = dict(entry)
    merged.update(blob)
    return merged

# ---------- file indexing ----------

def _index_file(path):
    if not os.path.exists(path):
        return None, "file not found"
    try:
        size = os.path.getsize(path)
        preview = ""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                preview = f.read(MAX_FILE_PREVIEW)
        except Exception:
            preview = "(binary file)"
        ext = os.path.splitext(path)[1].lower()
        tags = ["file"]
        if ext:
            tags.append(ext.lstrip("."))
        entry = _add_memory(
            "file",
            preview,
            tags=tags,
            summary="File: %s (%d bytes)" % (os.path.basename(path), size),
            source=path,
            extra={"file_path": path, "file_size": size, "extension": ext},
        )
        return entry, None
    except Exception as e:
        return None, str(e)

# ---------- HTTP handler ----------

class MemoryHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_ok(self, data, code=200):
        body = json.dumps(data, ensure_ascii=True).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_err(self, msg, code=400):
        self._json_ok({"error": msg, "trit": -1}, code)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    # ---- routing ----

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        if path == "/health":
            self._handle_health()
        elif path == "/memory/search":
            self._handle_search(qs)
        elif path == "/memory/recent":
            self._handle_recent(qs)
        elif path == "/memory/tags":
            self._handle_tags()
        elif path == "/memory/stats":
            self._handle_stats()
        elif path.startswith("/memory/by-tag/"):
            tag = unquote(path.split("/memory/by-tag/", 1)[1])
            self._handle_by_tag(tag)
        elif path.startswith("/memory/by-type/"):
            mtype = path.split("/memory/by-type/", 1)[1]
            self._handle_by_type(mtype)
        elif path.startswith("/memory/") and len(path.split("/")) == 3:
            mem_id = path.split("/")[2]
            self._handle_get_one(mem_id)
        else:
            self._json_err("not found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/memory/add":
            self._handle_add()
        elif path == "/memory/url":
            self._handle_url()
        elif path == "/memory/file":
            self._handle_file()
        else:
            self._json_err("not found", 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.startswith("/memory/") and len(path.split("/")) == 3:
            mem_id = path.split("/")[2]
            self._handle_delete(mem_id)
        else:
            self._json_err("not found", 404)

    # ---- handlers ----

    def _handle_health(self):
        with _lock:
            count = len(_index)
        self._json_ok({
            "status": "ok",
            "trit": 1,
            "service": "nova_memory",
            "port": PORT,
            "memories": count,
            "uptime": int(time.time() - start_time),
        })

    def _handle_add(self):
        try:
            body = self._read_body()
        except Exception:
            return self._json_err("invalid json")
        mem_type = body.get("type", "text")
        if mem_type not in VALID_TYPES:
            return self._json_err("invalid type: %s" % mem_type)
        content = body.get("content", "")
        if not content:
            return self._json_err("content required")
        tags = body.get("tags", [])
        summary = body.get("summary")
        source = body.get("source", "")
        entry = _add_memory(mem_type, content, tags=tags, summary=summary, source=source)
        self._json_ok({"trit": 1, "memory": entry}, 201)

    def _handle_url(self):
        try:
            body = self._read_body()
        except Exception:
            return self._json_err("invalid json")
        url = body.get("url", "").strip()
        if not url:
            return self._json_err("url required")
        notes = body.get("notes", "")
        tags = body.get("tags", ["url"])
        if "url" not in tags:
            tags.append("url")
        # extract domain as source
        try:
            domain = urlparse(url).netloc
        except Exception:
            domain = ""
        summary = body.get("title", url[:120])
        entry = _add_memory(
            "url",
            url,
            tags=tags,
            summary=summary,
            source=domain,
            extra={"url": url, "notes": notes, "title": body.get("title", "")},
        )
        self._json_ok({"trit": 1, "memory": entry}, 201)

    def _handle_file(self):
        try:
            body = self._read_body()
        except Exception:
            return self._json_err("invalid json")
        path = body.get("path", "").strip()
        if not path:
            return self._json_err("path required")
        entry, err = _index_file(path)
        if err:
            return self._json_err(err)
        self._json_ok({"trit": 1, "memory": entry}, 201)

    def _handle_search(self, qs):
        q = qs.get("q", [""])[0].strip()
        if not q:
            return self._json_err("q parameter required")
        query_tokens = _tokenize(q)
        if not query_tokens:
            return self._json_err("no searchable terms")
        type_filter = qs.get("type", [None])[0]
        date_from = None
        date_to = None
        if "from" in qs:
            try:
                date_from = datetime.fromisoformat(qs["from"][0]).timestamp()
            except Exception:
                pass
        if "to" in qs:
            try:
                date_to = datetime.fromisoformat(qs["to"][0]).timestamp()
            except Exception:
                pass
        limit = int(qs.get("limit", ["50"])[0])

        results = []
        with _lock:
            for entry in _index:
                sc = _score_memory(entry, query_tokens, type_filter, date_from, date_to)
                if sc > 0:
                    results.append((sc, entry))
        results.sort(key=lambda x: x[0], reverse=True)
        results = results[:limit]
        out = []
        for sc, entry in results:
            merged = _get_full(entry)
            merged["_score"] = round(sc, 3)
            out.append(merged)
        self._json_ok({"trit": 1, "count": len(out), "results": out})

    def _handle_recent(self, qs):
        n = int(qs.get("n", ["20"])[0])
        n = min(n, 500)
        with _lock:
            recent = sorted(_index, key=lambda e: e.get("timestamp", 0), reverse=True)[:n]
        out = [_get_full(e) for e in recent]
        self._json_ok({"trit": 1, "count": len(out), "memories": out})

    def _handle_tags(self):
        counts = {}
        with _lock:
            for entry in _index:
                for tag in entry.get("tags", []):
                    counts[tag] = counts.get(tag, 0) + 1
        sorted_tags = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        self._json_ok({"trit": 1, "tags": [{"tag": t, "count": c} for t, c in sorted_tags]})

    def _handle_by_tag(self, tag):
        with _lock:
            matches = [e for e in _index if tag in e.get("tags", [])]
        out = [_get_full(e) for e in matches]
        self._json_ok({"trit": 1, "count": len(out), "memories": out})

    def _handle_by_type(self, mtype):
        if mtype not in VALID_TYPES:
            return self._json_err("invalid type")
        with _lock:
            matches = [e for e in _index if e.get("type") == mtype]
        out = [_get_full(e) for e in matches]
        self._json_ok({"trit": 1, "count": len(out), "memories": out})

    def _handle_get_one(self, mem_id):
        with _lock:
            entry = None
            for e in _index:
                if e["id"] == mem_id:
                    entry = e
                    break
        if not entry:
            return self._json_err("not found", 404)
        self._json_ok({"trit": 1, "memory": _get_full(entry)})

    def _handle_delete(self, mem_id):
        with _lock:
            found = None
            for i, e in enumerate(_index):
                if e["id"] == mem_id:
                    found = i
                    break
            if found is None:
                return self._json_err("not found", 404)
            _index.pop(found)
            _delete_content(mem_id)
            _schedule_save()
        self._json_ok({"trit": 1, "deleted": mem_id})

    def _handle_stats(self):
        type_counts = {}
        total = 0
        with _lock:
            total = len(_index)
            for e in _index:
                t = e.get("type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1
        # disk usage
        disk = 0
        try:
            for root, dirs, files in os.walk(DATA_DIR):
                for fname in files:
                    disk += os.path.getsize(os.path.join(root, fname))
        except Exception:
            pass
        self._json_ok({
            "trit": 1,
            "total": total,
            "by_type": type_counts,
            "disk_bytes": disk,
            "disk_mb": round(disk / (1024 * 1024), 2),
            "index_file": INDEX_FILE,
        })


# ---------- main ----------

def main():
    _load_index()
    # start background flush thread
    t = threading.Thread(target=_flush_loop, daemon=True)
    t.start()
    print("NovaX Memory Service on http://127.0.0.1:%d" % PORT)
    print("  memories loaded: %d" % len(_index))
    server = http.server.HTTPServer(("127.0.0.1", PORT), MemoryHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        with _lock:
            if _dirty:
                _save_index()
        print("\nMemory service stopped.")


if __name__ == "__main__":
    main()
