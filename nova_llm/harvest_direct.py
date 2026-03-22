"""
Direct harvester: uses OpenAI API directly (bypasses Cloud Router).
Faster and more reliable when free-tier providers are rate-limited.
Saves incrementally every 5 pairs.
"""
import json, time, urllib.request, os

with open("C:/NovaX/cloud_config.json", "r") as _f:
    API_KEY = json.load(_f)["openai"]["key"]
URL = "https://api.openai.com/v1/chat/completions"
OUT = "C:/NovaX/data/llm_training/training_pairs_mega.json"
MODEL = "gpt-4o-mini"  # cheap, fast, good quality

# Import prompts from main harvester
from harvest_for_training import PROMPTS

def query(prompt):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.7
    }).encode()
    req = urllib.request.Request(URL, body, {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    })
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"]
        return text, "openai", MODEL
    except Exception as e:
        return "", "error", str(e)

def save(pairs):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(pairs, f, ensure_ascii=False)

def main():
    if not API_KEY:
        print("ERROR: OPENAI_API_KEY not set")
        return

    with open(OUT, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    existing = {p.get("prompt", "")[:80] for p in pairs}

    new_prompts = [p for p in PROMPTS if p[:80] not in existing]
    print(f"Existing: {len(pairs)} pairs")
    print(f"New prompts: {len(new_prompts)}")
    print(f"Using: {MODEL}")

    added = 0
    fails = 0
    for i, prompt in enumerate(new_prompts):
        text, provider, model = query(prompt)
        if len(text) < 20:
            fails += 1
            print(f"  [{i+1}/{len(new_prompts)}] FAIL: {prompt[:50]}")
            if fails > 5:
                print("Too many failures, stopping")
                break
            continue

        pairs.append({
            "prompt": prompt,
            "response": text,
            "domain": "harvested_v2",
            "provider": provider,
            "model": model
        })
        added += 1
        fails = 0
        print(f"  [{i+1}/{len(new_prompts)}] OK ({len(text)} chars): {prompt[:50]}")

        if added % 5 == 0:
            save(pairs)
            total_chars = sum(len(p.get("prompt",""))+len(p.get("response","")) for p in pairs)
            print(f"  ** Saved: {len(pairs)} pairs, {total_chars/1e6:.1f}M chars **")

        time.sleep(0.2)  # Stay under rate limits

    save(pairs)
    total_chars = sum(len(p.get("prompt",""))+len(p.get("response","")) for p in pairs)
    print(f"\nDone: +{added} new pairs, {len(pairs)} total, {total_chars:,} chars ({total_chars/1e6:.1f}M)")

if __name__ == "__main__":
    main()
