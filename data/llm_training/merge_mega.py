import json, hashlib, random, shutil, os, sys
from collections import Counter

BASE = r'C:\NovaX\data\llm_training'
MEGA = os.path.join(BASE, 'training_pairs_mega.json')
BACKUP = MEGA + '.bak'

FILES = [
    ('training_pairs_mega.json', 'mega_base', False),
    ('pairs_downloaded.json', 'downloaded', False),
    ('pairs_downloaded2.json', 'downloaded2', False),
    ('pairs_synthetic.json', 'synthetic', False),
    ('pairs_synthetic_boost.json', 'synthetic_boost', False),
    ('pairs_augmented.json', 'augmented', False),
    ('pairs_codemined.json', 'codemined', True),
    ('pairs_docs.json', 'docs', False),
]
CODEMINED_CAP = 20000

def md5_key(prompt, response):
    raw = (str(prompt) + '|||' + str(response)).encode('utf-8', errors='replace')
    return hashlib.md5(raw).hexdigest()

def normalize_pair(pair, fallback_source):
    prompt = pair.get('prompt', pair.get('instruction', '')).strip()
    response = pair.get('response', pair.get('output', pair.get('answer', ''))).strip()
    source = pair.get('source', pair.get('provider', fallback_source))
    domain = pair.get('domain', pair.get('category', 'general'))
    if not prompt or not response:
        return None
    return {'prompt': prompt, 'response': response, 'source': source, 'domain': domain}

random.seed(42)
print('MEGA MERGE')
if os.path.exists(MEGA):
    shutil.copy2(MEGA, BACKUP)
    print('Backup done:', os.path.getsize(BACKUP))
seen_hashes = set()
all_pairs = []
source_counts = Counter()
domain_counts = Counter()
file_stats = {}
dupes_total = 0
for filename, source_label, is_capped in FILES:
    filepath = os.path.join(BASE, filename)
    if not os.path.exists(filepath):
        print('SKIP', filename)
        continue
    print('LOAD', filename)
    sys.stdout.flush()
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        raw_pairs = json.load(f)
    lc = len(raw_pairs)
    print('  Raw:', lc)
    if is_capped and lc > CODEMINED_CAP:
        print('  CAP at', CODEMINED_CAP)
        raw_pairs = random.sample(raw_pairs, CODEMINED_CAP)
    kept = 0
    dupes = 0
    for pair in raw_pairs:
        normalized = normalize_pair(pair, source_label)
        if normalized is None:
            continue
        h = md5_key(normalized['prompt'], normalized['response'])
        if h in seen_hashes:
            dupes += 1
            continue
        seen_hashes.add(h)
        all_pairs.append(normalized)
        source_counts[normalized['source']] += 1
        domain_counts[normalized['domain']] += 1
        kept += 1
    dupes_total += dupes
    file_stats[filename] = (lc, kept, dupes)
    print('  Kept:', kept, 'Dupes:', dupes)
    sys.stdout.flush()
print('Saving...')
sys.stdout.flush()
with open(MEGA, 'w', encoding='utf-8') as f:
    json.dump(all_pairs, f, ensure_ascii=True, indent=1)
print('Saved. Size:', os.path.getsize(MEGA))
print('Total unique:', len(all_pairs))
print('Total dupes:', dupes_total)
for fn, sl, _ in FILES:
    if fn in file_stats:
        lo, ke, du = file_stats[fn]
        print('  ', fn, 'loaded='+str(lo), 'kept='+str(ke), 'dupes='+str(du))
for src, cnt in source_counts.most_common():
    print('  SRC', src, cnt)
for dom, cnt in domain_counts.most_common(25):
    print('  DOM', dom, cnt)
total = len(all_pairs)
if 90000 <= total <= 120000:
    print('TARGET MET:', total)
elif total < 90000:
    print('BELOW TARGET:', total)
else:
    print('ABOVE TARGET:', total)
print('Done.')
