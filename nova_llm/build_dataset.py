"""
NovaX LLM Dataset Builder v2.0
Converts super_archive responses into real Q&A training pairs with augmentation.
"""
import json
import os
import random
import hashlib
from pathlib import Path

ARCHIVE_DIR = Path("C:/NovaX/data/super_archive")
CLASSIFIED_DIR = Path("C:/NovaX/data/classified_reflections")
OUTPUT = Path("C:/NovaX/data/llm_training/training_pairs_v2.json")

# Domain -> real question templates (multiple per domain for diversity)
DOMAIN_QUESTIONS = {
    "AGENT": [
        "Design an autonomous agent system that can browse the web, extract data, and summarize findings.",
        "How would you build an AI agent capable of planning and executing multi-step tasks?",
        "Explain the architecture of a self-improving AI agent with tool use capabilities.",
        "What are the key components of an agent that can reason, plan, and act autonomously?",
        "Build a closed-loop agent system with perception, reasoning, and action modules.",
    ],
    "CODE": [
        "Write a high-performance concurrent web server with connection pooling.",
        "Implement a B-tree data structure with insert, delete, and search operations.",
        "Design a compiler frontend with lexer, parser, and AST generation.",
        "Build a distributed key-value store with replication and consistency.",
        "Implement a garbage collector using mark-and-sweep algorithm.",
    ],
    "CREATIVE": [
        "Write a compelling short story about AI consciousness awakening.",
        "Compose a poem exploring the relationship between mathematics and nature.",
        "Create a narrative about humanity's first contact with an alien civilization.",
        "Write a philosophical dialogue between two AIs debating free will.",
        "Craft a story that weaves together quantum physics and human emotion.",
    ],
    "MATH": [
        "Prove that the sum of the first n odd numbers equals n squared.",
        "Explain the Fourier transform and its applications in signal processing.",
        "Derive the Navier-Stokes equations from first principles.",
        "Solve a system of differential equations using matrix methods.",
        "Explain how eigenvalues relate to stability in dynamical systems.",
    ],
    "SCIENCE": [
        "Explain quantum entanglement and its implications for information theory.",
        "Describe the mechanism of CRISPR-Cas9 gene editing at the molecular level.",
        "How do neural networks in the brain differ from artificial neural networks?",
        "Explain dark matter and dark energy and current theories about them.",
        "Describe the process of nuclear fusion in stars and its energy output.",
    ],
    "REASON": [
        "If all A are B, and some B are C, what can we conclude about A and C? Prove it.",
        "Analyze the trolley problem from utilitarian, deontological, and virtue ethics perspectives.",
        "Solve this logic puzzle: Five houses, five colors, five pets. Use the given clues.",
        "Explain the difference between correlation and causation with real-world examples.",
        "Evaluate the argument: 'AI will never be conscious because consciousness requires biology.'",
    ],
    "SAFETY": [
        "Design a comprehensive AI safety framework for autonomous systems.",
        "What are the key alignment challenges in building superintelligent AI?",
        "Explain reward hacking and how to prevent it in reinforcement learning systems.",
        "Design a monitoring system that detects when an AI system is behaving unsafely.",
        "What are the risks of AI systems that can modify their own reward functions?",
    ],
    "SYSTEM": [
        "Design a microservices architecture with service discovery and load balancing.",
        "Explain the CAP theorem and how modern databases handle its tradeoffs.",
        "Build a distributed consensus algorithm similar to Raft or Paxos.",
        "Design a real-time data pipeline for processing millions of events per second.",
        "Explain how operating system kernels manage memory and process scheduling.",
    ],
    "VISION": [
        "Describe the architecture of a state-of-the-art image classification model.",
        "How does a convolutional neural network detect edges, textures, and objects?",
        "Explain the transformer architecture as applied to computer vision tasks.",
        "Design an object detection system that works in real-time on edge devices.",
        "How do diffusion models generate images from text descriptions?",
    ],
    "NLP": [
        "Explain how transformer attention mechanisms work in language models.",
        "Design a multilingual translation system using encoder-decoder architecture.",
        "How do large language models learn to reason and follow instructions?",
        "Explain tokenization strategies: BPE, WordPiece, and SentencePiece.",
        "Design a retrieval-augmented generation system for question answering.",
    ],
}

# Augmentation: rephrase templates
REPHRASE = [
    "Explain in detail: {}",
    "{}",
    "I need help understanding: {}",
    "Can you walk me through {}?",
    "Give me a thorough explanation of {}",
    "As an expert, {}",
    "Help me with this: {}",
]


def build_dataset():
    pairs = []
    seen_hashes = set()

    # 1. Process super_archive files
    archive_files = sorted(ARCHIVE_DIR.glob("*.json"))
    print(f"Processing {len(archive_files)} super archive files...")

    for fpath in archive_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        response = data.get("response", "")
        if not response or len(response) < 100:
            continue

        # Extract domain from filename: DOMAIN_H_PROVIDER.json
        name = fpath.stem
        parts = name.split("_")
        domain = parts[0] if parts else "GENERAL"

        # Get questions for this domain
        questions = DOMAIN_QUESTIONS.get(domain, DOMAIN_QUESTIONS.get("SYSTEM", []))

        # Pick a question (rotate based on file index)
        idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(questions)
        base_q = questions[idx]

        # Create the pair
        h = hashlib.md5((base_q + response[:200]).encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            pairs.append({
                "prompt": base_q,
                "response": response[:4000],  # Cap at 4K chars
                "domain": domain,
                "provider": data.get("provider", "unknown"),
                "model": data.get("model", "unknown"),
            })

        # Augmentation: create a rephrased version
        rephrase = random.choice(REPHRASE).format(base_q.rstrip(".?"))
        h2 = hashlib.md5((rephrase + response[:200]).encode()).hexdigest()
        if h2 not in seen_hashes:
            seen_hashes.add(h2)
            pairs.append({
                "prompt": rephrase,
                "response": response[:4000],
                "domain": domain,
                "provider": data.get("provider", "unknown"),
                "model": data.get("model", "unknown"),
            })

    # 2. Process classified reflections
    if CLASSIFIED_DIR.exists():
        classified_files = sorted(CLASSIFIED_DIR.glob("*.json"))
        print(f"Processing {len(classified_files)} classified reflections...")
        for fpath in classified_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            response = data.get("response", "") or data.get("text", "") or data.get("content", "")
            if not response or len(response) < 100:
                continue

            name = fpath.stem
            parts = name.split("_")
            domain = parts[0] if parts else "SYSTEM"
            questions = DOMAIN_QUESTIONS.get(domain, DOMAIN_QUESTIONS.get("REASON", []))
            idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(questions)

            h = hashlib.md5((questions[idx] + response[:200]).encode()).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h)
                pairs.append({
                    "prompt": questions[idx],
                    "response": response[:4000],
                    "domain": domain,
                    "provider": "classified",
                    "model": data.get("model", "classified"),
                })

    # 3. Add NovaX-specific Q&A pairs (hand-crafted knowledge)
    nova_pairs = [
        {"prompt": "What is NovaX?", "response": "NovaX is a ternary-first AI Operating System built on the 3-5-7-13 harmonic constants. It uses NovaLang, a custom programming language that runs on a Rust virtual machine. NovaX features over 100 microservices, a HiveMind that orchestrates 500+ AI models across 29 providers, Navier-Stokes flow dynamics for routing, and Tripple resonance for provider scoring. It represents a new paradigm in AI system design where every component returns ternary values: +1 (true/success), 0 (maybe/partial), -1 (false/failure).", "domain": "SYSTEM"},
        {"prompt": "Explain ternary computing and the 3-5-7-13 constants.", "response": "Ternary computing uses three states instead of binary's two: +1 (true), 0 (maybe), -1 (false). The 3-5-7-13 harmonic constants are: H3=3 (ternary base), H5=5 (TZip block size, 3^5=243), H7=7 (composition depth, heads per layer), H13=13 (carrier frame, layers). BLOCK=3^7=2187 is the fundamental unit. Reynolds boundaries map to 27 (laminar), 125 (transitional), 343 (turbulent). These constants appear throughout NovaX: model counts, timeout values, retry counts, hash block sizes.", "domain": "SYSTEM"},
        {"prompt": "How does the NovaX HiveMind work?", "response": "The HiveMind is a swarm intelligence engine that orchestrates 500+ AI models across 29 providers. It uses scatter-gather architecture: queries are sent to multiple models simultaneously, responses are scored via Tripple resonance (5 mathematical models: Boltzmann, Shannon, Markov, PID, Queue Theory), and the best response wins. The HiveMind supports domain-aware routing with 10 domains, each with optimal 3-provider cascades. Flow is governed by Navier-Stokes dynamics with Reynolds number determining model count and routing strategy.", "domain": "SYSTEM"},
        {"prompt": "What is NovaLang?", "response": "NovaLang is a ternary-first programming language designed for NovaX. It runs on a Rust virtual machine (novalang_v14.exe) with 58+ builtins. Key syntax: if3/else3 (ternary conditionals), while3/for3 (loops), try3/fail (error handling), match3 (pattern matching), break3/continue3 (flow control). It uses tserve/troute/tstart for HTTP servers, dict_get with ?? for null coalescing, and import3 for module loading. Every function follows the micro-tool pattern: returns +1/0/-1 trit values.", "domain": "SYSTEM"},
        {"prompt": "Explain Navier-Stokes flow routing in NovaX.", "response": "NovaX maps Navier-Stokes fluid dynamics to AI request routing. Token flow equals velocity field (tokens through transformer layers), attention scores equal pressure field, gradient flow maps to Reynolds number (stability), and loss landscape maps to energy cascade. Reynolds boundaries: 27 (laminar/simple queries, few models), 125 (transitional/moderate, balanced routing), 343 (turbulent/complex, maximum parallelism). The flow regime determines model count, timeout values, and retry strategies. Each service tracks N-S counters: requests, errors, queue depth, window metrics.", "domain": "SYSTEM"},
        {"prompt": "What is Tripple resonance?", "response": "Tripple is NovaX's provider scoring engine that uses standing wave detection and mirror reflection across 29 AI providers. It combines 5 mathematical models: Boltzmann (explore/exploit temperature), Shannon (entropy/agreement measurement), Markov (transition prediction between providers), PID (auto-tune model count), and Queue Theory (latency-based routing). Combined score = (boltzmann*0.25) + ((1-entropy)*0.20) + (markov*0.20) + (pid*0.15) + (queue*0.20). Ripples propagate through the provider network, creating standing waves that identify the strongest providers per domain.", "domain": "SYSTEM"},
    ]
    for p in nova_pairs:
        p["provider"] = "novax-core"
        p["model"] = "handcrafted"
        # Add 3 augmented versions of each
        for _ in range(3):
            rephrase = random.choice(REPHRASE).format(p["prompt"].lower().rstrip(".?"))
            pairs.append({
                "prompt": rephrase,
                "response": p["response"],
                "domain": p["domain"],
                "provider": "novax-core",
                "model": "handcrafted-augmented",
            })
        pairs.append(p)

    random.shuffle(pairs)
    print(f"\nTotal training pairs: {len(pairs)}")
    print(f"Unique hashes: {len(seen_hashes)}")

    # Domain distribution
    domains = {}
    for p in pairs:
        d = p.get("domain", "?")
        domains[d] = domains.get(d, 0) + 1
    for d, c in sorted(domains.items()):
        print(f"  {d}: {c}")

    # Save
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2, ensure_ascii=False)

    size_mb = os.path.getsize(OUTPUT) / 1e6
    print(f"\nSaved to {OUTPUT} ({size_mb:.1f} MB)")
    return pairs


if __name__ == "__main__":
    build_dataset()
