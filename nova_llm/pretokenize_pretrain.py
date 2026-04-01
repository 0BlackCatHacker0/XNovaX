"""Pre-tokenize pretraining data to numpy arrays for instant loading.

Reads all JSONL files from the pretraining directory, tokenizes with BPE,
and saves as memory-mapped numpy arrays. Next training run loads in <5 seconds
instead of 15-20 minutes.

Usage:
    python pretokenize_pretrain.py
    python pretokenize_pretrain.py --data-dir C:/NovaX/data/pretraining --out-dir C:/NovaX/data/pretraining/tokenized
"""

import json
import numpy as np
from pathlib import Path
import time
import sys

DATA_DIR = Path("C:/NovaX/data/pretraining")
OUT_DIR = DATA_DIR / "tokenized"
BPE_PATH = Path(__file__).parent / "bpe_vocab_32k.json"

BOS = 1
EOS = 2


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, default=str(DATA_DIR))
    parser.add_argument("--out-dir", type=str, default=str(OUT_DIR))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load tokenizer
    from bpe_tokenizer import NovaXTokenizer
    tokenizer = NovaXTokenizer(str(BPE_PATH))
    print(f"Tokenizer: {tokenizer.vocab_size} tokens")

    # Find all JSONL files
    jsonl_files = sorted(data_dir.glob("*.jsonl"))
    print(f"Found {len(jsonl_files)} JSONL files in {data_dir}")

    # First pass: tokenize everything into a flat list
    all_tokens = []
    total_docs = 0
    start = time.time()

    for fpath in jsonl_files:
        file_start = time.time()
        count = 0
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    text = obj.get("text", "")
                    if len(text) < 50:
                        continue
                    tokens = tokenizer.encode(text)
                    all_tokens.append(BOS)
                    all_tokens.extend(tokens)
                    all_tokens.append(EOS)
                    count += 1
                    if count % 50000 == 0:
                        elapsed = time.time() - file_start
                        tps = count / elapsed if elapsed > 0 else 0
                        print(f"    {fpath.name}: {count:,} docs ({tps:.0f} docs/s)...")
                except Exception:
                    continue
        total_docs += count
        elapsed = time.time() - file_start
        print(f"  {fpath.name}: {count:,} docs in {elapsed:.1f}s")

    total_time = time.time() - start
    print(f"\nTotal: {total_docs:,} documents, {len(all_tokens):,} tokens ({len(all_tokens)/1e6:.1f}M)")
    print(f"Tokenization time: {total_time:.1f}s ({total_docs/total_time:.0f} docs/s)")

    # Save as numpy array (memory-mappable)
    print(f"\nSaving to {out_dir}...")
    tokens_array = np.array(all_tokens, dtype=np.int32)
    tokens_path = out_dir / "pretrain_tokens.npy"
    np.save(str(tokens_path), tokens_array)
    size_mb = tokens_path.stat().st_size / 1e6
    print(f"  {tokens_path.name}: {size_mb:.1f} MB ({len(tokens_array):,} tokens)")

    # Save metadata
    meta = {
        "total_tokens": len(all_tokens),
        "total_documents": total_docs,
        "files": [f.name for f in jsonl_files],
        "vocab_size": tokenizer.vocab_size,
        "dtype": "int32",
        "special_tokens": {"BOS": BOS, "EOS": EOS},
        "tokenization_time_sec": round(total_time, 1),
    }
    meta_path = out_dir / "pretrain_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  {meta_path.name}: metadata saved")

    print(f"\nDone! Next training run: load {tokens_path.name} with np.load() for instant startup.")


if __name__ == "__main__":
    main()
