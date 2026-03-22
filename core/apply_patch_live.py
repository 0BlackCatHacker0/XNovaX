"""Apply health_patch to the live running orchestrator via its /api/exec endpoint."""
import urllib.request
import json

url = "http://127.0.0.1:9999/api/exec"
payload = json.dumps({
    "code": "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); import health_patch"
}).encode("utf-8")

req = urllib.request.Request(url, data=payload, method="POST")
req.add_header("Content-Type", "application/json")

try:
    resp = urllib.request.urlopen(req, timeout=10)
    body = resp.read().decode()
    print(f"Status: {resp.status}")
    print(f"Response: {body}")
except Exception as e:
    print(f"Error: {e}")
    # Try alternative: directly import and patch in this process's context
    # by connecting to the orchestrator's Python process
    print("\nTrying direct patch via import...")
    # The orchestrator runs as __main__ from the .pyc
    # We can't directly access it from another process
    # Let's try the /execute endpoint instead
    try:
        url2 = "http://127.0.0.1:9999/api/execute"
        payload2 = json.dumps({
            "cmd": "python C:\\NovaX\\core\\apply_patch_internal.py"
        }).encode("utf-8")
        req2 = urllib.request.Request(url2, data=payload2, method="POST")
        req2.add_header("Content-Type", "application/json")
        resp2 = urllib.request.urlopen(req2, timeout=15)
        print(f"Execute status: {resp2.status}")
        print(f"Execute response: {resp2.read().decode()}")
    except Exception as e2:
        print(f"Execute also failed: {e2}")
