"""
NovaX LLM Evaluation Harness
=============================
Lightweight benchmark evaluation for the NovaX 235M Ternary Transformer.

Benchmarks:
    hellaswag   - Commonsense reasoning (4-way multiple choice)
    arc_easy    - ARC-Easy science questions (4-way multiple choice)
    piqa        - Physical Intuition QA (2-way multiple choice)
    winogrande  - Coreference / commonsense (2-way fill-in-the-blank)
    boolq       - Boolean question answering (yes/no)
    perplexity  - Perplexity on held-out training data

Usage:
    python eval_harness.py --all                   # Run all benchmarks
    python eval_harness.py --benchmark hellaswag   # Run specific benchmark
    python eval_harness.py --benchmark perplexity  # Perplexity only
    python eval_harness.py --checkpoint PATH       # Use specific checkpoint

Results saved to: C:/NovaX/nova_llm/eval_results.json
"""

import argparse
import json
import math
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
ARCH_PATH = SCRIPT_DIR / "architecture.json"
CHECKPOINT_DIR = SCRIPT_DIR / "checkpoints"
BPE_VOCAB_PATH = SCRIPT_DIR / "bpe_vocab_32k.json"
DATA_PATH = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")
RESULTS_PATH = SCRIPT_DIR / "eval_results.json"
BENCHMARK_CACHE_DIR = SCRIPT_DIR / "eval_cache"

# ---------------------------------------------------------------------------
# Import model classes from train.py
# ---------------------------------------------------------------------------
sys.path.insert(0, str(SCRIPT_DIR))
from train import TernaryTransformer, load_config

# ---------------------------------------------------------------------------
# Tokenizer helper
# ---------------------------------------------------------------------------
class SimpleTokenizer:
    """Wraps BPE tokenizer or falls back to byte-level encoding."""

    BOS = 1
    EOS = 2
    SEP = 5
    PAD = 0

    def __init__(self):
        self._bpe = None
        if BPE_VOCAB_PATH.exists():
            try:
                from bpe_tokenizer import NovaXTokenizer
                self._bpe = NovaXTokenizer(str(BPE_VOCAB_PATH))
                print(f"[Tokenizer] BPE loaded ({self._bpe.vocab_size} tokens)")
            except Exception as e:
                print(f"[Tokenizer] BPE failed ({e}), using byte-level")
        else:
            print("[Tokenizer] BPE vocab not found, using byte-level")

    def encode(self, text: str) -> List[int]:
        if self._bpe is not None:
            return self._bpe.encode(text)
        ids = []
        for ch in text:
            code = ord(ch)
            if code < 256:
                ids.append(code + 13)
            else:
                ids.append(3)  # UNK
        return ids

    def decode(self, ids: List[int]) -> str:
        if self._bpe is not None:
            return self._bpe.decode(ids)
        out = []
        for tid in ids:
            if 13 <= tid < 269:
                out.append(chr(tid - 13))
        return "".join(out)


# ---------------------------------------------------------------------------
# Model loader
# ---------------------------------------------------------------------------
def load_model(checkpoint_path: Optional[str] = None) -> Tuple[TernaryTransformer, torch.device]:
    """Load model from checkpoint. Tries best.pt -> final.pt -> latest step."""
    config = load_config()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = TernaryTransformer(config)

    # Resolve checkpoint
    if checkpoint_path:
        ckpt_path = Path(checkpoint_path)
    else:
        # Priority: best.pt -> final.pt -> highest step
        for name in ["best.pt", "final.pt"]:
            candidate = CHECKPOINT_DIR / name
            if candidate.exists():
                ckpt_path = candidate
                break
        else:
            # Find highest step checkpoint
            steps = sorted(CHECKPOINT_DIR.glob("step_*.pt"))
            if steps:
                ckpt_path = steps[-1]
            else:
                print("[ERROR] No checkpoint found in", CHECKPOINT_DIR)
                sys.exit(1)

    print(f"[Model] Loading checkpoint: {ckpt_path}")
    # Security: weights_only=True blocks pickle-based code execution.
    try:
        ckpt = torch.load(str(ckpt_path), map_location=device, weights_only=True)
    except Exception:
        ckpt = torch.load(str(ckpt_path), map_location=device, weights_only=False)

    # Handle different checkpoint formats
    state_dict = ckpt.get("model_state_dict", ckpt.get("state_dict", ckpt))
    if isinstance(state_dict, dict) and "model_state_dict" not in state_dict and "state_dict" not in state_dict:
        # Might be raw state_dict
        pass

    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()

    param_count = model.param_count()
    print(f"[Model] {param_count / 1e6:.1f}M parameters on {device}")

    return model, device


# ---------------------------------------------------------------------------
# Log-probability scoring
# ---------------------------------------------------------------------------
@torch.no_grad()
def score_sequence(model: TernaryTransformer, token_ids: List[int],
                   device: torch.device, max_len: int = 256) -> float:
    """Compute total log-probability of a token sequence.

    Returns sum of log P(token_i | token_0..i-1) for i >= 1.
    """
    if len(token_ids) < 2:
        return -float("inf")

    ids = token_ids[:max_len]
    input_ids = torch.tensor([ids], dtype=torch.long, device=device)

    logits, _ = model(input_ids)  # (1, seq_len, vocab_size)

    # Shift: predict token i from position i-1
    shift_logits = logits[0, :-1, :]  # (seq_len-1, vocab)
    shift_targets = input_ids[0, 1:]  # (seq_len-1,)

    log_probs = F.log_softmax(shift_logits, dim=-1)
    token_log_probs = log_probs.gather(1, shift_targets.unsqueeze(1)).squeeze(1)

    return token_log_probs.sum().item()


@torch.no_grad()
def score_continuation(model: TernaryTransformer, context_ids: List[int],
                       continuation_ids: List[int], device: torch.device,
                       max_len: int = 256) -> float:
    """Score how likely continuation_ids follow context_ids.

    Returns average log-probability of continuation tokens only,
    conditioned on the context.
    """
    full_ids = (context_ids + continuation_ids)[:max_len]
    n_ctx = min(len(context_ids), max_len)
    n_cont = len(full_ids) - n_ctx

    if n_cont < 1:
        return -float("inf")

    input_ids = torch.tensor([full_ids], dtype=torch.long, device=device)
    logits, _ = model(input_ids)

    # Only score the continuation portion
    # Position n_ctx-1 predicts token n_ctx, etc.
    start = max(n_ctx - 1, 0)
    end = len(full_ids) - 1

    shift_logits = logits[0, start:end, :]
    shift_targets = input_ids[0, start + 1:end + 1]

    log_probs = F.log_softmax(shift_logits, dim=-1)
    token_log_probs = log_probs.gather(1, shift_targets.unsqueeze(1)).squeeze(1)

    # Length-normalized log probability
    return token_log_probs.mean().item()


# ---------------------------------------------------------------------------
# Benchmark data download / cache
# ---------------------------------------------------------------------------
def download_json(url: str, cache_name: str) -> list:
    """Download JSONL/JSON from URL and cache locally."""
    BENCHMARK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = BENCHMARK_CACHE_DIR / cache_name

    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"  Downloading {cache_name} ...")
    # Use 127.0.0.1 for any local calls, but these are external HuggingFace URLs
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NovaX-Eval/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        print(f"  [WARN] Download failed: {e}")
        return []

    # Parse JSONL (one JSON object per line) or JSON array
    data = []
    raw = raw.strip()
    if raw.startswith("["):
        data = json.loads(raw)
    else:
        for line in raw.split("\n"):
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # Cache
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    print(f"  Cached {len(data)} examples to {cache_path}")
    return data


def get_hellaswag_data(n: int = 0) -> list:
    """Get HellaSwag validation examples.

    Downloads the full validation JSONL and caches locally.
    Pass n=0 (default) to use the full dataset.
    """
    url = "https://raw.githubusercontent.com/rowanz/hellaswag/master/data/hellaswag_val.jsonl"
    data = download_json(url, "hellaswag_val.json")
    if not data:
        print("  [WARN] HellaSwag download failed, using embedded mini sample")
        data = _embedded_hellaswag()
    return data[:n] if n > 0 else data


def get_arc_easy_data(n: int = 0) -> list:
    """Get ARC-Easy test examples via HuggingFace datasets library.

    Downloads the full test split and caches to eval_cache/arc_easy_test.json.
    Pass n=0 (default) to use the full dataset.
    """
    BENCHMARK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = BENCHMARK_CACHE_DIR / "arc_easy_test.json"

    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  Loaded {len(data)} ARC-Easy examples from cache")
    else:
        try:
            from datasets import load_dataset
            print("  Downloading ARC-Easy via datasets library ...")
            ds = load_dataset("allenai/ai2_arc", "ARC-Easy", split="test")
            data = [dict(row) for row in ds]
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            print(f"  Cached {len(data)} ARC-Easy examples to {cache_path}")
        except Exception as e:
            print(f"  [WARN] ARC-Easy download failed: {e}")
            print("  Using embedded mini sample")
            data = _embedded_arc_easy()

    return data[:n] if n > 0 else data


def get_piqa_data(n: int = 0) -> list:
    """Get PIQA validation examples.

    Downloads the full validation JSONL and caches locally.
    Pass n=0 (default) to use the full dataset.
    """
    # PIQA labels and data
    data_url = "https://raw.githubusercontent.com/ybisk/ybisk.github.io/master/piqa/data/valid.jsonl"
    label_url = "https://raw.githubusercontent.com/ybisk/ybisk.github.io/master/piqa/data/valid-labels.lst"

    data = download_json(data_url, "piqa_valid.json")

    # Download labels separately
    label_cache = BENCHMARK_CACHE_DIR / "piqa_valid_labels.txt"
    labels = []
    if label_cache.exists():
        with open(label_cache, "r") as f:
            labels = [int(x.strip()) for x in f.readlines() if x.strip()]
    else:
        try:
            req = urllib.request.Request(label_url, headers={"User-Agent": "NovaX-Eval/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
            labels = [int(x.strip()) for x in raw.strip().split("\n") if x.strip()]
            BENCHMARK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(label_cache, "w") as f:
                f.write("\n".join(str(l) for l in labels))
        except Exception as e:
            print(f"  [WARN] PIQA labels download failed: {e}")

    # Merge labels into data
    if labels and data:
        for i, item in enumerate(data):
            if i < len(labels):
                item["label"] = labels[i]

    if not data:
        print("  [WARN] PIQA download failed, using embedded mini sample")
        data = _embedded_piqa()
    return data[:n] if n > 0 else data


def get_winogrande_data(n: int = 0) -> list:
    """Get WinoGrande validation examples via HuggingFace datasets library.

    Downloads the full validation split (winogrande_xl) and caches to
    eval_cache/winogrande_val.json.  Pass n=0 (default) to use the full dataset.
    """
    BENCHMARK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = BENCHMARK_CACHE_DIR / "winogrande_val.json"

    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  Loaded {len(data)} WinoGrande examples from cache")
    else:
        try:
            from datasets import load_dataset
            print("  Downloading WinoGrande via datasets library ...")
            ds = load_dataset("allenai/winogrande", "winogrande_xl", split="validation")
            data = [dict(row) for row in ds]
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            print(f"  Cached {len(data)} WinoGrande examples to {cache_path}")
        except Exception as e:
            print(f"  [WARN] WinoGrande download failed: {e}")
            data = []

    return data[:n] if n > 0 else data


def get_boolq_data(n: int = 0) -> list:
    """Get BoolQ validation examples via HuggingFace datasets library.

    Downloads the full validation split and caches to
    eval_cache/boolq_val.json.  Pass n=0 (default) to use the full dataset.
    """
    BENCHMARK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = BENCHMARK_CACHE_DIR / "boolq_val.json"

    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  Loaded {len(data)} BoolQ examples from cache")
    else:
        try:
            from datasets import load_dataset
            print("  Downloading BoolQ via datasets library ...")
            ds = load_dataset("google/boolq", split="validation")
            data = [dict(row) for row in ds]
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            print(f"  Cached {len(data)} BoolQ examples to {cache_path}")
        except Exception as e:
            print(f"  [WARN] BoolQ download failed: {e}")
            data = []

    return data[:n] if n > 0 else data


# ---------------------------------------------------------------------------
# Embedded mini samples (fallback if download fails)
# ---------------------------------------------------------------------------
def _embedded_hellaswag() -> list:
    """10 embedded HellaSwag examples for offline testing."""
    return [
        {"ctx": "A man is sitting on a roof. He starts pulling up shingles.",
         "endings": ["He nails them down.", "He falls off the roof.",
                     "He starts to remove the roofing.", "He starts singing."],
         "label": "2"},
        {"ctx": "A woman is cooking in the kitchen. She chops vegetables on a cutting board.",
         "endings": ["She throws them into a pot.", "She leaves the kitchen.",
                     "She starts dancing.", "She calls a plumber."],
         "label": "0"},
        {"ctx": "The dog runs across the yard. It sees a squirrel in a tree.",
         "endings": ["The dog starts barking at the squirrel.", "The dog falls asleep.",
                     "The dog starts reading a book.", "The dog flies away."],
         "label": "0"},
        {"ctx": "Students are sitting in a classroom. The teacher writes on the whiteboard.",
         "endings": ["Students take notes.", "Students leave the building.",
                     "The whiteboard catches fire.", "Everyone starts swimming."],
         "label": "0"},
        {"ctx": "A mechanic opens the hood of a car. He inspects the engine.",
         "endings": ["He starts cooking dinner.", "He identifies a loose belt.",
                     "He plants flowers.", "He starts painting a picture."],
         "label": "1"},
    ]


def _embedded_arc_easy() -> list:
    """10 embedded ARC-Easy examples for offline testing."""
    return [
        {"question": "Which of these is a renewable resource?",
         "choices": {"text": ["Coal", "Oil", "Sunlight", "Natural gas"], "label": ["A", "B", "C", "D"]},
         "answerKey": "C"},
        {"question": "What is the boiling point of water at sea level?",
         "choices": {"text": ["50 degrees C", "100 degrees C", "150 degrees C", "200 degrees C"],
                     "label": ["A", "B", "C", "D"]},
         "answerKey": "B"},
        {"question": "Which planet is closest to the Sun?",
         "choices": {"text": ["Venus", "Mercury", "Earth", "Mars"], "label": ["A", "B", "C", "D"]},
         "answerKey": "B"},
        {"question": "What gas do plants absorb from the atmosphere?",
         "choices": {"text": ["Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"],
                     "label": ["A", "B", "C", "D"]},
         "answerKey": "C"},
        {"question": "Sound travels fastest through which medium?",
         "choices": {"text": ["Air", "Water", "Steel", "Vacuum"], "label": ["A", "B", "C", "D"]},
         "answerKey": "C"},
    ]


def _embedded_piqa() -> list:
    """10 embedded PIQA examples for offline testing."""
    return [
        {"goal": "To clean a mirror", "sol1": "Use a cloth with glass cleaner.",
         "sol2": "Use sandpaper.", "label": 0},
        {"goal": "To boil water faster", "sol1": "Put a lid on the pot.",
         "sol2": "Put the pot in the freezer.", "label": 0},
        {"goal": "To remove a stripped screw", "sol1": "Use a rubber band over the screw head and press the screwdriver into it.",
         "sol2": "Pour water on the screw.", "label": 0},
        {"goal": "To keep food cold on a picnic", "sol1": "Use a cooler with ice packs.",
         "sol2": "Wrap the food in newspaper.", "label": 0},
        {"goal": "To sharpen a knife", "sol1": "Run the blade along a sharpening stone at an angle.",
         "sol2": "Rub the blade on a sponge.", "label": 0},
    ]


# ---------------------------------------------------------------------------
# Benchmark: HellaSwag
# ---------------------------------------------------------------------------
def eval_hellaswag(model: TernaryTransformer, tokenizer: SimpleTokenizer,
                   device: torch.device, n: int = 0) -> Dict:
    """Evaluate on HellaSwag - commonsense sentence completion."""
    print("\n" + "=" * 60)
    print("  HELLASWAG (Commonsense Reasoning)")
    print("=" * 60)

    data = get_hellaswag_data(n)
    if not data:
        return {"score": 0, "total": 0, "accuracy": 0.0, "error": "no data"}

    correct = 0
    total = 0
    details = []

    for i, item in enumerate(data):
        ctx = item.get("ctx", item.get("context", ""))
        endings = item.get("endings", [])
        label = int(item.get("label", 0))

        if not endings or not ctx:
            continue

        ctx_ids = tokenizer.encode(ctx)

        # Score each ending
        scores = []
        for ending in endings:
            end_ids = tokenizer.encode(ending)
            score = score_continuation(model, ctx_ids, end_ids, device)
            scores.append(score)

        predicted = max(range(len(scores)), key=lambda k: scores[k])
        is_correct = predicted == label
        correct += int(is_correct)
        total += 1

        details.append({
            "idx": i,
            "predicted": predicted,
            "label": label,
            "correct": is_correct,
        })

        if (i + 1) % 50 == 0 or i == len(data) - 1:
            acc = correct / total * 100 if total > 0 else 0
            print(f"  [{i+1}/{len(data)}] accuracy: {acc:.1f}% ({correct}/{total})")

    accuracy = correct / total * 100 if total > 0 else 0
    print(f"\n  HellaSwag Final: {accuracy:.2f}% ({correct}/{total})")

    return {
        "benchmark": "hellaswag",
        "score": correct,
        "total": total,
        "accuracy": round(accuracy, 2),
        "details": details[:20],  # Keep first 20 for brevity
    }


# ---------------------------------------------------------------------------
# Benchmark: ARC-Easy
# ---------------------------------------------------------------------------
def eval_arc_easy(model: TernaryTransformer, tokenizer: SimpleTokenizer,
                  device: torch.device, n: int = 0) -> Dict:
    """Evaluate on ARC-Easy - science multiple choice."""
    print("\n" + "=" * 60)
    print("  ARC-EASY (Science Questions)")
    print("=" * 60)

    data = get_arc_easy_data(n)
    if not data:
        return {"score": 0, "total": 0, "accuracy": 0.0, "error": "no data"}

    correct = 0
    total = 0
    details = []

    for i, item in enumerate(data):
        question = item.get("question", "")
        choices = item.get("choices", {})
        answer_key = item.get("answerKey", "")

        choice_texts = choices.get("text", [])
        choice_labels = choices.get("label", [])

        if not question or not choice_texts or not answer_key:
            continue

        # Find correct index
        correct_idx = -1
        for j, lbl in enumerate(choice_labels):
            if str(lbl) == str(answer_key):
                correct_idx = j
                break
        if correct_idx < 0:
            # Try numeric
            try:
                correct_idx = int(answer_key) - 1
            except (ValueError, IndexError):
                continue

        # Format: "Question: ... Answer:"
        ctx_text = f"Question: {question} Answer:"
        ctx_ids = tokenizer.encode(ctx_text)

        scores = []
        for choice_text in choice_texts:
            ans_text = f" {choice_text}"
            ans_ids = tokenizer.encode(ans_text)
            score = score_continuation(model, ctx_ids, ans_ids, device)
            scores.append(score)

        predicted = max(range(len(scores)), key=lambda k: scores[k])
        is_correct = predicted == correct_idx
        correct += int(is_correct)
        total += 1

        details.append({
            "idx": i,
            "predicted": predicted,
            "label": correct_idx,
            "correct": is_correct,
        })

        if (i + 1) % 50 == 0 or i == len(data) - 1:
            acc = correct / total * 100 if total > 0 else 0
            print(f"  [{i+1}/{len(data)}] accuracy: {acc:.1f}% ({correct}/{total})")

    accuracy = correct / total * 100 if total > 0 else 0
    print(f"\n  ARC-Easy Final: {accuracy:.2f}% ({correct}/{total})")

    return {
        "benchmark": "arc_easy",
        "score": correct,
        "total": total,
        "accuracy": round(accuracy, 2),
        "details": details[:20],
    }


# ---------------------------------------------------------------------------
# Benchmark: PIQA
# ---------------------------------------------------------------------------
def eval_piqa(model: TernaryTransformer, tokenizer: SimpleTokenizer,
              device: torch.device, n: int = 0) -> Dict:
    """Evaluate on PIQA - physical intuition QA."""
    print("\n" + "=" * 60)
    print("  PIQA (Physical Intuition)")
    print("=" * 60)

    data = get_piqa_data(n)
    if not data:
        return {"score": 0, "total": 0, "accuracy": 0.0, "error": "no data"}

    correct = 0
    total = 0
    details = []

    for i, item in enumerate(data):
        goal = item.get("goal", "")
        sol1 = item.get("sol1", "")
        sol2 = item.get("sol2", "")
        label = int(item.get("label", 0))

        if not goal or not sol1 or not sol2:
            continue

        ctx_text = f"Goal: {goal} Solution:"
        ctx_ids = tokenizer.encode(ctx_text)

        solutions = [f" {sol1}", f" {sol2}"]
        scores = []
        for sol_text in solutions:
            sol_ids = tokenizer.encode(sol_text)
            score = score_continuation(model, ctx_ids, sol_ids, device)
            scores.append(score)

        predicted = max(range(len(scores)), key=lambda k: scores[k])
        is_correct = predicted == label
        correct += int(is_correct)
        total += 1

        details.append({
            "idx": i,
            "predicted": predicted,
            "label": label,
            "correct": is_correct,
        })

        if (i + 1) % 50 == 0 or i == len(data) - 1:
            acc = correct / total * 100 if total > 0 else 0
            print(f"  [{i+1}/{len(data)}] accuracy: {acc:.1f}% ({correct}/{total})")

    accuracy = correct / total * 100 if total > 0 else 0
    print(f"\n  PIQA Final: {accuracy:.2f}% ({correct}/{total})")

    return {
        "benchmark": "piqa",
        "score": correct,
        "total": total,
        "accuracy": round(accuracy, 2),
        "details": details[:20],
    }


# ---------------------------------------------------------------------------
# Benchmark: WinoGrande
# ---------------------------------------------------------------------------
def eval_winogrande(model: TernaryTransformer, tokenizer: SimpleTokenizer,
                    device: torch.device, n: int = 0) -> Dict:
    """Evaluate on WinoGrande - coreference / commonsense (2-way).

    Each example has a sentence with a blank (_), option1, option2, and
    answer (1 or 2).  We score the full sentence with each option filled in.
    """
    print("\n" + "=" * 60)
    print("  WINOGRANDE (Coreference / Commonsense)")
    print("=" * 60)

    data = get_winogrande_data(n)
    if not data:
        return {"score": 0, "total": 0, "accuracy": 0.0, "error": "no data"}

    correct = 0
    total = 0
    details = []

    for i, item in enumerate(data):
        sentence = item.get("sentence", "")
        option1 = item.get("option1", "")
        option2 = item.get("option2", "")
        answer = item.get("answer", "")

        if not sentence or "_" not in sentence or not option1 or not option2:
            continue
        # answer is "1" or "2" (string); convert to 0-based index
        try:
            label = int(answer) - 1
        except (ValueError, TypeError):
            continue
        if label not in (0, 1):
            continue

        # Build two candidate sentences by filling in the blank
        sent1 = sentence.replace("_", option1)
        sent2 = sentence.replace("_", option2)

        # Score full sequences
        ids1 = tokenizer.encode(sent1)[:256]
        ids2 = tokenizer.encode(sent2)[:256]
        score1 = score_sequence(model, ids1, device, max_len=256)
        score2 = score_sequence(model, ids2, device, max_len=256)

        predicted = 0 if score1 >= score2 else 1
        is_correct = predicted == label
        correct += int(is_correct)
        total += 1

        details.append({
            "idx": i, "predicted": predicted, "label": label,
            "correct": is_correct,
        })

        if (i + 1) % 100 == 0 or i == len(data) - 1:
            acc = correct / total * 100 if total > 0 else 0
            print(f"  [{i+1}/{len(data)}] accuracy: {acc:.1f}% ({correct}/{total})")

    accuracy = correct / total * 100 if total > 0 else 0
    print(f"\n  WinoGrande Final: {accuracy:.2f}% ({correct}/{total})")

    return {
        "benchmark": "winogrande",
        "score": correct,
        "total": total,
        "accuracy": round(accuracy, 2),
        "details": details[:20],
    }


# ---------------------------------------------------------------------------
# Benchmark: BoolQ
# ---------------------------------------------------------------------------
def eval_boolq(model: TernaryTransformer, tokenizer: SimpleTokenizer,
               device: torch.device, n: int = 0) -> Dict:
    """Evaluate on BoolQ - boolean question answering.

    Each example has a passage, a question, and a boolean answer.
    We score "Yes" vs "No" as continuations of "Passage: ... Question: ... Answer:"
    """
    print("\n" + "=" * 60)
    print("  BOOLQ (Boolean Question Answering)")
    print("=" * 60)

    data = get_boolq_data(n)
    if not data:
        return {"score": 0, "total": 0, "accuracy": 0.0, "error": "no data"}

    correct = 0
    total = 0
    details = []

    yes_tok = None
    no_tok = None

    for i, item in enumerate(data):
        question = item.get("question", "")
        passage = item.get("passage", "")
        answer = item.get("answer", None)

        if not question or answer is None:
            continue

        # True -> label 0 ("Yes"), False -> label 1 ("No")
        label = 0 if answer else 1

        # Truncate passage to leave room for question + answer tokens
        ctx_text = f"Passage: {passage} Question: {question} Answer:"
        ctx_ids = tokenizer.encode(ctx_text)
        # Reserve space for continuation tokens within the 256 limit
        ctx_ids = ctx_ids[:240]

        # Lazy-init continuation token ids
        if yes_tok is None:
            yes_tok = tokenizer.encode(" Yes")
            no_tok = tokenizer.encode(" No")

        score_yes = score_continuation(model, ctx_ids, yes_tok, device, max_len=256)
        score_no = score_continuation(model, ctx_ids, no_tok, device, max_len=256)

        predicted = 0 if score_yes >= score_no else 1
        is_correct = predicted == label
        correct += int(is_correct)
        total += 1

        details.append({
            "idx": i, "predicted": predicted, "label": label,
            "correct": is_correct,
        })

        if (i + 1) % 100 == 0 or i == len(data) - 1:
            acc = correct / total * 100 if total > 0 else 0
            print(f"  [{i+1}/{len(data)}] accuracy: {acc:.1f}% ({correct}/{total})")

    accuracy = correct / total * 100 if total > 0 else 0
    print(f"\n  BoolQ Final: {accuracy:.2f}% ({correct}/{total})")

    return {
        "benchmark": "boolq",
        "score": correct,
        "total": total,
        "accuracy": round(accuracy, 2),
        "details": details[:20],
    }


# ---------------------------------------------------------------------------
# Benchmark: Perplexity
# ---------------------------------------------------------------------------
def eval_perplexity(model: TernaryTransformer, tokenizer: SimpleTokenizer,
                    device: torch.device, n: int = 200, max_samples: int = None) -> Dict:
    if max_samples is None:
        max_samples = n
    """Compute perplexity on held-out 10% of training data."""
    print("\n" + "=" * 60)
    print("  PERPLEXITY (Held-out Data)")
    print("=" * 60)

    if not DATA_PATH.exists():
        print(f"  [ERROR] Training data not found: {DATA_PATH}")
        return {"benchmark": "perplexity", "perplexity": -1, "error": "no data"}

    print(f"  Loading training data from {DATA_PATH} ...")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        all_pairs = json.load(f)

    # Use last 10% as held-out
    n_total = len(all_pairs)
    n_heldout = max(1, n_total // 10)
    heldout = all_pairs[-n_heldout:]

    # Cap at max_samples
    if len(heldout) > max_samples:
        heldout = heldout[:max_samples]

    print(f"  Evaluating on {len(heldout)} held-out pairs (from {n_total} total)")

    total_log_prob = 0.0
    total_tokens = 0
    max_seq = 256  # Must match model's max_seq_len

    for i, pair in enumerate(heldout):
        prompt = pair.get("prompt", "") or pair.get("input", "")
        response = pair.get("response", "") or pair.get("output", "") or pair.get("completion", "")

        text = prompt + " " + response
        ids = [tokenizer.BOS] + tokenizer.encode(text) + [tokenizer.EOS]
        ids = ids[:max_seq]

        if len(ids) < 2:
            continue

        input_ids = torch.tensor([ids], dtype=torch.long, device=device)
        with torch.no_grad():
            logits, _ = model(input_ids)

        # Compute cross-entropy for each position
        shift_logits = logits[0, :-1, :]
        shift_targets = input_ids[0, 1:]

        log_probs = F.log_softmax(shift_logits, dim=-1)
        token_log_probs = log_probs.gather(1, shift_targets.unsqueeze(1)).squeeze(1)

        # Exclude PAD positions
        mask = shift_targets != tokenizer.PAD
        valid_log_probs = token_log_probs[mask]

        total_log_prob += valid_log_probs.sum().item()
        total_tokens += mask.sum().item()

        if (i + 1) % 50 == 0 or i == len(heldout) - 1:
            if total_tokens > 0:
                ppl = math.exp(-total_log_prob / total_tokens)
                print(f"  [{i+1}/{len(heldout)}] perplexity: {ppl:.2f} ({total_tokens} tokens)")

    if total_tokens == 0:
        return {"benchmark": "perplexity", "perplexity": -1, "error": "no valid tokens"}

    perplexity = math.exp(-total_log_prob / total_tokens)
    print(f"\n  Perplexity Final: {perplexity:.2f} (over {total_tokens} tokens)")

    return {
        "benchmark": "perplexity",
        "perplexity": round(perplexity, 2),
        "total_tokens": total_tokens,
        "n_samples": len(heldout),
        "avg_log_prob": round(total_log_prob / total_tokens, 4),
    }


# ---------------------------------------------------------------------------
# Results management
# ---------------------------------------------------------------------------
def save_results(results: Dict):
    """Append results to eval_results.json with timestamp."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": results,
    }

    history = []
    if RESULTS_PATH.exists():
        try:
            with open(RESULTS_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = [history]
        except (json.JSONDecodeError, Exception):
            history = []

    history.append(entry)

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    print(f"\n[Results] Saved to {RESULTS_PATH}")


def print_summary(results: Dict):
    """Print a nicely formatted summary table."""
    print("\n")
    print("+" + "-" * 58 + "+")
    print("|" + " NovaX 235M Ternary LLM - Evaluation Summary".center(58) + "|")
    print("+" + "-" * 58 + "+")
    print("| {:<20} | {:<15} | {:<15} |".format("Benchmark", "Score", "Target"))
    print("+" + "-" * 22 + "+" + "-" * 17 + "+" + "-" * 17 + "+")

    targets = {
        "hellaswag":   "46-50%",
        "arc_easy":    "45-50%",
        "piqa":        "69-71%",
        "winogrande":  "50-55%",
        "boolq":       "55-62%",
        "perplexity":  "lower=better",
    }

    for bench_name, bench_data in results.items():
        target = targets.get(bench_name, "N/A")

        if bench_name == "perplexity":
            ppl = bench_data.get("perplexity", -1)
            score_str = f"{ppl:.2f}" if ppl > 0 else "N/A"
        else:
            acc = bench_data.get("accuracy", 0)
            total = bench_data.get("total", 0)
            score_str = f"{acc:.1f}% ({bench_data.get('score', 0)}/{total})"

        print("| {:<20} | {:<15} | {:<15} |".format(bench_name, score_str, target))

    print("+" + "-" * 22 + "+" + "-" * 17 + "+" + "-" * 17 + "+")
    print(f"| {'Timestamp':<20} | {time.strftime('%Y-%m-%d %H:%M:%S'):<33} |")
    print("+" + "-" * 58 + "+")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
BENCHMARKS = {
    "hellaswag": eval_hellaswag,
    "arc_easy": eval_arc_easy,
    "piqa": eval_piqa,
    "winogrande": eval_winogrande,
    "boolq": eval_boolq,
    "perplexity": eval_perplexity,
}


def main():
    parser = argparse.ArgumentParser(description="NovaX LLM Evaluation Harness")
    parser.add_argument("--benchmark", type=str, default=None,
                        choices=list(BENCHMARKS.keys()),
                        help="Run a specific benchmark")
    parser.add_argument("--all", action="store_true",
                        help="Run all benchmarks")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="Path to model checkpoint")
    parser.add_argument("--samples", type=int, default=0,
                        help="Max samples per benchmark (0 = full dataset, default: 0)")
    args = parser.parse_args()

    if not args.benchmark and not args.all:
        print("Usage: python eval_harness.py --all")
        print("       python eval_harness.py --benchmark hellaswag")
        print("\nAvailable benchmarks:", ", ".join(BENCHMARKS.keys()))
        sys.exit(0)

    print("=" * 60)
    print("  NovaX LLM Evaluation Harness")
    print("  Model: 235M Ternary Transformer")
    print("=" * 60)

    # Load model and tokenizer
    model, device = load_model(args.checkpoint)
    tokenizer = SimpleTokenizer()

    # Run benchmarks
    results = {}
    benchmarks_to_run = []

    if args.all:
        benchmarks_to_run = list(BENCHMARKS.keys())
    elif args.benchmark:
        benchmarks_to_run = [args.benchmark]

    t_start = time.time()

    for bench_name in benchmarks_to_run:
        bench_fn = BENCHMARKS[bench_name]
        try:
            result = bench_fn(model, tokenizer, device, n=args.samples)
            results[bench_name] = result
        except Exception as e:
            print(f"\n  [ERROR] {bench_name} failed: {e}")
            import traceback
            traceback.print_exc()
            results[bench_name] = {"error": str(e)}

    elapsed = time.time() - t_start

    # Summary
    if results:
        print_summary(results)
        print(f"\nTotal evaluation time: {elapsed:.1f}s")
        save_results(results)


if __name__ == "__main__":
    main()
