"""Quick fleet timeout audit - standalone script."""
import json
import socket
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

socket.setdefaulttimeout(60.0)

def check(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        if s.connect_ex(("127.0.0.1", port)) != 0:
            s.close()
            return None
        s.close()
        t0 = time.time()
        resp = urllib.request.urlopen(
            "http://127.0.0.1:%d/health" % port, timeout=3
        )
        data = json.loads(resp.read())
        ht = time.time() - t0
        svc = data.get("service", "?")
        return (port, svc, round(ht, 3))
    except Exception:
        return None

ports = list(range(9870, 10000))

with ThreadPoolExecutor(max_workers=13) as pool:
    results = list(pool.map(check, ports))

alive = [r for r in results if r]
print("Fleet: %d services alive" % len(alive))

slow = [r for r in alive if r[2] > 0.5]
fast = [r for r in alive if r[2] <= 0.5]
print("Fast (<0.5s): %d" % len(fast))
print("Slow (>0.5s): %d" % len(slow))

if slow:
    print("\nSlow services:")
    for p, s, t in sorted(slow, key=lambda x: -x[2]):
        print("  %s:%d = %ss" % (s, p, t))

if alive:
    fastest = min(alive, key=lambda x: x[2])
    slowest = max(alive, key=lambda x: x[2])
    avg = sum(r[2] for r in alive) / len(alive)
    print("\nFastest: %s:%d = %ss" % (fastest[1], fastest[0], fastest[2]))
    print("Slowest: %s:%d = %ss" % (slowest[1], slowest[0], slowest[2]))
    print("Average: %.3fs" % avg)
