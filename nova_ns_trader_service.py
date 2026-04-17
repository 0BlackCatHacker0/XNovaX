"""
NovaX N-S Trader Service — Port 9940
Navier-Stokes Autonomous Trading Engine

Endpoints:
  GET  /health              — Service health
  GET  /status              — Trader status (balance, position, PnL)
  GET  /signal              — Current N-S trading signal
  GET  /backtest            — Run backtest and return results
  POST /wallet/generate     — Generate new Base chain wallet
  GET  /wallet/balance      — Check wallet balance
  POST /trade/start         — Start autonomous trading
  POST /trade/stop          — Stop autonomous trading
  POST /trade/tick          — Execute single trading tick
  POST /kill                — Engage kill switch
  POST /unkill              — Disengage kill switch
  GET  /trades              — Recent trade log
  GET  /regimes             — Current N-S regime analysis
"""

import json
import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

# Add ns_trader to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core", "ns_trader"))

from ns_data import get_full_dataset, dataset_summary, get_realtime_price, fetch_cryptocompare_hourly
from ns_model import NSTradingModel
from ns_wallet import generate_wallet, get_wallet_info, get_balance, get_trade_log, withdraw
from ns_dex import get_quote, engage_kill_switch, disengage_kill_switch, is_killed
from ns_songbird_dex import get_sgb_balance, get_quote as sgb_get_quote, get_best_pair, unwrap_wsgb, wrap_sgb
from ns_backtest import NSBacktester
from ns_autonomous import NSAutonomousTrader, DEFAULT_CONFIG
from ns_swarm import TradingSwarm, SWARM_CONFIG
from ns_god_mode import GodMode, get_god_mode, GOD_SWARM_CONFIG, GOD_SCANNER_CONFIG
from ns_berserker import BerserkerEngine
from ns_base_scanner import BaseChainScanner

PORT = 9943
trader_instance = None
trader_thread = None
swarm_instance = None
swarm_thread = None
god_instance = None
god_thread = None


class NSTraderHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def _respond(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def do_OPTIONS(self):
        self._respond({})

    def _serve_file(self, filepath, content_type="text/html"):
        """Serve a static file directly."""
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        params = parse_qs(urlparse(self.path).query)

        # Serve dashboard directly (same-origin = no CORS issues)
        if path == "/dashboard" or path == "/":
            self._serve_file(os.path.join(os.path.dirname(__file__), "web", "nova_ns_trader.html"))
            return

        try:
            if path == "/health":
                god_running = god_instance.running if god_instance else False
                swarm_running = swarm_instance.running if swarm_instance else False
                trader_running = trader_instance.running if trader_instance else False
                mode = "GOD_MODE" if god_running else "SWARM" if swarm_running else "SINGLE" if trader_running else "IDLE"
                self._respond({
                    "status": "alive",
                    "service": "ns_trader",
                    "port": PORT,
                    "mode": mode,
                    "kill_switch": is_killed(),
                    "trading": god_running or swarm_running or trader_running,
                })

            elif path == "/status":
                if god_instance and god_instance.running:
                    self._respond(god_instance.status())
                elif swarm_instance and swarm_instance.running:
                    self._respond(swarm_instance.status())
                elif trader_instance and trader_instance.running:
                    self._respond(trader_instance.status())
                else:
                    wallet = get_wallet_info()
                    # Use Songbird-specific balance if on Songbird chain
                    if wallet.get("chain") == "songbird":
                        balance = get_sgb_balance()
                    else:
                        balance = get_balance()
                    self._respond({
                        "running": False,
                        "kill_switch": is_killed(),
                        "wallet": wallet,
                        "balance": balance,
                    })

            elif path == "/signal":
                coin = params.get("coin", ["songbird"])[0]
                df = get_full_dataset(coin, "hourly")
                model = NSTradingModel()
                signal = model.get_current_signal(df)
                signal["realtime"] = get_realtime_price(coin)
                self._respond(signal)

            elif path == "/backtest":
                coin = params.get("coin", ["bitcoin"])[0]
                capital = float(params.get("capital", ["100"])[0])
                period = params.get("period", ["daily"])[0]
                start = params.get("start", [None])[0]

                df = get_full_dataset(coin, period)
                if start:
                    df = df[df.index >= start].copy()

                model = NSTradingModel()
                signals = model.generate_signals(df)
                bt = NSBacktester(initial_capital=capital)
                result = bt.run(signals, price_col="close")
                self._respond(result.summary())

            elif path == "/wallet/balance":
                wallet = get_wallet_info()
                if wallet.get("chain") == "songbird":
                    self._respond(get_sgb_balance())
                else:
                    self._respond(get_balance())

            elif path == "/flare/balance":
                try:
                    from web3 import Web3 as W3
                    fw3 = W3(W3.HTTPProvider("https://flare-api.flare.network/ext/C/rpc"))
                    wallet = get_wallet_info()
                    addr = W3.to_checksum_address(wallet["address"])
                    flr_wei = fw3.eth.get_balance(addr)
                    flr = float(W3.from_wei(flr_wei, "ether"))
                    # Get FLR price
                    import requests as req
                    pr = req.get("https://min-api.cryptocompare.com/data/pricemultifull",
                                 params={"fsyms": "FLR", "tsyms": "USD"}, timeout=10).json()
                    flr_price = pr.get("RAW", {}).get("FLR", {}).get("USD", {}).get("PRICE", 0)
                    self._respond({
                        "flr": round(flr, 4),
                        "usd_value": round(flr * flr_price, 4),
                        "flr_price": flr_price,
                        "chain": "Flare",
                    })
                except Exception as e:
                    self._respond({"error": str(e)})

            elif path == "/god/status":
                if god_instance:
                    self._respond(god_instance.status())
                else:
                    self._respond({"mode": "GOD_MODE", "running": False})

            elif path == "/god/portfolio":
                god = god_instance or get_god_mode()
                self._respond(god.get_portfolio())

            elif path == "/base/scan":
                god = god_instance or get_god_mode()
                self._respond(god.scan_base())

            elif path == "/base/rankings":
                god = god_instance or get_god_mode()
                cached = god._cached_base_top5
                self._respond({
                    "scanned": len(cached),
                    "rankings": cached,
                })

            elif path == "/xrp/status":
                god = god_instance or get_god_mode()
                self._respond(god.xrp_tracker.status())

            elif path == "/berserker/status":
                god = god_instance or get_god_mode()
                self._respond(god.berserker.status())

            elif path == "/trades":
                limit = int(params.get("limit", ["50"])[0])
                self._respond({"trades": get_trade_log(limit)})

            elif path == "/regimes":
                coin = params.get("coin", ["songbird"])[0]
                df = get_full_dataset(coin, "hourly")
                model = NSTradingModel()
                signals = model.generate_signals(df)
                regime_counts = signals["regime"].value_counts().to_dict()
                recent_re = signals["reynolds"].tail(24).tolist()
                self._respond({
                    "current_regime": str(signals["regime"].iloc[-1]),
                    "current_reynolds": float(signals["reynolds"].iloc[-1]),
                    "regime_distribution": regime_counts,
                    "reynolds_24h": [round(r, 2) for r in recent_re],
                })

            else:
                self._respond({"error": f"Unknown path: {path}"}, 404)

        except Exception as e:
            self._respond({"error": str(e)}, 500)

    def do_POST(self):
        global trader_instance, trader_thread, swarm_instance, swarm_thread, god_instance, god_thread
        path = urlparse(self.path).path

        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length:
            body = json.loads(self.rfile.read(content_length))

        try:
            if path == "/wallet/generate":
                chain = body.get("chain", "base")
                self._respond(generate_wallet(chain))

            elif path == "/trade/start":
                if trader_instance and trader_instance.running:
                    self._respond({"error": "Trader already running"})
                    return

                config = {**DEFAULT_CONFIG, **body}
                trader_instance = NSAutonomousTrader(config)
                trader_thread = threading.Thread(
                    target=trader_instance.run, daemon=True, name="ns-trader"
                )
                trader_thread.start()
                self._respond({"status": "started", "config": config})

            elif path == "/trade/stop":
                if trader_instance:
                    trader_instance.stop()
                    self._respond({"status": "stopped"})
                else:
                    self._respond({"error": "No trader running"})

            elif path == "/trade/tick":
                if not trader_instance:
                    trader_instance = NSAutonomousTrader(DEFAULT_CONFIG)
                result = trader_instance.tick()
                self._respond(result)

            elif path == "/swarm/start":
                if swarm_instance and swarm_instance.running:
                    self._respond({"error": "Swarm already running"})
                    return
                # Stop single trader if running
                if trader_instance and trader_instance.running:
                    trader_instance.stop()
                config = {**SWARM_CONFIG, **body}
                swarm_instance = TradingSwarm(config)
                swarm_thread = threading.Thread(
                    target=swarm_instance.run, daemon=True, name="ns-swarm"
                )
                swarm_thread.start()
                self._respond({"status": "swarm_started", "scouts": len(swarm_instance.scouts),
                               "poll_interval": config["poll_interval"]})

            elif path == "/swarm/stop":
                if swarm_instance:
                    swarm_instance.stop()
                    self._respond({"status": "swarm_stopped"})
                else:
                    self._respond({"error": "No swarm running"})

            elif path == "/swarm/scan":
                if not swarm_instance:
                    swarm_instance = TradingSwarm(SWARM_CONFIG)
                results = swarm_instance.scan_all()
                signal, score, _ = swarm_instance.aggregate(results)
                self._respond({
                    "consensus": {1: "BUY", 0: "HOLD", -1: "SELL"}.get(signal, "?"),
                    "score": round(score, 3),
                    "scouts": {n: {"signal": r.get("signal", 0),
                                   "confidence": round(r.get("confidence", 0), 3),
                                   "edge": r.get("edge", "?")}
                               for n, r in results.items()},
                })

            elif path == "/swarm/status":
                if swarm_instance:
                    self._respond(swarm_instance.status())
                else:
                    self._respond({"running": False, "mode": "SWARM"})

            elif path == "/god/start":
                if god_instance and god_instance.running:
                    self._respond({"error": "God Mode already running"})
                    return
                # Stop everything else first
                if trader_instance and trader_instance.running:
                    trader_instance.stop()
                if swarm_instance and swarm_instance.running:
                    swarm_instance.stop()
                god_instance = GodMode()
                result = god_instance.start()
                self._respond(result)

            elif path == "/god/stop":
                if god_instance:
                    result = god_instance.stop()
                    self._respond(result)
                else:
                    self._respond({"error": "God Mode not running"})

            elif path == "/kill":
                reason = body.get("reason", "manual")
                if trader_instance:
                    trader_instance.stop()
                if swarm_instance:
                    swarm_instance.stop()
                if god_instance:
                    god_instance.stop()
                self._respond(engage_kill_switch(reason))

            elif path == "/unkill":
                self._respond(disengage_kill_switch())

            elif path == "/quote":
                amount = body.get("amount", 10)
                direction = body.get("direction", "buy")
                token = body.get("token")
                if token:
                    self._respond(sgb_get_quote(amount, token, direction))
                else:
                    self._respond(get_quote(amount, direction))

            elif path == "/unwrap":
                amount = body.get("amount", 100)
                self._respond(unwrap_wsgb(amount))

            elif path == "/wrap":
                amount = body.get("amount", 100)
                self._respond(wrap_sgb(amount))

            elif path == "/withdraw":
                to_address = body.get("to_address") or body.get("address")
                amount = body.get("amount", "max")
                chain = body.get("chain")
                if not to_address:
                    self._respond({"error": "to_address is required"}, 400)
                    return
                self._respond(withdraw(to_address, amount, chain))

            else:
                self._respond({"error": f"Unknown path: {path}"}, 404)

        except Exception as e:
            self._respond({"error": str(e)}, 500)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a new thread so HiveMind queries don't block."""
    daemon_threads = True


def start_service():
    server = ThreadedHTTPServer(("127.0.0.1", PORT), NSTraderHandler)
    print(f"[NS-Trader] Service alive on :{PORT}")
    print(f"[NS-Trader] Endpoints: /health /status /signal /backtest /wallet /trades /regimes")
    server.serve_forever()


if __name__ == "__main__":
    start_service()
