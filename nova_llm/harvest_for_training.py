"""
Quick harvester: generate training pairs via NovaX Cloud Router free-tier cascade.
Sends diverse prompts, collects responses, appends to mega dataset.
"""
import json, time, urllib.request, random

ROUTER = "http://127.0.0.1:9878/api/v1/query"
OUT = "C:/NovaX/data/llm_training/training_pairs_mega.json"

PROMPTS = [
    # Math & reasoning
    "Explain the quadratic formula step by step",
    "What is the derivative of x^3 + 2x^2 - 5x + 3?",
    "Prove that the square root of 2 is irrational",
    "Explain eigenvalues and eigenvectors with a simple example",
    "What is Big O notation and why does it matter?",
    "Explain the difference between P and NP problems",
    "How does gradient descent work in machine learning?",
    "What is the chain rule in calculus?",
    "Explain matrix multiplication with a 2x2 example",
    "What are prime numbers and why are they important in cryptography?",
    # Computer science
    "How does a hash table work internally?",
    "Explain the difference between a stack and a queue",
    "What is a binary search tree and how do insertions work?",
    "How does TCP/IP ensure reliable data transmission?",
    "Explain how garbage collection works in programming languages",
    "What is the difference between concurrency and parallelism?",
    "How does public key cryptography work?",
    "Explain how a compiler transforms source code to machine code",
    "What is a neural network and how does backpropagation work?",
    "How do databases use B-trees for indexing?",
    # Science
    "What is entropy and why does it always increase?",
    "Explain how CRISPR gene editing works",
    "What causes the seasons on Earth?",
    "How do black holes form and what happens at the event horizon?",
    "Explain the Heisenberg uncertainty principle",
    "What is the Standard Model of particle physics?",
    "How does photosynthesis convert light to energy?",
    "Explain the theory of general relativity simply",
    "What are gravitational waves and how were they detected?",
    "How does the immune system fight infections?",
    # Engineering
    "How does a CPU execute instructions?",
    "Explain how HTTPS secures web traffic",
    "What is the difference between REST and GraphQL?",
    "How do electric motors convert electricity to motion?",
    "Explain how a transformer architecture processes sequences",
    "What is containerization and how does Docker work?",
    "How does a GPU differ from a CPU architecturally?",
    "Explain the CAP theorem in distributed systems",
    "How do SSDs store data differently from HDDs?",
    "What is WebAssembly and why is it important?",
    # Coding
    "Write a Python function to find the longest common subsequence of two strings",
    "Implement a simple LRU cache in Python",
    "Write a function to detect if a linked list has a cycle",
    "Implement merge sort and explain its time complexity",
    "Write a Python generator that yields Fibonacci numbers",
    "Implement a trie data structure for autocomplete",
    "Write a function to serialize and deserialize a binary tree",
    "Implement Dijkstra's shortest path algorithm",
    "Write a Python decorator that retries a function on failure",
    "Implement a simple regex matcher that handles . and *",
    # Philosophy & writing
    "What is the trolley problem and what does it reveal about ethics?",
    "Explain the difference between deductive and inductive reasoning",
    "What is Occam's Razor and how is it applied in science?",
    "Explain the concept of emergence in complex systems",
    "What is the Turing test and is it still relevant?",
    # More technical depth
    "Explain how attention mechanisms work in transformers with the math",
    "What is the difference between L1 and L2 regularization?",
    "How does batch normalization help train deep networks?",
    "Explain the vanishing gradient problem and how ReLU helps",
    "What is transfer learning and why does it work?",
    "How does tokenization affect language model performance?",
    "Explain the difference between RNNs, LSTMs, and Transformers",
    "What is reinforcement learning from human feedback (RLHF)?",
    "How do diffusion models generate images?",
    "Explain the concept of embeddings in NLP",
    "What is the difference between bagging and boosting?",
    "How does a variational autoencoder work?",
    "Explain the bias-variance tradeoff",
    "What is federated learning?",
    "How does quantization reduce model size while preserving accuracy?",
    # Systems
    "How does virtual memory work in operating systems?",
    "Explain the difference between processes and threads",
    "How does a load balancer distribute traffic?",
    "What is eventual consistency in distributed databases?",
    "How does DNS resolve domain names to IP addresses?",
    "Explain how Git tracks changes internally",
    "What is the difference between symmetric and asymmetric encryption?",
    "How does a CDN improve website performance?",
    "Explain how WebSockets differ from HTTP",
    "What is sharding in databases?",
    # Creative/diverse
    "Explain the Monty Hall problem and why switching is better",
    "What is the Byzantine Generals Problem?",
    "How does error correction work in QR codes?",
    "Explain the concept of information entropy from Shannon's theory",
    "What is a zero-knowledge proof?",
    "How do recommendation systems work?",
    "Explain the halting problem and its implications",
    "What is homomorphic encryption?",
    "How does consensus work in blockchain?",
    "Explain the concept of dimensional reduction with PCA",
]

def query(prompt, max_tokens=1024):
    body = json.dumps({"prompt": prompt, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(ROUTER, body, {"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        result = data.get("result", {})
        text = result.get("response", "")
        provider = result.get("provider", data.get("provider", "unknown"))
        model = result.get("model", "unknown")
        return text, provider, model
    except Exception as e:
        return "", "error", str(e)

def main():
    # Load existing
    with open(OUT, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    existing_prompts = {p.get("prompt", "")[:80] for p in pairs}

    print(f"Existing: {len(pairs)} pairs")
    print(f"Prompts to harvest: {len(PROMPTS)}")

    added = 0
    for i, prompt in enumerate(PROMPTS):
        if prompt[:80] in existing_prompts:
            print(f"  [{i+1}/{len(PROMPTS)}] SKIP (exists): {prompt[:50]}")
            continue

        text, provider, model = query(prompt)
        if len(text) < 20:
            print(f"  [{i+1}/{len(PROMPTS)}] FAIL ({provider}): {prompt[:50]}")
            continue

        pairs.append({
            "prompt": prompt,
            "response": text,
            "domain": "harvested",
            "provider": provider,
            "model": model
        })
        added += 1
        print(f"  [{i+1}/{len(PROMPTS)}] OK ({provider}/{model}): {prompt[:50]}... ({len(text)} chars)")

        # Rate limit
        time.sleep(0.5)

    # Save
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(pairs, f, ensure_ascii=False)

    total_chars = sum(len(p.get("prompt", "")) + len(p.get("response", "")) for p in pairs)
    print(f"\nDone: +{added} new pairs, {len(pairs)} total, {total_chars:,} chars ({total_chars/1e6:.1f}M)")

if __name__ == "__main__":
    main()
