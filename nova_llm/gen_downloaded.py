"""
FREE DATASET DOWNLOADER - Download open training data from HuggingFace.
Uses direct HTTP to download JSONL/CSV files from open datasets.
Target: 10,000+ pairs from public domain datasets.
Writes to: C:/NovaX/data/llm_training/pairs_downloaded.json
"""
import json
import urllib.request
import urllib.error
import csv
import io
import random
import time

random.seed(789)
OUTPUT = "C:/NovaX/data/llm_training/pairs_downloaded.json"
pairs = []
seen = set()

def add(prompt, response, domain, source):
    key = prompt.strip().lower()[:200]
    if key in seen:
        return
    if len(prompt.strip()) < 10 or len(response.strip()) < 20:
        return
    # Limit response length
    if len(response) > 3000:
        response = response[:3000]
    seen.add(key)
    pairs.append({
        "prompt": prompt.strip(),
        "response": response.strip(),
        "domain": domain,
        "provider": f"downloaded_{source}",
        "model": "open_data"
    })

def fetch_url(url, timeout=30):
    """Fetch URL content."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'NovaX-LLM-Training/1.0'
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  Failed to fetch {url[:80]}: {e}")
        return None

def fetch_hf_dataset(repo, filename, split="train", limit=5000):
    """Fetch from HuggingFace datasets API."""
    # Try the datasets API first
    url = f"https://datasets-server.huggingface.co/rows?dataset={repo}&config=default&split={split}&offset=0&length={limit}"
    data = fetch_url(url, timeout=60)
    if data:
        try:
            parsed = json.loads(data)
            if 'rows' in parsed:
                return [row.get('row', row) for row in parsed['rows']]
        except:
            pass

    # Try direct parquet/jsonl download
    url2 = f"https://huggingface.co/datasets/{repo}/resolve/main/{filename}"
    data2 = fetch_url(url2, timeout=60)
    if data2:
        try:
            if filename.endswith('.jsonl'):
                return [json.loads(line) for line in data2.strip().split('\n') if line.strip()][:limit]
            elif filename.endswith('.json'):
                return json.loads(data2)[:limit]
        except:
            pass
    return None

# ============================================================
# 1. DOLLY-15K (Databricks open instruction dataset)
# ============================================================
print("[1/6] Fetching Dolly-15k...")
rows = fetch_hf_dataset("databricks/databricks-dolly-15k", "databricks-dolly-15k.jsonl", limit=5000)
if rows:
    count = 0
    for row in rows:
        instruction = row.get('instruction', '')
        context = row.get('context', '')
        response_text = row.get('response', '')
        category = row.get('category', 'general')

        if not instruction or not response_text:
            continue

        prompt = instruction
        if context:
            prompt = f"{instruction}\n\nContext: {context}"

        add(prompt, response_text, f"dolly_{category}", "dolly15k")
        count += 1
    print(f"  Dolly pairs: {count}")
else:
    print("  Dolly: failed to fetch")

# ============================================================
# 2. OPENASSISTANT (OASST)
# ============================================================
print("[2/6] Fetching OpenAssistant...")
rows = fetch_hf_dataset("OpenAssistant/oasst1", "oasst1.jsonl", limit=5000)
if rows:
    # OASST is a tree structure, extract prompt-response pairs
    messages = {}
    for row in rows:
        msg_id = row.get('message_id', '')
        parent_id = row.get('parent_id', '')
        text = row.get('text', '')
        role = row.get('role', '')
        messages[msg_id] = {'text': text, 'parent_id': parent_id, 'role': role}

    count = 0
    for msg_id, msg in messages.items():
        if msg['role'] == 'assistant' and msg['parent_id']:
            parent = messages.get(msg['parent_id'])
            if parent and parent['role'] == 'prompter':
                add(parent['text'], msg['text'], "conversation", "oasst")
                count += 1
                if count >= 3000:
                    break
    print(f"  OASST pairs: {count}")
else:
    print("  OASST: failed to fetch")

# ============================================================
# 3. SELF-INSTRUCT / ALPACA
# ============================================================
print("[3/6] Fetching Alpaca...")
rows = fetch_hf_dataset("tatsu-lab/alpaca", "data/train-00000-of-00001.parquet", limit=5000)
if rows:
    count = 0
    for row in rows:
        instruction = row.get('instruction', '')
        inp = row.get('input', '')
        output = row.get('output', '')

        if not instruction or not output:
            continue

        prompt = instruction
        if inp:
            prompt = f"{instruction}\n\nInput: {inp}"

        add(prompt, output, "alpaca_instruct", "alpaca")
        count += 1
    print(f"  Alpaca pairs: {count}")
else:
    print("  Alpaca: failed to fetch")

# ============================================================
# 4. GSMATH (Math word problems)
# ============================================================
print("[4/6] Fetching GSM8K math...")
rows = fetch_hf_dataset("openai/gsm8k", "main/train.jsonl", split="train", limit=3000)
if rows:
    count = 0
    for row in rows:
        question = row.get('question', '')
        answer = row.get('answer', '')
        if question and answer:
            add(question, answer, "math_word", "gsm8k")
            count += 1
    print(f"  GSM8K pairs: {count}")
else:
    print("  GSM8K: failed to fetch")

# ============================================================
# 5. CODE ALPACA
# ============================================================
print("[5/6] Fetching Code Alpaca...")
rows = fetch_hf_dataset("sahil2801/CodeAlpaca-20k", "data/train-00000-of-00001.parquet", limit=3000)
if rows:
    count = 0
    for row in rows:
        instruction = row.get('instruction', '')
        inp = row.get('input', '')
        output = row.get('output', '')
        if instruction and output:
            prompt = instruction
            if inp:
                prompt = f"{instruction}\n\n{inp}"
            add(prompt, output, "code_instruct", "code_alpaca")
            count += 1
    print(f"  Code Alpaca pairs: {count}")
else:
    print("  Code Alpaca: failed to fetch")

# ============================================================
# 6. SQUAD (Reading comprehension)
# ============================================================
print("[6/6] Fetching SQuAD...")
rows = fetch_hf_dataset("rajpurkar/squad", "plain_text/train.jsonl", split="train", limit=3000)
if rows:
    count = 0
    for row in rows:
        context = row.get('context', '')
        question = row.get('question', '')
        answers = row.get('answers', {})

        if not question or not context:
            continue

        answer_text = ""
        if isinstance(answers, dict):
            texts = answers.get('text', [])
            if texts:
                answer_text = texts[0] if isinstance(texts, list) else texts
        elif isinstance(answers, list) and answers:
            answer_text = answers[0].get('text', '') if isinstance(answers[0], dict) else str(answers[0])

        if not answer_text:
            continue

        add(f"Based on the following text, {question}\n\nText: {context[:500]}",
            f"Based on the provided text, the answer is: {answer_text}",
            "reading_comprehension", "squad")
        count += 1
    print(f"  SQuAD pairs: {count}")
else:
    print("  SQuAD: failed to fetch")

# ============================================================
# SAVE
# ============================================================
print(f"\n=== TOTAL DOWNLOADED PAIRS: {len(pairs)} ===")

with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(pairs, f, ensure_ascii=False, indent=1)

print(f"Saved to {OUTPUT}")
