"""
FREE DATASET DOWNLOADER v2 - Fixed HuggingFace API endpoints.
Uses the correct datasets-server API with proper config names.
Writes to: C:/NovaX/data/llm_training/pairs_downloaded2.json
"""
import json
import urllib.request
import urllib.error
import random

random.seed(999)
OUTPUT = "C:/NovaX/data/llm_training/pairs_downloaded2.json"
pairs = []
seen = set()

def add(prompt, response, domain, source):
    key = prompt.strip().lower()[:200]
    if key in seen:
        return
    if len(prompt.strip()) < 10 or len(response.strip()) < 20:
        return
    if len(response) > 3000:
        response = response[:3000]
    seen.add(key)
    pairs.append({
        "prompt": prompt.strip(),
        "response": response.strip(),
        "domain": domain,
        "provider": "downloaded_%s" % source,
        "model": "open_data"
    })

def fetch_hf_rows(dataset, config, split="train", offset=0, length=100):
    """Fetch rows from HuggingFace datasets server API."""
    url = "https://datasets-server.huggingface.co/rows?dataset=%s&config=%s&split=%s&offset=%d&length=%d" % (
        dataset, config, split, offset, length)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'NovaX/1.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if 'rows' in data:
                return [r.get('row', r) for r in data['rows']]
    except Exception as e:
        print("  Failed: %s (%s)" % (url[:100], str(e)[:80]))
    return None

def fetch_all_rows(dataset, config, split="train", max_rows=5000, batch=100):
    """Fetch multiple batches of rows."""
    all_rows = []
    for offset in range(0, max_rows, batch):
        rows = fetch_hf_rows(dataset, config, split, offset, batch)
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < batch:
            break
    return all_rows

# ============================================================
# 1. ALPACA (Stanford instruction-following dataset)
# ============================================================
print("[1/7] Fetching Alpaca...")
rows = fetch_all_rows("tatsu-lab/alpaca", "default", "train", 5000)
if rows:
    count = 0
    for row in rows:
        instruction = row.get('instruction', '')
        inp = row.get('input', '')
        output = row.get('output', '')
        if instruction and output:
            prompt = instruction
            if inp:
                prompt = "%s\n\nInput: %s" % (instruction, inp)
            add(prompt, output, "alpaca_instruct", "alpaca")
            count += 1
    print("  Alpaca pairs: %d" % count)
else:
    print("  Alpaca: failed")

# ============================================================
# 2. OASST2 (OpenAssistant conversations)
# ============================================================
print("[2/7] Fetching OASST2...")
rows = fetch_all_rows("OpenAssistant/oasst2", "default", "train", 5000)
if rows:
    # Build parent->child map for conversation trees
    messages = {}
    for row in rows:
        msg_id = row.get('message_id', '')
        parent_id = row.get('parent_id')
        text = row.get('text', '')
        role = row.get('role', '')
        if msg_id:
            messages[msg_id] = {'text': text, 'parent_id': parent_id, 'role': role}

    count = 0
    for msg_id, msg in messages.items():
        if msg['role'] == 'assistant' and msg.get('parent_id'):
            parent = messages.get(msg['parent_id'])
            if parent and parent['role'] == 'prompter' and parent['text'] and msg['text']:
                add(parent['text'], msg['text'], "conversation", "oasst2")
                count += 1
    print("  OASST2 pairs: %d" % count)
else:
    print("  OASST2: failed")

# ============================================================
# 3. GSM8K (Math word problems from OpenAI)
# ============================================================
print("[3/7] Fetching GSM8K...")
rows = fetch_all_rows("openai/gsm8k", "main", "train", 5000)
if rows:
    count = 0
    for row in rows:
        question = row.get('question', '')
        answer = row.get('answer', '')
        if question and answer:
            add(question, answer, "math_word", "gsm8k")
            count += 1
    print("  GSM8K pairs: %d" % count)
else:
    print("  GSM8K: failed")

# ============================================================
# 4. SQuAD v2 (Reading comprehension)
# ============================================================
print("[4/7] Fetching SQuAD...")
rows = fetch_all_rows("rajpurkar/squad_v2", "squad_v2", "train", 5000)
if not rows:
    rows = fetch_all_rows("rajpurkar/squad", "plain_text", "train", 5000)
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
            answer_text = answers[0] if isinstance(answers[0], str) else answers[0].get('text', '')

        if answer_text:
            add("Based on the context, answer: %s\n\nContext: %s" % (question, context[:400]),
                "The answer is: %s" % answer_text,
                "reading_comprehension", "squad")
            count += 1
    print("  SQuAD pairs: %d" % count)
else:
    print("  SQuAD: failed")

# ============================================================
# 5. WizardLM (Complex instructions)
# ============================================================
print("[5/7] Fetching WizardLM...")
rows = fetch_all_rows("WizardLMTeam/WizardLM_evol_instruct_V2_196k", "default", "train", 3000)
if rows:
    count = 0
    for row in rows:
        instruction = row.get('instruction', '') or row.get('conversations', [{}])[0].get('value', '') if row.get('conversations') else ''
        output = row.get('output', '') or (row.get('conversations', [{}]*2)[1].get('value', '') if row.get('conversations') and len(row.get('conversations', [])) > 1 else '')
        if instruction and output:
            add(instruction, output, "instruct_complex", "wizardlm")
            count += 1
    print("  WizardLM pairs: %d" % count)
else:
    print("  WizardLM: failed")

# ============================================================
# 6. Code Alpaca (Code instruction pairs)
# ============================================================
print("[6/7] Fetching CodeAlpaca...")
rows = fetch_all_rows("sahil2801/CodeAlpaca-20k", "default", "train", 3000)
if rows:
    count = 0
    for row in rows:
        instruction = row.get('instruction', '')
        inp = row.get('input', '')
        output = row.get('output', '')
        if instruction and output:
            prompt = instruction
            if inp:
                prompt = "%s\n\n%s" % (instruction, inp)
            add(prompt, output, "code_instruct", "code_alpaca")
            count += 1
    print("  CodeAlpaca pairs: %d" % count)
else:
    print("  CodeAlpaca: failed")

# ============================================================
# 7. TruthfulQA (Factual Q&A)
# ============================================================
print("[7/7] Fetching TruthfulQA...")
rows = fetch_all_rows("truthfulqa/truthful_qa", "generation", "validation", 1000)
if rows:
    count = 0
    for row in rows:
        question = row.get('question', '')
        best_answer = row.get('best_answer', '')
        if question and best_answer:
            add(question, best_answer, "factual_qa", "truthfulqa")
            count += 1
    print("  TruthfulQA pairs: %d" % count)
else:
    print("  TruthfulQA: failed")

# ============================================================
# SAVE
# ============================================================
print("\n=== TOTAL DOWNLOADED v2 PAIRS: %d ===" % len(pairs))

with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(pairs, f, ensure_ascii=False, indent=1)

print("Saved to %s" % OUTPUT)
