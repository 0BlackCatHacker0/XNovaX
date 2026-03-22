"""NovaX Neural Voice Server -- edge-tts powered
Serves audio files that the browser plays directly.
Port 9801 -- lightweight HTTP server.
"""
import http.server, json, asyncio, os, time, hashlib, threading

PORT = 9801
AUDIO_DIR = "C:\\NovaX\\tmp\\voice"
os.makedirs(AUDIO_DIR, exist_ok=True)

VOICE = "en-US-AvaNeural"
RATE = "+0%"
speak_count = 0
start_time = time.time()

class VoiceHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok", "trit": 1, "voice": VOICE,
                "speak_count": speak_count,
                "uptime": int(time.time() - start_time)
            }).encode())
        elif self.path.startswith("/audio/"):
            fname = os.path.basename(self.path.split("/audio/")[-1])
            fpath = os.path.join(AUDIO_DIR, fname)
            if not os.path.abspath(fpath).startswith(os.path.abspath(AUDIO_DIR)):
                self.send_response(403)
                self._cors()
                self.end_headers()
                return
            if os.path.exists(fpath):
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(os.path.getsize(fpath)))
                self.end_headers()
                with open(fpath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self._cors()
                self.end_headers()
        elif self.path == "/voices":
            try:
                voices = asyncio.run(self._list_voices())
            except Exception:
                voices = [{"name": "en-US-AvaNeural", "friendly": "Ava (Female)", "gender": "Female"}]
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(voices).encode())
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()

    async def _list_voices(self):
        import edge_tts
        vs = await edge_tts.list_voices()
        return [{"name": v["ShortName"], "friendly": v["FriendlyName"], "gender": v["Gender"]}
                for v in vs if "en-" in v["ShortName"]]

    def do_POST(self):
        global speak_count, VOICE, RATE
        if self.path == "/speak":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length > 0 else {}
            text = body.get("text", "")
            voice = body.get("voice", VOICE)
            rate = body.get("rate", RATE)

            if not text:
                self.send_response(400)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "no text"}).encode())
                return

            # Generate unique filename
            h = hashlib.md5(f"{text}{voice}{rate}".encode()).hexdigest()[:12]
            fname = f"nova_{h}.mp3"
            fpath = os.path.join(AUDIO_DIR, fname)

            # Check cache
            if not os.path.exists(fpath):
                try:
                    asyncio.run(self._generate(text, voice, rate, fpath))
                except Exception as e:
                    self.send_response(500)
                    self._cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e), "trit": -1}).encode())
                    return

            speak_count += 1
            audio_url = f"http://127.0.0.1:{PORT}/audio/{fname}"

            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": 1, "trit": 1,
                "audio_url": audio_url,
                "voice": voice, "chars": len(text),
                "cached": os.path.exists(fpath)
            }).encode())

        elif self.path == "/voice/query":
            # Full voice pipeline: text prompt -> AI query -> TTS audio
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length > 0 else {}
            prompt = body.get("text", "") or body.get("prompt", "")
            if not prompt:
                self.send_response(400)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": -1, "error": "no text"}).encode())
                return
            # Step 1: Query AI via orchestrator, fallback to cloud router
            reply = ""
            model = "unknown"
            try:
                import urllib.request
                qbody = json.dumps({"text": prompt, "mode": "speed"}).encode()
                req = urllib.request.Request(
                    "http://127.0.0.1:9999/think",
                    data=qbody,
                    headers={"Content-Type": "application/json"}
                )
                resp = urllib.request.urlopen(req, timeout=20)
                d = json.loads(resp.read().decode())
                reply = d.get("reply", "") or d.get("response", "")
                model = d.get("model", "nova")
            except Exception:
                pass
            if not reply:
                try:
                    qbody = json.dumps({"prompt": prompt + ". Plain text only. No markdown."}).encode()
                    req = urllib.request.Request(
                        "http://127.0.0.1:9878/api/v1/query",
                        data=qbody,
                        headers={"Content-Type": "application/json"}
                    )
                    resp = urllib.request.urlopen(req, timeout=20)
                    d = json.loads(resp.read().decode())
                    reply = d.get("response", "") or d.get("reply", "")
                    model = d.get("model", d.get("provider", "cloud"))
                except Exception as e:
                    reply = "AI query failed: " + str(e)
            # Step 2: Generate TTS for the reply
            audio_url = ""
            if reply:
                clean = reply[:1000]
                h = hashlib.md5((clean + VOICE + RATE).encode()).hexdigest()[:12]
                fname = "nova_" + h + ".mp3"
                fpath = os.path.join(AUDIO_DIR, fname)
                if not os.path.exists(fpath):
                    try:
                        asyncio.run(self._generate(clean, VOICE, RATE, fpath))
                    except Exception:
                        pass
                if os.path.exists(fpath):
                    audio_url = "http://127.0.0.1:" + str(PORT) + "/audio/" + fname
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": 1, "trit": 1,
                "prompt": prompt,
                "reply": reply,
                "model": model,
                "audio_url": audio_url
            }).encode())

        elif self.path == "/set-voice":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length > 0 else {}
            VOICE = body.get("voice", VOICE)
            RATE = body.get("rate", RATE)
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": 1, "voice": VOICE, "rate": RATE}).encode())
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()

    async def _generate(self, text, voice, rate, output_path):
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_path)

print(f"NovaX Neural Voice Server v1.1 on port {PORT}")
print(f"Voice: {VOICE} | Audio dir: {AUDIO_DIR}")
print("Endpoints: /speak, /voice/query, /set-voice, /voices, /audio/*, /health")
server = http.server.HTTPServer(("127.0.0.1", PORT), VoiceHandler)
server.serve_forever()
