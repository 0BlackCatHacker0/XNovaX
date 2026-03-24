"""
Merge all data sources for Round 7 training.
Combines: original pairs + evolved pairs + FineWeb-Edu + OpenWebMath
Output: C:/NovaX/data/llm_training/training_pairs_round7.json
"""

import json
import hashlib
import random
import time
from pathlib import Path

# Paths
ORIGINAL = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")
EVOLVED = Path("C:/NovaX/data/llm_training/evolved_pairs.json")
FINEWEB = Path("C:/NovaX/data/pretraining/fineweb_edu_sample.jsonl")
OPENWEBMATH = Path("C:/NovaX/data/pretraining/openwebmath_sample.jsonl")
COSMOPEDIA = Path("C:/NovaX/data/pretraining/cosmopedia_sample.jsonl")
OUTPUT = Path("C:/NovaX/data/llm_training/training_pairs_round7.json")

# Config - limit pretraining data to keep training time reasonable on RTX 4060
MAX_FINEWEB = 200_000      # 200K educational web examples
MAX_OPENWEBMATH = 50_000   # 50K math examples
MAX_COSMOPEDIA = 150_000   # 150K synthetic textbook examples (Phi-style, highest quality)
MAX_TEXT_LEN = 2000        # Cap text length for seq_len=256 tokenizer

def load_jsonl(path, max_n, text_field="text"):
    """Load JSONL file, extract text, convert to prompt/response format."""
    pairs = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= max_n:
                break
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            text = obj.get(text_field, "")
            if not text or len(text) < 50:
                continue

            # Convert raw text to instruction format
            # Split text into a "context" prompt and "continuation" response
            text = text[:MAX_TEXT_LEN]
            split_point = len(text) // 3  # First third as prompt

            # Find a sentence boundary near the split point
            for offset in range(min(200, split_point)):
                pos = split_point + offset
                if pos < len(text) and text[pos] in '.!?\n':
                    split_point = pos + 1
                    break

            prompt = text[:split_point].strip()
            response = text[split_point:].strip()

            if len(prompt) < 20 or len(response) < 20:
                continue

            pairs.append({
                "prompt": prompt,
                "response": response,
                "source": path.stem,
                "domain": "web_edu" if "fineweb" in path.stem else "math",
            })

    return pairs


def main():
    t0 = time.time()
    all_pairs = []
    seen = set()

    def dedup_add(pairs, source_name):
        added = 0
        for p in pairs:
            h = hashlib.md5((p["prompt"][:100] + p["response"][:100]).encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                all_pairs.append(p)
                added += 1
        print(f"  {source_name}: {added} added ({len(pairs)} total, {len(pairs)-added} dupes)")
        return added

    # 1. Original instruction pairs (highest quality, keep all)
    print("Loading original pairs...")
    with open(ORIGINAL, "r", encoding="utf-8") as f:
        original = json.load(f)
    dedup_add(original, "Original 107K")

    # 2. Evolved instruction pairs
    print("Loading evolved pairs...")
    with open(EVOLVED, "r", encoding="utf-8") as f:
        evolved = json.load(f)
    dedup_add(evolved, "Evol-Instruct")

    # 3. FineWeb-Edu (educational web text)
    if FINEWEB.exists():
        print(f"Loading FineWeb-Edu (max {MAX_FINEWEB})...")
        fineweb = load_jsonl(FINEWEB, MAX_FINEWEB)
        dedup_add(fineweb, "FineWeb-Edu")
    else:
        print("  FineWeb-Edu not found, skipping")

    # 4. OpenWebMath
    if OPENWEBMATH.exists():
        print(f"Loading OpenWebMath (max {MAX_OPENWEBMATH})...")
        owm = load_jsonl(OPENWEBMATH, MAX_OPENWEBMATH)
        dedup_add(owm, "OpenWebMath")
    else:
        print("  OpenWebMath not found, skipping")

    # 5. Cosmopedia (synthetic textbooks - Phi-style, highest quality)
    if COSMOPEDIA.exists() and COSMOPEDIA.stat().st_size > 0:
        print(f"Loading Cosmopedia (max {MAX_COSMOPEDIA})...")
        cosmo = load_jsonl(COSMOPEDIA, MAX_COSMOPEDIA)
        dedup_add(cosmo, "Cosmopedia")
    else:
        print("  Cosmopedia not found, skipping")

    # Shuffle
    random.seed(42)
    random.shuffle(all_pairs)

    # Save
    print(f"\nSaving {len(all_pairs)} pairs to {OUTPUT}...")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_pairs, f, ensure_ascii=False)

    size_mb = OUTPUT.stat().st_size / 1e6
    elapsed = time.time() - t0

    print(f"\n{'='*50}")
    print(f"  Round 7 Dataset Ready")
    print(f"  Total pairs: {len(all_pairs):,}")
    print(f"  File size: {size_mb:.1f} MB")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
