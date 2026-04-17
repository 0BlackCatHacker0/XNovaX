"""Apply health_patch to the live running orchestrator via its /api/exec endpoint.

SECURITY NOTE: The previous version fell back to POSTing arbitrary shell commands
to /api/execute when /api/exec was unavailable. That fallback has been removed —
if /api/exec is not working, the health patch should be applied at boot by
boot_orchestrator.py importing health_patch directly (see core/boot_orchestrator.py
around line 59).
"""
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
    print("Health patch not applied live.")
    print("The patch is also applied at boot by core/boot_orchestrator.py;")
    print("restart the orchestrator if live patching failed.")
