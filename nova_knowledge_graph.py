#!/usr/bin/env python3
"""
NovaX Personal Knowledge Graph Service
Port 9941 - SQLite-backed knowledge graph of interactions, decisions, concepts.
Thread-safe, no external dependencies.
"""

import sqlite3
import threading
import json
import time
import math
import re
import hashlib
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

PORT = 9941
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "knowledge_graph.db")

VALID_NODE_TYPES = {
    "CONCEPT", "DECISION", "PROJECT", "PERSON", "TOOL",
    "MODEL", "SERVICE", "FACT", "PREFERENCE"
}

VALID_RELATIONS = {
    "RELATES_TO", "DEPENDS_ON", "CREATED_BY", "USED_IN",
    "CONTRADICTS", "SUPPORTS", "PRECEDED_BY"
}

DOMAIN_KEYWORDS = {
    "math": ["math", "algebra", "calculus", "geometry", "equation", "theorem", "proof", "matrix", "vector", "integral"],
    "code": ["code", "function", "variable", "class", "module", "api", "debug", "compile", "runtime", "syntax"],
    "science": ["science", "physics", "chemistry", "biology", "experiment", "hypothesis", "theory", "atom", "cell"],
    "ai": ["ai", "model", "training", "neural", "llm", "embedding", "inference", "transformer", "token", "prompt"],
    "system": ["system", "service", "port", "server", "process", "memory", "cpu", "disk", "network", "config"],
    "design": ["design", "ui", "ux", "layout", "color", "font", "dashboard", "interface", "widget", "theme"],
    "data": ["data", "database", "sql", "table", "query", "schema", "index", "row", "column", "migration"],
}

DECAY_HALF_LIFE_DAYS = 30.0

# ---------- Database Layer ----------

_db_lock = threading.Lock()


def _get_conn():
    """Get a new connection for the current thread."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they do not exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _db_lock:
        conn = _get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    domains TEXT DEFAULT '[]',
                    tags TEXT DEFAULT '[]',
                    created TEXT NOT NULL,
                    updated TEXT NOT NULL,
                    embedding_hash TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    created TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    summary TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
                CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
                CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
            """)
            conn.commit()
        finally:
            conn.close()


# ---------- Utility Functions ----------

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def compute_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def recency_score(created_iso):
    """Compute a decay score based on age. 1.0 = just created, decays by half every DECAY_HALF_LIFE_DAYS."""
    try:
        created = datetime.fromisoformat(created_iso)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - created).total_seconds()
        age_days = max(age_seconds / 86400.0, 0)
        return math.pow(0.5, age_days / DECAY_HALF_LIFE_DAYS)
    except Exception:
        return 0.5


def detect_domains(text):
    """Return list of matching domain tags from text."""
    text_lower = text.lower()
    found = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                found.append(domain)
                break
    return found


def extract_keywords(text):
    """Extract simple keywords from text for matching."""
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    words = set(text.split())
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "about", "between",
        "through", "after", "before", "above", "below", "it", "its", "this",
        "that", "these", "those", "i", "me", "my", "we", "our", "you", "your",
        "he", "she", "they", "them", "and", "or", "but", "not", "no", "so",
        "if", "then", "than", "when", "what", "which", "who", "how", "all",
        "each", "every", "both", "few", "more", "most", "other", "some", "such",
        "only", "same", "just", "also", "very", "too", "any", "here", "there",
    }
    return words - stopwords


def find_related_nodes(conn, keywords, exclude_id=None):
    """Find existing nodes whose name or content shares keywords with the given set."""
    if not keywords:
        return []
    rows = conn.execute("SELECT id, name, content FROM nodes").fetchall()
    results = []
    for row in rows:
        if exclude_id and row["id"] == exclude_id:
            continue
        node_kw = extract_keywords(row["name"] + " " + (row["content"] or ""))
        overlap = keywords & node_kw
        if len(overlap) >= 1:
            score = len(overlap) / max(len(keywords), 1)
            results.append((row["id"], score))
    results.sort(key=lambda x: -x[1])
    return results[:10]


# ---------- CRUD Operations ----------

def add_node(data):
    """Add a node and auto-link to related existing nodes."""
    node_type = data.get("type", "CONCEPT").upper()
    if node_type not in VALID_NODE_TYPES:
        return {"error": "Invalid node type. Valid: " + ", ".join(sorted(VALID_NODE_TYPES))}, 400

    name = data.get("name", "").strip()
    if not name:
        return {"error": "name is required"}, 400

    content = data.get("content", "")
    tags = data.get("tags", [])
    ts = now_iso()
    combined_text = name + " " + content
    domains = data.get("domains", detect_domains(combined_text))
    emb_hash = compute_hash(combined_text)

    with _db_lock:
        conn = _get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO nodes (type, name, content, domains, tags, created, updated, embedding_hash) VALUES (?,?,?,?,?,?,?,?)",
                (node_type, name, content, json.dumps(domains), json.dumps(tags), ts, ts, emb_hash)
            )
            node_id = cur.lastrowid

            # Auto-link to related nodes
            keywords = extract_keywords(combined_text)
            related = find_related_nodes(conn, keywords, exclude_id=node_id)
            auto_edges = []
            for rel_id, score in related:
                if score >= 0.15:
                    weight = round(min(score * 2, 1.0), 3)
                    conn.execute(
                        "INSERT INTO edges (source_id, target_id, relation, weight, created) VALUES (?,?,?,?,?)",
                        (node_id, rel_id, "RELATES_TO", weight, ts)
                    )
                    auto_edges.append({"target_id": rel_id, "weight": weight})

            conn.commit()
            return {
                "id": node_id,
                "type": node_type,
                "name": name,
                "domains": domains,
                "auto_linked": auto_edges,
                "created": ts,
            }, 201
        finally:
            conn.close()


def link_nodes(data):
    """Manually link two nodes."""
    source_id = data.get("source_id")
    target_id = data.get("target_id")
    relation = data.get("relation", "RELATES_TO").upper()
    weight = float(data.get("weight", 1.0))

    if not source_id or not target_id:
        return {"error": "source_id and target_id are required"}, 400
    if relation not in VALID_RELATIONS:
        return {"error": "Invalid relation. Valid: " + ", ".join(sorted(VALID_RELATIONS))}, 400

    ts = now_iso()
    with _db_lock:
        conn = _get_conn()
        try:
            s = conn.execute("SELECT id FROM nodes WHERE id=?", (source_id,)).fetchone()
            t = conn.execute("SELECT id FROM nodes WHERE id=?", (target_id,)).fetchone()
            if not s or not t:
                return {"error": "One or both node IDs not found"}, 404

            conn.execute(
                "INSERT INTO edges (source_id, target_id, relation, weight, created) VALUES (?,?,?,?,?)",
                (source_id, target_id, relation, weight, ts)
            )
            conn.commit()
            return {"source_id": source_id, "target_id": target_id, "relation": relation, "weight": weight}, 201
        finally:
            conn.close()


def query_graph(q):
    """Natural language query - search nodes by keyword overlap."""
    if not q:
        return {"error": "q parameter required"}, 400

    keywords = extract_keywords(q)
    with _db_lock:
        conn = _get_conn()
        try:
            rows = conn.execute("SELECT * FROM nodes").fetchall()
            scored = []
            for row in rows:
                node_kw = extract_keywords(row["name"] + " " + (row["content"] or ""))
                overlap = keywords & node_kw
                if overlap:
                    kw_score = len(overlap) / max(len(keywords), 1)
                    rec = recency_score(row["created"])
                    combined = kw_score * 0.7 + rec * 0.3
                    node_dict = dict(row)
                    node_dict["score"] = round(combined, 4)
                    node_dict["recency"] = round(rec, 4)
                    node_dict["matched_keywords"] = list(overlap)
                    node_dict["domains"] = json.loads(node_dict.get("domains", "[]"))
                    node_dict["tags"] = json.loads(node_dict.get("tags", "[]"))
                    scored.append(node_dict)

            scored.sort(key=lambda x: -x["score"])
            return {"query": q, "results": scored[:20], "total_matches": len(scored)}, 200
        finally:
            conn.close()


def get_node(node_id):
    """Get a single node with all its edges."""
    with _db_lock:
        conn = _get_conn()
        try:
            row = conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
            if not row:
                return {"error": "Node not found"}, 404

            node = dict(row)
            node["domains"] = json.loads(node.get("domains", "[]"))
            node["tags"] = json.loads(node.get("tags", "[]"))
            node["recency"] = round(recency_score(node["created"]), 4)

            outgoing = conn.execute(
                "SELECT e.*, n.name as target_name, n.type as target_type FROM edges e JOIN nodes n ON e.target_id=n.id WHERE e.source_id=?",
                (node_id,)
            ).fetchall()
            incoming = conn.execute(
                "SELECT e.*, n.name as source_name, n.type as source_type FROM edges e JOIN nodes n ON e.source_id=n.id WHERE e.target_id=?",
                (node_id,)
            ).fetchall()

            node["outgoing"] = [dict(e) for e in outgoing]
            node["incoming"] = [dict(e) for e in incoming]
            return node, 200
        finally:
            conn.close()


def get_neighbors(node_id, depth=1):
    """BFS traversal to get neighborhood subgraph."""
    depth = min(int(depth), 5)
    with _db_lock:
        conn = _get_conn()
        try:
            root = conn.execute("SELECT id FROM nodes WHERE id=?", (node_id,)).fetchone()
            if not root:
                return {"error": "Node not found"}, 404

            visited = set()
            frontier = {node_id}
            all_nodes = {}
            all_edges = []

            for d in range(depth + 1):
                if not frontier:
                    break
                next_frontier = set()
                for nid in frontier:
                    if nid in visited:
                        continue
                    visited.add(nid)
                    row = conn.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()
                    if row:
                        nd = dict(row)
                        nd["domains"] = json.loads(nd.get("domains", "[]"))
                        nd["tags"] = json.loads(nd.get("tags", "[]"))
                        nd["depth"] = d
                        all_nodes[nid] = nd

                    if d < depth:
                        edges_out = conn.execute("SELECT * FROM edges WHERE source_id=?", (nid,)).fetchall()
                        edges_in = conn.execute("SELECT * FROM edges WHERE target_id=?", (nid,)).fetchall()
                        for e in edges_out:
                            all_edges.append(dict(e))
                            next_frontier.add(e["target_id"])
                        for e in edges_in:
                            all_edges.append(dict(e))
                            next_frontier.add(e["source_id"])

                frontier = next_frontier - visited

            # Deduplicate edges
            seen_edges = set()
            unique_edges = []
            for e in all_edges:
                key = (e["source_id"], e["target_id"], e["relation"])
                if key not in seen_edges:
                    seen_edges.add(key)
                    unique_edges.append(e)

            return {
                "root_id": node_id,
                "depth": depth,
                "nodes": list(all_nodes.values()),
                "edges": unique_edges,
                "node_count": len(all_nodes),
                "edge_count": len(unique_edges),
            }, 200
        finally:
            conn.close()


def get_timeline(topic):
    """Chronological view of nodes matching a topic."""
    if not topic:
        return {"error": "topic parameter required"}, 400

    keywords = extract_keywords(topic)
    with _db_lock:
        conn = _get_conn()
        try:
            rows = conn.execute("SELECT * FROM nodes ORDER BY created ASC").fetchall()
            matches = []
            for row in rows:
                node_kw = extract_keywords(row["name"] + " " + (row["content"] or ""))
                if keywords & node_kw:
                    nd = dict(row)
                    nd["domains"] = json.loads(nd.get("domains", "[]"))
                    nd["tags"] = json.loads(nd.get("tags", "[]"))
                    nd["recency"] = round(recency_score(nd["created"]), 4)
                    matches.append(nd)

            return {"topic": topic, "timeline": matches, "count": len(matches)}, 200
        finally:
            conn.close()


def get_stats():
    """Graph statistics."""
    with _db_lock:
        conn = _get_conn()
        try:
            node_count = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
            edge_count = conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]

            type_counts = {}
            for row in conn.execute("SELECT type, COUNT(*) as c FROM nodes GROUP BY type"):
                type_counts[row["type"]] = row["c"]

            relation_counts = {}
            for row in conn.execute("SELECT relation, COUNT(*) as c FROM edges GROUP BY relation"):
                relation_counts[row["relation"]] = row["c"]

            domain_counts = {}
            for row in conn.execute("SELECT domains FROM nodes"):
                for d in json.loads(row["domains"] or "[]"):
                    domain_counts[d] = domain_counts.get(d, 0) + 1

            recent = conn.execute("SELECT * FROM nodes ORDER BY updated DESC LIMIT 5").fetchall()
            recent_list = []
            for r in recent:
                nd = dict(r)
                nd["domains"] = json.loads(nd.get("domains", "[]"))
                nd["tags"] = json.loads(nd.get("tags", "[]"))
                recent_list.append(nd)

            return {
                "node_count": node_count,
                "edge_count": edge_count,
                "type_counts": type_counts,
                "relation_counts": relation_counts,
                "domain_counts": domain_counts,
                "recent_nodes": recent_list,
            }, 200
        finally:
            conn.close()


def delete_node(node_id):
    """Delete a node and its edges (CASCADE)."""
    with _db_lock:
        conn = _get_conn()
        try:
            row = conn.execute("SELECT id, name FROM nodes WHERE id=?", (node_id,)).fetchone()
            if not row:
                return {"error": "Node not found"}, 404
            name = row["name"]
            conn.execute("DELETE FROM edges WHERE source_id=? OR target_id=?", (node_id, node_id))
            conn.execute("DELETE FROM nodes WHERE id=?", (node_id,))
            conn.commit()
            return {"deleted": node_id, "name": name}, 200
        finally:
            conn.close()


# ---------- HTTP Handler ----------

class KGHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Knowledge Graph API."""

    def log_message(self, format, *args):
        # Suppress default logging
        pass

    def _send(self, body, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "http://localhost:9999")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(body, default=str).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self._send({}, 204)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        try:
            if path == "/health":
                self._send({"status": "ok", "service": "knowledge_graph", "port": PORT, "db": DB_PATH})

            elif path == "/kg/stats":
                body, status = get_stats()
                self._send(body, status)

            elif path == "/kg/query":
                q = params.get("q", [""])[0]
                body, status = query_graph(q)
                self._send(body, status)

            elif path == "/kg/timeline":
                topic = params.get("topic", [""])[0]
                body, status = get_timeline(topic)
                self._send(body, status)

            elif path.startswith("/kg/neighbors/"):
                try:
                    nid = int(path.split("/")[-1])
                except ValueError:
                    self._send({"error": "Invalid node ID"}, 400)
                    return
                depth = int(params.get("depth", ["1"])[0])
                body, status = get_neighbors(nid, depth)
                self._send(body, status)

            elif path.startswith("/kg/node/"):
                try:
                    nid = int(path.split("/")[-1])
                except ValueError:
                    self._send({"error": "Invalid node ID"}, 400)
                    return
                body, status = get_node(nid)
                self._send(body, status)

            else:
                self._send({"error": "Not found", "endpoints": [
                    "GET /health",
                    "GET /kg/stats",
                    "GET /kg/query?q=text",
                    "GET /kg/timeline?topic=X",
                    "GET /kg/node/<id>",
                    "GET /kg/neighbors/<id>?depth=N",
                    "POST /kg/add",
                    "POST /kg/link",
                    "DELETE /kg/node/<id>",
                ]}, 404)

        except Exception as e:
            self._send({"error": str(e)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            data = self._read_body()

            if path == "/kg/add":
                body, status = add_node(data)
                self._send(body, status)

            elif path == "/kg/link":
                body, status = link_nodes(data)
                self._send(body, status)

            else:
                self._send({"error": "Not found"}, 404)

        except json.JSONDecodeError:
            self._send({"error": "Invalid JSON"}, 400)
        except Exception as e:
            self._send({"error": str(e)}, 500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            if path.startswith("/kg/node/"):
                try:
                    nid = int(path.split("/")[-1])
                except ValueError:
                    self._send({"error": "Invalid node ID"}, 400)
                    return
                body, status = delete_node(nid)
                self._send(body, status)
            else:
                self._send({"error": "Not found"}, 404)

        except Exception as e:
            self._send({"error": str(e)}, 500)


# ---------- Main ----------

def main():
    init_db()
    server = HTTPServer(("127.0.0.1", PORT), KGHandler)
    print("[KnowledgeGraph] Service started on 127.0.0.1:%d" % PORT)
    print("[KnowledgeGraph] Database: %s" % DB_PATH)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[KnowledgeGraph] Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
