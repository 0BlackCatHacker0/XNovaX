#!/usr/bin/env python3
"""NovaX Server Health Monitor v1.0
Implements Section 5 Supervisor Pattern:
  1. Check port  2. Wait 5s  3. Retry 3x  4. Log crash + notify
"""
import socket, urllib.request, json, time, sys, os, subprocess, datetime

MANIFEST_PATH = r'C:\NovaX\config\servers\server_manifest.json'
LOG_DIR = r'C:\NovaX\config\servers\logs'

def load_manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)

def check_tcp(host, port, timeout=3):
    try:
        s = socket.create_connection((host, port), timeout)
        s.close()
        return True
    except:
        return False

def check_http(url, timeout=5):
    try:
        req = urllib.request.urlopen(url, timeout=timeout)
        return req.getcode() == 200
    except:
        return False

def check_service(name, svc):
    port = svc.get('port', 0)
    health_type = svc.get('health_type', 'tcp')
    health_url = svc.get('health', '')
    
    if health_type == 'http' and health_url:
        return check_http(health_url)
    elif port:
        return check_tcp('127.0.0.1', port)
    return False

def log_event(name, status, msg=''):
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {name}: {status} {msg}
'
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR, 'health_monitor.log'), 'a') as f:
        f.write(line)
    print(line.strip())

def run_health_check(verbose=True):
    manifest = load_manifest()
    results = {}
    for name in manifest['dependency_order']:
        svc = manifest['services'].get(name, {})
        port = svc.get('port', '?')
        alive = check_service(name, svc)
        status = 'UP' if alive else 'DOWN'
        results[name] = {'status': status, 'port': port}
        if verbose:
            icon = '[OK]' if alive else '[!!]'
            print(f'  {icon} :{port} {name} - {status}')
    
    up = sum(1 for r in results.values() if r['status'] == 'UP')
    down = sum(1 for r in results.values() if r['status'] == 'DOWN')
    print(f'
  Summary: {up} UP / {down} DOWN / {len(results)} total')
    return results

def supervisor_check(name, svc, max_retries=3, wait=5):
    """Section 5 pattern: check, wait, retry 3x, log crash"""
    for attempt in range(1, max_retries + 1):
        if check_service(name, svc):
            log_event(name, 'UP', f'attempt {attempt}')
            return True
        log_event(name, 'RETRY', f'attempt {attempt}/{max_retries}')
        time.sleep(wait)
    log_event(name, 'CRASH', f'failed after {max_retries} retries')
    return False

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if mode == 'check':
        print('=== NovaX Health Monitor ===')
        run_health_check()
    elif mode == 'json':
        results = run_health_check(verbose=False)
        print(json.dumps(results, indent=2))
    elif mode == 'watch':
        print('=== Continuous Monitor (Ctrl+C to stop) ===')
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f'=== NovaX Health - {datetime.datetime.now().strftime("%H:%M:%S")} ===')
            run_health_check()
            time.sleep(10)
