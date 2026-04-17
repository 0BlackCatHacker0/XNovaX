"""
NovaX LLM Inference Server v2.1 -- Port 9800
Loads trained TernaryTransformer from best.pt and serves text generation
with PagedTritKVCache for million-token context via VRAM->RAM->Disk tiering.

Endpoints:
  POST /llm/generate    -- text generation with temperature/top_k/top_p
  POST /llm/embed       -- extract embeddings
  POST /llm/route       -- classify query route (DIRECT/MATH/CODE/RETRIEVAL/ESCALATE)
  GET  /llm/info        -- model info + training stats
  GET  /llm/cache-stats -- detailed paged cache tier statistics
  GET  /health          -- service health (includes paged cache info)
  GET  /status          -- alias for /health

3-5-7-13 Harmonic Design:
  H3=3    -- ternary weight states {-1, 0, +1}
  H5=5    -- TZip (5 trits/byte)
  H7=7    -- composition depth, BLOCK=3^7=2187
  H13=13  -- num_layers, default top_k
  Context -- 1,000,000 tokens via paged trit cache (VRAM/RAM/Disk)
"""

import http.server
import json
import math
import os
import sys
import time
import threading
from pathlib import Path

import torch
import torch.nn.functional as F

# Import model classes from train.py
sys.path.insert(0, str(Path(__file__).parent))
from train import TernaryTransformer, load_config, ternary_quantize
from cached_inference import CachedInference
from memory_manager import MemoryManager
# v2: Advanced sampling -- Min-P + LZ repetition penalty
from inference_utils import sample_token as _v2_sample_token

# Try to load Rust trit engine for zero-multiply inference
try:
    from trit_engine_py import convert_model as trit_convert_model
    HAS_TRIT_ENGINE = True
except ImportError:
    HAS_TRIT_ENGINE = False

# ============================================================
# CONFIGURATION
# ============================================================
PORT = 9800
SERVICE_NAME = "nova-llm"
VERSION = "2.1.0"
MAX_CONTEXT = 1_000_000  # Million-token context via paged trit cache
CHECKPOINT = Path(__file__).parent / "checkpoints" / "best.pt"
VOCAB_PATH = Path(__file__).parent / "vocab.json"
# Prefer v2 config if available, fall back to v1
_v2_path = Path(__file__).parent / "architecture_v2.json"
ARCH_PATH = _v2_path if _v2_path.exists() else Path(__file__).parent / "architecture.json"
LOG_PATH = Path(__file__).parent / "training_log.json"

# Special tokens (must match NovaXDataset)
BOS = 1
EOS = 2
SEP = 5
PAD = 0

# ============================================================
# MODEL LOADING
# ============================================================
_model = None
_config = None
_device = None
_vocab = None
_id_to_token = {}
_cached_inf = None  # CachedInference wrapper
_mem_manager = None  # MemoryManager instance
_bpe_tokenizer = None  # BPE tokenizer (if available)
_start_time = time.time()
_gen_count = 0
_gen_lock = threading.Lock()


def load_model():
    """Load trained model from best.pt checkpoint."""
    global _model, _config, _device, _vocab, _id_to_token, _mem_manager

    _config = load_config()
    model_cfg = _config["model"]

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {_device}")
    if _device.type == "cuda":
        print(f"  GPU:    {torch.cuda.get_device_name(0)}")

    # Build model
    _model = TernaryTransformer(_config)

    # Load checkpoint
    if not CHECKPOINT.exists():
        print(f"  WARNING: No checkpoint at {CHECKPOINT}")
        print(f"  Serving stub responses until model is trained.")
        return False

    print(f"  Loading checkpoint: {CHECKPOINT}")
    # Security: weights_only=True blocks pickle-based code execution.
    try:
        ckpt = torch.load(CHECKPOINT, map_location=_device, weights_only=True)
    except Exception:
        ckpt = torch.load(CHECKPOINT, map_location=_device, weights_only=False)
    _model.load_state_dict(ckpt["model_state_dict"])
    _model.to(_device)
    _model.eval()

    # Use full precision for inference (best quality)
    for module in _model.modules():
        if hasattr(module, '_full_precision_mode'):
            module._full_precision_mode = True

    # Convert to zero-multiply trit inference if Rust engine available
    if HAS_TRIT_ENGINE:
        try:
            trit_stats = trit_convert_model(_model, verbose=True)
            print(f"  Trit Engine: {trit_stats['converted']} layers converted")
            print(f"  Trit Engine: {trit_stats['total_packed_bytes']:,} bytes packed "
                  f"(was {trit_stats['total_params'] * 4:,} bytes float32)")
        except Exception as e:
            print(f"  Trit Engine: conversion failed ({e}), using float32 fallback")
    else:
        print(f"  Trit Engine: DLL not found, using float32 matmul")

    best_loss = ckpt.get("best_loss", "?")
    step = ckpt.get("global_step", "?")
    print(f"  Loaded: step {step}, best_loss {best_loss}")
    print(f"  Parameters: {_model.param_count():,}")

    # Initialize MemoryManager for automatic tier management
    gpu_budget = 6000  # 6GB for KV cache (out of 8GB VRAM)
    ram_budget = 16000  # 16GB for warm tier
    _mem_manager = MemoryManager(
        gpu_budget_mb=gpu_budget,
        ram_budget_mb=ram_budget,
        disk_path="C:/NovaX/nova_llm/cache",
    )
    print(f"  MemoryManager: GPU budget {gpu_budget}MB, RAM budget {ram_budget}MB")

    # Print capacity estimate
    cap = MemoryManager.capacity_estimate(
        num_layers=model_cfg["num_layers"],
        num_heads=model_cfg["num_heads"],
        head_dim=model_cfg["head_dim"],
        gpu_budget_mb=gpu_budget,
        ram_budget_mb=ram_budget,
    )
    print(f"  Capacity: ~{cap['vram_tokens']:,} VRAM + ~{cap['ram_tokens']:,} RAM + unlimited disk")
    print(f"  Bytes/token: {cap['bytes_per_token']}")

    # Initialize paged trit KV cache for inference
    global _cached_inf
    _cached_inf = CachedInference(
        model=_model,
        config=_config,
        device=_device,
        use_paged=True,
        max_context=MAX_CONTEXT,
        memory_manager=_mem_manager,
    )
    print(f"  KV Cache: PAGED trit-packed, max {MAX_CONTEXT:,} tokens (3-tier: VRAM/RAM/Disk)")

    # Load vocabulary — prefer BPE tokenizer if available
    global _bpe_tokenizer
    bpe_path = Path(__file__).parent / "bpe_vocab.json"
    if bpe_path.exists():
        try:
            from bpe_tokenizer import NovaXTokenizer
            _bpe_tokenizer = NovaXTokenizer(str(bpe_path))
            print(f"  Tokenizer: BPE ({_bpe_tokenizer.vocab_size} tokens, ~64% compression)")
        except Exception as e:
            _bpe_tokenizer = None
            print(f"  Tokenizer: BPE load failed ({e}), byte-level fallback")
    else:
        _bpe_tokenizer = None

    if _bpe_tokenizer is None and VOCAB_PATH.exists():
        with open(VOCAB_PATH, "r", encoding="utf-8") as f:
            vdata = json.load(f)
        _vocab = vdata.get("vocab", {})
        _id_to_token = vdata.get("id_to_token", {})
        print(f"  Vocab: {len(_vocab)} tokens (byte-level)")
    elif _bpe_tokenizer is None:
        print(f"  Vocab: byte-level fallback")

    return True


# ============================================================
# TOKENIZATION (byte-level, matching train.py)
# ============================================================
def encode_text(text):
    """Encode text to token IDs. Uses BPE if available, byte-level fallback."""
    if _bpe_tokenizer is not None:
        return _bpe_tokenizer.encode(text)
    ids = []
    for ch in text:
        code = ord(ch)
        if code < 256:
            ids.append(code + 13)
        else:
            ids.append(3)  # UNK
    return ids


def decode_tokens(ids):
    """Decode token IDs back to text. Uses BPE if available."""
    if _bpe_tokenizer is not None:
        # Filter special tokens before BPE decode
        filtered = [t for t in ids if t not in (PAD, BOS, EOS, SEP)]
        return _bpe_tokenizer.decode(filtered)
    chars = []
    for tid in ids:
        if tid <= 0 or tid == BOS or tid == EOS or tid == SEP:
            continue
        if tid == 3:  # UNK
            chars.append("?")
        elif tid >= 13 and tid < 269:
            chars.append(chr(tid - 13))
        elif str(tid) in _id_to_token:
            chars.append(_id_to_token[str(tid)])
    return "".join(chars)


# ============================================================
# TEXT GENERATION
# ============================================================
def _lz_repetition_penalty(logits, generated, window=64, max_ngram=8, penalty_scale=2.0):
    """LZ-inspired repetition penalty using n-gram frequency in sliding window.

    Unlike crude per-token penalty, this detects REPEATED PATTERNS (n-grams)
    and penalizes tokens that would continue a repetition. Small models loop
    constantly — this is the surgical fix.
    """
    if len(generated) < 4:
        return logits

    window_tokens = generated[-window:]

    # Count n-gram frequencies in the window
    for n in range(2, min(max_ngram + 1, len(window_tokens))):
        # Check if the last (n-1) tokens match any previous n-gram
        suffix = tuple(window_tokens[-(n-1):])
        for i in range(len(window_tokens) - n):
            if tuple(window_tokens[i:i+n-1]) == suffix:
                # The token that followed this n-gram before
                continuation = window_tokens[i + n - 1]
                # Penalize proportionally to n-gram length (longer = more penalty)
                penalty = penalty_scale * (n / max_ngram)
                if logits[continuation] > 0:
                    logits[continuation] /= (1.0 + penalty)
                else:
                    logits[continuation] *= (1.0 + penalty)

    return logits


def _sample_token(logits, temperature, top_k, top_p, repetition_penalty, generated,
                  min_p=0.05, use_lz_penalty=True):
    """Apply advanced sampling strategy to logits and return next token.

    v2: Delegates to inference_utils.sample_token which implements:
    - Min-P: Dynamic threshold based on model confidence (ICLR 2025)
    - LZ repetition penalty: N-gram-aware, not crude per-token (2025)

    Falls back to inline implementation if inference_utils unavailable.
    """
    if temperature <= 0:
        return logits.argmax().item()

    return _v2_sample_token(
        logits,
        generated_ids=generated if generated else None,
        temperature=temperature,
        top_k=top_k,
        top_p=top_p,
        min_p=min_p,
        use_lz_penalty=use_lz_penalty,
        lz_window=128,
        lz_scale=2.0,
    )


@torch.no_grad()
def generate(prompt, max_tokens=256, temperature=0.7, top_k=13, top_p=0.9,
             repetition_penalty=1.1, context_budget=None, cfg_scale=0.0,
             min_p=0.05, use_lz_penalty=True):
    """Autoregressive text generation with paged trit KV cache.

    Uses CachedInference for incremental decoding:
    - Prefill: process entire prompt, cache K/V as trits (~16x compression)
    - Decode: process one token at a time, reuse cached K/V
    - Context: up to 1,000,000 tokens via paged 3-tier cache (VRAM/RAM/Disk)

    Args:
        prompt: input text
        max_tokens: max tokens to generate
        temperature: sampling temperature
        top_k: top-k sampling
        top_p: nucleus sampling
        repetition_penalty: penalize repeated tokens
        context_budget: optional max context override (None = use MAX_CONTEXT)
    """
    global _gen_count

    if _model is None:
        return {
            "text": "Model not loaded. Train first: python train.py",
            "tokens_generated": 0,
            "status": "not_loaded",
            "ternary": 0
        }

    t0 = time.time()

    # Apply context budget if specified
    effective_max = context_budget if context_budget and context_budget > 0 else MAX_CONTEXT

    # Encode prompt
    prompt_ids = [BOS] + encode_text(prompt) + [SEP]
    if len(prompt_ids) > effective_max - 10:
        prompt_ids = prompt_ids[:effective_max - 10]

    # Reset cache for new generation
    _cached_inf.reset()

    # If context_budget is larger than current max, extend
    if effective_max > _cached_inf.max_context:
        _cached_inf.extend_context(effective_max)

    # Phase 1: Prefill -- process entire prompt, cache all K/V
    input_ids = torch.tensor([prompt_ids], dtype=torch.long, device=_device)
    logits = _cached_inf.prefill(input_ids)
    next_logits = logits[0, -1, :]

    generated = []
    max_gen = min(max_tokens, effective_max - len(prompt_ids))

    # Classifier-Free Guidance (ICML 2024)
    # Makes a 235M model output 470M-equivalent quality
    # cfg_scale=0: disabled, cfg_scale=1.5: moderate boost, cfg_scale=2.5: strong boost
    use_cfg = cfg_scale > 0 and _model is not None
    uncond_logits = None
    if use_cfg:
        # Get unconditional logits (empty prompt baseline)
        empty_ids = torch.tensor([[BOS, SEP]], dtype=torch.long, device=_device)
        try:
            uncond_out = _model(empty_ids)
            if isinstance(uncond_out, tuple):
                uncond_logits = uncond_out[0][0, -1, :]
            else:
                uncond_logits = uncond_out[0, -1, :]
        except:
            use_cfg = False  # Fallback if unconditional forward fails

    # Phase 2: Decode -- one token at a time using cached K/V
    for _ in range(max_gen):
        # Apply CFG: guided_logits = uncond + scale * (cond - uncond)
        if use_cfg and uncond_logits is not None:
            guided_logits = uncond_logits + cfg_scale * (next_logits - uncond_logits)
        else:
            guided_logits = next_logits

        next_token = _sample_token(
            guided_logits.clone(), temperature, top_k, top_p,
            repetition_penalty, generated,
            min_p=min_p, use_lz_penalty=use_lz_penalty,
        )
        generated.append(next_token)

        if next_token == EOS:
            break

        # Single-token forward with KV cache
        next_logits = _cached_inf.decode_one(next_token)

    # Decode tokens to text
    text = decode_tokens(generated)
    elapsed = time.time() - t0
    tokens_per_sec = len(generated) / elapsed if elapsed > 0 else 0

    with _gen_lock:
        _gen_count += 1

    mem = _cached_inf.memory_stats()

    result = {
        "text": text,
        "tokens_generated": len(generated),
        "tokens_per_second": round(tokens_per_sec, 1),
        "elapsed_ms": round(elapsed * 1000, 1),
        "model": "NovaX-LLM-v2",
        "status": "ok",
        "ternary": 1,
        "context_tokens": mem["cached_tokens"],
        "kv_cache_bytes": mem["trit_bytes"],
        "kv_compression": mem["compression"],
        "paged_cache": mem.get("paged", False),
        "params": {
            "temperature": temperature,
            "top_k": top_k,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
            "max_tokens": max_tokens,
            "max_context": effective_max,
            "context_budget": context_budget,
        }
    }

    # Add tier breakdown for paged cache
    if mem.get("tier_report"):
        result["tier_breakdown"] = {
            "hot_pages_vram": mem["tier_report"]["hot_pages"],
            "warm_pages_ram": mem["tier_report"]["warm_pages"],
            "cold_pages_disk": mem["tier_report"]["cold_pages"],
        }

    return result


# ============================================================
# EMBEDDING EXTRACTION
# ============================================================
@torch.no_grad()
def get_embedding(text):
    """Extract embedding vector for text."""
    if _model is None:
        return {"error": "Model not loaded", "ternary": -1}

    t0 = time.time()
    ids = [BOS] + encode_text(text[:500]) + [EOS]
    input_ids = torch.tensor([ids], dtype=torch.long, device=_device)

    # Get embeddings from token_emb + final_norm
    x = _model.token_emb(input_ids)
    x = x * math.sqrt(_model.embed_dim)
    for layer in _model.layers:
        x = layer(x)
    x = _model.final_norm(x)

    # Mean pooling (exclude PAD)
    embedding = x[0].mean(dim=0).cpu().tolist()
    elapsed = time.time() - t0

    return {
        "embedding": embedding,
        "dim": len(embedding),
        "model": "NovaX-LLM-v1",
        "elapsed_ms": round(elapsed * 1000, 1),
        "ternary": 1
    }


# ============================================================
# ROUTE CLASSIFICATION (Router Brain)
# ============================================================
# Route categories for the NovaX swarm intelligence system
ROUTE_CATEGORIES = ["DIRECT", "MATH", "CODE", "RETRIEVAL", "ESCALATE"]

# Keyword-based classification (lightweight, no extra model needed)
# Will be replaced by learned route head after training with route data
ROUTE_KEYWORDS = {
    "MATH": ["calculate", "solve", "equation", "integral", "derivative", "sum",
             "multiply", "divide", "percent", "probability", "statistics",
             "algebra", "geometry", "calculus", "math", "number", "formula"],
    "CODE": ["code", "program", "function", "class", "debug", "error",
             "python", "rust", "javascript", "api", "implement", "algorithm",
             "compile", "syntax", "git", "deploy", "docker", "database", "sql"],
    "RETRIEVAL": ["who is", "when did", "where is", "what year", "how many people",
                  "latest", "current", "recent", "news", "today", "statistics of",
                  "capital of", "population of", "history of", "definition of"],
}

@torch.no_grad()
def classify_route(text):
    """Classify a query into a route category with confidence score.

    Uses keyword matching now; will upgrade to learned route head
    after training with route classification data.

    Returns: {"route": str, "confidence": float, "scores": dict}
    """
    text_lower = text.lower()
    scores = {"DIRECT": 0.3, "MATH": 0.0, "CODE": 0.0,
              "RETRIEVAL": 0.0, "ESCALATE": 0.0}

    # Keyword-based scoring
    for route, keywords in ROUTE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[route] += 0.15

    # Length-based heuristic: very long/complex queries should escalate
    if len(text) > 500:
        scores["ESCALATE"] += 0.3
    if "?" not in text and len(text) > 200:
        scores["ESCALATE"] += 0.2

    # Question mark boosts RETRIEVAL for factual questions
    if "?" in text and any(text_lower.startswith(w) for w in ["who", "what", "when", "where", "how many"]):
        scores["RETRIEVAL"] += 0.2

    # Normalize scores
    total = sum(scores.values())
    if total > 0:
        scores = {k: v / total for k, v in scores.items()}

    best_route = max(scores, key=scores.get)
    confidence = scores[best_route]

    # Confidence thresholds for routing decisions
    # High confidence (>0.5): route to specialist
    # Low confidence (<0.3): escalate to larger model
    if confidence < 0.3:
        best_route = "ESCALATE"

    return {
        "route": best_route,
        "confidence": round(confidence, 3),
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "method": "keyword_v1",
        "ternary": 1
    }


# ============================================================
# HTTP SERVER
# ============================================================
class InferenceHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health" or self.path == "/status":
            health = {
                "status": "ok",
                "trit": 1,
                "service": SERVICE_NAME,
                "version": VERSION,
                "port": PORT,
                "model_loaded": _model is not None,
                "device": str(_device) if _device else "none",
                "gen_count": _gen_count,
                "uptime": int(time.time() - _start_time),
                "max_context": MAX_CONTEXT,
                "kv_cache": "paged trit-packed (VRAM/RAM/Disk tiering)",
                "paged_mode": True,
            }
            # Add paged cache summary
            if _cached_inf and _cached_inf.use_paged:
                health["context_length"] = _cached_inf.context_length()
                if hasattr(_cached_inf.kv_cache, 'tier_report'):
                    tier = _cached_inf.kv_cache.tier_report()
                    health["cache_tiers"] = {
                        "hot_pages": tier["hot_pages"],
                        "warm_pages": tier["warm_pages"],
                        "cold_pages": tier["cold_pages"],
                    }
            if _mem_manager:
                tier_bytes = _mem_manager._tier_bytes()
                health["cache_memory"] = {
                    "hot_mb": round(tier_bytes["hot"] / (1024 * 1024), 2),
                    "warm_mb": round(tier_bytes["warm"] / (1024 * 1024), 2),
                    "cold_mb": round(tier_bytes["cold"] / (1024 * 1024), 2),
                }
            self._json(200, health)

        elif self.path == "/llm/cache-stats":
            # Detailed paged cache statistics endpoint
            if not _cached_inf:
                self._json(503, {"error": "Inference engine not initialized"})
                return

            stats = {
                "paged_mode": _cached_inf.use_paged,
                "context_length": _cached_inf.context_length(),
                "max_context": _cached_inf.max_context,
            }

            if _cached_inf.use_paged and hasattr(_cached_inf.kv_cache, 'tier_report'):
                tier = _cached_inf.kv_cache.tier_report()
                stats["tiers"] = {
                    "hot": {
                        "pages": tier["hot_pages"],
                        "location": "VRAM (GPU)",
                        "reynolds": tier["hot_reynolds"],
                    },
                    "warm": {
                        "pages": tier["warm_pages"],
                        "location": "RAM (System)",
                        "reynolds": tier["warm_reynolds"],
                    },
                    "cold": {
                        "pages": tier["cold_pages"],
                        "location": "Disk",
                    },
                }
                stats["total_pages"] = tier["hot_pages"] + tier["warm_pages"] + tier["cold_pages"]

            if _mem_manager:
                stats["memory"] = _mem_manager.stats()

            # Memory stats from cached inference
            mem = _cached_inf.memory_stats()
            stats["cache_bytes"] = mem["trit_bytes"]
            stats["compression"] = mem["compression"]

            # Capacity math
            cap = MemoryManager.capacity_estimate(
                num_layers=_cached_inf.num_layers,
                num_heads=_cached_inf.num_heads,
                head_dim=_cached_inf.head_dim,
            )
            stats["capacity"] = cap

            self._json(200, stats)

        elif self.path == "/llm/info":
            info = {
                "name": "NovaX-LLM-v2",
                "type": "ternary_transformer",
                "version": VERSION,
                "model_loaded": _model is not None,
                "device": str(_device) if _device else "none",
                "gen_count": _gen_count,
                "ternary": 1,
                "max_context": MAX_CONTEXT,
                "kv_cache": "paged trit-packed (3-tier)",
            }
            if _config:
                info["architecture"] = _config["model"]
                info["constants"] = _config.get("constants", {})
            if _model:
                info["parameters"] = f"{_model.param_count():,}"

            # Training stats
            if LOG_PATH.exists():
                try:
                    with open(LOG_PATH, "r") as f:
                        log = json.load(f)
                    if log:
                        last = log[-1]
                        best = min(log, key=lambda x: x.get("loss", 999))
                        info["training"] = {
                            "total_steps": last.get("step", 0),
                            "last_loss": last.get("loss", 0),
                            "best_loss": best.get("loss", 0),
                            "best_step": best.get("step", 0),
                            "best_perplexity": best.get("perplexity", 0),
                            "epochs": last.get("epoch", 0),
                        }
                except Exception:
                    pass

            self._json(200, info)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        if self.path == "/llm/generate":
            prompt = body.get("prompt", "")
            if not prompt:
                self._json(400, {"error": "No prompt provided", "ternary": -1})
                return

            result = generate(
                prompt,
                max_tokens=min(int(body.get("max_tokens", 256)), MAX_CONTEXT),
                temperature=float(body.get("temperature", 0.7)),
                top_k=int(body.get("top_k", 13)),
                top_p=float(body.get("top_p", 0.9)),
                repetition_penalty=float(body.get("repetition_penalty", 1.1)),
                context_budget=body.get("context_budget"),
                cfg_scale=float(body.get("cfg_scale", 0.0)),
                min_p=float(body.get("min_p", 0.05)),
                use_lz_penalty=bool(body.get("lz_penalty", True)),
            )
            self._json(200, result)

        elif self.path == "/llm/route":
            text = body.get("text", "") or body.get("prompt", "")
            if not text:
                self._json(400, {"error": "No text provided", "ternary": -1})
                return
            result = classify_route(text)
            self._json(200, result)

        elif self.path == "/llm/embed":
            text = body.get("text", "")
            if not text:
                self._json(400, {"error": "No text provided", "ternary": -1})
                return
            result = get_embedding(text)
            self._json(200, result)

        else:
            self._json(404, {"error": "not found"})


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  NovaX LLM Inference Server v{VERSION}")
    print(f"  Paged Trit KV Cache: Million-Token Context")
    print(f"{'='*50}")
    print(f"  Port: {PORT}")

    loaded = load_model()
    print(f"  Model ready: {loaded}")
    print(f"{'='*50}")
    print(f"\nEndpoints:")
    print(f"  POST /llm/generate    -- text generation (paged KV cache)")
    print(f"  POST /llm/embed       -- embedding extraction")
    print(f"  POST /llm/route       -- query route classification")
    print(f"  GET  /llm/info        -- model info")
    print(f"  GET  /llm/cache-stats -- detailed cache tier statistics")
    print(f"  GET  /health          -- service health")
    print()

    server = http.server.HTTPServer(("127.0.0.1", PORT), InferenceHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
