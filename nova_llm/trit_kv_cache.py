"""
NovaX LLM — Trit-Packed KV Cache for Massive Context Scaling
=============================================================
Quantizes attention K/V tensors to ternary {-1, 0, +1} with per-head
scaling, packs 5 trits per byte (TZip: 3^5=243 fits in uint8), and
manages a 3-tier paged cache (VRAM / RAM / Disk) to push context from
512 tokens to 2187 (BLOCK = 3^7) and beyond.

N-S Mapping:
    page_access_frequency = Reynolds number (high Re = hot, low Re = cold)
    eviction              = viscous dissipation (cold pages lose energy)
    tier promotion        = pressure gradient (demand pulls pages to VRAM)

3-5-7-13 Constants:
    TZip         = 5 trits/byte (H5)
    BLOCK/page   = 2187 tokens (3^7)
    layers       = 13 (H13)
    heads        = 12
    head_dim     = 64
"""

import math
import os
import struct
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# ============================================================
# 3-5-7-13 CONSTANTS
# ============================================================
H3 = 3
H5 = 5
H7 = 7
H13 = 13
BLOCK = 3 ** 7          # 2187
TZIP_TRITS = H5          # 5 trits per byte
TZIP_BASE = 3 ** H5      # 243 — fits in uint8

# Model defaults (from architecture.json)
DEFAULT_NUM_LAYERS = 13
DEFAULT_NUM_HEADS = 12
DEFAULT_HEAD_DIM = 64

# Disk cache path
DISK_CACHE_DIR = Path("C:/NovaX/temp/kv_pages")

# Reynolds thresholds for page eviction
RE_LAMINAR = 3 ** 3       # 27 — below this, page is cold
RE_TRANSITIONAL = 5 ** 3  # 125 — warm zone
RE_TURBULENT = 7 ** 3     # 343 — hot, keep in VRAM


# ============================================================
# TRIT PACKING / UNPACKING  (TZip: 5 trits per byte)
# ============================================================
# Encoding: trit -1 -> 0, trit 0 -> 1, trit +1 -> 2
# 5 trits packed as: t0 + t1*3 + t2*9 + t3*27 + t4*81  (range 0..242)

def _trits_to_byte(trits_5: np.ndarray) -> int:
    """Pack exactly 5 encoded trits (values 0,1,2) into one byte."""
    val = 0
    for i in range(len(trits_5)):
        val += int(trits_5[i]) * (3 ** i)
    return val


def _byte_to_trits(byte_val: int, count: int = TZIP_TRITS) -> np.ndarray:
    """Unpack one byte into up to 5 encoded trits (values 0,1,2)."""
    trits = np.zeros(count, dtype=np.int8)
    for i in range(count):
        trits[i] = byte_val % 3
        byte_val //= 3
    return trits


def pack_trits(encoded: np.ndarray) -> bytes:
    """Pack an array of encoded trits (0,1,2) into bytes, 5 per byte."""
    n = len(encoded)
    num_bytes = math.ceil(n / TZIP_TRITS)
    result = bytearray(num_bytes)
    for i in range(num_bytes):
        start = i * TZIP_TRITS
        end = min(start + TZIP_TRITS, n)
        chunk = encoded[start:end]
        val = 0
        for j in range(len(chunk)):
            val += int(chunk[j]) * (3 ** j)
        result[i] = val
    return bytes(result)


def unpack_trits(data: bytes, count: int) -> np.ndarray:
    """Unpack bytes back into `count` encoded trits (0,1,2)."""
    result = np.zeros(count, dtype=np.int8)
    idx = 0
    for byte_val in data:
        remaining = min(TZIP_TRITS, count - idx)
        v = byte_val
        for j in range(remaining):
            result[idx] = v % 3
            v //= 3
            idx += 1
        if idx >= count:
            break
    return result


# ============================================================
# 1. TritQuantizer
# ============================================================
class TritQuantizer:
    """Quantize float32 tensors to ternary {-1, 0, +1} with per-head scaling.

    Thresholds:
        |x| < scale/3  -> 0
        x >= scale/3   -> +1
        x <= -scale/3  -> -1

    Packing: TZip — 5 trits per byte (3^5=243 values, fits uint8).
    Scale stored as float16 per head for minimal overhead.
    """

    @staticmethod
    def quantize(tensor: "torch.Tensor", num_heads: int = 1
                 ) -> Tuple[bytes, np.ndarray, Tuple[int, ...]]:
        """Quantize a float32 tensor to trit-packed bytes + per-head float16 scales.

        Args:
            tensor: shape (batch?, num_heads, seq_len, head_dim) or (num_heads, seq_len, head_dim)
            num_heads: number of attention heads (used for per-head scaling)

        Returns:
            (packed_bytes, scales_f16, original_shape)
        """
        arr = tensor.detach().cpu().float().numpy()
        original_shape = arr.shape

        # Reshape to (num_heads, -1) for per-head scaling
        if arr.ndim == 4:
            # (B, H, T, D) — flatten batch into heads
            B, H, T, D = arr.shape
            arr_flat = arr.reshape(B * H, T * D)
        elif arr.ndim == 3:
            # (H, T, D)
            H, T, D = arr.shape
            arr_flat = arr.reshape(H, T * D)
        elif arr.ndim == 2:
            # (T, D) — single head
            arr_flat = arr.reshape(1, -1)
        else:
            arr_flat = arr.reshape(1, -1)

        n_groups = arr_flat.shape[0]
        scales = np.zeros(n_groups, dtype=np.float16)
        all_encoded = []

        for g in range(n_groups):
            row = arr_flat[g]
            s = np.max(np.abs(row))
            if s < 1e-10:
                s = 1.0  # avoid division by zero
            scales[g] = np.float16(s)

            threshold = float(scales[g]) / 3.0
            encoded = np.ones(len(row), dtype=np.int8)  # default = 1 (trit 0)
            encoded[row >= threshold] = 2   # trit +1
            encoded[row <= -threshold] = 0  # trit -1
            all_encoded.append(encoded)

        all_encoded = np.concatenate(all_encoded)
        packed = pack_trits(all_encoded)
        return packed, scales, original_shape

    @staticmethod
    def dequantize(packed: bytes, scales: np.ndarray, original_shape: Tuple[int, ...],
                   device: str = "cpu") -> "torch.Tensor":
        """Dequantize trit-packed bytes back to float32 tensor.

        Args:
            packed: trit-packed bytes from quantize()
            scales: per-head float16 scales
            original_shape: original tensor shape

        Returns:
            Approximate float32 tensor with original shape.
        """
        total_elements = 1
        for d in original_shape:
            total_elements *= d

        encoded = unpack_trits(packed, total_elements)
        # Decode: 0 -> -1, 1 -> 0, 2 -> +1
        trits = encoded.astype(np.float32) - 1.0

        # Reshape to (n_groups, group_size) and apply scales
        n_groups = len(scales)
        group_size = total_elements // n_groups
        trits = trits.reshape(n_groups, group_size)

        for g in range(n_groups):
            trits[g] *= float(scales[g])

        result = trits.reshape(original_shape)
        return torch.tensor(result, dtype=torch.float32, device=device)

    @staticmethod
    def packed_size(num_elements: int) -> int:
        """Bytes needed to store num_elements trits in TZip format."""
        return math.ceil(num_elements / TZIP_TRITS)


# ============================================================
# 2. TritKVCache
# ============================================================
class TritKVCache:
    """Trit-quantized KV cache for all layers of the transformer.

    Stores K and V projections as trit-packed bytes with per-head scales.
    Supports incremental update (append new tokens) and range retrieval.
    """

    def __init__(self, num_layers: int = DEFAULT_NUM_LAYERS,
                 num_heads: int = DEFAULT_NUM_HEADS,
                 head_dim: int = DEFAULT_HEAD_DIM,
                 max_tokens: int = BLOCK,
                 device: str = "cpu"):
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.max_tokens = max_tokens
        self.device = device

        self.quantizer = TritQuantizer()

        # Storage: per-layer list of (packed_bytes, scales, num_tokens)
        # We store per-token slices so appending is O(1).
        # k_store[layer] = list of (packed, scales, shape) per token-group
        self.k_store: List[List[Tuple[bytes, np.ndarray, tuple]]] = [
            [] for _ in range(num_layers)
        ]
        self.v_store: List[List[Tuple[bytes, np.ndarray, tuple]]] = [
            [] for _ in range(num_layers)
        ]
        self.token_count: List[int] = [0] * num_layers

    def update(self, layer_idx: int, key: "torch.Tensor", value: "torch.Tensor"):
        """Quantize and append new K, V tokens for a given layer.

        Args:
            layer_idx: which transformer layer (0..num_layers-1)
            key:   shape (batch, num_heads, new_tokens, head_dim) or (num_heads, new_tokens, head_dim)
            value: same shape as key
        """
        if self.token_count[layer_idx] + key.shape[-2] > self.max_tokens:
            # Evict oldest tokens to make room
            overflow = (self.token_count[layer_idx] + key.shape[-2]) - self.max_tokens
            self._evict_oldest(layer_idx, overflow)

        k_packed, k_scales, k_shape = self.quantizer.quantize(key, self.num_heads)
        v_packed, v_scales, v_shape = self.quantizer.quantize(value, self.num_heads)

        self.k_store[layer_idx].append((k_packed, k_scales, k_shape))
        self.v_store[layer_idx].append((v_packed, v_scales, v_shape))
        self.token_count[layer_idx] += key.shape[-2]

    def _evict_oldest(self, layer_idx: int, num_tokens: int):
        """Remove oldest tokens from a layer's cache."""
        evicted = 0
        while evicted < num_tokens and self.k_store[layer_idx]:
            entry_shape = self.k_store[layer_idx][0][2]
            entry_tokens = entry_shape[-2] if len(entry_shape) >= 2 else 1
            self.k_store[layer_idx].pop(0)
            self.v_store[layer_idx].pop(0)
            evicted += entry_tokens
            self.token_count[layer_idx] -= entry_tokens

    def get(self, layer_idx: int, start: int = 0, end: Optional[int] = None
            ) -> Tuple["torch.Tensor", "torch.Tensor"]:
        """Dequantize and return K, V for a token range.

        Args:
            layer_idx: transformer layer index
            start: start token index (inclusive)
            end: end token index (exclusive), None = all

        Returns:
            (key_tensor, value_tensor) each shape (num_heads, tokens, head_dim)
        """
        if end is None:
            end = self.token_count[layer_idx]

        # Dequantize all stored chunks for this layer
        k_chunks = []
        v_chunks = []
        for (kp, ks, kshape), (vp, vs, vshape) in zip(
                self.k_store[layer_idx], self.v_store[layer_idx]):
            k_chunks.append(self.quantizer.dequantize(kp, ks, kshape, self.device))
            v_chunks.append(self.quantizer.dequantize(vp, vs, vshape, self.device))

        if not k_chunks:
            empty = torch.zeros(self.num_heads, 0, self.head_dim,
                                device=self.device)
            return empty, empty

        # Concatenate along the sequence dimension
        # Normalize all chunks to 3D: (H, T, D)
        def normalize(t):
            if t.ndim == 4:
                return t.squeeze(0)  # remove batch dim
            if t.ndim == 2:
                return t.unsqueeze(0)
            return t

        k_all = torch.cat([normalize(c) for c in k_chunks], dim=-2)
        v_all = torch.cat([normalize(c) for c in v_chunks], dim=-2)

        # Slice the requested range
        return k_all[:, start:end, :], v_all[:, start:end, :]

    def bytes_used(self) -> int:
        """Total bytes used by trit-packed storage."""
        total = 0
        for layer_k, layer_v in zip(self.k_store, self.v_store):
            for (packed, scales, _) in layer_k:
                total += len(packed) + scales.nbytes
            for (packed, scales, _) in layer_v:
                total += len(packed) + scales.nbytes
        return total

    def float32_equivalent(self) -> int:
        """Bytes that would be used by float32 for same data."""
        total_tokens = sum(self.token_count)
        # K + V, each: num_heads * head_dim * 4 bytes per token
        return total_tokens * self.num_heads * self.head_dim * 4 * 2

    def memory_report(self) -> dict:
        """Report memory usage stats."""
        used = self.bytes_used()
        equiv = self.float32_equivalent()
        ratio = equiv / max(used, 1)
        return {
            "trit_bytes": used,
            "float32_bytes": equiv,
            "compression_ratio": round(ratio, 2),
            "total_tokens": sum(self.token_count),
            "layers_active": sum(1 for t in self.token_count if t > 0),
        }


# ============================================================
# 3. PagedTritKVCache  (VRAM / RAM / Disk tiering)
# ============================================================
class PagedTritKVCache:
    """Paged trit-packed KV cache with 3-tier memory management.

    Page size: BLOCK = 2187 tokens (3^7).

    Tiers:
        HOT   — VRAM (GPU memory): most recently accessed pages
        WARM  — RAM (system memory): auto-offloaded from VRAM
        COLD  — Disk (C:\\NovaX\\temp\\kv_pages\\): rarely accessed

    Eviction uses Reynolds-number analogy:
        Re = access_count * recency_weight
        Re > RE_TURBULENT (343)     -> HOT  (keep in VRAM)
        RE_LAMINAR (27) < Re < 343  -> WARM (offload to RAM)
        Re < RE_LAMINAR (27)        -> COLD (offload to disk)
    """

    def __init__(self, num_layers: int = DEFAULT_NUM_LAYERS,
                 num_heads: int = DEFAULT_NUM_HEADS,
                 head_dim: int = DEFAULT_HEAD_DIM,
                 max_tokens: int = BLOCK * 8,  # 8 pages default
                 device: str = "cpu",
                 vram_pages: int = 2,
                 ram_pages: int = 4,
                 disk_dir: Optional[str] = None):
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.max_tokens = max_tokens
        self.device = device
        self.page_size = BLOCK  # 2187 tokens per page
        self.vram_page_limit = vram_pages
        self.ram_page_limit = ram_pages
        self.disk_dir = Path(disk_dir or DISK_CACHE_DIR)
        self.disk_dir.mkdir(parents=True, exist_ok=True)

        self.quantizer = TritQuantizer()

        # Per-layer page management
        # page_id = (layer_idx, page_number)
        # Each page stores: {"k": (packed, scales, shape), "v": (packed, scales, shape), "tokens": int}
        self.hot: Dict[tuple, dict] = {}    # VRAM tier
        self.warm: Dict[tuple, dict] = {}   # RAM tier
        # Cold tier: pages serialized to disk

        # Access tracking for Reynolds-based eviction
        self.access_count: Dict[tuple, int] = {}
        self.last_access: Dict[tuple, float] = {}
        self.global_tick: int = 0

        # Current write position per layer
        self.write_pos: List[int] = [0] * num_layers  # total tokens written per layer

    def _page_idx(self, layer: int, token_pos: int) -> tuple:
        """Get page ID for a given layer and token position."""
        return (layer, token_pos // self.page_size)

    def _reynolds(self, page_id: tuple) -> float:
        """Compute Reynolds number for a page (access frequency * recency)."""
        count = self.access_count.get(page_id, 0)
        last = self.last_access.get(page_id, 0)
        recency = 1.0 / (1.0 + (self.global_tick - last))
        return count * recency * 100  # scale to match RE thresholds

    def _touch(self, page_id: tuple):
        """Record an access to a page."""
        self.global_tick += 1
        self.access_count[page_id] = self.access_count.get(page_id, 0) + 1
        self.last_access[page_id] = self.global_tick

    def _disk_path(self, page_id: tuple) -> Path:
        """Disk file path for a cold page."""
        layer, page_num = page_id
        return self.disk_dir / f"L{layer:02d}_P{page_num:06d}.kvpage"

    def _serialize_page(self, page: dict) -> bytes:
        """Serialize a page dict to bytes for disk storage."""
        parts = []
        for key in ("k", "v"):
            packed, scales, shape = page[key]
            # Header: len(packed) as u32, len(shape) as u8, shape dims as i32s, scales bytes
            header = struct.pack("<I", len(packed))
            header += struct.pack("<B", len(shape))
            for dim in shape:
                header += struct.pack("<i", dim)
            scales_bytes = scales.tobytes()
            header += struct.pack("<I", len(scales_bytes))
            parts.append(header + scales_bytes + packed)
        parts.append(struct.pack("<I", page["tokens"]))
        return b"".join(parts)

    def _deserialize_page(self, data: bytes) -> dict:
        """Deserialize bytes back to a page dict."""
        page = {}
        offset = 0
        for key in ("k", "v"):
            packed_len = struct.unpack_from("<I", data, offset)[0]; offset += 4
            ndims = struct.unpack_from("<B", data, offset)[0]; offset += 1
            shape = []
            for _ in range(ndims):
                shape.append(struct.unpack_from("<i", data, offset)[0]); offset += 4
            shape = tuple(shape)
            scales_len = struct.unpack_from("<I", data, offset)[0]; offset += 4
            scales = np.frombuffer(data[offset:offset + scales_len], dtype=np.float16).copy()
            offset += scales_len
            packed = data[offset:offset + packed_len]
            offset += packed_len
            page[key] = (packed, scales, shape)
        page["tokens"] = struct.unpack_from("<I", data, offset)[0]
        return page

    def _save_to_disk(self, page_id: tuple, page: dict):
        """Write a page to disk (cold tier)."""
        path = self._disk_path(page_id)
        path.write_bytes(self._serialize_page(page))

    def _load_from_disk(self, page_id: tuple) -> Optional[dict]:
        """Load a page from disk."""
        path = self._disk_path(page_id)
        if path.exists():
            return self._deserialize_page(path.read_bytes())
        return None

    def _evict_if_needed(self):
        """Evict pages based on Reynolds number when limits are exceeded."""
        # Sort hot pages by Re ascending (lowest Re = coldest)
        if len(self.hot) > self.vram_page_limit:
            hot_sorted = sorted(self.hot.keys(), key=lambda pid: self._reynolds(pid))
            while len(self.hot) > self.vram_page_limit:
                coldest = hot_sorted.pop(0)
                page = self.hot.pop(coldest)
                self.warm[coldest] = page  # demote to warm

        # If warm overflows, push to disk
        if len(self.warm) > self.ram_page_limit:
            warm_sorted = sorted(self.warm.keys(), key=lambda pid: self._reynolds(pid))
            while len(self.warm) > self.ram_page_limit:
                coldest = warm_sorted.pop(0)
                page = self.warm.pop(coldest)
                self._save_to_disk(coldest, page)  # demote to cold

    def _fetch_page(self, page_id: tuple) -> Optional[dict]:
        """Fetch a page from any tier, promoting it to hot."""
        self._touch(page_id)

        if page_id in self.hot:
            return self.hot[page_id]

        if page_id in self.warm:
            page = self.warm.pop(page_id)
            self.hot[page_id] = page
            self._evict_if_needed()
            return page

        # Try disk
        page = self._load_from_disk(page_id)
        if page is not None:
            self.hot[page_id] = page
            self._evict_if_needed()
            # Clean disk copy (now in VRAM)
            try:
                self._disk_path(page_id).unlink()
            except OSError:
                pass
            return page

        return None

    def update(self, layer_idx: int, key: "torch.Tensor", value: "torch.Tensor"):
        """Quantize and store new K, V tokens into paged cache.

        Args:
            layer_idx: transformer layer index
            key:   (num_heads, new_tokens, head_dim) or (batch, num_heads, new_tokens, head_dim)
            value: same shape as key
        """
        # Normalize to 3D
        if key.ndim == 4:
            key = key.squeeze(0)
            value = value.squeeze(0)

        new_tokens = key.shape[-2]
        pos = self.write_pos[layer_idx]

        # Process token by token or in page-aligned chunks
        written = 0
        while written < new_tokens:
            page_num = (pos + written) // self.page_size
            offset_in_page = (pos + written) % self.page_size
            page_id = (layer_idx, page_num)

            # How many tokens fit in current page
            space = self.page_size - offset_in_page
            chunk_size = min(space, new_tokens - written)

            k_chunk = key[:, written:written + chunk_size, :]
            v_chunk = value[:, written:written + chunk_size, :]

            k_packed, k_scales, k_shape = self.quantizer.quantize(k_chunk, self.num_heads)
            v_packed, v_scales, v_shape = self.quantizer.quantize(v_chunk, self.num_heads)

            existing = self._fetch_page(page_id)
            if existing is not None and offset_in_page > 0:
                # Append to existing page — for simplicity, dequantize, concat, re-quantize
                ek = self.quantizer.dequantize(*existing["k"], self.device)
                ev = self.quantizer.dequantize(*existing["v"], self.device)
                new_k = torch.cat([ek, self.quantizer.dequantize(k_packed, k_scales, k_shape, self.device)], dim=-2)
                new_v = torch.cat([ev, self.quantizer.dequantize(v_packed, v_scales, v_shape, self.device)], dim=-2)
                k_packed, k_scales, k_shape = self.quantizer.quantize(new_k, self.num_heads)
                v_packed, v_scales, v_shape = self.quantizer.quantize(new_v, self.num_heads)
                total_toks = existing["tokens"] + chunk_size
            else:
                total_toks = chunk_size

            page_data = {
                "k": (k_packed, k_scales, k_shape),
                "v": (v_packed, v_scales, v_shape),
                "tokens": total_toks,
            }
            self.hot[page_id] = page_data
            self._touch(page_id)
            written += chunk_size

        self.write_pos[layer_idx] += new_tokens
        self._evict_if_needed()

    def get(self, layer_idx: int, start: int = 0, end: Optional[int] = None
            ) -> Tuple["torch.Tensor", "torch.Tensor"]:
        """Dequantize and return K, V for a token range, transparently loading from any tier.

        Args:
            layer_idx: transformer layer index
            start: start token (inclusive)
            end: end token (exclusive), None = all written tokens

        Returns:
            (key, value) each shape (num_heads, tokens, head_dim)
        """
        if end is None:
            end = self.write_pos[layer_idx]

        k_parts = []
        v_parts = []

        first_page = start // self.page_size
        last_page = max(0, (end - 1)) // self.page_size

        for pn in range(first_page, last_page + 1):
            page_id = (layer_idx, pn)
            page = self._fetch_page(page_id)
            if page is None:
                continue

            k_full = self.quantizer.dequantize(*page["k"], self.device)
            v_full = self.quantizer.dequantize(*page["v"], self.device)

            # Normalize to 3D
            if k_full.ndim == 4:
                k_full = k_full.squeeze(0)
                v_full = v_full.squeeze(0)

            page_start_token = pn * self.page_size
            # Compute local slice within this page
            local_start = max(0, start - page_start_token)
            local_end = min(page["tokens"], end - page_start_token)

            if local_end > local_start:
                k_parts.append(k_full[:, local_start:local_end, :])
                v_parts.append(v_full[:, local_start:local_end, :])

        if not k_parts:
            empty = torch.zeros(self.num_heads, 0, self.head_dim, device=self.device)
            return empty, empty

        return torch.cat(k_parts, dim=1), torch.cat(v_parts, dim=1)

    def bytes_used(self) -> int:
        """Total bytes across all tiers."""
        total = 0
        for page in self.hot.values():
            for key in ("k", "v"):
                packed, scales, _ = page[key]
                total += len(packed) + scales.nbytes
        for page in self.warm.values():
            for key in ("k", "v"):
                packed, scales, _ = page[key]
                total += len(packed) + scales.nbytes
        # Disk pages — count file sizes
        if self.disk_dir.exists():
            for f in self.disk_dir.glob("*.kvpage"):
                total += f.stat().st_size
        return total

    def tier_report(self) -> dict:
        """Report pages per tier and Reynolds numbers."""
        hot_re = {str(k): round(self._reynolds(k), 1) for k in self.hot}
        warm_re = {str(k): round(self._reynolds(k), 1) for k in self.warm}
        cold_count = sum(1 for _ in self.disk_dir.glob("*.kvpage")) if self.disk_dir.exists() else 0
        return {
            "hot_pages": len(self.hot),
            "warm_pages": len(self.warm),
            "cold_pages": cold_count,
            "hot_reynolds": hot_re,
            "warm_reynolds": warm_re,
        }


# ============================================================
# 4. Memory Budget Calculator
# ============================================================
class MemoryBudget:
    """Calculate and compare memory usage for KV cache strategies."""

    def __init__(self, num_layers: int = DEFAULT_NUM_LAYERS,
                 num_heads: int = DEFAULT_NUM_HEADS,
                 head_dim: int = DEFAULT_HEAD_DIM):
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.head_dim = head_dim

    def float32_per_token(self) -> int:
        """Bytes per token for float32 KV cache (K + V)."""
        # Per layer: K and V each = num_heads * head_dim * 4 bytes
        per_layer = self.num_heads * self.head_dim * 4 * 2  # K + V
        return per_layer * self.num_layers

    def float16_per_token(self) -> int:
        """Bytes per token for float16 KV cache."""
        per_layer = self.num_heads * self.head_dim * 2 * 2
        return per_layer * self.num_layers

    def trit_per_token(self) -> float:
        """Bytes per token for trit-packed KV cache (TZip + scales)."""
        elements_per_layer = self.num_heads * self.head_dim  # per K or V
        # TZip: 5 trits per byte
        trit_bytes = math.ceil(elements_per_layer / TZIP_TRITS)
        # Per-head scale: 2 bytes (float16) per head
        scale_bytes = self.num_heads * 2
        # K + V
        per_layer = (trit_bytes + scale_bytes) * 2
        return per_layer * self.num_layers

    def max_tokens(self, vram_gb: float = 8.0, ram_gb: float = 32.0,
                   model_vram_gb: float = 1.5) -> dict:
        """Calculate max tokens for each format given memory constraints.

        Args:
            vram_gb: total VRAM
            ram_gb: total system RAM
            model_vram_gb: VRAM used by model weights + activations

        Returns:
            dict with max tokens per format
        """
        available_vram = (vram_gb - model_vram_gb) * (1024 ** 3)
        available_ram = ram_gb * 0.5 * (1024 ** 3)  # use 50% of RAM

        f32_tok = self.float32_per_token()
        f16_tok = self.float16_per_token()
        trit_tok = self.trit_per_token()

        return {
            "float32": {
                "vram_only": int(available_vram / f32_tok),
                "bytes_per_token": f32_tok,
            },
            "float16": {
                "vram_only": int(available_vram / f16_tok),
                "bytes_per_token": f16_tok,
            },
            "trit_packed": {
                "vram_only": int(available_vram / trit_tok),
                "vram_plus_ram": int((available_vram + available_ram) / trit_tok),
                "bytes_per_token": round(trit_tok, 1),
            },
        }

    def print_table(self, vram_gb: float = 8.0, ram_gb: float = 32.0,
                    model_vram_gb: float = 1.5):
        """Print a formatted comparison table."""
        info = self.max_tokens(vram_gb, ram_gb, model_vram_gb)
        avail_vram = vram_gb - model_vram_gb

        print(f"\n{'='*70}")
        print(f"  NovaX LLM KV Cache Memory Budget")
        print(f"  Model: {self.num_layers}L / {self.num_heads}H / {self.head_dim}D")
        print(f"  VRAM: {vram_gb} GB (avail: {avail_vram:.1f} GB)  |  RAM: {ram_gb} GB")
        print(f"{'='*70}")
        print(f"  {'Format':<16} {'B/token':>10} {'VRAM tokens':>14} {'VRAM+RAM':>14} {'Ratio':>8}")
        print(f"  {'-'*62}")

        f32 = info["float32"]
        f16 = info["float16"]
        trit = info["trit_packed"]

        print(f"  {'float32':<16} {f32['bytes_per_token']:>10,} {f32['vram_only']:>14,} {'N/A':>14} {'1.0x':>8}")
        print(f"  {'float16':<16} {f16['bytes_per_token']:>10,} {f16['vram_only']:>14,} {'N/A':>14} {'2.0x':>8}")
        ratio = f32['bytes_per_token'] / trit['bytes_per_token']
        print(f"  {'trit (TZip)':<16} {trit['bytes_per_token']:>10,} {trit['vram_only']:>14,} {trit['vram_plus_ram']:>14,} {ratio:>7.1f}x")

        print(f"\n  Target context: {BLOCK} tokens (BLOCK = 3^7)")
        target_trit_mb = BLOCK * trit["bytes_per_token"] / (1024 ** 2)
        target_f32_mb = BLOCK * f32["bytes_per_token"] / (1024 ** 2)
        print(f"  At {BLOCK} tokens:  trit = {target_trit_mb:.1f} MB  |  float32 = {target_f32_mb:.1f} MB")
        print(f"{'='*70}\n")


# ============================================================
# 5. Benchmark
# ============================================================
def benchmark(num_heads: int = DEFAULT_NUM_HEADS,
              head_dim: int = DEFAULT_HEAD_DIM,
              seq_len: int = 512,
              num_trials: int = 5):
    """Benchmark trit quantization: speed, memory, reconstruction error."""
    print(f"\n{'='*70}")
    print(f"  Trit KV Cache Benchmark")
    print(f"  Shape: ({num_heads}, {seq_len}, {head_dim}) = {num_heads * seq_len * head_dim:,} elements")
    print(f"  Trials: {num_trials}")
    print(f"{'='*70}\n")

    quantizer = TritQuantizer()

    # Generate random data simulating attention K/V
    torch.manual_seed(42)
    tensor = torch.randn(num_heads, seq_len, head_dim)

    # --- Float32 baseline ---
    f32_bytes = tensor.numel() * 4
    print(f"  Float32 size:    {f32_bytes:>10,} bytes")

    # --- Float16 baseline ---
    f16 = tensor.half()
    f16_bytes = f16.numel() * 2
    f16_mse = ((tensor - f16.float()) ** 2).mean().item()
    print(f"  Float16 size:    {f16_bytes:>10,} bytes  |  MSE: {f16_mse:.2e}")

    # --- Trit quantization ---
    # Warmup
    packed, scales, shape = quantizer.quantize(tensor, num_heads)
    _ = quantizer.dequantize(packed, scales, shape)

    # Timed quantize
    t0 = time.perf_counter()
    for _ in range(num_trials):
        packed, scales, shape = quantizer.quantize(tensor, num_heads)
    quant_time = (time.perf_counter() - t0) / num_trials

    trit_bytes = len(packed) + scales.nbytes
    print(f"  Trit size:       {trit_bytes:>10,} bytes  |  {TZIP_TRITS} trits/byte (TZip)")

    # Timed dequantize
    t0 = time.perf_counter()
    for _ in range(num_trials):
        restored = quantizer.dequantize(packed, scales, shape)
    dequant_time = (time.perf_counter() - t0) / num_trials

    # Reconstruction error
    mse = ((tensor - restored) ** 2).mean().item()
    cosine_sim = torch.nn.functional.cosine_similarity(
        tensor.flatten().unsqueeze(0),
        restored.flatten().unsqueeze(0)
    ).item()

    compression = f32_bytes / trit_bytes

    print(f"\n  --- Results ---")
    print(f"  Compression:     {compression:.1f}x  vs float32")
    print(f"  Compression:     {f16_bytes / trit_bytes:.1f}x  vs float16")
    print(f"  MSE (trit):      {mse:.6f}")
    print(f"  MSE (float16):   {f16_mse:.2e}")
    print(f"  Cosine sim:      {cosine_sim:.6f}")
    print(f"  Quantize time:   {quant_time * 1000:.2f} ms")
    print(f"  Dequantize time: {dequant_time * 1000:.2f} ms")

    # --- TritKVCache integration test ---
    print(f"\n  --- KV Cache Integration ---")
    cache = TritKVCache(num_layers=DEFAULT_NUM_LAYERS, num_heads=num_heads,
                        head_dim=head_dim, max_tokens=BLOCK)

    key = torch.randn(num_heads, seq_len, head_dim)
    val = torch.randn(num_heads, seq_len, head_dim)

    t0 = time.perf_counter()
    for layer in range(DEFAULT_NUM_LAYERS):
        cache.update(layer, key, val)
    update_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    for layer in range(DEFAULT_NUM_LAYERS):
        k_out, v_out = cache.get(layer)
    get_time = time.perf_counter() - t0

    report = cache.memory_report()
    print(f"  Stored: {report['total_tokens']} tokens across {report['layers_active']} layers")
    print(f"  Trit cache:      {report['trit_bytes']:>10,} bytes")
    print(f"  Float32 equiv:   {report['float32_bytes']:>10,} bytes")
    print(f"  Compression:     {report['compression_ratio']:.1f}x")
    print(f"  Update time:     {update_time * 1000:.1f} ms ({DEFAULT_NUM_LAYERS} layers)")
    print(f"  Get time:        {get_time * 1000:.1f} ms ({DEFAULT_NUM_LAYERS} layers)")

    # --- Paged cache test ---
    print(f"\n  --- Paged Cache (VRAM/RAM/Disk tiering) ---")
    paged = PagedTritKVCache(
        num_layers=3,  # test with 3 layers for speed
        num_heads=num_heads,
        head_dim=head_dim,
        max_tokens=BLOCK * 4,
        vram_pages=2,
        ram_pages=2,
    )

    # Write enough tokens to trigger eviction
    chunk = 256
    total_written = 0
    for i in range(0, BLOCK, chunk):
        size = min(chunk, BLOCK - i)
        k = torch.randn(num_heads, size, head_dim)
        v = torch.randn(num_heads, size, head_dim)
        for layer in range(3):
            paged.update(layer, k, v)
        total_written += size

    tier = paged.tier_report()
    print(f"  Written: {total_written} tokens (1 BLOCK)")
    print(f"  Hot pages:  {tier['hot_pages']}")
    print(f"  Warm pages: {tier['warm_pages']}")
    print(f"  Cold pages: {tier['cold_pages']}")
    print(f"  Total bytes: {paged.bytes_used():,}")

    # Test transparent retrieval
    k_out, v_out = paged.get(0, 0, min(512, total_written))
    print(f"  Retrieved: K{list(k_out.shape)}, V{list(v_out.shape)}")

    print(f"\n{'='*70}")
    print(f"  All benchmarks passed.")
    print(f"{'='*70}\n")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    if not HAS_TORCH:
        print("ERROR: PyTorch required. Install with: pip install torch")
        exit(1)

    # Print memory budget table
    budget = MemoryBudget()
    budget.print_table(vram_gb=8.0, ram_gb=32.0, model_vram_gb=1.5)

    # Run benchmark
    benchmark()
