# NovaX LLM v1 — Ternary Transformer

A 1B parameter language model with ternary weights `{-1, 0, +1}`, designed around the 3-5-7-13 harmonic constants. Fits on an RTX 4060 8GB GPU at ~198 MB in trit-packed format.

## Architecture

```
Input Text
    |
    v
[Tokenizer] ── BPE with 3-5-7-13 merge schedule ── 32,768 tokens
    |
    v
[TernaryEmbedding] ── 32768 vocab → 2187 dim (3^7 = BLOCK)
    |
    v
[TernaryTransformerBlock x13 (H13)]
    |
    ├── TernaryRMSNorm
    ├── MultiHeadAttention ── 7 heads (H7) x 243 dim (3^5)
    |       └── RotaryPositionalEncoding (base=243)
    ├── Residual connection
    ├── TernaryRMSNorm
    ├── SwiGLU FFN ── 6561 dim (3^8)
    |       └── TernaryGELU activation
    └── Residual connection
    |
    v
[TernaryRMSNorm]
    |
    v
[LM Head] ── 2187 → 32768 (weight-tied with embedding)
    |
    v
Output Logits → Token Sampling (top_k=13, temp=0.7)
```

## 3-5-7-13 Constant Mapping

| Constant | Value | Usage in Architecture |
|----------|-------|-----------------------|
| H3 = 3 | 3 | Ternary weight states {-1, 0, +1}, gradient accumulation steps |
| H5 = 5 | 3^5 = 243 | Head dimension, BPE merge batch size, RoPE base frequency |
| H7 = 7 | 7 | Number of attention heads, max token length |
| H13 = 13 | 13 | Number of transformer layers, special tokens, top-k sampling |
| BLOCK = 3^7 | 2187 | Embedding dimension, max sequence length, block size |
| RE_LAMINAR = 3^3 | 27 | Training batch size |
| RE_TURBULENT = 7^3 | 343 | Warmup steps |
| 3^8 | 6561 | FFN intermediate dimension |

## Ternary Weights

Standard transformers use 16-bit or 32-bit floating point weights. NovaX-LLM uses ternary weights with only three possible values:

- **+1**: Connection active (positive)
- **0**: Connection pruned (inactive)
- **-1**: Connection active (negative)

### How It Works

1. **Training**: Full-precision (fp32) shadow weights are maintained
2. **Forward pass**: Weights quantized to {-1, 0, +1} using adaptive threshold
3. **Backward pass**: Gradients flow through via Straight-Through Estimator (STE)
4. **Threshold**: `delta = 0.7 * mean(|W|)` per tensor — weights within delta become 0
5. **Scaling**: Learned per-channel scale factors compensate for quantization loss

### Storage Format

Trit-packed: 2 bits per weight, 16 weights per u32:
- Encoding: -1 → 0b00, 0 → 0b01, +1 → 0b10
- 1B parameters at 2 bits = ~198 MB model file

## Files

| File | Language | Purpose |
|------|----------|---------|
| `architecture.json` | JSON | Model architecture specification |
| `tokenizer.nova` | NovaLang | BPE tokenizer with ternary IDs |
| `train.py` | Python/PyTorch | Training script (GPU) |
| `inference.nova` | NovaLang | Inference service on port 9800 |
| `vocab.json` | JSON | Token vocabulary (built by tokenizer) |
| `checkpoints/` | Directory | Training checkpoints |
| `training_log.json` | JSON | Loss, perplexity, LR per step |

## How to Train

```bash
# Prerequisites: Python 3.10+, PyTorch 2.0+, CUDA
pip install torch

# 1. Build vocabulary (optional — byte-level fallback works)
# novalang.exe tokenizer.nova

# 2. Start training (10,000 steps)
python train.py

# 3. Resume from checkpoint
python train.py --resume

# 4. Resume from specific checkpoint
python train.py --checkpoint checkpoints/step_005000.pt

# 5. Export trained model to trit-packed format
python train.py --export checkpoints/final.pt
```

Training produces checkpoints every 1,000 steps in `checkpoints/`. Best model auto-saved as `checkpoints/best.pt`.

## How to Run Inference

```bash
# Start the inference service on port 9800
novalang.exe inference.nova

# Generate text
curl -X POST http://127.0.0.1:9800/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain ternary computing", "max_tokens": 100, "temperature": 0.7}'

# Get embedding vector
curl -X POST http://127.0.0.1:9800/llm/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "NovaX ternary AI"}'

# Model info and training status
curl http://127.0.0.1:9800/llm/info

# Health check
curl http://127.0.0.1:9800/health
```

## Training Data

Source: `C:\NovaX\data\llm_training\training_pairs.json` (~2.3 MB)

Distilled knowledge from 115 AI providers, covering:
- NovaX system knowledge and operations
- Ternary computing concepts
- Navier-Stokes flow routing
- 3-5-7-13 harmonic constant applications
- General AI and programming knowledge

## N-S Flow Mapping

| N-S Concept | LLM Analog |
|-------------|------------|
| Velocity field | Token flow through transformer layers |
| Pressure field | Attention score distribution across H7=7 heads |
| Reynolds number | Training stability (laminar=converging, turbulent=diverging) |
| Viscosity | Temperature parameter (controls generation smoothness) |
| Energy cascade | Large-scale pattern learning → fine-grained features |
| Kolmogorov scale | Minimum meaningful token representation |

## Hardware Requirements

- **GPU**: NVIDIA RTX 4060 8GB (or equivalent)
- **VRAM**: ~4 GB for training (fp16 + ternary), ~200 MB for inference
- **RAM**: 8 GB minimum
- **Storage**: ~2 GB for checkpoints
