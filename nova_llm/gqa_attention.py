"""
Grouped Query Attention (GQA) for NovaX Ternary Transformer v2.

GQA reduces KV cache by sharing K/V heads across groups of Q heads.
Standard MHA: 16 Q heads, 16 KV heads (1:1 ratio)
GQA-4:        16 Q heads,  4 KV heads (4:1 ratio = 4x cache reduction)

References:
- Ainslie et al. 2023 "GQA: Training Generalized Multi-Query Transformers"
- Used in Llama 2/3, Mistral, Gemma

Drop-in replacement for TernaryMultiHeadAttention in train.py.
"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

# NOTE: train.py imports TernaryGQAttention from this module, so a top-level
# `from train import apply_rotary` would be circular. We use a module-level
# cache populated on first use — still avoids the repeated `from train import`
# dict lookup cost on every forward() call.
_apply_rotary = None

def _get_apply_rotary():
    global _apply_rotary
    if _apply_rotary is None:
        from train import apply_rotary as _ar
        _apply_rotary = _ar
    return _apply_rotary


class TernaryGQAttention(nn.Module):
    """Grouped Query Attention with ternary weight projections.

    Args:
        embed_dim: Model embedding dimension (1024)
        num_heads: Number of query heads (16)
        num_kv_heads: Number of KV heads (4 for GQA-4)
        head_dim: Dimension per head (64)
    """
    def __init__(self, embed_dim, num_heads, num_kv_heads, head_dim,
                 TernaryLinearCls=None, RoPECls=None):
        super().__init__()
        self.num_heads = num_heads        # 16 query heads
        self.num_kv_heads = num_kv_heads  # 4 KV heads
        self.head_dim = head_dim          # 64
        self.num_groups = num_heads // num_kv_heads  # 4 queries per KV group

        assert num_heads % num_kv_heads == 0, \
            f"num_heads ({num_heads}) must be divisible by num_kv_heads ({num_kv_heads})"

        self.q_dim = num_heads * head_dim      # 16 * 64 = 1024
        self.kv_dim = num_kv_heads * head_dim  # 4 * 64 = 256

        # Use provided TernaryLinear or fallback to nn.Linear
        Linear = TernaryLinearCls or nn.Linear

        # Q projection: full size (16 heads)
        self.q_proj = Linear(embed_dim, self.q_dim, bias=False)
        # K, V projections: reduced size (4 heads) — this is the GQA savings
        self.k_proj = Linear(embed_dim, self.kv_dim, bias=False)
        self.v_proj = Linear(embed_dim, self.kv_dim, bias=False)
        # Output projection
        self.out_proj = Linear(self.q_dim, embed_dim, bias=False)

        # RoPE
        if RoPECls:
            self.rope = RoPECls(head_dim)
        else:
            self.rope = None

        self.scale = math.sqrt(head_dim)

        # Cached causal mask for fallback attention (no per-forward allocation)
        max_seq = 2187  # BLOCK = 3^7
        self.register_buffer('causal_mask',
                             torch.tril(torch.ones(max_seq, max_seq, dtype=torch.bool)),
                             persistent=False)

    def forward(self, x, mask=None):
        B, T, C = x.shape

        # Project Q (16 heads), K (4 heads), V (4 heads)
        q = self.q_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)

        # Apply RoPE if available
        if self.rope is not None:
            cos, sin = self.rope(q, T)
            # Hot path: use module-level cache directly (skip function call after first load)
            global _apply_rotary
            if _apply_rotary is None:
                _get_apply_rotary()  # populates _apply_rotary
            q = _apply_rotary(q, cos, sin)
            k = _apply_rotary(k, cos, sin)

        # Expand KV heads to match Q heads via zero-copy expand (no memory alloc)
        # k shape: (B, 4, T, 64) -> (B, 16, T, 64)
        B, _, T, D = k.shape
        k = k.unsqueeze(2).expand(B, self.num_kv_heads, self.num_groups, T, D).reshape(B, self.num_heads, T, D)
        v = v.unsqueeze(2).expand(B, self.num_kv_heads, self.num_groups, T, D).reshape(B, self.num_heads, T, D)

        # Use PyTorch 2.0+ fused SDPA (Flash Attention / Memory-Efficient kernel)
        # ~1.3-1.5x faster than manual attention, also more memory-efficient
        if hasattr(F, 'scaled_dot_product_attention') and getattr(self, '_use_sdpa', True):
            out = F.scaled_dot_product_attention(
                q, k, v,
                attn_mask=mask,
                is_causal=(mask is None),  # Auto causal mask when no explicit mask
                scale=1.0 / self.scale,
            )
        else:
            # Fallback: manual attention (for older PyTorch)
            attn = torch.matmul(q, k.transpose(-2, -1)) / self.scale
            if mask is not None:
                attn = attn.masked_fill(mask == 0, float("-inf"))
            else:
                attn = attn.masked_fill(~self.causal_mask[:T, :T], float("-inf"))
            attn = F.softmax(attn, dim=-1)
            out = torch.matmul(attn, v)
        out = out.transpose(1, 2).contiguous().view(B, T, self.q_dim)

        return self.out_proj(out)

    def kv_cache_size(self, seq_len, batch_size=1, dtype_bytes=2):
        """Calculate KV cache size in bytes.

        Standard MHA (16 heads): 2 * 16 * seq_len * 64 * 2 = 4096 * seq_len bytes
        GQA-4 (4 heads):         2 *  4 * seq_len * 64 * 2 = 1024 * seq_len bytes
        4x reduction!
        """
        return 2 * self.num_kv_heads * seq_len * self.head_dim * dtype_bytes * batch_size


def test():
    """Test GQA module with dummy data."""
    print("Testing Grouped Query Attention (GQA-4)...")

    # Config matching NovaX v2
    embed_dim = 1024
    num_heads = 16
    num_kv_heads = 4
    head_dim = 64

    gqa = TernaryGQAttention(embed_dim, num_heads, num_kv_heads, head_dim)

    # Count parameters
    q_params = embed_dim * (num_heads * head_dim)        # 1024 * 1024 = 1M
    kv_params = embed_dim * (num_kv_heads * head_dim) * 2  # 1024 * 256 * 2 = 524K
    out_params = (num_heads * head_dim) * embed_dim       # 1024 * 1024 = 1M

    total = sum(p.numel() for p in gqa.parameters())
    mha_total = 4 * embed_dim * (num_heads * head_dim)  # Standard MHA
    savings = (1 - total / mha_total) * 100

    print(f"  GQA params: {total:,} ({savings:.1f}% fewer than MHA)")
    print(f"  Q proj: {q_params:,} (16 heads)")
    print(f"  KV proj: {kv_params:,} (4 heads, shared)")
    print(f"  Out proj: {out_params:,}")

    # KV cache savings
    seq_len = 512
    gqa_cache = gqa.kv_cache_size(seq_len)
    mha_cache = 2 * num_heads * seq_len * head_dim * 2
    print(f"\n  KV cache @ seq={seq_len}:")
    print(f"    MHA: {mha_cache:,} bytes ({mha_cache/1024:.0f} KB)")
    print(f"    GQA: {gqa_cache:,} bytes ({gqa_cache/1024:.0f} KB)")
    print(f"    Savings: {(1-gqa_cache/mha_cache)*100:.0f}%")

    # Forward pass test
    x = torch.randn(2, 128, embed_dim)
    out = gqa(x)
    print(f"\n  Forward pass: input {x.shape} -> output {out.shape}")
    assert out.shape == x.shape, f"Shape mismatch: {out.shape} != {x.shape}"
    print("  PASSED!")


if __name__ == "__main__":
    test()
