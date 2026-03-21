"""
NovaX Synthetic Training Data Generator v1.0
=============================================
Uses locally-installed Ollama models to generate diverse, high-quality
training pairs for the NovaX 117M parameter LLM.

Usage:
    python generate_training_data.py --target 50000 --output training_pairs_v3.json
    python generate_training_data.py --target 10000 --workers 2 --timeout 60

Saves progress every 100 pairs. Can be stopped and resumed.
"""

import json
import os
import sys
import time
import random
import hashlib
import argparse
import logging
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://127.0.0.1:11434"
SCRIPT_DIR = Path(__file__).parent.resolve()
EXISTING_V2 = Path("C:/NovaX/data/llm_training/training_pairs_v2.json")

# Models ranked by quality/speed tradeoff — skip embedding & vision-only models
SKIP_MODELS = {
    "all-minilm", "mxbai-embed-large", "nomic-embed-text",
    "snowflake-arctic-embed", "bakllava", "llava", "llava-llama3",
    "minicpm-v", "moondream",
    # Also skip novax-* variants (fine-tuned duplicates, may be broken)
    # We'll filter these programmatically
}

# Preferred models in priority order (diverse architectures)
PREFERRED_MODELS = [
    "llama3:latest",
    "mistral:latest",
    "gemma2:latest",
    "qwen2.5:latest",
    "deepseek-r1:latest",
    "phi3:latest",
    "yi:latest",
    "zephyr:latest",
    "openchat:latest",
    "openhermes:latest",
    "neural-chat:latest",
    "starling-lm:latest",
    "dolphin-llama3:latest",
    "vicuna:latest",
    "nous-hermes:latest",
    "orca-mini:latest",
    "samantha-mistral:latest",
    "wizard-vicuna-uncensored:latest",
    # Code specialists
    "deepseek-coder:latest",
    "codellama:latest",
    "qwen2.5-coder:latest",
    "codegeex4:latest",
    "magicoder:latest",
    "wizardcoder:latest",
    "starcoder2:latest",
    "granite-code:latest",
    "stable-code:latest",
    "sqlcoder:latest",
    # Math specialists
    "mathstral:latest",
    "wizard-math:latest",
    # Reasoning
    "marco-o1:latest",
    "exaone3.5:latest",
    "internlm2:latest",
    "glm4:latest",
    "aya:latest",
    # Small/fast
    "tinyllama:latest",
    "tinydolphin:latest",
    "stablelm2:latest",
    "dolphin-phi:latest",
    "falcon3:1b",
    "falcon:latest",
    "yarn-mistral:latest",
]

# ---------------------------------------------------------------------------
# Topic seeds — 150+ diverse topics across all domains
# ---------------------------------------------------------------------------

TOPICS = {
    "code": [
        "binary search tree implementation", "hash map with collision handling",
        "merge sort algorithm", "graph BFS and DFS traversal", "linked list reversal",
        "dynamic programming knapsack problem", "red-black tree balancing",
        "trie data structure for autocomplete", "heap implementation priority queue",
        "A* pathfinding algorithm", "LRU cache implementation", "rate limiter design",
        "thread pool executor", "async event loop", "TCP socket server",
        "REST API with authentication", "JSON parser from scratch", "regex engine",
        "database connection pool", "pub-sub message queue", "web scraper with rate limiting",
        "file system watcher", "command line argument parser", "logging framework",
        "unit testing framework", "dependency injection container",
        "observer design pattern", "factory pattern with registration",
        "producer-consumer with bounded buffer", "read-write lock implementation",
        "bloom filter for membership testing", "consistent hashing for load balancing",
        "skip list data structure", "disjoint set union find", "segment tree range queries",
        "topological sort for dependency resolution", "minimum spanning tree Kruskal",
        "Dijkstra shortest path algorithm", "backtracking sudoku solver",
        "matrix multiplication optimization", "string matching KMP algorithm",
    ],
    "math": [
        "prove the Pythagorean theorem", "explain eigenvalues and eigenvectors",
        "derive the quadratic formula", "prove the fundamental theorem of calculus",
        "explain Bayes theorem with examples", "prove that sqrt(2) is irrational",
        "explain the central limit theorem", "derive Euler's formula",
        "explain gradient descent optimization", "prove the binomial theorem",
        "explain Markov chains and steady states", "derive Taylor series expansion",
        "explain linear regression mathematically", "prove the pigeonhole principle",
        "explain principal component analysis", "derive the chain rule for derivatives",
        "explain the simplex method for linear programming",
        "prove that there are infinitely many primes",
        "explain the fast Fourier transform algorithm",
        "derive the normal distribution probability density function",
        "explain matrix decomposition methods LU QR SVD",
        "prove the Cauchy-Schwarz inequality",
        "explain convex optimization and KKT conditions",
        "derive the formula for compound interest",
        "explain the method of Lagrange multipliers",
    ],
    "science": [
        "how does photosynthesis work at the molecular level",
        "explain general relativity and spacetime curvature",
        "how do vaccines train the immune system",
        "explain the Standard Model of particle physics",
        "how does DNA replication work", "explain plate tectonics and continental drift",
        "how do semiconductors and transistors work",
        "explain the greenhouse effect and climate change mechanisms",
        "how does nuclear fission generate energy",
        "explain the Doppler effect and its applications",
        "how do enzymes catalyze biochemical reactions",
        "explain the laws of thermodynamics",
        "how does the human brain process visual information",
        "explain stellar evolution from nebula to black hole",
        "how do antibiotics work against bacteria",
        "explain superconductivity and BCS theory",
        "how does the periodic table organize elements",
        "explain the water cycle and its climate impacts",
        "how do batteries store and release energy",
        "explain the difference between mitosis and meiosis",
    ],
    "reasoning": [
        "a farmer needs to transport a wolf, goat, and cabbage across a river",
        "you have 8 identical-looking balls, one is heavier, find it in 2 weighings",
        "explain why correlation does not imply causation with examples",
        "three doors problem Monty Hall - explain the correct strategy",
        "analyze the prisoners dilemma in game theory",
        "explain the difference between deductive and inductive reasoning",
        "a bat and ball cost $1.10 total, bat costs $1 more than ball",
        "explain Zeno's paradox and why it's resolved by calculus",
        "if it takes 5 machines 5 minutes to make 5 widgets how long for 100 machines",
        "explain the birthday paradox probability",
        "analyze the ship of Theseus thought experiment",
        "explain why the gambler's fallacy is wrong",
        "solve the Tower of Hanoi for n disks and explain the pattern",
        "explain Russell's paradox and its impact on set theory",
        "analyze the trolley problem from multiple ethical frameworks",
        "explain the difference between sound and valid arguments",
        "what is the halting problem and why is it unsolvable",
        "explain the concept of NP-completeness",
        "analyze the tragedy of the commons",
        "explain Godel's incompleteness theorems in simple terms",
    ],
    "creative": [
        "write a short story about a time traveler who can only go forward",
        "write a poem about the beauty of mathematics",
        "create a dialogue between a human and an AI about consciousness",
        "write a story about the last library on Earth",
        "compose a narrative about discovering a new color",
        "write about a world where music is the only form of communication",
        "create a story about an AI that learns to dream",
        "write a philosophical essay on the nature of reality",
        "compose a tale about a scientist who accidentally creates a universe",
        "write about first contact with an alien species that communicates through math",
        "create a story about memories that can be traded like currency",
        "write a narrative about a city that exists between dimensions",
        "compose a story about the last human to learn to read",
        "write about a world where emotions are visible as colors",
        "create a dialogue between past and future versions of yourself",
    ],
    "instruction": [
        "explain how to set up a Python virtual environment step by step",
        "how to configure a Linux firewall using iptables",
        "guide for setting up a PostgreSQL database with replication",
        "how to implement CI/CD pipeline with GitHub Actions",
        "step by step guide to deploy a Docker container to Kubernetes",
        "how to set up SSH key-based authentication",
        "guide for configuring nginx as a reverse proxy",
        "how to implement OAuth 2.0 authentication flow",
        "step by step guide to create a machine learning pipeline",
        "how to set up monitoring with Prometheus and Grafana",
        "guide for implementing websocket communication",
        "how to create a REST API with proper error handling",
        "step by step guide to database migration strategies",
        "how to implement full-text search with Elasticsearch",
        "guide for setting up a message queue with RabbitMQ",
    ],
    "systems": [
        "explain how a CPU pipeline works with stages",
        "how does virtual memory and page tables work",
        "explain the TCP three-way handshake and congestion control",
        "how does a B+ tree index work in databases",
        "explain the Raft consensus algorithm",
        "how does a garbage collector work in managed languages",
        "explain how TLS/SSL handshake establishes secure connections",
        "how does a compiler optimize code with SSA form",
        "explain how container isolation works with namespaces and cgroups",
        "how does a distributed hash table work",
        "explain write-ahead logging in databases",
        "how does branch prediction work in modern CPUs",
        "explain the difference between processes and threads at the OS level",
        "how does DNS resolution work end to end",
        "explain how a load balancer distributes traffic",
    ],
    "ml_ai": [
        "explain how backpropagation trains neural networks",
        "how do attention mechanisms work in transformers",
        "explain the difference between supervised and unsupervised learning",
        "how does a convolutional neural network detect features",
        "explain reinforcement learning with Q-learning",
        "how do generative adversarial networks work",
        "explain the vanishing gradient problem and solutions",
        "how does batch normalization improve training",
        "explain the transformer architecture in detail",
        "how do recurrent neural networks process sequences",
        "explain dropout regularization and why it works",
        "how does transfer learning work in deep learning",
        "explain the difference between precision and recall",
        "how do word embeddings capture semantic meaning",
        "explain how diffusion models generate images",
    ],
}

# Prompt templates for variety
PROMPT_TEMPLATES = [
    "{topic}",
    "Explain {topic}",
    "Explain {topic} in detail",
    "What is {topic}?",
    "How does {topic} work?",
    "Describe {topic}",
    "Write a detailed explanation of {topic}",
    "I need to understand {topic}. Can you help?",
    "Give a thorough technical explanation of {topic}",
    "As an expert, explain {topic}",
    "Teach me about {topic}",
    "What are the key concepts behind {topic}?",
    "Walk me through {topic} step by step",
    "Provide a comprehensive overview of {topic}",
]

CODE_PROMPT_TEMPLATES = [
    "Write a Python implementation of {topic}",
    "Implement {topic} in Python with comments",
    "Write clean, well-documented code for {topic}",
    "Show me how to implement {topic} with example usage",
    "Write a complete implementation of {topic} with error handling",
    "Implement {topic} and explain the time complexity",
    "Write production-quality code for {topic}",
    "Create a {topic} implementation with tests",
]

# Cross-pollination prompts (use output from one model as context for another)
CROSS_PROMPTS = [
    "Given this context:\n{context}\n\nNow explain the same topic differently, adding details that were missed.",
    "A colleague wrote this:\n{context}\n\nWrite a complementary explanation that covers different aspects.",
    "Review and expand on this explanation:\n{context}\n\nAdd practical examples and edge cases.",
    "This is a draft explanation:\n{context}\n\nRewrite it to be clearer and more complete.",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("synth-gen")

# ---------------------------------------------------------------------------
# Ollama client
# ---------------------------------------------------------------------------

def ollama_generate(model: str, prompt: str, timeout: int = 90) -> dict | None:
    """Call Ollama generate endpoint. Returns response dict or None on failure."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 1024,      # cap tokens for speed
            "temperature": 0.8,
            "top_p": 0.9,
        }
    }).encode("utf-8")

    req = Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, OSError) as e:
        log.debug(f"Ollama error ({model}): {e}")
        return None


def get_available_models() -> list[str]:
    """Fetch models from Ollama, filter to usable text models."""
    try:
        req = Request(f"{OLLAMA_URL}/api/tags")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.error(f"Cannot reach Ollama: {e}")
        sys.exit(1)

    all_models = [m["name"] for m in data.get("models", [])]

    # Filter: skip embedding, vision-only, and novax-* variants
    usable = []
    for m in all_models:
        base = m.split(":")[0]
        if base in SKIP_MODELS:
            continue
        if base.startswith("novax-"):
            continue
        usable.append(m)

    # Reorder: put preferred models first
    preferred_set = set(PREFERRED_MODELS)
    ordered = [m for m in PREFERRED_MODELS if m in usable]
    ordered += [m for m in usable if m not in preferred_set]
    return ordered


# ---------------------------------------------------------------------------
# Data storage with incremental save
# ---------------------------------------------------------------------------

class PairStore:
    """Thread-safe pair storage with incremental saves."""

    def __init__(self, output_path: Path, save_interval: int = 100):
        self.output_path = output_path
        self.save_interval = save_interval
        self.pairs: list[dict] = []
        self.seen_hashes: set[str] = set()
        self.lock = threading.Lock()
        self._unsaved = 0
        self._load_existing()

    def _load_existing(self):
        """Load previously generated pairs if output file exists (for resume)."""
        if self.output_path.exists():
            try:
                with open(self.output_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                for p in existing:
                    h = self._hash(p)
                    if h not in self.seen_hashes:
                        self.seen_hashes.add(h)
                        self.pairs.append(p)
                log.info(f"Resumed: loaded {len(self.pairs)} existing pairs from {self.output_path}")
            except Exception as e:
                log.warning(f"Could not load existing output: {e}")

    @staticmethod
    def _hash(pair: dict) -> str:
        key = (pair.get("prompt", "")[:100] + pair.get("response", "")[:200]).encode()
        return hashlib.md5(key).hexdigest()

    def add(self, pair: dict) -> bool:
        """Add a pair. Returns True if added (not duplicate). Thread-safe."""
        h = self._hash(pair)
        with self.lock:
            if h in self.seen_hashes:
                return False
            self.seen_hashes.add(h)
            self.pairs.append(pair)
            self._unsaved += 1
            if self._unsaved >= self.save_interval:
                self._save()
            return True

    def _save(self):
        """Save to disk. Must be called with lock held."""
        try:
            tmp = self.output_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.pairs, f, ensure_ascii=False)
            tmp.replace(self.output_path)
            self._unsaved = 0
            log.info(f"Saved {len(self.pairs)} pairs to {self.output_path.name}")
        except Exception as e:
            log.error(f"Save failed: {e}")

    def flush(self):
        with self.lock:
            self._save()

    def count(self) -> int:
        with self.lock:
            return len(self.pairs)


# ---------------------------------------------------------------------------
# Quality filters
# ---------------------------------------------------------------------------

def quality_check(response: str) -> bool:
    """Filter out low-quality responses."""
    if not response or len(response.strip()) < 80:
        return False
    # Too short = probably a refusal or error
    words = response.split()
    if len(words) < 15:
        return False
    # Repetition check: if any 10-word sequence repeats 3+ times, it's garbage
    if len(words) >= 30:
        chunks = [" ".join(words[i:i+10]) for i in range(len(words) - 9)]
        from collections import Counter
        counts = Counter(chunks)
        if counts.most_common(1)[0][1] >= 3:
            return False
    # Common refusal patterns
    lower = response.lower()
    refusal_markers = [
        "i cannot", "i can't help with", "i'm not able to",
        "as an ai language model, i cannot",
        "i don't have the ability",
    ]
    for marker in refusal_markers:
        if lower.startswith(marker):
            return False
    return True


# ---------------------------------------------------------------------------
# Generation strategies
# ---------------------------------------------------------------------------

def generate_direct(model: str, domain: str, topic: str, timeout: int) -> dict | None:
    """Strategy 1: Direct prompt -> response."""
    if domain == "code":
        template = random.choice(CODE_PROMPT_TEMPLATES)
    else:
        template = random.choice(PROMPT_TEMPLATES)

    prompt = template.format(topic=topic)
    result = ollama_generate(model, prompt, timeout=timeout)
    if result is None:
        return None

    response = result.get("response", "").strip()
    if not quality_check(response):
        return None

    return {
        "prompt": prompt,
        "response": response[:4000],
        "domain": domain.upper(),
        "provider": "ollama-synthetic",
        "model": model,
    }


def generate_cross_pollination(
    model_a: str, model_b: str, domain: str, topic: str, timeout: int
) -> list[dict]:
    """Strategy 2: Model A generates, Model B refines/expands."""
    pairs = []

    # Step 1: Get initial response from model A
    template = random.choice(PROMPT_TEMPLATES)
    prompt_a = template.format(topic=topic)
    result_a = ollama_generate(model_a, prompt_a, timeout=timeout)
    if result_a is None:
        return pairs

    response_a = result_a.get("response", "").strip()
    if quality_check(response_a):
        pairs.append({
            "prompt": prompt_a,
            "response": response_a[:4000],
            "domain": domain.upper(),
            "provider": "ollama-synthetic",
            "model": model_a,
        })

    # Step 2: Cross-pollinate with model B
    if response_a and len(response_a) > 50:
        cross_template = random.choice(CROSS_PROMPTS)
        # Truncate context to keep prompt short
        context = response_a[:800]
        cross_prompt = cross_template.format(context=context)

        result_b = ollama_generate(model_b, cross_prompt, timeout=timeout)
        if result_b:
            response_b = result_b.get("response", "").strip()
            if quality_check(response_b):
                # The cross-pollinated pair uses the original topic as prompt
                alt_prompt = f"Explain {topic} thoroughly with examples"
                pairs.append({
                    "prompt": alt_prompt,
                    "response": response_b[:4000],
                    "domain": domain.upper(),
                    "provider": "ollama-cross",
                    "model": f"{model_a}+{model_b}",
                })
    return pairs


def generate_qa_from_topic(model: str, domain: str, topic: str, timeout: int) -> list[dict]:
    """Strategy 3: Ask model to generate Q&A pairs about a topic."""
    meta_prompt = (
        f"Generate 3 question-answer pairs about: {topic}\n"
        f"Format each as:\nQ: <question>\nA: <detailed answer>\n\n"
        f"Make questions progressively harder. Answers should be thorough."
    )

    result = ollama_generate(model, meta_prompt, timeout=timeout)
    if result is None:
        return []

    text = result.get("response", "")
    pairs = []

    # Parse Q/A pairs from output
    chunks = text.split("Q:")
    for chunk in chunks[1:]:  # skip first empty split
        if "A:" not in chunk:
            continue
        parts = chunk.split("A:", 1)
        q = parts[0].strip().strip("?").strip() + "?"
        a = parts[1].strip()
        # Trim answer at next Q: if present
        if "Q:" in a:
            a = a[:a.index("Q:")].strip()

        if len(q) > 10 and quality_check(a):
            pairs.append({
                "prompt": q,
                "response": a[:4000],
                "domain": domain.upper(),
                "provider": "ollama-meta",
                "model": model,
            })
    return pairs


def generate_code_task(model: str, topic: str, timeout: int) -> dict | None:
    """Strategy 4: Code generation with specific structure."""
    prompt = (
        f"Write a complete, working Python implementation of {topic}.\n"
        f"Include:\n1. Clear docstrings\n2. Type hints\n3. Example usage\n"
        f"4. Edge case handling\nWrite only the code with comments."
    )
    result = ollama_generate(model, prompt, timeout=timeout)
    if result is None:
        return None

    response = result.get("response", "").strip()
    if not quality_check(response):
        return None
    # Code-specific: must contain at least one def/class or code block
    if "def " not in response and "class " not in response and "```" not in response:
        return None

    return {
        "prompt": prompt,
        "response": response[:4000],
        "domain": "CODE",
        "provider": "ollama-code",
        "model": model,
    }


def generate_math_reasoning(model: str, topic: str, timeout: int) -> dict | None:
    """Strategy 5: Math/reasoning with step-by-step."""
    prompt = (
        f"{topic}\n\n"
        f"Show your work step by step. Be rigorous and precise."
    )
    result = ollama_generate(model, prompt, timeout=timeout)
    if result is None:
        return None

    response = result.get("response", "").strip()
    if not quality_check(response):
        return None

    return {
        "prompt": prompt,
        "response": response[:4000],
        "domain": "MATH" if "math" in topic.lower() or "prove" in topic.lower() else "REASON",
        "provider": "ollama-reasoning",
        "model": model,
    }


# ---------------------------------------------------------------------------
# Main generation loop
# ---------------------------------------------------------------------------

def select_model_for_domain(models: list[str], domain: str) -> str:
    """Pick the best model for a given domain."""
    code_models = [m for m in models if any(k in m for k in
        ["code", "coder", "starcoder", "magicoder", "wizard"])]
    math_models = [m for m in models if any(k in m for k in
        ["math", "marco", "deepseek-r1"])]
    general_models = [m for m in models if m not in code_models + math_models]

    if domain == "code" and code_models:
        return random.choice(code_models)
    elif domain in ("math", "reasoning") and math_models:
        # 60% math specialist, 40% general
        if random.random() < 0.6 and math_models:
            return random.choice(math_models)
    # Default: weighted random from all, prefer top models
    if len(models) <= 5:
        return random.choice(models)
    # Top 30% get 60% of picks
    top_n = max(3, len(models) // 3)
    if random.random() < 0.6:
        return random.choice(models[:top_n])
    return random.choice(models)


def generation_worker(
    task: dict,
    models: list[str],
    store: PairStore,
    timeout: int,
    stats: dict,
    stats_lock: threading.Lock,
):
    """Worker function for thread pool."""
    domain = task["domain"]
    topic = task["topic"]
    strategy = task["strategy"]

    model = select_model_for_domain(models, domain)
    added = 0

    try:
        if strategy == "direct":
            pair = generate_direct(model, domain, topic, timeout)
            if pair and store.add(pair):
                added += 1

        elif strategy == "cross":
            model_b = random.choice([m for m in models if m != model] or models)
            pairs = generate_cross_pollination(model, model_b, domain, topic, timeout)
            for p in pairs:
                if store.add(p):
                    added += 1

        elif strategy == "qa_meta":
            pairs = generate_qa_from_topic(model, domain, topic, timeout)
            for p in pairs:
                if store.add(p):
                    added += 1

        elif strategy == "code_task":
            pair = generate_code_task(model, topic, timeout)
            if pair and store.add(pair):
                added += 1

        elif strategy == "math_reasoning":
            pair = generate_math_reasoning(model, topic, timeout)
            if pair and store.add(pair):
                added += 1

    except Exception as e:
        log.debug(f"Worker error: {e}")

    with stats_lock:
        stats["attempts"] += 1
        stats["added"] += added
        if added == 0:
            stats["failed"] += 1


def build_task_queue(target: int) -> list[dict]:
    """Build a shuffled queue of generation tasks."""
    tasks = []

    # Strategy weights: direct 40%, cross 15%, qa_meta 20%, code 15%, math 10%
    strategies_by_domain = {
        "code":       [("direct", 3), ("code_task", 4), ("cross", 1), ("qa_meta", 2)],
        "math":       [("direct", 2), ("math_reasoning", 4), ("cross", 1), ("qa_meta", 3)],
        "science":    [("direct", 4), ("cross", 2), ("qa_meta", 3)],
        "reasoning":  [("direct", 2), ("math_reasoning", 3), ("cross", 2), ("qa_meta", 3)],
        "creative":   [("direct", 5), ("cross", 3), ("qa_meta", 1)],
        "instruction":[("direct", 5), ("cross", 2), ("qa_meta", 2)],
        "systems":    [("direct", 4), ("cross", 2), ("qa_meta", 3)],
        "ml_ai":      [("direct", 4), ("cross", 2), ("qa_meta", 3)],
    }

    # Generate enough tasks (overshoot by 2x since some will fail/dedup)
    needed = target * 2
    per_domain = needed // len(TOPICS)

    for domain, topics in TOPICS.items():
        strat_pool = strategies_by_domain.get(domain, [("direct", 5), ("cross", 2), ("qa_meta", 3)])
        # Expand strategy pool by weights
        expanded = []
        for s, w in strat_pool:
            expanded.extend([s] * w)

        for _ in range(per_domain // len(topics) + 1):
            for topic in topics:
                strategy = random.choice(expanded)
                tasks.append({
                    "domain": domain,
                    "topic": topic,
                    "strategy": strategy,
                })

    random.shuffle(tasks)
    return tasks


def merge_with_existing(store: PairStore, v2_path: Path):
    """Merge existing v2 training pairs into the store."""
    if not v2_path.exists():
        log.warning(f"No existing training file at {v2_path}")
        return 0

    try:
        with open(v2_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        added = 0
        for pair in existing:
            if store.add(pair):
                added += 1
        log.info(f"Merged {added} pairs from {v2_path.name} (skipped {len(existing) - added} duplicates)")
        return added
    except Exception as e:
        log.error(f"Failed to merge {v2_path}: {e}")
        return 0


def print_stats(store: PairStore):
    """Print domain distribution summary."""
    domains = {}
    providers = {}
    models_used = set()
    with store.lock:
        for p in store.pairs:
            d = p.get("domain", "?")
            domains[d] = domains.get(d, 0) + 1
            prov = p.get("provider", "?")
            providers[prov] = providers.get(prov, 0) + 1
            models_used.add(p.get("model", "?"))

    print("\n" + "=" * 60)
    print(f"TOTAL PAIRS: {store.count()}")
    print("=" * 60)
    print("\nDomain distribution:")
    for d, c in sorted(domains.items(), key=lambda x: -x[1]):
        bar = "#" * min(50, c // max(1, store.count() // 50))
        print(f"  {d:12s} {c:6d} {bar}")
    print(f"\nProvider distribution:")
    for p, c in sorted(providers.items(), key=lambda x: -x[1]):
        print(f"  {p:20s} {c:6d}")
    print(f"\nUnique models used: {len(models_used)}")
    print(f"Total characters: {sum(len(p.get('response','')) for p in store.pairs):,}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NovaX Synthetic Training Data Generator")
    parser.add_argument("--target", type=int, default=50000, help="Target number of pairs")
    parser.add_argument("--output", type=str, default="training_pairs_v3.json",
                        help="Output filename (relative to script dir)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers (1 recommended for single GPU)")
    parser.add_argument("--timeout", type=int, default=90,
                        help="Per-request timeout in seconds")
    parser.add_argument("--save-interval", type=int, default=100,
                        help="Save progress every N pairs")
    parser.add_argument("--no-merge", action="store_true",
                        help="Do not merge existing v2 training pairs")
    parser.add_argument("--models", type=int, default=0,
                        help="Limit number of models to use (0=all available)")
    args = parser.parse_args()

    output_path = SCRIPT_DIR / args.output

    log.info("NovaX Synthetic Training Data Generator v1.0")
    log.info(f"Target: {args.target:,} pairs")
    log.info(f"Output: {output_path}")
    log.info(f"Workers: {args.workers}, Timeout: {args.timeout}s")

    # Get available models
    models = get_available_models()
    if args.models > 0:
        models = models[:args.models]
    log.info(f"Using {len(models)} Ollama models")
    if models:
        log.info(f"Top models: {', '.join(models[:10])}")

    # Initialize store
    store = PairStore(output_path, save_interval=args.save_interval)

    # Merge existing training data
    if not args.no_merge:
        merge_with_existing(store, EXISTING_V2)

    initial_count = store.count()
    log.info(f"Starting with {initial_count} pairs, need {max(0, args.target - initial_count)} more")

    if store.count() >= args.target:
        log.info("Already at target! Nothing to generate.")
        print_stats(store)
        return

    # Build task queue
    tasks = build_task_queue(args.target)
    log.info(f"Task queue: {len(tasks)} tasks across {len(TOPICS)} domains")

    # Stats tracking
    stats = {"attempts": 0, "added": 0, "failed": 0}
    stats_lock = threading.Lock()
    start_time = time.time()

    # Generate — sequential for single-GPU reliability, threaded for multi-worker
    task_idx = 0
    last_report = 0
    try:
        if args.workers == 1:
            # Simple sequential loop — most reliable for single GPU
            while store.count() < args.target and task_idx < len(tasks):
                task = tasks[task_idx]
                task_idx += 1

                generation_worker(task, models, store, args.timeout, stats, stats_lock)

                # Progress report every 10 attempts
                with stats_lock:
                    if stats["attempts"] - last_report >= 10:
                        last_report = stats["attempts"]
                        elapsed = time.time() - start_time
                        rate = stats["added"] / max(1, elapsed) * 3600
                        success_pct = stats["added"] / max(1, stats["attempts"]) * 100
                        eta_hrs = (args.target - store.count()) / max(1, rate) if rate > 0 else 999
                        log.info(
                            f"Progress: {store.count():,}/{args.target:,} pairs | "
                            f"Attempts: {stats['attempts']} | "
                            f"Rate: {rate:.0f}/hr | "
                            f"Success: {success_pct:.0f}% | "
                            f"ETA: {eta_hrs:.1f}h"
                        )

                # Regenerate tasks if running low
                if task_idx >= len(tasks) - 5 and store.count() < args.target:
                    log.info("Regenerating task queue...")
                    new_tasks = build_task_queue(args.target - store.count())
                    tasks.extend(new_tasks)
        else:
            # Multi-worker with thread pool
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                batch_size = args.workers * 2
                futures = {}

                while store.count() < args.target and task_idx < len(tasks):
                    # Fill up the executor
                    while len(futures) < batch_size and task_idx < len(tasks):
                        task = tasks[task_idx]
                        task_idx += 1
                        future = executor.submit(
                            generation_worker, task, models, store,
                            args.timeout, stats, stats_lock,
                        )
                        futures[future] = task

                    # Wait for any completions (no global timeout — individual requests have their own)
                    done = set()
                    try:
                        for future in as_completed(futures, timeout=args.timeout * 3):
                            done.add(future)
                            try:
                                future.result()
                            except Exception as e:
                                log.debug(f"Task exception: {e}")

                            # Progress report
                            with stats_lock:
                                if stats["attempts"] - last_report >= 10:
                                    last_report = stats["attempts"]
                                    elapsed = time.time() - start_time
                                    rate = stats["added"] / max(1, elapsed) * 3600
                                    success_pct = stats["added"] / max(1, stats["attempts"]) * 100
                                    eta_hrs = (args.target - store.count()) / max(1, rate) if rate > 0 else 999
                                    log.info(
                                        f"Progress: {store.count():,}/{args.target:,} pairs | "
                                        f"Rate: {rate:.0f}/hr | "
                                        f"Success: {success_pct:.0f}% | "
                                        f"ETA: {eta_hrs:.1f}h"
                                    )

                            if store.count() >= args.target:
                                break
                    except TimeoutError:
                        log.warning("Batch timed out, continuing with next batch...")
                        done = set(f for f in futures if f.done())

                    for f in done:
                        futures.pop(f, None)
                    # Cancel remaining timed-out futures
                    for f in list(futures):
                        if not f.done():
                            f.cancel()
                            futures.pop(f, None)

                    if task_idx >= len(tasks) - 5 and store.count() < args.target:
                        log.info("Regenerating task queue...")
                        tasks.extend(build_task_queue(args.target - store.count()))

    except KeyboardInterrupt:
        log.info("\nInterrupted! Saving progress...")

    # Final save
    store.flush()

    elapsed = time.time() - start_time
    log.info(f"\nGeneration complete in {elapsed/3600:.1f} hours")
    log.info(f"Attempts: {stats['attempts']}, Added: {stats['added']}, Failed: {stats['failed']}")

    # Print final stats
    print_stats(store)

    # Summary
    print(f"\nOutput: {output_path}")
    print(f"Size: {output_path.stat().st_size / 1e6:.1f} MB")
    new_pairs = store.count() - initial_count
    print(f"New synthetic pairs: {new_pairs:,}")
    print(f"Total pairs: {store.count():,}")


if __name__ == "__main__":
    main()
