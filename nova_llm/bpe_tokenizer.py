"""
NovaX BPE Tokenizer v1.0
Byte Pair Encoding tokenizer for NovaX LLM.

Backward-compatible with the byte-level encoding in inference_server.py:
  - Single bytes map to indices 13-268 (byte value + 13)
  - BPE merges start at index 269
  - Special tokens 0-12 are reserved

3-5-7-13 Harmonic Design:
  Token 0  = PAD
  Token 1  = BOS
  Token 2  = EOS
  Token 3  = UNK
  Token 4  = MASK
  Token 5  = SEP
  Token 6-12 = reserved
  Token 13-268 = single bytes (256 values)
  Token 269+ = BPE merges
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================
# CONSTANTS
# ============================================================
SPECIAL_TOKENS = {
    "<PAD>": 0,
    "<BOS>": 1,
    "<EOS>": 2,
    "<UNK>": 3,
    "<MASK>": 4,
    "<SEP>": 5,
}
RESERVED_END = 13       # indices 6-12 reserved
BYTE_OFFSET = 13        # single bytes start here
BYTE_END = 269           # 13 + 256
MERGE_START = 269        # BPE merges start here
DEFAULT_VOCAB_SIZE = 32768


class NovaXTokenizer:
    """BPE tokenizer for NovaX LLM.

    Token layout:
      0     = PAD
      1     = BOS
      2     = EOS
      3     = UNK
      4     = MASK
      5     = SEP
      6-12  = reserved
      13-268 = single bytes (backward compatible with current encoding)
      269+  = BPE merges
    """

    def __init__(self, vocab_path: Optional[str] = None):
        # token <-> id mappings
        self.token_to_id: Dict[bytes, int] = {}
        self.id_to_token: Dict[int, bytes] = {}
        # Ordered list of merges: [(token_a, token_b), ...]
        self.merges: List[Tuple[bytes, bytes]] = []
        # Merge priority lookup: (token_a, token_b) -> rank (lower = higher priority)
        self._merge_rank: Dict[Tuple[bytes, bytes], int] = {}

        # Initialize base vocabulary
        self._init_base_vocab()

        if vocab_path is not None:
            self.load(vocab_path)

    def _init_base_vocab(self):
        """Initialize with special tokens + 256 single-byte tokens."""
        self.token_to_id = {}
        self.id_to_token = {}

        # Special tokens (stored as string keys internally, mapped to bytes for consistency)
        for name, tid in SPECIAL_TOKENS.items():
            token_bytes = name.encode("utf-8")
            self.token_to_id[token_bytes] = tid
            self.id_to_token[tid] = token_bytes

        # Reserved 6-12
        for i in range(6, RESERVED_END):
            token_bytes = f"<RESERVED_{i}>".encode("utf-8")
            self.token_to_id[token_bytes] = i
            self.id_to_token[i] = token_bytes

        # Single bytes: 0x00..0xFF -> indices 13..268
        for b in range(256):
            token_bytes = bytes([b])
            tid = b + BYTE_OFFSET
            self.token_to_id[token_bytes] = tid
            self.id_to_token[tid] = token_bytes

    @property
    def vocab_size(self) -> int:
        return len(self.id_to_token)

    # ============================================================
    # TRAINING
    # ============================================================
    def train(self, texts: List[str], vocab_size: int = DEFAULT_VOCAB_SIZE,
              min_frequency: int = 2, verbose: bool = True):
        """Train BPE on a corpus of texts.

        Algorithm:
        1. Start with byte-level vocabulary (indices 13-268)
        2. Encode all texts to byte sequences, group by unique word
        3. Count all adjacent token pairs (weighted by word frequency)
        4. Merge most frequent pair -> new token (starting at 269)
        5. Incrementally update pair counts (no full rescan)
        6. Repeat until vocab_size reached or no pairs above min_frequency

        Uses word-frequency optimization: identical sequences are grouped and
        counted once, weighted by frequency. This is O(merges * unique_words)
        instead of O(merges * total_corpus_tokens).
        """
        self._init_base_vocab()
        self.merges = []
        self._merge_rank = {}

        if verbose:
            print(f"[BPE] Training on {len(texts)} texts, target vocab_size={vocab_size}")

        # Split texts into whitespace-delimited words, count frequencies.
        # This is the standard BPE optimization: treat each unique word as a
        # sequence, weighted by its corpus frequency.
        word_freqs: Counter = Counter()
        total_bytes = 0
        for text in texts:
            # Pre-tokenize: split on whitespace boundaries, keeping the space
            # attached to the following word (GPT-2 style) or as separate tokens.
            # For simplicity, split on spaces and newlines.
            for chunk in re.split(r'(\s+)', text):
                if chunk:
                    word_freqs[chunk] += 1
                    total_bytes += len(chunk.encode("utf-8"))

        # Convert words to byte-token sequences
        word_tokens: Dict[str, List[bytes]] = {}
        for word in word_freqs:
            encoded = word.encode("utf-8")
            word_tokens[word] = [bytes([b]) for b in encoded]

        if verbose:
            print(f"[BPE] Corpus: {len(word_freqs)} unique words, {total_bytes:,} bytes")

        num_merges_needed = vocab_size - len(self.id_to_token)
        if num_merges_needed <= 0:
            if verbose:
                print("[BPE] Vocab already at target size, no merges needed")
            return

        # Build initial pair counts
        pair_counts: Counter = Counter()
        # For each word, track which pairs exist (for incremental updates)
        # pair_to_words[pair] = set of words containing that pair
        pair_to_words: Dict[Tuple[bytes, bytes], set] = defaultdict(set)

        for word, tokens in word_tokens.items():
            freq = word_freqs[word]
            for i in range(len(tokens) - 1):
                pair = (tokens[i], tokens[i + 1])
                pair_counts[pair] += freq
                pair_to_words[pair].add(word)

        next_id = MERGE_START
        t0 = __import__("time").time()

        for merge_i in range(num_merges_needed):
            if not pair_counts:
                if verbose:
                    print(f"[BPE] No more pairs to merge at step {merge_i}")
                break

            # Find the most frequent pair
            best_pair = max(pair_counts, key=pair_counts.get)
            best_count = pair_counts[best_pair]

            if best_count < min_frequency:
                if verbose:
                    print(f"[BPE] Stopping: best pair frequency {best_count} < min_frequency {min_frequency}")
                break

            # Create merged token
            new_token = best_pair[0] + best_pair[1]
            self.token_to_id[new_token] = next_id
            self.id_to_token[next_id] = new_token
            self.merges.append(best_pair)
            self._merge_rank[best_pair] = len(self.merges) - 1
            next_id += 1

            # Apply merge to affected words and incrementally update pair counts
            affected_words = pair_to_words.pop(best_pair, set()).copy()
            del pair_counts[best_pair]

            for word in affected_words:
                freq = word_freqs[word]
                old_tokens = word_tokens[word]

                # Remove old pair counts for this word
                for i in range(len(old_tokens) - 1):
                    p = (old_tokens[i], old_tokens[i + 1])
                    if p != best_pair:
                        pair_counts[p] -= freq
                        if pair_counts[p] <= 0:
                            del pair_counts[p]
                        pair_to_words[p].discard(word)
                        if not pair_to_words[p]:
                            del pair_to_words[p]

                # Apply merge
                new_tokens = self._apply_merge(old_tokens, best_pair, new_token)
                word_tokens[word] = new_tokens

                # Add new pair counts
                for i in range(len(new_tokens) - 1):
                    p = (new_tokens[i], new_tokens[i + 1])
                    pair_counts[p] += freq
                    pair_to_words[p].add(word)

            if verbose and (merge_i + 1) % 500 == 0:
                elapsed = __import__("time").time() - t0
                print(f"[BPE] Merge {merge_i + 1}/{num_merges_needed}: "
                      f"{self._token_repr(best_pair[0])}+{self._token_repr(best_pair[1])} "
                      f"-> id {next_id - 1} (freq={best_count}) [{elapsed:.1f}s]")

        if verbose:
            elapsed = __import__("time").time() - t0
            print(f"[BPE] Training complete: {len(self.merges)} merges, "
                  f"vocab_size={self.vocab_size} [{elapsed:.1f}s]")

    @staticmethod
    def _apply_merge(word: List[bytes], pair: Tuple[bytes, bytes],
                     merged: bytes) -> List[bytes]:
        """Apply a single merge operation to a token sequence."""
        if len(word) < 2:
            return word
        new_word = []
        i = 0
        while i < len(word):
            if i < len(word) - 1 and word[i] == pair[0] and word[i + 1] == pair[1]:
                new_word.append(merged)
                i += 2
            else:
                new_word.append(word[i])
                i += 1
        return new_word

    # ============================================================
    # ENCODING
    # ============================================================
    def encode(self, text: str) -> List[int]:
        """Encode text to token IDs using learned merges.

        Uses word-level chunking + per-chunk BPE for O(chunk_size) performance.
        Splits on whitespace/punctuation boundaries first, then applies BPE
        within each chunk. This bounds the inner loop to small sequences.
        """
        if not text:
            return []

        # Build merge rank lookup once
        if not hasattr(self, '_merge_rank'):
            self._merge_rank = {}
            for i, pair in enumerate(self.merges):
                self._merge_rank[pair] = i

        raw = text.encode("utf-8")

        # Split into word-like chunks on whitespace/punctuation boundaries
        # This is the key optimization: BPE within small chunks is fast
        chunks = []
        chunk_start = 0
        for j in range(len(raw)):
            b = raw[j]
            # Split on space, newline, tab, or common punctuation
            if b in (32, 10, 13, 9):  # whitespace
                if j > chunk_start:
                    chunks.append(raw[chunk_start:j])
                chunks.append(raw[j:j+1])  # whitespace as own chunk
                chunk_start = j + 1
        if chunk_start < len(raw):
            chunks.append(raw[chunk_start:])

        all_ids = []
        for chunk in chunks:
            tokens = [bytes([b]) for b in chunk]
            # Apply BPE merges within this chunk
            changed = True
            while changed and len(tokens) >= 2:
                changed = False
                best_pair = None
                best_rank = len(self.merges)
                best_idx = -1
                for i in range(len(tokens) - 1):
                    pair = (tokens[i], tokens[i + 1])
                    rank = self._merge_rank.get(pair)
                    if rank is not None and rank < best_rank:
                        best_rank = rank
                        best_pair = pair
                        best_idx = i

                if best_pair is not None:
                    merged = best_pair[0] + best_pair[1]
                    new_tokens = []
                    i = 0
                    while i < len(tokens):
                        if i < len(tokens) - 1 and tokens[i] == best_pair[0] and tokens[i + 1] == best_pair[1]:
                            new_tokens.append(merged)
                            i += 2
                        else:
                            new_tokens.append(tokens[i])
                            i += 1
                    tokens = new_tokens
                    changed = True

            # Convert chunk tokens to IDs
            for token in tokens:
                tid = self.token_to_id.get(token)
                if tid is not None:
                    all_ids.append(tid)
                else:
                    for b in token:
                        all_ids.append(b + BYTE_OFFSET)

        return all_ids

    def encode_with_special(self, text: str, add_bos: bool = True,
                            add_eos: bool = False) -> List[int]:
        """Encode with BOS/EOS wrapping, matching inference_server.py convention."""
        ids = []
        if add_bos:
            ids.append(SPECIAL_TOKENS["<BOS>"])
        ids.extend(self.encode(text))
        if add_eos:
            ids.append(SPECIAL_TOKENS["<EOS>"])
        return ids

    # ============================================================
    # DECODING
    # ============================================================
    def decode(self, ids: List[int]) -> str:
        """Decode token IDs back to text.

        Maps each ID to its byte sequence, concatenates, decodes as UTF-8.
        Skips special tokens (PAD, BOS, EOS, SEP, MASK, reserved).
        """
        byte_chunks = []
        for tid in ids:
            if tid in (0, 1, 2, 4, 5) or (6 <= tid <= 12):
                continue  # Skip special/reserved
            if tid == 3:  # UNK
                byte_chunks.append(b"?")
                continue
            token_bytes = self.id_to_token.get(tid)
            if token_bytes is not None and not token_bytes.startswith(b"<"):
                byte_chunks.append(token_bytes)
            elif tid >= BYTE_OFFSET and tid < BYTE_END:
                # Fallback to byte-level
                byte_chunks.append(bytes([tid - BYTE_OFFSET]))

        raw = b"".join(byte_chunks)
        return raw.decode("utf-8", errors="replace")

    # ============================================================
    # SAVE / LOAD
    # ============================================================
    def save(self, path: str):
        """Save vocab + merges to JSON.

        Format:
        {
            "special_tokens": {"<PAD>": 0, ...},
            "vocab": {"<hex_repr>": id, ...},
            "merges": [["<hex_a>", "<hex_b>"], ...],
            "id_to_token": {id: "<hex_repr>", ...},
            "meta": {"version": "1.0", "vocab_size": N, "num_merges": M}
        }
        """
        # Use hex encoding for byte sequences to ensure JSON safety
        vocab_serialized = {}
        id_to_token_serialized = {}

        for token_bytes, tid in self.token_to_id.items():
            key = token_bytes.hex()
            vocab_serialized[key] = tid

        for tid, token_bytes in self.id_to_token.items():
            id_to_token_serialized[str(tid)] = token_bytes.hex()

        merges_serialized = []
        for a, b in self.merges:
            merges_serialized.append([a.hex(), b.hex()])

        data = {
            "special_tokens": SPECIAL_TOKENS,
            "vocab": vocab_serialized,
            "merges": merges_serialized,
            "id_to_token": id_to_token_serialized,
            "meta": {
                "version": "1.0",
                "vocab_size": self.vocab_size,
                "num_merges": len(self.merges),
                "byte_offset": BYTE_OFFSET,
                "merge_start": MERGE_START,
            },
        }

        path = str(path)
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=True)

        print(f"[BPE] Saved tokenizer to {path} "
              f"(vocab={self.vocab_size}, merges={len(self.merges)})")

    def load(self, path: str):
        """Load vocab + merges from JSON."""
        path = str(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Tokenizer file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Reinitialize
        self._init_base_vocab()
        self.merges = []
        self._merge_rank = {}

        # Load vocab (overwrites base where needed)
        vocab_data = data.get("vocab", {})
        for hex_key, tid in vocab_data.items():
            token_bytes = bytes.fromhex(hex_key)
            self.token_to_id[token_bytes] = tid
            self.id_to_token[tid] = token_bytes

        # Load merges in order
        merges_data = data.get("merges", [])
        for i, (hex_a, hex_b) in enumerate(merges_data):
            a = bytes.fromhex(hex_a)
            b = bytes.fromhex(hex_b)
            self.merges.append((a, b))
            self._merge_rank[(a, b)] = i

        meta = data.get("meta", {})
        print(f"[BPE] Loaded tokenizer from {path} "
              f"(vocab={self.vocab_size}, merges={len(self.merges)}, "
              f"version={meta.get('version', '?')})")

    # ============================================================
    # UTILITIES
    # ============================================================
    @staticmethod
    def _token_repr(token_bytes: bytes) -> str:
        """Human-readable representation of a byte-sequence token."""
        try:
            text = token_bytes.decode("utf-8")
            if text.isprintable() and len(text) > 0:
                return repr(text)
        except UnicodeDecodeError:
            pass
        return f"0x{token_bytes.hex()}"

    def token_to_string(self, tid: int) -> str:
        """Get human-readable string for a token ID."""
        token_bytes = self.id_to_token.get(tid)
        if token_bytes is None:
            return f"<INVALID:{tid}>"
        # Check special tokens
        for name, special_id in SPECIAL_TOKENS.items():
            if tid == special_id:
                return name
        if 6 <= tid <= 12:
            return f"<RESERVED_{tid}>"
        return self._token_repr(token_bytes)

    def compression_ratio(self, text: str) -> float:
        """Compute compression ratio vs byte-level encoding.

        Returns ratio of byte-level tokens to BPE tokens.
        Higher = better compression.
        """
        byte_count = len(text.encode("utf-8"))
        bpe_count = len(self.encode(text))
        if bpe_count == 0:
            return 0.0
        return byte_count / bpe_count

    def stats(self, texts: List[str]) -> dict:
        """Compute tokenization statistics over a set of texts."""
        total_chars = 0
        total_bytes = 0
        total_tokens = 0
        total_words = 0

        for text in texts:
            total_chars += len(text)
            total_bytes += len(text.encode("utf-8"))
            total_tokens += len(self.encode(text))
            total_words += len(text.split())

        return {
            "vocab_size": self.vocab_size,
            "num_merges": len(self.merges),
            "total_texts": len(texts),
            "total_chars": total_chars,
            "total_bytes": total_bytes,
            "total_tokens": total_tokens,
            "total_words": total_words,
            "avg_tokens_per_word": total_tokens / max(total_words, 1),
            "compression_ratio": total_bytes / max(total_tokens, 1),
            "bytes_per_token": total_bytes / max(total_tokens, 1),
        }


# ============================================================
# INTEGRATION HELPER
# ============================================================
def patch_inference_server(vocab_path: Optional[str] = None):
    """Returns encode/decode functions compatible with inference_server.py.

    Usage in inference_server.py:
        from bpe_tokenizer import patch_inference_server
        encode_text, decode_tokens = patch_inference_server("bpe_vocab.json")

    The returned functions have the same signatures as the originals:
        encode_text(text) -> List[int]
        decode_tokens(ids) -> str
    """
    if vocab_path is None:
        vocab_path = str(Path(__file__).parent / "bpe_vocab.json")

    tokenizer = NovaXTokenizer(vocab_path)

    def encode_text(text: str) -> List[int]:
        return tokenizer.encode(text)

    def decode_tokens(ids: List[int]) -> str:
        return tokenizer.decode(ids)

    return encode_text, decode_tokens


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NovaX BPE Tokenizer")
    parser.add_argument("--load", type=str, help="Load tokenizer from file")
    parser.add_argument("--encode", type=str, help="Text to encode")
    parser.add_argument("--decode", type=str, help="Comma-separated token IDs to decode")
    args = parser.parse_args()

    if args.load:
        tok = NovaXTokenizer(args.load)
    else:
        tok = NovaXTokenizer()

    if args.encode:
        ids = tok.encode(args.encode)
        print(f"Text:   {args.encode!r}")
        print(f"Tokens: {ids}")
        print(f"Count:  {len(ids)} (byte-level would be {len(args.encode.encode('utf-8'))})")
        print(f"Ratio:  {tok.compression_ratio(args.encode):.2f}x")

    if args.decode:
        ids = [int(x.strip()) for x in args.decode.split(",")]
        text = tok.decode(ids)
        print(f"IDs:  {ids}")
        print(f"Text: {text!r}")
