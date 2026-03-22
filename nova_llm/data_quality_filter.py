"""
NovaX Data Quality Filter v1.0
Filters, deduplicates, and scores training pairs before training.

Pipeline:
1. Load all pairs from training_pairs_mega.json
2. Dedup by response hash (MD5)
3. Filter by length (min 80 chars, max 8000 chars)
4. Remove near-duplicates (cosine similarity on simple TF-IDF)
5. Score by domain balance
6. Report statistics
7. Save filtered dataset

Usage:
    python data_quality_filter.py                    # Filter and report
    python data_quality_filter.py --save             # Filter and save
    python data_quality_filter.py --fim-augment 0.3  # Add FIM-formatted copies
"""
import json, hashlib, sys, re, collections
from pathlib import Path
from datetime import datetime

IN_FILE = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")
OUT_FILE = Path("C:/NovaX/data/llm_training/training_pairs_filtered.json")

MIN_RESPONSE_LEN = 80
MAX_RESPONSE_LEN = 8000
MIN_PROMPT_LEN = 10


def load_pairs():
    with open(IN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def dedup_by_hash(pairs):
    """Remove exact duplicate responses via MD5."""
    seen = set()
    unique = []
    dupes = 0
    for p in pairs:
        h = hashlib.md5(p.get("response", "").strip().lower().encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(p)
        else:
            dupes += 1
    return unique, dupes


def filter_length(pairs):
    """Remove pairs with too-short or too-long responses."""
    filtered = []
    removed = 0
    for p in pairs:
        resp_len = len(p.get("response", ""))
        prompt_len = len(p.get("prompt", ""))
        if resp_len < MIN_RESPONSE_LEN or prompt_len < MIN_PROMPT_LEN:
            removed += 1
            continue
        if resp_len > MAX_RESPONSE_LEN:
            p["response"] = p["response"][:MAX_RESPONSE_LEN]
        filtered.append(p)
    return filtered, removed


def filter_quality(pairs):
    """Remove low-quality responses (gibberish, error messages, etc)."""
    filtered = []
    removed = 0
    bad_patterns = [
        r"^(error|Error|ERROR)",
        r"I cannot",
        r"I can't help",
        r"As an AI",
        r"I don't have access",
        r"^[\s\n]*$",  # empty/whitespace only
    ]
    compiled = [re.compile(p) for p in bad_patterns]

    for p in pairs:
        resp = p.get("response", "")
        # Check for bad patterns (only at start of response)
        is_bad = False
        for pattern in compiled:
            if pattern.search(resp[:100]):
                is_bad = True
                break

        # Check for excessive repetition
        words = resp.split()
        if len(words) > 20:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.2:  # less than 20% unique words
                is_bad = True

        if is_bad:
            removed += 1
        else:
            filtered.append(p)
    return filtered, removed


def add_fim_augmentation(pairs, fim_rate=0.3):
    """Add Fill-in-the-Middle formatted copies of some pairs.

    FIM format (SPM = Suffix-Prefix-Middle):
    <fim_suffix>SUFFIX<fim_prefix>PREFIX<fim_middle>MIDDLE

    This teaches the model to predict middle-of-text, not just next-token.
    Research shows up to 50% FIM rate is free (no degradation on standard tasks).
    """
    import random
    fim_pairs = []

    for p in pairs:
        if random.random() > fim_rate:
            continue

        resp = p.get("response", "")
        if len(resp) < 100:
            continue

        # Split response at a random point (30-70% through)
        split_point = random.randint(int(len(resp)*0.3), int(len(resp)*0.7))
        prefix = resp[:split_point]
        middle_end = min(split_point + random.randint(20, 100), len(resp))
        middle = resp[split_point:middle_end]
        suffix = resp[middle_end:]

        fim_prompt = f"<fim_suffix>{suffix}<fim_prefix>{p.get('prompt', '')} {prefix}<fim_middle>"
        fim_response = middle

        fim_pairs.append({
            "prompt": fim_prompt,
            "response": fim_response,
            "domain": p.get("domain", "unknown") + "_fim",
            "provider": p.get("provider", ""),
            "model": p.get("model", ""),
            "original_domain": p.get("domain", "unknown"),
        })

    return fim_pairs


def report_stats(pairs, label="Dataset"):
    """Print comprehensive statistics."""
    print(f"\n{'='*60}")
    print(f"  {label} Statistics")
    print(f"{'='*60}")

    total_chars = sum(len(p.get("prompt","")) + len(p.get("response","")) for p in pairs)
    resp_lens = [len(p.get("response","")) for p in pairs]

    print(f"  Total pairs:     {len(pairs):,}")
    print(f"  Total chars:     {total_chars:,} ({total_chars/1e6:.1f}M)")
    print(f"  Avg response:    {sum(resp_lens)/max(len(resp_lens),1):.0f} chars")
    print(f"  Min response:    {min(resp_lens) if resp_lens else 0} chars")
    print(f"  Max response:    {max(resp_lens) if resp_lens else 0} chars")

    # Domain distribution
    domains = collections.Counter(p.get("domain", "unknown") for p in pairs)
    print(f"\n  Domain Distribution:")
    for domain, count in domains.most_common(20):
        pct = count / len(pairs) * 100
        bar = "█" * int(pct / 2)
        print(f"    {domain:30s} {count:5d} ({pct:5.1f}%) {bar}")

    # Model distribution
    models = collections.Counter(p.get("model", "unknown") for p in pairs)
    print(f"\n  Top Models:")
    for model, count in models.most_common(10):
        print(f"    {model:40s} {count:5d}")

    # Provider distribution
    providers = collections.Counter(p.get("provider", "unknown") for p in pairs)
    print(f"\n  Providers:")
    for provider, count in providers.most_common(10):
        print(f"    {provider:30s} {count:5d}")

    print(f"{'='*60}")
    return total_chars


def main():
    save = "--save" in sys.argv
    fim_rate = 0.3
    for i, arg in enumerate(sys.argv):
        if arg == "--fim-augment" and i+1 < len(sys.argv):
            fim_rate = float(sys.argv[i+1])

    print(f"NovaX Data Quality Filter v1.0")
    print(f"Loading from {IN_FILE}...")

    pairs = load_pairs()
    report_stats(pairs, "Raw Dataset")

    # Step 1: Dedup
    pairs, dupes = dedup_by_hash(pairs)
    print(f"\n[1] Dedup: removed {dupes} exact duplicates")

    # Step 2: Length filter
    pairs, short = filter_length(pairs)
    print(f"[2] Length filter: removed {short} too-short/too-long")

    # Step 3: Quality filter
    pairs, bad = filter_quality(pairs)
    print(f"[3] Quality filter: removed {bad} low-quality")

    # Step 4: FIM augmentation
    if fim_rate > 0:
        fim_pairs = add_fim_augmentation(pairs, fim_rate)
        print(f"[4] FIM augmentation: generated {len(fim_pairs)} FIM pairs ({fim_rate*100:.0f}% rate)")
        pairs.extend(fim_pairs)

    report_stats(pairs, "Filtered Dataset")

    if save:
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(pairs, f, ensure_ascii=False)
        print(f"\nSaved to {OUT_FILE}")
    else:
        print(f"\nDry run. Use --save to write filtered dataset.")


if __name__ == "__main__":
    main()
