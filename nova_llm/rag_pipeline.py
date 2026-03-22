"""
NovaX RAG Pipeline — Retrieval-Augmented Generation
Connects the 235M ternary LLM to Meilisearch (port 7700) for
unlimited knowledge without memorization.

"A 235M model that can reliably retrieve is more useful than
a 70B model that tries to memorize everything."

Endpoints (port 9804):
  POST /rag/query    -- RAG-augmented query (retrieve + generate)
  POST /rag/index    -- Index documents into Meilisearch
  POST /rag/search   -- Search-only (no generation)
  GET  /rag/stats    -- Index statistics
  GET  /health       -- Service health
"""
import json, time, hashlib, requests, http.server
from pathlib import Path

MEILI_URL = "http://127.0.0.1:7700"
MEILI_INDEX = "novax_knowledge"
LLM_URL = "http://127.0.0.1:9800/llm/generate"
ROUTE_URL = "http://127.0.0.1:9800/llm/route"

# ── Meilisearch Operations ──────────────────────────────────
def meili_search(query, limit=5):
    """Search Meilisearch for relevant documents."""
    try:
        r = requests.post(f"{MEILI_URL}/indexes/{MEILI_INDEX}/search", json={
            "q": query,
            "limit": limit,
            "attributesToRetrieve": ["id", "title", "content", "domain", "source"],
        }, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return data.get("hits", [])
    except:
        pass
    return []


def meili_index_doc(doc):
    """Index a single document into Meilisearch."""
    if "id" not in doc:
        doc["id"] = hashlib.md5(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:12]
    try:
        r = requests.post(f"{MEILI_URL}/indexes/{MEILI_INDEX}/documents",
                         json=[doc], timeout=5)
        return r.status_code in (200, 202)
    except:
        return False


def meili_index_batch(docs):
    """Index a batch of documents."""
    for doc in docs:
        if "id" not in doc:
            doc["id"] = hashlib.md5(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:12]
    try:
        r = requests.post(f"{MEILI_URL}/indexes/{MEILI_INDEX}/documents",
                         json=docs, timeout=30)
        return r.status_code in (200, 202)
    except:
        return False


def meili_stats():
    """Get index statistics."""
    try:
        r = requests.get(f"{MEILI_URL}/indexes/{MEILI_INDEX}/stats", timeout=3)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {"numberOfDocuments": 0, "isIndexing": False}


def ensure_index():
    """Create the index if it doesn't exist."""
    try:
        requests.post(f"{MEILI_URL}/indexes", json={
            "uid": MEILI_INDEX,
            "primaryKey": "id"
        }, timeout=5)
        # Set searchable attributes
        requests.put(f"{MEILI_URL}/indexes/{MEILI_INDEX}/settings/searchable-attributes",
                    json=["title", "content", "domain"], timeout=5)
    except:
        pass


# ── RAG Query ───────────────────────────────────────────────
def should_retrieve(query):
    """Decide if a query needs retrieval (factual) or can be answered directly."""
    try:
        r = requests.post(ROUTE_URL, json={"text": query}, timeout=3)
        if r.status_code == 200:
            route = r.json()
            return route.get("route") == "RETRIEVAL"
    except:
        pass
    # Fallback: keyword heuristics
    q = query.lower()
    retrieval_signals = ["who", "what year", "when", "where", "how many",
                        "definition of", "explain", "describe", "history of"]
    return any(q.startswith(s) or s in q for s in retrieval_signals)


def rag_query(query, max_tokens=256, num_results=3):
    """Full RAG pipeline: retrieve context, then generate with context."""
    t0 = time.time()

    # Step 1: Decide if retrieval is needed
    needs_retrieval = should_retrieve(query)

    context_docs = []
    if needs_retrieval:
        # Step 2: Search for relevant documents
        context_docs = meili_search(query, limit=num_results)

    # Step 3: Build augmented prompt
    if context_docs:
        context_text = "\n\n".join([
            f"[{doc.get('title', 'Source')}]: {doc.get('content', '')[:500]}"
            for doc in context_docs
        ])
        augmented_prompt = (
            f"Use the following context to answer the question. "
            f"If the context doesn't contain the answer, say so.\n\n"
            f"Context:\n{context_text}\n\n"
            f"Question: {query}\n\n"
            f"Answer:"
        )
    else:
        augmented_prompt = query

    # Step 4: Generate response using LLM
    try:
        r = requests.post(LLM_URL, json={
            "prompt": augmented_prompt,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "cfg_scale": 1.5,  # Use CFG for quality boost
        }, timeout=30)
        if r.status_code == 200:
            llm_result = r.json()
        else:
            llm_result = {"text": "LLM unavailable", "error": True}
    except:
        llm_result = {"text": "LLM unavailable", "error": True}

    elapsed = time.time() - t0

    return {
        "response": llm_result.get("text", ""),
        "retrieved": needs_retrieval,
        "num_sources": len(context_docs),
        "sources": [{"title": d.get("title", ""), "id": d.get("id", "")}
                    for d in context_docs],
        "model": llm_result.get("model", "NovaX-LLM"),
        "elapsed_ms": round(elapsed * 1000, 1),
        "tokens_generated": llm_result.get("tokens_generated", 0),
        "ternary": 1,
    }


# ── Index Training Data ────────────────────────────────────
def index_training_data(path=None):
    """Index existing training data into Meilisearch for RAG."""
    if path is None:
        path = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")

    if not path.exists():
        print(f"  Training data not found at {path}")
        return 0

    data = json.load(open(path, "r", encoding="utf-8"))
    docs = []
    for i, pair in enumerate(data):
        docs.append({
            "id": f"train_{i}",
            "title": pair.get("prompt", "")[:100],
            "content": pair.get("response", ""),
            "domain": pair.get("domain", "general"),
            "source": pair.get("model", "unknown"),
        })

    # Batch index in chunks of 500
    indexed = 0
    for i in range(0, len(docs), 500):
        batch = docs[i:i+500]
        if meili_index_batch(batch):
            indexed += len(batch)
            print(f"  Indexed {indexed}/{len(docs)} documents...")

    print(f"  Total indexed: {indexed}")
    return indexed


# ── HTTP Server (port 9804) ─────────────────────────────────
class RAGHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/health", "/status"):
            stats = meili_stats()
            self._json(200, {
                "service": "NovaX RAG Pipeline",
                "meili_docs": stats.get("numberOfDocuments", 0),
                "meili_indexing": stats.get("isIndexing", False),
                "ternary": 1,
            })
        elif self.path == "/rag/stats":
            self._json(200, meili_stats())
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        if self.path == "/rag/query":
            query = body.get("query", "") or body.get("prompt", "")
            if not query:
                self._json(400, {"error": "No query provided"})
                return
            result = rag_query(
                query,
                max_tokens=body.get("max_tokens", 256),
                num_results=body.get("num_results", 3),
            )
            self._json(200, result)

        elif self.path == "/rag/search":
            query = body.get("query", "")
            if not query:
                self._json(400, {"error": "No query provided"})
                return
            hits = meili_search(query, limit=body.get("limit", 5))
            self._json(200, {"hits": hits, "count": len(hits)})

        elif self.path == "/rag/index":
            docs = body.get("documents", [])
            if not docs:
                self._json(400, {"error": "No documents provided"})
                return
            success = meili_index_batch(docs)
            self._json(200, {"indexed": len(docs), "success": success})

        else:
            self._json(404, {"error": "Not found"})


def main():
    PORT = 9804
    print("=" * 50)
    print("  NovaX RAG Pipeline — Port", PORT)
    print("=" * 50)

    # Ensure index exists
    ensure_index()
    stats = meili_stats()
    print(f"  Meilisearch: {stats.get('numberOfDocuments', 0)} documents indexed")

    # Index training data if empty
    if stats.get("numberOfDocuments", 0) == 0:
        print(f"  Indexing training data into Meilisearch...")
        count = index_training_data()
        print(f"  Done: {count} documents")

    print(f"\nEndpoints:")
    print(f"  POST /rag/query   -- RAG-augmented query")
    print(f"  POST /rag/search  -- search only")
    print(f"  POST /rag/index   -- index documents")
    print(f"  GET  /rag/stats   -- index statistics")
    print(f"  GET  /health      -- service health")
    print()

    server = http.server.HTTPServer(("127.0.0.1", PORT), RAGHandler)
    print(f"  Listening on http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "index":
        ensure_index()
        index_training_data()
    else:
        main()
