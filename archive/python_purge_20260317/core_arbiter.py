# arbiter.py — Action Arbiter: executes task plans via the ActionBus
# Orchestrator calls arbiter.execute_plan(actions) for /step, /run, /ncp/apply
# Each action is a dict with {driver, action, params} — routed to bus.execute()

import time


class Arbiter:
    """Arbiter — executes action plans through the ActionBus and tracks decisions."""

    def __init__(self, bus=None):
        self.decisions = []
        self.bus = bus

    def execute_plan(self, actions, source="arbiter", **kwargs):
        """
        Execute a list of actions via the ActionBus.
        Each action: {"driver": "terminal", "action": "run_command", "params": {"cmd": "..."}}
        Returns list of result dicts with {ok, output, error, driver, action}.
        """
        results = []
        for act in (actions or []):
            driver = act.get("driver", "terminal")
            action = act.get("action", "run_command")
            params = act.get("params", {})
            start = time.time()

            if self.bus:
                r = self.bus.execute(driver, action, params)
                result = {
                    "ok": r.ok if hasattr(r, "ok") else bool(r),
                    "output": r.output if hasattr(r, "output") else str(r),
                    "error": r.error if hasattr(r, "error") else "",
                    "driver": driver,
                    "action": action,
                    "duration_ms": round((time.time() - start) * 1000),
                }
            else:
                result = {
                    "ok": False,
                    "output": "",
                    "error": "No ActionBus connected",
                    "driver": driver,
                    "action": action,
                    "duration_ms": 0,
                }

            results.append(result)
            self.decisions.append({
                "source": source,
                "action": f"{driver}.{action}",
                "ok": result["ok"],
                "time": time.time(),
            })

        return results

    def arbitrate(self, responses, context=None):
        """Pick best response from multiple AI responses."""
        if not responses:
            return {"response": "", "confidence": 0}
        # Simple heuristic: pick longest non-empty response
        best = None
        for r in responses:
            if isinstance(r, dict):
                text = r.get("response", "") or r.get("text", "") or ""
            else:
                text = str(r)
            if best is None or len(text) > len(best.get("response", "")):
                best = r if isinstance(r, dict) else {"response": text}
        return best or responses[0]

    def get_decisions(self, limit=50):
        return self.decisions[-limit:]
