"""Test keep_alive speedup - run two queries, compare times."""
import json, time, urllib.request

URL = "http://127.0.0.1:11434/api/generate"

def timed_query(prompt, model):
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "24h",
        "options": {"num_predict": 10}
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(URL, data, {"Content-Type": "application/json"})
    t0 = time.time()
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    elapsed = time.time() - t0
    return elapsed, result.get("response", "")[:40]

model = "qwen2.5:latest"
print("Query 1 (may cold-load model)...")
t1, r1 = timed_query("Say hello", model)
print("  Time: %.1fs  Response: %s" % (t1, r1))

print("Query 2 (model should be cached in VRAM)...")
t2, r2 = timed_query("Say goodbye", model)
print("  Time: %.1fs  Response: %s" % (t2, r2))

print("\nSpeedup: %.1fs -> %.1fs" % (t1, t2))
if t2 < 5:
    print("SUCCESS: keep_alive working - model stays in VRAM!")
else:
    print("NOTE: Model may need more VRAM or was already cached")
