"""
NovaX Training Pair Merger
Reads all pair files, deduplicates by MD5(prompt+response), saves merged result.
Scans for ALL pairs_*.json files automatically.
"""
import json, hashlib, os, sys
from pathlib import Path

DATA_DIR = Path("C:/NovaX/data/llm_training")
OUT_FILE = DATA_DIR / "training_pairs_mega.json"

def get_hash(prompt, response):
    """MD5 hash of prompt+response for dedup."""
    text = (prompt.strip() + response.strip()).lower()
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()

def load_pairs(filepath):
    """Load pairs from a JSON file. Handles both JSON array and JSONL."""
    if not filepath.exists():
        print("  SKIP (not found): %s" % filepath.name)
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            print("  SKIP (empty): %s" % filepath.name)
            return []

        # Try JSON array first
        if content.startswith("["):
            pairs = json.loads(content)
            print("  Loaded %d pairs from %s" % (len(pairs), filepath.name))
            return pairs

        # Try JSONL
        pairs = []
        for line in content.split("\n"):
            line = line.strip()
            if line:
                try:
                    pairs.append(json.loads(line))
                except:
                    pass
        print("  Loaded %d pairs from %s (JSONL)" % (len(pairs), filepath.name))
        return pairs
    except Exception as e:
        print("  ERROR loading %s: %s" % (filepath.name, str(e)))
        return []

def main():
    print("=" * 60)
    print("  NovaX Training Pair Merger")
    print("=" * 60)

    # Discover all source files
    SOURCE_FILES = []

    # 1. The original mega file (backup first)
    if OUT_FILE.exists():
        backup = DATA_DIR / "training_pairs_mega.json.backup"
        import shutil
        shutil.copy2(OUT_FILE, backup)
        print("Backed up mega file to %s" % backup.name)
        SOURCE_FILES.append(OUT_FILE)

    # 2. All pairs_*.json files
    for f in sorted(DATA_DIR.glob("pairs_*.json")):
        SOURCE_FILES.append(f)

    # 3. Other known training files
    for name in ["training_pairs.json", "training_pairs_v2.json", "training_pairs_v3.json",
                  "tool_training_pairs.json"]:
        p = DATA_DIR / name
        if p.exists() and p not in SOURCE_FILES:
            SOURCE_FILES.append(p)

    # 4. Factory output (JSONL)
    factory = DATA_DIR / "factory_output.jsonl"
    if factory.exists():
        SOURCE_FILES.append(factory)

    print("\nFound %d source files:" % len(SOURCE_FILES))
    for f in SOURCE_FILES:
        print("  - %s" % f.name)

    # Load all sources
    all_pairs = []
    seen_hashes = set()
    duplicates = 0
    stats_by_source = {}
    stats_by_domain = {}

    print("\nLoading source files...")
    for src in SOURCE_FILES:
        pairs = load_pairs(src)
        new_from_src = 0
        for p in pairs:
            prompt = p.get("prompt", "")
            response = p.get("response", "")
            if not prompt or not response:
                continue
            if len(response.strip()) < 10:
                continue

            h = get_hash(prompt, response)
            if h in seen_hashes:
                duplicates += 1
                continue

            seen_hashes.add(h)
            # Ensure standard fields
            clean = {
                "prompt": prompt.strip(),
                "response": response.strip(),
                "domain": p.get("domain", "mixed"),
                "provider": p.get("provider", p.get("source", "unknown")),
                "model": p.get("model", "unknown"),
            }
            all_pairs.append(clean)
            new_from_src += 1

            # Track stats
            source = clean["provider"]
            stats_by_source[source] = stats_by_source.get(source, 0) + 1
            domain = clean["domain"]
            stats_by_domain[domain] = stats_by_domain.get(domain, 0) + 1

        if pairs:
            print("    -> %d unique pairs added (%d dupes skipped)" % (new_from_src, len(pairs) - new_from_src))

    # Save merged result
    print("\nSaving merged result...")
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_pairs, f, ensure_ascii=False)

    # Print results
    total_chars = sum(len(p["prompt"]) + len(p["response"]) for p in all_pairs)

    print("\n" + "=" * 60)
    print("  Merge Complete!")
    print("  Total unique pairs: %d" % len(all_pairs))
    print("  Duplicates removed: %d" % duplicates)
    print("  Total characters: %s (%.1fM)" % ("{:,}".format(total_chars), total_chars / 1e6))
    print("  Output: %s" % OUT_FILE)

    print("\n  By source (top 20):")
    sorted_sources = sorted(stats_by_source.items(), key=lambda x: -x[1])
    for src, count in sorted_sources[:20]:
        print("    %-30s %6d pairs" % (src, count))
    if len(sorted_sources) > 20:
        others = sum(c for _, c in sorted_sources[20:])
        print("    %-30s %6d pairs" % ("(+ %d other sources)" % (len(sorted_sources) - 20), others))

    print("\n  By domain (top 20):")
    sorted_domains = sorted(stats_by_domain.items(), key=lambda x: -x[1])
    for dom, count in sorted_domains[:20]:
        print("    %-30s %6d pairs" % (dom, count))
    if len(sorted_domains) > 20:
        others = sum(c for _, c in sorted_domains[15:])
        print("    %-30s %6d pairs" % ("(+ %d other domains)" % (len(sorted_domains) - 20), others))

    print("=" * 60)

if __name__ == "__main__":
    main()
