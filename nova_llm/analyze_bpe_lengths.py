"""Analyze BPE token length distribution for training data."""
import json, sys, random
sys.path.insert(0, 'C:/NovaX/nova_llm')

try:
    from bpe_tokenizer import NovaXTokenizer
    tok = NovaXTokenizer('C:/NovaX/nova_llm/bpe_vocab_32k.json')
    with open('C:/NovaX/data/llm_training/training_pairs_mega.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    random.seed(42)
    sample = random.sample(data, min(500, len(data)))
    token_lens = []
    for p in sample:
        text = p.get('prompt', '') + ' ' + p.get('response', '')
        toks = tok.encode(text)
        token_lens.append(len(toks))

    sl = sorted(token_lens)
    n = len(sl)
    print(f'BPE token lengths (sample {n}):')
    print(f'  Min: {min(sl)}, Max: {max(sl)}, Mean: {sum(sl)//n}, Median: {sl[n//2]}')
    print(f'  P75: {sl[3*n//4]}, P90: {sl[int(n*0.9)]}, P95: {sl[int(n*0.95)]}, P99: {sl[int(n*0.99)]}')
    for t in [128, 192, 256, 384, 512]:
        c = sum(1 for l in sl if l <= t)
        print(f'  <={t} tokens: {c} ({c*100/n:.1f}%)')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
