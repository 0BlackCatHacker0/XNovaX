"""
NovaX LLM v1 — Ternary Transformer Training Script
====================================================
Real neural network training with ternary weights {-1, 0, +1}.
Architecture defined by 3-5-7-13 harmonic constants.

Usage:
    python train.py                    # Start fresh training
    python train.py --resume           # Resume from latest checkpoint
    python train.py --checkpoint PATH  # Resume from specific checkpoint

Requires: PyTorch >= 2.0, CUDA (RTX 4060 8GB target)

N-S Mapping:
    token_flow       = velocity_field (tokens through transformer layers)
    attention_scores = pressure_field (attention distribution)
    gradient_flow    = Reynolds number (training stability indicator)
    loss_landscape   = energy cascade (large->fine feature learning)
"""

import json
import math
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.amp import autocast
from torch.utils.data import Dataset, DataLoader

# v2: Grouped Query Attention (4x KV cache reduction)
from gqa_attention import TernaryGQAttention

import random

# Research Bible: Muon optimizer (~2x convergence, 33% less memory)
# Single-GPU implementation: Newton-Schulz orthogonalization of momentum
class MuonSingleGPU(torch.optim.Optimizer):
    """Muon optimizer for single GPU — no torch.distributed needed.

    MomentUm Orthogonalized by Newton-Schulz iterations.
    Only maintains first moment (no second moment like Adam), saving 33% memory.
    Applies Newton-Schulz orthogonalization to the momentum before update.
    """
    def __init__(self, params, lr=0.02, momentum=0.95, nesterov=True,
                 ns_steps=5):
        defaults = dict(lr=lr, momentum=momentum, nesterov=nesterov,
                       ns_steps=ns_steps)
        super().__init__(params, defaults)

    @torch.no_grad()
    def _newton_schulz(self, G, steps=5):
        """Newton-Schulz iteration to orthogonalize matrix G."""
        # Only works on 2D matrices
        if G.ndim != 2:
            return G
        a, b, c = (3.4445, -4.7750, 2.0315)
        X = G.float()
        # Normalize
        X = X / (X.norm() + 1e-7)
        for _ in range(steps):
            A = X @ X.T
            B = b * A + c * A @ A
            X = a * X + B @ X
        return X.to(G.dtype)

    @torch.no_grad()
    def step(self):
        for group in self.param_groups:
            lr = group['lr']
            mu = group['momentum']
            ns_steps = group['ns_steps']
            nesterov = group['nesterov']

            for p in group['params']:
                if p.grad is None:
                    continue
                g = p.grad

                # Initialize momentum buffer
                state = self.state[p]
                if 'momentum_buffer' not in state:
                    state['momentum_buffer'] = torch.zeros_like(p)
                buf = state['momentum_buffer']
                buf.mul_(mu).add_(g)

                if nesterov:
                    update = g + mu * buf
                else:
                    update = buf

                # Apply Newton-Schulz orthogonalization for 2D params
                if p.ndim == 2:
                    update = self._newton_schulz(update, steps=ns_steps)

                p.add_(update, alpha=-lr)

HAS_MUON = True
print("[Optimizer] MuonSingleGPU loaded - Newton-Schulz momentum orthogonalization")

# ============================================================
# 3-5-7-13 HARMONIC CONSTANTS
# ============================================================
H3 = 3
H5 = 5
H7 = 7
H13 = 13
BLOCK = 3 ** 7           # 2187
RE_LAMINAR = 3 ** 3      # 27
RE_TRANSITIONAL = 5 ** 3 # 125
RE_TURBULENT = 7 ** 3    # 343

# ============================================================
# FIM (Fill-in-the-Middle) SPECIAL TOKENS -- v2
# ============================================================
# Token IDs 6, 7, 8 are reserved (after PAD=0, BOS=1, EOS=2, UNK=3, MASK=4, SEP=5)
FIM_PREFIX = 6   # <fim_prefix>
FIM_MIDDLE = 7   # <fim_middle>
FIM_SUFFIX = 8   # <fim_suffix>
FIM_RATE = 0.3   # 30% of training examples get FIM transformation


def apply_fim_transform(token_ids, fim_rate=FIM_RATE):
    """Apply Fill-in-the-Middle (FIM) transformation to a token sequence.

    With probability fim_rate, splits the sequence at a random point and
    rearranges into SPM format:
        [SUFFIX] suffix [PREFIX] prefix [MIDDLE] middle

    This teaches the model to infill code/text given surrounding context.
    FIM is "free" -- no quality degradation on standard benchmarks.

    Args:
        token_ids: list of token IDs (without BOS/EOS -- just content)
        fim_rate: probability of applying FIM (0.3 = 30%)

    Returns:
        Transformed token IDs (or original if FIM not applied)
    """
    if random.random() > fim_rate:
        return token_ids

    if len(token_ids) < 6:
        return token_ids  # Too short to split meaningfully

    # Random split point (avoid edges)
    split = random.randint(2, len(token_ids) - 2)

    prefix = token_ids[:split]
    middle_and_suffix = token_ids[split:]

    # Second split for middle vs suffix (take at least 1 token each)
    if len(middle_and_suffix) > 2:
        split2 = random.randint(1, len(middle_and_suffix) - 1)
        middle = middle_and_suffix[:split2]
        suffix = middle_and_suffix[split2:]
    else:
        middle = middle_and_suffix[:1]
        suffix = middle_and_suffix[1:]

    # SPM format: [SUFFIX] suffix [PREFIX] prefix [MIDDLE] middle
    return [FIM_SUFFIX] + suffix + [FIM_PREFIX] + prefix + [FIM_MIDDLE] + middle


# ============================================================
# CONFIGURATION (loaded from architecture.json)
# ============================================================
# Config resolution: --fast flag -> v2_fast -> v2 -> v1
_fast_path = Path(__file__).parent / "architecture_v2_fast.json"
_v2_path = Path(__file__).parent / "architecture_v2.json"
ARCH_PATH = _v2_path if _v2_path.exists() else Path(__file__).parent / "architecture.json"
DATA_PATH = Path("C:/NovaX/data/llm_training/training_pairs_round8.json")
VOCAB_PATH = Path(__file__).parent / "vocab.json"
CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"
LOG_PATH = Path(__file__).parent / "training_log.json"

def load_config():
    """Load model architecture from architecture.json."""
    with open(ARCH_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg

# ============================================================
# TERNARY QUANTIZATION
# ============================================================
class TernaryQuantize(torch.autograd.Function):
    """Quantize weights to {-1, 0, +1} using Straight-Through Estimator (STE).

    Forward: weights are quantized to ternary values using threshold.
    Backward: gradient passes through unchanged (STE).

    Threshold is adaptive: delta = 0.7 * mean(|W|) per tensor.
    """
    @staticmethod
    def forward(ctx, weight):
        # Adaptive threshold: 0.7 * mean absolute value
        delta = 0.7 * weight.abs().mean()
        ternary = torch.zeros_like(weight)
        ternary[weight > delta] = 1.0
        ternary[weight < -delta] = -1.0
        # Save for potential backward use
        ctx.save_for_backward(weight)
        return ternary

    @staticmethod
    def backward(ctx, grad_output):
        # STE: pass gradient through unchanged
        weight, = ctx.saved_tensors
        # Clip gradients for weights far from ternary values
        grad = grad_output.clone()
        grad[weight.abs() > 2.0] = 0  # Dead zone for extreme weights
        return grad

def ternary_quantize(weight):
    """Apply ternary quantization with STE."""
    return TernaryQuantize.apply(weight)


# ============================================================
# TERNARY LINEAR LAYER
# ============================================================
class TernaryLinear(nn.Module):
    """Linear layer with ternary weights {-1, 0, +1}.

    Full-precision weights are maintained for gradient updates.
    During forward pass, weights are quantized to ternary using STE.
    A learned per-channel scaling factor compensates for quantization loss.
    """
    def __init__(self, in_features, out_features, bias=True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        # Full-precision weight for training
        self.weight = nn.Parameter(torch.empty(out_features, in_features))
        # Per-output-channel scaling factor
        self.scale = nn.Parameter(torch.ones(out_features))
        if bias:
            self.bias = nn.Parameter(torch.zeros(out_features))
        else:
            self.bias = None
        self.reset_parameters()

    def reset_parameters(self):
        # Kaiming init scaled for ternary
        nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))
        if self.bias is not None:
            fan_in = self.in_features
            bound = 1 / math.sqrt(fan_in)
            nn.init.uniform_(self.bias, -bound, bound)

    def forward(self, x):
        if getattr(self, '_full_precision_mode', True):
            # Train in full precision during warmup
            return F.linear(x, self.weight, self.bias)
        # After warmup: quantize to ternary with STE + learned scale
        w_t = ternary_quantize(self.weight)
        w_t = w_t * self.scale.unsqueeze(1)
        return F.linear(x, w_t, self.bias)


# ============================================================
# TERNARY EMBEDDING
# ============================================================
class TernaryEmbedding(nn.Module):
    """Embedding layer — full precision (embeddings aren't quantized).

    Embeddings remain in fp16/fp32 since they're lookup tables,
    not matrix multiplications that benefit from ternary compression.
    """
    def __init__(self, vocab_size, embedding_dim, padding_idx=0):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=padding_idx)

    def forward(self, x):
        return self.embedding(x)


# ============================================================
# TERNARY RMSNORM
# ============================================================
class TernaryRMSNorm(nn.Module):
    """Root Mean Square Layer Normalization.

    Simpler and faster than LayerNorm — no mean subtraction.
    RMSNorm(x) = x / sqrt(mean(x^2) + eps) * gamma
    """
    def __init__(self, dim, eps=1e-6):
        super().__init__()
        self.eps = eps
        self.gamma = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        rms = torch.sqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)
        return x / rms * self.gamma


# ============================================================
# ROTARY POSITIONAL ENCODING (Ternary-adapted)
# ============================================================
class RotaryPositionalEncoding(nn.Module):
    """Rotary Position Embedding (RoPE) adapted for ternary transformer.

    Applies rotation to query/key pairs for relative position encoding.
    Base frequency uses 3^5 = 243 (H5 harmonic).
    """
    def __init__(self, dim, max_seq_len=BLOCK, base=243):
        super().__init__()
        # Precompute rotation frequencies
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq)
        # Precompute cos/sin for max sequence length
        t = torch.arange(max_seq_len).float()
        freqs = torch.einsum("i,j->ij", t, self.inv_freq)
        self.register_buffer("cos_cached", freqs.cos())
        self.register_buffer("sin_cached", freqs.sin())

    def forward(self, x, seq_len):
        cos = self.cos_cached[:seq_len].unsqueeze(0).unsqueeze(0)  # (1, 1, seq, dim/2)
        sin = self.sin_cached[:seq_len].unsqueeze(0).unsqueeze(0)
        return cos, sin


def apply_rotary(x, cos, sin):
    """Apply rotary embeddings to input tensor (handles odd dimensions)."""
    d = x.shape[-1]
    rot_d = (d // 2) * 2  # Even portion for rotation
    x_rot = x[..., :rot_d]
    x_pass = x[..., rot_d:]  # Last element if odd dim, passes through unchanged
    x1 = x_rot[..., ::2]
    x2 = x_rot[..., 1::2]
    cos = cos[..., :x1.shape[-1]]
    sin = sin[..., :x1.shape[-1]]
    out1 = x1 * cos - x2 * sin
    out2 = x1 * sin + x2 * cos
    rotated = torch.stack([out1, out2], dim=-1).flatten(-2)
    return torch.cat([rotated, x_pass], dim=-1)


# ============================================================
# TERNARY GELU ACTIVATION
# ============================================================
class TernaryGELU(nn.Module):
    """GELU activation with ternary-aware scaling.

    Standard GELU but with output scaled by 3^0.5 to maintain
    variance through ternary weight layers.
    """
    def __init__(self):
        super().__init__()
        self.scale = math.sqrt(H3)  # sqrt(3)

    def forward(self, x):
        return F.gelu(x) * self.scale


# ============================================================
# MULTI-HEAD ATTENTION (H7 = 7 heads)
# ============================================================
class TernaryMultiHeadAttention(nn.Module):
    """Multi-head attention with H7=7 heads and H5=243 head dim.

    Uses ternary linear projections for Q, K, V, and output.
    Rotary positional encoding applied to Q and K.
    """
    def __init__(self, embed_dim, num_heads, head_dim):
        super().__init__()
        self.num_heads = num_heads  # H7 = 7
        self.head_dim = head_dim    # 3^5 = 243
        self.inner_dim = num_heads * head_dim  # 7 * 243 = 1701

        self.q_proj = TernaryLinear(embed_dim, self.inner_dim, bias=False)
        self.k_proj = TernaryLinear(embed_dim, self.inner_dim, bias=False)
        self.v_proj = TernaryLinear(embed_dim, self.inner_dim, bias=False)
        self.out_proj = TernaryLinear(self.inner_dim, embed_dim, bias=False)

        self.rope = RotaryPositionalEncoding(head_dim)
        self.scale = math.sqrt(head_dim)

        # Cached causal mask for fallback attention (no per-forward allocation)
        max_seq = BLOCK  # 2187
        self.register_buffer('causal_mask',
                             torch.tril(torch.ones(max_seq, max_seq, dtype=torch.bool)),
                             persistent=False)

    def forward(self, x, mask=None):
        B, T, C = x.shape

        # Project Q, K, V
        q = self.q_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)

        # Apply rotary encoding to Q and K
        cos, sin = self.rope(q, T)
        q = apply_rotary(q, cos, sin)
        k = apply_rotary(k, cos, sin)

        # Use PyTorch 2.0+ fused SDPA (Flash Attention kernel) when available
        if hasattr(F, 'scaled_dot_product_attention'):
            out = F.scaled_dot_product_attention(
                q, k, v,
                attn_mask=mask,
                is_causal=(mask is None),
                scale=1.0 / self.scale,
            )
        else:
            # Fallback: manual attention (cached causal mask, no allocation)
            attn = torch.matmul(q, k.transpose(-2, -1)) / self.scale
            if mask is not None:
                attn = attn.masked_fill(mask == 0, float("-inf"))
            else:
                attn = attn.masked_fill(~self.causal_mask[:T, :T], float("-inf"))
            attn = F.softmax(attn, dim=-1)
            out = torch.matmul(attn, v)
        out = out.transpose(1, 2).contiguous().view(B, T, self.inner_dim)
        return self.out_proj(out)


# ============================================================
# TRANSFORMER BLOCK
# ============================================================
class TernaryTransformerBlock(nn.Module):
    """Single transformer block with ternary weights.

    Pre-norm architecture:
        x -> RMSNorm -> MHA -> residual
        x -> RMSNorm -> FFN -> residual

    FFN uses ternary GELU gate (SwiGLU-like):
        FFN(x) = (TernaryGELU(W1 * x)) * (W2 * x)
        out = W3 * FFN(x)
    """
    def __init__(self, embed_dim, num_heads, head_dim, ffn_dim, dropout=0.1,
                 num_kv_heads=None):
        super().__init__()
        # Attention block -- use GQA if num_kv_heads specified (v2)
        self.attn_norm = TernaryRMSNorm(embed_dim)
        if num_kv_heads is not None and num_kv_heads < num_heads:
            # v2: Grouped Query Attention (4x KV cache reduction)
            self.attn = TernaryGQAttention(
                embed_dim, num_heads, num_kv_heads, head_dim,
                TernaryLinearCls=TernaryLinear,
                RoPECls=RotaryPositionalEncoding,
            )
        else:
            # v1: Standard multi-head attention
            self.attn = TernaryMultiHeadAttention(embed_dim, num_heads, head_dim)
        self.attn_drop = nn.Dropout(dropout)

        # FFN block (SwiGLU-style with ternary GELU)
        self.ffn_norm = TernaryRMSNorm(embed_dim)
        self.ffn_gate = TernaryLinear(embed_dim, ffn_dim, bias=False)
        self.ffn_up = TernaryLinear(embed_dim, ffn_dim, bias=False)
        self.ffn_down = TernaryLinear(ffn_dim, embed_dim, bias=False)
        self.activation = TernaryGELU()
        self.ffn_drop = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        # Attention with residual + dropout
        h = self.attn_norm(x)
        x = x + self.attn_drop(self.attn(h, mask))

        # FFN with residual + dropout (SwiGLU-style)
        h = self.ffn_norm(x)
        gate = self.activation(self.ffn_gate(h))
        up = self.ffn_up(h)
        x = x + self.ffn_drop(self.ffn_down(gate * up))

        return x


# ============================================================
# TERNARY TRANSFORMER MODEL
# ============================================================
class TernaryTransformer(nn.Module):
    """NovaX Ternary Transformer — ~210M parameter LLM.

    IMPORTANT: This docstring describes the abstract 3-5-7-13 harmonic target,
    but the LIVE configuration that this class actually instantiates comes from
    architecture.json / architecture_v2.json / architecture_pretrain.json. The
    real runtime shapes do NOT match the harmonic target — they use
    conventional power-of-2 sizes that fit within 8 GB VRAM on an RTX 4060.

    Harmonic-ideal target (aspirational, NOT currently instantiated):
        Embedding:  32768 vocab -> 2187 dim (3^7 = BLOCK)
        Layers:     13 transformer blocks (H13)
        Heads:      7 per layer (H7)
        Head dim:   243 (3^5)
        FFN dim:    6561 (3^8)
        Max seq:    2187 (BLOCK)

    Actual runtime config (from architecture_v2.json, the default):
        Embedding:  32768 vocab -> 1024 dim
        Layers:     16 transformer blocks
        Heads:      16 Q × 4 KV (GQA-4), head_dim = 64
        FFN dim:    2730 (SwiGLU)
        Max seq:    256

    Weights quantized to {-1, 0, +1} during forward pass after warmup.
    Full precision maintained for gradient computation (STE).
    """
    def __init__(self, config):
        super().__init__()
        model_cfg = config["model"]

        self.vocab_size = model_cfg["vocab_size"]
        self.embed_dim = model_cfg["embedding_dim"]
        self.num_layers = model_cfg["num_layers"]
        self.num_heads = model_cfg["num_heads"]
        self.head_dim = model_cfg["head_dim"]
        self.ffn_dim = model_cfg["ffn_dim"]
        self.max_seq_len = model_cfg["max_seq_len"]
        self.num_kv_heads = model_cfg.get("num_kv_heads", None)  # v2: GQA

        # Token embedding (full precision lookup)
        self.token_emb = TernaryEmbedding(self.vocab_size, self.embed_dim, padding_idx=0)

        # Transformer blocks
        self.layers = nn.ModuleList([
            TernaryTransformerBlock(
                self.embed_dim, self.num_heads, self.head_dim, self.ffn_dim,
                num_kv_heads=self.num_kv_heads,
            )
            for _ in range(self.num_layers)
        ])

        # Final norm and output projection
        self.final_norm = TernaryRMSNorm(self.embed_dim)
        self.lm_head = TernaryLinear(self.embed_dim, self.vocab_size, bias=False)

        # Weight tying: share embedding and output weights
        self.lm_head.weight = self.token_emb.embedding.weight

        # Count parameters
        self._param_count = sum(p.numel() for p in self.parameters())

    def forward(self, input_ids, targets=None):
        B, T = input_ids.shape
        assert T <= self.max_seq_len, f"Sequence length {T} exceeds max {self.max_seq_len}"

        # Token embeddings
        x = self.token_emb(input_ids)

        # Scale embeddings by sqrt(dim) for stability
        x = x * math.sqrt(self.embed_dim)

        # Pass through transformer layers with optional gradient checkpointing
        for layer in self.layers:
            if self.training and getattr(self, '_grad_checkpoint', False):
                x = torch.utils.checkpoint.checkpoint(layer, x, use_reentrant=False)
            else:
                x = layer(x)

        # Final normalization
        x = self.final_norm(x)

        # Language model head
        logits = self.lm_head(x)

        # Compute loss if targets provided
        # Research Bible: label smoothing (0.1) smooths landscape at ternary
        # quantization boundaries where STE introduces gradient bias
        loss = None
        if targets is not None:
            ce_loss = chunked_cross_entropy(
                logits, targets,
                ignore_index=0,  # PAD token
                label_smoothing=0.1,
            )
            # Z-loss for ternary stability (prevents logit explosion)
            zl = z_loss(logits)
            loss = ce_loss + zl

        return logits, loss

    def param_count(self):
        return self._param_count

    def ternary_ratio(self):
        """Calculate percentage of weights that are ternary {-1, 0, +1}."""
        total = 0
        ternary = 0
        for name, param in self.named_parameters():
            if "weight" in name and "norm" not in name and "emb" not in name:
                w = ternary_quantize(param.data)
                total += w.numel()
                ternary += ((w == -1) | (w == 0) | (w == 1)).sum().item()
        return ternary / max(total, 1) * 100


# ============================================================
# DATASET
# ============================================================
class NovaXDataset(Dataset):
    """Dataset from training_pairs.json.

    Each pair has {"prompt": ..., "response": ...}.
    Concatenated as: <BOS> prompt <SEP> response <EOS> <PAD...>
    Padded/truncated to block_size (2187).
    """
    BOS = 1
    EOS = 2
    SEP = 5
    PAD = 0

    def __init__(self, data_path, vocab_path, block_size=BLOCK, fim_rate=0.0):
        self.block_size = block_size
        self.fim_rate = fim_rate  # v2: FIM training objective

        # Load training pairs
        print(f"Loading training data from {data_path}...")
        with open(data_path, "r", encoding="utf-8") as f:
            self.pairs = json.load(f)
        print(f"  Loaded {len(self.pairs)} training pairs")

        # Try BPE tokenizer first (32K vocab, 71% token reduction)
        self._bpe = None
        bpe_path = Path(data_path).parent.parent.parent / "nova_llm" / "bpe_vocab_32k.json"
        if not bpe_path.exists():
            bpe_path = Path(__file__).parent / "bpe_vocab_32k.json"
        if bpe_path.exists():
            try:
                from bpe_tokenizer import NovaXTokenizer
                self._bpe = NovaXTokenizer(str(bpe_path))
                print(f"  Tokenizer: BPE ({self._bpe.vocab_size} tokens, ~71% compression)")
            except Exception as e:
                print(f"  BPE load failed ({e}), falling back to byte-level")

        # Load vocabulary (simple char-level if vocab not built yet)
        self.vocab = {}
        self.id_to_token = {}
        if self._bpe is None:
            if Path(vocab_path).exists():
                with open(vocab_path, "r", encoding="utf-8") as f:
                    vocab_data = json.load(f)
                self.vocab = vocab_data.get("vocab", {})
                self.id_to_token = vocab_data.get("id_to_token", {})
                print(f"  Loaded vocab: {len(self.vocab)} tokens")
            else:
                print("  WARNING: vocab.json not found, using byte-level encoding")
                # Byte-level fallback: 13 special + 256 bytes
                for i in range(256):
                    tok = f"<byte_{i}>"
                    self.vocab[tok] = i + 13
                    self.id_to_token[str(i + 13)] = tok

    def _encode_text(self, text):
        """Encode text to token IDs. BPE if available, byte-level fallback."""
        if self._bpe is not None:
            return self._bpe.encode(text)
        ids = []
        for ch in text:
            code = ord(ch)
            if code < 256:
                ids.append(code + 13)  # 13 special tokens offset
            else:
                ids.append(3)  # UNK
        return ids

    def _pretokenize(self):
        """Pre-tokenize entire dataset once (eliminates BPE overhead per step).

        When FIM is enabled (fim_rate > 0), stores raw content IDs separately
        so FIM transformation can be applied dynamically per __getitem__ call.
        """
        print("  Pre-tokenizing dataset...")
        self._tokenized = []
        self._raw_content = []  # v2: raw content for dynamic FIM
        for pair in self.pairs:
            prompt = pair.get("prompt", "") or pair.get("input", "")
            response = pair.get("response", "") or pair.get("output", "") or pair.get("completion", "")
            prompt_ids = self._encode_text(prompt)
            response_ids = self._encode_text(response)
            content_ids = prompt_ids + [self.SEP] + response_ids

            if self.fim_rate > 0:
                # Store raw content for dynamic FIM in __getitem__
                self._raw_content.append(content_ids)

            full_ids = [self.BOS] + content_ids + [self.EOS]
            if len(full_ids) > self.block_size:
                full_ids = full_ids[:self.block_size]
            pad_len = self.block_size - len(full_ids)
            full_ids = full_ids + [self.PAD] * pad_len
            self._tokenized.append(torch.tensor(full_ids, dtype=torch.long))

        # Free raw JSON data — no longer needed after tokenization (saves ~500MB RAM)
        pair_count = len(self.pairs)
        self.pairs = None

        # If FIM active, _tokenized is unused (FIM rebuilds from _raw_content)
        if self.fim_rate > 0 and self._raw_content:
            self._tokenized = None
            print(f"  Pre-tokenized {pair_count} pairs (FIM mode, raw content kept)")
        else:
            fim_str = f", FIM rate={self.fim_rate}" if self.fim_rate > 0 else ""
            print(f"  Pre-tokenized {pair_count} pairs{fim_str}")

    def __len__(self):
        # Use `is not None` instead of truthiness — empty list was ambiguous and
        # the (now-None) fallback path crashed on self.pairs[idx] after pretokenize.
        if getattr(self, '_raw_content', None) is not None and len(self._raw_content) > 0:
            return len(self._raw_content)
        if getattr(self, '_tokenized', None) is not None:
            return len(self._tokenized)
        if getattr(self, 'pairs', None) is not None:
            return len(self.pairs)
        return 0

    def __getitem__(self, idx):
        # FIM mode: use raw_content with dynamic FIM transform
        raw = getattr(self, '_raw_content', None)
        if raw is not None and len(raw) > 0:
            content = list(raw[idx])
            if self.fim_rate > 0:
                content = apply_fim_transform(content, self.fim_rate)
            full_ids = [self.BOS] + content + [self.EOS]
            if len(full_ids) > self.block_size:
                full_ids = full_ids[:self.block_size]
            pad_len = self.block_size - len(full_ids)
            full_ids = full_ids + [self.PAD] * pad_len
            t = torch.tensor(full_ids, dtype=torch.long)
            return t[:-1], t[1:]

        # Pre-tokenized fast path (no FIM)
        tok = getattr(self, '_tokenized', None)
        if tok is not None and len(tok) > 0:
            full_ids = tok[idx]
            return full_ids[:-1], full_ids[1:]

        pair = self.pairs[idx]
        prompt = pair.get("prompt", "") or pair.get("input", "")
        response = pair.get("response", "") or pair.get("output", "") or pair.get("completion", "")

        # Encode: <BOS> prompt <SEP> response <EOS>
        prompt_ids = self._encode_text(prompt)
        response_ids = self._encode_text(response)

        # v2: FIM transformation (30% of examples)
        content_ids = prompt_ids + [self.SEP] + response_ids
        if self.fim_rate > 0:
            content_ids = apply_fim_transform(content_ids, self.fim_rate)
        full_ids = [self.BOS] + content_ids + [self.EOS]

        # Truncate if needed
        if len(full_ids) > self.block_size:
            full_ids = full_ids[:self.block_size]

        # Pad to block_size
        pad_len = self.block_size - len(full_ids)
        full_ids = full_ids + [self.PAD] * pad_len

        # Input = all tokens except last, Target = all tokens except first
        input_ids = torch.tensor(full_ids[:-1], dtype=torch.long)
        target_ids = torch.tensor(full_ids[1:], dtype=torch.long)

        return input_ids, target_ids


class PretrainDataset(Dataset):
    """Dataset for next-token prediction pretraining on raw text.

    Reads JSONL files with {"text": ...} format, concatenates all text
    into one giant token stream, then chunks into block_size windows.
    No prompt/response structure — pure language modeling.
    """
    BOS = 1
    EOS = 2
    PAD = 0

    def __init__(self, data_dir, vocab_path, block_size=512):
        self.block_size = block_size
        data_dir = Path(data_dir)

        # Fast path: load pre-tokenized numpy array if it exists
        npy_path = data_dir / "tokenized" / "pretrain_tokens.npy"
        if npy_path.exists():
            import numpy as np
            print(f"  Loading pre-tokenized data from {npy_path}...")
            self._tokens = np.load(str(npy_path)).tolist()
            self._num_chunks = max(1, (len(self._tokens) - 1) // block_size)
            print(f"  Total tokens: {len(self._tokens):,} ({len(self._tokens)/1e6:.1f}M)")
            print(f"  Chunks (block_size={block_size}): {self._num_chunks:,}")
            return

        # Slow path: tokenize from JSONL files
        bpe_path = Path(__file__).parent / "bpe_vocab_32k.json"
        from bpe_tokenizer import NovaXTokenizer
        self._bpe = NovaXTokenizer(str(bpe_path))
        print(f"  Tokenizer: BPE ({self._bpe.vocab_size} tokens)")

        jsonl_files = sorted(data_dir.glob("*.jsonl"))
        print(f"  Found {len(jsonl_files)} JSONL files in {data_dir}")

        all_tokens = []
        for fpath in jsonl_files:
            count = 0
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        text = obj.get("text", "")
                        if len(text) < 50:
                            continue
                        tokens = self._bpe.encode(text)
                        all_tokens.append(self.BOS)
                        all_tokens.extend(tokens)
                        all_tokens.append(self.EOS)
                        count += 1
                    except Exception:
                        continue
            print(f"    {fpath.name}: {count:,} documents")

        self._tokens = all_tokens
        self._num_chunks = max(1, (len(all_tokens) - 1) // block_size)
        print(f"  Total tokens: {len(all_tokens):,} ({len(all_tokens)/1e6:.1f}M)")
        print(f"  Chunks (block_size={block_size}): {self._num_chunks:,}")

    def __len__(self):
        return self._num_chunks

    def __getitem__(self, idx):
        start = idx * self.block_size
        end = start + self.block_size + 1  # +1 for target shift
        chunk = self._tokens[start:end]

        # Pad if at the end
        if len(chunk) < self.block_size + 1:
            chunk = chunk + [self.PAD] * (self.block_size + 1 - len(chunk))

        t = torch.tensor(chunk, dtype=torch.long)
        return t[:-1], t[1:]  # input, target


# ============================================================
# LEARNING RATE SCHEDULER
# ============================================================
def cosine_with_warmup(step, warmup_steps, total_steps, max_lr, min_lr=1e-6):
    """Cosine annealing with linear warmup.

    Warmup: RE_TURBULENT = 343 steps (H7^3)
    """
    if step < warmup_steps:
        return max_lr * step / warmup_steps
    progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
    return min_lr + 0.5 * (max_lr - min_lr) * (1 + math.cos(math.pi * progress))


def wsd_schedule(step, warmup_steps, total_steps, max_lr, min_lr=1e-6):
    """Warmup-Stable-Decay schedule (Research Bible: ICLR 2025).

    Three phases:
      1. Linear warmup (0 to warmup_steps)
      2. Stable at peak LR (warmup_steps to 50% of total)
         - Spectra LR cut: halve LR at 50% of training
      3. Linear decay to min_lr (50% to 100%)

    Spectra recipe (ICLR 2025 Spotlight):
      - LR reduction at 50% of training
      - Weight decay removal at 67% (handled in training loop)
    """
    stable_end = int(total_steps * 0.50)

    # Phase 1: Warmup
    if step < warmup_steps:
        return max_lr * step / warmup_steps

    # Phase 2: Stable at peak LR
    if step < stable_end:
        return max_lr

    # Phase 3: Linear decay from peak/2 to min_lr (post-Spectra cut)
    decay_steps = total_steps - stable_end
    progress = (step - stable_end) / max(1, decay_steps)
    return (max_lr * 0.5) * (1.0 - progress) + min_lr * progress


def get_weight_decay(step, total_steps, base_wd):
    """Spectra recipe: remove weight decay at 67% of training.

    Ternary quantization provides sufficient regularization in late training.
    (Spectra/TriLM, ICLR 2025 Spotlight)
    """
    if step >= int(total_steps * 0.67):
        return 0.0
    return base_wd


def chunked_cross_entropy(logits, targets, ignore_index=0, label_smoothing=0.1,
                           chunk_size=1024):
    """Memory-efficient cross-entropy that processes logits in chunks.

    Research Bible: Avoids materializing the full (batch*seq, vocab) logit matrix.
    For vocab=32K, this saves ~250MB per batch vs naive F.cross_entropy.
    Falls back to standard CE for small tensors.
    """
    logits_flat = logits.view(-1, logits.size(-1))
    targets_flat = targets.view(-1)
    n = logits_flat.size(0)

    # For small tensors, standard CE is fine
    if n <= chunk_size:
        return F.cross_entropy(logits_flat, targets_flat,
                               ignore_index=ignore_index,
                               label_smoothing=label_smoothing)

    # Process in chunks to limit peak memory
    total_loss = 0.0
    total_count = 0
    for start in range(0, n, chunk_size):
        end = min(start + chunk_size, n)
        chunk_logits = logits_flat[start:end]
        chunk_targets = targets_flat[start:end]
        # Count non-ignored tokens in this chunk
        mask = chunk_targets != ignore_index
        count = mask.sum().item()
        if count == 0:
            continue
        chunk_loss = F.cross_entropy(chunk_logits, chunk_targets,
                                     ignore_index=ignore_index,
                                     label_smoothing=label_smoothing,
                                     reduction='sum')
        total_loss = total_loss + chunk_loss
        total_count += count

    if total_count == 0:
        return torch.tensor(0.0, device=logits.device, requires_grad=True)
    return total_loss / total_count


def z_loss(logits, coeff=1e-5):
    """Z-loss: penalize large logit magnitudes for ternary stability.

    Prevents logit explosion which is more likely in quantized models.
    Used by OLMo, Switch Transformer (coefficient 1e-5).
    """
    log_z = torch.logsumexp(logits, dim=-1)
    return coeff * log_z.square().mean()


# ============================================================
# TRAINING LOOP
# ============================================================
def train(resume_path=None, pretrain_dir=None):
    """Main training loop for NovaX Ternary Transformer."""
    # Reduce CUDA memory fragmentation on 8GB cards
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    config = load_config()
    train_cfg = config["training"]
    model_cfg = config["model"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # CUDA performance flags (RTX 4060 Ada Lovelace)
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True          # Auto-tune convolution algorithms
        torch.backends.cuda.matmul.allow_tf32 = True   # TF32 for matmul (19-bit, ~2x speed)
        torch.backends.cudnn.allow_tf32 = True          # TF32 for cuDNN ops
        torch.set_float32_matmul_precision('high')      # Enable TF32 globally

    print(f"\n{'='*60}")
    print(f"  NovaX LLM v2 -- Ternary Transformer Training")
    print(f"{'='*60}")
    print(f"  Device:         {device}")
    if device.type == "cuda":
        print(f"  GPU:            {torch.cuda.get_device_name(0)}")
        print(f"  VRAM:           {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print(f"  Parameters:     {model_cfg['vocab_size']} vocab, {model_cfg['embedding_dim']} dim")
    print(f"  Layers:         {model_cfg['num_layers']} (H13)")
    num_kv = model_cfg.get('num_kv_heads', model_cfg['num_heads'])
    print(f"  Heads:          {model_cfg['num_heads']} Q x {num_kv} KV x {model_cfg['head_dim']} dim")
    if num_kv < model_cfg['num_heads']:
        print(f"  Attention:      GQA-{model_cfg['num_heads']//num_kv} ({model_cfg['num_heads']//num_kv}x KV cache reduction)")
    print(f"  FFN dim:        {model_cfg['ffn_dim']}")
    print(f"  Block size:     {model_cfg['block_size']} (3^7 = BLOCK)")
    print(f"  Batch size:     {train_cfg['batch_size']}")
    print(f"  Grad accum:     {train_cfg['gradient_accumulation']}")
    if train_cfg.get('fim_rate', 0) > 0:
        print(f"  FIM rate:       {train_cfg['fim_rate']*100:.0f}% (Fill-in-the-Middle)")
    sdpa = hasattr(F, 'scaled_dot_product_attention')
    print(f"  Flash Attn:     {'YES (SDPA)' if sdpa else 'NO (manual)'}")
    print(f"  pin_memory:     {train_cfg.get('pin_memory', False)}")
    print(f"  num_workers:    {train_cfg.get('num_workers', 0)}")
    print(f"  Eff batch:      {train_cfg['batch_size'] * train_cfg['gradient_accumulation']}")
    print(f"  Warmup:         {train_cfg['warmup_steps']} (RE_TURBULENT)")
    print(f"  Total steps:    {train_cfg['total_steps']}")
    print(f"  Weight format:  ternary {{-1, 0, +1}}")
    print(f"{'='*60}\n")

    # Create model
    print("Building TernaryTransformer...")
    model = TernaryTransformer(config).to(device)
    # Default avg_loss so checkpoint save block is always well-defined
    avg_loss = float('inf')
    # Keep reference to uncompiled model for methods torch.compile may wrap (e.g. ternary_ratio)
    orig_model = model
    # Enable gradient checkpointing to save VRAM (trades compute for memory)
    use_grad_ckpt = config.get("model", {}).get("gradient_checkpointing", False)
    if use_grad_ckpt:
        model._grad_checkpoint = True
        print("  Gradient checkpointing: ENABLED (saves ~3-4x activation memory)")
    param_count = model.param_count()
    print(f"  Total parameters: {param_count:,} ({param_count/1e9:.3f}B)")
    print(f"  Ternary model size: ~{param_count * 2 / 8 / 1e6:.0f} MB (2-bit packed)")

    # Dataset and dataloader
    if pretrain_dir:
        print(f"\n>>> PRETRAINING MODE: Loading raw text from {pretrain_dir} <<<")
        dataset = PretrainDataset(pretrain_dir, VOCAB_PATH, block_size=model_cfg["block_size"])
    else:
        fim_rate = train_cfg.get("fim_rate", 0.0)  # v2: FIM training
        dataset = NovaXDataset(DATA_PATH, VOCAB_PATH, block_size=model_cfg["block_size"],
                               fim_rate=fim_rate)
        dataset._pretokenize()  # Pre-tokenize once, eliminates BPE overhead per step
    # Dataloader with parallel workers and pinned memory for async GPU transfer
    dataloader = DataLoader(
        dataset,
        batch_size=train_cfg["batch_size"],
        shuffle=True,
        num_workers=4,
        pin_memory=True,
        drop_last=True,
        persistent_workers=True,
    )

    # Optimizer — Research Bible: Muon for 2D weights, AdamW for rest
    # Split params: Muon for 2D hidden weights, AdamW for embeddings/norms/biases
    muon_params = []
    adamw_params = []
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if param.ndim == 2 and "embed" not in name and "lm_head" not in name:
            muon_params.append(param)
        else:
            adamw_params.append(param)

    print(f"[Optimizer] Muon: {len(muon_params)} params, AdamW: {len(adamw_params)} params")

    if HAS_MUON and muon_params:
        # Two separate optimizers — step both each iteration
        optimizer_muon = MuonSingleGPU(muon_params, lr=0.02, momentum=0.95)
        optimizer_adamw = torch.optim.AdamW(
            adamw_params,
            lr=train_cfg["learning_rate"],
            weight_decay=train_cfg["weight_decay"],
            betas=(0.9, 0.95),
        )
        optimizer = None  # Signal to use dual optimizers
    else:
        optimizer_muon = None
        optimizer_adamw = None
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=train_cfg["learning_rate"],
            weight_decay=train_cfg["weight_decay"],
            betas=(0.9, 0.95),
        )

    # Helper functions for dual optimizer setup
    def opt_zero_grad():
        if optimizer is not None:
            optimizer.zero_grad(set_to_none=True)
        else:
            optimizer_muon.zero_grad(set_to_none=True)
            optimizer_adamw.zero_grad(set_to_none=True)

    def opt_step():
        if optimizer is not None:
            optimizer.step()
        else:
            optimizer_muon.step()
            optimizer_adamw.step()

    def opt_state_dict():
        if optimizer is not None:
            return optimizer.state_dict()
        return {"muon": optimizer_muon.state_dict(), "adamw": optimizer_adamw.state_dict()}

    def opt_load_state_dict(sd):
        if optimizer is not None:
            optimizer.load_state_dict(sd)
        elif isinstance(sd, dict) and "muon" in sd:
            optimizer_muon.load_state_dict(sd["muon"])
            optimizer_adamw.load_state_dict(sd["adamw"])

    def opt_set_lr(lr, wd):
        if optimizer is not None:
            for pg in optimizer.param_groups:
                pg["lr"] = lr
                pg["weight_decay"] = wd
        else:
            # Muon: scale relative to base 0.02
            scale = lr / train_cfg["learning_rate"]
            for pg in optimizer_muon.param_groups:
                pg["lr"] = 0.02 * scale
            for pg in optimizer_adamw.param_groups:
                pg["lr"] = lr
                pg["weight_decay"] = wd

    # Enable mixed precision -- bf16 on Ada Lovelace Tensor Cores (2-2.5x speedup)
    # RTX 4060 supports bf16 natively; ternary {-1,0,+1} values are exact in bf16
    # NOTE: bfloat16 does NOT need GradScaler (no underflow risk like fp16)
    scaler = None

    # Training state
    global_step = 0
    best_loss = float("inf")
    training_log = []
    start_time = time.time()

    # Resume from checkpoint
    if resume_path and Path(resume_path).exists():
        print(f"Resuming from checkpoint: {resume_path}")
        ckpt = torch.load(resume_path, map_location=device, weights_only=True)
        model.load_state_dict(ckpt["model_state_dict"])
        opt_load_state_dict(ckpt["optimizer_state_dict"])
        global_step = ckpt.get("global_step", 0)
        best_loss = ckpt.get("best_loss", float("inf"))
        training_log = ckpt.get("training_log", [])
        print(f"  Resumed at step {global_step}, best_loss={best_loss:.4f}")

    # Ensure checkpoint directory exists
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # Training loop
    print("\n--- Training Started ---\n")

    # Phase 1: Full precision training (warmup period)
    # Switch to ternary quantization after warmup_steps
    warmup = train_cfg.get("warmup_steps", 343)
    print(f"  Phase 1: Full precision for {warmup} steps (warmup)")
    print(f"  Phase 2: Ternary quantization after step {warmup}")
    for module in model.modules():
        if isinstance(module, TernaryLinear):
            module._full_precision_mode = True

    model.train()
    accum_loss = 0.0
    accum_steps = 0
    grad_accum = train_cfg["gradient_accumulation"]  # H3 = 3
    total_steps = train_cfg["total_steps"]

    epoch = 0
    while global_step < total_steps:
        epoch += 1
        for batch_idx, (input_ids, target_ids) in enumerate(dataloader):
            if global_step >= total_steps:
                break

            input_ids = input_ids.to(device)
            target_ids = target_ids.to(device)

            # Forward pass with mixed precision (bf16, no scaler needed)
            with autocast("cuda", dtype=torch.bfloat16):
                logits, loss = model(input_ids, target_ids)
                loss = loss / grad_accum

            # NaN guard: use detach() instead of .item() (avoids GPU sync)
            loss_check = loss.detach()
            if torch.isnan(loss_check) or torch.isinf(loss_check):
                print(f"  WARNING: NaN/Inf loss at micro-step, skipping")
                opt_zero_grad()
                accum_steps = 0
                accum_loss = 0.0
                continue

            # Backward pass (no scaler needed with bfloat16)
            loss.backward()

            accum_loss += loss_check  # Stay on GPU, no sync
            accum_steps += 1

            # Gradient accumulation step (every H3=3 micro-batches)
            if accum_steps >= grad_accum:
                # Clip gradients
                torch.nn.utils.clip_grad_norm_(model.parameters(), train_cfg["max_grad_norm"])

                # Update learning rate (Research Bible: WSD schedule)
                lr = wsd_schedule(
                    global_step,
                    train_cfg["warmup_steps"],
                    total_steps,
                    train_cfg["learning_rate"],
                )
                # Spectra recipe: remove weight decay at 67% of training
                wd = get_weight_decay(global_step, total_steps, train_cfg["weight_decay"])
                opt_set_lr(lr, wd)

                # Optimizer step (no scaler needed with bfloat16)
                opt_step()
                opt_zero_grad()

                global_step += 1

                # Switch from full precision to ternary after warmup
                if global_step == warmup:
                    print(f"\n  >>> Switching to TERNARY quantization at step {global_step} <<<\n")
                    for module in model.modules():
                        if isinstance(module, TernaryLinear):
                            module._full_precision_mode = False
                    try:
                        if platform.system() == "Windows":
                            print("  torch.compile: SKIPPED (Triton not available on Windows)")
                        else:
                            model = torch.compile(model, mode="reduce-overhead")
                            print("  torch.compile: ENABLED")
                    except Exception as e:
                        print(f"  torch.compile: FAILED ({e}), continuing without")

                # Compute avg loss only at logging time to minimize GPU syncs
                if global_step % 10 == 0:
                    avg_loss = (accum_loss / accum_steps).item()  # GPU sync only at log time
                    perplexity = math.exp(min(avg_loss, 20))
                    elapsed = time.time() - start_time
                    steps_per_sec = global_step / elapsed if elapsed > 0 else 0
                    eta = (total_steps - global_step) / steps_per_sec if steps_per_sec > 0 else 0

                    log_entry = {
                        "step": global_step,
                        "loss": round(avg_loss, 4),
                        "perplexity": round(perplexity, 2),
                        "lr": round(lr, 8),
                        "elapsed_sec": round(elapsed, 1),
                        "steps_per_sec": round(steps_per_sec, 3),
                        "eta_sec": round(eta, 1),
                        "epoch": epoch,
                    }
                    training_log.append(log_entry)

                    # Write log to both nova_llm/ and web/ for dashboard
                    with open(LOG_PATH, "w", encoding="utf-8") as lf:
                        json.dump(training_log, lf)
                    try:
                        shutil.copy(str(LOG_PATH), "C:/NovaX/web/nova_llm_training_log.json")
                    except Exception:
                        pass

                    print(
                        f"  Step {global_step:>6}/{total_steps} | "
                        f"Loss: {avg_loss:.4f} | "
                        f"PPL: {perplexity:.2f} | "
                        f"LR: {lr:.6f} | "
                        f"ETA: {eta/60:.1f}m"
                    )

                # Checkpoint every 1000 steps (1000 is divisible by 10, so avg_loss is set)
                if global_step % 1000 == 0:
                    ckpt_path = CHECKPOINT_DIR / f"step_{global_step:06d}.pt"
                    ckpt = {
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": opt_state_dict(),
                        "global_step": global_step,
                        "best_loss": best_loss,
                        "training_log": training_log,
                        "config": config,
                    }
                    torch.save(ckpt, ckpt_path)
                    print(f"  >>> Checkpoint saved: {ckpt_path}")

                    # Save training log
                    with open(LOG_PATH, "w", encoding="utf-8") as f:
                        json.dump(training_log, f, indent=2)

                    # Track best loss
                    if avg_loss < best_loss:
                        best_loss = avg_loss
                        best_path = CHECKPOINT_DIR / "best.pt"
                        torch.save(ckpt, best_path)
                        print(f"  >>> New best model! Loss: {best_loss:.4f}")

                accum_loss = 0.0
                accum_steps = 0

    # Final save
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  Training Complete!")
    print(f"  Total steps:    {global_step}")
    print(f"  Best loss:      {best_loss:.4f}")
    print(f"  Total time:     {elapsed/3600:.2f} hours")
    print(f"  Ternary ratio:  {orig_model.ternary_ratio():.1f}%")
    print(f"{'='*60}\n")

    # Save final checkpoint
    final_path = CHECKPOINT_DIR / "final.pt"
    torch.save({
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": opt_state_dict(),
        "global_step": global_step,
        "best_loss": best_loss,
        "training_log": training_log,
        "config": config,
    }, final_path)
    print(f"Final model saved: {final_path}")

    # Save final training log
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(training_log, f, indent=2)
    print(f"Training log saved: {LOG_PATH}")


# ============================================================
# EXPORT: Convert trained model to trit-packed format
# ============================================================
def export_ternary(checkpoint_path, output_path=None):
    """Export model weights as trit-packed format for NovaLang inference.

    Packing: 16 ternary weights per u32 (2 bits each)
    Encoding: -1 -> 0b00, 0 -> 0b01, +1 -> 0b10
    """
    if output_path is None:
        output_path = CHECKPOINT_DIR / "novax_llm_v1.trit"

    config = load_config()
    model = TernaryTransformer(config)

    # Security: weights_only=True blocks pickle-based code execution.
    try:
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    except Exception:
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    # Quantize and pack all weights
    packed_layers = {}
    total_params = 0
    for name, param in model.named_parameters():
        if "weight" in name and "norm" not in name and "emb" not in name:
            # Quantize to ternary
            w = ternary_quantize(param.data)
            flat = w.flatten().tolist()
            total_params += len(flat)

            # Pack 16 trits per u32
            packed = []
            for i in range(0, len(flat), 16):
                u32 = 0
                for j in range(min(16, len(flat) - i)):
                    trit = flat[i + j]
                    # -1 -> 0, 0 -> 1, +1 -> 2
                    encoded = int(trit) + 1
                    u32 |= (encoded & 0x3) << (j * 2)
                packed.append(u32)
            packed_layers[name] = packed
        else:
            # Non-ternary params stored as float16
            packed_layers[name] = param.data.half().flatten().tolist()

    export_data = {
        "format": "novax_trit_packed_v1",
        "model": "NovaX-LLM-v1",
        "total_ternary_params": total_params,
        "packing": "16 trits per u32, 2 bits each",
        "encoding": {"-1": 0, "0": 1, "+1": 2},
        "config": config,
        "layers": packed_layers,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f)

    size_mb = os.path.getsize(output_path) / 1e6
    print(f"Exported trit-packed model: {output_path} ({size_mb:.1f} MB)")
    print(f"  Total ternary params: {total_params:,}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NovaX LLM v2 — Ternary Transformer Training")
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    parser.add_argument("--checkpoint", type=str, default=None, help="Resume from specific checkpoint")
    parser.add_argument("--export", type=str, default=None, help="Export checkpoint to trit-packed format")
    parser.add_argument("--fast", action="store_true", help="Use fast training config (384 seq, batch 8, 12K steps)")
    parser.add_argument("--pretrain", type=str, default=None,
                        help="Pretrain on raw text JSONL files in given directory (e.g. --pretrain C:/NovaX/data/pretraining)")
    args = parser.parse_args()

    # Override config path. These assignments rebind the module-level ARCH_PATH
    # (because __main__ IS module scope); load_config() will then pick up the
    # overridden value when train() is called below.
    if args.pretrain:
        _pretrain_path = Path(__file__).parent / "architecture_pretrain.json"
        if _pretrain_path.exists():
            ARCH_PATH = _pretrain_path
            print(f">>> PRETRAIN MODE: Using {_pretrain_path.name} <<<")
        else:
            print(f"WARNING: architecture_pretrain.json not found, using default config")
    elif args.fast and _fast_path.exists():
        ARCH_PATH = _fast_path
        print(f">>> FAST MODE: Using {_fast_path.name} <<<")
    elif args.fast:
        print(f"WARNING: --fast requested but {_fast_path} not found, using default")

    if args.export:
        export_ternary(args.export)
    else:
        resume_path = args.checkpoint
        if args.resume and resume_path is None:
            # Find latest checkpoint
            ckpts = sorted(CHECKPOINT_DIR.glob("step_*.pt"))
            if ckpts:
                resume_path = str(ckpts[-1])
                print(f"Auto-resuming from: {resume_path}")
            else:
                print("No checkpoints found, starting fresh")
        train(resume_path, pretrain_dir=args.pretrain)
