"""
NovaX LLM Chat — Interactive inference for the trained ternary model.
=====================================================================

Modes:
    python chat.py                           # Interactive chat (default)
    python chat.py --prompt "Hello world"    # Single prompt
    python chat.py --api                     # HTTP API on port 9805

Generation parameters:
    --temperature   Sampling temperature (default 0.7)
    --top-k         Top-k filtering (default 50)
    --top-p         Nucleus sampling threshold (default 0.9)
    --rep-penalty   Repetition penalty (default 1.1)
    --max-tokens    Maximum new tokens to generate (default 256)
    --checkpoint    Path to a specific checkpoint file

Requires: PyTorch >= 2.0
"""

import argparse
import json
import math
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import List, Optional

import pickle
import torch
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Resolve project paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
CHECKPOINT_DIR = SCRIPT_DIR / "checkpoints"
BPE_VOCAB_PATH = SCRIPT_DIR / "bpe_vocab_32k.json"

# Import model and config from train.py
sys.path.insert(0, str(SCRIPT_DIR))
from train import TernaryTransformer, load_config
from bpe_tokenizer import NovaXTokenizer, SPECIAL_TOKENS

# Special token IDs
BOS_ID = SPECIAL_TOKENS["<BOS>"]
EOS_ID = SPECIAL_TOKENS["<EOS>"]
PAD_ID = SPECIAL_TOKENS["<PAD>"]


# ============================================================
# CHECKPOINT DISCOVERY
# ============================================================

def find_best_checkpoint(checkpoint_dir: Path, explicit: Optional[str] = None) -> Path:
    """Find the best checkpoint to load.

    Priority:
        1. Explicitly provided path
        2. best.pt
        3. Latest step_*.pt (highest step number)
    """
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
        raise FileNotFoundError(f"Checkpoint not found: {explicit}")

    best = checkpoint_dir / "best.pt"
    if best.exists():
        return best

    # Find latest step checkpoint
    step_files = sorted(
        checkpoint_dir.glob("step_*.pt"),
        key=lambda f: int(f.stem.split("_")[1]),
        reverse=True,
    )
    if step_files:
        return step_files[0]

    raise FileNotFoundError(
        f"No checkpoints found in {checkpoint_dir}. "
        "Train the model first with train.py."
    )


# ============================================================
# MODEL LOADING
# ============================================================

def load_model(config: dict, checkpoint_path: Path, device: torch.device):
    """Instantiate TernaryTransformer and load checkpoint weights."""
    model = TernaryTransformer(config)
    # weights_only=True blocks arbitrary code execution via pickle (security fix).
    # Our checkpoints only contain tensors, dicts, lists, and primitives — all
    # supported by PyTorch's weights_only safelist.
    try:
        checkpoint = torch.load(str(checkpoint_path), map_location=device, weights_only=True)
    except (pickle.UnpicklingError, AttributeError, RuntimeError) as e:
        # Narrow fallback: only catches unpickling/safelist errors, not I/O or OOM.
        # WARN so the user knows the security check was bypassed for this checkpoint.
        print(f"[chat] WARN: weights_only=True rejected ({type(e).__name__}): {e}")
        print(f"[chat] WARN: falling back to weights_only=False — trust this checkpoint source!")
        checkpoint = torch.load(str(checkpoint_path), map_location=device, weights_only=False)

    # Checkpoints may store state_dict directly or under a key
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    elif isinstance(checkpoint, dict) and "model" in checkpoint:
        state_dict = checkpoint["model"]
    else:
        state_dict = checkpoint

    # Load with flexibility for minor mismatches
    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()

    # Extract training step if available
    step = None
    if isinstance(checkpoint, dict):
        step = checkpoint.get("step") or checkpoint.get("global_step") or checkpoint.get("epoch")

    return model, step


def print_model_stats(model, config, checkpoint_path, step, device):
    """Print model information on startup."""
    cfg = config["model"]
    param_count = model.param_count()
    print("=" * 60)
    print("  NovaX Ternary LLM — Chat Inference")
    print("=" * 60)
    print(f"  Parameters:    {param_count:,} ({param_count / 1e6:.1f}M)")
    print(f"  Embed dim:     {cfg['embedding_dim']}")
    print(f"  Layers:        {cfg['num_layers']}")
    print(f"  Heads:         {cfg['num_heads']}")
    print(f"  Max seq len:   {cfg['max_seq_len']}")
    print(f"  Vocab size:    {cfg['vocab_size']}")
    print(f"  Checkpoint:    {checkpoint_path.name}")
    if step is not None:
        print(f"  Training step: {step}")
    print(f"  Device:        {device}")
    if device.type == "cuda":
        print(f"  GPU:           {torch.cuda.get_device_name(device)}")
        mem = torch.cuda.get_device_properties(device).total_memory / 1024**3
        print(f"  GPU memory:    {mem:.1f} GB")
    print("=" * 60)


# ============================================================
# TEXT GENERATION
# ============================================================

@torch.no_grad()
def generate(
    model: TernaryTransformer,
    tokenizer: NovaXTokenizer,
    prompt: str,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
    top_k: int = 50,
    top_p: float = 0.9,
    repetition_penalty: float = 1.1,
    stream: bool = True,
    device: torch.device = torch.device("cpu"),
) -> str:
    """Autoregressive generation with sampling controls.

    Args:
        model:              The TernaryTransformer model in eval mode.
        tokenizer:          NovaXTokenizer with loaded BPE vocab.
        prompt:             Input text.
        max_new_tokens:     Maximum tokens to generate.
        temperature:        Sampling temperature (0 = greedy, higher = more random).
        top_k:              Keep only top-k logits (0 = disabled).
        top_p:              Nucleus sampling threshold (1.0 = disabled).
        repetition_penalty: Penalize repeated tokens (1.0 = disabled).
        stream:             Print tokens as they are generated.
        device:             Torch device.

    Returns:
        Generated text (excluding the prompt).
    """
    max_seq_len = model.max_seq_len

    # Encode prompt with BOS
    prompt_ids = tokenizer.encode_with_special(prompt, add_bos=True, add_eos=False)

    # Truncate if prompt exceeds context window (leave room for at least 1 new token)
    if len(prompt_ids) >= max_seq_len:
        prompt_ids = prompt_ids[-(max_seq_len - 1):]
        prompt_ids = [BOS_ID] + prompt_ids[1:]  # keep BOS at front

    input_ids = torch.tensor([prompt_ids], dtype=torch.long, device=device)
    generated_ids: List[int] = []

    for _ in range(max_new_tokens):
        # Truncate to max_seq_len if context grows too long
        if input_ids.shape[1] > max_seq_len:
            input_ids = input_ids[:, -max_seq_len:]

        # Forward pass
        logits, _ = model(input_ids)
        next_logits = logits[:, -1, :].float()  # (1, vocab_size)

        # --- Repetition penalty ---
        if repetition_penalty != 1.0 and len(generated_ids) > 0:
            prev_tokens = set(generated_ids) | set(prompt_ids)
            for token_id in prev_tokens:
                if 0 <= token_id < next_logits.shape[-1]:
                    if next_logits[0, token_id] > 0:
                        next_logits[0, token_id] /= repetition_penalty
                    else:
                        next_logits[0, token_id] *= repetition_penalty

        # --- Temperature ---
        if temperature <= 0:
            # Greedy
            next_token = next_logits.argmax(dim=-1).item()
        else:
            next_logits = next_logits / temperature

            # --- Top-k filtering ---
            if top_k > 0:
                top_k_val = min(top_k, next_logits.shape[-1])
                indices_to_remove = next_logits < torch.topk(next_logits, top_k_val)[0][..., -1, None]
                next_logits[indices_to_remove] = float("-inf")

            # --- Top-p (nucleus) filtering ---
            if 0.0 < top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                # Remove tokens with cumulative probability above the threshold
                sorted_indices_to_remove = cumulative_probs > top_p
                # Keep the first token above the threshold
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = False
                indices_to_remove = sorted_indices_to_remove.scatter(
                    1, sorted_indices, sorted_indices_to_remove
                )
                next_logits[indices_to_remove] = float("-inf")

            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1).item()

        # Stop on EOS or PAD
        if next_token == EOS_ID or next_token == PAD_ID:
            break

        generated_ids.append(next_token)

        # Stream output
        if stream:
            token_text = tokenizer.decode([next_token])
            print(token_text, end="", flush=True)

        # Append to context
        next_tensor = torch.tensor([[next_token]], dtype=torch.long, device=device)
        input_ids = torch.cat([input_ids, next_tensor], dim=1)

    if stream:
        print()  # newline after streaming

    return tokenizer.decode(generated_ids)


# ============================================================
# INTERACTIVE CHAT MODE
# ============================================================

def interactive_chat(model, tokenizer, args, device):
    """REPL-style chat loop."""
    print("\nType your message and press Enter. Commands:")
    print("  /quit or /exit   — exit chat")
    print("  /temp <value>    — set temperature")
    print("  /topk <value>    — set top-k")
    print("  /topp <value>    — set top-p")
    print("  /tokens <value>  — set max new tokens")
    print("  /reset           — show current settings")
    print()

    temperature = args.temperature
    top_k = args.top_k
    top_p = args.top_p
    rep_penalty = args.rep_penalty
    max_tokens = args.max_tokens

    while True:
        try:
            user_input = input("\033[92mYou>\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("Goodbye.")
            break
        elif user_input.startswith("/temp "):
            try:
                temperature = float(user_input.split()[1])
                print(f"  Temperature set to {temperature}")
            except (IndexError, ValueError):
                print("  Usage: /temp <float>")
            continue
        elif user_input.startswith("/topk "):
            try:
                top_k = int(user_input.split()[1])
                print(f"  Top-k set to {top_k}")
            except (IndexError, ValueError):
                print("  Usage: /topk <int>")
            continue
        elif user_input.startswith("/topp "):
            try:
                top_p = float(user_input.split()[1])
                print(f"  Top-p set to {top_p}")
            except (IndexError, ValueError):
                print("  Usage: /topp <float>")
            continue
        elif user_input.startswith("/tokens "):
            try:
                max_tokens = int(user_input.split()[1])
                print(f"  Max tokens set to {max_tokens}")
            except (IndexError, ValueError):
                print("  Usage: /tokens <int>")
            continue
        elif user_input == "/reset":
            print(f"  temperature={temperature}  top_k={top_k}  "
                  f"top_p={top_p}  rep_penalty={rep_penalty}  "
                  f"max_tokens={max_tokens}")
            continue

        # Generate response
        print("\033[94mNovaX>\033[0m ", end="", flush=True)
        t0 = time.perf_counter()
        response = generate(
            model, tokenizer, user_input,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            repetition_penalty=rep_penalty,
            stream=True,
            device=device,
        )
        elapsed = time.perf_counter() - t0
        token_count = len(tokenizer.encode(response))
        tps = token_count / elapsed if elapsed > 0 else 0
        print(f"  \033[90m[{token_count} tokens, {elapsed:.2f}s, {tps:.1f} tok/s]\033[0m")
        print()


# ============================================================
# API MODE
# ============================================================

def make_api_handler(model, tokenizer, device, defaults):
    """Create an HTTP request handler with access to model."""

    class NovaXAPIHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/generate":
                self.send_error(404, "Only POST /generate is supported")
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                req = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            prompt = req.get("prompt", "")
            if not prompt:
                self.send_error(400, "Missing 'prompt' field")
                return

            temperature = req.get("temperature", defaults["temperature"])
            top_k = req.get("top_k", defaults["top_k"])
            top_p = req.get("top_p", defaults["top_p"])
            rep_penalty = req.get("repetition_penalty", defaults["rep_penalty"])
            max_tokens = req.get("max_tokens", defaults["max_tokens"])

            t0 = time.perf_counter()
            response_text = generate(
                model, tokenizer, prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                repetition_penalty=rep_penalty,
                stream=False,
                device=device,
            )
            elapsed = time.perf_counter() - t0
            token_count = len(tokenizer.encode(response_text))

            result = {
                "prompt": prompt,
                "response": response_text,
                "tokens_generated": token_count,
                "elapsed_seconds": round(elapsed, 3),
                "tokens_per_second": round(token_count / elapsed, 1) if elapsed > 0 else 0,
                "parameters": {
                    "temperature": temperature,
                    "top_k": top_k,
                    "top_p": top_p,
                    "repetition_penalty": rep_penalty,
                    "max_tokens": max_tokens,
                },
            }

            response_body = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "model": "NovaX-LLM-v1"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def log_message(self, format, *a):
            # Quieter logging
            print(f"  [API] {a[0]} {a[1]} {a[2]}")

    return NovaXAPIHandler


def run_api_server(model, tokenizer, device, args):
    """Start the HTTP API server."""
    defaults = {
        "temperature": args.temperature,
        "top_k": args.top_k,
        "top_p": args.top_p,
        "rep_penalty": args.rep_penalty,
        "max_tokens": args.max_tokens,
    }
    handler = make_api_handler(model, tokenizer, device, defaults)
    server = HTTPServer(("0.0.0.0", args.port), handler)
    print(f"\nNovaX API server running on http://0.0.0.0:{args.port}")
    print(f"  POST /generate  — generate text")
    print(f"  GET  /health    — health check")
    print(f"\nExample:")
    print(f'  curl -X POST http://localhost:{args.port}/generate \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"prompt": "Hello, world!", "max_tokens": 128}}\'')
    print(f"\nPress Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API server.")
        server.shutdown()


# ============================================================
# MAIN
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="NovaX Ternary LLM — Chat & Inference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python chat.py                                    # Interactive chat
  python chat.py --prompt "Explain quantum computing"
  python chat.py --api                              # HTTP API server
  python chat.py --prompt "Hello" --temperature 0.0 # Greedy decoding
        """,
    )
    parser.add_argument("--prompt", type=str, default=None,
                        help="Single prompt to generate from (non-interactive)")
    parser.add_argument("--api", action="store_true",
                        help="Run as HTTP API server")
    parser.add_argument("--port", type=int, default=9805,
                        help="API server port (default: 9805)")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Path to checkpoint file (default: auto-detect best)")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Sampling temperature (default: 0.7)")
    parser.add_argument("--top-k", type=int, default=50,
                        help="Top-k sampling (default: 50, 0=disabled)")
    parser.add_argument("--top-p", type=float, default=0.9,
                        help="Nucleus sampling threshold (default: 0.9)")
    parser.add_argument("--rep-penalty", type=float, default=1.1,
                        help="Repetition penalty (default: 1.1, 1.0=disabled)")
    parser.add_argument("--max-tokens", type=int, default=256,
                        help="Maximum new tokens to generate (default: 256)")
    parser.add_argument("--device", type=str, default=None,
                        help="Device: cuda, cpu, or auto (default: auto)")
    parser.add_argument("--no-stream", action="store_true",
                        help="Disable streaming output")
    return parser.parse_args()


def main():
    args = parse_args()

    # --- Device selection ---
    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    # --- Load config ---
    config = load_config()

    # --- Find and load checkpoint ---
    checkpoint_path = find_best_checkpoint(CHECKPOINT_DIR, args.checkpoint)
    print(f"Loading checkpoint: {checkpoint_path}")
    model, step = load_model(config, checkpoint_path, device)

    # --- Load tokenizer ---
    tokenizer = NovaXTokenizer(str(BPE_VOCAB_PATH))

    # --- Print stats ---
    print_model_stats(model, config, checkpoint_path, step, device)

    # --- Run selected mode ---
    if args.prompt:
        # Single prompt mode
        if not args.no_stream:
            print(f"\n\033[94mNovaX>\033[0m ", end="", flush=True)
        t0 = time.perf_counter()
        response = generate(
            model, tokenizer, args.prompt,
            max_new_tokens=args.max_tokens,
            temperature=args.temperature,
            top_k=args.top_k,
            top_p=args.top_p,
            repetition_penalty=args.rep_penalty,
            stream=not args.no_stream,
            device=device,
        )
        elapsed = time.perf_counter() - t0
        if args.no_stream:
            print(f"\n{response}")
        token_count = len(tokenizer.encode(response))
        tps = token_count / elapsed if elapsed > 0 else 0
        print(f"\n  [{token_count} tokens, {elapsed:.2f}s, {tps:.1f} tok/s]")

    elif args.api:
        # API server mode
        run_api_server(model, tokenizer, device, args)

    else:
        # Interactive chat mode (default)
        interactive_chat(model, tokenizer, args, device)


if __name__ == "__main__":
    main()
