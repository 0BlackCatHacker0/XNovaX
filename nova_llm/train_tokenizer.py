"""
NovaX BPE Tokenizer Trainer v1.0
Trains the BPE tokenizer on available NovaX training data and saves to bpe_vocab.json.

Usage:
    python train_tokenizer.py [--vocab-size 32768] [--min-freq 2] [--output bpe_vocab.json]

Data sources (checked in order):
    1. C:/NovaX/data/llm_training/training_pairs_v2.json (1580 Q&A pairs)
    2. C:/NovaX/data/llm_training/training_pairs.json (855 pairs)
    3. C:/NovaX/data/super_archive/ (raw archive files)
    4. Fallback: built-in English corpus for basic BPE
"""

import json
import os
import sys
import time
from pathlib import Path

# Ensure nova_llm is importable
sys.path.insert(0, str(Path(__file__).parent))
from bpe_tokenizer import NovaXTokenizer, BYTE_OFFSET

# ============================================================
# DATA LOADING
# ============================================================
DATA_DIR = Path("C:/NovaX/data/llm_training")
ARCHIVE_DIR = Path("C:/NovaX/data/super_archive")
CLASSIFIED_DIR = Path("C:/NovaX/data/classified_reflections")
DEFAULT_OUTPUT = Path("C:/NovaX/nova_llm/bpe_vocab.json")


def load_training_texts() -> list:
    """Load training texts from available data sources."""
    texts = []

    # Source 1: training_pairs_v2.json
    v2_path = DATA_DIR / "training_pairs_v2.json"
    if v2_path.exists():
        try:
            with open(v2_path, "r", encoding="utf-8") as f:
                pairs = json.load(f)
            for pair in pairs:
                prompt = pair.get("prompt", "")
                response = pair.get("response", "")
                if prompt:
                    texts.append(prompt)
                if response:
                    texts.append(response)
            print(f"  [data] training_pairs_v2.json: {len(pairs)} pairs -> {len(texts)} texts")
        except Exception as e:
            print(f"  [data] training_pairs_v2.json: error - {e}")

    # Source 2: training_pairs.json
    v1_path = DATA_DIR / "training_pairs.json"
    if v1_path.exists():
        try:
            with open(v1_path, "r", encoding="utf-8") as f:
                pairs = json.load(f)
            count_before = len(texts)
            for pair in pairs:
                inp = pair.get("input", "")
                out = pair.get("output", "")
                if inp:
                    texts.append(inp)
                if out:
                    texts.append(out)
            print(f"  [data] training_pairs.json: {len(pairs)} pairs -> {len(texts) - count_before} texts")
        except Exception as e:
            print(f"  [data] training_pairs.json: error - {e}")

    # Source 3: super_archive
    if ARCHIVE_DIR.exists():
        count_before = len(texts)
        for fpath in sorted(ARCHIVE_DIR.glob("*.json"))[:100]:  # cap at 100 files
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            for key in ("content", "text", "response", "output"):
                                if key in item and isinstance(item[key], str) and len(item[key]) > 20:
                                    texts.append(item[key])
                elif isinstance(data, dict):
                    for key in ("content", "text", "response", "output"):
                        if key in data and isinstance(data[key], str) and len(data[key]) > 20:
                            texts.append(data[key])
            except Exception:
                continue
        print(f"  [data] super_archive: {len(texts) - count_before} texts")

    # Source 4: classified_reflections
    if CLASSIFIED_DIR.exists():
        count_before = len(texts)
        for fpath in sorted(CLASSIFIED_DIR.glob("*.json"))[:50]:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, str) and len(item) > 20:
                            texts.append(item)
                        elif isinstance(item, dict):
                            for key in ("content", "text", "response"):
                                if key in item and isinstance(item[key], str) and len(item[key]) > 20:
                                    texts.append(item[key])
            except Exception:
                continue
        print(f"  [data] classified_reflections: {len(texts) - count_before} texts")

    if not texts:
        print("  [data] No training data found, using fallback corpus")
        texts = _fallback_corpus()

    return texts


def _fallback_corpus() -> list:
    """Generate a reasonable fallback corpus for BPE training."""
    # Common English text patterns that will produce useful merges
    base_texts = [
        "The quick brown fox jumps over the lazy dog.",
        "Artificial intelligence and machine learning are transforming technology.",
        "Neural networks process information through layers of interconnected nodes.",
        "The transformer architecture uses self-attention mechanisms for sequence modeling.",
        "Python is a versatile programming language used for data science and web development.",
        "Quantum computing leverages superposition and entanglement for computation.",
        "The Navier-Stokes equations describe the motion of viscous fluid substances.",
        "Deep learning models require large datasets and significant computational resources.",
        "Natural language processing enables computers to understand human language.",
        "Reinforcement learning agents learn optimal policies through trial and error.",
    ]
    # Repeat and augment for statistical significance
    texts = base_texts * 100

    # Add common programming patterns
    code_samples = [
        "def function_name(self, parameter):\n    return self.value + parameter\n",
        "class ModelConfig:\n    def __init__(self, vocab_size=32768, hidden_dim=512):\n        self.vocab_size = vocab_size\n",
        "import torch\nimport json\nimport os\nfrom pathlib import Path\n",
        "for i in range(len(data)):\n    result = process(data[i])\n    results.append(result)\n",
        "if __name__ == '__main__':\n    main()\n",
    ]
    texts.extend(code_samples * 50)

    return texts


# ============================================================
# MAIN
# ============================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Train NovaX BPE Tokenizer")
    parser.add_argument("--vocab-size", type=int, default=DEFAULT_OUTPUT and 4096,
                        help="Target vocabulary size (default: 4096 for fast training, "
                             "use 32768 for production)")
    parser.add_argument("--min-freq", type=int, default=2,
                        help="Minimum pair frequency for merges (default: 2)")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help="Output path for trained tokenizer")
    parser.add_argument("--full", action="store_true",
                        help="Train with full vocab_size=32768 (slow but complete)")
    args = parser.parse_args()

    if args.full:
        args.vocab_size = 32768

    print("=" * 60)
    print("NovaX BPE Tokenizer Training")
    print("=" * 60)
    print(f"  Target vocab size: {args.vocab_size}")
    print(f"  Min frequency:     {args.min_freq}")
    print(f"  Output:            {args.output}")
    print()

    # Load data
    print("[1/4] Loading training data...")
    texts = load_training_texts()
    total_chars = sum(len(t) for t in texts)
    total_bytes = sum(len(t.encode("utf-8")) for t in texts)
    print(f"  Total: {len(texts)} texts, {total_chars:,} chars, {total_bytes:,} bytes")
    print()

    # Train
    print("[2/4] Training BPE tokenizer...")
    t0 = time.time()
    tokenizer = NovaXTokenizer()
    tokenizer.train(texts, vocab_size=args.vocab_size, min_frequency=args.min_freq)
    elapsed = time.time() - t0
    print(f"  Training time: {elapsed:.1f}s")
    print()

    # Save
    print("[3/4] Saving tokenizer...")
    tokenizer.save(args.output)
    print()

    # Statistics
    print("[4/4] Computing statistics...")
    # Use a sample of texts for stats
    sample = texts[:200] if len(texts) > 200 else texts
    stats = tokenizer.stats(sample)

    print()
    print("=" * 60)
    print("TOKENIZER STATISTICS")
    print("=" * 60)
    print(f"  Vocabulary size:        {stats['vocab_size']:,}")
    print(f"  BPE merges:             {stats['num_merges']:,}")
    print(f"  Sample texts:           {stats['total_texts']:,}")
    print(f"  Total bytes (sample):   {stats['total_bytes']:,}")
    print(f"  Total tokens (sample):  {stats['total_tokens']:,}")
    print(f"  Avg tokens/word:        {stats['avg_tokens_per_word']:.2f}")
    print(f"  Compression ratio:      {stats['compression_ratio']:.2f}x (bytes/token)")
    print(f"  Bytes per token:        {stats['bytes_per_token']:.2f}")
    print()

    # Compare with byte-level
    byte_level_tokens = stats["total_bytes"]  # byte-level = 1 token per byte
    bpe_tokens = stats["total_tokens"]
    improvement = (1 - bpe_tokens / max(byte_level_tokens, 1)) * 100
    print(f"  vs byte-level encoding:")
    print(f"    Byte-level tokens:    {byte_level_tokens:,}")
    print(f"    BPE tokens:           {bpe_tokens:,}")
    print(f"    Token reduction:      {improvement:.1f}%")
    print()

    # Show some example encodings
    print("EXAMPLE ENCODINGS:")
    print("-" * 60)
    examples = [
        "hello",
        "Hello, world!",
        "The quick brown fox",
        "artificial intelligence",
        "def __init__(self):",
        "NovaX LLM inference",
    ]
    for text in examples:
        ids = tokenizer.encode(text)
        byte_count = len(text.encode("utf-8"))
        ratio = byte_count / max(len(ids), 1)
        print(f"  {text!r:30s} -> {len(ids):3d} tokens (byte-level: {byte_count:3d}) "
              f"ratio: {ratio:.1f}x")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
