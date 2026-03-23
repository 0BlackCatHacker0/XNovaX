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
TRAINING_DATA_PATH = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")
MAX_INDEX_DOCS = 10000  # cap for initial indexing

# Track hybrid search capability
_hybrid_available = None  # None = not checked, True/False = result

# ── Meilisearch Operations ──────────────────────────────────
def check_hybrid_support():
    """Check if Meilisearch has vector search / hybrid enabled."""
    global _hybrid_available
    if _hybrid_available is not None:
        return _hybrid_available
    try:
        r = requests.get(f"{MEILI_URL}/experimental-features", timeout=3)
        if r.status_code == 200:
            feats = r.json()
            _hybrid_available = feats.get("vectorStore", False)
            if not _hybrid_available:
                # Try to enable it
                r2 = requests.patch(f"{MEILI_URL}/experimental-features",
                                    json={"vectorStore": True}, timeout=5)
                if r2.status_code == 200:
                    feats2 = r2.json()
                    _hybrid_available = feats2.get("vectorStore", False)
                    if _hybrid_available:
                        print("  [RAG] Enabled Meilisearch vector store for hybrid search")
            return _hybrid_available
    except Exception:
        pass
    _hybrid_available = False
    return False


def configure_embedders():
    """Configure Meilisearch embedders for hybrid search."""
    try:
        r = requests.patch(
            f"{MEILI_URL}/indexes/{MEILI_INDEX}/settings",
            json={
                "embedders": {
                    "default": {
                        "source": "huggingFace",
                        "model": "sentence-transformers/all-MiniLM-L6-v2",
                        "documentTemplate": "{{doc.title}} {{doc.content}}",
                    }
                }
            },
            timeout=10,
        )
        if r.status_code in (200, 202):
            print("  [RAG] Configured HuggingFace embedder for hybrid search")
            return True
    except Exception:
        pass
    return False


def meili_search(query, limit=5, semantic_ratio=0.5):
    """Search Meilisearch using hybrid search if available, else keyword."""
    search_body = {
        "q": query,
        "limit": limit,
        "attributesToRetrieve": ["id", "title", "content", "domain", "source"],
    }

    # Try hybrid search first
    use_hybrid = check_hybrid_support()
    if use_hybrid:
        search_body["hybrid"] = {"semanticRatio": semantic_ratio, "embedder": "default"}

    try:
        r = requests.post(f"{MEILI_URL}/indexes/{MEILI_INDEX}/search",
                          json=search_body, timeout=10)
        if r.status_code == 200:
            data = r.json()
            hits = data.get("hits", [])
            # Tag hits with search mode
            mode = "hybrid" if use_hybrid else "keyword"
            for h in hits:
                h["_searchMode"] = mode
            return hits
        elif r.status_code == 400 and use_hybrid:
            # Hybrid not configured properly -- fall back to keyword
            search_body.pop("hybrid", None)
            r2 = requests.post(f"{MEILI_URL}/indexes/{MEILI_INDEX}/search",
                               json=search_body, timeout=5)
            if r2.status_code == 200:
                hits = r2.json().get("hits", [])
                for h in hits:
                    h["_searchMode"] = "keyword_fallback"
                return hits
    except Exception:
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
    """Create the index if it doesn't exist, configure settings and embedders."""
    try:
        requests.post(f"{MEILI_URL}/indexes", json={
            "uid": MEILI_INDEX,
            "primaryKey": "id"
        }, timeout=5)
        # Set searchable + filterable attributes
        requests.patch(f"{MEILI_URL}/indexes/{MEILI_INDEX}/settings", json={
            "searchableAttributes": ["title", "content", "domain"],
            "filterableAttributes": ["domain", "source"],
            "sortableAttributes": ["domain"],
        }, timeout=5)
    except Exception:
        pass
    # Enable hybrid search if possible
    if check_hybrid_support():
        configure_embedders()


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

    search_mode = context_docs[0].get("_searchMode", "none") if context_docs else "none"
    return {
        "response": llm_result.get("text", ""),
        "retrieved": needs_retrieval,
        "num_sources": len(context_docs),
        "sources": [{"title": d.get("title", ""), "id": d.get("id", "")}
                    for d in context_docs],
        "searchMode": search_mode,
        "model": llm_result.get("model", "NovaX-LLM"),
        "elapsed_ms": round(elapsed * 1000, 1),
        "tokens_generated": llm_result.get("tokens_generated", 0),
        "ternary": 1,
    }


# ── Index Training Data ────────────────────────────────────
def index_training_data(path=None, max_docs=None):
    """Index existing training data into Meilisearch for RAG.

    Args:
        path: Path to training JSON. Defaults to TRAINING_DATA_PATH.
        max_docs: Cap on documents to index. Defaults to MAX_INDEX_DOCS.

    Returns:
        dict with indexed count, total available, and any errors.
    """
    if path is None:
        path = TRAINING_DATA_PATH
    else:
        path = Path(path)
    if max_docs is None:
        max_docs = MAX_INDEX_DOCS

    result = {"indexed": 0, "total_available": 0, "errors": [], "path": str(path)}

    if not path.exists():
        result["errors"].append(f"Training data not found at {path}")
        print(f"  [RAG] Training data not found at {path}")
        return result

    try:
        data = json.load(open(path, "r", encoding="utf-8"))
    except Exception as e:
        result["errors"].append(f"Failed to parse JSON: {e}")
        return result

    result["total_available"] = len(data)

    # Cap to max_docs
    if max_docs and len(data) > max_docs:
        data = data[:max_docs]
        print(f"  [RAG] Capping index to {max_docs} of {result['total_available']} pairs")

    docs = []
    for i, pair in enumerate(data):
        prompt = pair.get("prompt", "") or ""
        response = pair.get("response", "") or ""
        if not response.strip():
            continue  # skip empty responses
        docs.append({
            "id": f"train_{i}",
            "title": prompt[:100],
            "content": response,
            "domain": pair.get("domain", "general"),
            "source": pair.get("model", "unknown"),
        })

    # Batch index in chunks of 500
    indexed = 0
    for i in range(0, len(docs), 500):
        batch = docs[i:i+500]
        if meili_index_batch(batch):
            indexed += len(batch)
            if indexed % 2000 == 0 or i + 500 >= len(docs):
                print(f"  [RAG] Indexed {indexed}/{len(docs)} documents...")
        else:
            result["errors"].append(f"Batch at offset {i} failed")

    result["indexed"] = indexed
    print(f"  [RAG] Total indexed: {indexed}")
    return result


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
                "version": "2.0-hybrid",
                "meili_docs": stats.get("numberOfDocuments", 0),
                "meili_indexing": stats.get("isIndexing", False),
                "hybrid_search": check_hybrid_support(),
                "ternary": 1,
            })
        elif self.path == "/rag/stats":
            stats = meili_stats()
            hybrid = check_hybrid_support()
            self._json(200, {
                "numberOfDocuments": stats.get("numberOfDocuments", 0),
                "isIndexing": stats.get("isIndexing", False),
                "fieldDistribution": stats.get("fieldDistribution", {}),
                "hybridSearch": hybrid,
                "searchMode": "hybrid" if hybrid else "keyword",
                "index": MEILI_INDEX,
                "meiliUrl": MEILI_URL,
            })
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
            ratio = body.get("semantic_ratio", 0.5)
            hits = meili_search(query, limit=body.get("limit", 5),
                                semantic_ratio=ratio)
            search_mode = hits[0].get("_searchMode", "keyword") if hits else "unknown"
            self._json(200, {
                "hits": hits,
                "count": len(hits),
                "searchMode": search_mode,
                "hybridAvailable": check_hybrid_support(),
            })

        elif self.path == "/rag/index":
            docs = body.get("documents", [])
            if docs:
                # Index provided documents
                success = meili_index_batch(docs)
                self._json(200, {"indexed": len(docs), "success": success,
                                  "mode": "documents"})
            else:
                # Trigger reindex from training data
                import threading
                max_docs = body.get("max_docs", MAX_INDEX_DOCS)
                path = body.get("path", None)
                def _reindex():
                    ensure_index()
                    index_training_data(path=path, max_docs=max_docs)
                t = threading.Thread(target=_reindex, daemon=True)
                t.start()
                self._json(202, {
                    "status": "reindex_started",
                    "max_docs": max_docs,
                    "source": str(path or TRAINING_DATA_PATH),
                    "message": "Reindexing in background. Check /rag/stats for progress.",
                })

        else:
            self._json(404, {"error": "Not found"})


def main():
    PORT = 9804
    print("=" * 50)
    print("  NovaX RAG Pipeline v2.0 (Hybrid Search)")
    print("  Port:", PORT)
    print("=" * 50)

    # Ensure index exists and configure embedders
    ensure_index()
    stats = meili_stats()
    doc_count = stats.get("numberOfDocuments", 0)
    hybrid = check_hybrid_support()
    print(f"  Meilisearch: {doc_count} documents indexed")
    print(f"  Search mode: {'hybrid (semantic+keyword)' if hybrid else 'keyword only'}")

    # Index training data if empty
    if doc_count == 0:
        print(f"  Indexing training data into Meilisearch...")
        result = index_training_data()
        print(f"  Done: {result['indexed']} documents (of {result['total_available']} available)")

    print(f"\nEndpoints:")
    print(f"  POST /rag/query   -- RAG-augmented query (retrieve + generate)")
    print(f"  POST /rag/search  -- hybrid search (keyword + semantic)")
    print(f"  POST /rag/index   -- index docs or trigger reindex from training data")
    print(f"  GET  /rag/stats   -- index statistics + hybrid status")
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
