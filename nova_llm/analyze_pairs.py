"""Quick analysis of current training data."""
import json

d = json.load(open('C:/NovaX/data/llm_training/training_pairs_mega.json', encoding='utf-8'))
domains = {}
for p in d:
    dom = p.get('domain', 'unknown')
    domains[dom] = domains.get(dom, 0) + 1

print("=== Domain Distribution ===")
for k, v in sorted(domains.items(), key=lambda x: -x[1])[:15]:
    print(f"  {k}: {v}")

print(f"\nTotal pairs: {len(d)}")
print(f"Avg prompt len: {sum(len(p.get('prompt','')) for p in d) // len(d)}")
print(f"Avg response len: {sum(len(p.get('response','')) for p in d) // len(d)}")

# Show 3 samples
for i in [0, len(d)//2, len(d)-1]:
    print(f"\n--- Sample {i} ---")
    print(f"  Domain: {d[i].get('domain')}")
    print(f"  Prompt: {d[i].get('prompt','')[:150]}")
    print(f"  Response: {d[i].get('response','')[:150]}")
