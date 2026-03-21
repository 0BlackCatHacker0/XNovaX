"""
cloud_api_call.py — Thin bridge for NovaX cloud-router to call AI APIs with auth headers.
Called via: python cloud_api_call.py '<json_payload>'
Payload: {"provider":"openai","model":"gpt-4o-mini","prompt":"...","system":"..."}
Reads keys from C:/NovaX/cloud_config.json
Outputs JSON result to stdout.
"""
import sys, json, urllib.request, urllib.error, os, time

CONFIG_PATH = "C:/NovaX/cloud_config.json"

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except:
        return {}

def call_openai(key, model, prompt, system_prompt, url="https://api.openai.com/v1", identity=None, max_tokens=8192):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens}).encode()
    hdrs = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    if identity:
        if identity.get("user_agent"): hdrs["User-Agent"] = identity["user_agent"]
    req = urllib.request.Request(
        f"{url}/chat/completions",
        data=body,
        headers=hdrs
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            text = data["choices"][0]["message"]["content"]
            return {"ok": True, "response": text, "model": model, "provider": "openai"}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else str(e)
        return {"ok": False, "error": f"openai_http_{e.code}", "detail": err_body[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def call_anthropic(key, model, prompt, system_prompt, max_tokens=8192):
    messages = [{"role": "user", "content": prompt}]
    body_dict = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if system_prompt:
        body_dict["system"] = system_prompt
    body = json.dumps(body_dict).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            text = data["content"][0]["text"]
            return {"ok": True, "response": text, "model": model, "provider": "anthropic"}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else str(e)
        return {"ok": False, "error": f"anthropic_http_{e.code}", "detail": err_body[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def call_openrouter(key, model, prompt, system_prompt, identity=None, max_tokens=8192):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens}).encode()
    hdrs = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": identity.get("referer", "https://novax.local") if identity else "https://novax.local",
        "X-Title": identity.get("x_title", "NovaX Cloud Router") if identity else "NovaX Cloud Router"
    }
    if identity and identity.get("user_agent"):
        hdrs["User-Agent"] = identity["user_agent"]
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers=hdrs
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            text = data["choices"][0]["message"]["content"]
            return {"ok": True, "response": text, "model": model, "provider": "openrouter"}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else str(e)
        return {"ok": False, "error": f"openrouter_http_{e.code}", "detail": err_body[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "no payload"}))
        return
    # Support --file mode: read payload from file instead of argv
    if sys.argv[1] == "--file" and len(sys.argv) >= 3:
        try:
            with open(sys.argv[2], "r") as f:
                payload = json.load(f)
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"file_read_error: {e}"}))
            return
    else:
        try:
            payload = json.loads(sys.argv[1])
        except:
            print(json.dumps({"ok": False, "error": "invalid json"}))
            return

    provider = payload.get("provider", "")
    model = payload.get("model", "")
    prompt = payload.get("prompt", "")
    system_prompt = payload.get("system", "")
    max_tokens = payload.get("max_tokens", 8192)

    # Identity headers from NovaX Prime (optional, backward-compatible)
    identity = None
    if payload.get("user_agent") or payload.get("referer") or payload.get("x_title"):
        identity = {
            "user_agent": payload.get("user_agent", ""),
            "referer": payload.get("referer", ""),
            "x_title": payload.get("x_title", "")
        }

    if not prompt:
        print(json.dumps({"ok": False, "error": "missing prompt"}))
        return

    config = load_config()
    provider_cfg = config.get(provider, {})
    key = provider_cfg.get("key", "")

    if not key:
        # Try env var fallback
        env_map = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
        key = os.environ.get(env_map.get(provider, ""), "")

    if not key:
        print(json.dumps({"ok": False, "error": f"no_key_for_{provider}"}))
        return

    if not model:
        models = provider_cfg.get("models", [])
        model = models[0] if models else ""
    if not model:
        print(json.dumps({"ok": False, "error": f"no_model_for_{provider}"}))
        return

    # Check if this provider routes through OpenRouter ("via" field)
    via = provider_cfg.get("via", "")

    t0 = time.time()
    if via == "openrouter":
        # Route through OpenRouter — use OpenRouter key and call_openrouter
        or_cfg = config.get("openrouter", {})
        or_key = or_cfg.get("key", key)
        result = call_openrouter(or_key, model, prompt, system_prompt, identity, max_tokens)
        result["provider"] = provider  # Tag with original provider name
        result["via"] = "openrouter"
    elif provider == "openai":
        url = provider_cfg.get("url", "https://api.openai.com/v1")
        result = call_openai(key, model, prompt, system_prompt, url, identity, max_tokens)
    elif provider == "anthropic":
        result = call_anthropic(key, model, prompt, system_prompt, max_tokens)
    elif provider == "openrouter":
        result = call_openrouter(key, model, prompt, system_prompt, identity, max_tokens)
    else:
        # Generic OpenAI-compatible API
        url = provider_cfg.get("url", "")
        if url:
            result = call_openai(key, model, prompt, system_prompt, url, identity, max_tokens)
        else:
            result = {"ok": False, "error": f"unsupported_provider_{provider}"}

    result["time_ms"] = int((time.time() - t0) * 1000)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
