"""
NovaX Free-Tier API Harvester v1.0
Generates training pairs from free cloud APIs — NO GPU needed.
Runs alongside training or data factory without interference.

Providers (all free tier):
  1. Google AI Studio (Gemini Flash) — 15 RPM, 1000 req/day
  2. Groq (LLaMA 3.3 70B) — 30 RPM, ~14K req/day
  3. Cerebras (LLaMA 3.3 70B) — 50 RPM, ~2K req/day (1M tok/day)
  4. SambaNova (LLaMA 3.1 405B) — 10 RPM, ~5K req/day

Combined: 15,000-25,000 pairs/day at ZERO cost.
Runs on CPU only — no GPU contention with training.

Usage:
    python free_tier_harvester.py                  # Run all providers
    python free_tier_harvester.py --provider groq  # Single provider
    python free_tier_harvester.py --count 100      # Generate 100 pairs
"""
import json, time, urllib.request, random, hashlib, os, sys
from pathlib import Path
from datetime import datetime

OUT_FILE = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")
LOG_FILE = Path("C:/NovaX/nova_llm/harvester_log.jsonl")

# ─── PROVIDER CONFIGS ───────────────────────────────
PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY",
        "rpm": 25,  # conservative, actual is 30
        "delay": 2.5,
        "max_tokens": 1024,
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "llama-3.3-70b",
        "env_key": "CEREBRAS_API_KEY",
        "rpm": 40,
        "delay": 1.5,
        "max_tokens": 1024,
    },
    "sambanova": {
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "model": "Meta-Llama-3.1-405B-Instruct",
        "env_key": "SAMBANOVA_API_KEY",
        "rpm": 8,
        "delay": 8.0,
        "max_tokens": 1024,
    },
    "google": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "model": "gemini-2.0-flash",
        "env_key": "GOOGLE_AI_KEY",
        "rpm": 12,
        "delay": 5.0,
        "max_tokens": 1024,
        "is_google": True,
    },
}

# ─── DIVERSE PROMPTS (different from Ollama factory) ─────
# These focus on REASONING and CHAIN-OF-THOUGHT since cloud
# models are much better at these than local 7B models
PROMPTS = [
    # Chain-of-thought reasoning (cloud models excel here)
    "Think step by step: A bat and ball cost $1.10. The bat costs $1 more than the ball. How much does the ball cost?",
    "Reason through this: If all roses are flowers and some flowers fade quickly, can we conclude that some roses fade quickly? Explain your logic.",
    "Think step by step: You have 8 balls. One is heavier. You have a balance scale. What's the minimum number of weighings to find the heavy ball?",
    "Solve step by step: A train leaves Station A at 60 mph. Another leaves Station B (300 miles away) at 40 mph toward A. When do they meet?",
    "Think carefully: Three friends split a $30 hotel bill ($10 each). The clerk realizes it should be $25, gives $5 to the bellboy. The bellboy keeps $2, returns $1 each. Each paid $9 (total $27) + $2 bellboy = $29. Where's the missing dollar?",

    # Complex analysis
    "Compare and contrast: What are the fundamental architectural differences between transformers, RNNs, and state space models? Which is best for what?",
    "Analyze the trade-offs between eventual consistency and strong consistency in distributed databases. Give concrete examples.",
    "Explain the mathematical relationship between attention mechanisms and kernel methods. Are softmax attention and RBF kernels equivalent?",
    "What are the theoretical limits of model compression? Can a 1-bit model ever match a full-precision model of the same size?",
    "Explain why the ternary number system {-1, 0, +1} is mathematically elegant. Connect it to balanced ternary, radix economy, and neural network quantization.",

    # Deep technical explanations
    "Explain how the Straight-Through Estimator works for training quantized neural networks. Why does it work despite being mathematically incorrect?",
    "How does speculative decoding achieve lossless speedup? Prove that it produces the exact same distribution as standard autoregressive decoding.",
    "Explain the connection between the Navier-Stokes equations and information flow in neural networks. Can fluid dynamics model attention?",
    "What is the information-theoretic minimum number of bits needed to represent a neural network with N parameters? How close are ternary networks to this limit?",
    "Explain Kolmogorov complexity and its relationship to neural network generalization. Why do simpler models sometimes generalize better?",

    # System design with reasoning
    "Design a query routing system that can dispatch to 600+ AI models. How would you minimize cost while maintaining quality? Show your reasoning.",
    "Design a ternary inference engine optimized for CPU. Explain why ternary operations can be faster on CPU than GPU for small batch sizes.",
    "How would you build a self-improving AI system that generates its own training data? What safeguards prevent model collapse?",
    "Design a knowledge distillation pipeline that extracts knowledge from 70B+ models into a 235M model. What's the optimal strategy?",
    "How would you implement continuous learning in a deployed LLM without catastrophic forgetting? Compare EWC, replay, and LoRA approaches.",

    # Math reasoning
    "Prove that log base 2 of 3 (approximately 1.585) is the theoretical information content of a ternary digit. Show the derivation.",
    "Explain the scaling laws for language models. If a model has N parameters trained on D tokens, what is the expected loss?",
    "Derive the backpropagation equations for a single attention head. Show the gradient flow through softmax.",
    "Explain why the harmonic series diverges but the sum of 1/n^2 converges. What's the connection to the Riemann zeta function?",
    "Prove that balanced ternary has the lowest carry rate among all positional number systems. What makes base 3 special?",

    # Code with explanations
    "Implement a ternary matrix multiplication in Python that uses only addition and subtraction (no multiplication). Explain why this works.",
    "Write a BPE tokenizer from scratch. Explain each step of the algorithm and why it produces good subword units.",
    "Implement the Straight-Through Estimator for ternary quantization in PyTorch. Explain the forward/backward asymmetry.",
    "Write an efficient KV-cache implementation for grouped query attention. Explain how GQA reduces memory compared to standard MHA.",
    "Implement a simple RAG pipeline in Python: embedding, retrieval, generation. Explain when retrieval helps vs hurts.",

    # Creative technical writing
    "Write a technical blog post explaining why a 235M parameter ternary model can be competitive with much larger models, using the router+specialist architecture.",
    "Explain the concept of mixture of experts to a smart high school student. Use analogies.",
    "Write a comparison between training a small model on lots of data vs a large model on less data. What does the Chinchilla scaling law say?",
    "Explain the concept of 'intelligence per watt' in AI. Why does energy efficiency matter for the future of AI?",
    "Write a technical explanation of how NovaLang's if3/match3/try3 ternary control flow differs from binary true/false logic.",

    # Multi-step problem solving
    "You need to build an AI system that runs on a Raspberry Pi with 4GB RAM. Design the architecture, choose the model size, and explain your optimization strategy.",
    "A startup has $200/month for AI API costs but needs GPT-4 quality. Design a routing system that achieves this. Show the math.",
    "You have 102 local AI models and 350 cloud models. Design a selection algorithm that picks the best model for each query in under 10ms.",
    "Design a training curriculum for a 235M parameter model. What data should it see first, middle, and last? Why does order matter?",
    "You need to serve 1000 inference requests per second on a single RTX 4060. The model is 235M ternary parameters. Is this possible? Show the calculation.",

    # Edge cases and nuance
    "What are the failure modes of knowledge distillation? When does the student model learn the wrong things from the teacher?",
    "Explain model collapse in self-training loops. What causes it and how do you prevent it?",
    "What are the security implications of running a local LLM? How do you prevent prompt injection in a multi-tool system?",
    "Why do small language models hallucinate more than large ones? What architectural changes reduce hallucination?",
    "Explain the alignment tax: why does making a model safer sometimes make it less capable. How do you minimize this trade-off?",

    # Interdisciplinary connections
    "How is the attention mechanism in transformers related to memory retrieval in the human brain?",
    "What can fluid dynamics teach us about information routing in neural networks?",
    "How is the concept of entropy used differently in thermodynamics, information theory, and machine learning?",
    "What is the connection between category theory and neural network architecture design?",
    "How do error-correcting codes relate to robust neural network design?",
]


def query_openai_compatible(prompt, provider_config, api_key):
    """Query an OpenAI-compatible API (Groq, Cerebras, SambaNova)."""
    body = json.dumps({
        "model": provider_config["model"],
        "messages": [
            {"role": "system", "content": "You are a helpful, knowledgeable assistant. Provide clear, detailed, accurate responses with step-by-step reasoning when appropriate."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": provider_config["max_tokens"],
        "temperature": 0.8,
    }).encode()

    req = urllib.request.Request(
        provider_config["url"],
        body,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"]
        model = data.get("model", provider_config["model"])
        return text, model
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if hasattr(e, 'read') else str(e)
        if e.code == 429:
            return "", "RATE_LIMITED"
        return "", f"HTTP_{e.code}"
    except Exception as e:
        return "", f"ERROR: {str(e)[:80]}"


def query_google(prompt, provider_config, api_key):
    """Query Google AI Studio (Gemini)."""
    url = provider_config["url"].replace("{model}", provider_config["model"]) + f"?key={api_key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": provider_config["max_tokens"],
            "temperature": 0.8,
        }
    }).encode()

    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text, provider_config["model"]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return "", "RATE_LIMITED"
        return "", f"HTTP_{e.code}"
    except Exception as e:
        return "", f"ERROR: {str(e)[:80]}"


def query_provider(prompt, provider_name, provider_config, api_key):
    """Route to the correct query function."""
    if provider_config.get("is_google"):
        return query_google(prompt, provider_config, api_key)
    return query_openai_compatible(prompt, provider_config, api_key)


def load_existing():
    """Load existing training pairs."""
    if OUT_FILE.exists():
        with open(OUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_pairs(pairs):
    """Save pairs atomically."""
    tmp = str(OUT_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pairs, f, ensure_ascii=False)
    os.replace(tmp, str(OUT_FILE))


def get_hash(text):
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


def main():
    # Parse args
    target_count = 500  # default
    target_provider = None
    for i, arg in enumerate(sys.argv):
        if arg == "--count" and i+1 < len(sys.argv):
            target_count = int(sys.argv[i+1])
        if arg == "--provider" and i+1 < len(sys.argv):
            target_provider = sys.argv[i+1]

    print("=" * 60)
    print("  NovaX Free-Tier API Harvester v1.0")
    print(f"  Target: {target_count} pairs")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Check available API keys
    available = {}
    for name, config in PROVIDERS.items():
        if target_provider and name != target_provider:
            continue
        key = os.environ.get(config["env_key"], "")
        if not key:
            # Check cloud_config.json
            try:
                cc = json.load(open("C:/NovaX/cloud_config.json", "r"))
                for provider_cfg in cc.get("providers", []):
                    if provider_cfg.get("name", "").lower() == name:
                        key = provider_cfg.get("api_key", "")
                        break
            except:
                pass
        if key:
            available[name] = (config, key)
            print(f"  Provider OK: {name} ({config['model']})")
        else:
            print(f"  Provider SKIP: {name} (no API key in ${config['env_key']})")

    if not available:
        print("\nERROR: No API keys found! Set environment variables or add to cloud_config.json")
        print("  GROQ_API_KEY, CEREBRAS_API_KEY, SAMBANOVA_API_KEY, GOOGLE_AI_KEY")
        sys.exit(1)

    # Load existing
    pairs = load_existing()
    existing_hashes = {get_hash(p.get("response", "")) for p in pairs}
    print(f"\nExisting: {len(pairs)} pairs")

    # Shuffle prompts
    prompts = PROMPTS.copy()
    random.shuffle(prompts)

    # Round-robin across providers
    provider_names = list(available.keys())
    provider_idx = 0
    added = 0
    fails = 0
    rate_limited = {}
    start_time = time.time()

    for i in range(min(target_count, len(prompts) * len(provider_names))):
        # Pick provider (round-robin, skip rate-limited ones)
        attempts = 0
        while attempts < len(provider_names):
            pname = provider_names[provider_idx % len(provider_names)]
            provider_idx += 1
            if pname not in rate_limited:
                break
            # Check if rate limit cooldown expired (60s)
            if time.time() - rate_limited[pname] > 60:
                del rate_limited[pname]
                break
            attempts += 1

        if attempts >= len(provider_names):
            print(f"  All providers rate-limited. Waiting 30s...")
            time.sleep(30)
            rate_limited.clear()
            continue

        config, api_key = available[pname]
        prompt = prompts[i % len(prompts)]

        # Query
        text, model = query_provider(prompt, pname, config, api_key)

        if model == "RATE_LIMITED":
            rate_limited[pname] = time.time()
            print(f"  [{i+1}] RATE LIMITED: {pname}, cooling down 60s")
            continue

        if not text or len(text) < 50:
            fails += 1
            print(f"  [{i+1}] FAIL ({pname}): {model}")
            continue

        # Dedup
        h = get_hash(text)
        if h in existing_hashes:
            print(f"  [{i+1}] DUPE ({pname}): skipping")
            continue

        # Accept
        pairs.append({
            "prompt": prompt,
            "response": text[:8000],
            "domain": "harvested_free_tier",
            "provider": pname,
            "model": model,
            "timestamp": datetime.now().isoformat(),
        })
        existing_hashes.add(h)
        added += 1
        fails = 0

        # Save every pair
        save_pairs(pairs)

        elapsed = time.time() - start_time
        rate = added / (elapsed / 3600) if elapsed > 60 else 0
        print(f"  [{i+1}] +{added} ({pname}/{model}): {prompt[:45]}... ({len(text)} chars) [{rate:.0f}/hr]")

        # Rate limit delay
        time.sleep(config["delay"])

        if added >= target_count:
            break

    # Final stats
    elapsed = time.time() - start_time
    total_chars = sum(len(p.get("prompt","")) + len(p.get("response","")) for p in pairs)

    print(f"\n{'='*60}")
    print(f"  Harvester Complete!")
    print(f"  Added: {added} pairs")
    print(f"  Total: {len(pairs)} pairs, {total_chars:,} chars ({total_chars/1e6:.1f}M)")
    print(f"  Rate: {added/(elapsed/3600):.0f} pairs/hour" if elapsed > 60 else "")
    print(f"  Elapsed: {elapsed/60:.1f} minutes")
    print(f"{'='*60}")

    # Log
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "added": added,
            "total": len(pairs),
            "providers": list(available.keys()),
            "elapsed_minutes": round(elapsed/60, 1),
        }) + "\n")


if __name__ == "__main__":
    main()
