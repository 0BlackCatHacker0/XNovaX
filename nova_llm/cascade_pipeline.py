"""
NovaX Cascade Pipeline — FrugalGPT-style intelligent routing
Routes queries through escalating tiers based on confidence:

  Tier 1: NovaX LLM (235M ternary, FREE, ~50ms)
  Tier 2: Ollama local 7B (FREE, ~200ms)
  Tier 3: Cloud cheap (GPT-4o-mini, ~$0.15/M tokens)
  Tier 4: Cloud strong (Claude/GPT-4, ~$15/M tokens)

70-80% of queries handled at Tier 1-2 (FREE).
"""
import json, time, requests

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


def quality_check(response):
    """Basic quality assessment of a response."""
    if not response or len(response) < 20:
        return 0.1
    if len(response) < 50:
        return 0.3
    # Simple heuristics — will be replaced by learned quality scorer
    score = 0.5
    if len(response) > 100:
        score += 0.1
    if "." in response:  # Has sentences
        score += 0.1
    if any(c.isdigit() for c in response):  # Has numbers (factual)
        score += 0.1
    if response.count("\n") > 2:  # Structured response
        score += 0.1
    return min(score, 1.0)


def cascade_query(prompt, max_tokens=256, max_tier=4):
    """Execute the cascade pipeline.

    Tries each tier in order. Accepts the response if quality
    exceeds the tier's confidence threshold. Otherwise escalates.

    Returns the best response found with full metadata.
    """
    route_info = get_route(prompt)
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
        result = query_tier(tier, prompt, max_tokens)

        if result and result["response"]:
            quality = quality_check(result["response"])
            result["quality_score"] = round(quality, 3)
            results.append(result)

            # Accept if quality exceeds threshold
            if quality >= tier["confidence_threshold"]:
                result["route_info"] = route_info
                result["tiers_tried"] = len(results)
                result["total_cost"] = sum(r.get("cost", 0) for r in results)
                return result

    # Return best result found (or error)
    if results:
        best = max(results, key=lambda r: r.get("quality_score", 0))
        best["route_info"] = route_info
        best["tiers_tried"] = len(results)
        best["total_cost"] = sum(r.get("cost", 0) for r in results)
        return best

    return {
        "response": "All tiers failed to respond.",
        "tier": "NONE",
        "error": True,
        "route_info": route_info,
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
    print(f"  Tiers: {len(TIERS)}")
    for t in TIERS:
        print(f"    {t['name']:15s} | threshold: {t['confidence_threshold']:.1f} | cost: ${t['cost_per_token']*1e6:.2f}/M tok")
    print(f"\nEndpoints:")
    print(f"  POST /cascade/query  -- intelligent cascaded query")
    print(f"  POST /cascade/route  -- route classification only")
    print(f"  GET  /health         -- service health")
    print()

    server = http.server.HTTPServer(("127.0.0.1", PORT), CascadeHandler)
    print(f"  Listening on http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
