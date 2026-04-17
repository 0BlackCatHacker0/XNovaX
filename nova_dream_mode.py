"""
NovaX Dream Mode v1.0 -- Autonomous Self-Improvement System
============================================================
Runs on port 9940. When GPU is idle, autonomously:
  1. Generates training data via Ollama data factory
  2. Filters and deduplicates new pairs
  3. Evaluates model weaknesses on benchmark prompts
  4. Retrains when 1000+ new pairs accumulated
  5. Logs everything to data/dream_journal.json

Dream States:
  AWAKE      - Idle, waiting for conditions
  DREAMING   - Generating/filtering/evaluating
  DEEP_DREAM - Training active

Endpoints:
  GET  /health         - Service health check
  POST /dream/start    - Begin dream cycle
  POST /dream/stop     - Stop dream cycle
  GET  /dream/status   - Current state + phase info
  GET  /dream/journal  - Full dream journal

Port: 9940
"""

import json
import os
import subprocess
import sys
import hashlib
import threading
import time
import traceback
import urllib.request
import urllib.error
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

class DreamConfig:
    """All tunable parameters for Dream Mode."""

    # Service
    PORT = 9940
    HOST = "127.0.0.1"

    # Paths
    BASE_DIR = Path("C:/NovaX")
    LLM_DIR = BASE_DIR / "nova_llm"
    DATA_DIR = BASE_DIR / "data" / "llm_training"
    JOURNAL_PATH = BASE_DIR / "data" / "dream_journal.json"
    STATE_PATH = BASE_DIR / "data" / "dream_state.json"
    TRAINING_PAIRS = DATA_DIR / "training_pairs_mega.json"
    FILTERED_PAIRS = DATA_DIR / "training_pairs_filtered.json"
    CHECKPOINT_DIR = LLM_DIR / "checkpoints"
    BENCHMARK_RESULTS = DATA_DIR / "benchmark_results.json"

    # Scripts
    DATA_FACTORY_SCRIPT = LLM_DIR / "ollama_data_factory.py"
    QUALITY_FILTER_SCRIPT = LLM_DIR / "data_quality_filter.py"
    TRAIN_SCRIPT = LLM_DIR / "train.py"

    # Ollama
    OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
    OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"

    # Orchestrator
    ORCHESTRATOR_URL = "http://127.0.0.1:9999"

    # Phase durations (seconds)
    GENERATE_DURATION = 1800       # 30 min generating data
    GENERATE_BATCH_SIZE = 50       # pairs per generation batch
    FILTER_TIMEOUT = 120           # 2 min for filtering
    EVALUATE_TIMEOUT = 300         # 5 min for evaluation
    TRAIN_TIMEOUT = 7200           # 2 hours max for training
    SLEEP_BETWEEN_CYCLES = 300     # 5 min sleep between cycles
    GPU_CHECK_INTERVAL = 30        # check GPU every 30s

    # Thresholds
    MIN_NEW_PAIRS_FOR_TRAINING = 1000
    GPU_IDLE_THRESHOLD_MB = 1500   # GPU memory usage below this = idle
    GPU_UTIL_THRESHOLD = 15        # GPU utilization below this % = idle

    # Benchmark categories
    BENCHMARK_CATEGORIES = [
        "math", "coding", "science", "reasoning",
        "creative_writing", "tool_use", "ternary",
    ]

    # Benchmark prompts per category
    BENCHMARK_PROMPTS = {
        "math": [
            "What is the derivative of x^3 * sin(x)?",
            "Solve: 2x + 5 = 17",
            "What is 243 in base 3?",
        ],
        "coding": [
            "Write a Python function to find the longest common subsequence of two strings.",
            "Explain what a hash table is and implement one in Python.",
            "What is the time complexity of merge sort and why?",
        ],
        "science": [
            "Explain how CRISPR gene editing works.",
            "What is the difference between nuclear fission and fusion?",
            "Describe the Standard Model of particle physics.",
        ],
        "reasoning": [
            "If all roses are flowers and some flowers fade quickly, can we conclude all roses fade quickly?",
            "A bat and ball cost $1.10 total. The bat costs $1 more than the ball. How much is the ball?",
            "Three switches control three light bulbs in another room. How do you determine which switch controls which bulb with one trip?",
        ],
        "creative_writing": [
            "Write a haiku about artificial intelligence.",
            "Create a short story opening about a city that exists in two dimensions simultaneously.",
            "Write a persuasive paragraph about why ternary computing could surpass binary.",
        ],
        "tool_use": [
            "Given a function search(query) that returns results, how would you find information about quantum computing?",
            "Describe how you would use an API to fetch weather data and parse the JSON response.",
            "Explain how to chain multiple tool calls to accomplish a complex task.",
        ],
        "ternary": [
            "Explain balanced ternary number representation.",
            "What advantages does ternary logic have over binary?",
            "Convert the decimal number 42 to balanced ternary.",
        ],
    }


# ============================================================
# DREAM STATES
# ============================================================

class DreamState:
    AWAKE = "AWAKE"
    DREAMING = "DREAMING"
    DEEP_DREAM = "DEEP_DREAM"


class DreamPhase:
    IDLE = "idle"
    CHECKING_GPU = "checking_gpu"
    GENERATING = "generating"
    FILTERING = "filtering"
    EVALUATING = "evaluating"
    TRAINING = "training"
    SLEEPING = "sleeping"


# ============================================================
# GPU MONITOR
# ============================================================

class GPUMonitor:
    """Check GPU availability via nvidia-smi."""

    @staticmethod
    def get_gpu_stats():
        """Returns dict with gpu_util (%), memory_used (MB), memory_total (MB)."""
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return None
            line = result.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            return {
                "gpu_util": int(parts[0]),
                "memory_used": int(parts[1]),
                "memory_total": int(parts[2]),
            }
        except Exception:
            return None

    @staticmethod
    def is_gpu_idle(config=None):
        """Returns True if GPU is idle enough for dream work."""
        if config is None:
            config = DreamConfig
        stats = GPUMonitor.get_gpu_stats()
        if stats is None:
            return False
        return (stats["gpu_util"] < config.GPU_UTIL_THRESHOLD and
                stats["memory_used"] < config.GPU_IDLE_THRESHOLD_MB)

    @staticmethod
    def is_gpu_available_for_training(config=None):
        """Stricter check for training - GPU must be very idle."""
        if config is None:
            config = DreamConfig
        stats = GPUMonitor.get_gpu_stats()
        if stats is None:
            return False
        return (stats["gpu_util"] < 5 and
                stats["memory_used"] < 800)


# ============================================================
# ORCHESTRATOR CHECKER
# ============================================================

class OrchestratorChecker:
    """Check if user is actively using the system."""

    @staticmethod
    def is_user_active():
        """Check orchestrator for recent activity."""
        try:
            req = urllib.request.Request(
                DreamConfig.ORCHESTRATOR_URL + "/api/services/health",
                method="GET"
            )
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                # If orchestrator is responding, check for active sessions
                # A simple heuristic: if many services are busy, user is active
                active_count = sum(
                    1 for s in data.get("services", {}).values()
                    if isinstance(s, dict) and s.get("status") == "busy"
                )
                return active_count > 3
        except Exception:
            # If orchestrator is down, assume user is not active
            return False


# ============================================================
# DREAM JOURNAL
# ============================================================

class DreamJournal:
    """Persistent log of all dream activities."""

    def __init__(self, path=None):
        self.path = path or DreamConfig.JOURNAL_PATH
        self.entries = []
        self._load()

    def _load(self):
        """Load existing journal from disk."""
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.entries = data.get("entries", [])
        except Exception:
            self.entries = []

    def _save(self):
        """Save journal to disk."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "total_entries": len(self.entries),
                "entries": self.entries,
            }
            tmp_path = self.path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            # Path.replace() == os.replace() — ATOMIC on Windows.
            # Previous unlink+rename had a crash window where the file was missing.
            tmp_path.replace(self.path)
        except Exception as e:
            print(f"[DREAM] Journal save error: {e}")

    def log(self, phase, message, details=None):
        """Add an entry to the journal."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "message": message,
        }
        if details:
            entry["details"] = details
        self.entries.append(entry)
        self._save()
        # Also print to console
        print(f"[DREAM][{phase.upper()}] {message}")

    def get_recent(self, count=50):
        """Get the most recent entries."""
        return self.entries[-count:]

    def get_all(self):
        """Get all entries."""
        return self.entries

    def get_stats(self):
        """Get summary statistics."""
        if not self.entries:
            return {"total_entries": 0}
        phases = {}
        for e in self.entries:
            p = e.get("phase", "unknown")
            phases[p] = phases.get(p, 0) + 1
        return {
            "total_entries": len(self.entries),
            "first_entry": self.entries[0].get("timestamp"),
            "last_entry": self.entries[-1].get("timestamp"),
            "phases": phases,
        }


# ============================================================
# DREAM ENGINE
# ============================================================

class DreamEngine:
    """Core autonomous self-improvement engine."""

    def __init__(self, config=None):
        self.config = config or DreamConfig
        self.journal = DreamJournal(self.config.JOURNAL_PATH)
        self.state = DreamState.AWAKE
        self.phase = DreamPhase.IDLE
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.cycle_count = 0
        self.pairs_generated_total = 0
        self.pairs_filtered_total = 0
        self.training_runs = 0
        self.current_phase_start = None
        self.last_error = None
        self.stop_requested = False
        self._initial_pair_count = 0

        # Resume state from disk
        self._load_state()

    def _load_state(self):
        """Load persistent state for crash recovery."""
        try:
            if self.config.STATE_PATH.exists():
                with open(self.config.STATE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.cycle_count = data.get("cycle_count", 0)
                self.pairs_generated_total = data.get("pairs_generated_total", 0)
                self.pairs_filtered_total = data.get("pairs_filtered_total", 0)
                self.training_runs = data.get("training_runs", 0)
                print(f"[DREAM] Resumed state: {self.cycle_count} cycles, "
                      f"{self.pairs_generated_total} pairs generated")
        except Exception:
            pass

    def _save_state(self):
        """Save persistent state for crash recovery."""
        try:
            data = {
                "cycle_count": self.cycle_count,
                "pairs_generated_total": self.pairs_generated_total,
                "pairs_filtered_total": self.pairs_filtered_total,
                "training_runs": self.training_runs,
                "last_save": datetime.now().isoformat(),
                "state": self.state,
                "phase": self.phase,
            }
            self.config.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config.STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[DREAM] State save error: {e}")

    def _set_phase(self, phase):
        """Update current phase."""
        self.phase = phase
        self.current_phase_start = time.time()
        self._save_state()

    def _count_training_pairs(self):
        """Count current number of training pairs."""
        try:
            if self.config.TRAINING_PAIRS.exists():
                with open(self.config.TRAINING_PAIRS, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return len(data)
            return 0
        except Exception:
            return 0

    # ── Phase 1: Generate Training Data ──

    def _phase_generate(self):
        """Generate training data using Ollama data factory."""
        self._set_phase(DreamPhase.GENERATING)
        self.journal.log("generate", "Starting data generation phase")

        count_before = self._count_training_pairs()
        self._initial_pair_count = count_before

        try:
            # Check if Ollama is available
            try:
                req = urllib.request.Request(self.config.OLLAMA_TAGS_URL)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    tags_data = json.loads(resp.read().decode())
                    model_count = len(tags_data.get("models", []))
                    self.journal.log("generate",
                                    f"Ollama online with {model_count} models")
            except Exception as e:
                self.journal.log("generate",
                                f"Ollama not available: {e} -- skipping generation")
                return 0

            # Run the data factory as a subprocess with timeout
            script = str(self.config.DATA_FACTORY_SCRIPT)
            if not os.path.exists(script):
                self.journal.log("generate",
                                f"Data factory script not found: {script}")
                return 0

            python_exe = sys.executable
            self.journal.log("generate",
                             f"Running data factory for {self.config.GENERATE_DURATION}s")

            proc = subprocess.Popen(
                [python_exe, script,
                 "--batch-size", str(self.config.GENERATE_BATCH_SIZE)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.config.LLM_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            # Let it run for the configured duration, checking stop flag
            start_time = time.time()
            while time.time() - start_time < self.config.GENERATE_DURATION:
                if self.stop_requested:
                    proc.terminate()
                    self.journal.log("generate", "Generation stopped by user")
                    return 0
                if proc.poll() is not None:
                    break
                if not GPUMonitor.is_gpu_idle(self.config):
                    proc.terminate()
                    self.journal.log("generate",
                                    "GPU became busy -- stopping generation")
                    break
                time.sleep(10)

            # If still running after timeout, terminate
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()

            count_after = self._count_training_pairs()
            new_pairs = count_after - count_before
            self.pairs_generated_total += max(0, new_pairs)

            self.journal.log("generate",
                             f"Generation complete: {new_pairs} new pairs "
                             f"(total: {count_after})",
                             {"before": count_before, "after": count_after})
            return new_pairs

        except Exception as e:
            self.journal.log("generate", f"Generation error: {e}")
            self.last_error = str(e)
            return 0

    # ── Phase 2: Filter and Deduplicate ──

    def _phase_filter(self):
        """Run data quality filter on training pairs."""
        self._set_phase(DreamPhase.FILTERING)
        self.journal.log("filter", "Starting data filtering phase")

        try:
            script = str(self.config.QUALITY_FILTER_SCRIPT)
            if not os.path.exists(script):
                self.journal.log("filter",
                                f"Quality filter script not found: {script}")
                return False

            python_exe = sys.executable
            proc = subprocess.run(
                [python_exe, script, "--save"],
                capture_output=True, text=True,
                timeout=self.config.FILTER_TIMEOUT,
                cwd=str(self.config.LLM_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            output = proc.stdout[-500:] if proc.stdout else ""
            err = proc.stderr[-500:] if proc.stderr else ""

            if proc.returncode == 0:
                self.journal.log("filter", "Filtering complete",
                                {"output": output})
                return True
            else:
                self.journal.log("filter",
                                f"Filter returned code {proc.returncode}",
                                {"stderr": err})
                return False

        except subprocess.TimeoutExpired:
            self.journal.log("filter", "Filter timed out")
            return False
        except Exception as e:
            self.journal.log("filter", f"Filter error: {e}")
            self.last_error = str(e)
            return False

    # ── Phase 3: Evaluate Model Weaknesses ──

    def _phase_evaluate(self):
        """Run benchmark prompts to identify weak categories."""
        self._set_phase(DreamPhase.EVALUATING)
        self.journal.log("evaluate", "Starting model evaluation phase")

        results = {}
        total_score = 0
        total_prompts = 0

        try:
            for category, prompts in self.config.BENCHMARK_PROMPTS.items():
                if self.stop_requested:
                    break

                cat_scores = []
                for prompt in prompts:
                    if self.stop_requested:
                        break

                    score = self._evaluate_single(prompt)
                    cat_scores.append(score)
                    total_prompts += 1

                avg = sum(cat_scores) / len(cat_scores) if cat_scores else 0
                results[category] = {
                    "average_score": round(avg, 3),
                    "individual": cat_scores,
                    "prompt_count": len(cat_scores),
                }
                total_score += avg

            # Identify weakest categories
            sorted_cats = sorted(results.items(),
                                 key=lambda x: x[1]["average_score"])
            weakest = [c[0] for c in sorted_cats[:3]]

            overall_avg = total_score / len(results) if results else 0

            eval_report = {
                "timestamp": datetime.now().isoformat(),
                "overall_score": round(overall_avg, 3),
                "categories": results,
                "weakest_categories": weakest,
                "total_prompts_evaluated": total_prompts,
            }

            # Save benchmark results
            try:
                self.config.BENCHMARK_RESULTS.parent.mkdir(
                    parents=True, exist_ok=True)
                with open(self.config.BENCHMARK_RESULTS, "w",
                          encoding="utf-8") as f:
                    json.dump(eval_report, f, indent=2)
            except Exception:
                pass

            self.journal.log("evaluate",
                             f"Evaluation complete: overall={overall_avg:.3f}, "
                             f"weakest={weakest}",
                             {"report_summary": {
                                 "overall": round(overall_avg, 3),
                                 "weakest": weakest,
                             }})

            return eval_report

        except Exception as e:
            self.journal.log("evaluate", f"Evaluation error: {e}")
            self.last_error = str(e)
            return None

    def _evaluate_single(self, prompt):
        """Evaluate a single prompt using the NovaX LLM inference server.

        Score 0.0-1.0 based on response quality heuristics:
        - Response length (longer = more thorough, up to a point)
        - Contains structured elements (code blocks, lists, etc.)
        - Does not contain error indicators
        """
        try:
            # Try the NovaX inference server first (port 9885)
            payload = json.dumps({
                "prompt": prompt,
                "max_tokens": 512,
            }).encode()

            req = urllib.request.Request(
                "http://127.0.0.1:9885/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
                    response_text = data.get("response", data.get("text", ""))
            except Exception:
                # Fall back to Ollama directly
                ollama_payload = json.dumps({
                    "model": "llama3:latest",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 256},
                }).encode()
                req = urllib.request.Request(
                    self.config.OLLAMA_URL,
                    data=ollama_payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode())
                    response_text = data.get("response", "")

            if not response_text:
                return 0.0

            # Heuristic scoring
            score = 0.0

            # Length score (0-0.3): reward up to 500 chars
            length = len(response_text)
            score += min(length / 500.0, 1.0) * 0.3

            # Structure score (0-0.3): code blocks, lists, paragraphs
            has_code = "```" in response_text or "def " in response_text
            has_list = any(response_text.count(m) >= 2
                          for m in ["- ", "* ", "1. ", "2. "])
            has_paragraphs = response_text.count("\n\n") >= 1
            structure_points = sum([has_code, has_list, has_paragraphs])
            score += (structure_points / 3.0) * 0.3

            # Coherence score (0-0.2): no error markers
            error_markers = ["error", "cannot", "sorry", "i don't",
                             "i can't", "as an ai"]
            lower = response_text.lower()
            error_count = sum(1 for m in error_markers if m in lower)
            score += max(0, 0.2 - (error_count * 0.05))

            # Relevance score (0-0.2): prompt keywords appear in response
            prompt_words = set(prompt.lower().split())
            response_words = set(lower.split())
            overlap = len(prompt_words & response_words)
            score += min(overlap / max(len(prompt_words), 1), 1.0) * 0.2

            return round(min(score, 1.0), 3)

        except Exception:
            return 0.0

    # ── Phase 4: Retrain ──

    def _phase_retrain(self):
        """Trigger training if enough new pairs have accumulated."""
        self._set_phase(DreamPhase.TRAINING)

        current_count = self._count_training_pairs()
        new_since_start = current_count - self._initial_pair_count

        if new_since_start < self.config.MIN_NEW_PAIRS_FOR_TRAINING:
            self.journal.log("train",
                             f"Not enough new pairs for training: "
                             f"{new_since_start}/{self.config.MIN_NEW_PAIRS_FOR_TRAINING}")
            return False

        # Final GPU check before committing to training
        if not GPUMonitor.is_gpu_available_for_training(self.config):
            self.journal.log("train", "GPU not available for training")
            return False

        if OrchestratorChecker.is_user_active():
            self.journal.log("train",
                             "User is active -- deferring training")
            return False

        self.journal.log("train",
                         f"Starting training with {current_count} total pairs "
                         f"({new_since_start} new)")

        self.state = DreamState.DEEP_DREAM

        try:
            script = str(self.config.TRAIN_SCRIPT)
            if not os.path.exists(script):
                self.journal.log("train",
                                f"Train script not found: {script}")
                return False

            python_exe = sys.executable
            proc = subprocess.Popen(
                [python_exe, script, "--resume"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.config.LLM_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            # Monitor training
            start_time = time.time()
            while time.time() - start_time < self.config.TRAIN_TIMEOUT:
                if self.stop_requested:
                    proc.terminate()
                    self.journal.log("train", "Training stopped by user")
                    self.state = DreamState.DREAMING
                    return False
                if proc.poll() is not None:
                    break
                # Check if user became active
                if OrchestratorChecker.is_user_active():
                    proc.terminate()
                    self.journal.log("train",
                                    "User became active -- pausing training")
                    self.state = DreamState.DREAMING
                    return False
                time.sleep(30)

            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()

            returncode = proc.returncode
            self.state = DreamState.DREAMING

            if returncode == 0:
                self.training_runs += 1
                self.journal.log("train",
                                 f"Training complete (run #{self.training_runs})",
                                 {"duration_s": int(time.time() - start_time)})
                return True
            else:
                stderr_tail = ""
                try:
                    stderr_tail = proc.stderr.read().decode()[-500:]
                except Exception:
                    pass
                self.journal.log("train",
                                 f"Training exited with code {returncode}",
                                 {"stderr": stderr_tail})
                return False

        except Exception as e:
            self.state = DreamState.DREAMING
            self.journal.log("train", f"Training error: {e}")
            self.last_error = str(e)
            return False

    # ── Main Dream Cycle ──

    def _dream_cycle(self):
        """Run one complete dream cycle: generate -> filter -> evaluate -> retrain."""
        self.cycle_count += 1
        cycle_start = time.time()

        self.journal.log("cycle",
                         f"--- Dream cycle #{self.cycle_count} starting ---")

        # Phase 1: Generate
        if not self.stop_requested:
            new_pairs = self._phase_generate()
        else:
            new_pairs = 0

        # Phase 2: Filter
        if not self.stop_requested and new_pairs > 0:
            self._phase_filter()

        # Phase 3: Evaluate
        if not self.stop_requested:
            self._phase_evaluate()

        # Phase 4: Retrain (only if enough data)
        if not self.stop_requested:
            self._phase_retrain()

        cycle_duration = int(time.time() - cycle_start)
        self.journal.log("cycle",
                         f"--- Dream cycle #{self.cycle_count} complete "
                         f"({cycle_duration}s) ---",
                         {"duration_s": cycle_duration,
                          "new_pairs": new_pairs})

        self._save_state()

    def _dream_loop(self):
        """Main loop: check conditions -> dream cycle -> sleep -> repeat."""
        self.journal.log("system", "Dream Mode engine started")

        while self.running and not self.stop_requested:
            try:
                # Check preconditions
                self._set_phase(DreamPhase.CHECKING_GPU)

                if not GPUMonitor.is_gpu_idle(self.config):
                    self.journal.log("system", "GPU busy -- waiting")
                    self._wait_with_check(self.config.GPU_CHECK_INTERVAL)
                    continue

                if OrchestratorChecker.is_user_active():
                    self.journal.log("system", "User active -- waiting")
                    self._wait_with_check(self.config.GPU_CHECK_INTERVAL)
                    continue

                # All clear -- run a dream cycle
                self.state = DreamState.DREAMING
                self._dream_cycle()

                # Sleep between cycles
                if self.running and not self.stop_requested:
                    self._set_phase(DreamPhase.SLEEPING)
                    self.state = DreamState.AWAKE
                    self.journal.log("system",
                                     f"Sleeping {self.config.SLEEP_BETWEEN_CYCLES}s "
                                     f"before next cycle")
                    self._wait_with_check(self.config.SLEEP_BETWEEN_CYCLES)

            except Exception as e:
                self.journal.log("error", f"Dream loop error: {e}",
                                {"traceback": traceback.format_exc()})
                self.last_error = str(e)
                self._wait_with_check(60)

        self.state = DreamState.AWAKE
        self._set_phase(DreamPhase.IDLE)
        self.journal.log("system", "Dream Mode engine stopped")
        self._save_state()

    def _wait_with_check(self, seconds):
        """Sleep for N seconds, checking stop flag every second."""
        for _ in range(int(seconds)):
            if self.stop_requested or not self.running:
                return
            time.sleep(1)

    def start(self):
        """Start the dream engine."""
        with self.lock:
            if self.running:
                return {"status": "already_running"}

            self.running = True
            self.stop_requested = False
            self.state = DreamState.AWAKE
            self._set_phase(DreamPhase.CHECKING_GPU)
            self._initial_pair_count = self._count_training_pairs()

            self.thread = threading.Thread(
                target=self._dream_loop, daemon=True, name="DreamEngine"
            )
            self.thread.start()

            self.journal.log("system", "Dream Mode started by user")
            return {"status": "started"}

    def stop(self):
        """Stop the dream engine gracefully."""
        with self.lock:
            if not self.running:
                return {"status": "already_stopped"}

            self.stop_requested = True
            self.running = False
            self.journal.log("system", "Dream Mode stop requested")

            return {"status": "stopping"}

    def get_status(self):
        """Get current dream status."""
        phase_elapsed = 0
        if self.current_phase_start:
            phase_elapsed = int(time.time() - self.current_phase_start)

        gpu_stats = GPUMonitor.get_gpu_stats()

        return {
            "state": self.state,
            "phase": self.phase,
            "running": self.running,
            "cycle_count": self.cycle_count,
            "pairs_generated_total": self.pairs_generated_total,
            "pairs_filtered_total": self.pairs_filtered_total,
            "training_runs": self.training_runs,
            "phase_elapsed_s": phase_elapsed,
            "current_pair_count": self._count_training_pairs(),
            "gpu": gpu_stats,
            "last_error": self.last_error,
        }


# ============================================================
# HTTP SERVER
# ============================================================

class DreamHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Dream Mode endpoints."""

    engine = None  # Set by main()

    def log_message(self, format, *args):
        """Override to use our format."""
        print(f"[DREAM][HTTP] {args[0]} {args[1]} {args[2]}")

    def _send_json(self, data, status=200):
        """Send a JSON response."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:9999")
        self.send_header("Access-Control-Allow-Methods",
                         "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:9999")
        self.send_header("Access-Control-Allow-Methods",
                         "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        path = self.path.split("?")[0]

        if path == "/health":
            self._send_json({
                "service": "nova_dream_mode",
                "status": "running",
                "port": DreamConfig.PORT,
                "state": self.engine.state if self.engine else "no_engine",
                "version": "1.0",
            })

        elif path == "/dream/status":
            if self.engine:
                self._send_json(self.engine.get_status())
            else:
                self._send_json({"error": "engine not initialized"}, 500)

        elif path == "/dream/journal":
            if self.engine:
                journal = self.engine.journal
                self._send_json({
                    "stats": journal.get_stats(),
                    "entries": journal.get_all(),
                })
            else:
                self._send_json({"error": "engine not initialized"}, 500)

        elif path == "/dream/journal/recent":
            if self.engine:
                self._send_json({
                    "entries": self.engine.journal.get_recent(20),
                })
            else:
                self._send_json({"error": "engine not initialized"}, 500)

        else:
            self._send_json({"error": "not found", "path": path}, 404)

    def do_POST(self):
        """Handle POST requests."""
        path = self.path.split("?")[0]

        if path == "/dream/start":
            if self.engine:
                result = self.engine.start()
                self._send_json(result)
            else:
                self._send_json({"error": "engine not initialized"}, 500)

        elif path == "/dream/stop":
            if self.engine:
                result = self.engine.stop()
                self._send_json(result)
            else:
                self._send_json({"error": "engine not initialized"}, 500)

        else:
            self._send_json({"error": "not found", "path": path}, 404)


# ============================================================
# MAIN
# ============================================================

def main():
    config = DreamConfig()
    engine = DreamEngine(config)
    DreamHandler.engine = engine

    server = HTTPServer((config.HOST, config.PORT), DreamHandler)
    print(f"[DREAM] NovaX Dream Mode v1.0")
    print(f"[DREAM] Listening on {config.HOST}:{config.PORT}")
    print(f"[DREAM] Endpoints:")
    print(f"[DREAM]   GET  /health")
    print(f"[DREAM]   POST /dream/start")
    print(f"[DREAM]   POST /dream/stop")
    print(f"[DREAM]   GET  /dream/status")
    print(f"[DREAM]   GET  /dream/journal")
    print(f"[DREAM]   GET  /dream/journal/recent")
    print(f"[DREAM] State file: {config.STATE_PATH}")
    print(f"[DREAM] Journal: {config.JOURNAL_PATH}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[DREAM] Shutting down...")
        engine.stop()
        server.shutdown()
        print("[DREAM] Goodbye.")


if __name__ == "__main__":
    main()
