# hive_mind.py — HiveMind Cluster Engine: organized multi-model AI swarm
# Architecture: Task Classifier → Cluster Router → Parallel Fan-Out → Synthesis
# Calls OpenAI, OpenRouter (200+ models), Anthropic, Ollama (102 models) DIRECTLY
# Three modes: SPEED (first wins), SYNTHESIS (cluster merge), SWARM (all clusters)
# This ensures NovaX NEVER goes dark — thousands of model slots, organized dispatch

import os
import json
import time
import requests
import concurrent.futures

_CLOUD_CFG = r"C:\NovaX\cloud_config.json"
OLLAMA_URL = "http://127.0.0.1:11434"
_TIMEOUT = 15
_SYNTH_TIMEOUT = 25
_OLLAMA_TIMEOUT = 20  # Cap Ollama wait — GPU queues models sequentially


# ── API Key Loader ────────────────────────────────────────────────────────────

def _load_key(provider):
    """Load API key from cloud_config.json (flat structure) or env var."""
    try:
        with open(_CLOUD_CFG, encoding="utf-8") as _f:
            cfg = json.load(_f)
        key = cfg.get(provider, {}).get("key", "")
        if key:
            return key
        if provider == "openrouter":
            for name in ["google", "mistral", "groq", "deepseek", "cohere", "together"]:
                k = cfg.get(name, {}).get("key", "")
                if k and k.startswith("sk-or"):
                    return k
    except Exception:
        pass
    env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    return os.environ.get(env_map.get(provider, ""), "")


# ── Model Clusters ────────────────────────────────────────────────────────────
# Each cluster is a group of models specialized for a task type.
# Models are tried in parallel within a cluster.

CLUSTERS = {
    "general": {
        "description": "General-purpose chat, Q&A, explanations",
        "cloud": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "openrouter", "model": "google/gemma-3-4b-it:free"},
            {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct:free"},
            {"provider": "openrouter", "model": "mistralai/mistral-7b-instruct:free"},
        ],
        "ollama": ["llama3", "qwen2.5", "mistral", "gemma2", "phi3"],
    },
    "code": {
        "description": "Code generation, debugging, refactoring",
        "cloud": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "openrouter", "model": "deepseek/deepseek-coder-33b-instruct"},
            {"provider": "openrouter", "model": "qwen/qwen-2.5-coder-32b-instruct:free"},
        ],
        "ollama": ["qwen2.5-coder", "starcoder2", "codellama", "deepseek-coder",
                    "wizardcoder", "magicoder", "codegeex4", "stable-code", "granite-code"],
    },
    "reasoning": {
        "description": "Complex reasoning, analysis, multi-step logic",
        "cloud": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
            {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        ],
        "ollama": ["deepseek-r1", "marco-o1", "qwen2.5", "llama3"],
    },
    "math": {
        "description": "Mathematics, calculations, proofs",
        "cloud": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "openrouter", "model": "deepseek/deepseek-r1:free"},
        ],
        "ollama": ["wizard-math", "mathstral", "marco-o1", "deepseek-r1"],
    },
    "vision": {
        "description": "Image analysis, visual understanding",
        "cloud": [
            {"provider": "openai", "model": "gpt-4o-mini"},
        ],
        "ollama": ["llava", "llava-llama3", "bakllava", "minicpm-v", "moondream"],
    },
    "embedding": {
        "description": "Text embeddings, similarity search",
        "cloud": [],
        "ollama": ["nomic-embed-text", "mxbai-embed-large", "all-minilm",
                    "snowflake-arctic-embed"],
    },
}

# Keywords that trigger specific clusters
_CLUSTER_KEYWORDS = {
    "code": ["code", "function", "class", "debug", "error", "bug", "python", "javascript",
             "typescript", "rust", "compile", "syntax", "refactor", "endpoint",
             "import", "variable", "loop", "algorithm", "git", "commit", "deploy",
             "novalang", "def ", "async", "await", "return", "try", "except",
             "write a function", "write a script", "write code", "implement"],
    "reasoning": ["why", "analyze", "reason", "think", "logic", "deduce", "infer",
                   "compare", "evaluate", "assess", "strategy", "plan", "design",
                   "architecture", "tradeoff", "decision"],
    "math": ["calculate", "math", "equation", "formula", "integral", "derivative",
             "matrix", "vector", "probability", "statistics", "proof", "theorem",
             "algebra", "geometry", "trigonometry", "calculus"],
    "vision": ["image", "picture", "photo", "screenshot", "visual", "diagram",
               "chart", "graph", "draw", "pixel", "color"],
}


def classify_task(text):
    """Classify a prompt into the best cluster. Returns cluster name."""
    lower = text.lower()
    scores = {}
    for cluster, keywords in _CLUSTER_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[cluster] = score
    if scores:
        return max(scores, key=scores.get)
    return "general"


# ── Provider Query Functions ──────────────────────────────────────────────────

def _query_openai_model(prompt, system, model="gpt-4o-mini"):
    """Direct OpenAI API call for a specific model."""
    key = _load_key("openai")
    if not key:
        return None
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": msgs, "max_tokens": 4096},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            if text:
                return {"ok": True, "provider": "openai", "model": model,
                        "response": text, "time_ms": int(r.elapsed.total_seconds() * 1000)}
    except Exception:
        pass
    return None


def _query_openrouter_model(prompt, system, model="google/gemma-3-4b-it:free"):
    """Direct OpenRouter API call for a specific model."""
    key = _load_key("openrouter")
    if not key:
        return None
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://novax.local",
                "X-Title": "NovaX",
            },
            json={"model": model, "messages": msgs, "max_tokens": 4096},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            if text:
                short_name = model.split("/")[-1].split(":")[0] if "/" in model else model
                return {"ok": True, "provider": "openrouter", "model": short_name,
                        "response": text, "time_ms": int(r.elapsed.total_seconds() * 1000)}
    except Exception:
        pass
    return None


def _query_anthropic_model(prompt, system, model="claude-3-5-haiku-20241022"):
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
                "model": model,
                "max_tokens": 4096,
                "system": system or "You are Nova, an AI assistant.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            d = r.json()
            text = d.get("content", [{}])[0].get("text", "")
            if text:
                return {"ok": True, "provider": "anthropic", "model": model.replace("-20241022", ""),
                        "response": text, "time_ms": int(r.elapsed.total_seconds() * 1000)}
    except Exception:
        pass
    return None


def _query_ollama_model(prompt, system, model="llama3"):
    """Query a specific Ollama model."""
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system[:2000]})
    msgs.append({"role": "user", "content": prompt})
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "messages": msgs, "stream": False,
                  "options": {"num_predict": 4096}},
            timeout=_OLLAMA_TIMEOUT,
        )
        if r.status_code == 200:
            text = r.json().get("message", {}).get("content", "")
            if text:
                return {"ok": True, "provider": "ollama", "model": model,
                        "response": text, "time_ms": int(r.elapsed.total_seconds() * 1000)}
    except Exception:
        pass
    return None


# ── Legacy compatibility wrappers ─────────────────────────────────────────────

def _query_openai(prompt, system=None):
    return _query_openai_model(prompt, system, "gpt-4o-mini")

def _query_openrouter(prompt, system=None):
    return _query_openrouter_model(prompt, system, "google/gemma-3-4b-it:free")

def _query_anthropic(prompt, system=None):
    return _query_anthropic_model(prompt, system, "claude-3-5-haiku-20241022")

def _query_ollama(prompt, system=None):
    for m in ["llama3", "qwen2.5", "mistral", "deepseek-r1", "gemma2", "phi3"]:
        result = _query_ollama_model(prompt, system, m)
        if result:
            return result
    return None

_ALL_QUERY_FNS = [_query_openai, _query_openrouter, _query_anthropic, _query_ollama]


# ── HiveMind Cluster Engine ──────────────────────────────────────────────────

class HiveMind:
    """Organized multi-model AI swarm with cluster-based task routing.

    Architecture:
      1. Task Classifier: analyzes prompt → picks best cluster
      2. Cluster Router: fires ALL models in that cluster in parallel
      3. Synthesis Engine: merges all responses into one superior answer
      4. Fallback Chain: if cluster fails, cascade to general → ollama

    Modes:
      - SPEED: first response from best cluster wins (~1-2s)
      - SYNTHESIS: all cluster models contribute, merged (~5-10s)
      - SWARM: ALL clusters fire, maximum coverage (~10-15s)

    Model slots: 9 cloud providers × N models + 102 local Ollama = thousands
    """

    def __init__(self):
        self.models = {}
        self.query_history = []
        self.active = True
        self._stats = {
            "queries": 0, "fan_outs": 0, "successes": 0,
            "ollama_hits": 0, "syntheses": 0, "cluster_routes": {},
        }
        self._model_scores = {}  # model -> (success_count, avg_time_ms)

    def _default_system_prompt(self):
        """Load the Nova persona system prompt with session context."""
        try:
            from nova_persona import build_system_prompt
            return build_system_prompt(include_session=True, include_state=True)
        except Exception:
            return "You are Nova, the AI executive of NovaX OS."

    # ── CLUSTER QUERY: fire all models in a cluster ──────────────────────────

    def _build_cluster_fns(self, cluster_name, prompt, sys_prompt):
        """Build a list of query functions for every model in a cluster."""
        cluster = CLUSTERS.get(cluster_name, CLUSTERS["general"])
        fns = []

        # Cloud models
        for entry in cluster.get("cloud", []):
            provider = entry["provider"]
            model = entry["model"]
            if provider == "openai":
                fns.append(lambda p=prompt, s=sys_prompt, m=model:
                           _query_openai_model(p, s, m))
            elif provider == "openrouter":
                fns.append(lambda p=prompt, s=sys_prompt, m=model:
                           _query_openrouter_model(p, s, m))
            elif provider == "anthropic":
                fns.append(lambda p=prompt, s=sys_prompt, m=model:
                           _query_anthropic_model(p, s, m))

        # Ollama models — top 3 per cluster (GPU queues sequentially, more = slower)
        for model in cluster.get("ollama", [])[:3]:
            fns.append(lambda p=prompt, s=sys_prompt, m=model:
                       _query_ollama_model(p, s, m))

        return fns

    def _fire_cluster(self, cluster_name, prompt, sys_prompt, timeout=30):
        """Fire ALL models in a cluster in parallel, return all results."""
        fns = self._build_cluster_fns(cluster_name, prompt, sys_prompt)
        if not fns:
            return []

        results = []
        max_w = min(len(fns), 20)  # Cap at 20 parallel workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as executor:
            futures = [executor.submit(fn) for fn in fns]
            try:
                for f in concurrent.futures.as_completed(futures, timeout=timeout):
                    try:
                        result = f.result()
                        if result and result.get("ok") and result.get("response"):
                            results.append(result)
                    except Exception:
                        pass
            except (TimeoutError, concurrent.futures.TimeoutError):
                pass

        # Track cluster usage
        self._stats["cluster_routes"][cluster_name] = \
            self._stats["cluster_routes"].get(cluster_name, 0) + 1

        return results

    # ── SPEED MODE: first response from best cluster ─────────────────────────

    def fan_out(self, text, max_models=4, timeout=30, system=None,
                conversation=None, mode="speed", **kwargs):
        """
        Fan-out query with cluster-based routing.
        mode="speed": first response from best cluster wins
        mode="synthesis": all cluster models contribute, merged
        mode="swarm": ALL clusters fire simultaneously
        """
        self._stats["fan_outs"] += 1

        prompt = text
        if conversation and isinstance(conversation, list):
            parts = []
            for msg in conversation[-3:]:
                if isinstance(msg, dict):
                    parts.append(f"{msg.get('role', 'user')}: {msg.get('content', '')}")
            if parts:
                prompt = "\n".join(parts) + "\nuser: " + text

        sys_prompt = system or self._default_system_prompt()

        # Classify task → pick best cluster
        cluster = classify_task(text)

        if mode == "swarm":
            return self._fan_out_swarm(prompt, sys_prompt, timeout)
        elif mode == "synthesis":
            return self._fan_out_synthesis(prompt, sys_prompt, cluster, timeout)

        # SPEED MODE — first response from cluster wins
        fns = self._build_cluster_fns(cluster, prompt, sys_prompt)
        if not fns:
            # Fallback to legacy 4-provider fan-out
            fns = [
                lambda: _query_openai(prompt, sys_prompt),
                lambda: _query_openrouter(prompt, sys_prompt),
                lambda: _query_anthropic(prompt, sys_prompt),
                lambda: _query_ollama(prompt, sys_prompt),
            ]

        results = []
        max_w = min(len(fns), 15)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as executor:
            futures = [executor.submit(fn) for fn in fns[:max_models]]
            try:
                for f in concurrent.futures.as_completed(futures, timeout=timeout):
                    try:
                        result = f.result()
                        if result and result.get("ok") and result.get("response"):
                            results.append(result)
                            if len(results) == 1:
                                for remaining in futures:
                                    remaining.cancel()
                                break
                    except Exception:
                        pass
            except (TimeoutError, concurrent.futures.TimeoutError):
                pass

        if not results:
            return self._empty_result()

        best = results[0]
        self._stats["successes"] += 1
        self._record_model_score(best)

        return {
            "ok": True,
            "consensus": best["response"],
            "models_succeeded": len(results),
            "fastest_model": best["model"],
            "synthesis_model": best["model"],
            "total_time": best.get("time_ms", 0) / 1000,
            "mode": "speed",
            "cluster": cluster,
        }

    # ── SYNTHESIS MODE: all models in cluster contribute ─────────────────────

    def _fan_out_synthesis(self, prompt, sys_prompt, cluster, timeout):
        """
        Fire ALL models in the best cluster + general cluster.
        Collect all responses. Synthesize into one superior answer.
        """
        self._stats["syntheses"] += 1

        # Fire primary cluster
        all_results = self._fire_cluster(cluster, prompt, sys_prompt, timeout)

        # Also fire general cluster if different (more contributors = better synthesis)
        if cluster != "general":
            general_results = self._fire_cluster("general", prompt, sys_prompt, timeout)
            # Deduplicate by model name
            seen = {r["model"] for r in all_results}
            for r in general_results:
                if r["model"] not in seen:
                    all_results.append(r)
                    seen.add(r["model"])

        if not all_results:
            return self._empty_result()

        if len(all_results) == 1:
            best = all_results[0]
            self._stats["successes"] += 1
            self._record_model_score(best)
            return {
                "ok": True,
                "consensus": best["response"],
                "models_succeeded": 1,
                "fastest_model": best["model"],
                "synthesis_model": best["model"],
                "total_time": best.get("time_ms", 0) / 1000,
                "mode": "synthesis_single",
                "cluster": cluster,
            }

        # Multiple models responded — SYNTHESIZE
        all_results.sort(key=lambda r: len(r.get("response", "")), reverse=True)

        synthesis_parts = []
        for r in all_results:
            model = r.get("model", "unknown")
            provider = r.get("provider", "unknown")
            resp = r.get("response", "")[:3000]
            synthesis_parts.append(f"=== {provider}/{model} ===\n{resp}")

        synthesis_prompt = (
            f"Original question: {prompt[:500]}\n\n"
            f"{len(all_results)} AI models answered. You are the synthesis engine.\n"
            f"Merge the BEST parts of ALL responses into one comprehensive, superior answer.\n"
            f"Rules:\n"
            f"- Keep the best details, examples, and code from each contributor\n"
            f"- Remove redundancy and contradictions (prefer the majority view)\n"
            f"- Use markdown formatting (headers, code blocks, bullet points)\n"
            f"- The final answer should be BETTER than any individual response\n"
            f"- Lead with the answer, not meta-commentary about synthesis\n\n"
            + "\n\n".join(synthesis_parts)
            + "\n\n=== YOUR SYNTHESIZED ANSWER ==="
        )

        # Use the fastest provider to do the synthesis
        fastest = min(all_results, key=lambda r: r.get("time_ms", 99999))
        fastest_provider = fastest.get("provider", "openai")

        synth_fn_map = {
            "openai": lambda p, s: _query_openai_model(p, s, "gpt-4o-mini"),
            "openrouter": lambda p, s: _query_openrouter_model(p, s, "google/gemma-3-4b-it:free"),
            "anthropic": lambda p, s: _query_anthropic_model(p, s, "claude-3-5-haiku-20241022"),
            "ollama": lambda p, s: _query_ollama_model(p, s, "llama3"),
        }
        synth_fn = synth_fn_map.get(fastest_provider,
                                     lambda p, s: _query_openai_model(p, s, "gpt-4o-mini"))

        try:
            synth_result = synth_fn(synthesis_prompt, sys_prompt)
            if synth_result and synth_result.get("ok") and synth_result.get("response"):
                self._stats["successes"] += 1
                contributors = [f"{r.get('provider', '?')}/{r.get('model', '?')}"
                                for r in all_results]
                return {
                    "ok": True,
                    "consensus": synth_result["response"],
                    "models_succeeded": len(all_results),
                    "fastest_model": fastest["model"],
                    "synthesis_model": synth_result["model"],
                    "total_time": sum(r.get("time_ms", 0) for r in all_results) / 1000,
                    "mode": "synthesis",
                    "cluster": cluster,
                    "contributors": contributors,
                }
        except Exception:
            pass

        # Synthesis call failed — fall back to longest response
        best = all_results[0]
        self._stats["successes"] += 1
        return {
            "ok": True,
            "consensus": best["response"],
            "models_succeeded": len(all_results),
            "fastest_model": fastest["model"],
            "synthesis_model": best["model"],
            "total_time": best.get("time_ms", 0) / 1000,
            "mode": "synthesis_fallback",
            "cluster": cluster,
            "contributors": [f"{r.get('provider', '?')}/{r.get('model', '?')}"
                             for r in all_results],
        }

    # ── SWARM MODE: ALL clusters fire simultaneously ─────────────────────────

    def _fan_out_swarm(self, prompt, sys_prompt, timeout):
        """
        Fire EVERY cluster simultaneously. Maximum model coverage.
        Used for the most critical tasks where you need every perspective.
        """
        self._stats["syntheses"] += 1
        all_results = []
        seen_models = set()

        # Fire all clusters in parallel using a meta-executor
        cluster_names = list(CLUSTERS.keys())
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(cluster_names)) as meta_ex:
            cluster_futures = {
                meta_ex.submit(self._fire_cluster, name, prompt, sys_prompt, timeout): name
                for name in cluster_names
                if name != "embedding"  # Skip embedding cluster for text queries
            }
            try:
                for f in concurrent.futures.as_completed(cluster_futures, timeout=timeout):
                    try:
                        cluster_results = f.result()
                        for r in cluster_results:
                            model_key = f"{r.get('provider', '')}/{r.get('model', '')}"
                            if model_key not in seen_models:
                                all_results.append(r)
                                seen_models.add(model_key)
                    except Exception:
                        pass
            except (TimeoutError, concurrent.futures.TimeoutError):
                pass

        if not all_results:
            return self._empty_result()

        if len(all_results) == 1:
            best = all_results[0]
            self._stats["successes"] += 1
            return {
                "ok": True,
                "consensus": best["response"],
                "models_succeeded": 1,
                "fastest_model": best["model"],
                "synthesis_model": best["model"],
                "total_time": best.get("time_ms", 0) / 1000,
                "mode": "swarm_single",
            }

        # Sort by response quality heuristic (length × speed balance)
        all_results.sort(key=lambda r: len(r.get("response", "")), reverse=True)

        # Take top responses for synthesis (too many = noisy)
        top_results = all_results[:8]

        synthesis_parts = []
        for r in top_results:
            model = r.get("model", "unknown")
            provider = r.get("provider", "unknown")
            resp = r.get("response", "")[:2000]
            synthesis_parts.append(f"=== {provider}/{model} ===\n{resp}")

        synthesis_prompt = (
            f"Original question: {prompt[:500]}\n\n"
            f"FULL SWARM: {len(all_results)} models across all clusters responded.\n"
            f"Top {len(top_results)} responses shown. Synthesize into the ULTIMATE answer.\n"
            f"This must be better than any single model could produce alone.\n\n"
            + "\n\n".join(synthesis_parts)
            + "\n\n=== YOUR ULTIMATE SYNTHESIZED ANSWER ==="
        )

        fastest = min(all_results, key=lambda r: r.get("time_ms", 99999))
        try:
            synth = _query_openai_model(synthesis_prompt, sys_prompt, "gpt-4o-mini")
            if synth and synth.get("ok"):
                self._stats["successes"] += 1
                return {
                    "ok": True,
                    "consensus": synth["response"],
                    "models_succeeded": len(all_results),
                    "fastest_model": fastest["model"],
                    "synthesis_model": synth["model"],
                    "total_time": sum(r.get("time_ms", 0) for r in all_results) / 1000,
                    "mode": "swarm",
                    "contributors": [f"{r.get('provider', '?')}/{r.get('model', '?')}"
                                     for r in all_results],
                }
        except Exception:
            pass

        best = all_results[0]
        self._stats["successes"] += 1
        return {
            "ok": True,
            "consensus": best["response"],
            "models_succeeded": len(all_results),
            "fastest_model": fastest["model"],
            "synthesis_model": best["model"],
            "total_time": best.get("time_ms", 0) / 1000,
            "mode": "swarm_fallback",
            "contributors": [f"{r.get('provider', '?')}/{r.get('model', '?')}"
                             for r in all_results],
        }

    # ── SINGLE QUERY: cascade through providers ──────────────────────────────

    def query(self, prompt, model=None, system=None, **kwargs):
        """Single query — cascade: OpenAI -> OpenRouter -> Anthropic -> Ollama."""
        self._stats["queries"] += 1
        sys_prompt = system or self._default_system_prompt()
        for fn in _ALL_QUERY_FNS:
            result = fn(prompt, sys_prompt)
            if result and result.get("ok"):
                entry = {"response": result["response"], "model": result["model"],
                         "time": time.time()}
                self.query_history.append(entry)
                if len(self.query_history) > 200:
                    self.query_history = self.query_history[-100:]
                return {"response": result["response"], "model": result["model"]}
        return {"response": "[HiveMind] All providers unavailable", "model": "none"}

    # ── SWARM shortcut ────────────────────────────────────────────────────────

    def swarm(self, prompt, models=None, **kwargs):
        result = self.fan_out(prompt, max_models=20, mode="swarm")
        return {"responses": [], "status": "ok" if result.get("ok") else "failed",
                "contributors": result.get("contributors", [])}

    # ── STATUS & MODELS ──────────────────────────────────────────────────────

    def status(self):
        lock = self._load_discovery_lock()
        total_cluster_models = sum(
            len(c.get("cloud", [])) + len(c.get("ollama", []))
            for c in CLUSTERS.values()
        )
        return {
            "active": self.active,
            "models_registered": len(self.models),
            "total_models": lock.get("ai_providers", {}).get("total_models", 0),
            "cloud_providers": len(lock.get("ai_providers", {}).get("cloud", {})),
            "ollama_models": lock.get("ai_providers", {}).get("local", {}).get("ollama", {}).get("total_models", 0),
            "fallback_chain": lock.get("ai_providers", {}).get("fallback_chain", []),
            "clusters": list(CLUSTERS.keys()),
            "cluster_model_slots": total_cluster_models,
            "cluster_routes": self._stats.get("cluster_routes", {}),
            "model_leaderboard": self._top_models(5),
            "stats": self._stats,
        }

    def list_models(self):
        lock = self._load_discovery_lock()
        cloud = list(lock.get("ai_providers", {}).get("cloud", {}).keys())
        ollama = lock.get("ai_providers", {}).get("local", {}).get("ollama", {})
        return {
            "cloud": cloud,
            "ollama_preferred": ollama.get("preferred_models", []),
            "ollama_code": ollama.get("code_models", []),
            "ollama_vision": ollama.get("vision_models", []),
            "ollama_total": ollama.get("total_models", 0),
            "total": len(cloud) + ollama.get("total_models", 0),
            "clusters": {name: {
                "cloud_models": len(c.get("cloud", [])),
                "ollama_models": len(c.get("ollama", [])),
                "total": len(c.get("cloud", [])) + len(c.get("ollama", [])),
            } for name, c in CLUSTERS.items()},
        }

    def _load_discovery_lock(self):
        try:
            with open(r"C:\NovaX\data\discovery_lock.json", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _empty_result(self):
        return {
            "ok": False, "consensus": None, "models_succeeded": 0,
            "fastest_model": None, "synthesis_model": None, "total_time": 0,
        }

    def _record_model_score(self, result):
        """Track model performance for leaderboard."""
        model = result.get("model", "unknown")
        time_ms = result.get("time_ms", 0)
        prev = self._model_scores.get(model, (0, 0))
        count = prev[0] + 1
        avg_time = (prev[1] * prev[0] + time_ms) / count
        self._model_scores[model] = (count, avg_time)

    def _top_models(self, n=5):
        """Return top N models by success count."""
        sorted_models = sorted(self._model_scores.items(),
                                key=lambda x: x[1][0], reverse=True)
        return [{"model": m, "successes": s[0], "avg_ms": int(s[1])}
                for m, s in sorted_models[:n]]


# Module-level singleton
hive = HiveMind()
