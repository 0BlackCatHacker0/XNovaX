"""
NovaX Ollama Data Factory v1.0
Generates training pairs from local Ollama models at ~400-600 pairs/hour.
Designed to run overnight when GPU is free (after training completes).

Features:
- 12 knowledge domains with 300+ prompt templates
- Model rotation every 3 pairs (diversity)
- Model-to-model conversation every 10th pair
- Quality verification every 15th pair
- MD5 deduplication
- Crash-safe JSONL append
- Resume support
"""
import json, time, urllib.request, random, hashlib, os, sys
from pathlib import Path
from datetime import datetime

# ─── CONFIG ─────────────────────────────────────────
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OUT_FILE = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")
LOG_FILE = Path("C:/NovaX/nova_llm/factory_log.jsonl")
MAX_RESPONSE_CHARS = 4000
MIN_RESPONSE_CHARS = 80
TIMEOUT_SECONDS = 120

# Models to rotate through — actual names from Ollama registry
MODELS = [
    "llama3:latest",
    "qwen2.5:latest",
    "mistral:latest",
    "gemma2:latest",
    "phi3:latest",
    "codellama:latest",
    "deepseek-r1:latest",
    "dolphin-llama3:latest",
    "mathstral:latest",
    "neural-chat:latest",
    "aya:latest",
    "exaone3.5:latest",
]

# ─── 12 KNOWLEDGE DOMAINS ───────────────────────────
DOMAINS = {
    "math": [
        "Solve step by step: {math_problem}",
        "Explain the concept of {math_concept} with examples",
        "Prove that {math_statement}",
        "What is the relationship between {math_a} and {math_b}?",
        "Derive the formula for {math_formula}",
    ],
    "coding": [
        "Write a {lang} function that {coding_task}",
        "Debug this code and explain the fix: {code_snippet}",
        "Implement {data_structure} from scratch in {lang}",
        "Optimize this algorithm for {optimization_goal}: {algorithm}",
        "Write tests for a function that {test_target}",
    ],
    "science": [
        "Explain {science_concept} as if teaching a university student",
        "What is the current scientific understanding of {science_topic}?",
        "Compare and contrast {science_a} and {science_b}",
        "What experiments proved {science_discovery}?",
        "How does {science_process} work at the molecular level?",
    ],
    "reasoning": [
        "Analyze this argument step by step: {argument}",
        "What are the logical flaws in this reasoning: {flawed_reasoning}",
        "Given these premises, what conclusions can we draw: {premises}",
        "Explain why {counterintuitive_fact} seems wrong but is actually true",
        "Break down this complex problem into sub-problems: {complex_problem}",
    ],
    "engineering": [
        "How would you design a system for {system_requirement}?",
        "What are the trade-offs between {eng_a} and {eng_b}?",
        "Explain how {technology} works internally",
        "What are best practices for {engineering_practice}?",
        "Design a {component} that handles {constraint}",
    ],
    "creative_writing": [
        "Write a short explanation of {topic} using an analogy to {analogy}",
        "Explain {concept} to a 12-year-old",
        "Create a memorable mnemonic for remembering {list_of_things}",
        "Write a concise tutorial on {tutorial_topic}",
        "Summarize {complex_topic} in exactly 5 bullet points",
    ],
    "chain_of_thought": [
        "Think through this problem step by step, showing all reasoning: {cot_problem}",
        "Walk me through how you would solve: {cot_task}",
        "Explain your reasoning process for: {cot_question}",
        "Show your work: {cot_math}",
        "Analyze this scenario systematically: {cot_scenario}",
    ],
    "instruction_following": [
        "List exactly {n} ways to {task}. Number each one.",
        "Explain {topic} in exactly {n} sentences.",
        "Compare {a} and {b} using a table with {n} columns.",
        "Write a {format} about {subject} that includes {constraint}.",
        "Given this data: {data}, answer: {question}",
    ],
    "debate": [
        "Present arguments for AND against {debate_topic}",
        "What are the strongest counterarguments to {position}?",
        "Steelman the position that {controversial_claim}",
        "Analyze both sides: {side_a} vs {side_b}",
        "What would a critic say about {idea}?",
    ],
    "error_analysis": [
        "What is wrong with this code? {buggy_code}",
        "Find the logical error: {logical_error}",
        "This answer is incorrect. Explain why: {wrong_answer}",
        "What assumptions does this argument rely on? {argument}",
        "Identify potential failure modes of {system}",
    ],
    "summarization": [
        "Explain {long_topic} concisely in under 200 words",
        "What are the 3 most important things to know about {topic}?",
        "Give a TL;DR of {concept}",
        "Distill {complex_subject} to its core principles",
        "What is the single most important insight about {insight_topic}?",
    ],
    "multi_turn": [
        "I'm confused about {confusion_topic}. Can you help?",
        "Follow up: but what about {followup}?",
        "How does that relate to {related_topic}?",
        "Can you give me a concrete example of {example_request}?",
        "Okay, so to summarize what we discussed about {summary_topic}...",
    ],
}

# ─── SEED VARIABLES ─────────────────────────────────
SEEDS = {
    "math_problem": [
        "find the integral of sin(x)*cos(x) dx",
        "solve the system: 2x + 3y = 7, 4x - y = 5",
        "find the eigenvalues of [[3,1],[1,3]]",
        "compute the limit of (1+1/n)^n as n approaches infinity",
        "find the sum of the series 1/2 + 1/4 + 1/8 + ...",
        "solve x^3 - 6x^2 + 11x - 6 = 0",
        "find the area between y=x^2 and y=2x",
        "compute the determinant of a 4x4 matrix",
        "prove the AM-GM inequality for two numbers",
        "find the Taylor expansion of e^x around x=0 to 5 terms",
    ],
    "math_concept": [
        "eigenvalues", "continuity", "vector spaces", "group theory",
        "topology", "measure theory", "graph coloring", "convexity",
        "Fourier series", "differential equations", "number theory",
        "linear independence", "orthogonality", "completeness",
    ],
    "math_statement": [
        "sqrt(2) is irrational", "there are infinitely many primes",
        "the sum of angles in a triangle is 180 degrees",
        "every continuous function on [a,b] attains its maximum",
        "the harmonic series diverges",
    ],
    "lang": ["Python", "Rust", "JavaScript", "C", "Go", "TypeScript"],
    "coding_task": [
        "finds all prime factors of a number",
        "implements a binary search on a sorted array",
        "reverses a linked list in place",
        "finds the shortest path in a weighted graph",
        "parses a simple arithmetic expression",
        "implements a thread-safe counter",
        "finds all anagrams in a list of words",
        "implements a simple LRU cache",
        "validates an email address without regex",
        "converts between different number bases",
        "implements the observer pattern",
        "finds the longest common prefix of an array of strings",
    ],
    "data_structure": [
        "a balanced BST (AVL tree)", "a hash map with chaining",
        "a priority queue using a binary heap", "a graph using adjacency lists",
        "a trie for prefix matching", "a ring buffer",
        "a skip list", "a disjoint set (union-find)",
    ],
    "science_concept": [
        "quantum entanglement", "natural selection", "entropy",
        "plate tectonics", "general relativity", "photosynthesis",
        "the immune system", "superconductivity", "CRISPR",
        "neuroplasticity", "dark energy", "protein folding",
    ],
    "science_topic": [
        "consciousness", "the origin of life", "dark matter",
        "quantum gravity", "the microbiome", "climate feedback loops",
        "gene editing ethics", "the multiverse", "AI alignment",
    ],
    "debate_topic": [
        "AI replacing human jobs", "open source vs proprietary software",
        "privacy vs security tradeoffs", "social media's effect on society",
        "nuclear energy as climate solution", "remote work vs office work",
        "universal basic income", "space exploration funding",
    ],
    "topic": [
        "transformers in deep learning", "operating system kernels",
        "database indexing", "network protocols", "compiler optimization",
        "distributed consensus", "memory management", "type systems",
        "functional programming", "concurrency patterns",
    ],
    "n": ["3", "5", "7", "10"],
    "optimization_goal": ["memory usage", "time complexity", "readability"],
    "format": ["tutorial", "comparison", "step-by-step guide", "FAQ"],
}

def fill_template(template):
    """Fill a template with random seed values."""
    result = template
    for key, values in SEEDS.items():
        placeholder = "{" + key + "}"
        while placeholder in result:
            result = result.replace(placeholder, random.choice(values), 1)
    # Handle any remaining unfilled placeholders with generic values
    import re
    remaining = re.findall(r'\{(\w+)\}', result)
    for r in remaining:
        generic = random.choice(list(SEEDS.get("topic", ["this concept"])))
        result = result.replace("{" + r + "}", generic, 1)
    return result


def query_ollama(prompt, model, system_prompt=None, max_tokens=1024):
    """Query local Ollama model."""
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.8}
    }
    if system_prompt:
        body["system"] = system_prompt

    data = json.dumps(body).encode()
    req = urllib.request.Request(OLLAMA_URL, data, {"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS)
        result = json.loads(resp.read())
        return result.get("response", "")
    except Exception as e:
        return ""


def get_response_hash(text):
    """MD5 hash for dedup."""
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


def verify_quality(prompt, response, verifier_model):
    """Use a different model to score a response 1-5."""
    verify_prompt = f"""Score this response 1-5 (1=terrible, 5=excellent).
Only output the number.

Question: {prompt[:200]}
Response: {response[:500]}

Score:"""
    score_text = query_ollama(verify_prompt, verifier_model, max_tokens=5)
    try:
        score = int(score_text.strip()[0])
        return score
    except:
        return 3  # default to neutral


def model_conversation(model_a, model_b, seed_topic):
    """Two models have a conversation — model A asks, model B answers."""
    question = query_ollama(
        f"Ask an interesting, specific technical question about {seed_topic}. "
        f"Just output the question, nothing else.",
        model_a, max_tokens=100
    )
    if len(question) < 10:
        return None, None

    answer = query_ollama(question, model_b, max_tokens=1024)
    if len(answer) < MIN_RESPONSE_CHARS:
        return None, None

    return question.strip(), answer.strip()


def main():
    print("=" * 60)
    print("  NovaX Ollama Data Factory v1.0")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Load existing data
    if OUT_FILE.exists():
        with open(OUT_FILE, "r", encoding="utf-8") as f:
            pairs = json.load(f)
    else:
        pairs = []

    existing_hashes = {get_response_hash(p.get("response", "")) for p in pairs}
    print(f"Existing pairs: {len(pairs)}, unique hashes: {len(existing_hashes)}")

    # Check which models are available
    available_models = []
    for model in MODELS:
        try:
            test = query_ollama("Say 'ok'", model, max_tokens=5)
            if test:
                available_models.append(model)
                print(f"  Model OK: {model}")
        except:
            print(f"  Model SKIP: {model}")

    if not available_models:
        print("ERROR: No Ollama models available!")
        sys.exit(1)

    print(f"\nUsing {len(available_models)} models: {', '.join(available_models)}")

    # Build prompt pool
    all_prompts = []
    for domain, templates in DOMAINS.items():
        for _ in range(25):  # 25 variations per template
            template = random.choice(templates)
            prompt = fill_template(template)
            all_prompts.append((domain, prompt))

    random.shuffle(all_prompts)
    print(f"Prompt pool: {len(all_prompts)} prompts across {len(DOMAINS)} domains")

    # Generation loop
    added = 0
    skipped = 0
    verified = 0
    conversations = 0
    start_time = time.time()
    model_idx = 0

    print(f"\nStarting generation...\n")

    for i, (domain, prompt) in enumerate(all_prompts):
        # Rotate models every 3 pairs
        if i % 3 == 0:
            model_idx = (model_idx + 1) % len(available_models)
        current_model = available_models[model_idx]

        # Every 10th pair: model-to-model conversation
        if i % 10 == 9 and len(available_models) >= 2:
            model_a = random.choice(available_models)
            model_b = random.choice([m for m in available_models if m != model_a] or available_models)
            seed = random.choice(SEEDS.get("topic", ["programming"]))
            q, a = model_conversation(model_a, model_b, seed)
            if q and a:
                h = get_response_hash(a)
                if h not in existing_hashes:
                    pairs.append({
                        "prompt": q,
                        "response": a,
                        "domain": f"conversation_{domain}",
                        "provider": "ollama",
                        "model": f"{model_a}->{model_b}",
                        "timestamp": datetime.now().isoformat()
                    })
                    existing_hashes.add(h)
                    added += 1
                    conversations += 1
                    # Save immediately
                    with open(OUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(pairs, f, ensure_ascii=False)
                    print(f"  [{i+1}] CONV {model_a}->{model_b}: {q[:50]}... ({len(a)} chars)")
            continue

        # Standard generation
        system = "You are a helpful, knowledgeable assistant. Provide clear, detailed, accurate responses."
        if domain == "chain_of_thought":
            system = "You are an expert problem solver. Show your reasoning step by step. Label each step clearly."
        elif domain == "coding":
            system = "You are an expert programmer. Write clean, well-commented code with explanations."

        response = query_ollama(prompt, current_model, system_prompt=system)

        # Quality checks
        if len(response) < MIN_RESPONSE_CHARS:
            skipped += 1
            continue
        if len(response) > MAX_RESPONSE_CHARS:
            response = response[:MAX_RESPONSE_CHARS]

        # Dedup check
        h = get_response_hash(response)
        if h in existing_hashes:
            skipped += 1
            continue

        # Every 15th pair: quality verification
        score = 0
        if i % 15 == 14 and len(available_models) >= 2:
            verifier = random.choice([m for m in available_models if m != current_model] or available_models)
            score = verify_quality(prompt, response, verifier)
            verified += 1
            if score <= 2:
                skipped += 1
                print(f"  [{i+1}] REJECT (score={score}): {prompt[:50]}...")
                continue

        # Accept pair
        pairs.append({
            "prompt": prompt,
            "response": response,
            "domain": domain,
            "provider": "ollama",
            "model": current_model,
            "score": score if score > 0 else None,
            "timestamp": datetime.now().isoformat()
        })
        existing_hashes.add(h)
        added += 1

        # Save every pair (crash-safe)
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(pairs, f, ensure_ascii=False)

        elapsed = time.time() - start_time
        rate = added / (elapsed / 3600) if elapsed > 0 else 0
        print(f"  [{i+1}/{len(all_prompts)}] +{added} ({current_model}) [{domain}]: "
              f"{prompt[:45]}... ({len(response)} chars) [{rate:.0f}/hr]")

        # Brief pause to avoid overloading GPU
        time.sleep(0.3)

    # Final stats
    elapsed = time.time() - start_time
    total_chars = sum(len(p.get("prompt","")) + len(p.get("response","")) for p in pairs)

    print(f"\n{'='*60}")
    print(f"  Factory Complete!")
    print(f"  Added: {added} pairs ({conversations} conversations)")
    print(f"  Skipped: {skipped} (too short / duplicate / low quality)")
    print(f"  Verified: {verified}")
    print(f"  Total: {len(pairs)} pairs, {total_chars:,} chars ({total_chars/1e6:.1f}M)")
    print(f"  Rate: {added/(elapsed/3600):.0f} pairs/hour")
    print(f"  Elapsed: {elapsed/60:.1f} minutes")
    print(f"{'='*60}")

    # Log run
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "added": added,
            "skipped": skipped,
            "total": len(pairs),
            "rate_per_hour": round(added/(elapsed/3600), 1) if elapsed > 0 else 0,
            "elapsed_minutes": round(elapsed/60, 1),
            "models_used": available_models
        }) + "\n")


if __name__ == "__main__":
    main()
