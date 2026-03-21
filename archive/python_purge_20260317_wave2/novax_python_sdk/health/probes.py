"""Health probes - check if services are alive."""
import urllib.request, socket, subprocess

def probe_http(url, timeout=5):
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return r.status == 200
    except: return False

def probe_port(host, port, timeout=3):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except: return False

def probe_process(name):
    try:
        r = subprocess.run(f'tasklist /FI "IMAGENAME eq {name}" /NH',
                         shell=True, capture_output=True, text=True, timeout=5)
        return name.lower() in r.stdout.lower()
    except: return False

def probe_ollama(): return probe_http("http://127.0.0.1:11434/api/tags")
def probe_brain(): return probe_port("localhost", 9990)
def probe_bridge(): return probe_port("localhost", 9999)
