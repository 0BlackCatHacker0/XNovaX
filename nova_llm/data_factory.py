"""
NovaX Data Factory — Ollama-powered training data generator
Generates diverse training pairs from 102 local models at ZERO cost.
Target: 9,600+ pairs/day running 24/7.
"""
import json, time, random, hashlib, os, sys, requests
from pathlib import Path
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OUTPUT_FILE = Path("C:/NovaX/data/llm_training/factory_output.jsonl")
CHECKPOINT_FILE = Path("C:/NovaX/data/llm_training/factory_checkpoint.json")
MEGA_FILE = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")

# Models to rotate through (will be populated from Ollama)
PREFERRED_MODELS = [
    "llama3.2:latest", "qwen2.5:latest", "mistral:latest",
    "phi3:latest", "gemma2:latest", "deepseek-r1:latest",
    "falcon3:1b", "novax-falcon3:latest", "novax-qwen2.5-coder:latest",
]

# ── 12-Domain Taxonomy ──────────────────────────────────────────
DOMAINS = {
    "math": [
        "Solve step by step: What is {a} * {b} + {c}?",
        "Explain how to calculate the area of a {shape} with dimensions {dims}.",
        "A store has {n} items at ${price} each. If there's a {pct}% discount, what's the total?",
        "Prove that the sum of the first n natural numbers is n(n+1)/2.",
        "What is the derivative of {func}?",
        "Solve the equation: {a}x^2 + {b}x + {c} = 0",
    ],
    "science": [
        "Explain {concept} in simple terms.",
        "What is the difference between {a} and {b}?",
        "How does {process} work at the molecular level?",
        "Describe the scientific method and give an example.",
        "What causes {phenomenon} and how is it measured?",
    ],
    "coding": [
        "Write a Python function that {task}.",
        "Explain what this code does and suggest improvements:\n```\n{code}\n```",
        "What is the time complexity of {algorithm} and why?",
        "Debug this code: {buggy_code}",
        "Write a {language} function to implement {data_structure}.",
        "How would you design a REST API for {system}?",
    ],
    "reasoning": [
        "If {premise1} and {premise2}, what can we conclude?",
        "What are the pros and cons of {topic}?",
        "Compare and contrast {a} and {b}.",
        "What would happen if {hypothetical}?",
        "Analyze the logical fallacy in: {argument}",
    ],
    "creative": [
        "Write a short story about {theme} in {setting}.",
        "Create a metaphor that explains {concept} to a child.",
        "Write a haiku about {topic}.",
        "Describe {scene} using all five senses.",
    ],
    "explanation": [
        "Explain {topic} like I'm five years old.",
        "What is {concept} and why does it matter?",
        "How would you teach {subject} to a beginner?",
        "Summarize the key ideas of {theory}.",
    ],
    "chain_of_thought": [
        "Think step by step: {problem}",
        "Let's reason through this carefully: {scenario}",
        "Walk me through your reasoning for solving: {puzzle}",
        "Break down the problem into steps: {complex_task}",
    ],
    "instruction": [
        "How do I {task} on {platform}?",
        "Write step-by-step instructions for {process}.",
        "What are the best practices for {activity}?",
        "Create a checklist for {task}.",
    ],
    "conversation": [
        "I'm feeling {emotion} about {situation}. What advice would you give?",
        "Can you help me understand {topic}? I know {background}.",
        "I disagree with the idea that {claim}. What do you think?",
    ],
    "technical_docs": [
        "Write API documentation for a function that {functionality}.",
        "Explain the architecture of a {system_type} system.",
        "What are the security considerations for {technology}?",
    ],
    "data_analysis": [
        "How would you analyze {dataset_type} data to find {insight}?",
        "What statistical test should I use for {scenario}?",
        "Explain the difference between {metric_a} and {metric_b}.",
    ],
    "novax_domain": [
        "Explain ternary computing and why {-1, 0, +1} weights are efficient.",
        "How does a ternary transformer differ from a standard transformer?",
        "What is balanced ternary and what are its mathematical advantages?",
        "Describe how model routing works in a multi-model AI system.",
        "What is knowledge distillation and how does it compress large models?",
    ],
}

# ── Seed Variables ──────────────────────────────────────────────
SEEDS = {
    "a": [7, 13, 42, 99, 256, 1024, 3141],
    "b": [3, 11, 27, 64, 128, 512],
    "c": [1, 5, 10, 23, 50, 100],
    "shape": ["circle", "triangle", "trapezoid", "hexagon", "ellipse"],
    "dims": ["radius 5cm", "base 10 height 7", "sides 3,4,5", "width 8 height 12"],
    "n": [5, 12, 25, 100, 500],
    "price": [9.99, 24.50, 149.99, 3.50],
    "pct": [10, 15, 20, 25, 30, 50],
    "func": ["x^3 + 2x", "sin(x)*cos(x)", "e^(2x)", "ln(x^2+1)", "sqrt(x)*x^2"],
    "concept": ["entropy", "recursion", "photosynthesis", "quantum entanglement",
                 "gradient descent", "natural selection", "neural networks",
                 "relativity", "blockchain", "DNA replication"],
    "process": ["protein folding", "nuclear fusion", "machine learning training",
                "photosynthesis", "cell division", "encryption"],
    "phenomenon": ["aurora borealis", "black holes", "superconductivity", "tides"],
    "task": ["sorts a list using quicksort", "finds all prime numbers up to n",
             "implements a binary search tree", "reverses a linked list",
             "finds the longest palindrome substring", "implements LRU cache"],
    "algorithm": ["quicksort", "binary search", "BFS", "dynamic programming",
                  "merge sort", "Dijkstra's algorithm"],
    "language": ["Python", "Rust", "JavaScript", "Go", "C++"],
    "data_structure": ["hash map", "binary heap", "trie", "graph", "skip list"],
    "system": ["a task management app", "an e-commerce platform", "a chat service"],
    "topic": ["artificial intelligence", "climate change", "space exploration",
              "quantum computing", "renewable energy", "privacy"],
    "theme": ["discovery", "resilience", "transformation", "connection"],
    "setting": ["a distant planet", "underwater city", "medieval kingdom", "2150 Tokyo"],
    "subject": ["calculus", "machine learning", "music theory", "cooking"],
    "theory": ["evolution", "relativity", "game theory", "information theory"],
    "problem": ["Is it better to save $100/month or invest $1000 once per year?",
                "How many piano tuners are in Chicago?",
                "Should a company build or buy their ML infrastructure?"],
    "emotion": ["frustrated", "excited", "overwhelmed", "curious"],
    "situation": ["starting a new project", "learning a new skill", "making a big decision"],
    "technology": ["WebSocket APIs", "microservice architectures", "ternary neural networks"],
    "platform": ["Linux", "Windows", "a Raspberry Pi", "a cloud server"],
    "premise1": ["all humans are mortal", "the temperature is rising", "demand exceeds supply"],
    "premise2": ["Socrates is human", "ice melts above 0C", "prices will increase"],
    "hypothetical": ["gravity was twice as strong", "humans could photosynthesize",
                     "all software was open source"],
    "claim": ["AI will replace all jobs", "remote work is always better",
              "competition drives innovation"],
    "code": ["for i in range(10):\\n    if i % 2:\\n        print(i)",
             "def fib(n):\\n    return n if n<2 else fib(n-1)+fib(n-2)"],
    "buggy_code": ["def avg(lst):\\n    return sum(lst)/len(lst)  # crashes on empty list",
                   "x = [1,2,3]\\nfor i in range(len(x)):\\n    x.append(x[i]*2)  # infinite loop"],
}

# ── Personas ────────────────────────────────────────────────────
PERSONAS = [
    "You are a patient teacher explaining to a beginner.",
    "You are a senior software engineer doing a code review.",
    "You are a scientist writing for a research paper.",
    "You are a friendly tutor helping a high school student.",
    "You are a concise technical writer creating documentation.",
    "You are a creative storyteller with vivid imagery.",
    "You are a logical analyst breaking down complex problems.",
    "You are an enthusiastic mentor encouraging learning.",
]


def get_available_models():
    """Fetch available Ollama models."""
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        # Prefer models we know are good, then add others
        available = [m for m in PREFERRED_MODELS if m in models]
        available += [m for m in models if m not in available]
        return available
    except:
        return PREFERRED_MODELS


def generate_prompt():
    """Generate a diverse prompt from the taxonomy."""
    domain = random.choice(list(DOMAINS.keys()))
    template = random.choice(DOMAINS[domain])

    # Fill in variables
    prompt = template
    for key, values in SEEDS.items():
        placeholder = "{" + key + "}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, str(random.choice(values)), 1)

    return prompt, domain


def query_ollama(model, prompt, persona=None, timeout=60):
    """Query a single Ollama model."""
    system = persona or random.choice(PERSONAS)

    try:
        r = requests.post(OLLAMA_URL, json={
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": random.choice([0.7, 0.8, 0.9, 1.0]),
                "num_predict": 512,
            }
        }, timeout=timeout)

        if r.status_code == 200:
            data = r.json()
            response = data.get("response", "").strip()
            return response
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        return None
    return None


def quality_filter(response):
    """Basic quality filtering."""
    if not response or len(response) < 50:
        return False
    if len(response) > 8000:
        return False
    # Skip error messages
    if response.startswith("Error") or response.startswith("I cannot"):
        return False
    return True


def dedup_hash(prompt, response):
    """MD5 hash for deduplication."""
    return hashlib.md5(f"{prompt}|||{response}".encode()).hexdigest()


def load_checkpoint():
    """Load progress checkpoint."""
    if CHECKPOINT_FILE.exists():
        return json.load(open(CHECKPOINT_FILE))
    return {"total_generated": 0, "total_filtered": 0, "hashes": [], "start_time": time.time()}


def save_checkpoint(state):
    """Save progress checkpoint."""
    # Keep only last 10K hashes to prevent unbounded growth
    state["hashes"] = state["hashes"][-10000:]
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f)


def run_factory():
    """Main data factory loop."""
    print("=" * 60)
    print("  NovaX Data Factory — Ollama Training Data Generator")
    print("=" * 60)

    models = get_available_models()
    print(f"  Models available: {len(models)}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Domains: {len(DOMAINS)}")
    print()

    state = load_checkpoint()
    seen_hashes = set(state.get("hashes", []))
    model_idx = 0

    print(f"  Resuming from {state['total_generated']} generated, {state['total_filtered']} kept")
    print(f"  Press Ctrl+C to stop (progress saved automatically)")
    print("-" * 60)

    pairs_this_session = 0
    session_start = time.time()

    try:
        while True:
            # Rotate model every 3 iterations
            model = models[model_idx % len(models)]

            # Generate prompt
            prompt, domain = generate_prompt()

            # Query model
            t0 = time.time()
            response = query_ollama(model, prompt)
            elapsed = time.time() - t0

            state["total_generated"] += 1

            # Quality filter
            if not quality_filter(response):
                if state["total_generated"] % 10 == 0:
                    print(f"  [{state['total_generated']}] {model[:20]:20s} | FILTERED | {domain}")
                model_idx += 1
                continue

            # Dedup
            h = dedup_hash(prompt, response)
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            # Save pair
            pair = {
                "prompt": prompt,
                "response": response,
                "model": model,
                "domain": domain,
                "timestamp": datetime.now().isoformat(),
                "gen_time": round(elapsed, 2),
            }

            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")

            state["total_filtered"] += 1
            state["hashes"].append(h)
            pairs_this_session += 1

            # Progress
            rate = pairs_this_session / max(1, (time.time() - session_start) / 3600)
            print(f"  [{state['total_filtered']:5d}] {model[:20]:20s} | {domain:15s} | "
                  f"{len(response):4d} chars | {elapsed:.1f}s | {rate:.0f}/hr")

            # Rotate model
            if state["total_generated"] % 3 == 0:
                model_idx += 1

            # Checkpoint every 5 minutes
            if state["total_generated"] % 50 == 0:
                save_checkpoint(state)

    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print(f"  Stopped. Generated: {state['total_generated']}, Kept: {state['total_filtered']}")
        print(f"  Session pairs: {pairs_this_session}")
        elapsed_hrs = (time.time() - session_start) / 3600
        if elapsed_hrs > 0:
            print(f"  Session rate: {pairs_this_session/elapsed_hrs:.0f} pairs/hour")
        save_checkpoint(state)
        print(f"  Checkpoint saved to {CHECKPOINT_FILE}")
        print("=" * 60)


def merge_to_mega():
    """Merge factory output into the mega training file."""
    if not OUTPUT_FILE.exists():
        print("No factory output to merge.")
        return

    # Load existing mega data
    mega = []
    if MEGA_FILE.exists():
        mega = json.load(open(MEGA_FILE, "r", encoding="utf-8"))
    existing = len(mega)

    # Load factory output (JSONL)
    new_pairs = []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    pair = json.loads(line)
                    new_pairs.append(pair)
                except:
                    continue

    # Dedup against existing
    existing_hashes = set()
    for p in mega:
        h = hashlib.md5(f"{p.get('prompt','')}|||{p.get('response','')}".encode()).hexdigest()
        existing_hashes.add(h)

    added = 0
    for p in new_pairs:
        h = hashlib.md5(f"{p['prompt']}|||{p['response']}".encode()).hexdigest()
        if h not in existing_hashes:
            mega.append(p)
            existing_hashes.add(h)
            added += 1

    # Save
    with open(MEGA_FILE, "w", encoding="utf-8") as f:
        json.dump(mega, f, ensure_ascii=False, indent=1)

    print(f"Merged {added} new pairs into mega dataset. Total: {len(mega)} (was {existing})")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "merge":
        merge_to_mega()
    else:
        run_factory()
