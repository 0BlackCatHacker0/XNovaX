"""
augment_pairs.py - Pure-Python dataset augmentation for NovaX LLM training.
Reads training_pairs_mega.json (12,626 pairs) and produces pairs_augmented.json
with 15,000-25,000 augmented pairs. No AI models, CPU only.

Augmentation techniques:
  1. Reverse pairs (30%)
  2. Question decomposition (split on "and"/multi-sentence)
  3. Instruction variation (20%, 5 templates each)
  4. Response truncation -> summarization pairs (all >500 char responses)
  5. Fill-in-the-middle for code responses
  6. Contrastive pairs (wrong vs right)
  7. Domain tagging pairs
"""

import json
import random
import hashlib
import re
import os
import time

# ── paths ──────────────────────────────────────────────────────────────
SRC = "C:/NovaX/data/llm_training/training_pairs_mega.json"
DST = "C:/NovaX/data/llm_training/pairs_augmented.json"

random.seed(42)

# ── helpers ────────────────────────────────────────────────────────────
def md5(text):
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()

def make_pair(prompt, response, domain="augmented", source="augment"):
    return {
        "prompt": prompt.strip(),
        "response": response.strip(),
        "domain": domain,
        "provider": source,
        "model": "augmentation"
    }

def has_code(text):
    indicators = ["```", "def ", "function ", "class ", "import ", "const ", "var ",
                   "return ", "if (", "for (", "while (", "print(", "console.log"]
    return any(ind in text for ind in indicators)

def extract_code_blocks(text):
    """Extract fenced code blocks from text."""
    blocks = re.findall(r"```[\w]*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return blocks
    # fallback: look for indented code-like blocks (4+ lines starting with spaces)
    lines = text.split("\n")
    code_lines = []
    current = []
    for line in lines:
        if line.startswith("    ") or line.startswith("\t"):
            current.append(line)
        else:
            if len(current) >= 4:
                code_lines.append("\n".join(current))
            current = []
    if len(current) >= 4:
        code_lines.append("\n".join(current))
    return code_lines

# ── domain keyword map ─────────────────────────────────────────────────
DOMAIN_KEYWORDS = {
    "math": ["equation", "calcul", "algebra", "geometry", "integral", "derivative",
             "matrix", "probability", "statistic", "theorem", "proof", "formula",
             "number", "sum", "product", "factorial", "logarithm", "trigonometry"],
    "code": ["python", "javascript", "function", "algorithm", "api", "database",
             "sql", "html", "css", "react", "code", "program", "compile", "debug",
             "git", "docker", "kubernetes", "deploy", "server", "framework", "library"],
    "science": ["physics", "chemistry", "biology", "quantum", "molecule", "atom",
                "energy", "force", "gravity", "evolution", "cell", "dna", "gene",
                "experiment", "hypothesis", "theory", "element", "particle"],
    "reasoning": ["logic", "argument", "fallacy", "deduc", "induc", "paradox",
                  "philosophy", "ethic", "moral", "dilemma", "critical thinking",
                  "bias", "cognitive", "heuristic", "syllogism"],
    "language": ["grammar", "syntax", "semantic", "linguistic", "translation",
                 "vocabulary", "etymology", "phonetic", "morpholog", "prose",
                 "poetry", "narrative", "rhetoric", "metaphor", "literary"],
    "history": ["history", "civilization", "war", "empire", "revolution", "ancient",
                "medieval", "century", "dynasty", "colonial", "independence"],
    "creative": ["story", "poem", "creative", "fiction", "character", "plot",
                 "dialogue", "narrative", "imagine", "write a", "compose"],
    "general": []  # fallback
}

def detect_domain(text):
    text_lower = text.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if domain == "general":
            continue
        scores[domain] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get) if scores else "general"
    return best if scores.get(best, 0) > 0 else "general"


# ── augmentation functions ─────────────────────────────────────────────

def aug_reverse(pairs):
    """1. Reverse pairs - swap prompt/response roles (30% of pairs)."""
    count = 0
    results = []
    sample = random.sample(pairs, min(int(len(pairs) * 0.30), len(pairs)))
    for p in sample:
        prompt = p["prompt"]
        response = p["response"]
        # skip if response is too short or looks like JSON junk
        if len(response) < 30 or response.startswith("{"):
            continue
        new_prompt = "Given this explanation: " + response[:500] + ("..." if len(response) > 500 else "") + "\nWhat question is being answered?"
        new_response = prompt
        results.append(make_pair(new_prompt, new_response, p.get("domain", "augmented"), "aug_reverse"))
        count += 1
    return results, count


def aug_decompose(pairs):
    """2. Question decomposition - split complex questions into sub-questions."""
    count = 0
    results = []
    splitters = [" and ", " also ", " additionally ", ". ", "; "]
    templates = [
        "What is {}?",
        "Explain {}.",
        "How does {} work?",
        "Describe {}.",
    ]
    for p in pairs:
        prompt = p["prompt"]
        response = p["response"]
        if len(prompt) < 20:
            continue
        # Try splitting on conjunctions
        parts = None
        for sp in splitters:
            if sp in prompt.lower():
                idx = prompt.lower().index(sp)
                part1 = prompt[:idx].strip().rstrip(".,;?!")
                part2 = prompt[idx + len(sp):].strip().rstrip(".,;?!")
                if len(part1) > 10 and len(part2) > 10:
                    parts = [part1, part2]
                    break
        if not parts:
            continue
        # Generate sub-question pairs
        for part in parts:
            # Clean up: if it starts with a verb phrase, wrap in a question
            part_clean = part.strip()
            if part_clean and part_clean[0].islower():
                tmpl = random.choice(templates)
                sub_q = tmpl.format(part_clean)
            else:
                sub_q = part_clean
                if not sub_q.endswith("?"):
                    sub_q = "Explain: " + sub_q
            # Use a portion of the original response
            sub_resp = response[:max(200, len(response) // len(parts))]
            results.append(make_pair(sub_q, sub_resp, p.get("domain", "augmented"), "aug_decompose"))
            count += 1
    return results, count


def aug_instruction_variation(pairs):
    """3. Instruction variation - same response, different prompt phrasing (20%)."""
    count = 0
    results = []
    templates = [
        "Explain {}",
        "What is {}?",
        "Describe {} in detail.",
        "Tell me about {}.",
        "How does {} work?",
    ]
    sample = random.sample(pairs, min(int(len(pairs) * 0.20), len(pairs)))
    for p in sample:
        prompt = p["prompt"]
        response = p["response"]
        # Extract the topic from the prompt
        topic = prompt
        # Strip common prefixes
        for prefix in ["explain ", "what is ", "what are ", "describe ",
                       "tell me about ", "how does ", "how do ",
                       "can you explain ", "please explain ", "define "]:
            if topic.lower().startswith(prefix):
                topic = topic[len(prefix):]
                break
        topic = topic.rstrip("?.!,;")
        if len(topic) < 5:
            continue
        for tmpl in templates:
            new_prompt = tmpl.format(topic)
            # Skip if basically the same as original
            if new_prompt.lower().strip("?.! ") == prompt.lower().strip("?.! "):
                continue
            results.append(make_pair(new_prompt, response, p.get("domain", "augmented"), "aug_variation"))
            count += 1
    return results, count


def aug_summarization(pairs):
    """4. Response truncation for summarization pairs (responses >500 chars)."""
    count = 0
    results = []
    for p in pairs:
        response = p["response"]
        if len(response) <= 500:
            continue
        if response.startswith("{"):
            continue
        # Create summarization pair
        summary = response[:200].rsplit(" ", 1)[0] + "..."
        new_prompt = "Summarize the following text in a brief paragraph:\n\n" + response[:2000]
        results.append(make_pair(new_prompt, summary, p.get("domain", "augmented"), "aug_summarize"))
        count += 1
    return results, count


def aug_fim(pairs):
    """5. Fill-in-the-middle for code responses."""
    count = 0
    results = []
    for p in pairs:
        response = p["response"]
        if not has_code(response):
            continue
        code_blocks = extract_code_blocks(response)
        if not code_blocks:
            # Use the whole response as code if it looks code-like
            if len(response) > 100 and has_code(response):
                code_blocks = [response]
            else:
                continue
        for block in code_blocks[:1]:  # only first block per pair
            lines = block.strip().split("\n")
            if len(lines) < 6:
                continue
            # Split into prefix / middle / suffix
            third = len(lines) // 3
            prefix_lines = lines[:third]
            middle_lines = lines[third:2*third]
            suffix_lines = lines[2*third:]
            prefix = "\n".join(prefix_lines)
            middle = "\n".join(middle_lines)
            suffix = "\n".join(suffix_lines)
            if len(middle.strip()) < 10:
                continue
            new_prompt = "Complete the missing middle section of this code:\n\n" + prefix + "\n# ... MISSING CODE ...\n" + suffix
            results.append(make_pair(new_prompt, middle, "code", "aug_fim"))
            count += 1
    return results, count


def aug_contrastive(pairs):
    """6. Contrastive pairs - correct vs wrong response."""
    count = 0
    results = []
    # Collect all responses for shuffling
    all_responses = [p["response"] for p in pairs if len(p["response"]) > 50 and not p["response"].startswith("{")]
    if len(all_responses) < 100:
        return results, count

    sample = random.sample(pairs, min(int(len(pairs) * 0.15), len(pairs)))
    for p in sample:
        correct = p["response"]
        if len(correct) < 50 or correct.startswith("{"):
            continue
        # Generate wrong response: pick random sentences from other responses
        wrong_source = random.choice(all_responses)
        attempts = 0
        while wrong_source == correct and attempts < 5:
            wrong_source = random.choice(all_responses)
            attempts += 1
        if wrong_source == correct:
            continue
        # Take first ~200 chars of wrong source, truncate mid-sentence for extra wrongness
        wrong = wrong_source[:250]
        if ". " in wrong[50:]:
            wrong = wrong[:wrong.rindex(". ", 0, 250)]

        # Randomly decide order
        if random.random() < 0.5:
            option_a = wrong
            option_b = correct[:500]
            answer = "B"
        else:
            option_a = correct[:500]
            option_b = wrong
            answer = "A"

        new_prompt = ("Which response better answers this question?\n\n"
                      "Question: " + p["prompt"] + "\n\n"
                      "Response A: " + option_a + "\n\n"
                      "Response B: " + option_b)
        new_response = (answer + " is the better response. It directly and accurately addresses "
                        "the question about " + p["prompt"][:80] + ", while the other response "
                        "contains unrelated or inaccurate information.")
        results.append(make_pair(new_prompt, new_response, p.get("domain", "augmented"), "aug_contrastive"))
        count += 1
    return results, count


def aug_domain_tagging(pairs):
    """7. Domain tagging pairs."""
    count = 0
    results = []
    for p in pairs:
        prompt = p["prompt"]
        if len(prompt) < 10:
            continue
        domain = detect_domain(prompt)
        new_prompt = "What domain or subject area does this question belong to?\n\n\"" + prompt + "\""
        new_response = ("This question belongs to the '" + domain + "' domain. "
                        "It primarily deals with topics related to " + domain +
                        " concepts and knowledge.")
        results.append(make_pair(new_prompt, new_response, "meta", "aug_domain"))
        count += 1
    return results, count


# ── main pipeline ──────────────────────────────────────────────────────

def main():
    t0 = time.time()
    print("[augment_pairs] Loading source data from:", SRC)
    with open(SRC, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    print("[augment_pairs] Loaded", len(pairs), "original pairs")

    all_augmented = []
    counts = {}

    # Run each augmentation
    augmentations = [
        ("1_reverse", aug_reverse),
        ("2_decompose", aug_decompose),
        ("3_variation", aug_instruction_variation),
        ("4_summarize", aug_summarization),
        ("5_fim", aug_fim),
        ("6_contrastive", aug_contrastive),
        ("7_domain_tag", aug_domain_tagging),
    ]

    for name, func in augmentations:
        print(f"  Running {name}...", end=" ")
        results, ct = func(pairs)
        all_augmented.extend(results)
        counts[name] = ct
        print(f"{ct} pairs generated")

    print(f"\n[augment_pairs] Total before dedup: {len(all_augmented)}")

    # Dedup by MD5 of prompt+response
    seen = set()
    deduped = []
    dup_count = 0
    for item in all_augmented:
        key = md5(item["prompt"] + "||" + item["response"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
        else:
            dup_count += 1

    print(f"[augment_pairs] Duplicates removed: {dup_count}")
    print(f"[augment_pairs] Final augmented pairs: {len(deduped)}")

    # If over target, trim randomly; if under, that's fine
    if len(deduped) > 25000:
        random.shuffle(deduped)
        deduped = deduped[:25000]
        print(f"[augment_pairs] Trimmed to 25,000 pairs")

    # Write output
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - t0
    print(f"\n[augment_pairs] Written to: {DST}")
    print(f"[augment_pairs] Time: {elapsed:.1f}s")
    print(f"\n{'='*50}")
    print(f"  AUGMENTATION REPORT")
    print(f"{'='*50}")
    print(f"  Original pairs:      {len(pairs):>8}")
    for name, ct in counts.items():
        print(f"  {name:20s}: {ct:>8}")
    print(f"  {'':20s}  --------")
    print(f"  Total generated:     {sum(counts.values()):>8}")
    print(f"  After dedup:         {len(deduped):>8}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
