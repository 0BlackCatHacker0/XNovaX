#!/usr/bin/env python3
"""Profile all NovaX services by /health latency (parallel)."""
import time, json, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    resp = urllib.request.urlopen('http://127.0.0.1:9999/api/services/status', timeout=5)
    data = json.loads(resp.read())
except Exception as e:
    print(f'Cannot reach orchestrator: {e}')
    exit(1)

services = data.get('services', [])
print(f'Profiling {len(services)} services (parallel)...\n')

def probe(svc):
    name = svc.get('name', '?')
    port = svc.get('port', 0)
    if not port:
        return (999999.0, name, port, 'DOWN')
    t0 = time.time()
    try:
        r = urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=3)
        r.read()
        latency = (time.time() - t0) * 1000
        return (latency, name, port, 'OK')
    except Exception:
        latency = (time.time() - t0) * 1000
        return (latency, name, port, 'ERR')

results = []
with ThreadPoolExecutor(max_workers=20) as pool:
    futures = {pool.submit(probe, svc): svc for svc in services}
    for f in as_completed(futures):
        results.append(f.result())

results.sort(key=lambda x: -x[0])

print('Top 20 slowest:')
print('-' * 60)
for lat, name, port, status in results[:20]:
    if lat >= 999:
        print(f'  {name:30s} :{port:>5}  DOWN')
    else:
        print(f'  {name:30s} :{port:>5}  {lat:>8.1f}ms  {status}')

print()
ok_results = [r for r in results if r[3] == 'OK']
err_results = [r for r in results if r[3] == 'ERR']
down_results = [r for r in results if r[3] == 'DOWN']

if ok_results:
    lats = [r[0] for r in ok_results]
    print(f'Healthy: {len(ok_results)} | Avg: {sum(lats)/len(lats):.1f}ms | Min: {min(lats):.1f}ms | Max: {max(lats):.1f}ms')

    # Categorize by N-S Reynolds boundaries: H3^3=27, H5^3=125, H7^3=343
    laminar = [r for r in ok_results if r[0] < 27]     # < 27ms
    transition = [r for r in ok_results if 27 <= r[0] < 125]  # 27-125ms
    turbulent = [r for r in ok_results if 125 <= r[0] < 343]  # 125-343ms
    chaotic = [r for r in ok_results if r[0] >= 343]    # > 343ms

    print(f'\nN-S Flow Regimes:')
    print(f'  LAMINAR   (<27ms):  {len(laminar)} services')
    print(f'  TRANSITION (27-125ms): {len(transition)} services')
    print(f'  TURBULENT (125-343ms): {len(turbulent)} services')
    print(f'  CHAOTIC   (>343ms): {len(chaotic)} services')

    if chaotic:
        print(f'\nCHAOTIC (needs optimization):')
        for lat, name, port, _ in chaotic:
            print(f'  {name} :{port} = {lat:.1f}ms')
    if turbulent:
        print(f'\nTURBULENT (consider optimizing):')
        for lat, name, port, _ in turbulent:
            print(f'  {name} :{port} = {lat:.1f}ms')

if err_results:
    print(f'\nERROR (unhealthy): {len(err_results)}')
    for lat, name, port, _ in err_results:
        print(f'  {name} :{port} = {lat:.1f}ms')

if down_results:
    print(f'\nDOWN: {len(down_results)}')
    for _, name, port, _ in down_results:
        print(f'  {name} :{port}')
