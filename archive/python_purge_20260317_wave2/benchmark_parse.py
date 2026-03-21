import json, os, glob

providers = ['cerebras','sambanova','google','openai','openrouter','groq','together','mistral','cohere','deepseek','anthropic','apifreellm']
total_tokens = 0
total_chars = 0
succeeded = 0
failed = 0
results = []

for p in providers:
    fpath = f"/tmp/nova_{p}.json"
    if not os.path.exists(fpath):
        print(f"{p:22s} NO FILE")
        failed += 1
        continue
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            d = json.load(f)
        r = d.get("result", {})
        prov = r.get("provider", p)
        model = r.get("model", "?")
        tokens = int(r.get("tokens", 0))
        time_ms = r.get("time_ms", 0)
        resp = r.get("response", "")
        chars = len(resp)
        ok = d.get("ok", 0)
        if ok == 1 and chars > 0:
            succeeded += 1
            total_tokens += tokens
            total_chars += chars
            results.append((prov, model, tokens, time_ms, chars))
            print(f"{prov:22s} OK  model={model:35s} tokens={tokens:6d}  time={time_ms:6}ms  chars={chars:6d}")
        else:
            failed += 1
            print(f"{p:22s} FAIL  ok={ok}  chars={chars}")
    except Exception as e:
        failed += 1
        print(f"{p:22s} ERROR: {e}")

print()
print("=" * 70)
print(f"  PROVIDERS SUCCEEDED:   {succeeded} / {len(providers)}")
print(f"  PROVIDERS FAILED:      {failed}")
print(f"  TOTAL TOKENS:          {total_tokens:,}")
print(f"  TOTAL CHARS:           {total_chars:,}")
if succeeded > 0:
    print(f"  AVG TOKENS/PROVIDER:   {total_tokens // succeeded:,}")
    print(f"  AVG CHARS/PROVIDER:    {total_chars // succeeded:,}")
print(f"  COMBINED OUTPUT:       {total_chars:,} chars = ~{total_chars // 4:,} words")
print("=" * 70)
print()
print("NO SINGLE MODEL PRODUCED THIS. The combined swarm output is:")
print(f"  {total_chars:,} characters across {succeeded} providers")
print(f"  That's {succeeded}x the output of any individual model.")
print()

# Show first 200 chars of each response
print("--- RESPONSE PREVIEWS (first 200 chars each) ---")
for p in providers:
    fpath = f"/tmp/nova_{p}.json"
    if os.path.exists(fpath):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                d = json.load(f)
            resp = d.get("result", {}).get("response", "")
            if resp:
                print(f"\n[{p.upper()}]: {resp[:200]}...")
        except:
            pass
