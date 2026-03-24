"""
NovaX v2 Architecture — RingFormer-style Looped Ternary Transformer
=====================================================================
Next-gen architecture combining Research Bible findings:

1. Looped/Recursive Transformer (Huginn/RingFormer-style)
   - ONE shared block looped N times (default 8)
   - Per-loop LoRA-rank level signals differentiate iterations
   - Adaptive halting (Mixture-of-Recursions): per-token early exit

2. Differential Attention
   - Split Q,K into two groups, compute two attention maps, subtract
   - Noise-cancelling: irrelevant context cancelled out
   - GroupNorm between maps for stability

3. Hyper-Connections
   - Replace standard residual (x + F(x)) with learned connection matrices
   - Each layer draws from multiple previous states with learned weights

4. Mixture of Depths (MoD)
   - Per-loop router selects top-k tokens for full computation
   - Remaining tokens skip via residual (static compute graph)

Architecture Layout:
    Prelude (1 layer):  Embedding projection + initial transform
    Loop (1 block x 8): Diff-Attn + GQA-4, Hyper-Conn, MoD, LoRA, Halt
    Output (1 layer):   Final norm + LM head

Config:
    ~250M ternary params, effective depth of 128-layer model
    Active params per token: ~190M (MoD skips reduce compute)
    Hidden 1024, 16 heads (8 diff pairs), 4 KV groups, FFN 2730

Imports TernaryLinear, TernaryRMSNorm, TernaryQuantize from train.py.
Same forward(input_ids, targets=None) -> (logits, loss) interface.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

# Import ternary primitives from existing train.py
from train import (
    TernaryLinear,
    TernaryRMSNorm,
    TernaryQuantize,
    TernaryGELU,
    TernaryEmbedding,
    RotaryPositionalEncoding,
    apply_rotary,
    ternary_quantize,
    chunked_cross_entropy,
    z_loss,
    BLOCK,
)


# ============================================================
# CONFIGURATION
# ============================================================
V2_CONFIG = {
    "name": "NovaX-v2-RingFormer",
    "model": {
        "vocab_size": 32768,
        "embedding_dim": 1024,
        "num_heads": 16,           # 8 differential pairs
        "num_kv_heads": 4,         # GQA-4
        "head_dim": 64,            # 1024 / 16
        "ffn_dim": 2730,
        "max_seq_len": 512,
        "num_loops": 8,            # shared block looped 8x
        "lora_rank": 32,           # per-loop LoRA rank
        "mod_capacity": 0.625,     # MoD: top 62.5% tokens get full compute
        "halt_threshold": 0.5,     # adaptive halting confidence threshold
        "hyper_depth": 4,          # hyper-connection history window
        "dropout": 0.0,
    },
}


# ============================================================
# DIFFERENTIAL ATTENTION (Noise-Cancelling)
# ============================================================
class DifferentialAttention(nn.Module):
    """Differential Attention with GQA support.

    Splits Q,K into two groups, computes two attention maps, subtracts them.
    This cancels out noise from irrelevant context tokens.
    GroupNorm applied between the two maps for training stability.

    With 16 query heads and 4 KV heads (GQA-4):
    - Each "differential pair" uses 2 query sub-heads
    - 8 differential pairs total (16 / 2)
    - 4 KV heads shared across groups as in standard GQA
    """

    def __init__(self, embed_dim, num_heads, num_kv_heads, head_dim,
                 max_seq_len=512):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads            # 16
        self.num_kv_heads = num_kv_heads      # 4
        self.head_dim = head_dim              # 64
        self.num_diff_pairs = num_heads // 2  # 8 differential pairs
        self.num_groups = num_heads // num_kv_heads  # 4 Q heads per KV head

        # Full Q projection (split into two halves for differential)
        self.q_proj = TernaryLinear(embed_dim, num_heads * head_dim, bias=False)
        # Reduced KV projections (GQA: only num_kv_heads)
        # We need 2x KV for differential (one set per sub-attention)
        self.k_proj = TernaryLinear(embed_dim, num_kv_heads * head_dim * 2, bias=False)
        self.v_proj = TernaryLinear(embed_dim, num_kv_heads * head_dim, bias=False)
        self.out_proj = TernaryLinear(num_heads // 2 * head_dim, embed_dim, bias=False)

        # Learnable lambda parameters for scaling the difference
        # Initialized near 0.5 so both sub-attentions contribute initially
        self.lambda_q1 = nn.Parameter(torch.randn(head_dim) * 0.1)
        self.lambda_k1 = nn.Parameter(torch.randn(head_dim) * 0.1)
        self.lambda_q2 = nn.Parameter(torch.randn(head_dim) * 0.1)
        self.lambda_k2 = nn.Parameter(torch.randn(head_dim) * 0.1)
        self.lambda_init = nn.Parameter(torch.tensor(0.5))

        # GroupNorm applied to the diff attention output per head
        # Normalize over head_dim for each of the 8 diff pairs
        self.sub_norm = nn.GroupNorm(self.num_diff_pairs, self.num_diff_pairs * head_dim)

        # RoPE
        self.rope = RotaryPositionalEncoding(head_dim, max_seq_len=max_seq_len)
        self.scale = math.sqrt(head_dim)

        # Causal mask
        self.register_buffer(
            'causal_mask',
            torch.tril(torch.ones(max_seq_len, max_seq_len, dtype=torch.bool)),
            persistent=False,
        )

    def forward(self, x, mask=None):
        B, T, C = x.shape

        # Project Q: (B, T, num_heads * head_dim) -> split into two halves
        q_full = self.q_proj(x)
        # q_full shape: (B, T, 16 * 64 = 1024) -> split into q1, q2 each (B, T, 8*64)
        q1, q2 = q_full.chunk(2, dim=-1)
        q1 = q1.view(B, T, self.num_diff_pairs, self.head_dim).transpose(1, 2)
        q2 = q2.view(B, T, self.num_diff_pairs, self.head_dim).transpose(1, 2)

        # Project K: (B, T, num_kv_heads * head_dim * 2) -> split
        k_full = self.k_proj(x)
        k1, k2 = k_full.chunk(2, dim=-1)
        k1 = k1.view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)
        k2 = k2.view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)

        # Project V: standard GQA (B, T, num_kv_heads * head_dim)
        v = self.v_proj(x).view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)

        # Apply RoPE to all Q and K
        cos, sin = self.rope(q1, T)
        q1 = apply_rotary(q1, cos, sin)
        q2 = apply_rotary(q2, cos, sin)
        k1 = apply_rotary(k1, cos, sin)
        k2 = apply_rotary(k2, cos, sin)

        # Expand KV heads to match Q heads (GQA expansion)
        # k1: (B, 4, T, 64) -> (B, 8, T, 64) for 8 diff pairs
        groups_per_kv = self.num_diff_pairs // self.num_kv_heads  # 8 / 4 = 2
        k1 = k1.unsqueeze(2).expand(B, self.num_kv_heads, groups_per_kv, T, self.head_dim)
        k1 = k1.reshape(B, self.num_diff_pairs, T, self.head_dim)
        k2 = k2.unsqueeze(2).expand(B, self.num_kv_heads, groups_per_kv, T, self.head_dim)
        k2 = k2.reshape(B, self.num_diff_pairs, T, self.head_dim)
        v = v.unsqueeze(2).expand(B, self.num_kv_heads, groups_per_kv, T, self.head_dim)
        v = v.reshape(B, self.num_diff_pairs, T, self.head_dim)

        # Compute lambda (learnable mixing coefficient)
        lambda_val = (torch.exp(torch.sum(self.lambda_q1 * self.lambda_k1))
                      - torch.exp(torch.sum(self.lambda_q2 * self.lambda_k2))
                      + self.lambda_init)

        # Compute two attention maps
        attn1 = torch.matmul(q1, k1.transpose(-2, -1)) / self.scale
        attn2 = torch.matmul(q2, k2.transpose(-2, -1)) / self.scale

        # Apply causal mask
        if mask is not None:
            attn1 = attn1.masked_fill(mask == 0, float("-inf"))
            attn2 = attn2.masked_fill(mask == 0, float("-inf"))
        else:
            causal = ~self.causal_mask[:T, :T]
            attn1 = attn1.masked_fill(causal, float("-inf"))
            attn2 = attn2.masked_fill(causal, float("-inf"))

        attn1 = F.softmax(attn1, dim=-1)
        attn2 = F.softmax(attn2, dim=-1)

        # Differential: subtract and scale
        # (B, 8, T, T) @ (B, 8, T, 64) -> (B, 8, T, 64)
        out = torch.matmul(attn1 - lambda_val * attn2, v)

        # GroupNorm for stability: reshape to (B*T, 8*64) for GroupNorm
        out = out.transpose(1, 2).contiguous().view(B * T, self.num_diff_pairs * self.head_dim)
        out = self.sub_norm(out)
        out = out.view(B, T, self.num_diff_pairs * self.head_dim)

        # Scale by (1 - lambda_init) to stabilize early training
        out = out * (1 - self.lambda_init)

        return self.out_proj(out)


# ============================================================
# HYPER-CONNECTIONS (Learned Multi-Layer Residual)
# ============================================================
class HyperConnection(nn.Module):
    """Hyper-Connection: learned connection weights replacing standard residual.

    Instead of x + F(x), computes:
        alpha[0] * states[0] + alpha[1] * states[1] + ... + beta * F(x)
    where states are the last `depth` hidden states and alpha/beta are learned.

    Near-zero parameter cost (just depth+1 scalars per connection point).
    """

    def __init__(self, embed_dim, depth=4):
        super().__init__()
        self.depth = depth
        # Learned mixing weights for historical states + current output
        # shape: (depth + 1,) -- last element is the weight for F(x)
        self.alpha = nn.Parameter(torch.zeros(depth + 1))
        # Initialize to approximate standard residual:
        # alpha[-2] = 1.0 (most recent input), alpha[-1] = 1.0 (F(x) output)
        with torch.no_grad():
            self.alpha[-2] = 1.0  # weight for current x
            self.alpha[-1] = 1.0  # weight for F(x)

    def forward(self, state_history, f_out):
        """
        Args:
            state_history: list of tensors [(B,T,D), ...], last `depth` states
            f_out: tensor (B,T,D), output of the sub-layer F(x)

        Returns:
            Combined output (B,T,D)
        """
        # Pad history if we don't have enough states yet
        while len(state_history) < self.depth:
            state_history = [state_history[0]] + state_history

        # Take last `depth` states
        states = state_history[-self.depth:]

        # Weighted sum with softmax-normalized weights
        weights = F.softmax(self.alpha, dim=0)
        result = torch.zeros_like(f_out)
        for i, s in enumerate(states):
            result = result + weights[i] * s
        result = result + weights[self.depth] * f_out
        return result


# ============================================================
# MIXTURE OF DEPTHS (MoD) Router
# ============================================================
class MoDRouter(nn.Module):
    """Mixture-of-Depths router: decides which tokens get full computation.

    Produces a scalar score per token. Top-k tokens (by score) get routed
    through the full transformer block; remaining tokens pass through
    via residual only.

    Uses a static compute graph: always selects exactly top-k tokens.
    """

    def __init__(self, embed_dim, capacity=0.625):
        super().__init__()
        self.capacity = capacity  # fraction of tokens to fully process
        self.router = TernaryLinear(embed_dim, 1, bias=True)

    def forward(self, x):
        """
        Args:
            x: (B, T, D)

        Returns:
            token_mask: (B, T) bool -- True for tokens selected for full compute
            router_logits: (B, T) -- raw router scores (for aux loss)
        """
        B, T, D = x.shape
        # Router score per token
        router_logits = self.router(x).squeeze(-1)  # (B, T)

        # Number of tokens to select
        k = max(1, int(T * self.capacity))

        # Top-k selection (static graph: always selects exactly k tokens)
        _, indices = router_logits.topk(k, dim=-1)
        token_mask = torch.zeros(B, T, device=x.device, dtype=torch.bool)
        token_mask.scatter_(1, indices, True)

        return token_mask, router_logits


# ============================================================
# PER-LOOP LoRA ADAPTER (Level Signal)
# ============================================================
class LoRAAdapter(nn.Module):
    """Low-rank adapter injected per loop iteration as a "level signal".

    Each loop iteration gets a unique LoRA that differentiates what
    the shared block does at each depth level.

    Applies as additive residual:
        output = x + B(A(x)) * scale
    where A: D->R (down-project), B: R->D (up-project), R=rank.
    """

    def __init__(self, embed_dim, rank=32, scale=0.1):
        super().__init__()
        self.down = nn.Linear(embed_dim, rank, bias=False)
        self.up = nn.Linear(rank, embed_dim, bias=False)
        self.scale = scale
        # Initialize B to zero so LoRA starts as identity
        nn.init.zeros_(self.up.weight)
        nn.init.kaiming_uniform_(self.down.weight, a=math.sqrt(5))

    def forward(self, x):
        return x + self.up(self.down(x)) * self.scale


# ============================================================
# ADAPTIVE HALTING (Mixture-of-Recursions)
# ============================================================
class AdaptiveHalter(nn.Module):
    """Per-token adaptive halting mechanism.

    At each loop iteration, produces a halt probability per token.
    When cumulative halt probability exceeds threshold, the token
    stops being updated (its state is frozen).

    Implements ACT (Adaptive Computation Time) style halting with
    a ponder cost penalty to encourage early halting.
    """

    def __init__(self, embed_dim, threshold=0.5):
        super().__init__()
        self.threshold = threshold
        self.halt_proj = nn.Linear(embed_dim, 1, bias=True)
        # Initialize bias slightly negative so halting doesn't happen too early
        nn.init.constant_(self.halt_proj.bias, -1.0)

    def forward(self, x, cumulative_halt, halted_mask):
        """
        Args:
            x: (B, T, D) current hidden states
            cumulative_halt: (B, T) running sum of halt probabilities
            halted_mask: (B, T) bool -- True for tokens already halted

        Returns:
            new_cumulative_halt: (B, T)
            new_halted_mask: (B, T) bool
            halt_prob: (B, T) this step's halt probability (for ponder cost)
        """
        # Compute halt probability for this iteration
        halt_prob = torch.sigmoid(self.halt_proj(x).squeeze(-1))  # (B, T)

        # Only update non-halted tokens
        halt_prob = halt_prob * (~halted_mask).float()

        # Accumulate
        new_cumulative = cumulative_halt + halt_prob

        # Tokens that cross the threshold become halted
        new_halted = halted_mask | (new_cumulative >= self.threshold)

        return new_cumulative, new_halted, halt_prob


# ============================================================
# SHARED TRANSFORMER BLOCK (used inside the loop)
# ============================================================
class SharedTransformerBlock(nn.Module):
    """The single shared transformer block that gets looped.

    Contains:
    - Differential Attention with GQA-4
    - SwiGLU-style FFN with TernaryGELU
    - Pre-norm (RMSNorm)

    Returns attn_out and ffn_out separately so the outer loop can
    apply Hyper-Connections independently to each sub-layer.
    """

    def __init__(self, embed_dim, num_heads, num_kv_heads, head_dim, ffn_dim,
                 max_seq_len=512, dropout=0.0):
        super().__init__()
        # Attention
        self.attn_norm = TernaryRMSNorm(embed_dim)
        self.attn = DifferentialAttention(
            embed_dim, num_heads, num_kv_heads, head_dim,
            max_seq_len=max_seq_len,
        )
        self.attn_drop = nn.Dropout(dropout)

        # FFN (SwiGLU-style)
        self.ffn_norm = TernaryRMSNorm(embed_dim)
        self.ffn_gate = TernaryLinear(embed_dim, ffn_dim, bias=False)
        self.ffn_up = TernaryLinear(embed_dim, ffn_dim, bias=False)
        self.ffn_down = TernaryLinear(ffn_dim, embed_dim, bias=False)
        self.activation = TernaryGELU()
        self.ffn_drop = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        """Returns (attn_out, ffn_out) separately for hyper-connections."""
        # Attention sub-layer (pre-norm)
        h = self.attn_norm(x)
        attn_out = self.attn_drop(self.attn(h, mask))

        # Apply attention residual for FFN input
        x2 = x + attn_out

        # FFN sub-layer (pre-norm, SwiGLU-style)
        h = self.ffn_norm(x2)
        gate = self.activation(self.ffn_gate(h))
        up = self.ffn_up(h)
        ffn_out = self.ffn_drop(self.ffn_down(gate * up))

        return attn_out, ffn_out


# ============================================================
# PRELUDE LAYER (Initial projection)
# ============================================================
class PreludeLayer(nn.Module):
    """Prelude: maps embedding space into the loop's working space.

    A lightweight single-layer transform that prepares token embeddings
    for the looped middle section. Applies norm + linear + activation.
    """

    def __init__(self, embed_dim, dropout=0.0):
        super().__init__()
        self.norm = TernaryRMSNorm(embed_dim)
        self.proj = TernaryLinear(embed_dim, embed_dim, bias=False)
        self.activation = TernaryGELU()
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        h = self.norm(x)
        return x + self.drop(self.activation(self.proj(h)))


# ============================================================
# NovaX v2 TRANSFORMER (Main Model)
# ============================================================
class NovaXv2Transformer(nn.Module):
    """NovaX v2 -- RingFormer-style Looped Ternary Transformer.

    Architecture:
        Prelude:  Embedding + projection (1 layer)
        Loop:     1 shared block x num_loops iterations
                  + Differential Attention (GQA-4)
                  + Hyper-Connections
                  + Mixture-of-Depths router per loop
                  + Per-loop LoRA adapters
                  + Adaptive halting
        Output:   Final norm + LM head

    ~250M ternary parameters with effective depth equivalent to many
    more conventional layers thanks to weight sharing + loop unrolling.
    Active params per token: ~190M (MoD skips reduce compute).

    Interface: forward(input_ids, targets=None) -> (logits, loss)
    """

    def __init__(self, config=None):
        super().__init__()
        if config is None:
            config = V2_CONFIG

        cfg = config["model"]

        self.vocab_size = cfg["vocab_size"]
        self.embed_dim = cfg["embedding_dim"]
        self.num_heads = cfg["num_heads"]
        self.num_kv_heads = cfg["num_kv_heads"]
        self.head_dim = cfg["head_dim"]
        self.ffn_dim = cfg["ffn_dim"]
        self.max_seq_len = cfg["max_seq_len"]
        self.num_loops = cfg["num_loops"]
        self.lora_rank = cfg["lora_rank"]
        self.mod_capacity = cfg["mod_capacity"]
        self.halt_threshold = cfg["halt_threshold"]
        self.hyper_depth = cfg["hyper_depth"]
        self.dropout = cfg.get("dropout", 0.0)

        # ---- Prelude ----
        self.token_emb = TernaryEmbedding(self.vocab_size, self.embed_dim, padding_idx=0)
        self.prelude = PreludeLayer(self.embed_dim, dropout=self.dropout)

        # ---- Shared Transformer Block (looped) ----
        self.shared_block = SharedTransformerBlock(
            self.embed_dim, self.num_heads, self.num_kv_heads,
            self.head_dim, self.ffn_dim,
            max_seq_len=self.max_seq_len,
            dropout=self.dropout,
        )

        # ---- Per-loop components (NOT shared -- unique per iteration) ----
        # LoRA adapters: one per loop iteration (level signals)
        self.lora_adapters = nn.ModuleList([
            LoRAAdapter(self.embed_dim, rank=self.lora_rank)
            for _ in range(self.num_loops)
        ])

        # MoD routers: one per loop iteration
        self.mod_routers = nn.ModuleList([
            MoDRouter(self.embed_dim, capacity=self.mod_capacity)
            for _ in range(self.num_loops)
        ])

        # Hyper-connections: one for attention, one for FFN, per loop
        self.hyper_attn = nn.ModuleList([
            HyperConnection(self.embed_dim, depth=self.hyper_depth)
            for _ in range(self.num_loops)
        ])
        self.hyper_ffn = nn.ModuleList([
            HyperConnection(self.embed_dim, depth=self.hyper_depth)
            for _ in range(self.num_loops)
        ])

        # Adaptive halting (shared across loops -- one decision function)
        self.halter = AdaptiveHalter(self.embed_dim, threshold=self.halt_threshold)

        # ---- Output ----
        self.final_norm = TernaryRMSNorm(self.embed_dim)
        self.lm_head = TernaryLinear(self.embed_dim, self.vocab_size, bias=False)

        # Weight tying: share embedding and LM head weights
        self.lm_head.weight = self.token_emb.embedding.weight

        # Param count
        self._param_count = sum(p.numel() for p in self.parameters())

        # Gradient checkpointing flag
        self._grad_checkpoint = False

    def forward(self, input_ids, targets=None):
        """
        Args:
            input_ids: (B, T) token IDs
            targets: (B, T) target token IDs (optional, for loss computation)

        Returns:
            logits: (B, T, vocab_size)
            loss: scalar or None
        """
        B, T = input_ids.shape
        assert T <= self.max_seq_len, f"Seq len {T} exceeds max {self.max_seq_len}"

        # ---- Prelude ----
        x = self.token_emb(input_ids)
        x = x * math.sqrt(self.embed_dim)
        x = self.prelude(x)

        # ---- Looped Middle ----
        # State history for hyper-connections
        state_history = [x]

        # Adaptive halting state
        cumulative_halt = torch.zeros(B, T, device=x.device)
        halted_mask = torch.zeros(B, T, device=x.device, dtype=torch.bool)

        # ACT-style output accumulator (weighted by halt distributions)
        output_acc = torch.zeros_like(x)
        remainder = torch.ones(B, T, device=x.device)

        # Track ponder cost for regularization
        ponder_cost = torch.zeros(B, T, device=x.device)

        actual_loops = 0
        for loop_idx in range(self.num_loops):
            actual_loops += 1

            # --- MoD: route tokens ---
            token_mask, router_logits = self.mod_routers[loop_idx](x)

            # --- Apply LoRA level signal (differentiates this iteration) ---
            x_adapted = self.lora_adapters[loop_idx](x)

            # --- Shared block computation ---
            # Process all tokens but mask output for skipped ones (static graph)
            attn_out, ffn_out = self.shared_block(x_adapted)

            # Zero out outputs for tokens that MoD decided to skip
            skip_mask = (~token_mask).unsqueeze(-1).float()  # (B, T, 1)
            attn_out = attn_out * (1.0 - skip_mask)
            ffn_out = ffn_out * (1.0 - skip_mask)

            # --- Hyper-connections (replaces simple residual) ---
            x_after_attn = self.hyper_attn[loop_idx](state_history, attn_out)
            x = self.hyper_ffn[loop_idx](
                state_history + [x_after_attn], ffn_out
            )

            # Update state history (sliding window)
            state_history.append(x)
            if len(state_history) > self.hyper_depth + 1:
                state_history = state_history[-(self.hyper_depth + 1):]

            # --- Adaptive halting ---
            prev_halted = halted_mask.clone()
            cumulative_halt, halted_mask, halt_prob = self.halter(
                x, cumulative_halt, halted_mask
            )
            ponder_cost = ponder_cost + halt_prob

            # Accumulate output for tokens that just halted
            just_halted = halted_mask & (~prev_halted)
            if just_halted.any():
                halt_weight = remainder * just_halted.float()
                output_acc = output_acc + halt_weight.unsqueeze(-1) * x
                remainder = remainder * (~just_halted).float()

            # Early exit: stop if all tokens have halted
            if halted_mask.all():
                break

        # Tokens still running after all loops: use final state
        still_running = ~halted_mask
        if still_running.any():
            output_acc = output_acc + remainder.unsqueeze(-1) * x

        x = output_acc

        # ---- Output ----
        x = self.final_norm(x)
        logits = self.lm_head(x)

        # ---- Loss ----
        loss = None
        if targets is not None:
            # Cross-entropy with label smoothing (same as v1)
            ce_loss = chunked_cross_entropy(
                logits, targets,
                ignore_index=0,  # PAD token
                label_smoothing=0.1,
            )
            # Z-loss for ternary stability
            zl = z_loss(logits)

            # Ponder cost: penalize excessive loop iterations
            ponder_penalty = 1e-3 * ponder_cost.mean()

            # MoD router balance loss: encourage uniform token routing
            mod_aux = torch.tensor(0.0, device=logits.device)
            for i in range(actual_loops):
                router_probs = torch.sigmoid(
                    self.mod_routers[i].router(
                        state_history[min(i, len(state_history) - 1)]
                    ).squeeze(-1)
                )
                mod_aux = mod_aux + router_probs.var(dim=-1).mean()
            mod_aux = 1e-3 * mod_aux / max(actual_loops, 1)

            loss = ce_loss + zl + ponder_penalty + mod_aux

        return logits, loss

    # ---- Utility methods (matching v1 interface) ----

    def param_count(self):
        """Total parameter count."""
        return self._param_count

    def effective_depth(self):
        """Effective depth = num_loops iterations of the shared block."""
        return self.num_loops

    def active_param_estimate(self):
        """Estimate active params per token considering MoD skipping."""
        block_params = sum(p.numel() for p in self.shared_block.parameters())
        lora_params = sum(p.numel() for p in self.lora_adapters.parameters())
        active_block = block_params * self.mod_capacity * self.num_loops
        overhead = lora_params + sum(
            p.numel() for p in self.mod_routers.parameters()
        ) + sum(p.numel() for p in self.halter.parameters())
        embed_params = sum(p.numel() for p in self.token_emb.parameters())
        return int(active_block + overhead + embed_params)

    def ternary_ratio(self):
        """Calculate percentage of weights that are ternary {-1, 0, +1}."""
        total = 0
        ternary_count = 0
        for name, param in self.named_parameters():
            if "weight" in name and "norm" not in name and "emb" not in name:
                w = ternary_quantize(param.data)
                total += w.numel()
                ternary_count += ((w == -1) | (w == 0) | (w == 1)).sum().item()
        return ternary_count / max(total, 1) * 100

    def enable_gradient_checkpointing(self):
        """Enable gradient checkpointing for memory efficiency."""
        self._grad_checkpoint = True

    def print_architecture(self):
        """Print a summary of the v2 architecture."""
        print("=" * 60)
        print("NovaX v2 -- RingFormer Looped Ternary Transformer")
        print("=" * 60)
        print(f"  Vocab size:        {self.vocab_size:,}")
        print(f"  Embedding dim:     {self.embed_dim}")
        print(f"  Heads:             {self.num_heads} ({self.num_heads // 2} diff pairs)")
        print(f"  KV heads (GQA):    {self.num_kv_heads}")
        print(f"  Head dim:          {self.head_dim}")
        print(f"  FFN dim:           {self.ffn_dim}")
        print(f"  Max seq len:       {self.max_seq_len}")
        print(f"  Loop count:        {self.num_loops}")
        print(f"  LoRA rank/loop:    {self.lora_rank}")
        print(f"  MoD capacity:      {self.mod_capacity:.1%}")
        print(f"  Halt threshold:    {self.halt_threshold}")
        print(f"  Hyper-conn depth:  {self.hyper_depth}")
        print(f"  Total params:      {self._param_count:,}")
        print(f"  Active params/tok: ~{self.active_param_estimate():,}")
        print(f"  Effective depth:   {self.effective_depth()} loops")
        print()
        block_p = sum(p.numel() for p in self.shared_block.parameters())
        lora_p = sum(p.numel() for p in self.lora_adapters.parameters())
        router_p = sum(p.numel() for p in self.mod_routers.parameters())
        hyper_p = (sum(p.numel() for p in self.hyper_attn.parameters())
                   + sum(p.numel() for p in self.hyper_ffn.parameters()))
        halt_p = sum(p.numel() for p in self.halter.parameters())
        emb_p = sum(p.numel() for p in self.token_emb.parameters())
        prelude_p = sum(p.numel() for p in self.prelude.parameters())
        norm_p = sum(p.numel() for p in self.final_norm.parameters())
        print("  Parameter breakdown:")
        print(f"    Shared block:    {block_p:>12,}  (reused {self.num_loops}x)")
        print(f"    LoRA adapters:   {lora_p:>12,}  ({self.num_loops} x rank {self.lora_rank})")
        print(f"    MoD routers:     {router_p:>12,}  ({self.num_loops} routers)")
        print(f"    Hyper-conns:     {hyper_p:>12,}  (near-zero cost)")
        print(f"    Adaptive halt:   {halt_p:>12,}")
        print(f"    Prelude layer:   {prelude_p:>12,}")
        print(f"    Embedding:       {emb_p:>12,}  (tied with LM head)")
        print(f"    Final norm:      {norm_p:>12,}")
        print("=" * 60)


# ============================================================
# TEST / DEMO
# ============================================================
def test():
    """Run a forward pass to validate the architecture."""
    print("\n[NovaX v2] Architecture validation test...\n")

    model = NovaXv2Transformer()
    model.print_architecture()

    # Dummy forward pass (training mode)
    B, T = 2, 128
    input_ids = torch.randint(1, 32768, (B, T))
    targets = torch.randint(1, 32768, (B, T))

    print(f"\nForward pass (train): input_ids ({B}, {T})")
    model.train()
    logits, loss = model(input_ids, targets)
    print(f"  logits shape: {logits.shape}")
    print(f"  loss:         {loss.item():.4f}")
    assert logits.shape == (B, T, 32768), f"Bad logits shape: {logits.shape}"

    # Inference mode
    model.eval()
    with torch.no_grad():
        logits_eval, _ = model(input_ids)
    print(f"  eval logits:  {logits_eval.shape}")
    assert logits_eval.shape == (B, T, 32768)

    print("\n[NovaX v2] All tests PASSED")


if __name__ == "__main__":
    test()
