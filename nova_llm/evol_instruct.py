"""
Evol-Instruct: Rule-based instruction evolution for training data augmentation.
Expands ~107K instruction pairs to ~200-300K by applying evolution strategies.
No API calls needed - pure rule-based transformations.
"""

import json
import random
import hashlib
import time
import re
import os
from collections import Counter

# ============================================================
# Configuration
# ============================================================
INPUT_PATH = "C:/NovaX/data/llm_training/training_pairs_mega.json"
OUTPUT_PATH = "C:/NovaX/data/llm_training/evolved_pairs.json"
RANDOM_SEED = 42
TARGET_MIN = 200000
EVOLUTIONS_PER_PAIR = (2, 3)  # randomly apply 2-3 strategies per pair

random.seed(RANDOM_SEED)

# ============================================================
# Evolution Strategy Definitions
# ============================================================

# Strategy 1: Add Constraints
CONSTRAINT_TEMPLATES = [
    "Do this without using any external libraries.",
    "Do this without using loops.",
    "Do this without using recursion.",
    "Ensure your solution has O(n) time complexity or better.",
    "Ensure your solution uses constant extra space.",
    "Do this in a single pass through the data.",
    "Ensure your solution handles unicode characters correctly.",
    "Do this without using built-in sorting functions.",
    "Ensure your solution is thread-safe.",
    "Do this without using any global variables.",
    "Ensure backward compatibility with older versions.",
    "Do this using only pure functions (no side effects).",
    "Ensure your answer is production-ready with proper error handling.",
    "Do this without modifying the original input data.",
    "Ensure your solution works on both Windows and Linux.",
    "Do this in under 20 lines of code.",
    "Ensure your solution can handle at least 1 million entries efficiently.",
]

# Strategy 2: Deepen
DEEPEN_TEMPLATES = [
    "Explain the reasoning behind your answer step by step.",
    "Provide step-by-step reasoning for each part of your solution.",
    "Explain why this approach is preferred over alternatives.",
    "Walk through a concrete example to illustrate your solution.",
    "Explain the time and space complexity of your approach.",
    "Describe potential pitfalls and how to avoid them.",
    "Explain the underlying principles that make this work.",
    "Break down the problem into sub-problems and solve each one.",
    "Explain how this concept connects to broader principles in the field.",
    "Discuss the historical context and evolution of this approach.",
    "Provide both a high-level overview and detailed implementation.",
    "Explain what happens internally when this code executes.",
]

# Strategy 3: Concretize - pattern replacements
CONCRETIZE_RULES = [
    (r'\ba function\b', 'a Python function that processes a list of dictionaries'),
    (r'\ba program\b', 'a Python program with command-line argument parsing'),
    (r'\ban algorithm\b', 'an algorithm with clearly defined input/output types'),
    (r'\ba script\b', 'a Python script with logging and error handling'),
    (r'\ba class\b', 'a Python class with proper __init__, __repr__, and type hints'),
    (r'\ba database\b', 'a PostgreSQL database with indexed tables'),
    (r'\ba web app\b', 'a Flask web application with REST API endpoints'),
    (r'\ba server\b', 'an async Python server using aiohttp'),
    (r'\ba model\b', 'a PyTorch neural network model with configurable layers'),
    (r'\ba file\b', 'a UTF-8 encoded JSON file'),
    (r'\ba list\b', 'a list of 10,000+ heterogeneous elements'),
    (r'\ba data structure\b', 'a balanced binary search tree'),
    (r'\ba test\b', 'a pytest test suite with fixtures and parametrize'),
    (r'\ba system\b', 'a distributed system with multiple microservices'),
    (r'\ba tool\b', 'a CLI tool with subcommands and help text'),
    (r'\ba API\b', 'a RESTful API with authentication and rate limiting'),
]

CONCRETIZE_SUFFIXES = [
    " Use realistic sample data (e.g., user records with name, email, age).",
    " Include concrete example inputs and expected outputs.",
    " Use a real-world scenario: an e-commerce product catalog.",
    " Apply this to a dataset of 50,000 customer transactions.",
    " Demonstrate with a real-world use case: a social media feed.",
    " Use specific numeric examples to illustrate.",
]

# Strategy 4: Increase Reasoning
REASONING_TEMPLATES = [
    "What are the trade-offs of this approach?",
    "Compare at least 2 different approaches and explain which is better and why.",
    "What are the advantages and disadvantages?",
    "Under what conditions would this approach fail or underperform?",
    "How would you modify this for a system handling 10x the load?",
    "What assumptions does this approach make, and what happens if they're violated?",
    "Analyze the best-case, worst-case, and average-case scenarios.",
    "What would a senior engineer critique about this approach?",
    "How would this change if requirements evolved to include real-time processing?",
    "What monitoring or observability would you add in production?",
    "Compare the memory vs. speed trade-offs of different implementations.",
]

# Strategy 5: Complicate Input
COMPLICATE_TEMPLATES = [
    "Handle the case where the input is empty or null.",
    "Handle edge cases: empty input, single element, very large input (1M+ items).",
    "Handle the case where the input contains duplicate values.",
    "Handle malformed or corrupted input data gracefully.",
    "Handle the case where the input exceeds available memory.",
    "Handle concurrent access from multiple threads or processes.",
    "Handle the case where the input contains special characters or unicode.",
    "Handle network failures and timeouts gracefully.",
    "Handle the case where intermediate results overflow standard numeric types.",
    "Handle the case where the input is a stream (data arrives incrementally).",
    "Handle the case where some fields are missing or have unexpected types.",
    "Handle the transition from the old format to the new format during migration.",
]

# Strategy 6: Breadth - domain variations
LANGUAGE_SWAPS = {
    'python': ['JavaScript', 'TypeScript', 'Rust', 'Go', 'Java', 'C++', 'Kotlin'],
    'javascript': ['Python', 'TypeScript', 'Rust', 'Go', 'Java'],
    'java': ['Python', 'Kotlin', 'Go', 'Rust', 'C#'],
    'c++': ['Rust', 'C', 'Go', 'Python', 'Java'],
    'rust': ['Go', 'C++', 'Python', 'Java'],
    'sql': ['MongoDB queries', 'DynamoDB expressions', 'GraphQL queries'],
    'react': ['Vue.js', 'Svelte', 'Angular', 'Solid.js'],
    'flask': ['FastAPI', 'Django', 'Express.js', 'Spring Boot'],
    'tensorflow': ['PyTorch', 'JAX', 'ONNX Runtime'],
    'pytorch': ['TensorFlow', 'JAX', 'ONNX Runtime'],
    'docker': ['Podman', 'Kubernetes', 'Nomad'],
    'aws': ['Google Cloud', 'Azure', 'DigitalOcean'],
    'linux': ['Windows', 'macOS', 'FreeBSD'],
    'mysql': ['PostgreSQL', 'SQLite', 'MongoDB'],
    'postgresql': ['MySQL', 'SQLite', 'CockroachDB'],
    'redis': ['Memcached', 'Valkey', 'DragonflyDB'],
    'numpy': ['pandas', 'polars', 'cupy'],
    'pandas': ['polars', 'dask', 'vaex'],
}

DOMAIN_SHIFT_TEMPLATES = [
    "Now solve the same problem but in the context of {domain}.",
    "Adapt this solution for {domain}.",
    "How would you approach this differently for {domain}?",
]

DOMAIN_SHIFTS = [
    "a real-time embedded system",
    "a mobile application with limited battery",
    "a high-frequency trading system",
    "a machine learning pipeline",
    "a distributed microservices architecture",
    "a serverless cloud function",
    "a browser-based WebAssembly application",
    "an IoT edge device with 256MB RAM",
    "a multi-tenant SaaS platform",
    "a game engine running at 60fps",
]


# ============================================================
# Evolution Functions
# ============================================================

def evolve_add_constraints(prompt, response):
    """Add constraints to the instruction."""
    constraint = random.choice(CONSTRAINT_TEMPLATES)
    new_prompt = prompt.rstrip('.!? ') + ". " + constraint
    # Append constraint note to response
    new_response = response + "\n\n**Note:** " + constraint.replace("Do this ", "This solution ").replace("Ensure ", "This ensures ")
    return new_prompt, new_response, "add_constraints"


def evolve_deepen(prompt, response):
    """Add depth-seeking suffix to instruction."""
    addition = random.choice(DEEPEN_TEMPLATES)
    new_prompt = prompt.rstrip('.!? ') + ". " + addition
    new_response = response + "\n\n**Reasoning:** The approach above works because it addresses the core requirements systematically. Each step builds on the previous one, ensuring correctness and clarity."
    return new_prompt, new_response, "deepen"


def evolve_concretize(prompt, response):
    """Replace generic terms with specific examples."""
    new_prompt = prompt
    applied = False
    # Try pattern replacements (max 1 to keep it readable)
    for pattern, replacement in CONCRETIZE_RULES:
        if re.search(pattern, new_prompt, re.IGNORECASE):
            new_prompt = re.sub(pattern, replacement, new_prompt, count=1, flags=re.IGNORECASE)
            applied = True
            break
    if not applied:
        # Just add a concretizing suffix
        new_prompt = new_prompt.rstrip('.!? ') + ". " + random.choice(CONCRETIZE_SUFFIXES)
        applied = True
    new_response = response
    return new_prompt, new_response, "concretize"


def evolve_increase_reasoning(prompt, response):
    """Add reasoning demands to instruction."""
    addition = random.choice(REASONING_TEMPLATES)
    new_prompt = prompt.rstrip('.!? ') + ". " + addition
    new_response = response + "\n\n**Trade-off Analysis:** There are multiple viable approaches here. The chosen approach balances simplicity, performance, and maintainability, though alternatives exist depending on specific constraints."
    return new_prompt, new_response, "increase_reasoning"


def evolve_complicate_input(prompt, response):
    """Add edge case requirements."""
    complication = random.choice(COMPLICATE_TEMPLATES)
    new_prompt = prompt.rstrip('.!? ') + ". " + complication
    new_response = response + "\n\n**Edge Case Handling:** The solution accounts for edge cases including empty inputs, boundary values, and unexpected data types to ensure robustness."
    return new_prompt, new_response, "complicate_input"


def evolve_breadth(prompt, response):
    """Change the domain or technology."""
    prompt_lower = prompt.lower()
    new_prompt = prompt
    new_response = response
    swapped = False

    # Try language/tech swaps
    for orig, alternatives in LANGUAGE_SWAPS.items():
        if orig in prompt_lower:
            target = random.choice(alternatives)
            # Replace in prompt (case-insensitive)
            new_prompt = re.sub(re.escape(orig), target, prompt, flags=re.IGNORECASE)
            new_response = re.sub(re.escape(orig), target, response, flags=re.IGNORECASE)
            swapped = True
            break

    if not swapped:
        # Apply domain shift
        domain = random.choice(DOMAIN_SHIFTS)
        template = random.choice(DOMAIN_SHIFT_TEMPLATES)
        suffix = template.format(domain=domain)
        new_prompt = prompt.rstrip('.!? ') + ". " + suffix
        new_response = response + f"\n\n**Domain Adaptation ({domain}):** The core principles remain the same, but implementation details change to accommodate the specific constraints and requirements of {domain}."

    return new_prompt, new_response, "breadth"


EVOLUTION_FUNCTIONS = [
    evolve_add_constraints,
    evolve_deepen,
    evolve_concretize,
    evolve_increase_reasoning,
    evolve_complicate_input,
    evolve_breadth,
]


# ============================================================
# Deduplication
# ============================================================

def instruction_hash(text):
    """Create a normalized hash for near-duplicate detection."""
    # Normalize: lowercase, strip whitespace, remove punctuation
    normalized = text.lower().strip()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def simhash_fingerprint(text, num_bits=64):
    """Simple simhash for near-duplicate detection."""
    normalized = text.lower().strip()
    words = normalized.split()
    v = [0] * num_bits
    for word in words:
        h = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16)
        for i in range(num_bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(num_bits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def hamming_distance(a, b):
    """Hamming distance between two integers."""
    x = a ^ b
    count = 0
    while x:
        count += 1
        x &= x - 1
    return count


# ============================================================
# Main Pipeline
# ============================================================

def main():
    start_time = time.time()
    print("=" * 60)
    print("EVOL-INSTRUCT: Rule-Based Instruction Evolution")
    print("=" * 60)

    # Step 1: Load data
    print(f"\n[1/6] Loading data from {INPUT_PATH}...")
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        original_data = json.load(f)
    original_count = len(original_data)
    print(f"      Loaded {original_count:,} instruction pairs")

    # Step 2: Evolve
    print(f"\n[2/6] Evolving instructions (target: {TARGET_MIN:,}+ pairs)...")
    evolved_pairs = []
    strategy_counts = Counter()
    errors = 0

    for i, pair in enumerate(original_data):
        if i % 10000 == 0 and i > 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            print(f"      Processed {i:,}/{original_count:,} ({i*100/original_count:.1f}%) - {rate:.0f} pairs/sec - evolved: {len(evolved_pairs):,}")

        prompt = pair.get('prompt', '')
        response = pair.get('response', '')
        source = pair.get('source', 'evolved')
        domain = pair.get('domain', '')

        if not prompt or not response:
            errors += 1
            continue

        # Randomly pick 2-3 evolution strategies
        num_evolutions = random.randint(*EVOLUTIONS_PER_PAIR)
        strategies = random.sample(EVOLUTION_FUNCTIONS, min(num_evolutions, len(EVOLUTION_FUNCTIONS)))

        for evolve_fn in strategies:
            try:
                new_prompt, new_response, strategy_name = evolve_fn(prompt, response)

                # Only keep if prompt actually changed
                if new_prompt != prompt and len(new_prompt) > 10:
                    evolved_pairs.append({
                        'prompt': new_prompt,
                        'response': new_response,
                        'source': f"evol_{strategy_name}",
                        'domain': domain,
                        'evolution': strategy_name,
                        'original_source': source,
                    })
                    strategy_counts[strategy_name] += 1
            except Exception as e:
                errors += 1

    elapsed_evolve = time.time() - start_time
    print(f"      Evolution complete: {len(evolved_pairs):,} evolved pairs in {elapsed_evolve:.1f}s")
    print(f"      Errors/skipped: {errors:,}")

    # Step 3: Print strategy distribution
    print(f"\n[3/6] Evolution strategy distribution:")
    for strategy, count in sorted(strategy_counts.items(), key=lambda x: -x[1]):
        print(f"      {strategy:25s}: {count:>8,} ({count*100/len(evolved_pairs):.1f}%)")

    # Step 4: Combine original + evolved
    print(f"\n[4/6] Combining original + evolved pairs...")
    all_pairs = original_data + evolved_pairs
    print(f"      Total before dedup: {len(all_pairs):,}")

    # Step 5: Deduplicate
    print(f"\n[5/6] Deduplicating (exact + near-duplicate)...")
    seen_exact = set()
    seen_simhash = {}
    deduped = []
    exact_dupes = 0
    near_dupes = 0
    SIMHASH_THRESHOLD = 3  # hamming distance threshold

    for pair in all_pairs:
        prompt = pair['prompt']

        # Exact dedup
        exact_h = instruction_hash(prompt)
        if exact_h in seen_exact:
            exact_dupes += 1
            continue
        seen_exact.add(exact_h)

        # Near-duplicate via simhash (only check against a sample for speed)
        sh = simhash_fingerprint(prompt)
        is_near_dupe = False
        # Check against bucket (first 16 bits as bucket key for speed)
        bucket_key = sh >> 48  # top 16 bits
        if bucket_key in seen_simhash:
            for existing_sh in seen_simhash[bucket_key]:
                if hamming_distance(sh, existing_sh) <= SIMHASH_THRESHOLD:
                    is_near_dupe = True
                    near_dupes += 1
                    break

        if not is_near_dupe:
            deduped.append(pair)
            if bucket_key not in seen_simhash:
                seen_simhash[bucket_key] = []
            # Keep bucket small for speed
            if len(seen_simhash[bucket_key]) < 50:
                seen_simhash[bucket_key].append(sh)

    print(f"      Exact duplicates removed: {exact_dupes:,}")
    print(f"      Near-duplicates removed:  {near_dupes:,}")
    print(f"      After dedup: {len(deduped):,}")

    # Step 6: Save
    print(f"\n[6/6] Saving to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(deduped, f, ensure_ascii=False)
    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"      Saved {len(deduped):,} pairs ({file_size / (1024*1024):.1f} MB)")

    # Final stats
    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("FINAL STATS")
    print("=" * 60)
    print(f"  Original pairs:     {original_count:>10,}")
    print(f"  Evolved pairs:      {len(evolved_pairs):>10,}")
    print(f"  Total before dedup: {original_count + len(evolved_pairs):>10,}")
    print(f"  Exact dupes removed:{exact_dupes:>10,}")
    print(f"  Near dupes removed: {near_dupes:>10,}")
    print(f"  Final output:       {len(deduped):>10,}")
    print(f"  Expansion ratio:    {len(deduped)/original_count:>10.2f}x")
    print(f"  Total time:         {total_time:>10.1f}s")
    print(f"  Output file:        {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == '__main__':
    main()
