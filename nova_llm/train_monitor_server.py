"""NovaX LLM Training Monitor — HTTP API on port 9802"""
import http.server, json, os

LOG = "C:/NovaX/nova_llm/training_log.json"
PORT = 9802
TOTAL = 20000

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Origin")
        self.send_header("Access-Control-Max-Age", "3600")
        self.send_header("Cache-Control", "no-cache, no-store")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_log(self):
        try:
            with open(LOG, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def do_GET(self):
        log = self._read_log()

        if self.path in ("/health", "/status"):
            self._json(200, {
                "status": "ok", "trit": 1,
                "service": "nova-train-monitor",
                "port": PORT, "log_entries": len(log),
            })

        elif self.path == "/train/status":
            if not log:
                self._json(200, {"trit": 0, "status": "waiting"})
                return
            last = log[-1]
            step = last.get("step", 0)
            sps = last.get("steps_per_sec", 0)
            eta = (TOTAL - step) / max(sps, 0.001)
            best = min(log, key=lambda x: x.get("loss", 999))
            trend = [{"step": e["step"], "loss": e["loss"]} for e in log[-5:]]
            self._json(200, {
                "trit": 1,
                "status": "done" if step >= TOTAL else "training",
                "done": 1 if step >= TOTAL else -1,
                "step": step, "total_steps": TOTAL,
                "percent": round(step / TOTAL * 100, 1),
                "loss": last.get("loss", 0),
                "perplexity": last.get("perplexity", 0),
                "steps_per_sec": sps,
                "tokens_per_sec": round(sps * 4 * 512),
                "epoch": last.get("epoch", 0),
                "lr": last.get("lr", 0),
                "elapsed_sec": last.get("elapsed_sec", 0),
                "eta_hours": int(eta // 3600),
                "eta_minutes": int((eta % 3600) // 60),
                "best_loss": best.get("loss", 0),
                "best_step": best.get("step", 0),
                "trend": trend, "log_entries": len(log),
            })

        elif self.path == "/train/history":
            pts = [{"step": e["step"], "loss": e["loss"],
                    "ppl": e.get("perplexity", 0)} for e in log]
            self._json(200, {"trit": 1, "points": pts, "total": len(log)})

        else:
            self._json(404, {"error": "not found"})

if __name__ == "__main__":
    s = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Training monitor on port {PORT}")
    s.serve_forever()
