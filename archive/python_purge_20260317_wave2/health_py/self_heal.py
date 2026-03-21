"""NovaX Self-Healing Triggers v1.0
Section 11: On port down -> relaunch, On crash -> log + notify + retry
"""
import json, time, socket, subprocess, os, sys, datetime
sys.path.insert(0, r"C:\NovaX\core")
from nowindow import safe_popen

MANIFEST = r'C:\NovaX\config\servers\server_manifest.json'
LOG = r'C:\NovaX\config\servers\logs\self_heal.log'

def log(msg):
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG, 'a') as f: f.write(line + '\n')

def port_up(port):
    try:
        s = socket.create_connection(('127.0.0.1', port), 3)
        s.close()
        return True
    except: return False

def heal_loop(interval=30):
    with open(MANIFEST) as f:
        m = json.load(f)
    
    log('Self-healing daemon started')
    while True:
        for name in m['dependency_order']:
            svc = m['services'].get(name, {})
            port = svc.get('port')
            cmd = svc.get('restart_cmd')
            if not port: continue
            
            if not port_up(port):
                log(f'[DOWN] {name}:{port} - attempting restart')
                if cmd:
                    try:
                        safe_popen(cmd, shell=True)
                        log(f'[HEAL] {name} restart command sent')
                        time.sleep(5)
                        if port_up(port):
                            log(f'[OK] {name} recovered on :{port}')
                        else:
                            log(f'[FAIL] {name} still down after restart')
                    except Exception as e:
                        log(f'[ERROR] {name} restart failed: {e}')
                else:
                    log(f'[SKIP] {name} has no restart command')
        time.sleep(interval)

if __name__ == '__main__':
    heal_loop()
