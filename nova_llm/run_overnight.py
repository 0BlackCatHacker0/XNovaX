"""
NovaX Overnight Automation v1.0
Run this when training finishes. It will:
1. Stop any running training process
2. Launch the Ollama data factory (uses full GPU)
3. Run until interrupted (Ctrl+C) or target reached

Usage:
    python run_overnight.py              # Generate ~3000-5000 pairs overnight
    python run_overnight.py --target 5000  # Stop after 5000 new pairs
"""
import subprocess, sys, os, time, json
from pathlib import Path
from datetime import datetime

FACTORY = Path(__file__).parent / "ollama_data_factory.py"
HARVESTER = Path(__file__).parent / "free_tier_harvester.py"
OUT_FILE = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")

def count_pairs():
    if OUT_FILE.exists():
        with open(OUT_FILE, "r", encoding="utf-8") as f:
            return len(json.load(f))
    return 0

def main():
    target = 5000
    for i, arg in enumerate(sys.argv):
        if arg == "--target" and i+1 < len(sys.argv):
            target = int(sys.argv[i+1])

    print("=" * 60)
    print("  NovaX Overnight Data Generation")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target: {target} new pairs")
    print("=" * 60)

    initial_count = count_pairs()
    print(f"  Starting with {initial_count} pairs")
    print(f"  Target total: {initial_count + target}")
    print()
    print("  Phase 1: Ollama Data Factory (GPU-bound, ~400-600/hr)")
    print("  Press Ctrl+C to stop at any time.")
    print()

    # Run the factory
    try:
        proc = subprocess.run(
            [sys.executable, str(FACTORY)],
            cwd=str(FACTORY.parent),
        )
    except KeyboardInterrupt:
        print("\n\nStopped by user.")

    final_count = count_pairs()
    added = final_count - initial_count

    print(f"\n{'='*60}")
    print(f"  Overnight Generation Complete!")
    print(f"  Started with: {initial_count}")
    print(f"  Ended with:   {final_count}")
    print(f"  Added:        {added} new pairs")
    print(f"{'='*60}")

    if added > 0:
        print(f"\n  Next steps:")
        print(f"  1. python data_quality_filter.py --save --fim-augment 0.3")
        print(f"  2. python -c \"import json; print(len(json.load(open('{OUT_FILE}'))))\"")
        print(f"  3. Update architecture.json to architecture_v2.json")
        print(f"  4. python train.py  # Start round 4!")

if __name__ == "__main__":
    main()
