"""
NovaX AI Proxy - Routes AI requests through bridge.
Tries Brain (9990) first, falls back to Ollama (11434).
Solves CORS: voice terminal -> bridge:9999/api/ai -> brain/ollama
"""
import json, urllib.request, urllib.error, time, logging

log = logging.getLogger("NovaX.AIProxy")

BRAIN_URL = "http://127.0.0.1:9990/v1/chat/completions"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODELS = ["gemma2:latest", "codestral:latest", "llava:latest"]
PREFERRED_MODEL = "gemma2:latest"

SYSTEM_PROMPT = "You are Nova, a helpful female AI assistant with a warm personality. Keep responses concise and natural for voice conversation. Max 2-3 sentences."

last_brain_ok = 0
last_ollama_ok = 0

def chat(user_message, system=None, model=None):
    """Route chat to best available AI. Returns dict with response."""
    global last_brain_ok, last_ollama_ok
    sys_msg = system or SYSTEM_PROMPT
    
    # Try Brain first
    try:
        body = json.dumps({
            "model": "local",
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": 200
        }).encode()
        req = urllib.request.Request(BRAIN_URL, data=body,
            headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if text:
            last_brain_ok = time.time()
            return {"ok": True, "source": "brain", "response": text}
    except Exception as e:
        log.debug("Brain failed: " + str(e))
    
    # Fallback to Ollama
    try:
        mdl = model or PREFERRED_MODEL
        body = json.dumps({
            "model": mdl,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_message}
            ],
            "stream": False
        }).encode()
        req = urllib.request.Request(OLLAMA_URL, data=body,
            headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        text = data.get("message", {}).get("content", "")
        if text:
            last_ollama_ok = time.time()
            return {"ok": True, "source": "ollama", "model": mdl, "response": text}
    except Exception as e:
        log.debug("Ollama failed: " + str(e))
    
    return {"ok": False, "source": "none", "response": "Both AI services offline."}

def health():
    """Check which AI services are available."""
    brain_up = False
    ollama_up = False
    ollama_models = []
    
    try:
        urllib.request.urlopen("http://127.0.0.1:9990/health", timeout=2)
        brain_up = True
    except: pass
    
    try:
        r = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2)
        data = json.loads(r.read().decode())
        ollama_up = True
        ollama_models = [m["name"] for m in data.get("models", [])]
    except: pass
    
    return {
        "brain": brain_up,
        "ollama": ollama_up,
        "ollama_models": ollama_models,
        "preferred_model": PREFERRED_MODEL,
        "last_brain_ok": last_brain_ok,
        "last_ollama_ok": last_ollama_ok,
    }
