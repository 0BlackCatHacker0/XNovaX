"""
NovaX LLM -- Cached Inference with Trit-Packed KV Cache
=======================================================
Wraps TernaryTransformer with a KV cache that quantizes K/V to trits,
enabling context scaling from 512 to 1M+ tokens via paged 3-tier storage.

Paged mode (use_paged=True):
  HOT  tier = VRAM (GPU)  -- most recent / most accessed pages
  WARM tier = RAM         -- auto-offloaded from VRAM under pressure
  COLD tier = Disk        -- rarely accessed, loaded on demand

Integration: replaces the naive generate() loop in inference_server.py
with one that caches K/V per layer and only computes new tokens.

MemoryManager integration: after each decode_one() call, memory pressure
is checked and eviction triggered automatically if budgets are exceeded.
"""

import math
import time
import torch
import torch.nn.functional as F
from typing import Optional, Tuple, List

from trit_kv_cache import TritKVCache, PagedTritKVCache, TritQuantizer, BLOCK
# Hoisted from inside decode hot loops — train.py does not import this module,
# so there is no circular-import risk.
from train import apply_rotary


class CachedInference:
    """Wraps a TernaryTransformer for incremental generation with trit KV cache.

    On first call (prefill), processes the full prompt and caches all K/V.
    On subsequent calls (decode), processes only the new token, retrieves
    cached K/V for attention, and appends the new K/V.

    Memory: ~5.0 KB/token (trit) vs ~79.8 KB/token (float32) = ~16x savings.
    With paged cache: VRAM->RAM->Disk tiering for million-token context.
    """

    def __init__(self, model, config, device, use_paged=False, max_context=2187,
                 memory_manager=None):
        self.model = model
        self.device = device
        self.max_context = max_context

        model_cfg = config["model"]
        self.num_layers = model_cfg["num_layers"]
        self.num_heads = model_cfg["num_heads"]
        self.head_dim = model_cfg["head_dim"]
        self.embed_dim = model_cfg["embedding_dim"]

        self.use_paged = use_paged
        self.memory_manager = memory_manager

        # Choose cache type
        self._init_cache()

        self.seq_len = 0  # Current cached sequence length

    def _init_cache(self):
        """Initialize the KV cache based on mode."""
        if self.use_paged:
            # Calculate page limits from memory manager budgets if available
            # Default: generous limits for million-token context
            vram_pages = 256   # ~560K tokens in VRAM (256 * 2187)
            ram_pages = 1024   # ~2.2M tokens in RAM
            disk_dir = "C:/NovaX/nova_llm/cache"

            if self.memory_manager:
                # Estimate bytes per page to derive page limits from budgets
                elements = self.num_heads * self.head_dim
                trit_bytes = math.ceil(elements / 5)
                scale_bytes = self.num_heads * 2
                per_layer = (trit_bytes + scale_bytes) * 2  # K + V
                per_token = per_layer * self.num_layers
                bytes_per_page = per_token * BLOCK  # 2187 tokens per page

                if bytes_per_page > 0:
                    vram_pages = max(2, self.memory_manager.gpu_budget_bytes // bytes_per_page)
                    ram_pages = max(4, self.memory_manager.ram_budget_bytes // bytes_per_page)
                disk_dir = str(self.memory_manager.disk_path)

            self.kv_cache = PagedTritKVCache(
                num_layers=self.num_layers,
                num_heads=self.num_heads,
                head_dim=self.head_dim,
                max_tokens=self.max_context,
                device=str(self.device),
                vram_pages=vram_pages,
                ram_pages=ram_pages,
                disk_dir=disk_dir,
            )
            # Attach cache to memory manager for monitoring
            if self.memory_manager:
                self.memory_manager.attach_cache(self.kv_cache)
        else:
            self.kv_cache = TritKVCache(
                num_layers=self.num_layers,
                num_heads=self.num_heads,
                head_dim=self.head_dim,
                max_tokens=self.max_context,
            )

    def reset(self):
        """Clear the KV cache for a new sequence."""
        self._init_cache()
        self.seq_len = 0

    def context_length(self) -> int:
        """Return current cached sequence length (number of tokens cached)."""
        return self.seq_len

    def extend_context(self, new_max: int):
        """Grow the cache's maximum context dynamically.

        For paged cache: simply increases the max_tokens limit (pages are
        allocated on demand, so no memory is wasted).
        For flat cache: creates a new cache and copies existing data. Flat
        cache is limited by available RAM, so this mainly benefits paged mode.

        Args:
            new_max: new maximum context length (must be >= current max).
        """
        if new_max <= self.max_context:
            return  # Already large enough

        old_max = self.max_context
        self.max_context = new_max

        if self.use_paged:
            # Paged cache: just update the limit; pages are allocated lazily
            self.kv_cache.max_tokens = new_max
        else:
            # Flat cache: need to rebuild with larger limit
            # Preserve existing cached data by keeping the old cache's stores
            old_cache = self.kv_cache
            self.kv_cache = TritKVCache(
                num_layers=self.num_layers,
                num_heads=self.num_heads,
                head_dim=self.head_dim,
                max_tokens=new_max,
            )
            # Copy stored data from old cache
            self.kv_cache.k_store = old_cache.k_store
            self.kv_cache.v_store = old_cache.v_store
            self.kv_cache.token_count = old_cache.token_count

    def _ensure_device(self, tensor: torch.Tensor) -> torch.Tensor:
        """Ensure a tensor is on the correct device.

        PagedTritKVCache.get() may return tensors dequantized from different
        tiers (VRAM/RAM/disk) -- they all come out on CPU after numpy
        conversion. This method moves them to self.device.
        """
        if tensor.device != self.device:
            return tensor.to(self.device)
        return tensor

    @torch.no_grad()
    def prefill(self, input_ids: torch.Tensor) -> torch.Tensor:
        """Process prompt tokens, cache K/V for all layers, return logits.

        Args:
            input_ids: (1, T) token IDs
        Returns:
            logits: (1, T, vocab_size)
        """
        B, T = input_ids.shape
        x = self.model.token_emb(input_ids)
        x = x * math.sqrt(self.embed_dim)

        # Causal mask for full prompt
        causal_mask = torch.tril(torch.ones(T, T, device=self.device, dtype=torch.bool))

        for layer_idx, layer in enumerate(self.model.layers):
            # Pre-norm
            h = layer.attn_norm(x)

            # Compute Q, K, V
            attn = layer.attn
            q = attn.q_proj(h).view(B, T, attn.num_heads, attn.head_dim).transpose(1, 2)
            k = attn.k_proj(h).view(B, T, attn.num_heads, attn.head_dim).transpose(1, 2)
            v = attn.v_proj(h).view(B, T, attn.num_heads, attn.head_dim).transpose(1, 2)

            # Rotary encoding
            cos, sin = attn.rope(q, T)
            q = apply_rotary(q, cos, sin)
            k = apply_rotary(k, cos, sin)

            # Cache K, V (quantized to trits)
            # Shape: (B, num_heads, T, head_dim) -> squeeze batch for cache
            self.kv_cache.update(layer_idx, k.squeeze(0), v.squeeze(0))

            # Standard attention
            scores = torch.matmul(q, k.transpose(-2, -1)) / attn.scale
            scores = scores.masked_fill(~causal_mask, float("-inf"))
            weights = F.softmax(scores, dim=-1)
            out = torch.matmul(weights, v)
            # GQA uses q_dim; MHA uses inner_dim. Pick whichever the layer exposes.
            _out_dim = getattr(attn, 'q_dim', None) or getattr(attn, 'inner_dim', None)
            out = out.transpose(1, 2).contiguous().view(B, T, _out_dim)
            x = x + layer.attn_drop(attn.out_proj(out))

            # FFN
            h = layer.ffn_norm(x)
            gate = layer.activation(layer.ffn_gate(h))
            up = layer.ffn_up(h)
            x = x + layer.ffn_drop(layer.ffn_down(gate * up))

        # Final norm + logits
        x = self.model.final_norm(x)
        logits = self.model.lm_head(x)

        self.seq_len = T
        return logits

    @torch.no_grad()
    def decode_one(self, token_id: int) -> torch.Tensor:
        """Process a single new token using cached K/V, return next logits.

        Args:
            token_id: single token ID
        Returns:
            logits: (vocab_size,) logits for next token
        """
        B = 1
        T_new = 1
        T_total = self.seq_len + 1

        input_ids = torch.tensor([[token_id]], dtype=torch.long, device=self.device)
        x = self.model.token_emb(input_ids)
        x = x * math.sqrt(self.embed_dim)

        for layer_idx, layer in enumerate(self.model.layers):
            h = layer.attn_norm(x)
            attn = layer.attn

            # Compute Q, K, V for the NEW token only
            q = attn.q_proj(h).view(B, T_new, attn.num_heads, attn.head_dim).transpose(1, 2)
            k_new = attn.k_proj(h).view(B, T_new, attn.num_heads, attn.head_dim).transpose(1, 2)
            v_new = attn.v_proj(h).view(B, T_new, attn.num_heads, attn.head_dim).transpose(1, 2)

            # Rotary encoding at position T_total-1
            cos, sin = attn.rope(q, T_total)
            # Only apply rotary for the current position
            cos_pos = cos[:, :, -1:, :]
            sin_pos = sin[:, :, -1:, :]
            q = apply_rotary(q, cos_pos, sin_pos)
            k_new = apply_rotary(k_new, cos_pos, sin_pos)

            # Retrieve cached K, V (dequantized from trits -> torch tensors)
            k_cached, v_cached = self.kv_cache.get(layer_idx, 0, self.seq_len)
            # Ensure tensors from any tier (VRAM/RAM/disk) are on correct device
            k_cached = self._ensure_device(k_cached)
            v_cached = self._ensure_device(v_cached)
            if k_cached.shape[-2] > 0:
                # Add batch dim: (H, T, D) -> (1, H, T, D)
                k_cached_b = k_cached.unsqueeze(0)
                v_cached_b = v_cached.unsqueeze(0)
                # Concat cached + new
                k_full = torch.cat([k_cached_b, k_new], dim=2)
                v_full = torch.cat([v_cached_b, v_new], dim=2)
            else:
                k_full = k_new
                v_full = v_new

            # Cache the new K, V
            self.kv_cache.update(layer_idx, k_new.squeeze(0), v_new.squeeze(0))

            # Attention: Q (1 token) attending to all K/V (T_total tokens)
            scores = torch.matmul(q, k_full.transpose(-2, -1)) / attn.scale
            # No masking needed -- single query token attends to all past
            weights = F.softmax(scores, dim=-1)
            out = torch.matmul(weights, v_full)
            # GQA uses q_dim; MHA uses inner_dim. Pick whichever the layer exposes.
            _out_dim = getattr(attn, 'q_dim', None) or getattr(attn, 'inner_dim', None)
            out = out.transpose(1, 2).contiguous().view(B, T_new, _out_dim)
            x = x + layer.attn_drop(attn.out_proj(out))

            # FFN
            h = layer.ffn_norm(x)
            gate = layer.activation(layer.ffn_gate(h))
            up = layer.ffn_up(h)
            x = x + layer.ffn_drop(layer.ffn_down(gate * up))

        x = self.model.final_norm(x)
        logits = self.model.lm_head(x)

        self.seq_len = T_total

        # Check memory pressure after decode (MemoryManager integration)
        if self.memory_manager:
            self.memory_manager.evict_if_needed()

        return logits[0, 0, :]  # (vocab_size,)

    def memory_stats(self) -> dict:
        """Return memory usage comparison."""
        trit_bytes = self.kv_cache.bytes_used() if hasattr(self.kv_cache, 'bytes_used') else 0
        float32_bytes = self.seq_len * self.num_layers * self.num_heads * self.head_dim * 2 * 4  # K+V, float32
        stats = {
            "cached_tokens": self.seq_len,
            "trit_bytes": trit_bytes,
            "float32_bytes": float32_bytes,
            "compression": round(float32_bytes / max(trit_bytes, 1), 1),
            "savings_mb": round((float32_bytes - trit_bytes) / 1024 / 1024, 1),
            "paged": self.use_paged,
            "max_context": self.max_context,
        }

        # Add tier breakdown for paged cache
        if self.use_paged and hasattr(self.kv_cache, 'tier_report'):
            tier = self.kv_cache.tier_report()
            stats["tier_report"] = tier

        # Add memory manager stats if available
        if self.memory_manager:
            stats["memory_manager"] = self.memory_manager.stats()

        return stats
