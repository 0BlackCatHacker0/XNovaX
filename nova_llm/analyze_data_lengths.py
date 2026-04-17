"""Quick analysis of training data token length distribution."""
import json, statistics

with open('C:/NovaX/data/llm_training/training_pairs_mega.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total pairs: {len(data)}')
lens = [len(p.get('prompt','') + p.get('response','')) for p in data]
sl = sorted(lens)
n = len(sl)
print(f'Char lengths - Min: {min(lens)}, Max: {max(lens)}, Mean: {statistics.mean(lens):.0f}, Median: {statistics.median(lens):.0f}')
print(f'P10: {sl[n//10]}, P25: {sl[n//4]}, P50: {sl[n//2]}, P75: {sl[3*n//4]}, P90: {sl[int(n*0.9)]}, P95: {sl[int(n*0.95)]}, P99: {sl[int(n*0.99)]}')

for thresh in [128, 256, 384, 512, 768, 1024, 2048]:
    count = sum(1 for l in lens if l <= thresh)
    print(f'  <={thresh} chars: {count} ({count*100/n:.1f}%)')
