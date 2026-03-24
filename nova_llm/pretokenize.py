"""
Pre-tokenize the training dataset to disk.
Saves tokenized tensors so training startup skips the 20-min tokenization step.

Usage:
    python pretokenize.py                          # Tokenize current dataset
    python pretokenize.py --input PATH --output DIR # Custom paths
"""

import argparse
import json
import os
import struct
import time
from pathlib import Path

import numpy as np

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_PATH = Path("C:/NovaX/data/llm_training/training_pairs_round7.json")
VOCAB_PATH = SCRIPT_DIR / "bpe_vocab_32k.json"
OUTPUT_DIR = Path("C:/NovaX/data/llm_training/tokenized")

# Import tokenizer
from bpe_tokenizer import NovaXTokenizer

# Special tokens
BOS, EOS, SEP, PAD = 1, 2, 5, 0


def tokenize_pair(tokenizer, pair, max_len=256):
    """Tokenize a single prompt/response pair."""
    prompt = pair.get("prompt", "") or pair.get("input", "")
    response = pair.get("response", "") or pair.get("output", "") or pair.get("completion", "")

    prompt_ids = tokenizer.encode(prompt)
    response_ids = tokenizer.encode(response)

    # Format: BOS + prompt + SEP + response + EOS
    full_ids = [BOS] + prompt_ids + [SEP] + response_ids + [EOS]

    # Truncate
    if len(full_ids) > max_len:
        full_ids = full_ids[:max_len]

    return full_ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=str(DATA_PATH))
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR))
    parser.add_argument("--max-len", type=int, default=256)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading data from {input_path}...")
    t0 = time.time()
    with open(input_path, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    print(f"  Loaded {len(pairs):,} pairs in {time.time()-t0:.1f}s")

    print(f"Loading tokenizer from {VOCAB_PATH}...")
    tokenizer = NovaXTokenizer(str(VOCAB_PATH))
    print(f"  Vocab size: {tokenizer.vocab_size}")

    print(f"Tokenizing {len(pairs):,} pairs (max_len={args.max_len})...")
    t0 = time.time()

    all_ids = []
    all_lengths = []
    total_tokens = 0

    for i, pair in enumerate(pairs):
        ids = tokenize_pair(tokenizer, pair, args.max_len)
        all_ids.append(ids)
        all_lengths.append(len(ids))
        total_tokens += len(ids)

        if (i + 1) % 100_000 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(pairs) - i - 1) / rate
            print(f"  [{i+1:,}/{len(pairs):,}] {rate:.0f} pairs/sec, ETA {eta:.0f}s")

    elapsed = time.time() - t0
    print(f"  Tokenized {len(pairs):,} pairs in {elapsed:.1f}s ({len(pairs)/elapsed:.0f} pairs/sec)")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Avg length: {total_tokens/len(pairs):.1f} tokens/pair")

    # Save as numpy arrays for fast loading
    # 1. Flat token array (all sequences concatenated)
    flat_ids = []
    for ids in all_ids:
        flat_ids.extend(ids)
    flat_array = np.array(flat_ids, dtype=np.uint16)

    # 2. Offsets array (cumulative lengths for indexing)
    offsets = np.zeros(len(all_lengths) + 1, dtype=np.int64)
    for i, length in enumerate(all_lengths):
        offsets[i + 1] = offsets[i] + length

    # Save
    tokens_path = output_dir / "tokens.npy"
    offsets_path = output_dir / "offsets.npy"
    meta_path = output_dir / "meta.json"

    np.save(str(tokens_path), flat_array)
    np.save(str(offsets_path), offsets)

    meta = {
        "num_pairs": len(pairs),
        "total_tokens": total_tokens,
        "avg_length": round(total_tokens / len(pairs), 1),
        "max_len": args.max_len,
        "vocab_size": tokenizer.vocab_size,
        "source": str(input_path),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    tokens_mb = tokens_path.stat().st_size / 1e6
    offsets_mb = offsets_path.stat().st_size / 1e6

    print(f"\nSaved to {output_dir}/")
    print(f"  tokens.npy:  {tokens_mb:.1f} MB ({total_tokens:,} uint16)")
    print(f"  offsets.npy: {offsets_mb:.1f} MB ({len(pairs)+1:,} int64)")
    print(f"  meta.json:   metadata")
    print(f"  Total: {tokens_mb + offsets_mb:.1f} MB (vs {input_path.stat().st_size/1e6:.1f} MB JSON)")
    print(f"\nNext round can load pre-tokenized data in <1 second instead of 20 minutes.")


if __name__ == "__main__":
    main()
