#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
from faster_whisper import WhisperModel
import json, tempfile, os, sys, time

PORT = 9876
MODEL_SIZE = "base.en"

print(f"[Nova STT] Loading Whisper model '{MODEL_SIZE}'...")
t0 = time.time()
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
print(f"[Nova STT] Model loaded in {time.time()-t0:.1f}s")

class STTHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors(); self.end_headers()
            self.wfile.write(json.dumps({"status":"ok","model":MODEL_SIZE,"port":PORT,"engine":"faster-whisper"}).encode())
        else: self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path != '/transcribe':
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get('Content-Length', 0))
        if n == 0: self._resp({"text":"","error":"No audio"}); return
        data = self.rfile.read(n)
        ct = self.headers.get('Content-Type', '')
        sx = '.webm' if 'webm' in ct else '.wav' if 'wav' in ct else '.ogg' if 'ogg' in ct else '.webm'
        tp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=sx, delete=False) as f:
                f.write(data); tp = f.name
            t0 = time.time()
            segs, info = model.transcribe(tp, beam_size=5, language="en",
                vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200))
            txt = " ".join([s.text for s in segs]).strip()
            dt = time.time() - t0
            if txt: print(f"[Nova STT] '{txt}' ({dt:.2f}s)")
            self._resp({"text":txt,"language":"en","duration":round(dt,2)})
        except Exception as e:
            print(f"[Nova STT] Error: {e}"); self._resp({"text":"","error":str(e)})
        finally:
            if tp and os.path.exists(tp):
                try: os.unlink(tp)
                except: pass
    def _resp(self, d):
        b = json.dumps(d).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self._cors(); self.end_headers(); self.wfile.write(b)

if __name__ == '__main__':
    print(f"[Nova STT] Port {PORT} | faster-whisper ({MODEL_SIZE}) | No cloud. No flags.")
    HTTPServer(('0.0.0.0', PORT), STTHandler).serve_forever()