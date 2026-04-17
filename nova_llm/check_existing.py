import json
d = json.load(open("C:/NovaX/data/llm_training/training_pairs_mega.json", "r", encoding="utf-8"))
print("Total pairs:", len(d))
if d:
    print("Sample keys:", list(d[0].keys()))
    print("First prompt:", d[0].get("prompt", "")[:80])
    sources = {}
    for p in d:
        s = p.get("source", p.get("provider", "unknown"))
        sources[s] = sources.get(s, 0) + 1
    print("By source:", sources)
