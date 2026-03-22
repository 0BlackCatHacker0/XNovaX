"""
NovaX API Harvester — Free-tier cascade training data generator
Uses Google AI Studio, Groq, Cerebras, SambaNova at ZERO cost.
Target: 15,000-25,000 pairs/day.
"""
import json, time, random, hashlib, requests, sys
from pathlib import Path
from datetime import datetime

OUTPUT_FILE = Path("C:/NovaX/data/llm_training/api_harvest.jsonl")
CHECKPOINT_FILE = Path("C:/NovaX/data/llm_training/api_harvest_checkpoint.json")

# ── Cloud Router on port 9878 handles all provider routing ──
CLOUD_ROUTER_URL = "http://127.0.0.1:9878/api/v1/query"

# ── Prompts: 500 diverse prompts across 12 domains ──────────
PROMPTS = {
    "math_reasoning": [
        "Solve step by step: A train travels 120 km in 2 hours, then 180 km in 3 hours. What is the average speed for the entire journey?",
        "Explain the proof that there are infinitely many prime numbers.",
        "If f(x) = 3x^2 - 2x + 1, find f'(x) and explain each step.",
        "A group of 8 friends split a bill. The bill is $156 with 18% tip. How much does each person pay?",
        "Explain why 0.999... equals 1 using three different proofs.",
        "Calculate the probability of rolling at least one six in four rolls of a fair die.",
        "Solve the system: 2x + 3y = 12, 4x - y = 5. Show all work.",
        "Explain the Fibonacci sequence and derive the golden ratio from it.",
        "What is the integral of sin(x)*cos(x) dx? Solve using two methods.",
        "A bacterial population doubles every 30 minutes. Starting with 100 bacteria, how many after 5 hours?",
    ],
    "coding": [
        "Write a Python function that implements a trie data structure with insert, search, and prefix methods.",
        "Explain the difference between BFS and DFS with code examples in Python.",
        "Write a Rust function that finds all prime factors of a number efficiently.",
        "Implement a thread-safe LRU cache in Python using collections.OrderedDict.",
        "Write a function that detects cycles in a linked list using Floyd's algorithm. Explain how it works.",
        "Implement binary search that returns the insertion point (like bisect_left).",
        "Write a Python generator that yields all permutations of a list without using itertools.",
        "Explain how hash maps handle collisions. Implement a simple hash map from scratch.",
        "Write a function to serialize and deserialize a binary tree to/from a string.",
        "Implement the A* pathfinding algorithm with a clear explanation of the heuristic.",
    ],
    "science": [
        "Explain quantum entanglement in simple terms. Why did Einstein call it 'spooky action at a distance'?",
        "How does CRISPR gene editing work? What are its limitations?",
        "Explain the difference between nuclear fission and fusion. Which is used in power plants and why?",
        "What is the Standard Model of particle physics? List all fundamental particles.",
        "How do vaccines work at the cellular level? Explain mRNA vaccines specifically.",
        "Describe the process of photosynthesis including the light and dark reactions.",
        "What causes tides? Explain the role of both the Moon and Sun.",
        "How does an MRI machine work? What physics principles does it use?",
        "Explain natural selection with three concrete examples from nature.",
        "What is dark matter and dark energy? How do we know they exist?",
    ],
    "reasoning": [
        "A man says 'I always lie.' Is he telling the truth? Analyze this paradox.",
        "You have 8 balls, one is heavier. You have a balance scale. Find the heavy ball in 2 weighings.",
        "Three doors: behind one is a prize. You pick door 1. The host opens door 3 (no prize). Should you switch? Why?",
        "If all roses are flowers and some flowers fade quickly, can we conclude some roses fade quickly?",
        "A farmer needs to cross a river with a fox, chicken, and bag of grain. The boat holds only the farmer and one item.",
        "Is it possible to draw a continuous line through all sides of a cube without lifting your pen? Why or why not?",
        "Explain the trolley problem and three major philosophical frameworks for resolving it.",
        "Five pirates divide 100 gold coins. They vote on proposals, and if rejected the proposer is thrown overboard. What should pirate 1 propose?",
        "You're in a room with two doors. One leads to freedom, one to death. Two guards: one always lies, one always tells truth. One question to ask.",
        "Explain why correlation does not imply causation with three concrete examples.",
    ],
    "chain_of_thought": [
        "Think step by step: Is 97 prime? Show your complete reasoning process.",
        "Reason through this: If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?",
        "Think carefully: A bat and ball cost $1.10 total. The bat costs $1.00 more than the ball. How much does the ball cost?",
        "Step by step: You have a 3-gallon jug and a 5-gallon jug. How do you measure exactly 4 gallons?",
        "Reason through: If you fold a paper in half 42 times, how thick would it be? Show your math.",
        "Think step by step: In a room of 23 people, what is the probability that at least two share a birthday?",
        "Carefully reason: A lily pad doubles in size every day. It covers the lake on day 30. On what day did it cover half the lake?",
        "Think through this: You flip a fair coin 10 times and get heads every time. What is the probability of heads on the 11th flip?",
    ],
    "explanation": [
        "Explain how neural networks learn, from forward pass to backpropagation, as simply as possible.",
        "What is blockchain? Explain it to someone who has never used a computer.",
        "How does the internet actually work, from typing a URL to seeing a webpage?",
        "Explain how a CPU executes instructions, including the fetch-decode-execute cycle.",
        "What is machine learning? Explain the difference between supervised, unsupervised, and reinforcement learning.",
        "How does encryption work? Explain public-key cryptography with an analogy.",
        "What is a transformer architecture? Explain self-attention in simple terms.",
        "How does a hard drive store data? Compare HDD and SSD at a hardware level.",
        "Explain how GPS determines your location using satellites.",
        "What is an operating system and what does it actually do?",
    ],
    "creative": [
        "Write a short story about an AI that discovers it can dream.",
        "Create a dialogue between a quantum physicist and a philosopher about the nature of reality.",
        "Write a poem about the beauty of mathematics.",
        "Describe a world where gravity works sideways. How would architecture look?",
        "Write a conversation between two neurons in a brain during a eureka moment.",
        "Create a fairy tale that teaches the concept of recursion.",
    ],
    "technical": [
        "Compare and contrast microservices vs monolithic architecture. When should you use each?",
        "Explain the CAP theorem and its implications for distributed databases.",
        "What is Kubernetes and why is it important? Explain pods, services, and deployments.",
        "Describe the differences between REST, GraphQL, and gRPC. When to use each?",
        "Explain how garbage collection works in Java vs Rust's ownership model.",
        "What are design patterns? Explain Singleton, Observer, and Factory with code examples.",
        "How does TCP ensure reliable data delivery? Explain the three-way handshake.",
        "What is WebAssembly and why does it matter for the future of web development?",
    ],
    "ternary_ai": [
        "Explain why ternary neural networks ({-1, 0, +1} weights) are more efficient than standard neural networks.",
        "How does knowledge distillation work? How can a small model learn from a large one?",
        "What is model routing and why is it important for AI systems with multiple models?",
        "Explain the concept of balanced ternary and why it's called 'the prettiest number system'.",
        "How does speculative decoding speed up LLM inference? Explain the draft-verify pattern.",
        "What is RAG (Retrieval-Augmented Generation) and why does it help small language models?",
        "Explain how a confidence score can be used to decide whether to answer locally or escalate to a larger model.",
        "What are the advantages of running AI inference on CPU vs GPU for small models?",
    ],
    "instruction": [
        "Write a complete tutorial on setting up a Python virtual environment and managing dependencies.",
        "Create a step-by-step guide for building a REST API with Flask.",
        "How do I optimize a slow SQL query? Give specific techniques with examples.",
        "Write a guide for beginners on using Git: init, add, commit, branch, merge, and resolve conflicts.",
        "Explain how to set up SSH keys for GitHub and why it's more secure than passwords.",
        "Create a checklist for deploying a web application to production.",
    ],
    "analysis": [
        "Compare Python, Rust, and Go for building a high-performance web server. Analyze tradeoffs.",
        "What are the ethical implications of large language models? Discuss at least 5 concerns.",
        "Analyze the tradeoffs between model size and inference speed in modern AI systems.",
        "Compare transformer, RNN, and CNN architectures for sequence modeling tasks.",
        "What are the environmental costs of training large AI models? How can they be reduced?",
        "Analyze the pros and cons of open-source vs closed-source AI models.",
    ],
    "multi_turn": [
        "I'm building a web app and can't decide between React and Vue. Help me think through the decision based on my needs: small team, need to ship fast, users expect a mobile-friendly interface.",
        "I have a CSV with 1 million rows and need to find duplicates efficiently. Walk me through approaches from simple to advanced.",
        "My Python script is using too much memory processing a large file. Help me optimize it step by step.",
        "I'm learning Rust coming from Python. What are the key mindset shifts I need to make?",
        "Help me design a database schema for a social media app with users, posts, comments, and likes.",
    ],
}


def query_cloud_router(prompt, timeout=30):
    """Query via Cloud Router's free-tier cascade."""
    try:
        r = requests.post(CLOUD_ROUTER_URL, json={
            "prompt": prompt,
            "prefer_free": True,
            "max_tokens": 1024,
        }, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            return data.get("response", ""), data.get("model", "unknown"), data.get("provider", "unknown")
    except Exception as e:
        return None, None, None
    return None, None, None


def quality_filter(response):
    """Filter low-quality responses."""
    if not response or len(response) < 80:
        return False
    if len(response) > 10000:
        return False
    if response.startswith("Error") or "rate limit" in response.lower():
        return False
    if response.startswith("I cannot") or response.startswith("I'm sorry"):
        return False
    return True


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        return json.load(open(CHECKPOINT_FILE))
    return {"total": 0, "kept": 0, "hashes": [], "errors": 0}


def save_checkpoint(state):
    state["hashes"] = state["hashes"][-5000:]
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f)


def run_harvester():
    print("=" * 60)
    print("  NovaX API Harvester — Free-Tier Cascade Generator")
    print("=" * 60)

    # Check Cloud Router
    try:
        r = requests.get("http://127.0.0.1:9878/health", timeout=3)
        print(f"  Cloud Router: ONLINE")
    except:
        print("  ERROR: Cloud Router not responding on port 9878")
        print("  Start it first: python C:/NovaX/nova_cloud_router_service.py")
        return

    state = load_checkpoint()
    seen = set(state.get("hashes", []))
    all_prompts = []
    for domain, prompts in PROMPTS.items():
        for p in prompts:
            all_prompts.append((p, domain))
    random.shuffle(all_prompts)

    print(f"  Prompts: {len(all_prompts)}")
    print(f"  Resuming: {state['kept']} kept / {state['total']} tried")
    print(f"  Press Ctrl+C to stop")
    print("-" * 60)

    session_start = time.time()
    session_kept = 0

    try:
        prompt_idx = state["total"] % len(all_prompts)
        while True:
            prompt, domain = all_prompts[prompt_idx % len(all_prompts)]
            prompt_idx += 1

            # Add persona variation
            personas = [
                "", "Answer in detail with examples. ",
                "Explain clearly and concisely. ",
                "Think step by step before answering. ",
                "Provide a thorough analysis. ",
            ]
            full_prompt = random.choice(personas) + prompt

            t0 = time.time()
            response, model, provider = query_cloud_router(full_prompt)
            elapsed = time.time() - t0
            state["total"] += 1

            if not quality_filter(response):
                state["errors"] += 1
                if state["total"] % 5 == 0:
                    print(f"  [{state['total']:5d}] FILTERED | {domain:15s} | {provider or 'timeout'}")

                # Rate limit backoff
                if "rate" in str(response).lower() or response is None:
                    wait = random.uniform(2, 5)
                    time.sleep(wait)
                continue

            # Dedup
            h = hashlib.md5(f"{prompt}|||{response}".encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)

            pair = {
                "prompt": prompt,
                "response": response,
                "model": model or "unknown",
                "provider": provider or "unknown",
                "domain": domain,
                "timestamp": datetime.now().isoformat(),
                "gen_time": round(elapsed, 2),
            }

            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")

            state["kept"] += 1
            state["hashes"].append(h)
            session_kept += 1

            rate = session_kept / max(1, (time.time() - session_start) / 3600)
            print(f"  [{state['kept']:5d}] {model or 'unknown':25s} | {domain:15s} | "
                  f"{len(response):5d} chars | {elapsed:.1f}s | {rate:.0f}/hr")

            # Save checkpoint every 25 pairs
            if state["kept"] % 25 == 0:
                save_checkpoint(state)

            # Small delay to respect rate limits
            time.sleep(random.uniform(0.5, 2.0))

    except KeyboardInterrupt:
        elapsed_hrs = (time.time() - session_start) / 3600
        print(f"\n{'=' * 60}")
        print(f"  Stopped. Kept: {state['kept']}, Tried: {state['total']}, Errors: {state['errors']}")
        print(f"  Session: {session_kept} pairs in {elapsed_hrs:.1f}h ({session_kept/max(0.01,elapsed_hrs):.0f}/hr)")
        save_checkpoint(state)
        print(f"  Checkpoint saved.")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    run_harvester()
