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
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.amp import GradScaler, autocast
from torch.utils.data import Dataset, DataLoader

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
# CONFIGURATION (loaded from architecture.json)
# ============================================================
ARCH_PATH = Path(__file__).parent / "architecture.json"
DATA_PATH = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")
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

        # Scaled dot-product attention
        attn = torch.matmul(q, k.transpose(-2, -1)) / self.scale

        # Causal mask
        if mask is not None:
            attn = attn.masked_fill(mask == 0, float("-inf"))
        else:
            # Auto causal mask
            causal = torch.tril(torch.ones(T, T, device=x.device, dtype=torch.bool))
            attn = attn.masked_fill(~causal, float("-inf"))

        attn = F.softmax(attn, dim=-1)

        # Apply attention to values
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
    def __init__(self, embed_dim, num_heads, head_dim, ffn_dim, dropout=0.1):
        super().__init__()
        # Attention block
        self.attn_norm = TernaryRMSNorm(embed_dim)
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
    """NovaX Ternary Transformer — 1B parameter LLM.

    Architecture (3-5-7-13 harmonic):
        Embedding:  32768 vocab -> 2187 dim (3^7 = BLOCK)
        Layers:     13 transformer blocks (H13)
        Heads:      7 per layer (H7)
        Head dim:   243 (3^5)
        FFN dim:    6561 (3^8)
        Max seq:    2187 (BLOCK)

    Weights quantized to {-1, 0, +1} during forward pass.
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

        # Token embedding (full precision lookup)
        self.token_emb = TernaryEmbedding(self.vocab_size, self.embed_dim, padding_idx=0)

        # Transformer blocks (H13 = 13 layers)
        self.layers = nn.ModuleList([
            TernaryTransformerBlock(
                self.embed_dim, self.num_heads, self.head_dim, self.ffn_dim
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
        loss = None
        if targets is not None:
            loss = F.cross_entropy(
                logits.view(-1, self.vocab_size),
                targets.view(-1),
                ignore_index=0  # PAD token
            )

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

    def __init__(self, data_path, vocab_path, block_size=BLOCK):
        self.block_size = block_size

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
        """Pre-tokenize entire dataset once (eliminates BPE overhead per step)."""
        print("  Pre-tokenizing dataset...")
        self._tokenized = []
        for pair in self.pairs:
            prompt = pair.get("prompt", "") or pair.get("input", "")
            response = pair.get("response", "") or pair.get("output", "") or pair.get("completion", "")
            prompt_ids = self._encode_text(prompt)
            response_ids = self._encode_text(response)
            full_ids = [self.BOS] + prompt_ids + [self.SEP] + response_ids + [self.EOS]
            if len(full_ids) > self.block_size:
                full_ids = full_ids[:self.block_size]
            pad_len = self.block_size - len(full_ids)
            full_ids = full_ids + [self.PAD] * pad_len
            self._tokenized.append(torch.tensor(full_ids, dtype=torch.long))
        print(f"  Pre-tokenized {len(self._tokenized)} pairs")

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        # Use pre-tokenized data if available (fast path)
        if hasattr(self, '_tokenized') and self._tokenized:
            full_ids = self._tokenized[idx]
            return full_ids[:-1], full_ids[1:]

        pair = self.pairs[idx]
        prompt = pair.get("prompt", "") or pair.get("input", "")
        response = pair.get("response", "") or pair.get("output", "") or pair.get("completion", "")

        # Encode: <BOS> prompt <SEP> response <EOS>
        prompt_ids = self._encode_text(prompt)
        response_ids = self._encode_text(response)
        full_ids = [self.BOS] + prompt_ids + [self.SEP] + response_ids + [self.EOS]

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


# ============================================================
# TRAINING LOOP
# ============================================================
def train(resume_path=None):
    """Main training loop for NovaX Ternary Transformer."""
    config = load_config()
    train_cfg = config["training"]
    model_cfg = config["model"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n{'='*60}")
    print(f"  NovaX LLM v1 — Ternary Transformer Training")
    print(f"{'='*60}")
    print(f"  Device:         {device}")
    if device.type == "cuda":
        print(f"  GPU:            {torch.cuda.get_device_name(0)}")
        print(f"  VRAM:           {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print(f"  Parameters:     {model_cfg['vocab_size']} vocab, {model_cfg['embedding_dim']} dim")
    print(f"  Layers:         {model_cfg['num_layers']} (H13)")
    print(f"  Heads:          {model_cfg['num_heads']} (H7) x {model_cfg['head_dim']} (3^5)")
    print(f"  FFN dim:        {model_cfg['ffn_dim']} (3^8)")
    print(f"  Block size:     {model_cfg['block_size']} (3^7 = BLOCK)")
    print(f"  Batch size:     {train_cfg['batch_size']} (RE_LAMINAR)")
    print(f"  Grad accum:     {train_cfg['gradient_accumulation']} (H3)")
    print(f"  Warmup:         {train_cfg['warmup_steps']} (RE_TURBULENT)")
    print(f"  Total steps:    {train_cfg['total_steps']}")
    print(f"  Weight format:  ternary {{-1, 0, +1}}")
    print(f"{'='*60}\n")

    # Create model
    print("Building TernaryTransformer...")
    model = TernaryTransformer(config).to(device)
    # Enable gradient checkpointing to save VRAM (trades compute for memory)
    use_grad_ckpt = config.get("model", {}).get("gradient_checkpointing", False)
    if use_grad_ckpt:
        model._grad_checkpoint = True
        print("  Gradient checkpointing: ENABLED (saves ~3-4x activation memory)")
    param_count = model.param_count()
    print(f"  Total parameters: {param_count:,} ({param_count/1e9:.3f}B)")
    print(f"  Ternary model size: ~{param_count * 2 / 8 / 1e6:.0f} MB (2-bit packed)")

    # Dataset and dataloader
    dataset = NovaXDataset(DATA_PATH, VOCAB_PATH, block_size=model_cfg["block_size"])
    dataset._pretokenize()  # Pre-tokenize once, eliminates BPE overhead per step
    dataloader = DataLoader(
        dataset,
        batch_size=train_cfg["batch_size"],
        shuffle=True,
        num_workers=0,
        pin_memory=False,
        drop_last=True,
    )

    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=train_cfg["learning_rate"],
        weight_decay=train_cfg["weight_decay"],
        betas=(0.9, 0.95),  # Slightly lower beta2 for ternary stability
    )

    # Enable mixed precision — bf16 on Ada Lovelace Tensor Cores (2-2.5x speedup)
    # RTX 4060 supports bf16 natively; ternary {-1,0,+1} values are exact in bf16
    from torch.amp import GradScaler, autocast
    scaler = GradScaler("cuda")

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
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        global_step = ckpt.get("global_step", 0)
        best_loss = ckpt.get("best_loss", float("inf"))
        training_log = ckpt.get("training_log", [])
        if scaler and "scaler_state_dict" in ckpt:
            scaler.load_state_dict(ckpt["scaler_state_dict"])
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

            # Forward pass with mixed precision
            if scaler:
                with autocast("cuda", dtype=torch.bfloat16):
                    logits, loss = model(input_ids, target_ids)
                    loss = loss / grad_accum
            else:
                logits, loss = model(input_ids, target_ids)
                loss = loss / grad_accum

            # NaN guard: check BEFORE backward to prevent gradient poisoning
            loss_val = loss.item()
            if math.isnan(loss_val) or math.isinf(loss_val):
                print(f"  WARNING: NaN/Inf loss at micro-step, skipping")
                optimizer.zero_grad()
                accum_steps = 0
                accum_loss = 0.0
                continue

            # Backward pass (only if loss is clean)
            if scaler:
                scaler.scale(loss).backward()
            else:
                loss.backward()

            accum_loss += loss_val
            accum_steps += 1

            # Gradient accumulation step (every H3=3 micro-batches)
            if accum_steps >= grad_accum:
                # Clip gradients
                if scaler:
                    scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), train_cfg["max_grad_norm"])

                # Update learning rate
                lr = cosine_with_warmup(
                    global_step,
                    train_cfg["warmup_steps"],
                    total_steps,
                    train_cfg["learning_rate"],
                )
                for pg in optimizer.param_groups:
                    pg["lr"] = lr

                # Optimizer step
                if scaler:
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    optimizer.step()
                optimizer.zero_grad()

                global_step += 1

                # Switch from full precision to ternary after warmup
                if global_step == warmup:
                    print(f"\n  >>> Switching to TERNARY quantization at step {global_step} <<<\n")
                    for module in model.modules():
                        if isinstance(module, TernaryLinear):
                            module._full_precision_mode = False
                    # Skip torch.compile on Windows (Triton not supported)
                    import platform
                    if platform.system() != "Windows":
                        try:
                            model = torch.compile(model, mode="reduce-overhead")
                            print("  >>> torch.compile enabled (reduce-overhead mode) <<<")
                        except Exception as e:
                            print(f"  >>> torch.compile failed ({e}), continuing without <<<")
                    else:
                        print("  >>> Skipping torch.compile (Windows/no Triton) <<<")

                avg_loss = accum_loss / accum_steps  # True average across micro-steps
                perplexity = math.exp(min(avg_loss, 20))  # Cap to avoid overflow

                # Log every 10 steps
                if global_step % 10 == 0:
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

                # Checkpoint every 1000 steps
                if global_step % 1000 == 0:
                    ckpt_path = CHECKPOINT_DIR / f"step_{global_step:06d}.pt"
                    ckpt = {
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "global_step": global_step,
                        "best_loss": best_loss,
                        "training_log": training_log,
                        "config": config,
                    }
                    if scaler:
                        ckpt["scaler_state_dict"] = scaler.state_dict()
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
    print(f"  Ternary ratio:  {model.ternary_ratio():.1f}%")
    print(f"{'='*60}\n")

    # Save final checkpoint
    final_path = CHECKPOINT_DIR / "final.pt"
    torch.save({
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
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
    parser = argparse.ArgumentParser(description="NovaX LLM v1 — Ternary Transformer Training")
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    parser.add_argument("--checkpoint", type=str, default=None, help="Resume from specific checkpoint")
    parser.add_argument("--export", type=str, default=None, help="Export checkpoint to trit-packed format")
    args = parser.parse_args()

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
        train(resume_path)
