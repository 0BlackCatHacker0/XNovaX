"""
NovaX LLM Training Monitor — Live status bar
Run: python train_monitor.py
"""
import json, time, os, sys

LOG = os.path.join(os.path.dirname(__file__), "training_log.json")
REFRESH = 5  # seconds

def bar(pct, width=30):
    filled = int(width * pct / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

prev_step = -1
while True:
    try:
        with open(LOG, "r") as f:
            log = json.load(f)
        if not log:
            print("Waiting for training to start...")
            time.sleep(REFRESH)
            continue

        last = log[-1]
        step = last.get("step", 0)
        total = 20000
        loss = last.get("loss", 0)
        ppl = last.get("perplexity", 0)
        sps = last.get("steps_per_sec", 0)
        epoch = last.get("epoch", 0)
        lr = last.get("lr", 0)
        elapsed = last.get("elapsed_sec", 0)

        pct = step / total * 100
        eta_sec = (total - step) / max(sps, 0.001)
        eta_h = int(eta_sec // 3600)
        eta_m = int((eta_sec % 3600) // 60)
        tok_s = sps * 12 * 512

        # Loss trend
        recent = log[-5:] if len(log) >= 5 else log
        trend = " > ".join(f"{e['loss']:.2f}" for e in recent)

        clear()
        print("=" * 60)
        print("  NovaX LLM Training Monitor")
        print("=" * 60)
        print(f"  {bar(pct)} {pct:5.1f}%")
        print(f"  Step:    {step:,} / {total:,}")
        print(f"  Loss:    {loss:.4f}")
        print(f"  PPL:     {ppl:,.2f}")
        print(f"  Speed:   {sps:.2f} steps/s ({tok_s:.0f} tok/s)")
        print(f"  LR:      {lr:.6f}")
        print(f"  Epoch:   {epoch}")
        print(f"  ETA:     {eta_h}h {eta_m}m")
        print(f"  Elapsed: {int(elapsed//3600)}h {int((elapsed%3600)//60)}m")
        print(f"  Trend:   {trend}")
        print("=" * 60)
        print("  Ctrl+C to exit monitor (training continues)")

        if step >= total:
            print("\n  TRAINING COMPLETE!")
            break

        prev_step = step
    except Exception as e:
        print(f"  Waiting... ({e})")

    time.sleep(REFRESH)
