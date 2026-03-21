# NovaX Voice Server v2 — PowerShell STT + edge-tts TTS
# Runs in visible window for audio access
import http.server
import json
import sys
import os
import threading
import subprocess
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))

PORT = 9802
CREATE_NO_WINDOW = 0  # DO NOT use CREATE_NO_WINDOW — need audio access

def ps_listen(timeout=5):
    """Use PowerShell System.Speech.Recognition to listen and transcribe."""
    ps_code = f"""
Add-Type -AssemblyName System.Speech
$rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$rec.SetInputToDefaultAudioDevice()
$grammar = New-Object System.Speech.Recognition.DictationGrammar
$rec.LoadGrammar($grammar)
$result = $rec.Recognize([TimeSpan]::FromSeconds({timeout}))
if ($result) {{
    Write-Output "$($result.Text)|$($result.Confidence)"
}} else {{
    Write-Output "|0"
}}
$rec.Dispose()
"""
    try:
        r = subprocess.run(
            ["powershell", "-Command", ps_code],
            capture_output=True, text=True, timeout=timeout + 10
        )
        parts = r.stdout.strip().split("|")
        text = parts[0] if parts else ""
        conf = float(parts[1]) if len(parts) > 1 else 0
        return text, conf
    except Exception as e:
        return "", 0


def edge_speak(text):
    """Speak using edge-tts with neural voice."""
    try:
        from voice import speak
        speak(text, blocking=True)
    except Exception as e:
        # Fallback to System.Speech — pass text via env var to prevent injection
        ps_code = 'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.SelectVoice("Microsoft Zira Desktop"); $s.Speak($env:NOVA_SPEAK_TEXT)'
        subprocess.run(
            ["powershell", "-Command", ps_code],
            env={**os.environ, "NOVA_SPEAK_TEXT": text[:800]},
            timeout=30
        )


class VoiceHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": 1, "service": "nova-voice-v2", "port": PORT})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/speak":
            text = body.get("text", "")
            if text:
                threading.Thread(target=edge_speak, args=(text,), daemon=True).start()
                self._json(200, {"ok": 1, "spoke": len(text)})
            else:
                self._json(400, {"ok": -1, "error": "no text"})

        elif self.path == "/listen":
            timeout = min(int(body.get("timeout", 5)), 30)
            print(f"[Voice] Listening for {timeout}s...")
            text, conf = ps_listen(timeout)
            if text:
                print(f"[Voice] Heard: {text} (conf: {conf:.2f})")
                self._json(200, {"ok": 1, "text": text, "confidence": conf})
            else:
                print("[Voice] Nothing heard")
                self._json(200, {"ok": 0, "text": "", "confidence": 0})

        elif self.path == "/full-loop":
            timeout = min(int(body.get("timeout", 5)), 30)
            print(f"[Voice] Full loop: listening {timeout}s...")

            # Step 1: Listen
            text, conf = ps_listen(timeout)
            if not text:
                print("[Voice] Nothing heard")
                self._json(200, {"ok": 0, "text": "", "response": ""})
                return

            print(f"[Voice] Heard: {text}")

            # Step 2: Query AI
            try:
                qbody = json.dumps({"prompt": text + ". Plain text only. No markdown."}).encode()
                req = urllib.request.Request(
                    "http://127.0.0.1:9878/api/v1/query",
                    data=qbody, headers={"Content-Type": "application/json"}
                )
                resp = urllib.request.urlopen(req, timeout=15)
                raw = resp.read().decode()
                try:
                    d = json.loads(raw)
                    reply = d.get("response", "") or d.get("reply", "")
                except Exception:
                    reply = raw[:500]
            except Exception as e:
                reply = f"AI query failed: {e}"

            print(f"[Voice] AI: {reply[:100]}")

            # Step 3: Speak
            threading.Thread(target=edge_speak, args=(reply,), daemon=True).start()

            self._json(200, {"ok": 1, "text": text, "response": reply, "confidence": conf})

        else:
            self._json(404, {"error": "not found"})


print(f"NovaX Voice Server v2 on port {PORT}")
print("Using: PowerShell System.Speech (STT) + edge-tts (TTS)")
print("Endpoints: /speak, /listen, /full-loop, /health")
httpd = http.server.HTTPServer(("127.0.0.1", PORT), VoiceHandler)
httpd.serve_forever()
