"""
NovaX Dataset Downloader
Downloads free instruction datasets and converts to training pair format.
No pip packages required - uses only stdlib urllib.
"""
import json, urllib.request, hashlib, os, sys, time
from pathlib import Path

OUT_FILE = Path("C:/NovaX/data/llm_training/pairs_downloaded.json")
MEGA_FILE = Path("C:/NovaX/data/llm_training/training_pairs_mega.json")

def download_url(url, desc):
    """Download a URL with progress, return bytes."""
    print("Downloading %s..." % desc)
    print("  URL: %s" % url)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NovaX/1.0"})
        resp = urllib.request.urlopen(req, timeout=300)
        data = resp.read()
        print("  Downloaded: %.1f MB" % (len(data) / 1e6))
        return data
    except Exception as e:
        print("  FAILED: %s" % str(e))
        return None

def get_hash(prompt, response):
    """MD5 hash for dedup."""
    text = (prompt.strip() + response.strip()).lower()
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()

def load_existing_hashes():
    """Load hashes from mega file for dedup."""
    hashes = set()
    if MEGA_FILE.exists():
        try:
            pairs = json.load(open(MEGA_FILE, "r", encoding="utf-8"))
            for p in pairs:
                h = get_hash(p.get("prompt", ""), p.get("response", ""))
                hashes.add(h)
            print("Loaded %d existing hashes from mega file" % len(hashes))
        except:
            pass
    return hashes

def download_alpaca():
    """Download Stanford Alpaca dataset (52K instruction pairs)."""
    url = "https://raw.githubusercontent.com/tatsu-lab/stanford_alpaca/main/alpaca_data.json"
    data = download_url(url, "Alpaca (52K instruction pairs)")
    if not data:
        return []

    raw = json.loads(data.decode("utf-8"))
    pairs = []
    for item in raw:
        instruction = item.get("instruction", "").strip()
        inp = item.get("input", "").strip()
        output = item.get("output", "").strip()

        if not instruction or not output:
            continue

        # Combine instruction + input as prompt
        if inp:
            prompt = "%s\n\nInput: %s" % (instruction, inp)
        else:
            prompt = instruction

        pairs.append({
            "prompt": prompt,
            "response": output,
            "source": "alpaca",
            "domain": "mixed"
        })

    print("  Alpaca: %d pairs extracted" % len(pairs))
    return pairs

def download_dolly():
    """Download Databricks Dolly dataset (15K instruction pairs)."""
    url = "https://huggingface.co/datasets/databricks/databricks-dolly-15k/resolve/main/databricks-dolly-15k.jsonl"
    data = download_url(url, "Dolly (15K instruction pairs)")
    if not data:
        return []

    pairs = []
    for line in data.decode("utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except:
            continue

        instruction = item.get("instruction", "").strip()
        context = item.get("context", "").strip()
        response = item.get("response", "").strip()
        category = item.get("category", "mixed")

        if not instruction or not response:
            continue

        if context:
            prompt = "%s\n\nContext: %s" % (instruction, context)
        else:
            prompt = instruction

        pairs.append({
            "prompt": prompt,
            "response": response,
            "source": "dolly",
            "domain": category
        })

    print("  Dolly: %d pairs extracted" % len(pairs))
    return pairs

def main():
    print("=" * 60)
    print("  NovaX Dataset Downloader")
    print("=" * 60)

    # Load existing hashes for dedup
    existing_hashes = load_existing_hashes()

    # Load already-downloaded pairs if they exist
    if OUT_FILE.exists():
        try:
            existing_downloaded = json.load(open(OUT_FILE, "r", encoding="utf-8"))
            print("Existing downloaded pairs: %d" % len(existing_downloaded))
            for p in existing_downloaded:
                existing_hashes.add(get_hash(p.get("prompt", ""), p.get("response", "")))
        except:
            existing_downloaded = []
    else:
        existing_downloaded = []

    all_new = []

    # Download Alpaca
    print("\n--- Alpaca Dataset ---")
    alpaca = download_alpaca()
    deduped = 0
    for p in alpaca:
        h = get_hash(p["prompt"], p["response"])
        if h not in existing_hashes:
            all_new.append(p)
            existing_hashes.add(h)
        else:
            deduped += 1
    print("  After dedup: %d new, %d duplicates removed" % (len(all_new), deduped))

    # Download Dolly
    print("\n--- Dolly Dataset ---")
    dolly = download_dolly()
    new_before = len(all_new)
    deduped = 0
    for p in dolly:
        h = get_hash(p["prompt"], p["response"])
        if h not in existing_hashes:
            all_new.append(p)
            existing_hashes.add(h)
        else:
            deduped += 1
    dolly_added = len(all_new) - new_before
    print("  After dedup: %d new, %d duplicates removed" % (dolly_added, deduped))

    # Merge with existing downloaded pairs
    final = existing_downloaded + all_new

    # Save
    os.makedirs(OUT_FILE.parent, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("  Results:")
    print("  New pairs added: %d" % len(all_new))
    print("  Total in %s: %d" % (OUT_FILE.name, len(final)))

    # Stats by source
    by_source = {}
    for p in final:
        s = p.get("source", "unknown")
        by_source[s] = by_source.get(s, 0) + 1
    print("  By source: %s" % by_source)

    # Show samples
    if all_new:
        print("\n  Sample 1: %s" % all_new[0].get("prompt", "")[:80])
        print("  Response: %s..." % all_new[0].get("response", "")[:80])
    if len(all_new) > 1:
        print("\n  Sample 2: %s" % all_new[-1].get("prompt", "")[:80])
        print("  Response: %s..." % all_new[-1].get("response", "")[:80])
    print("=" * 60)

if __name__ == "__main__":
    main()
