"""
NovaX Cascade Pipeline — FrugalGPT-style intelligent routing
Routes queries through escalating tiers based on confidence:

  Tier 1: NovaX LLM (235M ternary, FREE, ~50ms)
  Tier 2: Ollama local 7B (FREE, ~200ms)
  Tier 3: Cloud cheap (GPT-4o-mini, ~$0.15/M tokens)
  Tier 4: Cloud strong (Claude/GPT-4, ~$15/M tokens)

70-80% of queries handled at Tier 1-2 (FREE).
"""
import json, time, hashlib, requests

# ── Redis Cache (graceful fallback to dict) ───────────────
try:
    import redis
    _redis = redis.Redis(host="127.0.0.1", port=6379, db=0,
                         socket_connect_timeout=2, socket_timeout=2,
                         decode_responses=True)
    _redis.ping()
    _REDIS_OK = True
    print("[cascade] Redis connected at 127.0.0.1:6379")
except Exception:
    _redis = None
    _REDIS_OK = False
    print("[cascade] Redis unavailable -- using in-memory dict cache")

_DICT_CACHE = {}  # fallback: {key: (json_str, expire_ts)}
CACHE_TTL = 3600  # 1 hour


def _cache_key(prompt):
    return "cascade:" + hashlib.md5(prompt.encode("utf-8")).hexdigest()


def _cache_get(key):
    """Return cached JSON string or None."""
    if _REDIS_OK:
        try:
            val = _redis.get(key)
            if val:
                return val
        except Exception:
            pass
    # dict fallback
    entry = _DICT_CACHE.get(key)
    if entry:
        val, exp = entry
        if time.time() < exp:
            return val
        else:
            _DICT_CACHE.pop(key, None)
    return None


def _cache_set(key, value_str):
    """Store JSON string with TTL."""
    if _REDIS_OK:
        try:
            _redis.setex(key, CACHE_TTL, value_str)
            return
        except Exception:
            pass
    # dict fallback
    _DICT_CACHE[key] = (value_str, time.time() + CACHE_TTL)

# ── Tier Configuration ──────────────────────────────────────
TIERS = [
    {
        "name": "NovaX-LLM",
        "url": "http://127.0.0.1:9800/llm/generate",
        "cost_per_token": 0.0,
        "latency_ms": 50,
        "confidence_threshold": 0.7,  # Accept if confidence >= this
    },
    {
        "name": "Ollama-Local",
        "url": "http://127.0.0.1:11434/api/generate",
        "model": "llama3.2:latest",
        "cost_per_token": 0.0,
        "latency_ms": 200,
        "confidence_threshold": 0.5,
    },
    {
        "name": "Cloud-Cheap",
        "url": "http://127.0.0.1:9878/api/v1/query",
        "cost_per_token": 0.00000015,
        "latency_ms": 800,
        "confidence_threshold": 0.3,
        "params": {"prefer_free": True},
    },
    {
        "name": "Cloud-Strong",
        "url": "http://127.0.0.1:9878/api/v1/query",
        "cost_per_token": 0.000015,
        "latency_ms": 1500,
        "confidence_threshold": 0.0,  # Always accept (last resort)
        "params": {"prefer_free": False},
    },
]

# ── Route Classification ────────────────────────────────────
def get_route(prompt):
    """Get route classification from NovaX LLM."""
    try:
        r = requests.post("http://127.0.0.1:9800/llm/route",
                         json={"text": prompt}, timeout=3)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {"route": "ESCALATE", "confidence": 0.0}


def query_tier(tier, prompt, max_tokens=256):
    """Query a specific tier and return response + metadata."""
    t0 = time.time()
    try:
        if "Ollama" in tier["name"]:
            r = requests.post(tier["url"], json={
                "model": tier.get("model", "llama3.2:latest"),
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            }, timeout=30)
            if r.status_code == 200:
                data = r.json()
                return {
                    "response": data.get("response", ""),
                    "model": tier.get("model", "ollama"),
                    "tier": tier["name"],
                    "latency_ms": round((time.time() - t0) * 1000),
                    "cost": 0.0,
                }
        elif "NovaX" in tier["name"]:
            r = requests.post(tier["url"], json={
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "response": data.get("text", data.get("response", "")),
                    "model": "NovaX-LLM-v1",
                    "tier": tier["name"],
                    "latency_ms": round((time.time() - t0) * 1000),
                    "cost": 0.0,
                }
        else:
            # Cloud Router
            params = tier.get("params", {})
            r = requests.post(tier["url"], json={
                "prompt": prompt,
                "max_tokens": max_tokens,
                **params,
            }, timeout=30)
            if r.status_code == 200:
                data = r.json()
                response = data.get("response", "")
                tokens = len(response.split())
                return {
                    "response": response,
                    "model": data.get("model", "cloud"),
                    "tier": tier["name"],
                    "latency_ms": round((time.time() - t0) * 1000),
                    "cost": round(tokens * tier["cost_per_token"], 6),
                }
    except Exception as e:
        pass
    return None


def _score_structure(response):
    """Signal A: length + structure heuristic (original logic, refined)."""
    if not response or len(response) < 20:
        return 0.1
    if len(response) < 50:
        return 0.3
    score = 0.5
    if len(response) > 100:
        score += 0.1
    if "." in response:
        score += 0.1
    if any(c.isdigit() for c in response):
        score += 0.1
    if response.count("\n") > 2:
        score += 0.1
    return min(score, 1.0)


def _score_logit_confidence(tier_result):
    """Signal B: token probability confidence from model output (if available).
    Models that return logprobs/confidence get a real score;
    otherwise returns a neutral 0.5 so it doesn't skew the ensemble."""
    if not tier_result:
        return 0.5
    # Check various keys models might return
    conf = tier_result.get("confidence")
    if conf is not None:
        return float(max(0.0, min(1.0, conf)))
    logprob = tier_result.get("avg_logprob") or tier_result.get("logprob")
    if logprob is not None:
        # Convert log-prob to 0-1 range: e^logprob (logprob is negative)
        import math
        return max(0.0, min(1.0, math.exp(float(logprob))))
    return 0.5  # neutral when unavailable


def _score_keyword_relevance(prompt, response):
    """Signal C: does the response contain keywords from the query?"""
    if not prompt or not response:
        return 0.0
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "to",
                  "of", "and", "in", "that", "it", "for", "on", "with", "as",
                  "at", "by", "this", "from", "or", "but", "not", "do", "if",
                  "my", "me", "i", "you", "we", "what", "how", "can", "will"}
    words = [w.lower().strip("?.,!\"'") for w in prompt.split()]
    keywords = [w for w in words if len(w) > 2 and w not in stop_words]
    if not keywords:
        return 0.5  # neutral when no keywords extracted
    resp_lower = response.lower()
    hits = sum(1 for kw in keywords if kw in resp_lower)
    return hits / len(keywords)


# Ensemble weights (sum = 1.0)
_W_STRUCTURE = 0.40
_W_LOGIT = 0.30
_W_KEYWORD = 0.30


def quality_check(response, prompt="", tier_result=None):
    """3-signal ensemble quality scorer.
    Returns a float 0.0-1.0 combining:
      A) structure/length heuristic  (40%)
      B) logit confidence            (30%)
      C) keyword relevance           (30%)
    """
    s_struct = _score_structure(response)
    s_logit = _score_logit_confidence(tier_result)
    s_keyword = _score_keyword_relevance(prompt, response)
    combined = (_W_STRUCTURE * s_struct +
                _W_LOGIT * s_logit +
                _W_KEYWORD * s_keyword)
    return round(max(0.0, min(1.0, combined)), 4)


def _rag_augment(prompt, num_results=3):
    """Query Meilisearch via rag_pipeline and prepend context to prompt.
    Returns (augmented_prompt, sources_list)."""
    try:
        from rag_pipeline import meili_search
    except ImportError:
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from rag_pipeline import meili_search
        except ImportError:
            return prompt, []

    hits = meili_search(prompt, limit=num_results)
    if not hits:
        return prompt, []

    context_text = "\n\n".join([
        "[%s]: %s" % (doc.get("title", "Source"), doc.get("content", "")[:500])
        for doc in hits
    ])
    augmented = (
        "Use the following context to answer the question. "
        "If the context doesn't contain the answer, say so.\n\n"
        "Context:\n%s\n\n"
        "Question: %s\n\n"
        "Answer:" % (context_text, prompt)
    )
    sources = [{"title": d.get("title", ""), "id": d.get("id", "")}
               for d in hits]
    return augmented, sources


def cascade_query(prompt, max_tokens=256, max_tier=4):
    """Execute the cascade pipeline with Redis caching, RAG, and ensemble scoring.

    1. Check cache (Redis or dict) -- return instantly on hit
    2. If route=RETRIEVAL, prepend Meilisearch context via RAG
    3. Try each tier in order; accept when ensemble quality >= threshold
    4. Cache the final result with 1-hour TTL
    """
    # ── Cache check ──
    ck = _cache_key(prompt)
    cached = _cache_get(ck)
    if cached:
        try:
            result = json.loads(cached)
            result["cache_hit"] = True
            return result
        except Exception:
            pass

    route_info = get_route(prompt)

    # ── RAG augmentation for RETRIEVAL route ──
    effective_prompt = prompt
    rag_sources = []
    if route_info.get("route") == "RETRIEVAL":
        effective_prompt, rag_sources = _rag_augment(prompt, num_results=3)

    results = []

    # If route says DIRECT and we're confident, only try Tier 1
    if route_info["route"] == "DIRECT" and route_info["confidence"] > 0.5:
        max_tier = 1

    # If route says ESCALATE, skip to Tier 3
    start_tier = 0
    if route_info["route"] == "ESCALATE":
        start_tier = 2  # Skip local tiers

    for i in range(start_tier, min(max_tier, len(TIERS))):
        tier = TIERS[i]
        result = query_tier(tier, effective_prompt, max_tokens)

        if result and result["response"]:
            quality = quality_check(result["response"],
                                    prompt=prompt,
                                    tier_result=result)
            result["quality_score"] = round(quality, 4)
            results.append(result)

            # Accept if quality exceeds threshold
            if quality >= tier["confidence_threshold"]:
                result["route_info"] = route_info
                result["tiers_tried"] = len(results)
                result["total_cost"] = sum(r.get("cost", 0) for r in results)
                if rag_sources:
                    result["rag_sources"] = rag_sources
                result["cache_hit"] = False
                _cache_set(ck, json.dumps(result))
                return result

    # Return best result found (or error)
    if results:
        best = max(results, key=lambda r: r.get("quality_score", 0))
        best["route_info"] = route_info
        best["tiers_tried"] = len(results)
        best["total_cost"] = sum(r.get("cost", 0) for r in results)
        if rag_sources:
            best["rag_sources"] = rag_sources
        best["cache_hit"] = False
        _cache_set(ck, json.dumps(best))
        return best

    return {
        "response": "All tiers failed to respond.",
        "tier": "NONE",
        "error": True,
        "route_info": route_info,
        "cache_hit": False,
    }


# ── HTTP Server (port 9803) ─────────────────────────────────
import http.server

class CascadeHandler(http.server.BaseHTTPRequestHandler):
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
            self._json(200, {
                "service": "NovaX Cascade Pipeline",
                "tiers": len(TIERS),
                "tier_names": [t["name"] for t in TIERS],
                "cache": "redis" if _REDIS_OK else "dict",
                "cache_ttl": CACHE_TTL,
                "quality_scorer": "3-signal-ensemble",
                "rag_enabled": True,
                "ternary": 1,
            })
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        if self.path == "/cascade/query":
            prompt = body.get("prompt", "")
            if not prompt:
                self._json(400, {"error": "No prompt provided"})
                return
            result = cascade_query(
                prompt,
                max_tokens=body.get("max_tokens", 256),
                max_tier=body.get("max_tier", 4),
            )
            self._json(200, result)
        elif self.path == "/cascade/route":
            text = body.get("text", "") or body.get("prompt", "")
            result = get_route(text) if text else {"error": "No text"}
            self._json(200, result)
        else:
            self._json(404, {"error": "Not found"})


def main():
    PORT = 9803
    print("=" * 50)
    print("  NovaX Cascade Pipeline — Port", PORT)
    print("=" * 50)
    print("  Cache : %s (TTL %ds)" % ("Redis 127.0.0.1:6379" if _REDIS_OK else "in-memory dict", CACHE_TTL))
    print("  Scorer: 3-signal ensemble (structure %.0f%% / logit %.0f%% / keyword %.0f%%)" % (
        _W_STRUCTURE * 100, _W_LOGIT * 100, _W_KEYWORD * 100))
    print("  RAG   : Meilisearch 127.0.0.1:7700 (RETRIEVAL route)")
    print("  Tiers : %d" % len(TIERS))
    for t in TIERS:
        print("    %-15s | threshold: %.1f | cost: $%.2f/M tok" % (
            t["name"], t["confidence_threshold"], t["cost_per_token"] * 1e6))
    print("\nEndpoints:")
    print("  POST /cascade/query  -- intelligent cascaded query")
    print("  POST /cascade/route  -- route classification only")
    print("  GET  /health         -- service health")
    print()

    server = http.server.HTTPServer(("127.0.0.1", PORT), CascadeHandler)
    print(f"  Listening on http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
