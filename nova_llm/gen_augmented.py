"""
AUGMENTATION GENERATOR - Transform existing pairs into more pairs.
Techniques: reverse Q/A, decompose, rephrase templates, chain, negate.
Target: 6,000+ new pairs from existing 12,615.
Writes to: C:/NovaX/data/llm_training/pairs_augmented.json
"""
import json
import random
import re
import hashlib

random.seed(123)
OUTPUT = "C:/NovaX/data/llm_training/pairs_augmented.json"

# Load existing pairs
print("Loading existing pairs...")
existing = json.load(open('C:/NovaX/data/llm_training/training_pairs_mega.json', encoding='utf-8'))
print(f"Loaded {len(existing)} existing pairs")

pairs = []

def add(prompt, response, domain, technique):
    if len(prompt.strip()) < 10 or len(response.strip()) < 20:
        return
    pairs.append({
        "prompt": prompt.strip(),
        "response": response.strip(),
        "domain": f"aug_{domain}",
        "provider": f"augmentation_{technique}",
        "model": "augment_v1"
    })

# ============================================================
# 1. REVERSE Q&A - Turn response into question (2000+)
# ============================================================
print("[1/5] Reverse Q&A augmentation...")

for p in existing[:3000]:
    prompt = p.get('prompt', '')
    response = p.get('response', '')
    domain = p.get('domain', 'general')

    if len(response) < 50 or len(response) > 2000:
        continue

    # Extract key sentence from response
    sentences = re.split(r'[.!?\n]', response)
    key_sentences = [s.strip() for s in sentences if 20 < len(s.strip()) < 200]

    if not key_sentences:
        continue

    key = random.choice(key_sentences[:3])

    # Create "given this info, what was the question?" style
    add(f"Given this information: \"{key}\"\nWhat question would this answer?",
        f"This would answer: \"{prompt}\"",
        domain, "reverse")

    # Create summary/explain style
    if len(response) > 200:
        add(f"Summarize the following in one sentence: {response[:500]}",
            key_sentences[0] + ".",
            domain, "summarize")

print(f"  Reverse pairs: {len(pairs)}")
reverse_count = len(pairs)

# ============================================================
# 2. REPHRASE WITH TEMPLATES (2000+)
# ============================================================
print("[2/5] Rephrase augmentation...")

rephrase_prefixes = [
    "Can you explain ",
    "I'd like to understand ",
    "Please describe ",
    "Tell me about ",
    "What can you tell me about ",
    "Help me understand ",
    "Could you elaborate on ",
    "Give me an overview of ",
    "Break down for me ",
    "In simple terms, ",
]

rephrase_suffixes = [
    "",
    " in detail",
    " briefly",
    " with examples",
    " step by step",
    " for a beginner",
    " in technical terms",
]

for p in existing[:2500]:
    prompt = p.get('prompt', '')
    response = p.get('response', '')
    domain = p.get('domain', 'general')

    if len(prompt) < 15 or len(response) < 50:
        continue

    # Extract the core topic from the prompt
    topic = prompt
    for prefix in ["What is ", "What are ", "How do ", "How does ", "Explain ", "Describe ",
                    "What does ", "Why ", "When ", "Where ", "Who "]:
        if topic.lower().startswith(prefix.lower()):
            topic = topic[len(prefix):]
            break

    topic = topic.rstrip('?').rstrip('.')

    if len(topic) < 5:
        continue

    # Generate rephrased versions
    prefix = random.choice(rephrase_prefixes)
    suffix = random.choice(rephrase_suffixes)
    new_prompt = f"{prefix}{topic}{suffix}?"

    # Slightly modify response too
    response_prefix = random.choice([
        "",
        "Sure! ",
        "Of course. ",
        "Great question. ",
        "Here's an explanation: ",
    ])

    add(new_prompt,
        response_prefix + response[:1500],
        domain, "rephrase")

rephrase_count = len(pairs) - reverse_count
print(f"  Rephrase pairs: {rephrase_count}")

# ============================================================
# 3. DECOMPOSITION - Break complex responses into sub-QA (1000+)
# ============================================================
print("[3/5] Decomposition augmentation...")

for p in existing[:2000]:
    response = p.get('response', '')
    domain = p.get('domain', 'general')
    prompt = p.get('prompt', '')

    if len(response) < 300:
        continue

    # Split by paragraphs or numbered sections
    paragraphs = [para.strip() for para in re.split(r'\n\n|\n(?=\d+\.)|(?=#{1,3}\s)', response)
                  if len(para.strip()) > 50]

    if len(paragraphs) < 2:
        continue

    # Extract topic from prompt
    topic = prompt.rstrip('?').rstrip('.')

    for i, para in enumerate(paragraphs[:4]):
        # Clean up markdown
        clean_para = re.sub(r'[#*`]', '', para).strip()
        if len(clean_para) < 50:
            continue

        sub_q = f"Regarding {topic}: explain part {i+1}."
        add(sub_q, clean_para, domain, "decompose")

decompose_count = len(pairs) - reverse_count - rephrase_count
print(f"  Decompose pairs: {decompose_count}")

# ============================================================
# 4. NEGATION/CONTRAST (500+)
# ============================================================
print("[4/5] Negation/contrast augmentation...")

contrast_templates = [
    ("What is the difference between {a} and {b}?",
     "{a} and {b} are different concepts. {a}: {desc_a}. In contrast, {b}: {desc_b}."),
    ("Compare {a} and {b}.",
     "Comparing {a} and {b}: {a} {desc_a}. On the other hand, {b} {desc_b}."),
    ("When should I use {a} vs {b}?",
     "Use {a} when {desc_a}. Use {b} when {desc_b}. The choice depends on your specific requirements."),
]

# Create comparison pairs from related concepts
comparison_topics = [
    ("Python", "JavaScript", "is a dynamically typed, interpreted language focused on readability and versatility", "is a dynamically typed language primarily for web browsers but also used server-side with Node.js"),
    ("TCP", "UDP", "provides reliable, ordered delivery with connection handshake", "provides fast, connectionless delivery without guarantees"),
    ("SQL", "NoSQL", "databases use structured tables with fixed schemas and ACID transactions", "databases use flexible schemas (document, key-value, graph) optimized for specific access patterns"),
    ("REST", "GraphQL", "uses multiple endpoints with fixed response structures", "uses a single endpoint where clients specify exactly what data they need"),
    ("stack", "queue", "is a LIFO (Last In, First Out) data structure", "is a FIFO (First In, First Out) data structure"),
    ("array", "linked list", "provides O(1) random access but O(n) insertion", "provides O(1) insertion at head but O(n) access"),
    ("merge sort", "quick sort", "guarantees O(n log n) but uses O(n) extra space", "is O(n log n) average and in-place but O(n^2) worst case"),
    ("BFS", "DFS", "explores level by level using a queue, finds shortest path in unweighted graphs", "explores as deep as possible using a stack/recursion, good for topological sort"),
    ("process", "thread", "has its own memory space and is heavier to create", "shares memory with other threads in the same process and is lighter"),
    ("compiled language", "interpreted language", "is translated to machine code before execution (faster runtime)", "is executed line by line at runtime (more flexible, slower)"),
    ("Docker", "virtual machine", "shares the host OS kernel and is lightweight", "runs a full OS instance and provides stronger isolation"),
    ("git merge", "git rebase", "creates a merge commit preserving branch history", "replays commits on top of the target branch for a linear history"),
    ("supervised learning", "unsupervised learning", "uses labeled data to learn input-output mappings", "finds patterns in unlabeled data without explicit targets"),
    ("CNN", "RNN", "processes spatial data using convolutional filters (great for images)", "processes sequential data using hidden states (great for text/time series)"),
    ("overfitting", "underfitting", "occurs when a model memorizes training data and fails to generalize", "occurs when a model is too simple to capture data patterns"),
    ("encryption", "hashing", "is reversible with the correct key and preserves data", "is one-way and produces a fixed-size output regardless of input size"),
    ("mutex", "semaphore", "allows only one thread to access a resource at a time", "allows a configurable number of threads to access a resource"),
    ("GET", "POST", "retrieves data without side effects and parameters go in the URL", "submits data for processing and parameters go in the request body"),
    ("monolithic", "microservices", "architecture deploys the entire application as one unit", "architecture splits the application into independent, deployable services"),
    ("ACID", "BASE", "provides strict consistency guarantees in databases", "provides eventual consistency for higher availability and partition tolerance"),
]

for a, b, desc_a, desc_b in comparison_topics:
    for template_q, template_a in contrast_templates:
        add(template_q.format(a=a, b=b),
            template_a.format(a=a, b=b, desc_a=desc_a, desc_b=desc_b),
            "comparison", "contrast")

contrast_count = len(pairs) - reverse_count - rephrase_count - decompose_count
print(f"  Contrast pairs: {contrast_count}")

# ============================================================
# 5. CHAIN-OF-THOUGHT WRAPPING (500+)
# ============================================================
print("[5/5] Chain-of-thought augmentation...")

for p in existing[:1000]:
    prompt = p.get('prompt', '')
    response = p.get('response', '')
    domain = p.get('domain', 'general')

    if len(response) < 100 or len(response) > 1500:
        continue

    # Add "think step by step" wrapper
    add(f"Think step by step: {prompt}",
        f"Let me think through this step by step.\n\n{response}",
        domain, "cot")

    # Add "explain like I'm 5" wrapper
    if len(response) > 200:
        # Simplify: take first 2 sentences
        sentences = re.split(r'[.!?]', response)
        simple = '. '.join(s.strip() for s in sentences[:2] if s.strip()) + '.'
        add(f"Explain simply: {prompt}",
            f"In simple terms: {simple}",
            domain, "simplify")

cot_count = len(pairs) - reverse_count - rephrase_count - decompose_count - contrast_count
print(f"  CoT/simplify pairs: {cot_count}")

# ============================================================
# SAVE
# ============================================================
print(f"\n=== TOTAL AUGMENTED PAIRS: {len(pairs)} ===")

# Dedup
seen = set()
deduped = []
for p in pairs:
    key = p["prompt"].strip().lower()[:200]
    if key not in seen:
        seen.add(key)
        deduped.append(p)

print(f"After dedup: {len(deduped)}")

with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(deduped, f, ensure_ascii=False, indent=1)

print(f"Saved to {OUTPUT}")
