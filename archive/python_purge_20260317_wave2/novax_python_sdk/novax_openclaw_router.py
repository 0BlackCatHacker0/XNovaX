"""
novax_openclaw_router.py — AI Router for NovaX
Routes requests to OpenClaw (Claude Sonnet) or Ollama based on task classification.

Place in: C:\NovaX\novax\novax_openclaw_router.py

Architecture:
  User Request → Router → classify_task() → route to best AI
    ├── Complex reasoning, code, analysis → OpenClaw (Claude Sonnet 4.5)
    ├── Quick chat, simple Q&A → Ollama (llama3/mistral)
    └── Vision tasks → Ollama (llava)

OpenClaw runs on port 18789 with WebSocket + RPC.
Ollama runs on port 11434 with REST API.
"""

import json
import logging
import time
import urllib.request
import urllib.error

log = logging.getLogger("novax.router")

# ============================================================
#  CONFIG
# ============================================================

OPENCLAW_HOST = "http://127.0.0.1:18789"
OLLAMA_HOST = "http://127.0.0.1:11434"

# Task keywords that should go to Claude (complex reasoning)
CLAUDE_KEYWORDS = [
    "code", "debug", "fix", "refactor", "architect", "design",
    "analyze", "explain", "write", "essay", "report", "document",
    "plan", "strategy", "review", "compare", "evaluate",
    "python", "javascript", "typescript", "rust", "html", "css",
    "sql", "api", "server", "deploy", "docker", "kubernetes",
    "xrpl", "blockchain", "smart contract", "token",
    "nova", "novax", "openclaw", "bridge", "brain",
    "complex", "detailed", "thorough", "comprehensive",
]

# Task keywords that should stay with Ollama (quick/local)
OLLAMA_KEYWORDS = [
    "quick", "simple", "hello", "hi", "hey", "what time",
    "weather", "joke", "trivia", "translate", "summarize short",
    "image", "picture", "photo", "describe image", "vision",
]

# ============================================================
#  HEALTH CHECKS
# ============================================================

def check_openclaw_health():
    """Check if OpenClaw gateway is healthy."""
    try:
        req = urllib.request.Request(
            f"{OPENCLAW_HOST}/__openclaw__/health",
            method="GET"
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


def check_ollama_health():
    """Check if Ollama is healthy."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/tags",
            method="GET"
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


def get_health_status():
    """Get health of both AI backends."""
    return {
        "openclaw": check_openclaw_health(),
        "ollama": check_ollama_health(),
        "timestamp": time.time(),
    }


# ============================================================
#  TASK CLASSIFICATION
# ============================================================

def classify_task(prompt: str) -> str:
    """
    Classify a prompt to determine which AI backend to use.
    Returns: "openclaw" or "ollama"
    """
    prompt_lower = prompt.lower().strip()

    # Check for explicit routing directives
    if prompt_lower.startswith("/claude") or prompt_lower.startswith("/sonnet"):
        return "openclaw"
    if prompt_lower.startswith("/ollama") or prompt_lower.startswith("/local"):
        return "ollama"
    if prompt_lower.startswith("/llama"):
        return "ollama"

    # Score based on keywords
    claude_score = sum(1 for kw in CLAUDE_KEYWORDS if kw in prompt_lower)
    ollama_score = sum(1 for kw in OLLAMA_KEYWORDS if kw in prompt_lower)

    # Long prompts (>200 chars) likely need deeper reasoning
    if len(prompt) > 200:
        claude_score += 2

    # Code blocks strongly suggest Claude
    if "```" in prompt or "def " in prompt or "function " in prompt:
        claude_score += 3

    # Default: Claude for anything non-trivial
    if claude_score > ollama_score:
        return "openclaw"
    elif ollama_score > claude_score:
        return "ollama"
    else:
        # Tie or no keywords — default to Claude for quality
        return "openclaw"


# ============================================================
#  SEND TO OPENCLAW (via HTTP RPC)
# ============================================================

def send_to_openclaw(prompt: str, session: str = "novax") -> dict:
    """
    Send a message to OpenClaw's WebChat RPC endpoint.
    Returns: {"text": "response", "model": "claude-sonnet-4-5", "source": "openclaw"}
    """
    try:
        # Get gateway token from config
        import subprocess
        token = subprocess.check_output(
            ["openclaw", "config", "get", "gateway.auth.token"],
            timeout=5, text=True
        ).strip()

        # Use the chat.send RPC method
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": int(time.time()),
            "method": "chat.send",
            "params": {
                "session": session,
                "message": prompt,
                "agent": "main",
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OPENCLAW_HOST}/__openclaw__/api/rpc",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST"
        )

        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read().decode("utf-8"))

        if "result" in data:
            return {
                "text": data["result"].get("text", ""),
                "model": "claude-sonnet-4-5",
                "source": "openclaw",
                "duration_ms": data["result"].get("durationMs", 0),
            }
        elif "error" in data:
            return {
                "text": f"OpenClaw error: {data['error'].get('message', 'unknown')}",
                "model": "claude-sonnet-4-5",
                "source": "openclaw",
                "error": True,
            }

    except Exception as e:
        log.error(f"OpenClaw request failed: {e}")
        return {
            "text": f"OpenClaw unavailable: {e}",
            "model": "claude-sonnet-4-5",
            "source": "openclaw",
            "error": True,
        }


# ============================================================
#  SEND TO OLLAMA
# ============================================================

def send_to_ollama(prompt: str, model: str = "llama3") -> dict:
    """
    Send a message to Ollama's REST API.
    Returns: {"text": "response", "model": "llama3", "source": "ollama"}
    """
    try:
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read().decode("utf-8"))

        return {
            "text": data.get("response", ""),
            "model": model,
            "source": "ollama",
            "duration_ms": int(data.get("total_duration", 0) / 1_000_000),
        }

    except Exception as e:
        log.error(f"Ollama request failed: {e}")
        return {
            "text": f"Ollama unavailable: {e}",
            "model": model,
            "source": "ollama",
            "error": True,
        }


# ============================================================
#  UNIFIED ROUTE FUNCTION
# ============================================================

def route_request(prompt: str, force_backend: str = None) -> dict:
    """
    Main entry point. Routes a prompt to the best available AI.

    Args:
        prompt: The user's message
        force_backend: "openclaw" or "ollama" to override auto-routing

    Returns: dict with text, model, source, duration_ms
    """
    # Determine target
    if force_backend:
        target = force_backend
    else:
        target = classify_task(prompt)

    log.info(f"Routing to {target}: {prompt[:80]}...")

    # Check health and failover
    health = get_health_status()

    if target == "openclaw":
        if health["openclaw"]:
            result = send_to_openclaw(prompt)
            if not result.get("error"):
                return result
            # Fallback to Ollama on error
            log.warning("OpenClaw returned error, falling back to Ollama")

        if health["ollama"]:
            log.warning("OpenClaw unavailable, routing to Ollama")
            return send_to_ollama(prompt)
        else:
            return {"text": "All AI backends unavailable.", "source": "none", "error": True}

    elif target == "ollama":
        if health["ollama"]:
            result = send_to_ollama(prompt)
            if not result.get("error"):
                return result
            log.warning("Ollama returned error, falling back to OpenClaw")

        if health["openclaw"]:
            log.warning("Ollama unavailable, routing to OpenClaw")
            return send_to_openclaw(prompt)
        else:
            return {"text": "All AI backends unavailable.", "source": "none", "error": True}

    return {"text": "Unknown routing target.", "source": "none", "error": True}


# ============================================================
#  CLI TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("NovaX-OpenClaw Router Test")
    print("=" * 40)

    # Health check
    health = get_health_status()
    print(f"OpenClaw: {'OK' if health['openclaw'] else 'OFFLINE'}")
    print(f"Ollama:   {'OK' if health['ollama'] else 'OFFLINE'}")
    print()

    # Test routing
    test_prompts = [
        "hello",
        "write a python function that sorts a list of dictionaries by a key",
        "/claude explain the XRPL consensus mechanism",
        "/ollama what's 2+2",
        "analyze this code and find the bug",
    ]

    for p in test_prompts:
        target = classify_task(p)
        print(f"  [{target:>8}] {p[:60]}")

    print()
    print("Send test message? (y/n): ", end="")
    if input().strip().lower() == "y":
        result = route_request("Say hello in one sentence.")
        print(f"\nResponse from {result['source']}:")
        print(f"  {result['text']}")
