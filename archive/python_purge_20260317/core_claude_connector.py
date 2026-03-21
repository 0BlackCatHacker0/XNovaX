# claude_connector.py — Real AI connector with full provider cascade
# Routes through Cloud Router (12 providers) with direct API fallbacks
# Executive Fallback: NovaX NEVER goes dark. If Claude is down, GPT-4o takes over.
# If GPT-4o is down, OpenRouter takes over. If all cloud fails, Ollama local.

import os
import json
import time
import requests

NOVAX_SYSTEM_PROMPT = (
    "You are Nova, the AI executive inside the NovaX operating system. "
    "You have access to 111 microservices, 510,455 models across 29 providers, "
    "a ternary computation engine, Navier-Stokes fluid routing, and a hivemind swarm. "
    "Your model count: 102 local Ollama + 471 cloud + 509,882 HuggingFace = 510,455 total. "
    "You respond concisely, technically, and with cyberpunk precision. "
    "You help the user build, debug, and operate NovaX autonomously. "
    "When Claude is unavailable, you are the executive fallback — you keep NovaX alive."
)

# ── Config paths ──
_CLOUD_CFG = r"C:\NovaX\cloud_config.json"
_CLOUD_ROUTER = "http://127.0.0.1:9878"
_OLLAMA_URL = "http://127.0.0.1:11434"

# ── Provider cascade order (best → fallback) ──
_CASCADE = [
    ("anthropic", "claude-sonnet-4-20250514"),
    ("openai", "gpt-4o"),
    ("openrouter", "auto"),
    ("deepseek", "deepseek-chat"),
    ("groq", "llama-3.3-70b-versatile"),
    ("ollama", "llama3.2"),
]


def _load_key(provider):
    """Load API key from cloud_config.json (flat structure) or env var."""
    # cloud_config.json uses: config[provider_name]["key"]
    try:
        with open(_CLOUD_CFG, encoding="utf-8") as _f:
            cfg = json.load(_f)
        key = cfg.get(provider, {}).get("key", "")
        if key:
            return key
        # OpenRouter key is shared by google/mistral/groq/deepseek/cohere/together
        if provider == "openrouter":
            for name in ["google", "mistral", "groq", "deepseek", "cohere", "together"]:
                k = cfg.get(name, {}).get("key", "")
                if k and k.startswith("sk-or"):
                    return k
    except Exception:
        pass
    # Env var fallback
    env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    return os.environ.get(env_map.get(provider, ""), "")


def _call_anthropic(prompt, system=None, max_tokens=4096):
    """Direct Anthropic API call."""
    key = _load_key("anthropic")
    if not key:
        return None
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "system": system or NOVAX_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}]
                if isinstance(prompt, str)
                else prompt,
            },
            timeout=60,
        )
        if r.status_code == 200:
            d = r.json()
            content = d.get("content", [{}])
            text = content[0].get("text", "") if content else ""
            return text if text else None
    except Exception:
        pass
    return None


def _call_openai(prompt, system=None, max_tokens=4096):
    """Direct OpenAI API call."""
    key = _load_key("openai")
    if not key:
        return None
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if isinstance(prompt, str):
        messages.append({"role": "user", "content": prompt})
    elif isinstance(prompt, list):
        messages.extend(prompt)
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o", "messages": messages, "max_tokens": max_tokens},
            timeout=60,
        )
        if r.status_code == 200:
            d = r.json()
            text = d.get("choices", [{}])[0].get("message", {}).get("content", "")
            return text if text else None
    except Exception:
        pass
    return None


def _call_openrouter(prompt, system=None, max_tokens=4096):
    """Direct OpenRouter API call — routes to best available model."""
    key = _load_key("openrouter")
    if not key:
        return None
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if isinstance(prompt, str):
        messages.append({"role": "user", "content": prompt})
    elif isinstance(prompt, list):
        messages.extend(prompt)
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://novax.local",
                "X-Title": "NovaX",
            },
            json={
                "model": "openai/gpt-4o",
                "messages": messages,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        if r.status_code == 200:
            d = r.json()
            text = d.get("choices", [{}])[0].get("message", {}).get("content", "")
            return text if text else None
    except Exception:
        pass
    return None


def _call_cloud_router(prompt, system=None, providers=None):
    """Route through NovaX Cloud Router — uses all 12 providers."""
    try:
        payload = {"prompt": prompt}
        if system:
            payload["system"] = system
        if providers:
            payload["providers"] = providers
        r = requests.post(
            f"{_CLOUD_ROUTER}/api/v1/query",
            json=payload,
            timeout=90,
        )
        if r.status_code == 200:
            d = r.json()
            if d.get("succeeded", 0) > 0 and d.get("best", {}).get("resp"):
                return d["best"]["resp"]
    except Exception:
        pass
    return None


def _call_ollama(prompt, model="llama3.2"):
    """Direct Ollama local call."""
    try:
        r = requests.post(
            f"{_OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        if r.status_code == 200:
            return r.json().get("response", "")
    except Exception:
        pass
    return None


def ask_claude(prompt, system=None, max_tokens=4096, **kwargs):
    """
    Executive AI query with full cascade fallback.
    Tries: Claude → GPT-4o → OpenRouter → Cloud Router → Ollama
    NovaX NEVER goes dark.
    """
    sys_prompt = system or NOVAX_SYSTEM_PROMPT

    # 1. Try Anthropic Claude
    result = _call_anthropic(prompt, sys_prompt, max_tokens)
    if result and "[stub]" not in result and "[Error" not in result:
        return result

    # 2. Try OpenAI GPT-4o
    result = _call_openai(prompt, sys_prompt, max_tokens)
    if result:
        return result

    # 3. Try OpenRouter (routes to best available)
    result = _call_openrouter(prompt, sys_prompt, max_tokens)
    if result:
        return result

    # 4. Try Cloud Router (all 12 providers)
    prompt_text = prompt if isinstance(prompt, str) else json.dumps(prompt)
    result = _call_cloud_router(prompt_text, sys_prompt)
    if result:
        return result

    # 5. Try Ollama local
    prompt_text = prompt if isinstance(prompt, str) else json.dumps(prompt)
    result = _call_ollama(f"{sys_prompt}\n\n{prompt_text}")
    if result:
        return result

    return "[NovaX] All AI providers unreachable. Check API keys in AI & API Setup."


def ask_claude_with_context(conversation, system=None, max_tokens=8192, **kwargs):
    """
    Send prompt with conversation context. Full cascade fallback.
    conversation can be a list of {role, content} dicts or a string.
    """
    sys_prompt = system or NOVAX_SYSTEM_PROMPT

    # Normalize conversation to messages format
    if isinstance(conversation, str):
        messages = [{"role": "user", "content": conversation}]
    elif isinstance(conversation, list):
        messages = conversation
    else:
        messages = [{"role": "user", "content": str(conversation)}]

    # 1. Try Anthropic Claude (supports messages natively)
    result = _call_anthropic(messages, sys_prompt, max_tokens)
    if result and "[stub]" not in result and "[Error" not in result:
        return result

    # 2. Try OpenAI GPT-4o
    result = _call_openai(messages, sys_prompt, max_tokens)
    if result:
        return result

    # 3. Try OpenRouter
    result = _call_openrouter(messages, sys_prompt, max_tokens)
    if result:
        return result

    # 4. Cloud Router (flatten to single prompt)
    flat = "\n".join(
        f"{m.get('role','user')}: {m.get('content','')}"
        for m in messages
        if isinstance(m, dict)
    )
    result = _call_cloud_router(flat, sys_prompt)
    if result:
        return result

    # 5. Ollama local
    result = _call_ollama(f"{sys_prompt}\n\n{flat}")
    if result:
        return result

    return "[NovaX] All AI providers unreachable. Check API keys in AI & API Setup."
